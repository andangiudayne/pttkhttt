"""OrderService — checkout(cart) biến đổi Cart → Order (CartItem → OrderItem), đúng mô hình A03;
view_order() phục vụ UC09 Theo dõi đơn; mọi bước ghi của checkout nằm trong MỘT giao dịch (NFR06)."""
from __future__ import annotations
from contextlib import nullcontext
from chobay.dao.interfaces import CartDAO, OrderDAO, ProductDAO, CustomerDAO
from chobay.model.customer import Customer, CustomerNew
from chobay.model.staff import Staff
from chobay.model.order import Order, OrderItem
from chobay.model.enums import DeliveryMode, OrderStatus, PaymentStatus, DeliveryPreference, ShippingStatus
from chobay.ai.delivery.rules import DeliveryRequest, Weather
from .payment_service import PaymentService
from .shipping_service import ShippingService
from .weather_service import IWeatherService, WeatherStub


class CheckoutError(Exception):
    pass


class StockError(CheckoutError):
    """Biểu đồ hoạt động 2.5: “Đủ hàng? — không” → khách quay lại sửa giỏ / chọn món thay thế."""


class OrderService:
    def __init__(self, cart_dao: CartDAO, order_dao: OrderDAO, product_dao: ProductDAO, customer_dao: CustomerDAO,
                 payment_service: PaymentService, shipping_service: ShippingService, transaction=None,
                 weather_service: IWeatherService | None = None):
        self.cart_dao, self.order_dao, self.product_dao = cart_dao, order_dao, product_dao
        self.customer_dao, self.payments, self.shipping = customer_dao, payment_service, shipping_service
        self.transaction = transaction or nullcontext          # Container truyền db.transaction
        self.weather = weather_service or WeatherStub()           # IWeatherService — thời tiết hiện tại cho UC06

    @staticmethod
    def _address(customer: Customer, address_id):
        """Địa chỉ phải thuộc chính khách hàng (không giao tới địa chỉ của người khác)."""
        address = next((a for a in customer.addresses if a.address_id == address_id), None)
        if address is None:
            raise CheckoutError("Địa chỉ giao không hợp lệ — hãy chọn một địa chỉ của bạn")
        return address

    @staticmethod
    def check_stock(cart) -> None:
        """Kiểm tra tồn kho từng món (bước đầu của biểu đồ hoạt động Đặt hàng)."""
        short = [it.product.name for it in cart.items if not it.product.is_available(it.quantity)]
        if short:
            raise StockError(f"{', '.join(short)} không đủ hàng — hãy sửa số lượng hoặc chọn món khác")

    def weather_for(self, customer: Customer, address_id: int) -> Weather:
        """Thời tiết tại tọa độ địa chỉ giao (IWeatherService — Open-Meteo khi chạy web)."""
        a = self._address(customer, address_id)
        return self.weather.current(a.latitude, a.longitude)

    def quote(self, customer: Customer, address_id: int, pref: DeliveryPreference, weather: Weather | None = None):
        """Bước xem trước: AI đề xuất phương thức giao cho giỏ hiện tại (thời tiết lấy từ IWeatherService nếu không truyền)."""
        weather = weather or self.weather_for(customer, address_id)
        cart = self.cart_dao.get_cart(customer)
        address = self._address(customer, address_id)
        return self.shipping.plan(DeliveryRequest(cart.items, address, weather), pref)

    def checkout(self, customer: Customer, address_id: int, method: str, pref: DeliveryPreference,
                 weather: Weather | None = None, card_number: str = "", mode: DeliveryMode | None = None,
                 expiry: str = "", cvv: str = "", wallet: str = "") -> Order:
        cart = self.cart_dao.get_cart(customer)
        if cart.is_empty():
            raise CheckoutError("Giỏ hàng trống")
        self.check_stock(cart)                                 # BR-O1: chỉ đặt hàng còn tồn kho
        address = self._address(customer, address_id)
        weather = weather or self.weather.current(address.latitude, address.longitude)   # thời tiết tại nơi giao
        try:
            payment = self.payments.create(method, 0, card_number, expiry, cvv, wallet)   # kiểm tra trước khi gọi AI
        except ValueError as exc:
            raise CheckoutError(str(exc)) from exc
        try:
            decision = self.shipping.plan(DeliveryRequest(cart.items, address, weather), pref, mode)   # mode: khách tự chọn
        except ValueError as exc:
            raise CheckoutError(str(exc)) from exc
        if decision.chosen is None:
            raise CheckoutError("Không có phương thức giao phù hợp")

        order = Order(0, customer.customer_id, address_id,
                      [OrderItem(i.product, i.quantity, i.product.price) for i in cart.items],  # CartItem → OrderItem, giá lúc mua
                      preference=pref)
        order.shipping_fee = decision.chosen.fee
        order.discount = self.discount_for(customer, order.subtotal())   # ưu đãi không làm tổng tiền âm
        if isinstance(customer, CustomerNew):
            customer.welcome_voucher = 0                               # voucher chào mừng dùng 1 lần

        payment.amount = order.total()
        payment = self.payments.process(payment)
        if payment.status == PaymentStatus.FAILED:            # BR-O2: không xác nhận đơn khi thanh toán lỗi
            raise CheckoutError("Thanh toán bị từ chối — vui lòng chọn phương thức khác")
        order.status = OrderStatus.PAID if payment.status == PaymentStatus.PAID else OrderStatus.PACKING
        order.payment = payment

        try:
            with self.transaction():                          # NFR06: tạo đơn + thanh toán + trừ kho + giao = 1 giao dịch
                self.order_dao.create_order(order)
                self.order_dao.save_payment(order.order_id, payment)
                for it in order.items:                        # BR-O3: trừ tồn kho sau khi xác nhận
                    self.product_dao.update_stock(it.product.product_id, -it.quantity)
                self.shipping.create_shipping(order, decision)
                self.cart_dao.clear(cart)                     # giỏ rỗng sau checkout
                customer.loyalty_points += order.total() // 10_000
                self.customer_dao.update_cust(customer)
        except Exception as exc:                              # ROLLBACK: không có đơn dở dang, giỏ còn nguyên
            if payment.status == PaymentStatus.PAID:
                self.payments.refund(payment)                 # bù trừ: hoàn tiền giao dịch đã ủy quyền
            raise CheckoutError(f"Không lưu được đơn ({type(exc).__name__}) — giỏ hàng được giữ nguyên") from exc
        return order

    # ---------- UC09 Xem / theo dõi đơn hàng ----------
    @staticmethod
    def discount_for(customer: Customer, subtotal: int) -> int:
        """Ưu đãi của khách: VIP giảm theo %, khách mới có voucher chào mừng; không vượt quá tiền hàng."""
        d = int(subtotal * customer.discount_rate())
        if isinstance(customer, CustomerNew) and customer.welcome_voucher:
            d += customer.welcome_voucher
        return min(d, subtotal)

    def view_order(self, order_id: int, customer: Customer | None = None) -> dict | None:
        """Đơn + lô giao + hub + địa chỉ cho trang theo dõi. Có customer → chỉ xem được đơn của chính mình."""
        order = self.order_dao.get_order(order_id)
        if order is None or (customer is not None and order.customer_id != customer.customer_id):
            return None
        shipping = self.shipping.get_by_order(order_id)
        owner = self.customer_dao.get_cust(order.customer_id)
        address = next(a for a in owner.addresses if a.address_id == order.address_id)
        return {"order": order, "s": shipping, "hub": self.shipping.hub_of(shipping), "address": address, "customer": owner}

    def reorder(self, order_id: int, customer: Customer) -> dict:
        """UC04.1 Mua lại: đưa TOÀN BỘ sản phẩm của một đơn cũ (chỉ đơn của chính khách) vào giỏ.
        Số lượng bị giới hạn theo tồn kho hiện tại; món hết hàng được bỏ qua và báo lại cho khách."""
        order = self.order_dao.get_order(order_id)
        if order is None or order.customer_id != customer.customer_id:
            raise LookupError(f"Không có đơn {order_id}")
        added, adjusted, skipped = [], [], []
        with self.transaction():
            cart = self.cart_dao.get_cart(customer)
            for it in order.items:
                product = self.product_dao.get_item(it.product.product_id)          # tồn kho hiện tại, không dùng bản cũ
                in_cart = next((c.quantity for c in cart.items if c.product.product_id == product.product_id), 0)
                room = product.stock - in_cart if product else 0
                if product is None or room <= 0:
                    skipped.append(it.product.name)
                    continue
                qty = min(it.quantity, room)
                self.cart_dao.add_item(cart, product, qty)
                (adjusted if qty < it.quantity else added).append(product.name)
                if qty < it.quantity:
                    adjusted[-1] = f"{product.name} (còn {qty})"
        return {"added": added, "adjusted": adjusted, "skipped": skipped}

    def approve_delivery(self, order_id: int, staff: Staff) -> None:
        """UC15: điều phối viên duyệt chuyến ô tô bay / tàu ngầm (BR-H1). Chỉ vai trò DISPATCHER được duyệt."""
        if staff is None or not staff.can_dispatch():
            raise PermissionError("Chỉ điều phối viên được duyệt chuyến")
        s = self.shipping.get_by_order(order_id)
        if s is None:
            raise LookupError(f"Không có đơn {order_id}")
        self.shipping.approve(s.shipping_id, staff.username)

    def simulate_delivery(self, order_id: int, staff: Staff) -> None:
        """Điều phối viên cho xuất phát; prototype giả lập phương tiện gửi vị trí tới khi giao xong → DELIVERED (UC09, UC17)."""
        if staff is None or not staff.can_dispatch():
            raise PermissionError("Chỉ điều phối viên được cho phương tiện xuất phát")
        v = self.view_order(order_id)
        if v is None:
            raise LookupError(f"Không có đơn {order_id}")
        self.shipping.simulate_progress(order_id, v["address"])     # từ chối nếu chưa duyệt / đã giao
        self.order_dao.update_status(order_id, OrderStatus.DELIVERED)
        self.order_dao.mark_paid(order_id)                          # COD: thu tiền khi giao xong

    def my_orders(self, customer: Customer) -> list[dict]:
        """UC09 — “Đơn mua” của khách: mọi đơn của chính khách, mới nhất trước, kèm lô giao."""
        return [self.view_order(o.order_id, customer) for o in self.order_dao.find_by_customer(customer.customer_id)]

    def dispatch_board(self, status: ShippingStatus | None = None) -> list[dict]:
        """Dữ liệu cho Kênh điều phối: mỗi chuyến kèm đơn, khách, địa chỉ, hub (như view_order, không giới hạn khách)."""
        return [self.view_order(s.order_id) for s in self.shipping.board(status)]

    def dispatch_counts(self) -> dict[str, int]:
        """Số chuyến theo trạng thái cho các ô tổng quan và tab lọc."""
        rows = self.shipping.board()
        return {st.value: sum(1 for s in rows if s.status == st) for st in ShippingStatus} | {"ALL": len(rows)}

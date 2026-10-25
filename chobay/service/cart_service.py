from chobay.dao.interfaces import CartDAO, ProductDAO
from chobay.model.cart import Cart
from chobay.model.customer import Customer


class CartError(Exception):
    """Lỗi nghiệp vụ của giỏ hàng — controller hiển thị thông báo, không trả lỗi 500."""


class OutOfStockError(CartError):
    pass


class CartService:
    def __init__(self, cart_dao: CartDAO, product_dao: ProductDAO):
        self.cart_dao, self.product_dao = cart_dao, product_dao

    def view_cart(self, customer: Customer) -> Cart:
        return self.cart_dao.get_cart(customer)

    def add_to_cart(self, customer: Customer, product_id: int, qty: int = 1) -> Cart:
        if qty < 1:
            raise CartError("Số lượng phải từ 1 trở lên")
        product = self.product_dao.get_item(product_id)
        if product is None:
            raise CartError(f"Sản phẩm {product_id} không tồn tại")
        cart = self.cart_dao.get_cart(customer)
        in_cart = next((i.quantity for i in cart.items if i.product.product_id == product_id), 0)
        if not product.is_available(in_cart + qty):
            raise OutOfStockError(f"{product.name} chỉ còn {product.stock} — không đủ hàng")
        self.cart_dao.add_item(cart, product, qty)
        return self.cart_dao.get_cart(customer)

    def update_quantity(self, customer: Customer, product_id: int, qty: int) -> Cart:
        cart = self.cart_dao.get_cart(customer)
        item = next((it for it in cart.items if it.product.product_id == product_id), None)
        if item is None:
            return cart
        new_qty = min(qty, item.product.stock)            # không vượt tồn kho
        if new_qty <= 0:                                  # SL 0 hoặc sản phẩm đã hết hàng → bỏ khỏi giỏ
            self.cart_dao.remove_item(cart, product_id)
        else:
            item.quantity = new_qty
            self.cart_dao.update_cart(cart)
        return self.cart_dao.get_cart(customer)

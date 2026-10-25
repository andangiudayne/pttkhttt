"""Pop-up Market — Web tạp hóa tích hợp AI tìm kiếm đa phương thức & AI điều phối giao hàng đa phương tiện.
create_app() lắp ráp các tầng theo kiến trúc MVC + DAO (Dependency Injection thủ công)."""
import os
from flask import Flask, flash, redirect, request, url_for
from chobay.dao.database import Database
from chobay.dao.impl.product_dao_impl import ProductDAOImpl
from chobay.dao.impl.customer_dao_impl import CustomerDAOImpl
from chobay.dao.impl.cart_dao_impl import CartDAOImpl
from chobay.dao.impl.order_dao_impl import OrderDAOImpl
from chobay.dao.impl.delivery_dao_impl import ShippingDAOImpl, VehicleDAOImpl
from chobay.dao.impl.search_log_dao_impl import SearchLogDAOImpl
from chobay.dao.impl.staff_dao_impl import StaffDAOImpl
from chobay.ai.search.query_service import QueryService
from chobay.ai.search.speech_service import SpeechService
from chobay.ai.search.image_service import ImageService
from chobay.ai.search.search_service import SearchService
from chobay.ai.search.ranking_service import RankingService
from chobay.ai.delivery.predictors import train_default
from chobay.ai.delivery.dispatcher import DeliveryDispatcher
from chobay.service.cart_service import CartService
from chobay.service.payment_service import PaymentService
from chobay.service.shipping_service import ShippingService
from chobay.service.order_service import OrderService
from chobay.service.catalog_service import CatalogService
from chobay.service.customer_service import CustomerService
from chobay.service.auth_service import AuthService
from chobay.service.weather_service import IWeatherService, OpenMeteoWeatherService, WeatherStub


class Container:
    """Nơi khởi tạo & nối các đối tượng của 3 tầng."""

    def __init__(self, db: Database, weather_service: IWeatherService | None = None):
        self.product_dao = ProductDAOImpl(db)
        self.customer_dao = CustomerDAOImpl(db)
        self.cart_dao = CartDAOImpl(db, self.product_dao)
        self.order_dao = OrderDAOImpl(db, self.product_dao)
        self.shipping_dao = ShippingDAOImpl(db)
        self.vehicle_dao = VehicleDAOImpl(db)
        self.search_log_dao = SearchLogDAOImpl(db)
        self.staff_dao = StaffDAOImpl(db)
        # AI layer
        self.query_service, self.speech_service = QueryService(), SpeechService()
        self.image_service = ImageService()
        self.search_service = SearchService(self.product_dao, self.image_service, self.order_dao, self.search_log_dao)
        self.ranking_service = RankingService()
        self.eta_model, self.risk_model = train_default()
        self.dispatcher = DeliveryDispatcher(self.vehicle_dao, self.eta_model, self.risk_model)
        # Business services — Controller chỉ dùng các đối tượng dưới đây + AI Search, không dùng *_dao
        self.catalog_service = CatalogService(self.product_dao)
        self.customer_service = CustomerService(self.customer_dao)
        self.auth_service = AuthService(self.customer_dao, self.staff_dao)
        self.cart_service = CartService(self.cart_dao, self.product_dao)
        self.payment_service = PaymentService()
        self.weather_service = weather_service or WeatherStub()   # IWeatherService — web dùng OpenMeteoWeatherService
        self.shipping_service = ShippingService(self.dispatcher, self.shipping_dao, self.vehicle_dao)
        self.order_service = OrderService(self.cart_dao, self.order_dao, self.product_dao, self.customer_dao,
                                          self.payment_service, self.shipping_service, db.transaction,
                                          self.weather_service)


def create_app(db_path: str | None = None, weather_service: IWeatherService | None = None) -> Flask:
    app = Flask(__name__, template_folder="view/templates", static_folder="view/static")
    app.secret_key = os.environ.get("CHOBAY_SECRET", "chobay-dev")   # prototype; triển khai thật đặt biến môi trường
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024              # ảnh tìm kiếm tối đa 5 MB
    db = Database(db_path) if db_path else Database()
    if weather_service is None:                                     # CHOBAY_WEATHER=stub → trạm giả lập (kiểm thử, không mạng)
        weather_service = WeatherStub() if os.environ.get("CHOBAY_WEATHER", "auto") == "stub" else OpenMeteoWeatherService()
    app.extensions["chobay"] = Container(db, weather_service)
    from chobay.controller import (home_controller, search_controller, cart_controller, order_controller,
                                   account_controller, dispatch_controller)
    for bp in (home_controller.bp, search_controller.bp, cart_controller.bp, order_controller.bp,
               account_controller.bp, dispatch_controller.bp):
        app.register_blueprint(bp)

    @app.errorhandler(413)
    def too_large(_):
        flash("Ảnh quá lớn — tối đa 5 MB")
        return redirect(request.referrer or url_for("home.index"))

    @app.template_filter("vnd")
    def vnd(v):
        return f"{int(v):,}".replace(",", ".") + "đ"

    from chobay.model.delivery import spec as _spec
    from chobay.model.enums import DeliveryMode as _DM
    VI = {
        "OrderStatus": {"PENDING_PAYMENT": "Chờ thanh toán", "PAID": "Đã thanh toán", "PACKING": "Đang soạn hàng",
                        "DISPATCHED": "Đang giao", "DELIVERED": "Đã giao", "CANCELLED": "Đã hủy"},
        "ShippingStatus": {"PLANNED": "Đã lên lịch", "AWAITING_APPROVAL": "Chờ xác nhận chuyến",
                           "ASSIGNED": "Đã có phương tiện", "IN_TRANSIT": "Đang trên đường", "DELIVERED": "Đã giao",
                           "FAILED": "Giao không thành công"},
        "PaymentStatus": {"PENDING": "Chờ thanh toán", "PAID": "Đã thanh toán", "FAILED": "Thất bại", "REFUNDED": "Đã hoàn tiền"},
        "TempClass": {"AMBIENT": "Nhiệt độ thường", "CHILLED": "Giữ mát 0–5 °C", "FROZEN": "Đông lạnh ≤ −18 °C"},
        "AreaType": {"URBAN_HIGHRISE": "Chung cư", "URBAN_STREET": "Nhà phố", "SUBURBAN": "Ngoại thành",
                     "RIVERSIDE": "Ven sông", "ISLAND": "Xã đảo"},
        "DeliveryPreference": {"FAST": "Nhanh nhất", "CHEAP": "Tiết kiệm nhất", "GREEN": "Ít phát thải nhất"},
        "DeliveryMode": {m.value: _spec(m).name_vi.split(" (")[0] for m in _DM},
    }

    @app.template_filter("arrival")
    def arrival(eta_min, start=None):
        """ETA (phút) → khung giờ nhận hàng như các sàn TMĐT: “10:40 – 10:55 hôm nay”."""
        from datetime import datetime, timedelta
        t0 = start or datetime.now()
        lo, hi = t0 + timedelta(minutes=int(eta_min * 0.9)), t0 + timedelta(minutes=int(eta_min * 1.15) + 5)
        day = "hôm nay" if hi.date() == t0.date() else "ngày mai" if (hi.date() - t0.date()).days == 1 else hi.strftime("%d/%m")
        return f"{lo:%H:%M} – {hi:%H:%M} {day}"

    @app.template_filter("vi")
    def vi(e):
        """Enum → nhãn tiếng Việt cho khách (giao diện không hiện mã kỹ thuật)."""
        return VI.get(type(e).__name__, {}).get(getattr(e, "value", e), getattr(e, "value", e))

    @app.context_processor
    def inject():
        from chobay.controller.common import current_customer, current_staff
        c = app.extensions["chobay"]
        cust = current_customer()
        cart = c.cart_service.view_cart(cust) if cust else None
        return {"me": cust, "staff": current_staff(), "cart_count": sum(i.quantity for i in cart.items) if cart else 0,
                "categories": c.catalog_service.categories()}
    return app

"""OrderController — Checkout (AI đề xuất, khách chọn phương thức giao), đặt hàng, đơn mua và theo dõi đơn (UC05–UC07, UC09)."""
from flask import Blueprint, render_template, redirect, request, url_for, flash, abort
from chobay.model.enums import DeliveryMode, DeliveryPreference
from chobay.service.order_service import CheckoutError, StockError
from .common import ctx, current_customer, customer_required

bp = Blueprint("order", __name__)


def _pref(value) -> DeliveryPreference:
    """Giá trị lạ trên URL/form → mặc định Nhanh, không trả lỗi 500."""
    return DeliveryPreference(value) if value in DeliveryPreference.__members__ else DeliveryPreference.FAST


def _mode(value) -> DeliveryMode | None:
    """Phương thức khách chọn; giá trị lạ → None (dùng đề xuất của AI)."""
    return DeliveryMode(value) if value in DeliveryMode.__members__ else None


@bp.get("/checkout")
@customer_required
def checkout_form():
    cust = current_customer()
    pref = _pref(request.args.get("pref", "FAST"))
    addr_id = request.args.get("address", cust.addresses[0].address_id, type=int)
    if addr_id not in {a.address_id for a in cust.addresses}:
        flash("Địa chỉ giao không hợp lệ — đã chọn địa chỉ mặc định")
        addr_id = cust.addresses[0].address_id
    cart = ctx().cart_service.view_cart(cust)
    if cart.is_empty():
        return redirect(url_for("cart.view"))
    try:
        ctx().order_service.check_stock(cart)                  # “Đủ hàng?” trước khi AI đề xuất cách giao
    except StockError as e:
        flash(str(e))
        return redirect(url_for("cart.view"))
    decision = ctx().order_service.quote(cust, addr_id, pref)          # OrderService lấy thời tiết qua IWeatherService
    weather = ctx().order_service.weather_for(cust, addr_id)          # thời tiết tại địa chỉ giao
    discount = ctx().order_service.discount_for(cust, cart.subtotal())
    return render_template("checkout.html", cart=cart, decision=decision, pref=pref, addr_id=addr_id, w=weather,
                           w_info=ctx().weather_service.info(),
                           discount=discount, prefs=list(DeliveryPreference), wallets=ctx().payment_service.WALLETS,
                           address_label=next(a.label for a in cust.addresses if a.address_id == addr_id).lower())


@bp.post("/checkout")
@customer_required
def place_order():
    cust, f = current_customer(), request.form
    try:
        order = ctx().order_service.checkout(cust, f.get("address", type=int), f.get("method", "CASH"),
                                             _pref(f.get("pref", "FAST")), None, f.get("card_number", ""),
                                             _mode(f.get("mode")), f.get("card_exp", ""), f.get("card_cvv", ""),
                                             f.get("wallet", ""))
    except StockError as e:                                     # hết hàng → quay lại giỏ để sửa
        flash(str(e))
        return redirect(url_for("cart.view"))
    except CheckoutError as e:                                  # giữ địa chỉ, ưu tiên khách đã chọn
        flash(str(e))
        return redirect(url_for("order.checkout_form", address=f.get("address", type=int), pref=f.get("pref", "FAST")))
    return redirect(url_for("order.success", order_id=order.order_id))


@bp.get("/order/<int:order_id>/success")
@customer_required
def success(order_id):
    """Màn hình “Đặt hàng thành công” — hậu điều kiện UC05: khách nhận xác nhận và mã theo dõi."""
    view = ctx().order_service.view_order(order_id, current_customer())
    if view is None:
        abort(404)
    return render_template("order_success.html", **view)


@bp.get("/order/<int:order_id>")
@customer_required
def track(order_id):
    view = ctx().order_service.view_order(order_id, current_customer())      # UC09 Xem / theo dõi đơn
    if view is None:
        abort(404)
    return render_template("track.html", **view)


@bp.post("/order/<int:order_id>/reorder")
@customer_required
def reorder(order_id):
    """UC04.1 Mua lại: thêm cả đơn cũ vào giỏ rồi chuyển tới giỏ hàng."""
    try:
        r = ctx().order_service.reorder(order_id, current_customer())
    except LookupError:
        abort(404)
    n = len(r["added"]) + len(r["adjusted"])
    if n:
        flash(f"Đã thêm {n} sản phẩm của đơn #{order_id} vào giỏ")
    if r["adjusted"]:
        flash("Số lượng đã giảm theo tồn kho: " + ", ".join(r["adjusted"]))
    if r["skipped"]:
        flash("Hiện hết hàng, chưa thêm được: " + ", ".join(r["skipped"]))
    return redirect(url_for("cart.view") if n else url_for("order.my_orders"))


ORDER_TABS = [("ALL", "Tất cả", None), ("WAIT", "Chờ xác nhận", {"AWAITING_APPROVAL"}),
              ("SHIP", "Đang giao", {"ASSIGNED", "IN_TRANSIT", "PLANNED"}), ("DONE", "Đã giao", {"DELIVERED"})]


@bp.get("/orders")
@customer_required
def my_orders():
    """“Đơn mua” — danh sách đơn của chính khách, lọc theo tab như các sàn TMĐT."""
    rows = ctx().order_service.my_orders(current_customer())
    tab = request.args.get("tab", "ALL")
    keep = next((st for k, _, st in ORDER_TABS if k == tab), None)
    counts = {k: sum(1 for r in rows if st is None or r["s"].status.value in st) for k, _, st in ORDER_TABS}
    shown = [r for r in rows if keep is None or r["s"].status.value in keep]
    return render_template("orders.html", rows=shown, tabs=ORDER_TABS, tab=tab if keep is not None else "ALL", counts=counts)

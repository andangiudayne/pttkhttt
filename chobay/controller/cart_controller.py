"""CartController — xem giỏ, thêm, sửa số lượng (UC04, FR10)."""
from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from chobay.service.cart_service import CartError
from .common import ctx, current_customer, customer_required

bp = Blueprint("cart", __name__)


@bp.get("/cart")
@customer_required
def view():
    return render_template("cart.html", cart=ctx().cart_service.view_cart(current_customer()))


@bp.post("/cart/add/<int:pid>")
@customer_required
def add(pid):
    ajax = request.headers.get("X-Requested-With") == "fetch"          # nút “+ Giỏ” gửi nền, ở lại trang (giữ kết quả tìm kiếm)
    cust = current_customer()
    try:
        ctx().cart_service.add_to_cart(cust, pid, request.form.get("qty", 1, type=int))
        msg, ok = "Đã thêm vào giỏ", True
    except CartError as e:
        msg, ok = str(e), False
    if ajax:
        count = sum(i.quantity for i in ctx().cart_service.view_cart(cust).items)
        return jsonify(ok=ok, message=msg, count=count)
    flash(msg)
    return redirect(request.referrer or url_for("cart.view"))


@bp.post("/cart/update/<int:pid>")
@customer_required
def update(pid):
    ctx().cart_service.update_quantity(current_customer(), pid, request.form.get("qty", 0, type=int))
    return redirect(url_for("cart.view"))

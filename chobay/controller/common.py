"""Tiện ích dùng chung cho các Controller: lấy Container, người đang đăng nhập và kiểm tra vai trò."""
from functools import wraps
from flask import current_app, flash, redirect, request, session, url_for


def ctx():
    return current_app.extensions["chobay"]


def current_customer():
    """Khách hàng đang đăng nhập (UC01) hoặc None."""
    cid = session.get("customer_id")
    if cid is None:
        return None
    cust = ctx().customer_service.get_customer(cid)
    if cust is None:                                  # phiên trỏ tới khách không còn tồn tại → đăng xuất
        session.pop("customer_id", None)
    return cust


def current_staff():
    """Nhân viên đang đăng nhập (điều phối viên…) hoặc None."""
    username = session.get("staff")
    if username is None:
        return None
    staff = ctx().auth_service.get_staff(username)
    if staff is None or staff.status != "ACTIVE":
        session.pop("staff", None)
        return None
    return staff


def customer_required(view):
    """Giỏ hàng, thanh toán, đơn hàng chỉ dành cho khách đã đăng nhập."""
    @wraps(view)
    def wrapper(*a, **kw):
        if current_customer() is None:
            flash("Vui lòng đăng nhập để tiếp tục")
            return redirect(url_for("account.login", next=request.full_path.rstrip("?") if request.method == "GET" else request.referrer))
        return view(*a, **kw)
    return wrapper


def dispatcher_required(view):
    """Bảng điều phối chỉ dành cho vai trò DISPATCHER (BR-H1)."""
    @wraps(view)
    def wrapper(*a, **kw):
        staff = current_staff()
        if staff is None or not staff.can_dispatch():
            flash("Trang này dành cho điều phối viên — vui lòng đăng nhập bằng tài khoản điều phối")
            return redirect(url_for("account.login", next=request.full_path.rstrip("?")))
        return view(*a, **kw)
    return wrapper

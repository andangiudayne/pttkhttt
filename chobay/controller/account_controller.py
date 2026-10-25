"""AccountController — UC01 Đăng nhập / Đăng xuất cho khách hàng và điều phối viên."""
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, request, session, url_for, flash
from chobay.model.staff import Staff
from .common import ctx

bp = Blueprint("account", __name__)


def _safe_next(target: str | None, default: str) -> str:
    """Chỉ cho chuyển hướng trong chính trang web (chặn open redirect)."""
    if target and target.startswith("/") and not target.startswith("//") and not urlparse(target).netloc:
        return target
    return default


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = ctx().auth_service.login(request.form.get("username", ""), request.form.get("password", ""))
        if user is None:
            flash("Sai tên đăng nhập hoặc mật khẩu")
            return render_template("login.html", username=request.form.get("username", "")), 401
        session.clear()
        if isinstance(user, Staff):
            session["staff"] = user.username
            return redirect(_safe_next(request.form.get("next"), url_for("dispatch.board")))
        session["customer_id"] = user.customer_id
        flash(f"Xin chào, {user.name.display()}!")
        return redirect(_safe_next(request.form.get("next"), url_for("home.index")))
    return render_template("login.html", username="")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("home.index"))

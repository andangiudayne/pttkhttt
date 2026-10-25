"""DispatchController — Kênh điều phối (giao diện riêng cho tác nhân Điều phối viên):
tổng quan + danh sách chuyến có lọc theo trạng thái / tìm mã đơn, chi tiết chuyến với lý do AI (UC15 Duyệt chuyến đặc biệt),
cho phương tiện xuất phát, giám sát đội phương tiện (UC17 một phần) và trạm thời tiết (IWeatherService — WeatherStub)."""
from math import isfinite
from flask import Blueprint, render_template, redirect, request, url_for, flash, abort
from chobay.model.delivery import spec
from chobay.model.enums import DeliveryMode, ShippingStatus
from .common import ctx, current_staff, dispatcher_required

bp = Blueprint("dispatch", __name__)
PER_PAGE = 15
TABS = [("ALL", "Tất cả"), ("AWAITING_APPROVAL", "Chờ duyệt"), ("ASSIGNED", "Chờ xuất phát"),
        ("IN_TRANSIT", "Đang giao"), ("DELIVERED", "Đã giao")]


def _back(order_id=None):
    """Quay về trang vừa thao tác (chi tiết chuyến hoặc danh sách)."""
    ref = request.referrer or ""
    if order_id and f"/dispatch/{order_id}" in ref and not ref.rstrip("/").endswith(("approve", "depart")):
        return redirect(url_for("dispatch.detail", order_id=order_id))
    return redirect(ref if ref.startswith(request.host_url + "dispatch") else url_for("dispatch.board"))


@bp.get("/dispatch")
@dispatcher_required
def board():
    tab = request.args.get("status", "ALL")
    status = ShippingStatus(tab) if tab in ShippingStatus.__members__ else None
    rows = ctx().order_service.dispatch_board(status)
    q = request.args.get("q", "").strip().lstrip("#")
    if q:
        rows = [r for r in rows if str(r["order"].order_id) == q or q.lower() in r["customer"].name.display().lower()]
    fleet = [v for _, vs in ctx().shipping_service.fleet() for v in vs]
    page = max(1, request.args.get("page", 1, type=int))
    pages = max(1, -(-len(rows) // PER_PAGE))
    page = min(page, pages)
    total = len(rows)
    rows = rows[(page - 1) * PER_PAGE: page * PER_PAGE]
    return render_template("dispatch.html", rows=rows, tab=tab if status else "ALL", tabs=TABS, q=q,
                           page_no=page, pages=pages, total=total,
                           counts=ctx().order_service.dispatch_counts(), w=ctx().weather_service.current(),
                           idle=sum(v.status == "IDLE" for v in fleet), fleet_total=len(fleet), page="board")


@bp.get("/dispatch/<int:order_id>")
@dispatcher_required
def detail(order_id):
    view = ctx().order_service.view_order(order_id)                # điều phối viên xem mọi đơn
    if view is None:
        abort(404)
    a = view["address"]                                            # bước 2 UC15: kiểm thời tiết tại nơi giao
    return render_template("dispatch_detail.html", **view, w=ctx().weather_service.current(a.latitude, a.longitude),
                           w_info=ctx().weather_service.info(a.latitude, a.longitude), page="board")


@bp.post("/dispatch/<int:order_id>/approve")
@dispatcher_required
def approve(order_id):
    try:
        ctx().order_service.approve_delivery(order_id, current_staff())
        flash(f"Đã duyệt chuyến của đơn #{order_id}")
    except LookupError:
        abort(404)
    except ValueError as e:
        flash(str(e))
    return _back(order_id)


@bp.post("/dispatch/<int:order_id>/depart")
@dispatcher_required
def depart(order_id):
    try:
        ctx().order_service.simulate_delivery(order_id, current_staff())
        flash(f"Đơn #{order_id}: phương tiện đã xuất phát và giao xong")
    except LookupError:
        abort(404)
    except ValueError as e:
        flash(str(e))
    return _back(order_id)


@bp.get("/dispatch/fleet")
@dispatcher_required
def fleet():
    return render_template("fleet.html", groups=ctx().shipping_service.fleet(), page="fleet")


@bp.route("/dispatch/weather", methods=["GET", "POST"])
@dispatcher_required
def weather():
    """Thời tiết tự động theo dự báo (Open-Meteo); điều phối viên chỉ ghi đè khi có sự cố hoặc diễn tập."""
    ws = ctx().weather_service
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "auto":
            ws.clear_override()
            flash("Đã quay lại thời tiết tự động theo dự báo")
        elif action == "refresh":
            if hasattr(ws, "refresh"):
                ws.refresh()
            flash("Đã làm mới số liệu dự báo")
        elif action == "override":
            rain, wind = request.form.get("rain", type=float), request.form.get("wind", type=float)
            if rain is None or wind is None or not (isfinite(rain) and isfinite(wind)):
                flash("Hãy nhập lượng mưa và tốc độ gió là số")
            elif not (0 <= rain <= 100 and 0 <= wind <= 40):
                flash("Giá trị ngoài phạm vi: mưa 0–100 mm/h, gió 0–40 m/s")
            else:
                w = ws.update(rain, wind)
                flash(f"Đã ghi đè thủ công: mưa {w.rain_mmh:g} mm/h, gió {w.wind_ms:g} m/s")
        else:
            flash("Thao tác không hợp lệ")
        return redirect(url_for("dispatch.weather"))
    return render_template("weather.html", w=ws.current(), info=ws.info(), hours=ws.forecast(hours=6),
                           types=[spec(m) for m in DeliveryMode], page="weather")

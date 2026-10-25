"""ShippingService — dùng AI DeliveryDispatcher để lập kế hoạch, tạo lô giao và nhật ký hành trình."""
from __future__ import annotations
from datetime import datetime, timedelta
from chobay.dao.interfaces import ShippingDAO, VehicleDAO
from chobay.ai.delivery.dispatcher import DeliveryDispatcher, DispatchDecision
from chobay.ai.delivery.rules import DeliveryRequest
from chobay.model.delivery import Hub, Shipping, TrackingEvent
from chobay.model.enums import DeliveryMode, DeliveryPreference, ShippingStatus
from chobay.model.order import Order

LEG_NOTES = {
    "DRONE": ["Đóng gói vào hộp giữ lạnh", "Drone cất cánh từ sân thượng kho", "Đang bay — độ cao 80 m", "Hạ hàng bằng tời xuống bệ đỗ"],
    "ROBOT": ["Đóng gói vào khoang robot", "Robot rời kho", "Đang đi trên vỉa hè", "Robot tới trước cửa nhà khách"],
    "AUTO_CAR": ["Xếp hàng vào khoang mát/đông", "Xe tự lái rời kho", "Đang di chuyển trên đường", "Xe tới điểm nhận của khách"],
    "FLYING_CAR": ["Chuyển hàng tới Vertiport", "Điều phối viên duyệt chuyến bay", "Ô tô bay cất cánh", "Hạ cánh, robot giao 1 km cuối"],
    "SUBMARINE": ["Chuyển hàng tới cảng Cần Giờ", "Điều phối viên duyệt hải trình", "Tàu ngầm lặn — độ sâu 15 m", "Cập bến đảo, robot giao tận nhà"],
    "AUTO_BOAT": ["Chuyển hàng tới bến Thanh Đa", "Xuồng tự hành rời bến", "Đang chạy trên sông Sài Gòn", "Cập bến nhà khách"],
    "EBIKE": ["Shipper nhận hàng", "Rời kho", "Đang giao", "Giao tận tay"],
    "LOCKER": ["Đóng gói", "Xếp vào tủ khóa", "Gửi mã mở tủ cho khách", "Khách đã nhận"],
}


class ShippingService:
    def __init__(self, dispatcher: DeliveryDispatcher, shipping_dao: ShippingDAO, vehicle_dao: VehicleDAO):
        self.dispatcher, self.shipping_dao, self.vehicle_dao = dispatcher, shipping_dao, vehicle_dao

    def plan(self, req: DeliveryRequest, pref: DeliveryPreference, mode: DeliveryMode | None = None) -> DispatchDecision:
        """AI đề xuất (UC06); nếu khách chọn phương thức hợp lệ khác (luồng thay thế 5a của UC05) thì dùng lựa chọn đó.
        Phương thức vi phạm luật cứng không bao giờ được chọn, kể cả khi khách yêu cầu (BR-D01…D12)."""
        d = self.dispatcher.decide(req, pref)
        if mode is None or d.chosen is None or d.chosen.mode == mode:
            return d
        pick = next((o for o in d.options if o.mode == mode and o.feasible), None)
        if pick is None:
            raise ValueError("Cách giao này không dùng được cho đơn của bạn — hãy chọn cách khác")
        fee = f"{pick.fee:,}".replace(",", ".")
        reason = (f"Khách chọn {pick.mode.value} ({pick.name_vi}) thay cho đề xuất {d.chosen.mode.value} — "
                  f"ETA {pick.eta_min}′, phí {fee}đ. Đề xuất AI: {d.reason}")
        return DispatchDecision(pick, d.options, d.confidence, pick.vehicle.needs_approval, reason, d.fallback_used)

    ACTIVE = [ShippingStatus.AWAITING_APPROVAL, ShippingStatus.ASSIGNED, ShippingStatus.IN_TRANSIT]

    def board(self, status: ShippingStatus | None = None) -> list[Shipping]:
        """UC15 — bảng điều phối: danh sách chuyến cho điều phối viên; status=None: mọi chuyến (mới nhất trước)."""
        return self.shipping_dao.find_by_status([status] if status else self.ACTIVE + [ShippingStatus.DELIVERED,
                                                                                     ShippingStatus.FAILED])

    def fleet(self) -> list[tuple[Hub, list]]:
        """UC17 — đội phương tiện nhóm theo hub."""
        vehicles = self.vehicle_dao.find_all()
        return [(h, [v for v in vehicles if v.hub_id == h.hub_id]) for h in self.vehicle_dao.hubs()]

    def create_shipping(self, order: Order, d: DispatchDecision) -> Shipping:
        c = d.chosen
        status = ShippingStatus.AWAITING_APPROVAL if d.needs_human else ShippingStatus.ASSIGNED
        s = Shipping(0, order.order_id, c.mode, c.hub.hub_id, c.distance_km, c.eta_min, c.fee, status,
                     c.vehicle.vehicle_id if c.vehicle else None, c.score, d.confidence, d.reason)
        self.shipping_dao.create_shipping(s)
        if c.vehicle:
            self.vehicle_dao.mark_busy(c.vehicle.vehicle_id)
        t0 = datetime.now()
        notes = LEG_NOTES[c.mode.value]
        self.shipping_dao.add_event(s.shipping_id, TrackingEvent(t0, status, c.hub.latitude, c.hub.longitude, notes[0]))
        return s

    def get_by_order(self, order_id: int) -> Shipping | None:
        return self.shipping_dao.get_by_order(order_id)

    def hub_of(self, s: Shipping) -> Hub:
        return next(h for h in self.vehicle_dao.hubs() if h.hub_id == s.hub_id)

    def approve(self, shipping_id: int, dispatcher_username: str) -> None:
        """Human-in-the-loop: điều phối viên duyệt chuyến ô tô bay / tàu ngầm — chỉ khi chuyến đang chờ duyệt."""
        s = self.shipping_dao.get_by_id(shipping_id)
        if s is None or s.status != ShippingStatus.AWAITING_APPROVAL:
            raise ValueError("Chuyến này không ở trạng thái chờ duyệt")
        self.shipping_dao.update_status(shipping_id, ShippingStatus.ASSIGNED, approved_by=dispatcher_username)

    def simulate_progress(self, order_id: int, address) -> Shipping:
        """Demo: sinh các sự kiện hành trình (vị trí nội suy hub → nhà khách)."""
        s = self.shipping_dao.get_by_order(order_id)
        if s.status != ShippingStatus.ASSIGNED:                    # BR-H1: chưa duyệt thì không được chạy; đã giao thì thôi
            raise ValueError("Chuyến chưa được duyệt hoặc đã giao xong" if s.status != ShippingStatus.DELIVERED
                             else "Đơn đã giao xong")
        hub = self.hub_of(s)
        notes = LEG_NOTES[s.mode.value]
        t0 = s.events[0].ts if s.events else datetime.now()
        steps = [(0.0, ShippingStatus.ASSIGNED), (0.35, ShippingStatus.IN_TRANSIT), (1.0, ShippingStatus.DELIVERED)]
        for k, (f, st) in enumerate(steps, start=1):
            lat = hub.latitude + (address.latitude - hub.latitude) * f
            lon = hub.longitude + (address.longitude - hub.longitude) * f
            self.shipping_dao.add_event(s.shipping_id, TrackingEvent(t0 + timedelta(minutes=s.eta_minutes * (k / 3)),
                                                                     st, lat, lon, notes[min(k, 3)]))
            self.shipping_dao.update_status(s.shipping_id, st)
        if s.vehicle_id:
            self.vehicle_dao.mark_idle(s.vehicle_id)                    # giao xong → phương tiện rảnh lại (BR-D12)
        return self.shipping_dao.get_by_order(order_id)

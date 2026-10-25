"""Luật nghiệp vụ cứng (business rules) — KHÔNG phải AI.
Lọc những phương thức giao KHÔNG được phép trước khi AI xếp hạng (Rule vs AI, mục 10 tài liệu môn học)."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import radians, sin, cos, asin, sqrt
from chobay.model.cart import CartItem
from chobay.model.customer import Address
from chobay.model.delivery import DeliveryVehicle
from chobay.model.enums import DeliveryMode, TempClass, AreaType

AIR = {DeliveryMode.DRONE, DeliveryMode.FLYING_CAR}
WATER = {DeliveryMode.SUBMARINE, DeliveryMode.AUTO_BOAT}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def route_km(mode: DeliveryMode, straight_km: float) -> float:
    """Quãng đường thực tế: bay thẳng, đường thủy ×1.25, đường bộ ×1.35 (hệ số đường vòng)."""
    if mode in AIR:
        return round(straight_km, 2)
    if mode in WATER:
        return round(straight_km * 1.25, 2)
    if mode == DeliveryMode.LOCKER:
        return 0.5                      # tủ khóa gần nhất (giả định ≤ 1 km)
    return round(straight_km * 1.35, 2)


@dataclass
class Weather:
    rain_mmh: float = 0.0
    wind_ms: float = 3.0
    traffic_index: float = 0.5          # 0 = đường vắng, 1 = kẹt cứng
    hour: int = 10


@dataclass
class DeliveryRequest:
    items: list[CartItem]
    address: Address
    weather: Weather = field(default_factory=Weather)

    @property
    def weight(self) -> float:
        return round(sum(i.line_weight() for i in self.items), 3)

    @property
    def coldest(self) -> TempClass:
        cs = {i.product.temp_class for i in self.items}
        return TempClass.FROZEN if TempClass.FROZEN in cs else TempClass.CHILLED if TempClass.CHILLED in cs else TempClass.AMBIENT

    @property
    def fragile(self) -> bool:
        return any(i.product.is_fragile for i in self.items)

    @property
    def strong_odor(self) -> bool:
        return any(i.product.strong_odor for i in self.items)


@dataclass
class RuleViolation:
    code: str
    message: str


class ConstraintChecker:
    """Kiểm tra 11 luật BR-D01…BR-D11 cho một phương tiện cụ thể."""

    def check(self, v: DeliveryVehicle, req: DeliveryRequest, distance_km: float,
              travel_min: float | None = None) -> list[RuleViolation]:
        out: list[RuleViolation] = []
        a, w = req.address, req.weather
        if not v.can_carry(req.weight):
            out.append(RuleViolation("BR-D01", f"Đơn nặng {req.weight} kg > tải tối đa {v.max_payload_kg} kg"))
        if v.mode != DeliveryMode.LOCKER and not v.can_reach(distance_km):
            out.append(RuleViolation("BR-D02", f"Quãng đường {distance_km} km > tầm {v.max_range_km} km"))
        if a.area_type not in v.allowed_areas:
            out.append(RuleViolation("BR-D03", f"Không phục vụ khu vực {a.area_type.value}"))
        if req.coldest == TempClass.FROZEN and not v.has_freezer and (travel_min is None or travel_min > 30):
            out.append(RuleViolation("BR-D04", "Có hàng đông lạnh: cần khoang cấp đông hoặc giao ≤ 30 phút"))
        if req.coldest == TempClass.CHILLED and not v.has_cooler and (travel_min is None or travel_min > 20):
            out.append(RuleViolation("BR-D05", "Có hàng mát: cần khoang giữ lạnh hoặc giao ≤ 20 phút"))
        if w.wind_ms > v.max_wind_ms or w.rain_mmh > v.max_rain_mmh:
            out.append(RuleViolation("BR-D06", f"Thời tiết vượt ngưỡng (gió {w.wind_ms} m/s, mưa {w.rain_mmh} mm/h)"))
        if v.mode == DeliveryMode.DRONE and not a.has_drop_zone:
            out.append(RuleViolation("BR-D07", "Địa chỉ không có điểm thả drone"))
        if v.mode == DeliveryMode.FLYING_CAR and a.nearest_vertiport_km > 1.0:
            out.append(RuleViolation("BR-D08", f"Bãi đáp gần nhất cách {a.nearest_vertiport_km} km (> 1 km)"))
        if v.mode == DeliveryMode.FLYING_CAR and req.strong_odor:
            out.append(RuleViolation("BR-D09", "Hàng mùi mạnh (sầu riêng) không đi khoang ô tô bay dùng chung"))
        if v.mode == DeliveryMode.DRONE and req.fragile and w.wind_ms > 6:
            out.append(RuleViolation("BR-D10", "Hàng dễ vỡ + gió > 6 m/s: drone không thả an toàn"))
        if a.area_type == AreaType.ISLAND and v.mode not in WATER:
            out.append(RuleViolation("BR-D11", "Xã đảo chỉ tiếp cận bằng đường thủy"))
        return out

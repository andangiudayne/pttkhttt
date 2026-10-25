"""Đội phương tiện giao hàng đa phương thức, kho trung chuyển (Hub) và lô giao (Shipping)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .enums import DeliveryMode, ShippingStatus, AreaType


@dataclass
class Hub:
    hub_id: int
    name: str
    hub_type: str              # DARK_STORE | DRONE_PORT | VERTIPORT | SEA_DOCK | RIVER_DOCK
    latitude: float
    longitude: float
    transfer_min: int = 0      # phút chuyển hàng từ kho tối trung tâm tới hub này


@dataclass
class DeliveryVehicle:
    """Lớp trừu tượng: mỗi phương tiện có giới hạn tải, tầm bay/chạy, khoang lạnh…"""
    vehicle_id: int
    code: str
    hub_id: int
    status: str = "IDLE"
    battery_pct: int = 100

    mode: DeliveryMode = DeliveryMode.EBIKE
    name_vi: str = ""
    max_payload_kg: float = 0
    max_range_km: float = 0
    speed_kmh: float = 0
    has_cooler: bool = False
    has_freezer: bool = False
    base_fee: int = 0
    fee_per_km: int = 0
    co2_g_per_km: int = 0
    max_wind_ms: float = 99
    max_rain_mmh: float = 999
    needs_approval: bool = False
    allowed_areas: tuple = tuple(AreaType)

    def can_carry(self, weight_kg: float) -> bool:
        return weight_kg <= self.max_payload_kg

    def can_reach(self, distance_km: float) -> bool:
        return distance_km <= self.max_range_km

    def fee(self, distance_km: float) -> int:
        return int(round((self.base_fee + self.fee_per_km * distance_km) / 1000.0) * 1000)


# ---- 8 phương thức giao hàng (thông số là giả định thiết kế của nhóm) ----
URBAN = (AreaType.URBAN_HIGHRISE, AreaType.URBAN_STREET)
ROAD = (AreaType.URBAN_HIGHRISE, AreaType.URBAN_STREET, AreaType.SUBURBAN, AreaType.RIVERSIDE)


@dataclass
class Drone(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.DRONE
    name_vi: str = "Drone giao hàng"
    max_payload_kg: float = 2.5
    max_range_km: float = 12
    speed_kmh: float = 60
    has_cooler: bool = True
    base_fee: int = 15_000
    fee_per_km: int = 2_000
    co2_g_per_km: int = 8
    max_wind_ms: float = 10
    max_rain_mmh: float = 2
    allowed_areas: tuple = (AreaType.URBAN_HIGHRISE, AreaType.URBAN_STREET, AreaType.SUBURBAN, AreaType.RIVERSIDE)


@dataclass
class SidewalkRobot(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.ROBOT
    name_vi: str = "Robot giao hàng vỉa hè"
    max_payload_kg: float = 15
    max_range_km: float = 3
    speed_kmh: float = 6
    has_cooler: bool = True
    base_fee: int = 8_000
    fee_per_km: int = 1_500
    co2_g_per_km: int = 3
    max_wind_ms: float = 20
    max_rain_mmh: float = 10
    allowed_areas: tuple = URBAN


@dataclass
class AutonomousCar(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.AUTO_CAR
    name_vi: str = "Xe tự lái (van điện không người lái)"
    max_payload_kg: float = 300
    max_range_km: float = 60
    speed_kmh: float = 30
    has_cooler: bool = True
    has_freezer: bool = True
    base_fee: int = 20_000
    fee_per_km: int = 3_000
    co2_g_per_km: int = 40
    max_wind_ms: float = 25
    max_rain_mmh: float = 50
    allowed_areas: tuple = ROAD


@dataclass
class FlyingCar(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.FLYING_CAR
    name_vi: str = "Ô tô bay chở hàng (eVTOL)"
    max_payload_kg: float = 150
    max_range_km: float = 40
    speed_kmh: float = 120
    has_cooler: bool = True
    has_freezer: bool = True
    base_fee: int = 120_000
    fee_per_km: int = 8_000
    co2_g_per_km: int = 60
    max_wind_ms: float = 12
    max_rain_mmh: float = 5
    needs_approval: bool = True
    allowed_areas: tuple = (AreaType.URBAN_HIGHRISE, AreaType.URBAN_STREET, AreaType.SUBURBAN)


@dataclass
class AutonomousSubmarine(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.SUBMARINE
    name_vi: str = "Tàu ngầm tự hành chở hàng (AUV)"
    max_payload_kg: float = 200
    max_range_km: float = 120
    speed_kmh: float = 15
    has_cooler: bool = True
    has_freezer: bool = True
    base_fee: int = 150_000
    fee_per_km: int = 4_000
    co2_g_per_km: int = 20
    needs_approval: bool = True
    allowed_areas: tuple = (AreaType.ISLAND,)   # lặn dưới sóng — không phụ thuộc gió/mưa


@dataclass
class AutonomousBoat(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.AUTO_BOAT
    name_vi: str = "Xuồng tự hành trên sông"
    max_payload_kg: float = 100
    max_range_km: float = 40
    speed_kmh: float = 20
    has_cooler: bool = True
    base_fee: int = 30_000
    fee_per_km: int = 2_500
    co2_g_per_km: int = 12
    max_wind_ms: float = 15
    max_rain_mmh: float = 20
    allowed_areas: tuple = (AreaType.RIVERSIDE,)


@dataclass
class EBikeCourier(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.EBIKE
    name_vi: str = "Shipper xe máy điện"
    max_payload_kg: float = 30
    max_range_km: float = 20
    speed_kmh: float = 22
    has_cooler: bool = True        # thùng giữ lạnh; hàng đông lạnh dùng đá khô ≤ 45'
    base_fee: int = 15_000
    fee_per_km: int = 4_000
    co2_g_per_km: int = 15
    max_wind_ms: float = 20
    max_rain_mmh: float = 30
    allowed_areas: tuple = ROAD


@dataclass
class SmartLocker(DeliveryVehicle):
    mode: DeliveryMode = DeliveryMode.LOCKER
    name_vi: str = "Tủ khóa thông minh (tự nhận)"
    max_payload_kg: float = 25
    max_range_km: float = 1.0       # tủ phải cách nhà khách ≤ 1 km
    speed_kmh: float = 0
    has_cooler: bool = True
    has_freezer: bool = True
    base_fee: int = 0
    fee_per_km: int = 0
    allowed_areas: tuple = URBAN


FLEET_CLASSES = {
    DeliveryMode.DRONE: Drone, DeliveryMode.ROBOT: SidewalkRobot,
    DeliveryMode.AUTO_CAR: AutonomousCar, DeliveryMode.FLYING_CAR: FlyingCar,
    DeliveryMode.SUBMARINE: AutonomousSubmarine, DeliveryMode.AUTO_BOAT: AutonomousBoat,
    DeliveryMode.EBIKE: EBikeCourier, DeliveryMode.LOCKER: SmartLocker,
}


def spec(mode: DeliveryMode) -> DeliveryVehicle:
    """Trả về một thể hiện mẫu chứa thông số kỹ thuật của phương thức."""
    return FLEET_CLASSES[mode](vehicle_id=0, code=f"SPEC-{mode.value}", hub_id=0)


@dataclass
class TrackingEvent:
    ts: datetime
    status: ShippingStatus
    latitude: float
    longitude: float
    note: str = ""


@dataclass
class Shipping:
    shipping_id: int
    order_id: int
    mode: DeliveryMode
    hub_id: int
    distance_km: float
    eta_minutes: int
    fee: int
    status: ShippingStatus = ShippingStatus.PLANNED
    vehicle_id: Optional[int] = None
    ai_score: float = 0.0
    ai_confidence: float = 0.0
    ai_reason: str = ""
    approved_by: Optional[str] = None
    events: list[TrackingEvent] = field(default_factory=list)

"""Các kiểu liệt kê (enumeration) dùng chung trong tầng Model của ChợBay."""
from enum import Enum


class TempClass(str, Enum):
    """Điều kiện bảo quản của sản phẩm — quyết định phương tiện giao được phép."""
    AMBIENT = "AMBIENT"   # nhiệt độ thường
    CHILLED = "CHILLED"   # mát 0–5 °C (sữa chua, thịt, tôm, rau)
    FROZEN = "FROZEN"     # đông lạnh ≤ -18 °C (kem, cá phi lê đông lạnh)


class AreaType(str, Enum):
    """Loại khu vực của địa chỉ giao — quyết định hạ tầng giao hàng sẵn có."""
    URBAN_HIGHRISE = "URBAN_HIGHRISE"  # chung cư cao tầng, có thể có sân đỗ drone
    URBAN_STREET = "URBAN_STREET"      # nhà phố nội đô, có vỉa hè
    SUBURBAN = "SUBURBAN"              # ngoại thành
    RIVERSIDE = "RIVERSIDE"            # ven sông/kênh, có bến xuồng
    ISLAND = "ISLAND"                  # xã đảo, chỉ tiếp cận bằng đường biển


class DeliveryMode(str, Enum):
    DRONE = "DRONE"
    ROBOT = "ROBOT"
    AUTO_CAR = "AUTO_CAR"
    FLYING_CAR = "FLYING_CAR"
    SUBMARINE = "SUBMARINE"
    AUTO_BOAT = "AUTO_BOAT"
    EBIKE = "EBIKE"
    LOCKER = "LOCKER"


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PACKING = "PACKING"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ShippingStatus(str, Enum):
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"   # ô tô bay / tàu ngầm cần điều phối viên duyệt
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class DeliveryPreference(str, Enum):
    FAST = "FAST"      # ưu tiên nhanh
    CHEAP = "CHEAP"    # ưu tiên rẻ
    GREEN = "GREEN"    # ưu tiên ít phát thải


class StaffRole(str, Enum):
    DISPATCHER = "DISPATCHER"   # điều phối viên — UC15 duyệt chuyến, UC17 xem đội phương tiện, UC20 thời tiết

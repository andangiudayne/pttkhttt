"""Staff — nhân viên vận hành (Điều phối viên) đăng nhập UC01."""
from __future__ import annotations
from dataclasses import dataclass
from .enums import StaffRole


@dataclass
class Staff:
    staff_id: int
    full_name: str
    role: StaffRole
    username: str
    password_hash: str
    status: str = "ACTIVE"

    def can_dispatch(self) -> bool:
        """Chỉ điều phối viên đang hoạt động mới được duyệt chuyến và cho xuất phát (BR-H1)."""
        return self.role == StaffRole.DISPATCHER and self.status == "ACTIVE"

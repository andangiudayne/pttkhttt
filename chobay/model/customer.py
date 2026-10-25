"""Khách hàng và các lớp giá trị đi kèm (FullName, Address, Account)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .enums import AreaType


@dataclass
class FullName:
    first_name: str
    last_name: str

    def display(self) -> str:
        return f"{self.last_name} {self.first_name}"


@dataclass
class Address:
    address_id: int
    label: str
    street: str
    ward: str
    district: str
    city: str
    latitude: float
    longitude: float
    area_type: AreaType
    has_drop_zone: bool = False          # có bệ/ban công đỗ drone
    nearest_vertiport_km: float = 99.0   # khoảng cách tới bãi đáp ô tô bay gần nhất

    def one_line(self) -> str:
        return f"{self.street}, {self.ward}, {self.district}, {self.city}"


@dataclass
class Account:
    username: str
    password_hash: str
    status: str = "ACTIVE"


@dataclass
class Customer:
    customer_id: int
    name: FullName
    email: str
    phone: str
    account: Optional[Account] = None
    addresses: list[Address] = field(default_factory=list)
    loyalty_points: int = 0

    def discount_rate(self) -> float:
        return 0.0

    def default_address(self) -> Optional[Address]:
        return self.addresses[0] if self.addresses else None


@dataclass
class CustomerVIP(Customer):
    vip_level: int = 1
    vip_discount: float = 0.05

    def discount_rate(self) -> float:
        return self.vip_discount


@dataclass
class CustomerNew(Customer):
    welcome_voucher: int = 20_000   # VND, dùng 1 lần cho đơn đầu tiên

"""AuthService — UC01 Đăng nhập cho cả hai nhóm tác nhân người: Khách hàng (account) và Nhân viên (staff).
Mật khẩu so bằng băm PBKDF2-SHA256 (NFR03); tài khoản bị khóa không đăng nhập được."""
from __future__ import annotations
from typing import Optional, Union
from chobay.dao.interfaces import CustomerDAO, StaffDAO
from chobay.model.customer import Customer
from chobay.model.staff import Staff
from .customer_service import check_password


class AuthService:
    def __init__(self, customer_dao: CustomerDAO, staff_dao: StaffDAO):
        self.customer_dao, self.staff_dao = customer_dao, staff_dao

    def login(self, username: str, password: str) -> Optional[Union[Customer, Staff]]:
        username = (username or "").strip().lower()
        staff = self.staff_dao.get_by_username(username)
        if staff is not None:
            return staff if staff.status == "ACTIVE" and check_password(password, staff.password_hash) else None
        cust = self.customer_dao.find_by_username(username)
        if cust and cust.account and cust.account.status == "ACTIVE" and check_password(password, cust.account.password_hash):
            return cust
        return None

    def get_staff(self, username: str) -> Optional[Staff]:
        return self.staff_dao.get_by_username(username)

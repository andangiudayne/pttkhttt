"""CustomerService — UC01 tài khoản. Mật khẩu chỉ lưu dạng băm PBKDF2-SHA256 có salt (NFR03)."""
from __future__ import annotations
import hashlib
import hmac
import os
from typing import Optional
from chobay.dao.interfaces import CustomerDAO
from chobay.model.customer import Customer

ITER = 120_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITER)
    return f"pbkdf2_sha256${ITER}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it)).hex()
    return hmac.compare_digest(test, digest)


class CustomerService:
    def __init__(self, customer_dao: CustomerDAO):
        self.customer_dao = customer_dao

    def get_customer(self, customer_id: int) -> Optional[Customer]:
        return self.customer_dao.get_cust(customer_id)

    def verify_password(self, customer: Customer, password: str) -> bool:
        return bool(customer.account) and check_password(password, customer.account.password_hash)

    def change_password(self, customer: Customer, old: str, new: str) -> bool:
        if len(new) < 8 or not self.verify_password(customer, old):
            return False
        self.customer_dao.change_pass(customer, hash_password(new))
        return True

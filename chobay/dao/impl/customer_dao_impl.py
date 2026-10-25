from typing import Optional
from chobay.dao.database import Database
from chobay.dao.interfaces import CustomerDAO
from chobay.model.customer import Customer, CustomerVIP, CustomerNew, FullName, Address, Account
from chobay.model.enums import AreaType


class CustomerDAOImpl(CustomerDAO):
    def __init__(self, db: Database):
        self.db = db

    def get_cust(self, customer_id: int) -> Optional[Customer]:
        with self.db.connect() as con:
            r = con.execute("SELECT * FROM customer WHERE customer_id = ?", (customer_id,)).fetchone()
            if not r:
                return None
            vip = con.execute("SELECT * FROM customer_vip WHERE customer_id = ?", (customer_id,)).fetchone()
            new = con.execute("SELECT * FROM customer_new WHERE customer_id = ?", (customer_id,)).fetchone()
            acc = con.execute("SELECT * FROM account WHERE customer_id = ?", (customer_id,)).fetchone()
            addrs = con.execute("SELECT * FROM address WHERE customer_id = ? ORDER BY address_id",
                                (customer_id,)).fetchall()
        base = dict(customer_id=r["customer_id"], name=FullName(r["first_name"], r["last_name"]),
                    email=r["email"], phone=r["phone"], loyalty_points=r["loyalty_points"],
                    account=Account(acc["username"], acc["password_hash"], acc["status"]) if acc else None,
                    addresses=[Address(a["address_id"], a["label"], a["street"], a["ward"], a["district"], a["city"],
                                       a["latitude"], a["longitude"], AreaType(a["area_type"]),
                                       bool(a["has_drop_zone"]), a["nearest_vertiport_km"]) for a in addrs])
        if vip:
            return CustomerVIP(**base, vip_level=vip["vip_level"], vip_discount=vip["vip_discount"])
        if new:
            return CustomerNew(**base, welcome_voucher=0 if new["voucher_used"] else new["welcome_voucher"])
        return Customer(**base)

    def update_cust(self, customer: Customer) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE customer SET first_name=?, last_name=?, email=?, phone=?, loyalty_points=? "
                        "WHERE customer_id=?", (customer.name.first_name, customer.name.last_name, customer.email,
                                                customer.phone, customer.loyalty_points, customer.customer_id))
            if isinstance(customer, CustomerNew) and customer.welcome_voucher == 0:
                con.execute("UPDATE customer_new SET voucher_used = 1 WHERE customer_id = ?", (customer.customer_id,))

    def change_pass(self, customer: Customer, new_hash: str) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE account SET password_hash = ? WHERE customer_id = ?", (new_hash, customer.customer_id))

    def find_by_username(self, username: str) -> Optional[Customer]:
        with self.db.connect() as con:
            r = con.execute("SELECT customer_id FROM account WHERE username = ?", (username,)).fetchone()
        return self.get_cust(r["customer_id"]) if r else None

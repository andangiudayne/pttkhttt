from typing import Optional
from chobay.dao.database import Database
from chobay.dao.interfaces import StaffDAO
from chobay.model.enums import StaffRole
from chobay.model.staff import Staff


class StaffDAOImpl(StaffDAO):
    def __init__(self, db: Database):
        self.db = db

    def get_by_username(self, username: str) -> Optional[Staff]:
        with self.db.connect() as con:
            r = con.execute("SELECT * FROM staff WHERE username = ?", (username,)).fetchone()
        return Staff(r["staff_id"], r["full_name"], StaffRole(r["role"]), r["username"], r["password_hash"],
                     r["status"]) if r else None

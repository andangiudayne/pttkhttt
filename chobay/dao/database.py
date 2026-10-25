"""Kết nối CSDL SQLite dùng chung cho các lớp DAOImpl.

transaction(): gom nhiều lời gọi DAO thành MỘT giao dịch nguyên tử (NFR06).
Trong khối `with db.transaction():` mọi DAOImpl dùng chung một kết nối; lỗi ở bất kỳ bước nào → ROLLBACK toàn bộ."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class _Shared:
    """Bọc kết nối đang mở của giao dịch: `with` không commit/đóng — để transaction() quyết định."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def __enter__(self) -> sqlite3.Connection:
        return self.con

    def __exit__(self, *exc) -> bool:
        return False


class Database:
    def __init__(self, path: str | Path = ROOT / "db" / "chobay.db"):
        self.path = str(path)
        self._local = threading.local()

    def _open(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def connect(self):
        """Ngoài giao dịch: kết nối mới (tự commit khi ra khỏi `with`). Trong giao dịch: kết nối dùng chung."""
        con = getattr(self._local, "con", None)
        return _Shared(con) if con is not None else self._open()

    @contextmanager
    def transaction(self):
        if getattr(self._local, "con", None) is not None:      # lồng nhau → dùng giao dịch bên ngoài
            yield self._local.con
            return
        con = self._open()
        self._local.con = con
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            self._local.con = None
            con.close()

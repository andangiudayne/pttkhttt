"""Xuất toàn bộ dữ liệu mẫu ra docs/data/<bảng>.csv (UTF-8 có BOM — mở thẳng bằng Excel không lỗi dấu tiếng Việt).
Chạy sau init_db:  python -m db.export_csv"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data"
SKIP_COLS = {"product_embedding": {"vector"}}       # vector ảnh 1.000+ số — chỉ có ý nghĩa với máy, không xuất


def main(db_path: Path = ROOT / "db" / "chobay.db") -> dict[str, int]:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts = {}
    for t in tables:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})") if r[1] not in SKIP_COLS.get(t, set())]
        rows = con.execute(f"SELECT {', '.join(cols)} FROM {t} ORDER BY 1").fetchall()
        with open(OUT / f"{t}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        counts[t] = len(rows)
    with open(OUT / "README.md", "w", encoding="utf-8") as f:
        f.write("# Dữ liệu mẫu ChợBay\n\nSinh bởi `python -m db.init_db` (seed_data.py + seed_history.py), "
                "xuất bằng `python -m db.export_csv`. Mỗi bảng của `db/schema.sql` là một tệp CSV.\n\n"
                "| Bảng | Số dòng |\n|---|---|\n" + "".join(f"| `{t}` | {n} |\n" for t, n in counts.items()))
    con.close()
    return counts


if __name__ == "__main__":
    for t, n in main().items():
        print(f"{t:20} {n}")

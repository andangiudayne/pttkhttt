"""Tạo CSDL chobay.db từ schema.sql + seed_data.py, lập chỉ mục vector ảnh (product_embedding)
và sinh dữ liệu lịch sử (seed_history.py: đơn đã giao, đánh giá, search_log).
Chạy:  python -m db.init_db"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from db import seed_data as S                              # noqa: E402
from chobay.model.delivery import spec                     # noqa: E402
from chobay.model.enums import DeliveryMode                # noqa: E402
from chobay.ai.search.image_service import ImageService    # noqa: E402
from chobay.service.customer_service import hash_password  # noqa: E402

DB = ROOT / "db" / "chobay.db"
IMG = ROOT / "chobay" / "view" / "static" / "img" / "products"


def build_catalog_mean():
    """Vector trung bình CNN của toàn bộ ảnh catalog — dùng để 'định tâm' embedding (tăng độ phân biệt)."""
    import numpy as np
    svc = ImageService()
    if svc.backend != "cnn+color":
        return
    feats = [svc.raw_cnn(str(IMG / row[14])) for row in S.PRODUCTS if (IMG / row[14]).exists()]
    np.save(ROOT / "models" / "catalog_mean.npy", np.mean(feats, axis=0))


def main(db_path: Path = DB):
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.executemany("INSERT INTO category VALUES (?,?,?)", S.CATEGORIES)
    build_catalog_mean()
    images = ImageService()
    for (pid, kind, cat, name, brand, price, unit, w, temp, fragile, liquid, odor, stock, rating, image,
         extra, kw, desc) in S.PRODUCTS:
        con.execute("""INSERT INTO product(product_id, category_id, kind, name, brand, price, unit, weight_kg, temp_class,
                       is_fragile, is_liquid, strong_odor, stock, rating, image_path, description)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, cat, kind, name, brand, price, unit, w, temp, fragile, liquid, odor, stock, rating, image, desc))
        if kind == "FreshFood":
            con.execute("INSERT INTO fresh_food VALUES (?,?,?)", (pid, extra["origin"], extra["shelf_life_hours"]))
        elif kind == "FrozenFood":
            con.execute("INSERT INTO frozen_food VALUES (?,?)", (pid, extra["storage_temp_c"]))
        elif kind == "PackagedFood":
            con.execute("INSERT INTO packaged_food VALUES (?,?,?)", (pid, extra.get("barcode"), extra["expiry_days"]))
        else:
            con.execute("INSERT INTO beverage VALUES (?,?,?)", (pid, extra["volume_ml"], extra.get("barcode")))
        img_path = IMG / image
        vec = images.encode(str(img_path)) if img_path.exists() else []
        con.execute("INSERT INTO product_embedding VALUES (?,?,?)", (pid, json.dumps(vec), kw))

    for cid, first, last, email, phone, ctype, pts in S.CUSTOMERS:
        con.execute("INSERT INTO customer(customer_id, first_name, last_name, email, phone, loyalty_points) VALUES (?,?,?,?,?,?)",
                    (cid, first, last, email, phone, pts))
        con.execute("INSERT INTO account(customer_id, username, password_hash) VALUES (?,?,?)",
                    (cid, email.split("@")[0], hash_password("chobay123")))
        if ctype == "VIP":
            con.execute("INSERT INTO customer_vip VALUES (?,?,?)", (cid, 2, 0.05))
        elif ctype == "NEW":
            con.execute("INSERT INTO customer_new(customer_id) VALUES (?)", (cid,))
    for sid, full_name, role, username in S.STAFF:
        con.execute("INSERT INTO staff(staff_id, full_name, role, username, password_hash) VALUES (?,?,?,?,?)",
                    (sid, full_name, role, username, hash_password("chobay123")))
    con.executemany("INSERT INTO address VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", S.ADDRESSES)
    con.executemany("INSERT INTO hub VALUES (?,?,?,?,?,?)", S.HUBS)
    for m in DeliveryMode:
        v = spec(m)
        con.execute("INSERT INTO vehicle_type VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (m.value, v.name_vi, v.max_payload_kg, v.max_range_km, v.speed_kmh, int(v.has_cooler),
                     int(v.has_freezer), v.base_fee, v.fee_per_km, v.co2_g_per_km, v.max_wind_ms, v.max_rain_mmh,
                     int(v.needs_approval), ",".join(a.value for a in v.allowed_areas)))
    con.executemany("INSERT INTO vehicle VALUES (?,?,?,?,?,?)", S.VEHICLES)
    con.commit()
    con.close()
    from db.seed_history import generate                    # đơn đã giao 3 tuần qua, đánh giá, lịch sử tìm kiếm
    st = generate(db_path)
    print(f"OK — {db_path}: {len(S.PRODUCTS)} sản phẩm, {len(S.CUSTOMERS)} khách, {len(S.STAFF)} điều phối viên, "
          f"{st['orders']} đơn đã giao, {st['reviews']} đánh giá, {st['search_logs']} lượt tìm kiếm")


if __name__ == "__main__":
    main()

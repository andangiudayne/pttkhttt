import json
from typing import Optional
from chobay.dao.database import Database
from chobay.dao.interfaces import ProductDAO
from chobay.model.product import (Review, Product, FreshFood, FrozenFood, PackagedFood, Beverage,
                                  Category, TempClass)

_KIND = {"FreshFood": FreshFood, "FrozenFood": FrozenFood, "PackagedFood": PackagedFood, "Beverage": Beverage}

_SQL = """
SELECT p.*, c.name AS cat_name, c.slug AS cat_slug,
       f.origin, f.shelf_life_hours, z.storage_temp_c,
       k.barcode AS pk_barcode, k.expiry_days, b.volume_ml, b.barcode AS bv_barcode
FROM product p JOIN category c ON c.category_id = p.category_id
LEFT JOIN fresh_food f    ON f.product_id = p.product_id
LEFT JOIN frozen_food z   ON z.product_id = p.product_id
LEFT JOIN packaged_food k ON k.product_id = p.product_id
LEFT JOIN beverage b      ON b.product_id = p.product_id
"""


class ProductDAOImpl(ProductDAO):
    def __init__(self, db: Database):
        self.db = db

    def _row_to_product(self, r) -> Product:
        cls = _KIND[r["kind"]]
        base = dict(product_id=r["product_id"], name=r["name"], brand=r["brand"],
                    category=Category(r["category_id"], r["cat_name"], r["cat_slug"]),
                    price=r["price"], unit=r["unit"], weight_kg=r["weight_kg"],
                    temp_class=TempClass(r["temp_class"]), stock=r["stock"], image_path=r["image_path"],
                    description=r["description"], is_fragile=bool(r["is_fragile"]),
                    is_liquid=bool(r["is_liquid"]), strong_odor=bool(r["strong_odor"]), rating=r["rating"])
        if cls is FreshFood:
            return FreshFood(**base, origin=r["origin"], shelf_life_hours=r["shelf_life_hours"])
        if cls is FrozenFood:
            return FrozenFood(**base, storage_temp_c=r["storage_temp_c"])
        if cls is PackagedFood:
            return PackagedFood(**base, barcode=r["pk_barcode"], expiry_days=r["expiry_days"])
        return Beverage(**base, volume_ml=r["volume_ml"], barcode=r["bv_barcode"])

    def get_item(self, product_id: int) -> Optional[Product]:
        with self.db.connect() as con:
            r = con.execute(_SQL + " WHERE p.product_id = ?", (product_id,)).fetchone()
        return self._row_to_product(r) if r else None

    def find_all(self) -> list[Product]:
        with self.db.connect() as con:
            rows = con.execute(_SQL + " ORDER BY p.category_id, p.product_id").fetchall()
        return [self._row_to_product(r) for r in rows]

    def find_by_category(self, category_id: int) -> list[Product]:
        with self.db.connect() as con:
            rows = con.execute(_SQL + " WHERE p.category_id = ? ORDER BY p.product_id", (category_id,)).fetchall()
        return [self._row_to_product(r) for r in rows]

    def categories(self) -> list[Category]:
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM category ORDER BY category_id").fetchall()
        return [Category(r["category_id"], r["name"], r["slug"]) for r in rows]

    def update_stock(self, product_id: int, delta: int) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE product SET stock = stock + ? WHERE product_id = ?", (delta, product_id))

    def get_embedding(self, product_id: int) -> tuple[list[float], str]:
        with self.db.connect() as con:
            r = con.execute("SELECT image_vector, keywords FROM product_embedding WHERE product_id = ?",
                            (product_id,)).fetchone()
        return (json.loads(r["image_vector"]), r["keywords"]) if r else ([], "")

    def get_reviews(self, product_id: int) -> list[Review]:
        with self.db.connect() as con:
            rows = con.execute("""SELECT r.*, c.last_name || ' ' || c.first_name AS author FROM review r
                                  JOIN customer c ON c.customer_id = r.customer_id
                                  WHERE r.product_id = ? ORDER BY r.created_at DESC""", (product_id,)).fetchall()
        return [Review(r["review_id"], r["customer_id"], r["product_id"], r["rating"], r["comment"] or "", r["created_at"],
                       r["author"]) for r in rows]

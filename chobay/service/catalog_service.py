"""CatalogService — UC03 Xem sản phẩm & danh mục. Controller đọc catalog qua service, không chạm DAO (A06: Presentation ↛ Data)."""
from __future__ import annotations
from typing import Optional
from chobay.dao.interfaces import ProductDAO
from chobay.ai.delivery.rules import ConstraintChecker, DeliveryRequest
from chobay.model.cart import CartItem
from chobay.model.customer import Address
from chobay.model.delivery import spec
from chobay.model.enums import AreaType, DeliveryMode
from chobay.model.product import Category, Product

GOODS_RULES = {"BR-D01", "BR-D04", "BR-D05", "BR-D09"}          # luật chỉ phụ thuộc hàng hóa
_ANY_PLACE = Address(0, "", "", "", "", "", 10.73, 106.72, AreaType.URBAN_HIGHRISE, True, 0.0)


class CatalogService:
    def __init__(self, product_dao: ProductDAO):
        self.product_dao = product_dao

    def list_products(self, category_id: int | None = None) -> list[Product]:
        return self.product_dao.find_by_category(category_id) if category_id else self.product_dao.find_all()

    def get_product(self, product_id: int) -> Optional[Product]:
        return self.product_dao.get_item(product_id)

    def categories(self) -> list[Category]:
        return self.product_dao.categories()

    def reviews(self, product_id: int) -> dict:
        """UC03 Xem sản phẩm: điểm trung bình, số lượt và phân bố sao từ bảng review."""
        rs = self.product_dao.get_reviews(product_id)
        dist = {k: sum(r.rating == k for r in rs) for k in range(5, 0, -1)}
        return {"items": rs, "count": len(rs), "avg": round(sum(r.rating for r in rs) / len(rs), 1) if rs else None,
                "dist": dist}

    def delivery_fit(self, product: Product, qty: int = 1) -> list[tuple[str, str | None]]:
        """FR09: phương thức nào chở được món này (chỉ xét hàng hóa, giống bảng 3.6). Trả (tên, mã luật vi phạm | None)."""
        req = DeliveryRequest([CartItem(product, qty, product.price)], _ANY_PLACE)
        out = []
        for m in DeliveryMode:
            v = spec(m)
            codes = [x.code for x in ConstraintChecker().check(v, req, 1.0, None) if x.code in GOODS_RULES]
            out.append((v.name_vi, codes[0] if codes else None))
        return out

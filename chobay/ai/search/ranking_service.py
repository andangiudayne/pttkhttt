"""RankingService — S(x|q) = α·S_text + β·S_image + γ·S_business, rồi lọc độ liên quan tương đối.

Lọc tương đối: chỉ giữ sản phẩm có điểm ≥ RELATIVE × điểm của sản phẩm tốt nhất
(ảnh: so S_image vì cosine ảnh của 22 sản phẩm khá sát nhau; chữ/giọng nói/chữ+ảnh: so S).
Nhờ vậy ảnh tương ớt chỉ trả tương ớt, không kèm gạo, sữa đặc… chỉ vì chúng “ít khác” nhất."""
from __future__ import annotations
from chobay.model.enums import TempClass, AreaType
from chobay.model.customer import Address
from .query_service import Query
from .search_service import Candidate


class RankingService:
    RELATIVE = {"IMAGE": 0.8, "default": 0.75}

    def weights(self, q: Query) -> tuple[float, float, float]:
        if q.type == "IMAGE":
            return 0.0, 0.85, 0.15
        if q.type == "MULTI":
            return 0.45, 0.40, 0.15
        return 0.80, 0.0, 0.20

    def business_score(self, c: Candidate, address: Address | None) -> float:
        p = c.product
        in_stock = 1.0 if p.stock > 0 else 0.0
        quick = 1.0
        if address is not None and address.area_type == AreaType.ISLAND and p.temp_class != TempClass.AMBIENT:
            quick = 0.6          # ra đảo bằng tàu ngầm mất ~2 giờ — hàng lạnh kém ưu tiên hơn
        return 0.5 * in_stock + 0.3 * (p.rating / 5) + 0.2 * quick

    def rank(self, q: Query, cands: list[Candidate], address: Address | None = None, k: int = 5) -> list[Candidate]:
        a, b, g = self.weights(q)
        for c in cands:
            c.s_business = self.business_score(c, address)
            c.score = round(a * c.s_text + b * c.s_image + g * c.s_business, 3)
        ranked = sorted(cands, key=lambda c: c.score, reverse=True)
        return self.relevant(q, ranked)[:k]

    def relevant(self, q: Query, ranked: list[Candidate]) -> list[Candidate]:
        """Bỏ ứng viên kém liên quan hẳn so với kết quả tốt nhất (tránh trả 'món cho đủ số')."""
        if not ranked:
            return ranked
        key = (lambda c: c.s_image) if q.type == "IMAGE" else (lambda c: c.score)
        best = max(key(c) for c in ranked)
        ratio = self.RELATIVE.get(q.type, self.RELATIVE["default"])
        return [c for c in ranked if key(c) >= ratio * best]

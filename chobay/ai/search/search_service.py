"""SearchService — truy hồi ứng viên C(q) = TopK_x s(q, x). Retrieval ≠ Ranking (nguyên tắc 3, Assignment 06).
Cũng là điểm vào tầng ứng dụng cho tìm đơn hàng (Search Order) và lịch sử tìm kiếm — Controller không gọi DAO."""
from __future__ import annotations
from dataclasses import dataclass
from chobay.dao.interfaces import ProductDAO, OrderDAO, SearchLogDAO
from chobay.model.order import Order
from chobay.model.product import Product
from chobay.model.search_log import SearchLog
from .query_service import Query, normalize, tokenize_vi
from .image_service import ImageService

TOP_K_IMAGE = 8


@dataclass
class Candidate:
    product: Product
    s_text: float = 0.0
    s_image: float = 0.0
    s_business: float = 0.0
    score: float = 0.0


class SearchService:
    def __init__(self, product_dao: ProductDAO, image_service: ImageService,
                 order_dao: OrderDAO | None = None, search_log_dao: SearchLogDAO | None = None):
        self.product_dao = product_dao                   # ProductRepository + VectorIndex (product_embedding)
        self.images = image_service
        self.order_dao = order_dao                       # OrderRepository
        self.search_log_dao = search_log_dao

    CATEGORY_ONLY = 0.6        # từ chỉ khớp tên nhóm hàng (vd "thịt" ↔ nhóm "Thịt, cá, trứng…") được điểm thấp hơn khớp tên món

    @staticmethod
    def text_score(q: Query, p: Product, keywords: str) -> float:
        """0.75 · tỷ lệ từ khớp + 0.25 · tỷ lệ cặp từ liền kề khớp (cụm từ).
        Khớp ở tên / thương hiệu / từ khóa của món = 1; chỉ khớp ở tên nhóm hàng = 0.6."""
        if not q.tokens:
            return 0.0
        own_vi = set(tokenize_vi(f"{p.name} {p.brand}"))
        own_plain = normalize(f"{p.name} {p.brand}").split() + keywords.split()
        cat_vi, cat_plain = set(tokenize_vi(p.category.name)), normalize(p.category.name).split()

        def weight(tv, tp, vi_set, plain_set):
            typed_accent = normalize(tv) != tv          # khách gõ có dấu → so khớp có dấu
            return tv in vi_set if typed_accent else tp in plain_set

        cat_words = [w for w in cat_plain if w.isalnum()]
        cat_w = 1.0 if q.tokens == cat_words else SearchService.CATEGORY_ONLY   # gõ đúng tên nhóm ("đồ uống") → cả nhóm
        kw = set(keywords.split())                      # từ khóa/đồng nghĩa không dấu do cửa hàng soạn cho từng món

        def hit(tv, tp):
            typed_accent = normalize(tv) != tv
            in_kw = tp in kw and (not typed_accent or tv in own_vi | cat_vi)   # "dưa" không khớp từ khóa "dua" của nước dừa
            if weight(tv, tp, own_vi, set(own_plain)) or in_kw:
                return 1.0
            return cat_w if weight(tv, tp, cat_vi, set(cat_plain)) else 0.0

        hits = sum(hit(tv, tp) for tv, tp in zip(q.tokens_vi, q.tokens))
        pairs = list(zip(q.tokens, q.tokens[1:]))
        own_seq, cat_seq = " ".join(own_plain), " ".join(cat_plain)
        if pairs:
            phrase = sum(1.0 if f"{a} {b}" in own_seq else SearchService.CATEGORY_ONLY if f"{a} {b}" in cat_seq else 0.0
                         for a, b in pairs) / len(pairs)
        else:
            phrase = hits / len(q.tokens)
        return round(0.75 * hits / len(q.tokens) + 0.25 * phrase, 4)

    def retrieve(self, q: Query) -> list[Candidate]:
        cands = []
        for p in self.product_dao.find_all():
            if q.max_price and p.price > q.max_price:
                continue
            vec, keywords = self.product_dao.get_embedding(p.product_id)
            c = Candidate(p, s_text=self.text_score(q, p, keywords))
            if q.embedding is not None and vec:
                c.s_image = max(0.0, self.images.cosine(q.embedding, vec))
            cands.append(c)
        if q.embedding is not None:                       # ảnh: TopK theo độ tương đồng
            by_img = sorted(cands, key=lambda c: c.s_image, reverse=True)[:TOP_K_IMAGE]
            keep = {id(c) for c in by_img} | {id(c) for c in cands if c.s_text > 0.5}
            return [c for c in cands if id(c) in keep]
        return [c for c in cands if c.s_text >= 0.35]

    # ---------- Search Order (A06) ----------
    def find_orders(self, q: Query, customer_id: int) -> list[Order]:
        """Chỉ tìm trong đơn của CHÍNH khách đang đăng nhập (riêng tư). order_id None → đơn gần nhất."""
        orders = self.order_dao.find_by_customer(customer_id)          # mới nhất trước
        if q.order_id is not None:
            return [o for o in orders if o.order_id == q.order_id]
        return orders[:1]

    # ---------- lịch sử tìm kiếm (search_log) ----------
    def log_search(self, customer_id: int | None, q: Query, label: str, top_product_id: int | None) -> int:
        mode = "IMAGE" if q.type in ("IMAGE", "MULTI") else q.type
        return self.search_log_dao.save(SearchLog(customer_id, mode, label, top_product_id))

    def recent(self, customer_id: int, limit: int = 5) -> list[SearchLog]:
        return self.search_log_dao.find_recent(customer_id, limit)

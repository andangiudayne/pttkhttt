"""QueryService — mọi đầu vào (text / voice / image) → một biểu diễn truy vấn chung (Common Query Representation)."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field

# đồng nghĩa (không dấu) — chuẩn hóa cách gọi khác nhau của khách
SYNONYMS = {
    "mi tom": "mi goi", "mi an lien": "mi goi", "hoa qua": "trai cay", "sua bo": "sua tuoi",
    "cafe": "ca phe", "coffee": "ca phe", "thit heo": "thit", "thit lon": "thit",
    "durian": "sau rieng", "chinsu": "chin su", "yaourt": "sua chua", "trung vit": "trung",
}
STOPWORDS = {"cho", "toi", "minh", "mua", "tim", "giup", "voi", "di", "nhe", "nha", "a", "oi", "can", "muon", "mot",
             "it", "loai", "san", "pham", "hay", "co", "khong", "cai", "nao", "ban", "em", "anh", "chi", "gia", "re",
             "nhat", "ho", "dum", "giao", "nhanh", "the", "hang", "ve", "lay"}
PROTECTED = {"gia vi", "hai san"}      # cụm có từ dừng bên trong ("giá"/"gia vị", "sản phẩm"/"hải sản") — giữ nguyên


def strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def tokenize_vi(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text.lower())
    return re.sub(r"[^\w ]+", " ", t).split()


def normalize(text: str) -> str:
    """Chuỗi không dấu, chữ thường — dùng cho từ khóa & khách gõ không dấu."""
    t = strip_accents(text.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Query:
    type: str                                        # TEXT | VOICE | IMAGE | MULTI
    text: str = ""
    tokens: list[str] = field(default_factory=list)  # không dấu
    tokens_vi: list[str] = field(default_factory=list)  # có dấu (nếu khách gõ có dấu) — khử nhập nhằng "cay"/"cây"
    embedding: list[float] | None = None
    max_price: int | None = None
    intent: str = "PRODUCT"                          # PRODUCT | ORDER (A06: Search Order)
    order_id: int | None = None                      # None + intent ORDER → đơn gần nhất


class QueryService:
    PRICE = re.compile(r"\b(duoi|<)\s*(\d+)\s*(k|nghin|ngan)?\b")
    ORDER = re.compile(r"\b(?:ma\s+)?(?:don(?:\s+hang)?|order)\b(?:\s+(?:so|ma))?\s*(\d+)?")

    def _order_intent(self, qtype: str, plain: list[str]) -> Query | None:
        """“đơn hàng số 3”, “tìm đơn 3”, “đơn gần nhất của mình đâu” → truy vấn đơn hàng (không tìm sản phẩm)."""
        joined = " ".join(plain)
        m = self.ORDER.search(joined)
        if not m:
            return None
        tokens = [w for w in plain if w not in STOPWORDS]
        return Query(qtype, joined, tokens, tokens, intent="ORDER", order_id=int(m.group(1)) if m.group(1) else None)

    def _parse(self, qtype: str, text: str) -> Query:
        vi = tokenize_vi(text)
        plain = [normalize(w) for w in vi]
        if qtype in ("TEXT", "VOICE") and (oq := self._order_intent(qtype, plain)):
            return oq
        max_price = None
        joined = " ".join(plain)
        m = self.PRICE.search(joined)
        if m:                                              # "dưới 40k" → bộ lọc giá
            max_price = int(m.group(2)) * (1000 if m.group(3) else 1) or None   # “dưới 0k” → bỏ qua bộ lọc
            drop = set(range(len(joined[:m.start()].split()), len(joined[:m.end()].split())))
            vi = [w for i, w in enumerate(vi) if i not in drop]
            plain = [w for i, w in enumerate(plain) if i not in drop]
        i = 0
        while i < len(plain) - 1:                          # đồng nghĩa 2 từ
            pair = plain[i] + " " + plain[i + 1]
            if pair in SYNONYMS:
                rep = SYNONYMS[pair].split()
                plain[i:i + 2] = rep
                vi[i:i + 2] = rep                          # khớp ở không gian không dấu
            i += 1
        plain = [SYNONYMS.get(w, w) for w in plain]
        def protected(k):
            return any(0 <= j and j + 1 < len(plain) and f"{plain[j]} {plain[j + 1]}" in PROTECTED for j in (k - 1, k))
        keep = [k for k, w in enumerate(plain) if (w not in STOPWORDS or protected(k)) and not w.isdigit()]
        return Query(qtype, " ".join(plain[k] for k in keep), [plain[k] for k in keep], [vi[k] for k in keep],
                     None, max_price)

    def text_query(self, text: str) -> Query:
        return self._parse("TEXT", text)

    def voice_query(self, transcript: str) -> Query:
        return self._parse("VOICE", transcript)

    def image_query(self, embedding: list[float]) -> Query:
        return Query("IMAGE", embedding=embedding)

    def multimodal_query(self, text: str, embedding: list[float]) -> Query:
        q = self._parse("MULTI", text)
        q.embedding = embedding
        return q

"""Lịch sử tìm kiếm — dữ liệu phản hồi của AI Search (Customer 1 — 0..* SearchLog)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchLog:
    customer_id: Optional[int]
    mode: str                          # TEXT | VOICE | IMAGE
    query: str
    top_product_id: Optional[int] = None
    log_id: int = 0
    ts: str = ""

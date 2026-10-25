"""Sản phẩm tạp hóa. Thuộc tính vật lý (khối lượng, nhiệt độ, dễ vỡ, mùi)
được AI điều phối giao hàng dùng để chọn phương tiện phù hợp."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .enums import TempClass


@dataclass
class Category:
    category_id: int
    name: str
    slug: str


@dataclass
class Product:
    product_id: int
    name: str
    brand: str
    category: Category
    price: int                 # VND
    unit: str
    weight_kg: float
    temp_class: TempClass
    stock: int
    image_path: str
    description: str = ""
    is_fragile: bool = False
    is_liquid: bool = False
    strong_odor: bool = False
    rating: float = 4.5

    def is_available(self, qty: int = 1) -> bool:
        return self.stock >= qty

    def kind(self) -> str:
        return "Product"


@dataclass
class FreshFood(Product):
    origin: str = ""
    shelf_life_hours: int = 48

    def kind(self) -> str:
        return "FreshFood"


@dataclass
class FrozenFood(Product):
    storage_temp_c: int = -18

    def kind(self) -> str:
        return "FrozenFood"


@dataclass
class PackagedFood(Product):
    barcode: Optional[str] = None
    expiry_days: int = 180

    def kind(self) -> str:
        return "PackagedFood"


@dataclass
class Beverage(Product):
    volume_ml: int = 0
    barcode: Optional[str] = None

    def kind(self) -> str:
        return "Beverage"


@dataclass
class Review:
    """Đánh giá của khách cho sản phẩm đã mua (Customer 1 — 0..* Review — 1 Product)."""
    review_id: int
    customer_id: int
    product_id: int
    rating: int                       # 1..5
    comment: str = ""
    created_at: str = ""
    author: str = ""                  # tên hiển thị (đọc kèm khi truy vấn)

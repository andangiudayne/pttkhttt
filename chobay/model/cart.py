"""Giỏ hàng = trạng thái mua sắm tạm thời (CartItem ≠ OrderItem)."""
from __future__ import annotations
from dataclasses import dataclass, field
from .product import Product, TempClass


@dataclass
class CartItem:
    product: Product
    quantity: int
    cart_price: int            # giá hiện tại khi bỏ vào giỏ

    def line_total(self) -> int:
        return self.cart_price * self.quantity

    def line_weight(self) -> float:
        return self.product.weight_kg * self.quantity


@dataclass
class Cart:
    cart_id: int
    customer_id: int
    items: list[CartItem] = field(default_factory=list)

    def subtotal(self) -> int:
        return sum(i.line_total() for i in self.items)

    def total_weight(self) -> float:
        return round(sum(i.line_weight() for i in self.items), 3)

    def coldest_class(self) -> TempClass:
        classes = {i.product.temp_class for i in self.items}
        if TempClass.FROZEN in classes:
            return TempClass.FROZEN
        if TempClass.CHILLED in classes:
            return TempClass.CHILLED
        return TempClass.AMBIENT

    def is_empty(self) -> bool:
        return not self.items

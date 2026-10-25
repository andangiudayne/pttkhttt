"""Đơn hàng = giao dịch đã xác nhận; OrderItem giữ nguyên giá tại thời điểm mua."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .enums import OrderStatus, DeliveryPreference, PaymentStatus
from .product import Product


@dataclass
class OrderItem:
    product: Product
    quantity: int
    unit_price: int            # giá giao dịch — không đổi khi giá sản phẩm thay đổi

    def line_total(self) -> int:
        return self.unit_price * self.quantity


@dataclass
class Payment:
    amount: int
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_ref: Optional[str] = None

    def method(self) -> str:
        return "BASE"


@dataclass
class PayCash(Payment):         # thanh toán khi nhận hàng (COD)
    def method(self) -> str:
        return "CASH"


@dataclass
class PayCredit(Payment):       # thẻ tín dụng/ghi nợ
    card_last4: str = ""

    def method(self) -> str:
        return "CREDIT"


@dataclass
class PayEWallet(Payment):      # ví điện tử
    wallet_provider: str = ""

    def method(self) -> str:
        return "EWALLET"


@dataclass
class Order:
    order_id: int
    customer_id: int
    address_id: int
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING_PAYMENT
    order_date: datetime = field(default_factory=datetime.now)
    shipping_fee: int = 0
    discount: int = 0
    preference: DeliveryPreference = DeliveryPreference.FAST
    payment: Optional[Payment] = None

    def subtotal(self) -> int:
        return sum(i.line_total() for i in self.items)

    def total(self) -> int:
        return self.subtotal() + self.shipping_fee - self.discount

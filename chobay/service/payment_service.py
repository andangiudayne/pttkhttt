"""PaymentService — UC07 Thanh toán qua cổng (prototype: cổng giả lập).

Thẻ: kiểm tra số thẻ (thuật toán Luhn), hạn dùng MM/YY và CVV, rồi CHỈ giữ 4 số cuối — số thẻ đầy đủ và CVV
không bao giờ được lưu (NFR03). Ví điện tử: khách chọn nhà cung cấp ví, lưu vào PayEWallet.wallet_provider."""
import re
import uuid
from abc import ABC, abstractmethod
from datetime import date
from chobay.model.order import Payment, PayCash, PayCredit, PayEWallet
from chobay.model.enums import PaymentStatus


class IPaymentGateway(ABC):
    """Interface tới cổng thanh toán bên ngoài (biểu đồ thành phần 4.4)."""

    @abstractmethod
    def authorize(self, payment: Payment) -> bool: ...


class PaymentGatewayStub(IPaymentGateway):
    """Giả lập cổng thanh toán: thẻ thử 4000 0000 0000 0002 (4 số cuối 0002) bị ngân hàng từ chối — để demo luồng E1."""

    DECLINED_LAST4 = "0002"

    def authorize(self, payment: Payment) -> bool:
        return not (isinstance(payment, PayCredit) and payment.card_last4 == self.DECLINED_LAST4)


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch) * (2 if alt else 1)
        total += d - 9 if d > 9 else d
        alt = not alt
    return total % 10 == 0


class PaymentService:
    METHODS = ("CASH", "CREDIT", "EWALLET")
    WALLETS = ("MoMo", "ZaloPay", "VNPAY")

    def __init__(self, gateway: IPaymentGateway | None = None):
        self.gateway = gateway or PaymentGatewayStub()

    def create(self, method: str, amount: int, card_number: str = "", expiry: str = "", cvv: str = "",
               wallet: str = "") -> Payment:
        if method not in self.METHODS:
            raise ValueError(f"Cách thanh toán “{method}” không được hỗ trợ")
        if method == "CREDIT":
            return PayCredit(amount=amount, card_last4=self._check_card(card_number, expiry, cvv))
        if method == "EWALLET":
            if wallet not in self.WALLETS:
                raise ValueError("Hãy chọn ví điện tử để thanh toán")
            return PayEWallet(amount=amount, wallet_provider=wallet)
        return PayCash(amount=amount)

    @staticmethod
    def _check_card(card_number: str, expiry: str, cvv: str) -> str:
        digits = re.sub(r"[\s-]", "", card_number or "")
        if not (digits.isdigit() and 13 <= len(digits) <= 19 and luhn_ok(digits)):
            raise ValueError("Số thẻ không hợp lệ — kiểm tra lại 16 số trên mặt thẻ")
        m = re.fullmatch(r"\s*(\d{2})\s*/\s*(\d{2})\s*", expiry or "")
        if not m or not 1 <= int(m.group(1)) <= 12:
            raise ValueError("Ngày hết hạn phải có dạng MM/YY")
        month, year = int(m.group(1)), 2000 + int(m.group(2))
        today = date.today()
        if (year, month) < (today.year, today.month):
            raise ValueError("Thẻ đã hết hạn")
        if not re.fullmatch(r"\d{3,4}", cvv or ""):
            raise ValueError("Mã CVV gồm 3 chữ số ở mặt sau thẻ")
        return digits[-4:]                                  # NFR03: chỉ giữ 4 số cuối

    def process(self, payment: Payment) -> Payment:
        if isinstance(payment, PayCash):          # COD: thu tiền khi giao
            payment.status = PaymentStatus.PENDING
        elif self.gateway.authorize(payment):
            payment.status = PaymentStatus.PAID
            payment.transaction_ref = "TX-" + uuid.uuid4().hex[:10].upper()
        else:
            payment.status = PaymentStatus.FAILED
        return payment

    def refund(self, payment: Payment) -> Payment:
        """Bù trừ khi lưu đơn thất bại sau khi cổng đã ủy quyền (prototype: chỉ đổi trạng thái)."""
        payment.status = PaymentStatus.REFUNDED
        return payment

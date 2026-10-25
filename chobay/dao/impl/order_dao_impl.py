from datetime import datetime
from typing import Optional
from chobay.dao.database import Database
from chobay.dao.interfaces import OrderDAO, ProductDAO
from chobay.model.order import Order, OrderItem, Payment, PayCash, PayCredit, PayEWallet
from chobay.model.enums import OrderStatus, DeliveryPreference, PaymentStatus


class OrderDAOImpl(OrderDAO):
    def __init__(self, db: Database, product_dao: ProductDAO):
        self.db = db
        self.product_dao = product_dao

    def create_order(self, order: Order) -> int:
        with self.db.connect() as con:
            cur = con.execute("""INSERT INTO orders(customer_id, address_id, order_date, status, subtotal,
                                 shipping_fee, discount, total, preference) VALUES (?,?,?,?,?,?,?,?,?)""",
                              (order.customer_id, order.address_id, order.order_date.isoformat(timespec="seconds"),
                               order.status.value, order.subtotal(), order.shipping_fee, order.discount,
                               order.total(), order.preference.value))
            order_id = cur.lastrowid
            con.executemany("INSERT INTO order_item(order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
                            [(order_id, i.product.product_id, i.quantity, i.unit_price) for i in order.items])
        order.order_id = order_id
        return order_id

    def get_order(self, order_id: int) -> Optional[Order]:
        with self.db.connect() as con:
            r = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not r:
                return None
            items = con.execute("SELECT * FROM order_item WHERE order_id = ?", (order_id,)).fetchall()
            p = con.execute("""SELECT p.*, c.card_last4, w.wallet_provider FROM payment p
                               LEFT JOIN pay_credit c ON c.payment_id = p.payment_id
                               LEFT JOIN pay_ewallet w ON w.payment_id = p.payment_id
                               WHERE p.order_id = ?""", (order_id,)).fetchone()
        order = Order(r["order_id"], r["customer_id"], r["address_id"],
                      [OrderItem(self.product_dao.get_item(i["product_id"]), i["quantity"], i["unit_price"]) for i in items],
                      OrderStatus(r["status"]), datetime.fromisoformat(r["order_date"]), r["shipping_fee"],
                      r["discount"], DeliveryPreference(r["preference"]))
        if p:
            base = dict(amount=p["amount"], status=PaymentStatus(p["status"]), transaction_ref=p["transaction_ref"])
            order.payment = (PayCredit(**base, card_last4=p["card_last4"] or "") if p["method"] == "CREDIT" else
                             PayEWallet(**base, wallet_provider=p["wallet_provider"] or "") if p["method"] == "EWALLET" else
                             PayCash(**base))
        return order

    def find_by_customer(self, customer_id: int) -> list[Order]:
        with self.db.connect() as con:
            ids = [r[0] for r in con.execute("SELECT order_id FROM orders WHERE customer_id = ? ORDER BY order_id DESC",
                                             (customer_id,))]
        return [self.get_order(i) for i in ids]

    def update_status(self, order_id: int, status: OrderStatus) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status.value, order_id))

    def mark_paid(self, order_id: int) -> None:
        """COD: tiền được thu khi giao xong → thanh toán chuyển PAID."""
        with self.db.connect() as con:
            con.execute("UPDATE payment SET status = 'PAID', paid_at = ? WHERE order_id = ? AND status = 'PENDING'",
                        (datetime.now().isoformat(timespec="seconds"), order_id))

    def save_payment(self, order_id: int, payment: Payment) -> None:
        with self.db.connect() as con:
            cur = con.execute("""INSERT INTO payment(order_id, method, amount, status, transaction_ref, paid_at)
                                 VALUES (?,?,?,?,?,?)""",
                              (order_id, payment.method(), payment.amount, payment.status.value, payment.transaction_ref,
                               datetime.now().isoformat(timespec="seconds") if payment.status == PaymentStatus.PAID else None))
            pid = cur.lastrowid
            if isinstance(payment, PayCredit):
                con.execute("INSERT INTO pay_credit(payment_id, card_last4) VALUES (?,?)", (pid, payment.card_last4))
            elif isinstance(payment, PayEWallet):
                con.execute("INSERT INTO pay_ewallet(payment_id, wallet_provider) VALUES (?,?)", (pid, payment.wallet_provider))
            else:
                con.execute("INSERT INTO pay_cash(payment_id, cash_tendered) VALUES (?, NULL)", (pid,))

from chobay.dao.database import Database
from chobay.dao.interfaces import CartDAO, ProductDAO
from chobay.model.cart import Cart, CartItem
from chobay.model.customer import Customer
from chobay.model.product import Product


class CartDAOImpl(CartDAO):
    def __init__(self, db: Database, product_dao: ProductDAO):
        self.db = db
        self.product_dao = product_dao

    def get_cart(self, customer: Customer) -> Cart:
        with self.db.connect() as con:
            r = con.execute("SELECT cart_id FROM cart WHERE customer_id = ?", (customer.customer_id,)).fetchone()
            if r is None:
                cur = con.execute("INSERT INTO cart(customer_id) VALUES (?)", (customer.customer_id,))
                cart_id = cur.lastrowid
            else:
                cart_id = r["cart_id"]
            rows = con.execute("SELECT * FROM cart_item WHERE cart_id = ? ORDER BY cart_item_id", (cart_id,)).fetchall()
        items = []
        for x in rows:                                    # cart_price = giá hiện tại; đổi giá thì cập nhật giỏ
            p = self.product_dao.get_item(x["product_id"])
            if p.price != x["cart_price"]:
                with self.db.connect() as con:
                    con.execute("UPDATE cart_item SET cart_price = ? WHERE cart_item_id = ?", (p.price, x["cart_item_id"]))
            items.append(CartItem(p, x["quantity"], p.price))
        return Cart(cart_id, customer.customer_id, items)

    def add_item(self, cart: Cart, product: Product, qty: int) -> None:
        with self.db.connect() as con:
            con.execute("""INSERT INTO cart_item(cart_id, product_id, quantity, cart_price) VALUES (?,?,?,?)
                           ON CONFLICT(cart_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity,
                           cart_price = excluded.cart_price""", (cart.cart_id, product.product_id, qty, product.price))
            con.execute("UPDATE cart SET updated_at = CURRENT_TIMESTAMP WHERE cart_id = ?", (cart.cart_id,))

    def update_cart(self, cart: Cart) -> None:
        with self.db.connect() as con:
            for it in cart.items:
                con.execute("UPDATE cart_item SET quantity = ?, cart_price = ? WHERE cart_id = ? AND product_id = ?",
                            (it.quantity, it.cart_price, cart.cart_id, it.product.product_id))

    def remove_item(self, cart: Cart, product_id: int) -> None:
        with self.db.connect() as con:
            con.execute("DELETE FROM cart_item WHERE cart_id = ? AND product_id = ?", (cart.cart_id, product_id))

    def clear(self, cart: Cart) -> None:
        with self.db.connect() as con:
            con.execute("DELETE FROM cart_item WHERE cart_id = ?", (cart.cart_id,))

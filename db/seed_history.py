"""Sinh dữ liệu lịch sử cho CSDL mẫu: đơn hàng đã giao trong 3 tuần gần đây, đánh giá sản phẩm, lịch sử tìm kiếm.

Đơn hàng đi qua ĐÚNG các lớp nghiệp vụ của ứng dụng (CartService → OrderService.checkout → DeliveryDispatcher
→ duyệt UC15 nếu cần → simulate_delivery), nên mỗi đơn có đủ order_item, payment (+ pay_cash / pay_credit / pay_ewallet),
shipping với quyết định AI (điểm, độ tin cậy, lý do) và tracking_event như đơn khách đặt trên web.
Sau đó chỉ lùi mốc thời gian về quá khứ, trả tồn kho và phương tiện về trạng thái ban đầu để buổi demo bắt đầu sạch.

Chạy tự động ở cuối  python -m db.init_db  (random.seed cố định → lần nào cũng ra cùng một bộ dữ liệu)."""
from __future__ import annotations
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from db import seed_data as S

SEED = 2026
DAYS = 21                      # lịch sử 3 tuần
N_ORDERS = 120
CARD = ("4242 4242 4242 4242", "12/30", "123")

# khách có lịch sử (khách 2 — giabao — là khách mới, giữ nguyên voucher chào mừng cho demo); trọng số = tần suất mua
BUYERS = {1: 6, 3: 3, 4: 4, 5: 5, 6: 6, 7: 8, 8: 5, 9: 7, 10: 6, 11: 3, 12: 4, 13: 8, 14: 5, 15: 4}

# giỏ hàng mẫu theo thói quen mua (id sản phẩm trong seed_data.PRODUCTS)
BASKETS = [
    [6, 8, 13], [1, 2, 12], [3, 19, 18], [16, 22], [21, 18, 12], [20, 21], [11, 9], [6, 6, 13, 19],
    [15, 18], [14, 8], [5, 19], [4, 21, 18], [10, 16], [1, 1, 3, 12], [7], [17], [22, 16, 10],
    [19, 13, 9], [2, 11], [20, 12, 18], [8, 8, 6], [15, 4], [11, 6, 13], [3, 3, 2], [16, 10, 8],
]

COMMENTS = {
    5: ["Hàng tươi, đóng gói cẩn thận, giao nhanh hơn dự kiến.", "Chất lượng tốt, sẽ mua lại.",
        "Giao đúng khung giờ, hàng còn mát lạnh.", "Đúng như mô tả, giá hợp lý.", "Rất hài lòng, shop đóng gói kỹ.",
        "Ngon, cả nhà đều khen.", ""],
    4: ["Hàng ổn, giao hơi trễ vài phút.", "Chất lượng tốt nhưng bao bì hơi móp.", "Ổn so với giá tiền.",
        "Hàng đúng mô tả, lần sau mong giao sớm hơn.", ""],
    3: ["Tạm được, chưa như kỳ vọng.", "Hàng bình thường, giao đúng giờ.", "Hạn sử dụng hơi ngắn."],
    2: ["Hàng tới hơi dập, đã báo shop.", "Không tươi bằng lần trước."],
    1: ["Giao thiếu hàng, phải liên hệ lại."],
}

MODE_COMMENTS = {                      # nhận xét 5 sao nhắc tới đúng phương tiện đã giao đơn đó
    "DRONE": "Giao bằng drone tới tận ban công, con mình thích lắm.",
    "SUBMARINE": "Ở đảo mà vẫn nhận được hàng tươi, tàu ngầm giao đúng hẹn.",
    "LOCKER": "Nhận ở tủ khóa tiện, đi làm về ghé lấy luôn.",
    "AUTO_BOAT": "Xuồng giao tới bến gần nhà, hàng còn mát.",
    "FLYING_CAR": "Ô tô bay giao nhanh thật, ở ngoại thành mà chưa tới 1 tiếng.",
}

TEXT_QUERIES = ["sữa tươi", "sua chua dau", "mì tôm", "mi kim chi", "tương ớt chinsu", "trứng gà", "rau muống",
                "thanh long", "xoài cát", "sầu riêng", "tôm sú", "thịt ba chỉ", "cá basa", "kem sầu riêng",
                "cà phê g7", "sữa đặc", "nước dừa", "bánh mì", "gạo nếp", "bánh phở", "bún bò huế",
                "sữa tươi dưới 40k", "trái cây", "đồ đông lạnh", "hải sản tươi", "thung sua vinamilk"]
VOICE_QUERIES = ["tìm giúp mình kem sầu riêng nha", "cho mình mua sữa tươi không đường",
                 "mình muốn mua trứng gà", "có tôm sú tươi không", "tìm mì gói dưới 10.000 đồng",
                 "mua rau muống nấu canh", "cho tôi xem xoài cát hòa lộc", "tìm nước dừa"]
IMAGE_FILES = ["ca_basa_khach_chup.jpg", "rau_muong_khach_chup.jpg", "sau_rieng_khach_chup.jpg",
               "thanh_long_khach_chup.jpg", "tom_khach_chup.jpg", "trung_ga_khach_chup.jpg"]


def _weather(rnd: random.Random, ts: datetime):
    from chobay.ai.delivery.rules import Weather
    rainy = ts.hour >= 14 and rnd.random() < 0.35                     # mùa mưa TP.HCM: mưa chiều
    rain = round(rnd.uniform(4, 30), 1) if rainy else 0.0
    wind = round(rnd.uniform(6, 13) if rainy else rnd.uniform(1.5, 7), 1)
    traffic = 0.85 if ts.hour in (7, 8, 17, 18, 19) else round(rnd.uniform(0.35, 0.65), 2)
    return Weather(rain_mmh=rain, wind_ms=wind, traffic_index=traffic, hour=ts.hour)


def _timeline(rnd: random.Random, now: datetime) -> list[datetime]:
    start = (now - timedelta(days=DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for _ in range(N_ORDERS):
        day = start + timedelta(days=rnd.randrange(DAYS))
        hour = rnd.choices(range(7, 22), weights=[3, 4, 3, 3, 4, 3, 2, 2, 3, 4, 5, 6, 5, 4, 2])[0]
        out.append(day.replace(hour=hour, minute=rnd.randrange(60), second=rnd.randrange(60)))
    return sorted(out)


def _restore_stock(db: Path) -> None:
    with sqlite3.connect(db) as con:
        con.executemany("UPDATE product SET stock = ? WHERE product_id = ?", [(p[12], p[0]) for p in S.PRODUCTS])


def _place_orders(c, db: Path, rnd: random.Random) -> list[tuple[int, datetime]]:
    from chobay.model.enums import DeliveryPreference, ShippingStatus
    from chobay.service.order_service import CheckoutError
    staff = c.staff_dao.get_by_username("dieuphoi")
    prefs = [DeliveryPreference.FAST, DeliveryPreference.CHEAP, DeliveryPreference.GREEN]
    placed = []
    for ts in _timeline(rnd, datetime.now()):
        cid = rnd.choices(list(BUYERS), weights=list(BUYERS.values()))[0]
        weather = _weather(rnd, ts)
        for _attempt in range(4):                                      # giỏ không giao được → khách đổi giỏ khác
            _restore_stock(db)
            cust = c.customer_dao.get_cust(cid)
            cart = c.cart_service.view_cart(cust)
            for it in list(cart.items):
                c.cart_service.update_quantity(cust, it.product.product_id, 0)
            for pid in rnd.choice(BASKETS):
                c.cart_service.add_to_cart(cust, pid, 1)
            pref = rnd.choices(prefs, weights=[5, 3, 2])[0]
            method = rnd.choices(["CASH", "CREDIT", "EWALLET"], weights=[4, 3, 3])[0]
            mode = None
            if rnd.random() < 0.2:                                     # ~20% khách bấm “Đổi cách giao”
                try:
                    q = c.order_service.quote(cust, cust.default_address().address_id, pref, weather)
                    alt = [o.mode for o in q.options if o.feasible and q.chosen and o.mode != q.chosen.mode]
                    mode = rnd.choice(alt) if alt else None
                except (CheckoutError, ValueError):
                    mode = None
            try:
                order = c.order_service.checkout(
                    cust, cust.default_address().address_id, method, pref, weather,
                    card_number=CARD[0] if method == "CREDIT" else "", expiry=CARD[1] if method == "CREDIT" else "",
                    cvv=CARD[2] if method == "CREDIT" else "", mode=mode,
                    wallet=rnd.choice(["MoMo", "ZaloPay", "VNPAY"]) if method == "EWALLET" else "")
            except CheckoutError:
                continue
            if c.shipping_service.get_by_order(order.order_id).status == ShippingStatus.AWAITING_APPROVAL:
                c.order_service.approve_delivery(order.order_id, staff)     # UC15 — điều phối viên duyệt
            c.order_service.simulate_delivery(order.order_id, staff)
            placed.append((order.order_id, ts))
            break
    return placed


def _backdate(db: Path, placed: list[tuple[int, datetime]], rnd: random.Random) -> None:
    """Lùi mọi mốc thời gian của đơn về thời điểm đặt hàng giả lập (giữ nguyên khoảng cách giữa các sự kiện)."""
    iso = lambda d: d.isoformat(timespec="seconds")                     # noqa: E731
    sql = lambda d: d.strftime("%Y-%m-%d %H:%M:%S")                    # noqa: E731
    with sqlite3.connect(db) as con:
        for oid, ts in placed:
            (real,) = con.execute("SELECT order_date FROM orders WHERE order_id = ?", (oid,)).fetchone()
            delta = ts - datetime.fromisoformat(real)
            sid, = con.execute("SELECT shipping_id FROM shipping WHERE order_id = ?", (oid,)).fetchone()
            approve_wait = timedelta(minutes=rnd.randint(3, 12))
            evs = con.execute("SELECT event_id, ts, status FROM tracking_event WHERE shipping_id = ? ORDER BY event_id",
                              (sid,)).fetchall()
            last = ts
            for k, (eid, ets, st) in enumerate(evs):
                t = datetime.fromisoformat(ets) + delta + (approve_wait if k and evs[0][2] == "AWAITING_APPROVAL" else timedelta())
                con.execute("UPDATE tracking_event SET ts = ? WHERE event_id = ?", (iso(t), eid))
                last = max(last, t)
            con.execute("UPDATE orders SET order_date = ? WHERE order_id = ?", (iso(ts), oid))
            con.execute("UPDATE shipping SET created_at = ?, delivered_at = ? WHERE shipping_id = ?", (sql(ts), sql(last), sid))
            method, = con.execute("SELECT method FROM payment WHERE order_id = ?", (oid,)).fetchone()
            con.execute("UPDATE payment SET paid_at = ? WHERE order_id = ?", (iso(last if method == "CASH" else ts), oid))


def _reviews(db: Path, rnd: random.Random) -> int:
    """~55% món đã giao được khách đánh giá; điểm trung bình mỗi sản phẩm bám sát product.rating (±0,1)."""
    target = {p[0]: p[13] for p in S.PRODUCTS}
    with sqlite3.connect(db) as con:
        rows = con.execute("""SELECT DISTINCT o.customer_id, i.product_id, s.delivered_at, s.mode
                              FROM orders o JOIN order_item i ON i.order_id = o.order_id
                              JOIN shipping s ON s.order_id = o.order_id ORDER BY o.order_id""").fetchall()
        seen, picked = set(), {}
        for cid, pid, delivered, mode in rows:
            if (cid, pid) in seen or rnd.random() > 0.55:
                continue
            seen.add((cid, pid))
            picked.setdefault(pid, []).append([cid, delivered, 5, mode])
        n = 0
        for pid, revs in picked.items():
            for r in revs:
                r[2] = rnd.choices([5, 4, 3, 2], weights=[6, 3, 0.8, 0.2])[0]
            for _ in range(200):                                       # chỉnh để trung bình ≈ rating sản phẩm
                avg = sum(r[2] for r in revs) / len(revs)
                if abs(avg - target[pid]) <= 0.1 or len(revs) < 2:
                    break
                cand = [r for r in revs if (r[2] < 5 if avg < target[pid] else r[2] > 2)]
                rnd.choice(cand)[2] += 1 if avg < target[pid] else -1
            for cid, delivered, rating, mode in revs:
                comment = (MODE_COMMENTS[mode] if rating == 5 and mode in MODE_COMMENTS and rnd.random() < 0.3
                           else rnd.choice(COMMENTS[rating]))
                at = datetime.strptime(delivered, "%Y-%m-%d %H:%M:%S") + timedelta(hours=rnd.uniform(2, 40))
                at = min(at, datetime.now() - timedelta(minutes=30))
                con.execute("INSERT INTO review(customer_id, product_id, rating, comment, created_at) VALUES (?,?,?,?,?)",
                            (cid, pid, rating, comment, at.strftime("%Y-%m-%d %H:%M:%S")))
                n += 1
    return n


def _search_logs(c, db: Path, rnd: random.Random) -> int:
    """~160 lượt tìm (chữ / giọng nói / ảnh) — top_product_id là kết quả thật của AI Search cho từng truy vấn."""
    def top(q):
        res = c.ranking_service.rank(q, c.search_service.retrieve(q), None)
        return res[0].product.product_id if res else None
    pool = [("TEXT", t, top(c.query_service.text_query(t))) for t in TEXT_QUERIES]
    for v in VOICE_QUERIES:
        t = c.speech_service.transcribe(v)
        pool.append(("VOICE", t, top(c.query_service.voice_query(t))))
    img_dir = Path(__file__).resolve().parents[1] / "tests" / "query_images"
    for f in IMAGE_FILES:
        if (img_dir / f).exists():
            pool.append(("IMAGE", f, top(c.query_service.image_query(c.image_service.encode(str(img_dir / f))))))
    weights = [6 if m == "TEXT" else 3 if m == "VOICE" else 2 for m, _, _ in pool]
    now = datetime.now()
    rows = []
    for _ in range(160):
        mode, label, pid = rnd.choices(pool, weights=weights)[0]
        cid = rnd.choice(list(BUYERS) + [None, None, None])            # một phần là khách vãng lai chưa đăng nhập
        ts = now - timedelta(days=rnd.uniform(0.2, DAYS))
        rows.append((cid, mode, label, pid, ts.strftime("%Y-%m-%d %H:%M:%S")))
    rows.sort(key=lambda r: r[4])
    with sqlite3.connect(db) as con:
        con.executemany("INSERT INTO search_log(customer_id, mode, query, top_product_id, ts) VALUES (?,?,?,?,?)", rows)
    return len(rows)


def generate(db: Path) -> dict:
    from chobay import Container
    from chobay.dao.database import Database
    rnd = random.Random(SEED)
    c = Container(Database(db))
    placed = _place_orders(c, db, rnd)
    _backdate(db, placed, rnd)
    _restore_stock(db)
    with sqlite3.connect(db) as con:                                   # đội phương tiện rảnh, pin như ban đầu
        con.executemany("UPDATE vehicle SET status = ?, battery_pct = ? WHERE vehicle_id = ?",
                        [(v[4], v[5], v[0]) for v in S.VEHICLES])
        con.execute("DELETE FROM cart_item")
    stats = {"orders": len(placed), "reviews": _reviews(db, rnd), "search_logs": _search_logs(c, db, rnd)}
    return stats

"""Kiểm thử đơn vị & tích hợp Pop-up Market — chạy: python -m pytest -q"""
import re
import shutil
import pytest
from pathlib import Path
from chobay import Container
from chobay.dao.database import Database
from chobay.ai.delivery.rules import DeliveryRequest, Weather
from chobay.model.cart import CartItem
from chobay.model.enums import DeliveryMode, DeliveryPreference, OrderStatus, ShippingStatus
from chobay.service.order_service import CheckoutError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def c(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "test.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    return Container(Database(db))


def web(tmp_path, user=None, name="web.db"):
    """Ứng dụng web trên bản sao CSDL; user ≠ None → đăng nhập trước (UC01), mật khẩu mẫu chobay123."""
    from chobay import create_app
    db = tmp_path / name
    shutil.copy(ROOT / "db" / "chobay.db", db)
    app = create_app(str(db))
    cl = app.test_client()
    if user:
        assert cl.post("/login", data={"username": user, "password": "chobay123"}).status_code == 302
    return app, cl


def req(c, cid, items, w=Weather()):
    cu = c.customer_dao.get_cust(cid)
    return DeliveryRequest([CartItem(c.product_dao.get_item(p), q, c.product_dao.get_item(p).price) for p, q in items],
                           cu.default_address(), w)


# ---------- Luật giao hàng (business rules) ----------
def test_TC01_drone_rejects_heavy_order(c):
    d = c.dispatcher.decide(req(c, 1, [(7, 1)]))                       # thùng sữa 9,6 kg
    drone = next(o for o in d.options if o.mode == DeliveryMode.DRONE)
    assert not drone.feasible and drone.violations[0].code == "BR-D01"


def test_TC02_island_goes_by_submarine_and_needs_approval(c):
    d = c.dispatcher.decide(req(c, 3, [(20, 1), (14, 1)]))
    assert d.chosen.mode == DeliveryMode.SUBMARINE and d.needs_human


def test_TC03_durian_never_on_flying_car(c):
    d = c.dispatcher.decide(req(c, 5, [(17, 1)]))
    fc = next(o for o in d.options if o.mode == DeliveryMode.FLYING_CAR)
    assert any(v.code == "BR-D09" for v in fc.violations)


def test_TC04_storm_grounds_drones(c):
    d = c.dispatcher.decide(req(c, 1, [(8, 1)], Weather(rain_mmh=25, wind_ms=12)))
    assert d.chosen.mode != DeliveryMode.DRONE


def test_TC05_frozen_needs_freezer_or_fast(c):
    d = c.dispatcher.decide(req(c, 5, [(15, 3)]))
    assert d.chosen.vehicle.has_freezer


# ---------- AI Search ----------
def test_TC06_search_without_accents(c):
    q = c.query_service.text_query("nuoc dua")
    top = c.ranking_service.rank(q, c.search_service.retrieve(q))
    assert top[0].product.product_id == 10


def test_TC07_price_filter(c):
    q = c.query_service.text_query("sữa tươi dưới 40k")
    assert q.max_price == 40_000
    assert all(x.product.price <= 40_000 for x in c.search_service.retrieve(q))


def test_TC08_voice_search(c):
    q = c.query_service.voice_query(c.speech_service.transcribe("tìm giúp mình kem sầu riêng nha"))
    assert c.ranking_service.rank(q, c.search_service.retrieve(q))[0].product.product_id == 14


def test_TC09_image_search_dragon_fruit(c):
    emb = c.image_service.encode(str(ROOT / "tests/query_images/thanh_long_khach_chup.jpg"))
    q = c.query_service.image_query(emb)
    assert c.ranking_service.rank(q, c.search_service.retrieve(q))[0].product.product_id == 16


# ---------- Checkout: Cart → Order ----------
def test_TC10_checkout_transforms_cart_to_order(c):
    cust = c.customer_dao.get_cust(1)
    stock_before = c.product_dao.get_item(8).stock
    c.cart_service.add_to_cart(cust, 8, 2)
    c.cart_service.add_to_cart(cust, 13, 1)
    order = c.order_service.checkout(cust, 1, "EWALLET", DeliveryPreference.FAST, Weather(), wallet="MoMo")
    assert [i.product.product_id for i in order.items] == [8, 13]           # CartItem → OrderItem
    assert c.cart_service.view_cart(cust).is_empty()                         # giỏ rỗng sau checkout
    assert c.product_dao.get_item(8).stock == stock_before - 2               # trừ tồn kho
    assert order.status == OrderStatus.PAID
    s = c.shipping_dao.get_by_order(order.order_id)
    assert s.mode == DeliveryMode.DRONE and s.status == ShippingStatus.ASSIGNED


def test_TC11_payment_rejected_keeps_cart(c):
    cust = c.customer_dao.get_cust(2)
    c.cart_service.add_to_cart(cust, 1, 3)
    with pytest.raises(CheckoutError):
        c.order_service.checkout(cust, 2, "CREDIT", DeliveryPreference.CHEAP, Weather(),
                                 "4000 0000 0000 0002", expiry="12/30", cvv="123")   # thẻ thử bị ngân hàng từ chối
    assert not c.cart_service.view_cart(cust).is_empty()


def test_TC12_unit_price_preserved_after_price_change(c):
    cust = c.customer_dao.get_cust(4)
    c.cart_service.add_to_cart(cust, 22, 1)
    order = c.order_service.checkout(cust, 4, "CASH", DeliveryPreference.GREEN, Weather())
    with c.product_dao.db.connect() as con:
        con.execute("UPDATE product SET price = price + 10000 WHERE product_id = 22")
    again = c.order_dao.get_order(order.order_id)
    assert again.items[0].unit_price == 75_000


# ---------- Search Order (A06) ----------
def test_TC13_search_order_by_text_and_voice(c):
    cust = c.customer_dao.get_cust(3)
    c.cart_service.add_to_cart(cust, 5, 1)
    order = c.order_service.checkout(cust, 3, "CASH", DeliveryPreference.FAST, Weather())
    q = c.query_service.text_query(f"đơn hàng số {order.order_id}")
    assert q.intent == "ORDER" and [o.order_id for o in c.search_service.find_orders(q, 3)] == [order.order_id]
    q = c.query_service.voice_query(c.speech_service.transcribe("đơn hàng gần nhất của mình đâu rồi"))
    assert c.search_service.find_orders(q, 3)[0].order_id == order.order_id
    assert c.search_service.find_orders(c.query_service.text_query(f"đơn {order.order_id}"), 1) == []   # đơn người khác: không thấy


# ---------- NFR06: checkout là một giao dịch nguyên tử ----------
def test_TC14_checkout_rolls_back_when_a_step_fails(c, monkeypatch):
    cust = c.customer_dao.get_cust(2)
    c.cart_service.update_quantity(cust, 1, 0)
    c.cart_service.add_to_cart(cust, 9, 1)
    stock_before = c.product_dao.get_item(9).stock
    with c.product_dao.db.connect() as con:
        n_before = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    def boom(*a, **k):
        raise RuntimeError("fleet offline")
    monkeypatch.setattr(c.shipping_service, "create_shipping", boom)
    with pytest.raises(CheckoutError):
        c.order_service.checkout(cust, 2, "EWALLET", DeliveryPreference.FAST, Weather(), wallet="ZaloPay")
    with c.product_dao.db.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == n_before          # không có đơn dở dang
    assert c.product_dao.get_item(9).stock == stock_before                                    # tồn kho không bị trừ
    assert not c.cart_service.view_cart(cust).is_empty()                                     # giỏ còn nguyên


# ---------- Kiến trúc: tầng trình bày không gọi tầng dữ liệu ----------
def test_TC15_controllers_never_touch_dao():
    for f in (ROOT / "chobay" / "controller").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "_dao" not in src and "chobay.dao" not in src, f.name


# ---------- NFR03: mật khẩu chỉ lưu dạng băm ----------
def test_TC16_password_stored_as_salted_hash(c):
    cust = c.customer_service.get_customer(1)
    assert cust.account.password_hash.startswith("pbkdf2_sha256$") and "chobay123" not in cust.account.password_hash
    assert c.customer_service.verify_password(cust, "chobay123")
    assert not c.customer_service.verify_password(cust, "sai-mat-khau")


# ---------- FR19 / NFR05: AI lỗi → luật dự phòng, đơn vẫn có cách giao ----------
def test_TC17_model_failure_falls_back_and_needs_human(tmp_path, monkeypatch):
    db = tmp_path / "fresh.db"                                              # CSDL sạch: mọi phương tiện đang rảnh
    shutil.copy(ROOT / "db" / "chobay.db", db)
    c = Container(Database(db))

    def broken(*a, **k):
        raise TimeoutError("model unavailable")
    monkeypatch.setattr(c.dispatcher.eta, "predict", broken)
    d = c.dispatcher.decide(req(c, 2, [(19, 1)]))
    assert d.fallback_used and d.needs_human and d.chosen.mode in (DeliveryMode.EBIKE, DeliveryMode.AUTO_CAR)
    d = c.dispatcher.decide(req(c, 3, [(5, 1)]))                           # xã đảo → tàu ngầm
    assert d.fallback_used and d.chosen.mode == DeliveryMode.SUBMARINE


# ---------- Dữ liệu vào sai: báo lỗi nghiệp vụ, không làm hỏng dữ liệu ----------
def test_TC18_invalid_input_is_rejected(c):
    from chobay.service.cart_service import CartError
    cust = c.customer_dao.get_cust(5)
    for bad in (0, -3):
        with pytest.raises(CartError):
            c.cart_service.add_to_cart(cust, 1, bad)                         # số lượng ≤ 0
    with pytest.raises(CartError):
        c.cart_service.add_to_cart(cust, 9999, 1)                            # sản phẩm không tồn tại
    c.cart_service.add_to_cart(cust, 1, 1)
    for addr, method, card in ((3, "CASH", ""), (999, "CASH", ""), (5, "BITCOIN", ""), (5, "CREDIT", "4242 4242 4242 4241"),
                               (5, "EWALLET", "")):
        with pytest.raises(CheckoutError):                                   # địa chỉ người khác, cách trả lạ, thẻ sai
            c.order_service.checkout(cust, addr, method, DeliveryPreference.FAST, Weather(), card)
    assert not c.cart_service.view_cart(cust).is_empty()                    # giỏ vẫn còn


# ---------- BR-H1 + BR-D12: chưa duyệt không được chạy; giao xong trả phương tiện ----------
def test_TC19_trip_lifecycle_respects_approval(tmp_path):
    db = tmp_path / "life.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    c = Container(Database(db))
    staff = c.staff_dao.get_by_username("dieuphoi")                          # điều phối viên (UC15)
    cust = c.customer_dao.get_cust(3)                                        # xã đảo → tàu ngầm, cần duyệt
    c.cart_service.add_to_cart(cust, 20, 1)
    order = c.order_service.checkout(cust, 3, "CASH", DeliveryPreference.FAST, Weather())
    with pytest.raises(PermissionError):
        c.order_service.approve_delivery(order.order_id, None)               # không phải điều phối viên → cấm
    with pytest.raises(ValueError):
        c.order_service.simulate_delivery(order.order_id, staff)             # chưa duyệt → không cho xuất phát
    c.order_service.approve_delivery(order.order_id, staff)
    with pytest.raises(ValueError):
        c.order_service.approve_delivery(order.order_id, staff)              # không duyệt lần hai
    c.order_service.simulate_delivery(order.order_id, staff)
    s = c.shipping_dao.get_by_order(order.order_id)
    assert s.status == ShippingStatus.DELIVERED and s.approved_by == "dieuphoi"
    assert c.order_dao.get_order(order.order_id).status == OrderStatus.DELIVERED
    assert s.vehicle_id in [v.vehicle_id for v in c.vehicle_dao.find_available(DeliveryMode.SUBMARINE)]   # rảnh lại
    with pytest.raises(ValueError):
        c.order_service.simulate_delivery(order.order_id, staff)             # không giao lại lần hai


# ---------- Giá và ưu đãi ----------
def test_TC20_checkout_uses_current_price_and_total_never_negative(c):
    cust = c.customer_dao.get_cust(4)
    c.cart_service.add_to_cart(cust, 9, 1)
    with c.product_dao.db.connect() as con:
        con.execute("UPDATE product SET price = price + 5000 WHERE product_id = 9")
    now = c.product_dao.get_item(9).price
    assert c.cart_service.view_cart(cust).items[0].cart_price == now         # giỏ hiện giá mới
    order = c.order_service.checkout(cust, 4, "CASH", DeliveryPreference.GREEN, Weather())
    assert order.items[0].unit_price == now and order.total() >= 0


# ---------- Giao diện: dữ liệu vào sai không gây lỗi 500 ----------
def test_TC21_web_routes_never_crash_on_bad_input(tmp_path):
    app, cl = web(tmp_path, "minhanh")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    cl.post("/cart/add/13", data={"qty": 1})
    calls = [("post", "/cart/add/8", {"qty": -5}), ("post", "/cart/add/9999", {"qty": 1}), ("get", "/checkout?pref=XYZ", None),
             ("get", "/checkout?address=999", None), ("post", "/checkout", {"address": 999, "method": "CASH"}),
             ("post", "/checkout", {"method": "BITCOIN", "address": 1}), ("post", "/checkout", {"address": 1, "mode": "UFO"}),
             ("post", "/dispatch/9999/approve", None), ("post", "/dispatch/9999/depart", None), ("get", "/order/9999", None),
             ("get", "/cart", None), ("post", "/login", {"username": "x"}), ("get", "/login?next=//evil.example", None),
             ("post", "/search", {"q": "<script>x</script>", "mode": "TEXT"}), ("post", "/search", {"q": "a" * 500, "mode": "VOICE"})]
    for method, url, data in calls:
        r = getattr(cl, method)(url, data=data)
        assert r.status_code < 500, (url, r.status_code)
        assert b"<script>x</script>" not in r.data


# ---------- FR09: trang sản phẩm cho biết cách giao phù hợp ----------
def test_TC22_product_shows_matching_delivery_modes(c):
    from chobay.service.catalog_service import CatalogService
    cat = CatalogService(c.product_dao)
    fit = dict(cat.delivery_fit(c.product_dao.get_item(17)))                  # sầu riêng: mùi mạnh
    assert fit["Ô tô bay chở hàng (eVTOL)"] == "BR-D09"
    fish = dict(cat.delivery_fit(c.product_dao.get_item(15), qty=3))         # cá basa đông lạnh 3 kg
    assert fish["Drone giao hàng"] == "BR-D01" and fish["Xe tự lái (van điện không người lái)"] is None


# ---------- Voice: chuẩn hóa bản phiên âm Web Speech API + nghe chưa rõ ----------
def test_TC23_voice_transcript_normalized_and_low_confidence(tmp_path):
    from chobay import create_app
    from chobay.ai.search.speech_service import SpeechService
    sp = SpeechService()
    assert sp.transcribe("  sữa tươi dưới 40.000 đồng ") == "sữa tươi dưới 40000"
    assert sp.transcribe("dầu ăn dưới 1,5 triệu") == "dầu ăn dưới 1500000"
    db = tmp_path / "voice.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    cl = create_app(str(db)).test_client()
    ok = cl.post("/search", data={"q": "Sữa tươi dưới 40.000 đồng", "mode": "VOICE", "conf": "0.91"}).get_data(as_text=True)
    assert "392.000" not in ok and "Sữa tươi" in ok                       # bộ lọc giá hiểu "40.000 đồng"
    low = cl.post("/search", data={"q": "kem", "mode": "VOICE", "conf": "0.1"}).get_data(as_text=True)
    assert "Nghe chưa rõ" in low


# ---------- Image: trang kết quả hiện lại ảnh khách tải lên (không lưu xuống đĩa) ----------
def test_TC24_image_search_shows_uploaded_photo(tmp_path):
    from chobay import create_app
    db = tmp_path / "img.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    before = {p for p in ROOT.rglob("*") if p.is_file() and ".pytest_cache" not in p.parts and "__pycache__" not in p.parts}
    with open(ROOT / "tests/query_images/thanh_long_khach_chup.jpg", "rb") as fh:
        html = create_app(str(db)).test_client().post(
            "/search", data={"mode": "IMAGE", "image": (fh, "thanh_long.jpg")}, content_type="multipart/form-data").get_data(as_text=True)
    assert html.count('src="data:image/jpeg;base64,') >= 2          # ảnh trong khung kết quả + thumbnail trong ô tìm kiếm
    assert "Đã tìm bằng ảnh thanh_long.jpg" in html and "Sản phẩm giống ảnh của bạn" in html
    assert re.search(r'class="n"[^>]*>([^<]+)<', html).group(1).startswith("Thanh long")   # thanh long đứng đầu
    after = {p for p in ROOT.rglob("*") if p.is_file() and ".pytest_cache" not in p.parts and "__pycache__" not in p.parts}
    assert after == before                                           # NFR riêng tư: không ghi ảnh tải lên


# ---------- Giao diện khách không lộ thông tin kỹ thuật; Chế độ demo mới hiện ----------
def test_TC25_customer_pages_show_no_internals_dispatcher_sees_ai_reason(tmp_path):
    app, cl = web(tmp_path, "thuha", "ui.db")
    cl.post("/cart/add/14", data={"qty": 1})                                     # khách xã đảo mua kem
    oid = re.search(r"/order/(\d+)", cl.post("/checkout", data={"address": 3, "method": "CASH", "pref": "FAST"}).headers["Location"]).group(1)
    pages = ["/search?q=sữa+tươi+dưới+40k", "/product/14", "/cart", f"/order/{oid}"]
    internals = ["Biểu diễn truy vấn", "S_text", "BR-D", "AWAITING_APPROVAL", "FROZEN", "FAST", "Duyệt chuyến", "demo"]
    def visible(url):                                                              # chữ khách nhìn thấy (bỏ thẻ, script)
        html = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", cl.get(url).get_data(as_text=True))
        return re.sub(r"<[^>]+>", " ", html)
    for url in pages:
        assert not [w for w in internals if w in visible(url)], url
    assert "Chờ xác nhận chuyến" in visible(f"/order/{oid}")                       # trạng thái tiếng Việt
    assert cl.get("/dispatch").status_code == 302                                   # khách không vào được Bảng điều phối
    cl.post("/logout")
    cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    board = cl.get("/dispatch").get_data(as_text=True)
    assert "Duyệt chuyến" in board
    assert "Chọn SUBMARINE" in cl.get(f"/dispatch/{oid}").get_data(as_text=True)   # lý do AI lưu trong Shipping (NFR12)


# ---------- Xếp hạng: chỉ trả sản phẩm liên quan, không lấp cho đủ số ----------
def test_TC26_ranking_keeps_only_relevant_products(c):
    def top(text=None, img=None):
        emb = c.image_service.encode(str(ROOT / img)) if img else None
        q = c.query_service.multimodal_query(text, emb) if text and img else c.query_service.image_query(emb) if img \
            else c.query_service.text_query(text)
        return [x.product.product_id for x in c.ranking_service.rank(q, c.search_service.retrieve(q))]
    assert top(img="tests/query_images/tom_khach_chup.jpg") == [20]                   # ảnh tôm → chỉ tôm
    assert top(text="tương ớt chinsu", img="tests/query_images/tom_khach_chup.jpg")[0] == 12   # chữ rõ ràng thắng ảnh lệch
    assert top("thịt") == [21]                                                         # khớp tên món, không kéo cả nhóm
    assert set(top("đồ uống")) == {10, 11}                                             # gõ đúng tên nhóm → cả nhóm
    assert top("gia vị") == [12] and top("hải sản") == [20]                            # cụm chứa từ dừng vẫn hiểu
    assert set(top("trái cây")) == {16, 17, 22}                                        # rau muống không phải trái cây


# ---------- Biểu đồ hoạt động Đặt hàng: “Đủ hàng? — không” → quay lại giỏ ----------
def test_TC27_out_of_stock_sends_customer_back_to_cart(tmp_path):
    from chobay import create_app
    db = tmp_path / "stock.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    app = create_app(str(db))
    cl = app.test_client()
    cl.post("/login", data={"username": "minhanh", "password": "chobay123"})
    cl.post("/cart/add/12", data={"qty": 3})
    p = app.extensions["chobay"].product_dao
    p.update_stock(12, -p.get_item(12).stock + 1)                     # kho chỉ còn 1 chai sau khi khách bỏ giỏ 3 chai
    r = cl.get("/checkout")
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")
    assert "không đủ hàng" in cl.get("/cart").get_data(as_text=True)
    r = cl.post("/checkout", data={"address": 1, "method": "CASH", "pref": "FAST"})
    assert r.headers["Location"].endswith("/cart") and p.get_item(12).stock == 1   # không tạo đơn, không trừ kho



# ---------- UC01 Đăng nhập theo vai trò ----------
def test_TC28_login_roles_and_safe_redirect(tmp_path):
    app, cl = web(tmp_path, name="auth.db")
    assert cl.get("/cart").headers["Location"].startswith("/login")             # chưa đăng nhập → về trang đăng nhập
    assert cl.post("/login", data={"username": "minhanh", "password": "sai"}).status_code == 401
    r = cl.post("/login", data={"username": "minhanh", "password": "chobay123", "next": "//evil.example/x"})
    assert r.headers["Location"] == "/"                                         # chặn chuyển hướng ra ngoài
    assert cl.get("/dispatch").status_code == 302                                # khách không có vai trò điều phối
    cl.post("/logout")
    r = cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    assert r.headers["Location"] == "/dispatch" and cl.get("/dispatch").status_code == 200


# ---------- UC05 luồng 5a: khách tự chọn cách giao hợp lệ ----------
def test_TC29_customer_can_choose_another_valid_delivery_mode(c):
    cust = c.customer_dao.get_cust(1)                                          # chung cư Nhà Bè: AI đề xuất drone
    c.cart_service.add_to_cart(cust, 8, 1)
    d = c.order_service.quote(cust, 1, DeliveryPreference.FAST, Weather())
    other = next(o for o in d.options if o.feasible and o.mode != d.chosen.mode)
    order = c.order_service.checkout(cust, 1, "CASH", DeliveryPreference.FAST, Weather(), mode=other.mode)
    s = c.shipping_dao.get_by_order(order.order_id)
    assert s.mode == other.mode and s.ai_reason.startswith("Khách chọn")       # lưu cả lựa chọn của khách lẫn đề xuất AI
    c.cart_service.add_to_cart(cust, 8, 1)
    bad = next(o for o in d.options if not o.feasible)
    with pytest.raises(CheckoutError):
        c.order_service.checkout(cust, 1, "CASH", DeliveryPreference.FAST, Weather(), mode=bad.mode)   # vi phạm luật → từ chối
    assert not c.cart_service.view_cart(cust).is_empty()                         # giỏ vẫn giữ



# ---------- UC07: thanh toán thẻ / ví như sàn TMĐT, chỉ lưu 4 số cuối (NFR03) ----------
def test_TC30_card_checked_only_last4_stored_and_success_page(tmp_path):
    from chobay.service.payment_service import PaymentService
    ps = PaymentService()
    for number, exp, cvv in (("4242 4242 4242 4241", "12/30", "123"), ("4242 4242 4242 4242", "01/20", "123"),
                             ("4242 4242 4242 4242", "13/30", "123"), ("4242 4242 4242 4242", "12/30", "12")):
        with pytest.raises(ValueError):                                           # sai Luhn, hết hạn, tháng sai, CVV sai
            ps.create("CREDIT", 0, number, exp, cvv)
    app, cl = web(tmp_path, "minhanh", "pay.db")
    cl.post("/cart/add/8", data={"qty": 1})
    r = cl.post("/checkout", data={"address": 1, "pref": "FAST", "method": "CREDIT", "card_number": "4242 4242 4242 4242",
                                   "card_exp": "12/30", "card_cvv": "123", "card_name": "NGUYEN MINH ANH"})
    assert r.headers["Location"].endswith("/success")
    page = cl.get(r.headers["Location"]).get_data(as_text=True)
    assert "Đặt hàng thành công" in page and "Thẻ •••• 4242" in page
    import sqlite3
    db = sqlite3.connect(tmp_path / "pay.db")
    oid = int(re.search(r"/order/(\d+)/success", r.headers["Location"]).group(1))
    assert db.execute("""SELECT card_last4 FROM pay_credit JOIN payment USING(payment_id)
                         WHERE order_id = ?""", (oid,)).fetchall() == [("4242",)]
    assert {r[0] for r in db.execute("SELECT card_last4 FROM pay_credit")} == {"4242"}   # mọi đơn: chỉ 4 số cuối
    dump = "\n".join(db.iterdump())
    assert "4242424242424242" not in dump and "4242 4242 4242 4242" not in dump   # không lưu số thẻ đầy đủ



# ---------- Kênh điều phối: lọc theo trạng thái, tìm mã đơn, chi tiết, đội phương tiện (UC15, UC17) ----------
def test_TC31_dispatch_center_filters_detail_fleet(tmp_path):
    app, cl = web(tmp_path, "thuha", "ops.db")
    cl.post("/cart/add/20", data={"qty": 1})
    oid = re.search(r"/order/(\d+)", cl.post("/checkout", data={"address": 3, "method": "CASH", "pref": "FAST"}).headers["Location"]).group(1)
    assert cl.get("/dispatch/fleet").status_code == 302                            # khách không xem được đội xe
    cl.post("/logout"); cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    waiting = cl.get("/dispatch?status=AWAITING_APPROVAL").get_data(as_text=True)
    tag = f">#{oid}</a>"
    assert tag in waiting and tag not in cl.get("/dispatch?status=DELIVERED").get_data(as_text=True)
    assert tag in cl.get(f"/dispatch?q=%23{oid}").get_data(as_text=True)             # tìm theo mã đơn
    detail = cl.get(f"/dispatch/{oid}").get_data(as_text=True)
    assert "Quyết định của AI" in detail and "Lê Thu Hà" in detail and "Duyệt chuyến" in detail
    assert "Thời tiết hiện tại" in detail                                             # UC15 bước 2: kiểm thời tiết
    assert cl.get("/dispatch/99999").status_code == 404
    fleet = cl.get("/dispatch/fleet").get_data(as_text=True)
    assert len(re.findall(r'class="veh ?(busy)?"', fleet)) == 12 and "Đang chạy" in fleet                  # 12 xe; tàu ngầm đang giữ cho đơn
    cl.post("/dispatch/weather", data={"action": "override", "rain": 15, "wind": 14})
    assert "Tạm ngưng" in cl.get("/dispatch/weather").get_data(as_text=True)          # drone dừng khi gió 14 m/s
    cl.post(f"/dispatch/{oid}/approve", headers={"Referer": f"http://localhost/dispatch/{oid}"})
    cl.post(f"/dispatch/{oid}/depart")
    assert tag in cl.get("/dispatch?status=DELIVERED").get_data(as_text=True)


# ---------- Dữ liệu mẫu (db/seed_history.py): đơn đã giao, đánh giá, lịch sử tìm kiếm ----------
def test_TC32_seed_history_is_consistent():
    import sqlite3
    from db import seed_data as S
    db = sqlite3.connect(ROOT / "db" / "chobay.db")
    one = lambda q: db.execute(q).fetchone()[0]                                          # noqa: E731
    assert one("SELECT count(*) FROM orders") >= 100 and one("SELECT count(*) FROM orders WHERE status <> 'DELIVERED'") == 0
    assert one("SELECT count(*) FROM orders o LEFT JOIN shipping s USING(order_id) LEFT JOIN payment p USING(order_id) "
               "WHERE s.shipping_id IS NULL OR p.paid_at IS NULL OR s.status <> 'DELIVERED'") == 0  # đủ giao + đã thu tiền
    assert one("SELECT count(*) FROM shipping WHERE mode IN ('SUBMARINE','FLYING_CAR') AND approved_by IS NULL") == 0  # BR-H1
    assert one("SELECT count(*) FROM orders WHERE customer_id = 2") == 0                  # khách mới giữ voucher
    assert one("SELECT count(*) FROM vehicle WHERE status <> 'IDLE'") == 0 and one("SELECT count(*) FROM cart_item") == 0
    assert dict(db.execute("SELECT product_id, stock FROM product")) == {p[0]: p[12] for p in S.PRODUCTS}
    assert one("""SELECT count(*) FROM review r WHERE NOT EXISTS (SELECT 1 FROM orders o JOIN order_item i USING(order_id)
                  WHERE o.customer_id = r.customer_id AND i.product_id = r.product_id AND datetime(o.order_date) < datetime(r.created_at))""") == 0
    assert one("SELECT max(order_date) FROM orders") < datetime_now_iso()
    assert {m for (m,) in db.execute("SELECT DISTINCT mode FROM search_log")} == {"TEXT", "VOICE", "IMAGE"}


def datetime_now_iso():
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def test_TC33_my_orders_reviews_and_cod_paid(tmp_path):
    app, cl = web(tmp_path, "minhanh", "mine.db")
    page = cl.get("/orders").get_data(as_text=True)
    import sqlite3
    db = sqlite3.connect(tmp_path / "mine.db")
    mine = {r[0] for r in db.execute("SELECT order_id FROM orders WHERE customer_id = 1")}
    other = db.execute("SELECT order_id FROM orders WHERE customer_id <> 1 LIMIT 1").fetchone()[0]
    assert mine and all(f"Đơn #{o}<" in page for o in mine) and f"Đơn #{other}<" not in page   # chỉ đơn của mình
    assert cl.get(f"/order/{other}").status_code == 404
    prod = cl.get("/product/6").get_data(as_text=True)                                     # đánh giá từ người đã mua
    assert "Đánh giá sản phẩm" in prod and "Đã mua hàng" in prod
    cl.post("/cart/add/8", data={"qty": 1})
    oid = re.search(r"/order/(\d+)", cl.post("/checkout", data={"address": 1, "method": "CASH", "pref": "FAST"}).headers["Location"]).group(1)
    pay = lambda: db.execute("SELECT status FROM payment WHERE order_id = ?", (oid,)).fetchone()[0]   # noqa: E731
    assert pay() == "PENDING" and f"Đơn #{oid}<" in cl.get("/orders?tab=SHIP").get_data(as_text=True)
    cl.post("/logout"); cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    cl.post(f"/dispatch/{oid}/depart")
    assert pay() == "PAID"                                                                 # COD thu tiền khi giao xong
    board = cl.get("/dispatch?status=DELIVERED&page=2").get_data(as_text=True)
    assert 'class="pager"' in board and f">#{oid}</a>" not in board                       # phân trang: đơn mới ở trang 1


# ---------- Thời tiết tự động theo dự báo (OpenMeteoWeatherService — IWeatherService) ----------
def _meteo(rain15=0.0, wind=3.0, hours=None, at=None):
    """Phản hồi giả đúng định dạng api.open-meteo.com/v1/forecast (current 15 phút + hourly)."""
    from datetime import datetime, timedelta
    from chobay.service.weather_service import vn_time
    import time as _t
    h0 = vn_time(at or _t.time()).replace(minute=0, second=0, microsecond=0)
    hours = hours or [(0.0, 10, 4.0)] * 12
    return {"current": {"time": h0.isoformat(timespec="minutes"), "interval": 900, "precipitation": rain15, "wind_speed_10m": wind},
            "hourly": {"time": [(h0 + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(len(hours))],
                       "precipitation": [r for r, _, _ in hours], "precipitation_probability": [p for _, p, _ in hours],
                       "wind_speed_10m": [w for _, _, w in hours]}}


def test_TC34_weather_auto_from_forecast_cache_and_fallback():
    from chobay.service.weather_service import OpenMeteoWeatherService
    calls, now = [], [1_800_000_000.0]
    def fetch(lat, lon):
        calls.append((lat, lon))
        if len(calls) >= 3:
            raise OSError("mất mạng")
        return _meteo(rain15=5.0, wind=12.5, hours=[(18.0, 90, 13.0)] + [(0.0, 10, 4.0)] * 11, at=now[0])
    ws = OpenMeteoWeatherService(fetch=fetch, clock=lambda: now[0])
    w = ws.current(10.5410, 106.9620)                                  # xã đảo Thạnh An
    assert (w.rain_mmh, w.wind_ms) == (20.0, 12.5)                      # 5 mm / 15 phút = 20 mm/h
    assert calls == [(10.5, 107.0)] and ws.info(10.54, 106.96)["source"] == "Open-Meteo"
    ws.current(10.54, 106.96); assert len(calls) == 1                    # đệm 15 phút, không gọi lại
    ws.current(10.78, 106.70); assert len(calls) == 2                    # ô lưới khác → gọi riêng (theo địa chỉ giao)
    f = ws.forecast(10.54, 106.96, hours=6)
    assert len(f) == 6 and f[0].rain_mmh == 18.0 and f[0].rain_prob == 90
    now[0] += 16 * 60                                                   # hết hạn đệm + mất mạng → giữ số liệu gần nhất
    assert ws.current(10.54, 106.96).wind_ms == 12.5 and ws.info(10.54, 106.96)["error"]
    assert ws.current(11.2, 106.1).wind_ms == 3.0                       # chưa từng có số liệu → dự phòng mưa 0, gió 3
    n = len(calls); ws.current(11.2, 106.1); assert len(calls) == n      # chờ 5 phút mới thử lại, web không bị chậm
    ws.update(30, 15); assert ws.current(10.54, 106.96).rain_mmh == 30 and ws.info()["mode"] == "MANUAL"
    ws.clear_override(); assert ws.info(10.54, 106.96)["mode"] == "AUTO"


def test_TC35_weather_page_and_ai_use_forecast(tmp_path):
    from chobay import create_app
    from chobay.service.weather_service import OpenMeteoWeatherService
    db = tmp_path / "wx.db"
    shutil.copy(ROOT / "db" / "chobay.db", db)
    storm = OpenMeteoWeatherService(fetch=lambda lat, lon: _meteo(rain15=6.0, wind=14.0))   # bão: 24 mm/h, gió 14 m/s
    app = create_app(str(db), weather_service=storm)
    cl = app.test_client()
    cl.post("/login", data={"username": "minhanh", "password": "chobay123"})
    cl.post("/cart/add/8", data={"qty": 1})
    page = cl.get("/checkout").get_data(as_text=True)
    assert "dự báo tại nơi giao" in page and "mưa 24 mm/h" in page
    assert 'class="mode-name">Drone giao hàng <span class="badge-ai"' not in page          # AI không chọn drone khi bão (BR-D06)
    cl.post("/logout"); cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    wx = cl.get("/dispatch/weather").get_data(as_text=True)
    assert "Tự động theo dự báo" in wx and "Dự báo 6 giờ tới" in wx and "Tạm ngưng" in wx
    cl.post("/dispatch/weather", data={"action": "override", "rain": 0, "wind": 2})
    assert "Về tự động" in cl.get("/dispatch/weather").get_data(as_text=True)
    cl.post("/dispatch/weather", data={"action": "auto"})
    assert "Tự động theo dự báo" in cl.get("/dispatch/weather").get_data(as_text=True)


def test_TC36_reorder_adds_whole_order_capped_by_stock(tmp_path):
    """UC04.1 Mua lại: đưa TOÀN BỘ sản phẩm của đơn cũ vào giỏ; số lượng theo tồn kho; chỉ đơn của chính khách."""
    app, cl = web(tmp_path, "minhanh")
    ct = app.extensions["chobay"]
    cust = ct.customer_dao.find_by_username("minhanh")
    old = next(o for o in ct.order_dao.find_by_customer(cust.customer_id) if len(o.items) >= 3)
    r = cl.post(f"/order/{old.order_id}/reorder", follow_redirects=True)
    assert r.status_code == 200 and f"Đã thêm {len(old.items)} sản phẩm của đơn #{old.order_id}" in r.get_data(as_text=True)
    cart = ct.cart_service.view_cart(cust)
    assert {i.product.product_id: i.quantity for i in cart.items} == {i.product.product_id: i.quantity for i in old.items}
    cl.post(f"/order/{old.order_id}/reorder")                                  # mua lại lần nữa → cộng dồn, không vượt tồn kho
    for i in ct.cart_service.view_cart(cust).items:
        assert i.quantity <= i.product.stock
    # hết hàng → bỏ qua món đó và báo lại, các món còn lại vẫn vào giỏ
    gone = old.items[0].product.product_id
    for it in ct.cart_service.view_cart(cust).items:
        ct.cart_service.update_quantity(cust, it.product.product_id, 0)
    ct.product_dao.update_stock(gone, -ct.product_dao.get_item(gone).stock)
    r = cl.post(f"/order/{old.order_id}/reorder", follow_redirects=True).get_data(as_text=True)
    assert "hết hàng, chưa thêm được" in r
    assert gone not in {i.product.product_id for i in ct.cart_service.view_cart(cust).items}
    assert len(ct.cart_service.view_cart(cust).items) == len(old.items) - 1
    assert cl.post("/order/99999/reorder").status_code == 404
    cl.post("/logout"); cl.post("/login", data={"username": "giabao", "password": "chobay123"})
    assert cl.post(f"/order/{old.order_id}/reorder").status_code == 404        # không mua lại đơn của người khác
    assert 'action="/order/%d/reorder"' % old.order_id not in cl.get("/orders").get_data(as_text=True)


def test_TC37_robust_inputs_and_add_to_cart_in_place(tmp_path):
    """Không còn lỗi 500 với dữ liệu lạ; “+ Giỏ” gửi nền (giữ kết quả tìm kiếm); trang Thời tiết kiểm tra đầu vào."""
    app, cl = web(tmp_path, "giabao")
    assert cl.get("/?cat=999").status_code == 200 and cl.get("/?cat=abc").status_code == 200
    r = cl.post("/cart/add/1", data={"qty": 2}, headers={"X-Requested-With": "fetch"})
    assert r.get_json() == {"ok": True, "message": "Đã thêm vào giỏ", "count": 2}
    r = cl.post("/cart/add/1", data={"qty": 9999}, headers={"X-Requested-With": "fetch"})
    assert r.get_json()["ok"] is False and r.get_json()["count"] == 2           # quá tồn kho → báo lỗi, giỏ giữ nguyên
    assert "cart-del" in cl.get("/cart").get_data(as_text=True)                  # có nút Xóa từng món
    cl.post("/cart/update/1", data={"qty": 0}); assert ct_empty(app, "giabao")
    cl.post("/logout"); cl.post("/login", data={"username": "dieuphoi", "password": "chobay123"})
    for d, msg in [({"action": "override", "rain": "abc", "wind": "3"}, "là số"), ({"action": "override", "rain": "5", "wind": "999"}, "ngoài phạm vi"),
                   ({"action": "override", "rain": "nan", "wind": "3"}, "là số"), ({"action": "zzz"}, "không hợp lệ")]:
        assert msg in cl.post("/dispatch/weather", data=d, follow_redirects=True).get_data(as_text=True)
    w = app.extensions["chobay"].weather_service.current()
    assert (w.rain_mmh, w.wind_ms) == (0.0, 3.0)                                   # giá trị sai không làm đổi thời tiết


def ct_empty(app, username):
    ct = app.extensions["chobay"]
    return ct.cart_service.view_cart(ct.customer_dao.find_by_username(username)).is_empty()

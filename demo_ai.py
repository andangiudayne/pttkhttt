"""Demo console cho Chương 3: AI Search đa phương thức + AI Delivery Dispatcher.
Chạy:  python demo_ai.py"""
import json
import shutil
import tempfile
from pathlib import Path
from chobay import Container
from chobay.dao.database import Database
from chobay.ai.delivery.rules import DeliveryRequest, Weather
from chobay.model.cart import CartItem
from chobay.model.enums import DeliveryPreference

ROOT = Path(__file__).parent
TMP = Path(tempfile.mkdtemp()) / "demo.db"            # chạy trên bản sao → không làm bẩn chobay.db trước buổi demo
shutil.copy(ROOT / "db" / "chobay.db", TMP)
c = Container(Database(TMP))
P = c.product_dao.get_item
out = {"search": [], "dispatch": [], "models": {}}

print("=== Pop-up Market — AI Search Demo ===")
SEARCHES = [
    ("TEXT", "nuoc dua", None, 10),
    ("TEXT", "sữa tươi dưới 40k", None, 6),
    ("TEXT", "mi tom chua cay", None, 1),
    ("VOICE", "tìm giúp mình kem sầu riêng nha", None, 14),
    ("VOICE", "mua cho tôi ít tôm tươi", None, 20),
    ("IMAGE", "", "tests/query_images/thanh_long_khach_chup.jpg", 16),
    ("IMAGE", "", "tests/query_images/sau_rieng_khach_chup.jpg", 17),
    ("IMAGE", "", "tests/query_images/rau_muong_khach_chup.jpg", 18),
    ("MULTI", "trái cây", "tests/query_images/thanh_long_khach_chup.jpg", 16),
    ("TEXT", "ca phe sua", None, 11),
    ("IMAGE", "", "tests/query_images/trung_ga_khach_chup.jpg", 19),
    ("IMAGE", "", "tests/query_images/tom_khach_chup.jpg", 20),
    ("IMAGE", "", "tests/query_images/ca_basa_khach_chup.jpg", 15),
    ("TEXT", "mì tôm chua cay", None, 1),
    ("TEXT", "sua chau dau", None, 8),
    ("VOICE", "cho em một vỉ trứng gà", None, 19),
]
cust = c.customer_dao.get_cust(1)
ok = 0
for mode, text, img, expect in SEARCHES:
    if mode == "VOICE":
        q = c.query_service.voice_query(c.speech_service.transcribe(text))
    elif mode == "IMAGE":
        q = c.query_service.image_query(c.image_service.encode(str(ROOT / img)))
    elif mode == "MULTI":
        q = c.query_service.multimodal_query(text, c.image_service.encode(str(ROOT / img)))
    else:
        q = c.query_service.text_query(text)
    top = c.ranking_service.rank(q, c.search_service.retrieve(q), cust.default_address(), k=3)
    hit = bool(top) and top[0].product.product_id == expect
    ok += hit
    label = text or Path(img).name
    print(f"\n[{mode}] {label!r} → tokens={q.tokens} max_price={q.max_price}")
    for r in top:
        print(f"   {r.product.name:<45} S={r.score:.3f} (text {r.s_text:.2f}, image {r.s_image:.2f}, business {r.s_business:.2f})")
    out["search"].append(dict(mode=mode, query=label, tokens=q.tokens, expect=expect, hit=hit,
                              top=[dict(pid=r.product.product_id, name=r.product.name, score=r.score, s_text=round(r.s_text, 2),
                                        s_image=round(r.s_image, 2), s_business=round(r.s_business, 2)) for r in top]))
print(f"\nProduct search success = {ok}/{len(SEARCHES)} = {ok/len(SEARCHES):.0%}")
out["search_success"] = [ok, len(SEARCHES)]

print("\n=== Pop-up Market — AI Delivery Dispatcher Demo ===")
print(f"ETA model MAE (test) = {c.eta_model.mae:.2f} phút · Risk model AUC = {c.risk_model.auc:.3f}")
out["models"] = dict(eta_mae=round(c.eta_model.mae, 2), risk_auc=round(c.risk_model.auc, 3))
SCEN = [
    ("S1 Chung cư Nhà Bè — sữa chua + bánh mì (nhẹ, mát)", 1, [(8, 1), (13, 2)], Weather(0, 4, 0.7, 8), "FAST"),
    ("S2 Chung cư Nhà Bè — 2 thùng sữa 48 hộp (19,2 kg)", 1, [(7, 2)], Weather(0, 4, 0.7, 8), "CHEAP"),
    ("S3 Xã đảo Thạnh An — tôm + kem sầu riêng + gạo", 3, [(20, 2), (14, 1), (5, 1)], Weather(15, 14, 0.3, 10), "FAST"),
    ("S4 Ven sông Q12 — sầu riêng + xoài", 4, [(17, 1), (22, 2)], Weather(0, 5, 0.8, 17), "GREEN"),
    ("S5 Thủ Dầu Một — cá basa đông lạnh 3 kg", 5, [(15, 3)], Weather(0, 6, 0.9, 18), "FAST"),
    ("S6 Thủ Dầu Một — sầu riêng (mùi mạnh)", 5, [(17, 1)], Weather(0, 6, 0.9, 18), "FAST"),
    ("S7 Nhà phố Q1 — trứng + rau, trời mưa to", 2, [(19, 1), (18, 1)], Weather(25, 11, 0.8, 18), "FAST"),
]
for title, cid, items, w, pref in SCEN:
    cu = c.customer_dao.get_cust(cid)
    req = DeliveryRequest([CartItem(P(pid), q, P(pid).price) for pid, q in items], cu.default_address(), w)
    d = c.dispatcher.decide(req, DeliveryPreference(pref))
    print(f"\n{title}  [{pref}] weight={req.weight} kg, coldest={req.coldest.value}")
    for o in d.options:
        flag = "✓" if o.feasible else "✗"
        why = "" if o.feasible else f"  ← {o.violations[0].code} {o.violations[0].message}"
        print(f"   {flag} {o.mode.value:<11} ETA {o.eta_min:>4}′  fee {o.fee:>8,}  risk {o.risk:5.1%}  score {o.score if o.feasible else '-':>6}{why}")
    print(f"   ⇒ {d.reason}  (conf {d.confidence}, human={d.needs_human})")
    out["dispatch"].append(dict(title=title, pref=pref, weight=req.weight, coldest=req.coldest.value,
                                rain=w.rain_mmh, wind=w.wind_ms, chosen=d.chosen.mode.value if d.chosen else None,
                                confidence=d.confidence, needs_human=d.needs_human, reason=d.reason,
                                options=[dict(mode=o.mode.value, name=o.name_vi, feasible=o.feasible, eta=o.eta_min,
                                              fee=o.fee, risk=round(o.risk, 3), co2=o.co2_g, score=o.score if o.feasible else None,
                                              dist=o.distance_km, viol=[v.code + " " + v.message for v in o.violations])
                                         for o in d.options]))
print("\n=== Search Order (A06) ===")
cart_cust = c.customer_dao.get_cust(1)
c.cart_service.add_to_cart(cart_cust, 8, 1)
placed = c.order_service.checkout(cart_cust, 1, "CASH", DeliveryPreference.CHEAP, Weather())
ORDER_Q = [("TEXT", f"đơn hàng số {placed.order_id}"), ("VOICE", "đơn hàng gần nhất của mình đâu rồi")]
ok_o = 0
for mode, text in ORDER_Q:
    q = c.query_service.voice_query(c.speech_service.transcribe(text)) if mode == "VOICE" else c.query_service.text_query(text)
    found = c.search_service.find_orders(q, 1)
    hit = bool(found) and found[0].order_id == placed.order_id
    ok_o += hit
    print(f"[{mode}] {text!r} → intent={q.intent} order_id={q.order_id} → "
          + (f"Đơn #{found[0].order_id} · {found[0].status.value} · {found[0].total():,}đ" if found else "không thấy"))
    out["search"].append(dict(mode=mode, query=text, intent="ORDER", expect=placed.order_id, hit=hit,
                              top=[dict(order_id=o.order_id, status=o.status.value, total=o.total()) for o in found]))
out["order_success"] = [ok_o, len(ORDER_Q)]
tot = ok + ok_o, len(SEARCHES) + len(ORDER_Q)
print(f"Overall search success = {tot[0]}/{tot[1]} = {tot[0]/tot[1]:.0%}")
(ROOT / "docs").mkdir(exist_ok=True)
json.dump(out, open(ROOT / "docs" / "demo_results.json", "w"), ensure_ascii=False, indent=1)

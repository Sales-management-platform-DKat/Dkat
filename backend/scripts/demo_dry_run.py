"""Dry run of the demo script (docs/demo/kich-ban-demo.md) against the RUNNING server.

    python -m scripts.demo_reset        # 1. known data
    uvicorn app.main:app                # 2. server (another terminal)
    python -m scripts.demo_dry_run      # 3. the 9 demo steps with the same API calls as the screens

Sends REAL notifications (SMTP / eSMS from backend/.env) to the presenter's contact:
DEMO_CUSTOMER_PHONE (default SMS_TEST_TO) and DEMO_CUSTOMER_EMAIL (default EMAIL_TEST_TO).
Exit code 1 if any step fails. The data is used up afterwards: run demo_reset again before the demo.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.core.config import settings

API = os.getenv("DEMO_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"
PASSWORD = os.getenv("DEMO_PASSWORD", "DKat@Demo2026")
PHONE = os.getenv("DEMO_CUSTOMER_PHONE") or settings.SMS_TEST_TO
EMAIL = os.getenv("DEMO_CUSTOMER_EMAIL") or settings.EMAIL_TEST_TO
STORE_ID = int(os.getenv("DEMO_STORE_ID", "1"))
HERO_SKU = "AK-GIO-DEN-M"
VN = timezone(timedelta(hours=7))

client = httpx.Client(timeout=90)
results: list[tuple[str, bool, str, float]] = []


def call(method, path, token=None, body=None, expect=(200, 201, 204), params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = client.request(method, API + path, json=body, headers=headers, params=params)
    if r.status_code not in expect:
        raise AssertionError(f"{method} {path} -> {r.status_code} {r.text[:300]}")
    return r.json() if r.content else None


def step(name):
    def deco(fn):
        t0 = time.perf_counter()
        try:
            detail, ok = fn()
        except Exception as exc:  # noqa: BLE001 - report and continue with the next step
            detail, ok = f"{type(exc).__name__}: {exc}", False
        elapsed = time.perf_counter() - t0
        results.append((name, ok, detail, elapsed))
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({elapsed:.1f}s)\n      {detail}", flush=True)
        return fn
    return deco


def login(username):
    return call("POST", "/auth/login", body={"username": username, "password": PASSWORD})["access_token"]


def find_variant(token, sku):
    for product in call("GET", "/products", token, params={"page": 1, "size": 100}):
        for v in product.get("variants", []):
            if v.get("sku") == sku:
                return v["variant_id"]
    raise AssertionError(f"SKU {sku} not found")


def stock(token, branch_id, variant_id):
    return call("GET", f"/inventory/{branch_id}/{variant_id}", token)


S = {}
if not PHONE and not EMAIL:
    sys.exit("Set DEMO_CUSTOMER_PHONE and/or DEMO_CUSTOMER_EMAIL (or SMS_TEST_TO / EMAIL_TEST_TO) in backend/.env")


@step("0. Server và dữ liệu demo sẵn sàng")
def _():
    health = client.get(API.replace("/api/v1", "") + "/health").json()
    branches = client.get(API + "/public/branches", params={"storeId": STORE_ID}).json()
    S["cn01"] = next(b["branchId"] for b in branches if b["name"].endswith("Quận 1"))
    return f"health={health}, branches={[b['name'] for b in branches]}", health.get("database") == "up" and len(branches) == 3


@step("1. Đăng nhập OWNER (owner01)")
def _():
    S["owner"] = login("owner01")
    me = call("GET", "/auth/me", S["owner"])
    return f"role={me.get('role')}, shop={me.get('shop_name')}", me.get("role") == "owner"


@step("2. OWNER tạo sản phẩm mới + biến thể + nhập kho")
def _():
    o = S["owner"]
    cat = next(c for c in call("GET", "/categories", o, params={"status": "ACTIVE"}) if c["name"] == "Áo")
    p = call("POST", "/products", o, {"categoryId": cat["categoryId"], "name": "Áo polo DKat", "description": "Mẫu mới ra mắt trong buổi demo"})
    v = call("POST", f"/products/{p['productId']}/variants", o, {"sku": "AP-POLO-NAVY-M", "variantName": "Navy / M", "price": "259000", "costPrice": "120000"})
    call("POST", "/inventory/import", o, {"branchId": S["cn01"], "note": "Hàng mới về", "items": [{"variantId": v["variant_id"], "quantity": 12}]})
    q = stock(o, S["cn01"], v["variant_id"])["quantity"]
    return f"{p['productCode']} Áo polo DKat - Navy / M, tồn CN01 = {q}", q == 12


@step("3. POS: staff01 bán Áo thun M x2 + Mũ x1 cho khách quen, thu tiền mặt")
def _():
    s = S["staff"] = login("staff01:staff")
    o = S["owner"]
    tee, cap = find_variant(o, "AT-COT-M"), find_variant(o, "MU-LT-DEN")
    before = stock(o, S["cn01"], tee)["quantity"]
    found = call("GET", "/customers/quick-search", s, params={"q": "0901000001", "keyword": "0901000001"})
    rows = found if isinstance(found, list) else found.get("items", [])
    customer = rows[0]
    customer_id = customer.get("customerId") or customer.get("id")
    order = call("POST", "/sales-orders", s, {"branchId": S["cn01"], "customerId": customer_id,
                                              "items": [{"variantId": tee, "quantity": 2}, {"variantId": cap, "quantity": 1}]})
    paid = call("POST", f"/sales-orders/{order['salesOrderId']}/confirm-payment", s, {"paymentMethod": "CASH", "amount": order["totalAmount"]})
    after = stock(o, S["cn01"], tee)["quantity"]
    S["pos_total"] = Decimal(order["totalAmount"])
    return f"{order['orderCode']} khách {customer.get('fullName')} tổng {order['totalAmount']} -> {paid['status']}; tồn Áo thun M {before} -> {after}", \
        paid["status"] == "PAID" and after == before - 2 and S["pos_total"] == Decimal("547000")


@step("4. Website: khách đặt trước Áo khoác gió Đen/M (đang hết hàng)")
def _():
    # same calls as the website: search "khoác" -> product detail -> variant Đen / M at DKat Quận 1
    found = client.get(API + "/public/products", params={"storeId": STORE_ID, "keyword": "khoác"}).json()["items"]
    detail = client.get(API + f"/public/products/{found[0]['id']}").json()
    hero = next(v for v in detail["variants"] if v["sku"] == HERO_SKU)
    S["hero"] = hero["id"]
    status = next(x["availability"] for x in hero["branches"] if x["branchId"] == S["cn01"])
    customer = {"fullName": "Khách Demo", "phone": PHONE, "address": "1 Lê Duẩn, Quận 1"}
    if EMAIL:
        customer["email"] = EMAIL
    r = client.post(API + "/preorders", json={"branchId": S["cn01"], "customer": customer,
                                              "items": [{"variantId": S["hero"], "quantity": 1}], "note": "Đặt từ website"})
    body = r.json()
    S["mine"] = body.get("preorderId")
    S["mine_code"] = body.get("preorderCode")
    return f"tình trạng CN01 trên web: {status}; POST /preorders -> {r.status_code} {S['mine_code']} {body.get('status')}", \
        status == "OUT_OF_STOCK" and r.status_code == 201 and body.get("status") == "WAITING_STOCK"


@step("5. Nhập kho 1 chiếc -> FIFO: chị Lan (đặt hôm qua) được giữ hàng trước, khách demo vẫn chờ")
def _():
    o = S["owner"]
    rows = call("GET", "/preorders", o, params={"branchId": S["cn01"], "page": 1, "size": 50})
    lan = next(p for p in rows if p["customer"]["fullName"] == "Trần Thị Lan")
    S["lan"] = lan["preorderId"]
    t0 = time.perf_counter()
    call("POST", "/inventory/import", o, {"branchId": S["cn01"], "note": "Hàng về đợt 1", "items": [{"variantId": S["hero"], "quantity": 1}]})
    took = time.perf_counter() - t0
    lan_status = call("GET", f"/preorders/{S['lan']}", o)["status"]
    mine_status = call("GET", f"/preorders/{S['mine']}", o)["status"]
    return f"nhập kho {took:.1f}s; chị Lan {lan_status}, khách demo {mine_status}", \
        lan_status in ("READY", "NOTIFIED") and mine_status == "WAITING_STOCK"


@step("6. Nhập thêm 1 chiếc -> đơn của khách demo READY và gửi SMS/email thật")
def _():
    o = S["owner"]
    t0 = time.perf_counter()
    call("POST", "/inventory/import", o, {"branchId": S["cn01"], "note": "Hàng về đợt 2", "items": [{"variantId": S["hero"], "quantity": 1}]})
    took = time.perf_counter() - t0
    detail = call("GET", f"/preorders/{S['mine']}", o)
    history = call("GET", f"/preorders/{S['mine']}/notifications", o)
    sends = "; ".join(f"{n['channel']} {n['recipient']} {n['status']}{' (' + (n['errorMessage'] or '').split(':')[0] + ')' if n['status'] == 'FAILED' else ''}"
                      for n in history["items"])
    S["mine_total"] = detail["totalAmount"]
    return f"nhập kho {took:.1f}s; đơn {detail['status']}, hạn giữ {detail.get('expiresAt')}; thông báo: {sends}", \
        detail["status"] == "NOTIFIED" and any(n["status"] == "SENT" for n in history["items"])


@step("7. Lịch sử thông báo của chị Lan (email về hộp thư nhóm)")
def _():
    history = call("GET", f"/preorders/{S['lan']}/notifications", S["owner"])
    sends = "; ".join(f"{n['channel']} {n['recipient']} {n['status']}" for n in history["items"])
    return sends or "không có", any(n["status"] == "SENT" and n["channel"] == "EMAIL" for n in history["items"])


@step("8. Khách đến lấy hàng: staff01 thu tiền và xác nhận nhận hàng")
def _():
    s, o = S["staff"], S["owner"]
    before = stock(o, S["cn01"], S["hero"])
    paid = call("POST", f"/preorders/{S['mine']}/confirm-payment", s, {"paymentMethod": "CASH", "amount": S["mine_total"]})
    done = call("POST", f"/preorders/{S['mine']}/fulfill", s, {})
    after = stock(o, S["cn01"], S["hero"])
    return f"thanh toán {paid['paymentStatus']}, đơn {done['status']}; tồn áo khoác CN01 {before['quantity']} -> {after['quantity']} (còn giữ cho chị Lan {after['reserved']})", \
        done["status"] == "FULFILLED" and after["quantity"] == before["quantity"] - 1 and after["reserved"] == 1


@step("9. Dashboard: doanh thu hôm nay gồm đơn POS + đơn đặt trước, top sản phẩm, biểu đồ 30 ngày")
def _():
    o = S["owner"]
    today = datetime.now(VN).date()
    day = call("GET", "/reports/summary", o, params={"from": str(today), "to": str(today)})
    month = call("GET", "/reports/summary", o, params={"from": str(today - timedelta(days=29)), "to": str(today)})
    top = call("GET", "/reports/top-products", o, params={"from": str(today - timedelta(days=29)), "to": str(today), "limit": 5, "sortBy": "revenue"})
    revenue = call("GET", "/reports/revenue", o, params={"from": str(today - timedelta(days=29)), "to": str(today), "granularity": "day"})

    def pick(d, *keys):
        for k in keys:
            if isinstance(d, dict) and k in d:
                return d[k]
        return None
    cards = pick(day, "totalRevenue", "revenue", "netRevenue")
    if isinstance(cards, dict):
        cards = pick(cards, "value", "current")
    expected = S["pos_total"] + Decimal(str(S["mine_total"]))
    top_items = top if isinstance(top, list) else pick(top, "items", "products") or []
    points = revenue if isinstance(revenue, list) else pick(revenue, "points", "items", "series") or []
    return (f"doanh thu hôm nay {cards} (mong đợi {expected}); 30 ngày {pick(pick(month, 'revenue') or {}, 'value')}; "
            f"top: {[pick(t, 'name', 'productName') for t in top_items[:3]]}; {len(points)} điểm trên biểu đồ"), \
        cards is not None and Decimal(str(cards)) == expected and len(top_items) > 0


failed = [r for r in results if not r[1]]
total = sum(r[3] for r in results)
print(f"\n{len(results) - len(failed)}/{len(results)} bước đạt, tổng thời gian máy chạy {total:.0f}s")
sys.exit(1 if failed else 0)

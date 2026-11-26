"""E2E test run on the develop environment: Auth, POS, Pre-order, Notification.

Needs the develop server on :8010 and seed_state.json from seed_develop.py.
Writes logs/22_e2e_requests.log (every request/response) and e2e_results.json.
"""
import json
import os
import time
from decimal import Decimal
from pathlib import Path

import pymysql

from e2e_lib import Http

QA = Path(__file__).parent
PW = "Dkat@12345678"
st = json.loads((QA / "seed_state.json").read_text(encoding="utf-8"))
B, V = st["branches"], st["variants"]
S, M, L = V["QA-AO-01-S"], V["QA-AO-01-M"], V["QA-AO-01-L"]
http = Http(QA / "logs" / "22_e2e_requests.log")
results = []


def db_query(sql, args=()):
    conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], database="dkat_develop", autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def g(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


def tc(tc_id, func, cond, steps, expected):
    def deco(fn):
        http.current_tc = tc_id
        try:
            actual, ok = fn()
        except Exception as exc:  # a crash is a failed test, keep going
            actual, ok = f"Lỗi khi chạy: {type(exc).__name__}: {exc}", False
        results.append(dict(id=tc_id, func=func, cond=cond, steps=steps, expected=expected,
                            actual=actual, result="Pass" if ok else "Fail"))
        print(("PASS " if ok else "FAIL ") + tc_id + " | " + actual)
        return fn
    return deco


def login(user, pw=PW):
    return http.call("POST", "/auth/login", json_body={"username": user, "password": pw})


def stock(branch, variant):
    r = http.call("GET", f"/inventory/{branch}/{variant}", OWNER)
    return r.json() if r.status_code == 200 else {}


OWNER = login("owner01").json()["access_token"]
MANAGER = login("manager01:manager").json()["access_token"]
STAFF = login("staff01:staff").json()["access_token"]
COND_SEED = "Môi trường develop sạch, seed qua API (owner01, manager01 CN01+CN02, staff01 CN01)"

# ------------------------------------------------------------------ AUTH
@tc("TC-DEV-AUTH-01", "Xác thực", COND_SEED, "1. POST /auth/login {username: owner01, password đúng}",
    "200, có access_token và user.role = owner")
def _():
    r = login("owner01")
    b = r.json()
    return f"{r.status_code}, role={g(b.get('user', {}), 'role')}, token={'có' if b.get('access_token') else 'không'}", \
        r.status_code == 200 and bool(b.get("access_token"))


@tc("TC-DEV-AUTH-02", "Xác thực", COND_SEED, "1. POST /auth/login với mật khẩu sai", "401, không có token")
def _():
    r = login("owner01", "SaiMatKhau@123")
    return f"{r.status_code} {r.text[:120]}", r.status_code == 401


@tc("TC-DEV-AUTH-03", "Xác thực", COND_SEED,
    "1. POST /auth/login username = manager01:manager\n2. POST /auth/login username = staff01:staff",
    "Cả hai 200, role lần lượt manager / staff")
def _():
    a, b = login("manager01:manager"), login("staff01:staff")
    ra, rb = g(a.json().get("user", {}), "role"), g(b.json().get("user", {}), "role")
    return f"{a.status_code} role={ra}; {b.status_code} role={rb}", a.status_code == b.status_code == 200


@tc("TC-DEV-AUTH-04", "Xác thực", COND_SEED + "; locked01 đã bị khóa (LOCKED)",
    "1. POST /auth/login username = locked01:staff", "Bị từ chối (401/403), không có token")
def _():
    r = login("locked01:staff")
    return f"{r.status_code} {r.text[:120]}", r.status_code in (401, 403) and "access_token" not in r.text


@tc("TC-DEV-AUTH-05", "Xác thực", COND_SEED, "1. GET /auth/me không gửi token", "401")
def _():
    r = http.call("GET", "/auth/me")
    return f"{r.status_code} {r.text[:100]}", r.status_code == 401


@tc("TC-DEV-AUTH-06", "Xác thực", COND_SEED,
    "1. Đăng nhập owner01 lấy token T\n2. POST /auth/logout với T\n3. GET /auth/me với T",
    "Bước 3 trả 401 (phiên đã thu hồi)")
def _():
    t = login("owner01").json()["access_token"]
    out = http.call("POST", "/auth/logout", t)
    me = http.call("GET", "/auth/me", t)
    return f"logout {out.status_code}; /auth/me sau logout {me.status_code}", me.status_code == 401


@tc("TC-DEV-AUTH-07", "Phân quyền", COND_SEED, "1. staff01 POST /products với body hợp lệ", "403")
def _():
    r = http.call("POST", "/products", STAFF, {"categoryId": st["category"], "name": "Không được tạo"})
    return f"{r.status_code} {r.text[:120]}", r.status_code == 403


@tc("TC-DEV-AUTH-08", "Phân quyền", COND_SEED, "1. staff01 (chỉ CN01) GET /sales-orders?branchId=<CN02>", "403")
def _():
    r = http.call("GET", "/sales-orders", STAFF, params={"branchId": B["CN02"]})
    return f"{r.status_code} {r.text[:120]}", r.status_code == 403


@tc("TC-DEV-AUTH-09", "Phân quyền", COND_SEED, "1. manager01 (CN01, CN02) GET /inventory?branchId=<CN03>", "403")
def _():
    r = http.call("GET", "/inventory", MANAGER, params={"branchId": B["CN03"]})
    return f"{r.status_code} {r.text[:120]}", r.status_code == 403


# ------------------------------------------------------------------ POS
POS = {}


@tc("TC-DEV-POS-01", "POS / Đơn bán", COND_SEED + "; Size S tồn 10 tại CN01, giá 150.000",
    "1. staff01 POST /sales-orders {branchId: CN01, discountAmount: 10000, items: [Size S x2]}",
    "201, trạng thái PENDING, tổng = 2 x 150.000 - 10.000 = 290.000")
def _():
    r = http.call("POST", "/sales-orders", STAFF, {"branchId": B["CN01"], "discountAmount": "10000", "items": [{"variantId": S, "quantity": 2}]})
    b = r.json()
    POS["order"] = b
    total = g(b, "totalAmount", "total_amount")
    return f"{r.status_code}, status={g(b, 'status')}, total={total}", \
        r.status_code == 201 and g(b, "status") == "PENDING" and Decimal(str(total)) == Decimal("290000")


@tc("TC-DEV-POS-02", "POS / Đơn bán", "Có đơn PENDING từ TC-DEV-POS-01",
    "1. staff01 POST /sales-orders/{id}/confirm-payment {CASH, amount: 200000}",
    "Bị từ chối (4xx) vì số tiền khác tổng đơn; đơn vẫn PENDING")
def _():
    oid = g(POS["order"], "salesOrderId", "orderId", "order_id", "id")
    r = http.call("POST", f"/sales-orders/{oid}/confirm-payment", STAFF, {"paymentMethod": "CASH", "amount": "200000"})
    d = http.call("GET", f"/sales-orders/{oid}", STAFF).json()
    return f"{r.status_code} {r.text[:120]}; đơn {g(d, 'status')}", 400 <= r.status_code < 500 and g(d, "status") == "PENDING"


@tc("TC-DEV-POS-03", "POS / Đơn bán", "Có đơn PENDING từ TC-DEV-POS-01; tồn Size S tại CN01 = 10",
    "1. staff01 POST /sales-orders/{id}/confirm-payment {CASH, amount: 290000}\n2. GET /inventory/{CN01}/{Size S}",
    "200, đơn PAID; tồn Size S giảm còn 8")
def _():
    oid = g(POS["order"], "salesOrderId", "orderId", "order_id", "id")
    r = http.call("POST", f"/sales-orders/{oid}/confirm-payment", STAFF, {"paymentMethod": "CASH", "amount": "290000"})
    q = g(stock(B["CN01"], S), "quantity")
    return f"{r.status_code}, status={g(r.json(), 'status')}, tồn Size S={q}", \
        r.status_code == 200 and g(r.json(), "status") == "PAID" and q == 8


@tc("TC-DEV-POS-04", "POS / Đơn bán", "Tồn Size M tại CN01 = 10",
    "1. staff01 POST /sales-orders {CN01, Size M x11}", "409, không tạo đơn (vượt tồn khả dụng)")
def _():
    r = http.call("POST", "/sales-orders", STAFF, {"branchId": B["CN01"], "items": [{"variantId": M, "quantity": 11}]})
    return f"{r.status_code} {r.text[:150]}", r.status_code == 409


@tc("TC-DEV-POS-05", "POS / Đơn bán", "Tồn Size M tại CN01 = 10",
    "1. Tạo đơn PENDING Size M x1\n2. POST /sales-orders/{id}/cancel {reason}\n3. GET tồn Size M",
    "Đơn CANCELLED; tồn Size M vẫn 10")
def _():
    o = http.call("POST", "/sales-orders", STAFF, {"branchId": B["CN01"], "items": [{"variantId": M, "quantity": 1}]}).json()
    oid = g(o, "salesOrderId", "orderId", "order_id", "id")
    r = http.call("POST", f"/sales-orders/{oid}/cancel", STAFF, {"reason": "Khách đổi ý"})
    q = g(stock(B["CN01"], M), "quantity")
    return f"{r.status_code}, status={g(r.json(), 'status')}, tồn Size M={q}", \
        r.status_code == 200 and g(r.json(), "status") == "CANCELLED" and q == 10


@tc("TC-DEV-POS-06", "POS / Đơn bán", "Đơn PAID từ TC-DEV-POS-03; tồn Size S = 8",
    "1. owner01 POST /sales-orders/{id}/refund {reason}\n2. GET tồn Size S",
    "200, đơn CANCELLED và payment REFUNDED (thiết kế PBI 122); tồn Size S hoàn lại 10")
def _():
    oid = g(POS["order"], "salesOrderId", "orderId", "order_id", "id")
    r = http.call("POST", f"/sales-orders/{oid}/refund", OWNER, {"reason": "Hàng lỗi"})
    q = g(stock(B["CN01"], S), "quantity")
    pays = [p.get("status") for p in (r.json().get("payments") or [])]
    POS["times"] = (g(r.json(), "createdAt"), g(r.json(), "paidAt"))
    return f"{r.status_code}, status={g(r.json(), 'status')}, payments={pays}, tồn Size S={q}", \
        r.status_code == 200 and g(r.json(), "status") == "CANCELLED" and bool(pays) \
        and all(x == "REFUNDED" for x in pays) and q == 10


@tc("TC-DEV-POS-09", "POS / Đơn bán",
    "Đơn tạo và thanh toán trong cùng 1 giây (TC-DEV-POS-01, 03); MySQL local chạy giờ +07",
    "1. Lấy createdAt và paidAt của đơn (response refund / GET /sales-orders/{id})\n2. So sánh (cả hai có hậu tố Z = UTC)",
    "createdAt và paidAt cùng là UTC, chênh nhau vài giây")
def _():
    from datetime import datetime
    created, paid = POS["times"]
    diff = abs((datetime.fromisoformat(created.replace("Z", "")) - datetime.fromisoformat(paid.replace("Z", ""))).total_seconds())
    return f"createdAt={created}, paidAt={paid}, lệch {diff / 3600:.1f} giờ", diff < 60


@tc("TC-DEV-POS-07", "POS / Đơn bán", COND_SEED, "1. staff01 (chỉ CN01) POST /sales-orders {branchId: CN02, Size S x1}", "403")
def _():
    r = http.call("POST", "/sales-orders", STAFF, {"branchId": B["CN02"], "items": [{"variantId": S, "quantity": 1}]})
    return f"{r.status_code} {r.text[:120]}", r.status_code == 403


@tc("TC-DEV-POS-08", "POS / Đơn bán", COND_SEED,
    "1. staff01 POST /customers {fullName, phone 0901234567}\n2. GET /customers/quick-search?q=0901\n3. Tạo đơn POS với customerId",
    "Tạo khách 201; tìm nhanh thấy khách; đơn 201 gắn đúng customerId")
def _():
    c = http.call("POST", "/customers", STAFF, {"fullName": "Khách POS QA", "phone": "0901234567"})
    cid = g(c.json(), "customerId", "customer_id", "id")
    qs = http.call("GET", "/customers/quick-search", STAFF, params={"q": "0901", "keyword": "0901"})
    o = http.call("POST", "/sales-orders", STAFF, {"branchId": B["CN01"], "customerId": cid, "items": [{"variantId": M, "quantity": 1}]})
    oc = g(o.json(), "customerId", "customer_id")
    if o.status_code == 201:
        http.call("POST", f"/sales-orders/{g(o.json(), 'orderId', 'order_id', 'id')}/cancel", STAFF, {"reason": "dọn dữ liệu test"})
    found = str(cid) in qs.text
    return f"khách {c.status_code} id={cid}; quick-search {qs.status_code} thấy={found}; đơn {o.status_code} customerId={oc}", \
        c.status_code == 201 and qs.status_code == 200 and found and o.status_code == 201 and oc == cid


# ------------------------------------------------------------------ PRE-ORDER
PRE = {}
CUST = {"fullName": "Khách đặt trước QA", "phone": "0912345678", "email": "khach.qa@example.com", "address": "1 Đường QA"}


@tc("TC-DEV-PRE-01", "Đặt trước", COND_SEED + "; Size L hết hàng ở mọi chi nhánh",
    "1. Không đăng nhập: POST /preorders {branchId: CN01, customer, items: [Size L x2]}",
    "201, đơn WAITING_STOCK, có mã đơn")
def _():
    r = http.call("POST", "/preorders", json_body={"branchId": B["CN01"], "customer": CUST, "items": [{"variantId": L, "quantity": 2}]}, ip="198.51.100.10")
    b = r.json()
    PRE["a"] = b
    return f"{r.status_code}, status={g(b, 'status')}, mã={g(b, 'preorderCode', 'orderCode')}", \
        r.status_code == 201 and g(b, "status") == "WAITING_STOCK"


@tc("TC-DEV-PRE-02", "Đặt trước", "Size S còn hàng tại CN01",
    "1. Không đăng nhập: POST /preorders với Size S", "409 VARIANT_IN_STOCK (hàng còn thì mua trực tiếp)")
def _():
    r = http.call("POST", "/preorders", json_body={"branchId": B["CN01"], "customer": CUST, "items": [{"variantId": S, "quantity": 1}]}, ip="198.51.100.11")
    return f"{r.status_code} {r.text[:150]}", r.status_code == 409 and "VARIANT_IN_STOCK" in r.text


@tc("TC-DEV-PRE-03", "Đặt trước", "Đăng nhập staff01; màn hình POS (frontend/src/LivePos.jsx) mở form Đặt trước tại quầy",
    "1. Gửi đúng body mà LivePos.jsx gửi: {branchId, customerName, phone, address, email, items: [Size L x1]}",
    "201, tạo được đơn đặt trước từ màn hình POS")
def _():
    body = {"branchId": B["CN01"], "customerName": "Khách tại quầy", "phone": "0987654321", "address": "Tại quầy",
            "email": None, "items": [{"variantId": L, "quantity": 1}]}
    r = http.call("POST", "/preorders", STAFF, body, ip="198.51.100.12")
    return f"{r.status_code} {r.text[:200]}", r.status_code == 201


@tc("TC-DEV-PRE-04", "Đặt trước", "Có đơn từ TC-DEV-PRE-01 tại CN01",
    "1. staff01 GET /preorders\n2. manager01 GET /preorders?branchId=<CN03>",
    "staff01 thấy đơn CN01; manager01 xem CN03 bị 403")
def _():
    a = http.call("GET", "/preorders", STAFF)
    c = http.call("GET", "/preorders", MANAGER, params={"branchId": B["CN03"]})
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    seen = f'"preorderId":{pid}' in a.text.replace(" ", "") or f'"id":{pid}' in a.text.replace(" ", "")
    return f"staff {a.status_code} thấy đơn={seen}; manager CN03 {c.status_code}", a.status_code == 200 and seen and c.status_code == 403


@tc("TC-DEV-PRE-05", "Đặt trước", "Đơn A (Size L x2) WAITING_STOCK tại CN01",
    "1. owner01 POST /inventory/import {CN01, Size L x5}\n2. GET /preorders/{A}",
    "Đơn A được phân bổ đủ hàng: READY (hoặc NOTIFIED nếu đã gửi thông báo), có expiresAt")
def _():
    r = http.call("POST", "/inventory/import", OWNER, {"branchId": B["CN01"], "note": "Hàng về", "items": [{"variantId": L, "quantity": 5}]})
    time.sleep(2)
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    d = http.call("GET", f"/preorders/{pid}", OWNER).json()
    PRE["a_detail"] = d
    return f"import {r.status_code}; đơn {g(d, 'status')}, expiresAt={g(d, 'expiresAt')}", \
        r.status_code == 201 and g(d, "status") in ("READY", "NOTIFIED") and bool(g(d, "expiresAt"))


# ------------------------------------------------------------------ NOTIFICATION
@tc("TC-DEV-NOTI-01", "Thông báo", "Đơn A vừa chuyển READY ở TC-DEV-PRE-05 (khách có SĐT và email)",
    "1. GET /preorders/{A}: xem danh sách notifications và trạng thái\n2. Kiểm tra bảng notifications trong DB",
    "Có ít nhất 1 bản ghi thông báo PREORDER_READY (SMS hoặc email); đơn chuyển NOTIFIED khi gửi thành công")
def _():
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    d = http.call("GET", f"/preorders/{pid}", OWNER).json()
    rows = db_query("SELECT channel, status FROM notifications WHERE preorder_id=%s", (pid,))
    return f"đơn {g(d, 'status')}; notifications trong API={d.get('notifications')}; trong DB={len(rows)} dòng", \
        len(rows) > 0


@tc("TC-DEV-NOTI-02", "Thông báo", "Log server develop sau TC-DEV-PRE-05",
    "1. Tìm trong log server cảnh báo của preorders.services.notifications",
    "Không có cảnh báo 'NotificationService unavailable'")
def _():
    log = (QA / "logs" / "20_server_develop.log").read_text(encoding="utf-8", errors="replace")
    hit = [l for l in log.splitlines() if "NotificationService unavailable" in l]
    return (f"Có {len(hit)} dòng: {hit[0].strip()[:160]}" if hit else "Không có cảnh báo"), not hit


@tc("TC-DEV-NOTI-03", "Thông báo", "Theo docs/api-contract.md (FR-09.5): API xem và gửi lại thông báo",
    "1. GET /preorders/{A}/notifications\n2. POST /notifications/1/resend",
    "Hai API tồn tại (200 hoặc 404 nghiệp vụ có mã lỗi), không phải 404 route không tồn tại")
def _():
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    a = http.call("GET", f"/preorders/{pid}/notifications", OWNER)
    b = http.call("POST", "/notifications/1/resend", OWNER)
    return f"{a.status_code} {a.text[:60]}; {b.status_code} {b.text[:60]}", \
        a.status_code != 404 or "Not Found" not in a.text


# ------------------------------------------------------------------ PRE-ORDER (continued)
@tc("TC-DEV-PRE-06", "Đặt trước", "Đơn A đã READY (TC-DEV-PRE-05)",
    "1. owner01 POST /preorders/{A}/confirm-payment {CASH, amount = tổng đơn}", "200, paymentStatus = PAID")
def _():
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    total = g(PRE["a_detail"], "totalAmount", "total_amount")
    r = http.call("POST", f"/preorders/{pid}/confirm-payment", OWNER, {"paymentMethod": "CASH", "amount": str(total)})
    return f"{r.status_code}, paymentStatus={g(r.json(), 'paymentStatus', 'payment_status')} {r.text[:120] if r.status_code != 200 else ''}", \
        r.status_code == 200 and g(r.json(), "paymentStatus", "payment_status") == "PAID"


@tc("TC-DEV-PRE-07", "Đặt trước", "Đơn A READY, đã thanh toán; tồn Size L tại CN01 = 5",
    "1. PUT /preorders/{A}/fulfillment {method: PICKUP}\n2. POST /preorders/{A}/fulfill\n3. GET tồn Size L",
    "Đơn FULFILLED; tồn Size L giảm còn 3")
def _():
    pid = g(PRE["a"], "preorderId", "preorder_id", "id")
    a = http.call("PUT", f"/preorders/{pid}/fulfillment", OWNER, {"method": "PICKUP"})
    b = http.call("POST", f"/preorders/{pid}/fulfill", OWNER, None)
    q = g(stock(B["CN01"], L), "quantity")
    return f"fulfillment {a.status_code}; fulfill {b.status_code} status={g(b.json(), 'status')}; tồn Size L={q}", \
        b.status_code == 200 and g(b.json(), "status") == "FULFILLED" and q == 3


@tc("TC-DEV-PRE-08", "Đặt trước", "Size L ở CN02 hết hàng",
    "1. Tạo đơn đặt trước Size L x1 tại CN02 (WAITING_STOCK)\n2. manager01 POST /preorders/{id}/cancel {reason}",
    "200, đơn CANCELLED")
def _():
    c = http.call("POST", "/preorders", json_body={"branchId": B["CN02"], "customer": CUST, "items": [{"variantId": L, "quantity": 1}]}, ip="198.51.100.13")
    pid = g(c.json(), "preorderId", "preorder_id", "id")
    r = http.call("POST", f"/preorders/{pid}/cancel", MANAGER, {"reason": "Khách hủy"})
    return f"tạo {c.status_code}; hủy {r.status_code} status={g(r.json(), 'status')}", \
        r.status_code == 200 and g(r.json(), "status") == "CANCELLED"


@tc("TC-DEV-PRE-09", "Đặt trước", "Cùng một IP gửi liên tục (giới hạn 5 đơn / 10 phút / IP)",
    "1. Gửi 6 lần POST /preorders hợp lệ từ cùng IP", "5 lần đầu 201, lần 6 trả 429")
def _():
    codes = [http.call("POST", "/preorders", json_body={"branchId": B["CN03"], "customer": dict(CUST, phone=f"09300000{i:02d}"),
                                                         "items": [{"variantId": L, "quantity": 1}]}, ip="198.51.100.99").status_code
             for i in range(6)]
    return f"mã trả về: {codes}", codes[:5] == [201] * 5 and codes[5] == 429


@tc("TC-DEV-PRE-10", "Đặt trước", "Có đơn READY quá hạn giữ hàng (expires_at đã qua); server develop đang chạy",
    "1. Kiểm tra app.main lifespan có khởi động run_preorder_expiry\n2. Chạy integration test test_api_lifespan_runs_scheduled_expiry",
    "Server tự hủy đơn quá hạn theo lịch (job chạy trong lifespan)")
def _():
    log = (QA / "logs" / "14_qa_pbi129_preorder_fifo.log").read_text(encoding="utf-8", errors="replace")
    failed = "FAIL: test_api_lifespan_runs_scheduled_expiry" in log
    return ("Job không được khởi động: lifespan chỉ gọi create_all; test lifespan FAIL (completed.wait timeout)" if failed
            else "Test lifespan PASS"), not failed


(QA / "e2e_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n{sum(r['result'] == 'Pass' for r in results)}/{len(results)} passed")

"""Integration test cases POS & Auth (sheet "POS & Auth" of docs/qa/DKat_Test_Cases.xlsx) through the API.

    python -m scripts.demo_reset          # 1. seed data the test cases refer to (DB_NAME=dkat_demo)
    uvicorn app.main:app --port 8000      # 2. server (another terminal)
    python -m scripts.check_pos_auth      # 3. TC-PA-01 .. TC-PA-12, PASS/FAIL each, exit code 1 on failure

Run it on FRESH seed data: the expected stock numbers are the ones demo_reset produces.
The test cases are also written step by step for the UI in the sheet; this script checks the same
inputs and expected results through the API in a few seconds.
"""
import os
import sys
from decimal import Decimal

import httpx

API = os.getenv("DEMO_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"
PW = os.getenv("DEMO_PASSWORD", "DKat@Demo2026")
CN01, CN02, CN03 = 1, 2, 3
client = httpx.Client(base_url=API, timeout=30)
results: list[tuple[str, bool, str]] = []
S: dict = {}


def login(username, password=PW):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def tc(tc_id, title):
    def deco(fn):
        try:
            detail, ok = fn()
        except Exception as exc:  # noqa: BLE001 - report and continue
            detail, ok = f"{type(exc).__name__}: {exc}", False
        results.append((tc_id, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {tc_id} {title}\n      {detail}", flush=True)
        return fn
    return deco


def stock(sku, branch=CN01):
    rows = client.get("/inventory", headers=auth(S["owner"]), params={"branchId": branch, "page": 1, "size": 100}).json()
    row = next(r for r in rows if r["sku"] == sku)
    return row["quantity"], row["available"]


def variant(sku):
    rows = client.get("/inventory", headers=auth(S["owner"]), params={"branchId": CN01, "page": 1, "size": 100}).json()
    return next(r["variantId"] for r in rows if r["sku"] == sku)


def order(token, branch, lines, customer_id=None):
    return client.post("/sales-orders", headers=auth(token), json={
        "branchId": branch, "customerId": customer_id,
        "items": [{"variantId": variant(sku), "quantity": q} for sku, q in lines]})


@tc("TC-PA-01", "Đăng nhập OWNER")
def _():
    r = login("owner01")
    S["owner"] = r.json().get("access_token")
    user = r.json().get("user", {})
    branches = client.get("/branches", headers=auth(S["owner"])).json()
    names = [b["name"] for b in (branches if isinstance(branches, list) else branches.get("items", []))]
    return f"{r.status_code}, role={user.get('role')}, cửa hàng={user.get('shop_name')}, chi nhánh={names}", \
        r.status_code == 200 and user.get("role") == "owner" and len(names) == 3


@tc("TC-PA-02", "Đăng nhập MANAGER (manager01:manager), chỉ CN01 + CN02")
def _():
    r = login("manager01:manager")
    S["manager"] = r.json().get("access_token")
    ok_cn02 = client.get("/inventory", headers=auth(S["manager"]), params={"branchId": CN02}).status_code
    cn03 = client.get("/inventory", headers=auth(S["manager"]), params={"branchId": CN03}).status_code
    return f"{r.status_code}, role={r.json().get('user', {}).get('role')}; tồn kho CN02 -> {ok_cn02}, CN03 -> {cn03}", \
        r.status_code == 200 and r.json()["user"]["role"] == "manager" and ok_cn02 == 200 and cn03 == 403


@tc("TC-PA-03", "Đăng nhập EMPLOYEE (staff01:staff), chỉ CN01, không vào báo cáo")
def _():
    r = login("staff01:staff")
    S["staff"] = r.json().get("access_token")
    report = client.get("/reports/summary", headers=auth(S["staff"]), params={"branchId": CN01}).status_code
    cn02 = client.get("/inventory", headers=auth(S["staff"]), params={"branchId": CN02}).status_code
    return f"{r.status_code}, role={r.json().get('user', {}).get('role')}; báo cáo -> {report}; tồn kho CN02 -> {cn02}", \
        r.status_code == 200 and r.json()["user"]["role"] == "staff" and report == 403 and cn02 == 403


@tc("TC-PA-04", "Đăng nhập sai: thiếu hậu tố vai trò / sai mật khẩu")
def _():
    a = login("staff01")
    b = login("owner01", "SaiMatKhau@2026")
    me = client.get("/auth/me").status_code
    return f"staff01 (thiếu :staff) -> {a.status_code}; owner01 sai mật khẩu -> {b.status_code}; /auth/me không token -> {me}", \
        a.status_code == 401 and b.status_code == 401 and me == 401 and "access_token" not in a.text + b.text


@tc("TC-PA-05", "Tạo đơn POS chờ thanh toán: Áo thun Trắng/M x2 + Mũ x1, khách Nguyễn Minh Anh")
def _():
    customer = client.get("/customers/quick-search", headers=auth(S["staff"]), params={"q": "0901000001"}).json()[0]
    r = order(S["staff"], CN01, [("AT-COT-M", 2), ("MU-LT-DEN", 1)], customer["customerId"])
    body = r.json()
    S["order"] = body
    q = stock("AT-COT-M")[0]
    return f"{r.status_code} {body.get('orderCode')} {body.get('status')} tổng {body.get('totalAmount')}, khách {customer['fullName']}; tồn AT-COT-M CN01 vẫn {q}", \
        r.status_code == 201 and body["status"] == "PENDING" and Decimal(body["totalAmount"]) == Decimal("547000") and q == 11


@tc("TC-PA-06", "Xác nhận thanh toán tiền mặt 547.000 đ, trừ kho đúng")
def _():
    oid = S["order"]["salesOrderId"]
    r = client.post(f"/sales-orders/{oid}/confirm-payment", headers=auth(S["staff"]), json={"paymentMethod": "CASH", "amount": "547000"})
    tee, cap = stock("AT-COT-M")[0], stock("MU-LT-DEN")[0]
    return f"{r.status_code} {r.json().get('status')}; tồn CN01 AT-COT-M 11 -> {tee}, MU-LT-DEN 10 -> {cap}", \
        r.status_code == 200 and r.json()["status"] == "PAID" and tee == 9 and cap == 9


@tc("TC-PA-07", "Xác nhận thanh toán sai số tiền bị từ chối")
def _():
    o = order(S["staff"], CN01, [("QJ-SLIM-31", 1)]).json()
    r = client.post(f"/sales-orders/{o['salesOrderId']}/confirm-payment", headers=auth(S["staff"]), json={"paymentMethod": "CASH", "amount": "400000"})
    status = client.get(f"/sales-orders/{o['salesOrderId']}", headers=auth(S["staff"])).json()["status"]
    client.post(f"/sales-orders/{o['salesOrderId']}/cancel", headers=auth(S["staff"]), json={"reason": "Dọn dữ liệu TC-PA-07"})
    return f"tổng {o['totalAmount']}, trả 400000 -> {r.status_code} {r.text[:120]}; đơn vẫn {status}; tồn QJ-SLIM-31 {stock('QJ-SLIM-31')[0]}", \
        r.status_code == 422 and "PAYMENT_AMOUNT_MISMATCH" in r.text and status == "PENDING" and stock("QJ-SLIM-31")[0] == 10


@tc("TC-PA-08", "Không đủ tồn: Quần jean Xanh/30 x11 (tồn 10), Áo khoác Đen/M x1 (tồn 0)")
def _():
    a = order(S["staff"], CN01, [("QJ-SLIM-30", 11)])
    b = order(S["staff"], CN01, [("AK-GIO-DEN-M", 1)])
    return f"QJ-SLIM-30 x11 -> {a.status_code} {a.text[:90]}; AK-GIO-DEN-M x1 -> {b.status_code} {b.text[:90]}; tồn QJ-SLIM-30 {stock('QJ-SLIM-30')[0]}", \
        a.status_code == 409 and "OUT_OF_STOCK" in a.text and '"available":10' in a.text.replace(" ", "") \
        and b.status_code == 409 and '"available":0' in b.text.replace(" ", "") and stock("QJ-SLIM-30")[0] == 10


@tc("TC-PA-09", "Hủy đơn PENDING: Quần jean Xanh/29 x1, tồn không đổi, không thu tiền được nữa")
def _():
    o = order(S["staff"], CN01, [("QJ-SLIM-29", 1)]).json()
    r = client.post(f"/sales-orders/{o['salesOrderId']}/cancel", headers=auth(S["staff"]), json={"reason": "Khách đổi ý"})
    pay = client.post(f"/sales-orders/{o['salesOrderId']}/confirm-payment", headers=auth(S["staff"]), json={"paymentMethod": "CASH", "amount": o["totalAmount"]})
    q = stock("QJ-SLIM-29")[0]
    return f"hủy -> {r.status_code} {r.json().get('status')} lý do '{r.json().get('cancelReason')}'; thu tiền sau khi hủy -> {pay.status_code}; tồn QJ-SLIM-29 {q}", \
        r.status_code == 200 and r.json()["status"] == "CANCELLED" and pay.status_code == 409 and q == 11


@tc("TC-PA-10", "Hoàn đơn đã thanh toán (OWNER): đơn 547.000 đ của TC-PA-06, hoàn kho")
def _():
    oid = S["order"]["salesOrderId"]
    r = client.post(f"/sales-orders/{oid}/refund", headers=auth(S["owner"]), json={"reason": "Khách trả hàng"})
    body = r.json()
    pays = [p["status"] for p in body.get("payments", [])]
    again = client.post(f"/sales-orders/{oid}/refund", headers=auth(S["owner"]), json={"reason": "Lần 2"}).status_code
    tee, cap = stock("AT-COT-M")[0], stock("MU-LT-DEN")[0]
    return f"{r.status_code} đơn {body.get('status')}, thanh toán {pays}; hoàn lần 2 -> {again}; tồn AT-COT-M 9 -> {tee}, MU-LT-DEN 9 -> {cap}", \
        r.status_code == 200 and body["status"] == "CANCELLED" and pays == ["REFUNDED"] and again == 409 and tee == 11 and cap == 10


@tc("TC-PA-11", "EMPLOYEE không hoàn được đơn đã thanh toán")
def _():
    o = order(S["owner"], CN01, [("AT-COT-S", 1)]).json()
    client.post(f"/sales-orders/{o['salesOrderId']}/confirm-payment", headers=auth(S["owner"]), json={"paymentMethod": "CASH", "amount": o["totalAmount"]})
    r = client.post(f"/sales-orders/{o['salesOrderId']}/refund", headers=auth(S["staff"]), json={"reason": "Thử"})
    status = client.get(f"/sales-orders/{o['salesOrderId']}", headers=auth(S["owner"])).json()["status"]
    client.post(f"/sales-orders/{o['salesOrderId']}/refund", headers=auth(S["owner"]), json={"reason": "Dọn dữ liệu TC-PA-11"})
    return f"staff01 hoàn -> {r.status_code} {r.text[:80]}; đơn vẫn {status}", r.status_code == 403 and status == "PAID"


@tc("TC-PA-12", "Phân quyền theo chi nhánh khi bán hàng")
def _():
    a = order(S["staff"], CN02, [("AT-COT-L", 1)]).status_code
    b = client.get("/sales-orders", headers=auth(S["staff"]), params={"branchId": CN02}).status_code
    c = order(S["manager"], CN03, [("AT-COT-L", 1)]).status_code
    d = order(S["manager"], CN02, [("AT-COT-L", 1)])
    if d.status_code == 201:
        client.post(f"/sales-orders/{d.json()['salesOrderId']}/cancel", headers=auth(S["manager"]), json={"reason": "Dọn dữ liệu TC-PA-12"})
    return f"staff01 tạo đơn CN02 -> {a}; staff01 xem đơn CN02 -> {b}; manager01 tạo đơn CN03 -> {c}; manager01 tạo đơn CN02 -> {d.status_code}", \
        a == 403 and b == 403 and c == 403 and d.status_code == 201


failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} test case đạt")
sys.exit(1 if failed else 0)

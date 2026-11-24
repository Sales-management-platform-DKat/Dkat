"""Integration test cases Pre-order & Notification (sheet "Đặt trước & Thông báo" of docs/qa/DKat_Test_Cases.xlsx).

    python -m scripts.demo_reset              # 1. seed data the test cases refer to (DB_NAME=dkat_demo)
    python -m scripts.check_preorder_notify   # 2. TC-PN-01 .. TC-PN-12 in order, PASS/FAIL each (no server needed)

Runs the app in-process and switches the notification configuration between steps, like the manual
test switches server profiles:
  profile A = ESMS_SANDBOX=true (eSMS checks the request, sends nothing), no SMTP
  profile B = wrong ESMS_API_KEY (SMS refused: AUTH_FAILED), SMTP from backend/.env
The retry job and the expiry job are called directly instead of waiting 5 minutes / 7 days.
Sends ONE real email: to EMAIL_TEST_TO (customer C, TC-PN-07) and one to the queue mailbox
(customer Lan, TC-PN-08). Phone numbers are fictional; no real SMS is sent (sandbox / refused key).
Exit code 1 if any test case fails. Data is used up afterwards: run demo_reset again.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import settings

HERO = "AK-GIO-DEN-M"   # Áo khoác gió DKat Đen / M, 599.000 đ, stock 0 everywhere after demo_reset
CN01 = 1
REAL = {k: getattr(settings, k) for k in ("ESMS_API_KEY", "ESMS_SANDBOX", "SMTP_HOST")}
results: list[tuple[str, bool, str]] = []
S: dict = {}


def profile(name: str) -> None:
    if name == "A":
        settings.ESMS_API_KEY, settings.ESMS_SANDBOX, settings.SMTP_HOST = REAL["ESMS_API_KEY"], True, ""
    else:
        settings.ESMS_API_KEY, settings.ESMS_SANDBOX, settings.SMTP_HOST = "SAI-KHOA-KIEM-THU", False, REAL["SMTP_HOST"]


def tc(tc_id, title):
    def deco(fn):
        try:
            detail, ok = fn()
        except Exception as exc:  # noqa: BLE001
            detail, ok = f"{type(exc).__name__}: {exc}", False
        results.append((tc_id, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {tc_id} {title}\n      {detail}", flush=True)
        return fn
    return deco


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not settings.EMAIL_TEST_TO or not REAL["SMTP_HOST"]:
        print("Cần SMTP_* và EMAIL_TEST_TO trong backend/.env (email thật cho TC-PN-07, 08)")
        return 1
    settings.NOTIFY_RETRY_ENABLED = False
    settings.NOTIFY_SMS_POLL_SECONDS = 1.0
    from fastapi.testclient import TestClient

    from app.db.session import engine
    from app.main import app
    from app.modules.notifications.retry import retry_failed_notifications
    from app.workers.preorder_expiry import expire_due_preorders

    def sql(q, **p):
        with engine.begin() as db:
            return db.execute(text(q), p).mappings().all() if q.lstrip().upper().startswith("SELECT") else db.execute(text(q), p)

    with TestClient(app) as client:
        def login(u):
            return {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"username": u, "password": "DKat@Demo2026"}).json()["access_token"]}

        owner, staff = login("owner01"), login("staff01:staff")
        inv_rows = client.get("/api/v1/inventory", headers=owner, params={"branchId": CN01, "page": 1, "size": 100}).json()
        hero = next(r["variantId"] for r in inv_rows if r["sku"] == HERO)

        def stock():
            r = next(x for x in client.get("/api/v1/inventory", headers=owner, params={"branchId": CN01, "page": 1, "size": 100}).json() if x["sku"] == HERO)
            return r["quantity"], r["reserved"], r["available"]

        def state(pid):
            row = sql("""SELECT p.status, p.payment_status, SUM(i.allocated_quantity) a, SUM(i.quantity) q
                         FROM preorders p JOIN preorder_items i ON i.preorder_id=p.preorder_id WHERE p.preorder_id=:id GROUP BY p.preorder_id""", id=pid)[0]
            return f"{row['status']} {int(row['a'])}/{int(row['q'])}"

        def sends(pid):
            return [(n["channel"], n["status"], (n["errorMessage"] or "").split(":")[0], n["retryCount"])
                    for n in client.get(f"/api/v1/preorders/{pid}/notifications", headers=owner).json()["items"]]

        def submit(customer, qty=1, variant=None):
            sql("DELETE FROM preorder_request_limits")  # the in-process client has a single IP
            return client.post("/api/v1/preorders", json={"branchId": CN01, "customer": customer,
                                                          "items": [{"variantId": variant or hero, "quantity": qty}]})

        def import_hero(n):
            r = client.post("/api/v1/inventory/import", headers=owner, json={"branchId": CN01, "note": "Kiểm thử", "items": [{"variantId": hero, "quantity": n}]})
            assert r.status_code == 201, r.text

        profile("A")
        S["lan"] = sql("SELECT preorder_id FROM preorders WHERE customer_name='Trần Thị Lan'")[0]["preorder_id"]

        @tc("TC-PN-01", "Thiếu họ tên bị từ chối")
        def _():
            r = submit({"fullName": "", "phone": "0912000001", "address": "1 Lê Lợi"})
            return f"{r.status_code} {r.json()['code']} {r.json()['details']}", r.status_code == 422 and r.json()["details"][0]["field"] == "customer.fullName"

        @tc("TC-PN-02", "Thiếu SĐT / SĐT sai định dạng bị từ chối")
        def _():
            a = submit({"fullName": "Khách B", "address": "1 Lê Lợi"})
            b = submit({"fullName": "Khách B", "phone": "12345", "address": "1 Lê Lợi"})
            return f"thiếu -> {a.status_code} {a.json()['details'][0]}; '12345' -> {b.status_code} {b.json()['details'][0]['field']}", \
                a.status_code == 422 and a.json()["details"][0]["field"] == "customer.phone" and b.status_code == 422 and b.json()["details"][0]["field"] == "customer.phone"

        @tc("TC-PN-03", "Thiếu địa chỉ bị từ chối; hàng còn thì không cho đặt trước")
        def _():
            a = submit({"fullName": "Khách B", "phone": "0912000001"})
            in_stock = next(r["variantId"] for r in inv_rows if r["sku"] == "AK-GIO-DEN-L")
            b = submit({"fullName": "Khách B", "phone": "0912000001", "address": "1 Lê Lợi"}, variant=in_stock)
            count = sql("SELECT COUNT(*) n FROM preorders")[0]["n"]
            return f"thiếu địa chỉ -> {a.status_code} {a.json()['details'][0]['field']}; Đen / L còn 6 -> {b.status_code} {b.json()['code']}; số đơn vẫn {count}", \
                a.status_code == 422 and b.status_code == 409 and b.json()["code"] == "VARIANT_IN_STOCK" and count == 1

        @tc("TC-PN-04", "Đặt trước thành công không trừ kho")
        def _():
            b = submit({"fullName": "Khách B", "phone": "0912000001", "address": "2 Lê Lợi, Quận 1"}, qty=2).json()
            c = submit({"fullName": "Khách C", "phone": "0912000002", "email": settings.EMAIL_TEST_TO, "address": "3 Lê Lợi, Quận 1"}).json()
            d = submit({"fullName": "Khách D", "phone": "0912000003", "address": "4 Lê Lợi, Quận 1"}).json()
            S.update(b=b["preorderId"], c=c["preorderId"], d=d["preorderId"], b_total=b["totalAmount"])
            st = stock()
            return f"B {b['status']} {b['totalAmount']}, C {c['status']}, D {d['status']}; tồn {HERO} CN01 (thực/giữ/khả dụng) = {st}", \
                [b["status"], c["status"], d["status"]] == ["WAITING_STOCK"] * 3 and b["totalAmount"] == "1198000.00" and st == (0, 0, 0)

        @tc("TC-PN-05", "Nhập 2 chiếc -> phân bổ FIFO đúng thứ tự")
        def _():
            import_hero(2)
            got = {k: state(S[k]) for k in ("lan", "b", "c", "d")}
            return f"{got}; tồn {stock()}; thông báo Lan {sends(S['lan'])}", \
                got == {"lan": "READY 1/1", "b": "WAITING_STOCK 1/2", "c": "WAITING_STOCK 0/1", "d": "WAITING_STOCK 0/1"} and stock() == (2, 2, 0) \
                and sends(S["lan"]) == [("EMAIL", "FAILED", "NOT_CONFIGURED", 0)]

        @tc("TC-PN-06", "Đơn đủ hàng -> READY -> gửi SMS -> NOTIFIED (cấu hình A, SMS sandbox)")
        def _():
            import_hero(1)
            return f"B {state(S['b'])}, gửi {sends(S['b'])}; C {state(S['c'])}; tồn {stock()}", \
                state(S["b"]) == "NOTIFIED 2/2" and sends(S["b"]) == [("SMS", "SENT", "", 0)] and state(S["c"]) == "WAITING_STOCK 0/1" and stock() == (3, 3, 0)

        @tc("TC-PN-07", "SMS lỗi -> tự chuyển email (cấu hình B: sai khóa eSMS, SMTP thật)")
        def _():
            profile("B")
            import_hero(1)
            return f"C {state(S['c'])}, gửi {sends(S['c'])}; tồn {stock()}", \
                state(S["c"]) == "NOTIFIED 1/1" and sends(S["c"]) == [("SMS", "FAILED", "AUTH_FAILED", 0), ("EMAIL", "SENT", "", 0)] and stock() == (4, 4, 0)

        @tc("TC-PN-08", "Thử lại tự động: email lỗi của chị Lan được gửi lại, đơn -> NOTIFIED; SMS của C không gửi lại")
        def _():
            summary = asyncio.run(retry_failed_notifications())
            return f"lượt thử lại {summary}; Lan {state(S['lan'])} {sends(S['lan'])}; C {sends(S['c'])}", \
                summary == {"checked": 1, "sent": 1, "failed": 0, "skipped": 0} and state(S["lan"]) == "NOTIFIED 1/1" \
                and sends(S["lan"]) == [("EMAIL", "SENT", "", 1)] and sends(S["c"])[0][3] == 0

        @tc("TC-PN-09", "Gửi lại thủ công (nút Gửi lại): SMS lỗi của C, rồi gửi lại thông báo đã SENT bị từ chối")
        def _():
            nid = client.get(f"/api/v1/preorders/{S['c']}/notifications", headers=staff).json()["items"]
            sms_id, email_id = nid[0]["id"], nid[1]["id"]
            a = client.post(f"/api/v1/notifications/{sms_id}/resend", headers=staff)
            b = client.post(f"/api/v1/notifications/{email_id}/resend", headers=staff)
            return f"gửi lại SMS -> {a.status_code} {a.json()['result']} retryCount {a.json()['notification']['retryCount']} " \
                   f"({(a.json()['notification']['errorMessage'] or '').split(':')[0]}); gửi lại email đã SENT -> {b.status_code} {b.json()['detail']['code']}", \
                a.status_code == 200 and a.json()["result"] == "FAILED" and a.json()["notification"]["retryCount"] == 1 \
                and b.status_code == 409 and b.json()["detail"]["code"] == "NOTIFICATION_NOT_FAILED"

        @tc("TC-PN-10", "Xác nhận nhận hàng mới trừ kho (đơn B, 1.198.000 đ)")
        def _():
            before = stock()
            pay = client.post(f"/api/v1/preorders/{S['b']}/confirm-payment", headers=staff, json={"paymentMethod": "CASH", "amount": S["b_total"]})
            mid = stock()
            done = client.post(f"/api/v1/preorders/{S['b']}/fulfill", headers=staff, json={})
            after = stock()
            return f"trước {before}; sau thu tiền {pay.json().get('paymentStatus')} {mid}; sau giao {done.json().get('status')} {after}", \
                before == (4, 4, 0) and mid == (4, 4, 0) and done.json()["status"] == "FULFILLED" and after == (2, 2, 0)

        @tc("TC-PN-11", "Hủy đơn đang giữ hàng -> giải phóng cho khách kế tiếp (FIFO)")
        def _():
            r = client.post(f"/api/v1/preorders/{S['c']}/cancel", headers=staff, json={"reason": "Khách không lấy nữa"})
            return f"C -> {r.json().get('status')}; D {state(S['d'])} gửi {sends(S['d'])}; tồn {stock()}", \
                r.json()["status"] == "CANCELLED" and state(S["d"]) == "READY 1/1" and stock() == (2, 2, 0) \
                and sends(S["d"]) == [("SMS", "FAILED", "AUTH_FAILED", 0)]

        @tc("TC-PN-12", "Hết hạn giữ hàng -> EXPIRED, giải phóng hàng")
        def _():
            sql("UPDATE preorders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE preorder_id = :id", id=S["lan"])
            n = expire_due_preorders()
            return f"job hết hạn: {n} đơn; Lan {state(S['lan'])}; D {state(S['d'])}; tồn {stock()}", \
                n == 1 and state(S["lan"]) == "EXPIRED 0/1" and state(S["d"]) == "READY 1/1" and stock() == (2, 1, 1)

    for k, v in REAL.items():
        setattr(settings, k, v)
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} test case đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

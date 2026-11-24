"""FR-09.1-09.5 pre-order notifications against a disposable local MySQL (dkat_notify_test).

Real stack: admin provisioning -> branch / product / variant -> public pre-order -> stock import ->
FIFO allocation -> NotificationService.notifyPreorder -> notifications rows -> NOTIFIED. Only the two
providers (send_sms / send_email) are replaced, so nothing leaves the machine.

    DKAT_NOTIFY_TEST_DB=1 DB_NAME=dkat_notify_test python -m unittest -v integration_tests.test_notifications_mysql
"""
import os
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.core.config import settings
from app.core.mailer import EmailResult
from app.db.session import engine
from app.main import app
from app.modules.notifications import repository
from app.modules.notifications.retry import PERMANENT_ERROR_CODES

SMS_REFUSED = EmailResult(False, None, "TEMPLATE_MISMATCH: eSMS 146 nội dung chưa đăng ký mẫu")
EMAIL_OK = EmailResult(True, "<qa-1@dkat.test>", None)
SMS_OK = EmailResult(True, "sms-qa-1", None)


@unittest.skipUnless(os.getenv("DKAT_NOTIFY_TEST_DB") == "1", "Requires isolated MySQL test database")
class PreorderNotificationMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_notify_test":
            raise RuntimeError("Use a local, disposable dkat_notify_test schema only")
        settings.NOTIFY_RETRY_ENABLED = False  # the job is tested by calling it directly
        settings.ESMS_SANDBOX = False
        settings.NOTIFY_SMS_POLL_SECONDS = 0.01  # delivery-status polling without waiting 5 s per step
        with engine.begin() as db:  # TestClient has one client IP: start with an empty public rate limit
            db.execute(text("DELETE FROM preorder_request_limits"))
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.owner, cls.branch, cls.variants = cls.provision("noti")
        cls.other_owner, _, _ = cls.provision("other")
        cls.ip = 0

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    @classmethod
    def provision(cls, prefix):
        name = f"{prefix}{uuid4().hex[:8]}"
        password = "notify-test-password-1"
        r = cls.client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
            "shop_name": name, "plan": "basic", "subscription_months": 12, "owner_username": name,
            "owner_full_name": name, "owner_password": password, "owner_email": f"{name}@example.com"})
        assert r.status_code == 201, r.text
        token = cls.client.post("/api/v1/auth/login", json={"username": name, "password": password}).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        branch = cls.client.post("/api/v1/branches", headers=auth, json={
            "branchCode": "N1", "name": "Chi nhánh Thông báo", "address": "1 Lê Lợi", "phone": "0281234567"}).json()["id"]
        category = cls.client.post("/api/v1/categories", headers=auth, json={"name": "Áo"}).json()["categoryId"]
        product = cls.client.post("/api/v1/products", headers=auth, json={"categoryId": category, "name": "Áo thông báo"}).json()["productId"]
        variants = [cls.client.post(f"/api/v1/products/{product}/variants", headers=auth, json={
            "sku": f"{name}-{i}", "variantName": f"Size {i}", "price": "100000"}).json()["variant_id"] for i in range(4)]
        return auth, branch, variants

    def preorder(self, variant, *, phone="0912345678", email="khach@example.com"):
        type(self).ip += 1
        customer = {"fullName": "Khách Thông Báo", "phone": phone, "address": "2 Lê Lợi"}
        if email:
            customer["email"] = email
        r = self.client.post("/api/v1/preorders", json={"branchId": self.branch, "customer": customer,
                                                        "items": [{"variantId": variant, "quantity": 1}]},
                             headers={"X-Forwarded-For": f"198.51.100.{self.ip}"})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["preorderId"]

    def import_stock(self, variant):
        r = self.client.post("/api/v1/inventory/import", headers=self.owner,
                             json={"branchId": self.branch, "items": [{"variantId": variant, "quantity": 1}]})
        self.assertEqual(r.status_code, 201, r.text)

    def rows(self, preorder_id):
        with engine.connect() as db:
            return db.execute(text("""SELECT channel, status, event_type, error_message, retry_count, notification_id
                                      FROM notifications WHERE preorder_id=:p ORDER BY notification_id"""),
                              {"p": preorder_id}).mappings().all()

    def status(self, preorder_id):
        return self.client.get(f"/api/v1/preorders/{preorder_id}", headers=self.owner).json()["status"]

    def test_ready_sends_sms_then_falls_back_to_email_and_marks_notified(self):
        pid = self.preorder(self.variants[0])
        with patch("app.modules.notifications.service.send_sms", AsyncMock(return_value=SMS_REFUSED)) as sms, \
                patch("app.modules.notifications.service.send_email", AsyncMock(return_value=EMAIL_OK)) as email:
            self.import_stock(self.variants[0])
        self.assertEqual(sms.await_count, 1)
        self.assertEqual(email.await_count, 1)
        self.assertIn("PD-", sms.await_args.args[1])  # the SMS text carries the pre-order code
        rows = self.rows(pid)
        self.assertEqual([(r["channel"], r["status"], r["event_type"]) for r in rows],
                         [("SMS", "FAILED", "PREORDER_READY"), ("EMAIL", "SENT", "PREORDER_READY")])
        self.assertTrue(rows[0]["error_message"].startswith("TEMPLATE_MISMATCH"))
        self.assertEqual(self.status(pid), "NOTIFIED")

        r = self.client.get(f"/api/v1/preorders/{pid}/notifications", headers=self.owner)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual([i["channel"] for i in body["items"]], ["SMS", "EMAIL"])
        self.assertNotIn("0912345678", r.text)  # NFR-08: recipients are masked
        self.assertNotIn("khach@example.com", r.text)
        self.assertEqual([i["canResend"] for i in body["items"]], [True, False])
        # the job must not resend the SMS: the customer was reached later by email
        candidates = self.run_async(repository.auto_retry_candidates(3, PERMANENT_ERROR_CODES, 50))
        self.assertNotIn(rows[0]["notification_id"], candidates)

    def test_manual_resend_counts_the_attempt_and_refuses_a_second_resend(self):
        pid = self.preorder(self.variants[1], email=None)
        with patch("app.modules.notifications.service.send_sms", AsyncMock(return_value=EmailResult(False, None, "TIMEOUT: eSMS"))):
            self.import_stock(self.variants[1])
        (row,) = self.rows(pid)
        self.assertEqual((row["channel"], row["status"]), ("SMS", "FAILED"))
        self.assertEqual(self.status(pid), "READY")  # nobody reached yet
        with patch("app.modules.notifications.service.send_sms", AsyncMock(return_value=SMS_OK)), \
                patch("app.modules.notifications.service.get_send_status", AsyncMock(return_value={"status": "DELIVERED"})):
            r = self.client.post(f"/api/v1/notifications/{row['notification_id']}/resend", headers=self.owner)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["result"], "SENT")
        self.assertEqual(r.json()["notification"]["retryCount"], 1)
        again = self.client.post(f"/api/v1/notifications/{row['notification_id']}/resend", headers=self.owner)
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(again.json()["detail"]["code"], "NOTIFICATION_NOT_FAILED")

    def test_other_store_and_anonymous_cannot_read_or_resend(self):
        pid = self.preorder(self.variants[2])
        with patch("app.modules.notifications.service.send_sms", AsyncMock(return_value=SMS_REFUSED)), \
                patch("app.modules.notifications.service.send_email", AsyncMock(return_value=EMAIL_OK)):
            self.import_stock(self.variants[2])
        nid = self.rows(pid)[0]["notification_id"]
        self.assertEqual(self.client.get(f"/api/v1/preorders/{pid}/notifications", headers=self.other_owner).status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/notifications/{nid}/resend", headers=self.other_owner).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/preorders/{pid}/notifications").status_code, 401)
        self.assertEqual(self.client.post(f"/api/v1/notifications/{nid}/resend").status_code, 401)

    def test_unconfigured_providers_never_break_the_stock_import(self):
        pid = self.preorder(self.variants[3])
        saved = (settings.SMTP_HOST, settings.ESMS_API_KEY, settings.ESMS_SECRET_KEY)
        settings.SMTP_HOST = settings.ESMS_API_KEY = settings.ESMS_SECRET_KEY = ""
        try:
            self.import_stock(self.variants[3])  # 201 even though no channel can send
        finally:
            settings.SMTP_HOST, settings.ESMS_API_KEY, settings.ESMS_SECRET_KEY = saved
        rows = self.rows(pid)
        self.assertEqual([(r["channel"], r["status"]) for r in rows], [("SMS", "FAILED"), ("EMAIL", "FAILED")])
        self.assertTrue(all(r["error_message"].startswith("NOT_CONFIGURED") for r in rows), rows)
        self.assertEqual(self.status(pid), "READY")

    @staticmethod
    def run_async(coro):
        import asyncio
        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()

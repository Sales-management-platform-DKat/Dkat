"""Platform admin (X-Admin-Token) vs store accounts (bearer JWT), and access-token validation."""
import time
import unittest

from app.core.security import create_access_token, decode_access_token
from tests import test_auth_flow as base

ADMIN = {"X-Admin-Token": base.TEST_ADMIN_TOKEN}


class AdminAuthTests(unittest.TestCase):
    setUpClass = classmethod(base.AuthFlowTests.setUpClass.__func__)
    tearDownClass = classmethod(base.AuthFlowTests.tearDownClass.__func__)
    setUp = base.AuthFlowTests.setUp
    provision = base.AuthFlowTests.provision
    login = base.AuthFlowTests.login

    def owner_headers(self):
        self.assertEqual(self.provision().status_code, 201)
        token = self.login("owner1", "owner-password-123").json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_admin_token_opens_admin_dashboard(self):
        self.assertEqual(self.provision().status_code, 201)
        response = self.client.get("/api/v1/admin/accounts", headers=ADMIN)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([a["owner_username"] for a in response.json()], ["owner1"])

    def test_admin_token_with_copy_paste_whitespace_is_accepted(self):
        response = self.client.get("/api/v1/admin/accounts", headers={"X-Admin-Token": f"  {base.TEST_ADMIN_TOKEN}\t"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_wrong_or_missing_admin_token_is_rejected(self):
        for headers in ({}, {"X-Admin-Token": "wrong-token-" + "x" * 30}, {"X-Admin-Token": "   "}):
            response = self.client.get("/api/v1/admin/accounts", headers=headers)
            self.assertEqual(response.status_code, 401, (headers, response.text))

    def test_unconfigured_admin_token_returns_503_not_open_access(self):
        from app.core import config
        config.ADMIN_TOKEN = ""
        response = self.client.get("/api/v1/admin/accounts", headers={"X-Admin-Token": ""})
        self.assertEqual(response.status_code, 503)

    def test_owner_bearer_token_cannot_use_platform_admin(self):
        headers = self.owner_headers()
        self.assertEqual(self.client.get("/api/v1/admin/accounts", headers=headers).status_code, 401)
        created = self.client.post("/api/v1/admin/accounts", headers=headers, json={
            "shop_name": "Hack", "plan": "basic", "subscription_months": 1, "owner_username": "x1",
            "owner_email": "x1@example.test", "owner_full_name": "x", "owner_password": "password-123456",
        })
        self.assertEqual(created.status_code, 401)

    def test_employee_cannot_use_management_or_admin_features(self):
        headers = self.owner_headers()
        created = self.client.post("/api/v1/users", headers=headers, json={
            "username": "staff1", "full_name": "Staff", "password": "staff-password-123", "role": "staff",
        })
        self.assertEqual(created.status_code, 201, created.text)
        staff = {"Authorization": "Bearer " + self.login("staff1:staff", "staff-password-123").json()["access_token"]}
        self.assertEqual(self.client.get("/api/v1/users", headers=staff).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/branches", headers=staff, json={
            "branchCode": "X1", "name": "X", "address": "Y"}).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/admin/accounts", headers=staff).status_code, 401)

    def test_wrong_password_is_rejected(self):
        self.assertEqual(self.provision().status_code, 201)
        response = self.login("owner1", "not-the-password")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.json())

    def test_expired_access_token_is_rejected(self):
        self.owner_headers()
        me = self.login("owner1", "owner-password-123").json()
        sid = decode_access_token(me["access_token"])["sid"]
        # Same user and live session, but signed as if issued an hour ago (TTL is 15 minutes).
        expired, _ = create_access_token(me["user"]["id"], sid, now=int(time.time()) - 3600)
        response = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
        self.assertEqual(response.status_code, 401)

    def test_invalid_and_tampered_tokens_are_rejected(self):
        headers = self.owner_headers()
        token = headers["Authorization"].split()[1]
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 200)
        tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
        for bad in ("not-a-jwt", tampered, token + "x"):
            response = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"})
            self.assertEqual(response.status_code, 401, bad)


if __name__ == "__main__":
    unittest.main()

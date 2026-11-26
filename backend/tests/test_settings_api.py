"""Settings screen APIs: /stores/me, PUT /auth/me, password change and sessions."""
import unittest

from tests import test_auth_flow as base

OWNER_PASSWORD = "owner-password-123"


class SettingsApiTests(unittest.TestCase):
    setUpClass = classmethod(base.AuthFlowTests.setUpClass.__func__)
    tearDownClass = classmethod(base.AuthFlowTests.tearDownClass.__func__)
    setUp = base.AuthFlowTests.setUp
    provision = base.AuthFlowTests.provision
    login = base.AuthFlowTests.login

    def owner(self):
        self.assertEqual(self.provision().status_code, 201)
        response = self.login("owner1", OWNER_PASSWORD)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def staff(self, owner):
        created = self.client.post("/api/v1/users", headers=owner, json={
            "username": "staff1", "full_name": "Staff", "password": "staff-password-123", "role": "staff"})
        self.assertEqual(created.status_code, 201, created.text)
        token = self.login("staff1:staff", "staff-password-123").json()["access_token"]
        return {"Authorization": "Bearer " + token}

    # ---- store ----
    def test_store_summary_and_owner_can_rename(self):
        owner = self.owner()
        store = self.client.get("/api/v1/stores/me", headers=owner)
        self.assertEqual(store.status_code, 200, store.text)
        body = store.json()
        self.assertEqual((body["plan"], body["subscriptionStatus"], body["canEdit"]), ("basic", "ACTIVE", True))
        self.assertGreaterEqual(body["branchCount"], body["activeBranchCount"])
        renamed = self.client.put("/api/v1/stores/me", headers=owner, json={"name": "  Cửa hàng mới  "})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["name"], "Cửa hàng mới")
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=owner).json()["shop_name"], "Cửa hàng mới")

    def test_staff_reads_store_but_cannot_rename(self):
        owner = self.owner()
        staff = self.staff(owner)
        store = self.client.get("/api/v1/stores/me", headers=staff)
        self.assertEqual((store.status_code, store.json()["canEdit"]), (200, False))
        self.assertEqual(self.client.put("/api/v1/stores/me", headers=staff, json={"name": "Hack"}).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/stores/me", headers=owner).json()["staffCount"], 1)

    def test_store_name_is_validated(self):
        owner = self.owner()
        for name in ("", " a ", "x" * 151):
            self.assertEqual(self.client.put("/api/v1/stores/me", headers=owner, json={"name": name}).status_code, 422, name)

    # ---- profile ----
    def test_profile_update_normalises_and_rejects_taken_email(self):
        owner = self.owner()
        updated = self.client.put("/api/v1/auth/me", headers=owner, json={
            "full_name": "  Chủ Mới ", "email": "NEW@Example.test ", "phone": "0901 234 567"})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual((updated.json()["full_name"], updated.json()["email"], updated.json()["phone"]),
                         ("Chủ Mới", "new@example.test", "0901 234 567"))
        cleared = self.client.put("/api/v1/auth/me", headers=owner, json={"full_name": "Chủ Mới", "email": "", "phone": ""})
        self.assertEqual((cleared.json()["email"], cleared.json()["phone"]), (None, None))
        staff = self.staff(owner)
        self.client.put("/api/v1/auth/me", headers=owner, json={"full_name": "Chủ", "email": "boss@example.test"})
        taken = self.client.put("/api/v1/auth/me", headers=staff, json={"full_name": "Staff", "email": "Boss@example.test"})
        self.assertEqual((taken.status_code, taken.json()["detail"]["code"]), (409, "EMAIL_TAKEN"))
        bad = self.client.put("/api/v1/auth/me", headers=owner, json={"full_name": "Chủ", "phone": "abc"})
        self.assertEqual(bad.status_code, 422)

    # ---- password & sessions ----
    def test_wrong_current_password_is_400_not_401(self):
        owner = self.owner()
        response = self.client.post("/api/v1/auth/change-password", headers=owner, json={
            "current_password": "nope", "new_password": "another-password-123"})
        self.assertEqual((response.status_code, response.json()["detail"]["code"]), (400, "CURRENT_PASSWORD_INVALID"))
        same = self.client.post("/api/v1/auth/change-password", headers=owner, json={
            "current_password": OWNER_PASSWORD, "new_password": OWNER_PASSWORD})
        self.assertEqual(same.json()["detail"]["code"], "PASSWORD_UNCHANGED")
        short = self.client.post("/api/v1/auth/change-password", headers=owner, json={
            "current_password": OWNER_PASSWORD, "new_password": "short"})
        self.assertEqual(short.status_code, 422)

    def test_password_change_signs_out_other_devices_only(self):
        current = self.owner()
        other = {"Authorization": "Bearer " + self.login("owner1", OWNER_PASSWORD).json()["access_token"]}
        self.assertEqual(self.client.get("/api/v1/auth/sessions", headers=current).json(),
                         {"active_sessions": 2, "other_sessions": 1})
        changed = self.client.post("/api/v1/auth/change-password", headers=current, json={
            "current_password": OWNER_PASSWORD, "new_password": "brand-new-password-1"})
        self.assertEqual((changed.status_code, changed.json()["revoked_sessions"]), (200, 1))
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=current).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=other).status_code, 401)
        self.assertEqual(self.login("owner1", OWNER_PASSWORD).status_code, 401)
        self.assertEqual(self.login("owner1", "brand-new-password-1").status_code, 200)

    def test_revoke_other_sessions(self):
        current = self.owner()
        others = [{"Authorization": "Bearer " + self.login("owner1", OWNER_PASSWORD).json()["access_token"]} for _ in range(2)]
        revoked = self.client.post("/api/v1/auth/sessions/revoke-others", headers=current)
        self.assertEqual(revoked.json(), {"revoked_sessions": 2})
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=current).status_code, 200)
        for headers in others:
            self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 401)

    def test_settings_endpoints_require_login(self):
        for method, path in (("get", "/api/v1/stores/me"), ("put", "/api/v1/auth/me"), ("post", "/api/v1/auth/change-password"),
                             ("get", "/api/v1/auth/sessions"), ("post", "/api/v1/auth/sessions/revoke-others")):
            self.assertEqual(getattr(self.client, method)(path).status_code, 401, path)


if __name__ == "__main__":
    unittest.main()

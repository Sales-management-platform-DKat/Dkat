import unittest
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.auth.models import Shop, StoreSubscription
from app.modules.auth.service import utcnow
import app.main as main_module
import app.modules.customers.router as customer_router


TEST_ADMIN_TOKEN = "test-admin-token-0123456789-abcdefgh"
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main_module.engine = test_engine
        customer_router.engine = test_engine
        app.dependency_overrides[get_db] = override_get_db
        config.ADMIN_TOKEN = TEST_ADMIN_TOKEN
        config.AUTH_SECRET_KEY = "test-auth-secret-key-with-at-least-32-characters"
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        app.dependency_overrides.clear()
        test_engine.dispose()

    def setUp(self):
        config.ADMIN_TOKEN = TEST_ADMIN_TOKEN
        config.AUTH_SECRET_KEY = "test-auth-secret-key-with-at-least-32-characters"
        self.client.cookies.clear()
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)
        with test_engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS branches (branch_id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL, name VARCHAR(100) NOT NULL)")
            connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS user_branches (user_id INTEGER NOT NULL, branch_id INTEGER NOT NULL)")
            connection.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS sales_orders (
                    sales_order_id INTEGER PRIMARY KEY, order_code VARCHAR(50) NOT NULL,
                    branch_id INTEGER NOT NULL, customer_id INTEGER, created_at DATETIME NOT NULL,
                    status VARCHAR(30) NOT NULL, total_amount NUMERIC NOT NULL
                )
            """)
            connection.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS preorders (
                    preorder_id INTEGER PRIMARY KEY, preorder_code VARCHAR(50) NOT NULL,
                    branch_id INTEGER NOT NULL, customer_id INTEGER, created_at DATETIME NOT NULL,
                    status VARCHAR(30) NOT NULL, total_amount NUMERIC NOT NULL
                )
            """)

    def provision(self, username="owner1"):
        return self.client.post(
            "/api/v1/admin/accounts",
            headers={"X-Admin-Token": TEST_ADMIN_TOKEN},
            json={
                "shop_name": "Cá»­a hÃ ng thá»­ nghiá»‡m",
                "plan": "basic",
                "subscription_months": 12,
                "owner_username": username,
                "owner_email": f"{username}@example.test",
                "owner_full_name": "Chá»§ cá»­a hÃ ng",
                "owner_password": "owner-password-123",
            },
        )

    def login(self, username, password):
        return self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

    def test_admin_provisions_shop_and_owner_login(self):
        config.ADMIN_TOKEN = ""
        unconfigured = self.client.post("/api/v1/admin/accounts")
        self.assertEqual(unconfigured.status_code, 503)
        config.ADMIN_TOKEN = TEST_ADMIN_TOKEN

        unauthorized = self.client.post(
            "/api/v1/admin/accounts",
            json={
                "shop_name": "Cá»­a hÃ ng thá»­ nghiá»‡m",
                "plan": "basic",
                "subscription_months": 12,
                "owner_username": "owner1",
                "owner_email": "owner1@example.test",
                "owner_full_name": "Chá»§ cá»­a hÃ ng",
                "owner_password": "owner-password-123",
            },
        )
        self.assertEqual(unauthorized.status_code, 401)

        provisioned = self.provision()
        self.assertEqual(provisioned.status_code, 201, provisioned.text)
        self.assertEqual(provisioned.json()["plan"], "basic")
        self.assertEqual(provisioned.json()["owner_username"], "owner1")

        login = self.login("owner1", "owner-password-123")
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["role"], "owner")
        token = login.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=owner_headers).json()["shop_id"],
            provisioned.json()["shop_id"],
        )
        self.assertEqual(self.login("owner1", "wrong-password").status_code, 401)
        self.assertEqual(
            self.client.post("/api/v1/auth/logout", headers=owner_headers).status_code,
            204,
        )
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=owner_headers).status_code, 401)

    def test_customer_list_profile_update_and_purchase_history_routes(self):
        self.assertEqual(self.provision().status_code, 201)
        login = self.login("owner1", "owner-password-123")
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        created = self.client.post("/api/v1/customers", headers=headers, json={
            "fullName": "Nguyá»…n An", "phone": "0901234567", "email": "an@example.test",
            "address": "Quáº­n 1", "note": "KhÃ¡ch thÃ¢n thiáº¿t",
        })
        self.assertEqual(created.status_code, 201, created.text)
        customer_id = created.json()["customerId"]
        self.assertEqual(created.json()["note"], "KhÃ¡ch thÃ¢n thiáº¿t")
        listing = self.client.get("/api/v1/customers?q=Nguyá»…n", headers=headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()[0]["customerId"], customer_id)
        detail = self.client.get(f"/api/v1/customers/{customer_id}", headers=headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        history = self.client.get(f"/api/v1/customers/{customer_id}/history", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json(), [])
        updated = self.client.put(f"/api/v1/customers/{customer_id}", headers=headers, json={
            "fullName": "Nguyá»…n An má»›i", "phone": "0901234567", "email": None,
            "address": None, "note": None,
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["fullName"], "Nguyá»…n An má»›i")

    def test_revenue_reports_allow_owner_and_block_employee(self):
        self.assertEqual(self.provision().status_code, 201)
        owner_login = self.login("owner1", "owner-password-123")
        owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
        owner_result = self.client.get("/api/v1/reports/summary", headers=owner_headers)
        self.assertEqual(owner_result.status_code, 200, owner_result.text)
        employee = self.client.post("/api/v1/users", headers=owner_headers, json={
            "username": "staff1", "full_name": "NhÃ¢n viÃªn", "password": "staff-password-123",
            "role": "staff",
        })
        self.assertEqual(employee.status_code, 201, employee.text)
        employee_login = self.login("staff1:staff", "staff-password-123")
        employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
        denied = self.client.get("/api/v1/reports/summary", headers=employee_headers)
        self.assertEqual(denied.status_code, 403)

    def test_each_role_uses_its_suffix_and_own_password(self):
        self.assertEqual(self.provision().status_code, 201)
        owner_token = self.login("owner1", "owner-password-123").json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        for username, role in (("manager1", "manager"), ("staff1", "staff")):
            created = self.client.post(
                "/api/v1/users",
                headers=owner_headers,
                json={
                    "username": username,
                    "full_name": role.title(),
                    "role": role,
                    "password": f"{role}-password-123",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["shop_id"], self.client.get(
                "/api/v1/auth/me", headers=owner_headers
            ).json()["shop_id"])

        manager = self.login("manager1:manager", "manager-password-123")
        staff = self.login("staff1:staff", "staff-password-123")
        self.assertEqual(manager.status_code, 200, manager.text)
        self.assertEqual(staff.status_code, 200, staff.text)
        self.assertEqual(manager.json()["user"]["role"], "manager")
        self.assertEqual(staff.json()["user"]["role"], "staff")
        self.assertEqual(
            self.login("manager1:manager", "staff-password-123").status_code,
            401,
        )

        staff_headers = {"Authorization": f"Bearer {staff.json()['access_token']}"}
        forbidden = self.client.post(
            "/api/v1/users",
            headers=staff_headers,
            json={
                "username": "another",
                "full_name": "KhÃ´ng Ä‘Æ°á»£c cáº¥p quyá»n",
                "role": "staff",
                "password": "another-password-123",
            },
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_expired_subscription_blocks_login_and_duplicate_owner(self):
        provisioned = self.provision()
        self.assertEqual(provisioned.status_code, 201)
        self.assertEqual(self.provision().status_code, 409)

        with TestSession() as db:
            subscription = db.scalar(select(StoreSubscription))
            subscription.subscription_expires_at = utcnow() - timedelta(days=1)
            db.commit()

        self.assertEqual(self.login("owner1", "owner-password-123").status_code, 401)

    def test_refresh_rotation_remember_cookie_and_reuse_revokes_sessions(self):
        self.assertEqual(self.provision().status_code, 201)
        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "owner1",
                "password": "owner-password-123",
                "remember_me": True,
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        original_access = login.json()["access_token"]
        original_refresh = login.cookies.get("dkat_refresh")
        self.assertTrue(original_refresh)
        set_cookie = login.headers["set-cookie"].lower()
        self.assertIn("httponly", set_cookie)
        self.assertIn("max-age=", set_cookie)
        self.assertNotIn("secure", set_cookie)

        rotated = self.client.post("/api/v1/auth/refresh")
        self.assertEqual(rotated.status_code, 200, rotated.text)
        self.assertNotEqual(rotated.json()["access_token"], original_access)
        rotated_access = rotated.json()["access_token"]
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {rotated_access}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {original_access}"},
            ).status_code,
            401,
        )

        self.client.cookies.clear()
        self.client.cookies.set(
            "dkat_refresh", original_refresh, path="/api/v1/auth"
        )
        reused = self.client.post("/api/v1/auth/refresh")
        self.assertEqual(reused.status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {rotated_access}"},
            ).status_code,
            401,
        )

    def test_unremembered_login_uses_session_cookie(self):
        self.assertEqual(self.provision().status_code, 201)
        login = self.login("owner1", "owner-password-123")
        self.assertEqual(login.status_code, 200, login.text)
        set_cookie = login.headers["set-cookie"].lower()
        self.assertIn("httponly", set_cookie)
        self.assertNotIn("max-age=", set_cookie)


if __name__ == "__main__":
    unittest.main()

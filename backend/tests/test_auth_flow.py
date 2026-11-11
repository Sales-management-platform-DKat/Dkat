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
        app.dependency_overrides[get_db] = override_get_db
        config.ADMIN_TOKEN = TEST_ADMIN_TOKEN
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        app.dependency_overrides.clear()
        test_engine.dispose()

    def setUp(self):
        config.ADMIN_TOKEN = TEST_ADMIN_TOKEN
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)

    def provision(self, username="owner1"):
        return self.client.post(
            "/api/v1/admin/accounts",
            headers={"X-Admin-Token": TEST_ADMIN_TOKEN},
            json={
                "shop_name": "Cửa hàng thử nghiệm",
                "plan": "pro",
                "subscription_months": 12,
                "owner_username": username,
                "owner_full_name": "Chủ cửa hàng",
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
                "shop_name": "Cửa hàng thử nghiệm",
                "plan": "pro",
                "subscription_months": 12,
                "owner_username": "owner1",
                "owner_full_name": "Chủ cửa hàng",
                "owner_password": "owner-password-123",
            },
        )
        self.assertEqual(unauthorized.status_code, 401)

        provisioned = self.provision()
        self.assertEqual(provisioned.status_code, 201, provisioned.text)
        self.assertEqual(provisioned.json()["plan"], "pro")
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
                "full_name": "Không được cấp quyền",
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


if __name__ == "__main__":
    unittest.main()

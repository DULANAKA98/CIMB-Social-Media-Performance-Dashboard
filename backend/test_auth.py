import os
import tempfile
import unittest

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'auth_test.db')}"

import auth  # noqa: E402

os.environ["SESSION_SECRET"] = "test-secret-" + "x" * 40
os.environ["DASHBOARD_USERS"] = f"analyst:{auth.hash_password('correct horse battery')}"

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, engine  # noqa: E402
from main import app, login_throttle  # noqa: E402


class AuthHelperTests(unittest.TestCase):
    def test_password_hash_round_trip(self):
        stored = auth.hash_password("s3cret-password!")
        self.assertTrue(auth.verify_password("s3cret-password!", stored))
        self.assertFalse(auth.verify_password("wrong", stored))
        self.assertNotIn("$", stored)  # safe in docker compose env files

    def test_session_rejects_tampering_and_expiry(self):
        token = auth.create_session("analyst", now=1_000_000)
        self.assertEqual(auth.read_session(token, now=1_000_100), "analyst")
        self.assertIsNone(auth.read_session(token, now=1_000_000 + auth.SESSION_SECONDS + 1))
        body, signature = token.split(".")
        self.assertIsNone(auth.read_session(f"{body}x.{signature}", now=1_000_100))

    def test_password_change_invalidates_sessions(self):
        token = auth.create_session("analyst")
        original = os.environ["DASHBOARD_USERS"]
        try:
            os.environ["DASHBOARD_USERS"] = f"analyst:{auth.hash_password('a brand new password')}"
            self.assertIsNone(auth.read_session(token))
        finally:
            os.environ["DASHBOARD_USERS"] = original

    def test_throttle_locks_after_limit(self):
        throttle = auth.LoginThrottle(limit=3, window=60)
        for _ in range(3):
            throttle.failed("Analyst", now=10)
        self.assertGreater(throttle.retry_after("analyst", now=11), 0)
        self.assertEqual(throttle.retry_after("analyst", now=71), 0)


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        login_throttle.succeeded("analyst")
        self.client = TestClient(app)

    def test_api_requires_login(self):
        self.assertEqual(self.client.get("/api/campaigns").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_login_me_logout(self):
        wrong = self.client.post("/api/auth/login", json={"username": "analyst", "password": "nope"})
        self.assertEqual(wrong.status_code, 401)
        ok = self.client.post("/api/auth/login", json={"username": "Analyst", "password": "correct horse battery"})
        self.assertEqual(ok.status_code, 200, ok.text)
        cookie = ok.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertEqual(self.client.get("/api/auth/me").json(), {"username": "analyst"})
        self.assertEqual(self.client.get("/api/campaigns").status_code, 200)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/campaigns").status_code, 401)

    def test_repeated_failures_are_throttled(self):
        for _ in range(auth.LOGIN_FAILURE_LIMIT):
            self.client.post("/api/auth/login", json={"username": "analyst", "password": "nope"})
        locked = self.client.post("/api/auth/login", json={"username": "analyst", "password": "correct horse battery"})
        self.assertEqual(locked.status_code, 429)

    def test_follower_refresh_keeps_its_own_secret(self):
        # Not blocked by the login check; still rejected without its shared secret.
        os.environ["FOLLOWER_REFRESH_SECRET"] = "job-secret"
        self.assertEqual(self.client.post("/api/followers/refresh").status_code, 401)

    def test_unconfigured_server_fails_closed(self):
        original = os.environ.pop("SESSION_SECRET")
        try:
            self.assertEqual(self.client.get("/api/campaigns").status_code, 503)
        finally:
            os.environ["SESSION_SECRET"] = original


if __name__ == "__main__":
    unittest.main()

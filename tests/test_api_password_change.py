import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from api.main import app
except Exception:  # pragma: no cover - depends on optional api requirements
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi test dependencies are not installed")
class PasswordChangeApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.apply_password_change")
    def test_post_password_change_success(self, apply_password_change, read_one_camera_payload):
        apply_password_change.return_value = {
            "ok": True,
            "errors": [],
            "credential_status": "verified",
            "camera": {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "new-password",
            },
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.221",
            "name": None,
            "connection": {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "new-password",
            },
            "summary": {"model": "AXIS M3215-LVE"},
        }
        response = self.client.post(
            "/api/password-change",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.221",
                        "username": "root",
                        "password": "old-password",
                    }
                ],
                "new_password": "new-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["credential_status"], "verified")
        self.assertEqual(body["results"][0]["result"]["connection"]["password"], "new-password")

    @patch("api.main._read_one_camera_payload", side_effect=RuntimeError("re-auth failed"))
    @patch("api.main.apply_password_change")
    def test_post_password_change_needs_reauth(self, apply_password_change, _read_one_camera_payload):
        apply_password_change.return_value = {
            "ok": True,
            "errors": [],
            "credential_status": "verified",
            "camera": {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "new-password",
            },
        }
        response = self.client.post(
            "/api/password-change",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.221",
                        "username": "root",
                        "password": "old-password",
                    }
                ],
                "new_password": "new-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["results"][0]["ok"])
        self.assertEqual(body["results"][0]["credential_status"], "needs_reauth")
        self.assertIsNone(body["results"][0]["result"])

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.apply_password_change")
    def test_post_password_change_needs_reauth_when_refresh_returns_auth_error(
        self,
        apply_password_change,
        read_one_camera_payload,
    ):
        apply_password_change.return_value = {
            "ok": True,
            "errors": [],
            "credential_status": "verified",
            "camera": {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "new-password",
            },
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.221",
            "name": None,
            "error": "Authentication failed (wrong username or password).",
            "connection": {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "new-password",
            },
        }
        response = self.client.post(
            "/api/password-change",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.221",
                        "username": "root",
                        "password": "old-password",
                    }
                ],
                "new_password": "new-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"][0]["credential_status"], "needs_reauth")
        self.assertIsNone(body["results"][0]["result"])

    @patch("api.main.apply_password_change")
    def test_post_password_change_failure(self, apply_password_change):
        apply_password_change.return_value = {
            "ok": False,
            "errors": ["Administrator privileges are required to change the camera password."],
            "credential_status": "failed",
        }
        response = self.client.post(
            "/api/password-change",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.221",
                        "username": "root",
                        "password": "old-password",
                    }
                ],
                "new_password": "new-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["results"][0]["ok"])
        self.assertEqual(body["results"][0]["credential_status"], "failed")


if __name__ == "__main__":
    unittest.main()

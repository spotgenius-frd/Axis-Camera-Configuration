import unittest
from unittest.mock import patch

from axis_bulk_config.client import AxisCameraError
from axis_bulk_config.write_service import apply_password_change


class RecordingClient:
    def __init__(self):
        self.calls = []

    def pwdgrp_get_accounts(self):
        self.calls.append(("get", {}))
        return "root"

    def pwdgrp_update_password(self, user: str, new_password: str):
        self.calls.append(("update", {"user": user, "new_password": new_password}))
        return f"Modified account {user}."


class PasswordChangeServiceTest(unittest.TestCase):
    @patch("axis_bulk_config.write_service.make_client")
    def test_apply_password_change_success(self, make_client):
        client = RecordingClient()
        make_client.return_value = client
        result = apply_password_change(
            {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "old-password",
                "name": "Front gate",
            },
            "new-password",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["credential_status"], "verified")
        self.assertEqual(result["camera"]["password"], "new-password")
        self.assertEqual(client.calls[1][1]["user"], "root")

    @patch("axis_bulk_config.write_service.make_client")
    def test_apply_password_change_reports_unsupported_api(self, make_client):
        client = RecordingClient()
        client.pwdgrp_get_accounts = lambda: (_ for _ in ()).throw(
            AxisCameraError("missing", status_code=404)
        )
        make_client.return_value = client
        result = apply_password_change(
            {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "old-password",
            },
            "new-password",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["credential_status"], "failed")
        self.assertEqual(result["errors"], ["User management API is not supported on this camera."])

    @patch("axis_bulk_config.write_service.make_client")
    def test_apply_password_change_redacts_secret_from_error(self, make_client):
        client = RecordingClient()
        client.pwdgrp_update_password = lambda user, password: (_ for _ in ()).throw(
            RuntimeError(f"Rejected password {password}")
        )
        make_client.return_value = client
        result = apply_password_change(
            {
                "ip": "192.168.1.221",
                "username": "root",
                "password": "old-password",
            },
            "super-secret",
        )
        self.assertFalse(result["ok"])
        self.assertNotIn("super-secret", result["errors"][0])
        self.assertIn("[redacted]", result["errors"][0])


if __name__ == "__main__":
    unittest.main()

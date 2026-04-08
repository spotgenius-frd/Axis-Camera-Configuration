import unittest
from unittest.mock import patch

from axis_bulk_config.client import AxisCameraError
from axis_bulk_config.write_service import (
    onboard_scanned_camera,
    probe_scanned_camera_auth,
    setup_scanned_camera,
)


class _LegacyClient:
    def __init__(self, get_error=None, update_error=None):
        self.get_error = get_error
        self.update_error = update_error
        self.calls = []

    def pwdgrp_get_accounts(self):
        self.calls.append(("get", {}))
        if self.get_error:
            raise self.get_error
        return "root"

    def pwdgrp_update_password(self, user: str, new_password: str):
        self.calls.append(("update", {"user": user, "new_password": new_password}))
        if self.update_error:
            raise self.update_error
        return f"Modified {user}"


class ScanOnboardingServiceTest(unittest.TestCase):
    @patch("axis_bulk_config.write_service.pwdgrp_probe_initial_admin_required", return_value=True)
    def test_probe_scanned_camera_auth_first_time_available(self, _probe):
        result = probe_scanned_camera_auth(
            {"ip": "192.168.1.40", "hostname": "axis-new", "https_port": 443}
        )

        self.assertEqual(result["auth_status"], "authenticated")
        self.assertEqual(result["auth_path"], "initial_admin_required")

    @patch("axis_bulk_config.write_service.make_client")
    @patch("axis_bulk_config.write_service.pwdgrp_probe_initial_admin_required", return_value=False)
    def test_probe_scanned_camera_auth_legacy_root_pass(self, _probe, make_client):
        make_client.return_value = _LegacyClient()

        result = probe_scanned_camera_auth(
            {"ip": "192.168.1.50", "hostname": "axis-legacy", "http_port": 80}
        )

        self.assertEqual(result["auth_status"], "authenticated")
        self.assertEqual(result["auth_path"], "legacy_root_pass")

    @patch("axis_bulk_config.write_service.make_client")
    @patch("axis_bulk_config.write_service.pwdgrp_probe_initial_admin_required", return_value=False)
    def test_probe_scanned_camera_auth_existing_credentials_required(self, _probe, make_client):
        make_client.return_value = _LegacyClient(
            get_error=AxisCameraError("unauthorized", status_code=401)
        )

        result = probe_scanned_camera_auth(
            {"ip": "192.168.1.60", "hostname": "axis-configured", "http_port": 80}
        )

        self.assertEqual(result["auth_status"], "unauthenticated")
        self.assertEqual(result["auth_path"], "existing_credentials_required")

    @patch("axis_bulk_config.write_service.refresh_camera")
    def test_setup_scanned_camera_existing_credentials_success(self, refresh_camera):
        refresh_camera.return_value = {
            "camera_ip": "192.168.1.70",
            "summary": {"model": "AXIS configured"},
        }

        result = setup_scanned_camera(
            {
                "ip": "192.168.1.70",
                "hostname": "axis-configured",
                "http_port": 80,
                "auth_status": "unauthenticated",
                "auth_path": "existing_credentials_required",
                "username": "root",
                "password": "KnownPassword1!",
            }
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["auth_path"], "existing_credentials_authenticated")

    @patch("axis_bulk_config.write_service.refresh_camera")
    @patch("axis_bulk_config.write_service.pwdgrp_add_account_unauthenticated")
    def test_onboard_scanned_camera_modern_factory_default_success(
        self,
        pwdgrp_add_account_unauthenticated,
        refresh_camera,
    ):
        pwdgrp_add_account_unauthenticated.return_value = "Created account root."
        refresh_camera.return_value = {
            "camera_ip": "192.168.1.40",
            "summary": {"model": "AXIS M3215-LVE"},
        }

        result = onboard_scanned_camera(
            {
                "ip": "192.168.1.40",
                "hostname": "axis-new",
                "http_port": 80,
                "https_port": 443,
            },
            "Spotgenius1!",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["auth_path"], "initial_root_created")
        self.assertEqual(result["camera"]["username"], "root")
        self.assertEqual(result["camera"]["password"], "Spotgenius1!")
        self.assertEqual(result["camera"]["scheme"], "https")

    @patch("axis_bulk_config.write_service.refresh_camera")
    @patch("axis_bulk_config.write_service.make_client")
    @patch("axis_bulk_config.write_service.pwdgrp_add_account_unauthenticated")
    def test_setup_scanned_camera_maps_legacy_default_flow(
        self,
        pwdgrp_add_account_unauthenticated,
        make_client,
        refresh_camera,
    ):
        pwdgrp_add_account_unauthenticated.side_effect = AxisCameraError(
            "not authorized",
            status_code=401,
        )
        make_client.return_value = _LegacyClient()
        refresh_camera.return_value = {
            "camera_ip": "192.168.1.50",
            "summary": {"model": "AXIS legacy"},
        }

        result = setup_scanned_camera(
            {
                "ip": "192.168.1.50",
                "hostname": "axis-legacy",
                "http_port": 80,
                "auth_status": "authenticated",
                "auth_path": "legacy_root_pass",
            },
            new_root_password="Spotgenius1!",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["auth_path"], "legacy_default_normalized")


if __name__ == "__main__":
    unittest.main()

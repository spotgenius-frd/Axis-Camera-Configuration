import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from api.main import app
except Exception:  # pragma: no cover - depends on optional api requirements
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi test dependencies are not installed")
class NetworkScanApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main._network_scan_metadata")
    def test_get_network_scan_options_returns_defaults(self, network_scan_metadata):
        network_scan_metadata.return_value = {
            "scan_target": {
                "interface_name": "eth0",
                "display_name": "eth0",
                "interface_ip": "192.168.1.15",
                "cidr": "192.168.1.0/24",
            },
            "interface_options": [
                {
                    "name": "eth0",
                    "display_name": "eth0",
                    "ip_address": "192.168.1.15",
                    "network_cidr": "192.168.1.0/24",
                    "suggested_cidr": "192.168.1.0/24",
                    "is_private": True,
                }
            ],
            "devices": [],
            "errors": [],
        }

        response = self.client.get("/api/network-scan/options")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scan_target"]["interface_name"], "eth0")
        self.assertEqual(len(body["interface_options"]), 1)

    @patch("api.main.probe_scanned_camera_auth")
    @patch("api.main.discover_axis_devices")
    def test_post_network_scan_success_enriches_auth(self, discover_axis_devices, probe_scanned_camera_auth):
        discover_axis_devices.return_value = {
            "scan_target": {
                "interface_name": "eth0",
                "display_name": "eth0",
                "interface_ip": "192.168.1.15",
                "cidr": "192.168.1.0/24",
            },
            "interface_options": [],
            "devices": [
                {
                    "ip": "192.168.1.40",
                    "mac": "B8:A4:4F:00:11:22",
                    "model": "AXIS M3215-LVE",
                    "serial": "00408CF3ABCD",
                    "firmware": "11.11.192",
                    "hostname": "axis-m3215",
                    "http_port": 80,
                    "https_port": 443,
                    "discovery_sources": ["tcp:80", "bdi:http"],
                    "confidence": "confirmed",
                }
            ],
            "errors": [],
        }
        probe_scanned_camera_auth.return_value = {
            "auth_status": "authenticated",
            "auth_path": "initial_admin_required",
            "auth_message": "First-time setup available.",
        }

        response = self.client.post(
            "/api/network-scan",
            json={"interface_name": "eth0", "cidr": "192.168.1.0/24"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["devices"]), 1)
        self.assertEqual(body["devices"][0]["model"], "AXIS M3215-LVE")
        self.assertEqual(body["devices"][0]["auth_status"], "authenticated")
        self.assertEqual(body["devices"][0]["auth_path"], "initial_admin_required")

    @patch("api.main.discover_axis_devices")
    def test_post_network_scan_invalid_cidr_returns_400(self, discover_axis_devices):
        discover_axis_devices.return_value = {
            "scan_target": None,
            "interface_options": [],
            "devices": [],
            "errors": ["CIDR 'bad-cidr' is not a valid IPv4 network."],
        }

        response = self.client.post(
            "/api/network-scan",
            json={"interface_name": "eth0", "cidr": "bad-cidr"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("bad-cidr", response.text)

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.setup_scanned_camera")
    def test_post_network_scan_onboard_ready(self, setup_scanned_camera, read_one_camera_payload):
        setup_scanned_camera.return_value = {
            "ok": True,
            "status": "ready",
            "auth_path": "first_time_initialized",
            "camera": {
                "ip": "192.168.1.40",
                "port": 443,
                "scheme": "https",
                "username": "root",
                "password": "new-password",
            },
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.40",
            "name": "axis-new",
            "connection": {
                "ip": "192.168.1.40",
                "port": 443,
                "scheme": "https",
                "username": "root",
                "password": "new-password",
            },
            "summary": {"model": "AXIS M3215-LVE"},
        }

        response = self.client.post(
            "/api/network-scan/onboard",
            json={
                "devices": [
                    {
                        "ip": "192.168.1.40",
                        "hostname": "axis-new",
                        "http_port": 80,
                        "https_port": 443,
                        "discovery_sources": ["tcp:80"],
                        "confidence": "confirmed",
                        "auth_status": "authenticated",
                        "auth_path": "initial_admin_required",
                    }
                ],
                "new_root_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"][0]["status"], "ready")
        self.assertTrue(body["results"][0]["setup_verified"])
        self.assertIn("verified", body["results"][0]["setup_message"].lower())
        self.assertEqual(body["results"][0]["auth_path"], "first_time_initialized")
        self.assertEqual(body["results"][0]["connection"]["password"], "new-password")

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.setup_scanned_camera")
    def test_post_network_scan_onboard_existing_credentials_success(
        self,
        setup_scanned_camera,
        read_one_camera_payload,
    ):
        setup_scanned_camera.return_value = {
            "ok": True,
            "status": "ready",
            "auth_path": "existing_credentials_authenticated",
            "camera": {
                "ip": "192.168.1.41",
                "port": 80,
                "scheme": "http",
                "username": "root",
                "password": "KnownPassword1!",
            },
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.41",
            "name": "axis-configured",
            "connection": {
                "ip": "192.168.1.41",
                "port": 80,
                "scheme": "http",
                "username": "root",
                "password": "KnownPassword1!",
            },
            "summary": {"model": "AXIS configured"},
        }

        response = self.client.post(
            "/api/network-scan/onboard",
            json={
                "devices": [
                    {
                        "ip": "192.168.1.41",
                        "hostname": "axis-configured",
                        "http_port": 80,
                        "discovery_sources": ["tcp:80"],
                        "confidence": "confirmed",
                        "auth_status": "unauthenticated",
                        "auth_path": "existing_credentials_required",
                        "username": "root",
                        "password": "KnownPassword1!",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"][0]["status"], "ready")
        self.assertTrue(body["results"][0]["setup_verified"])
        self.assertEqual(body["results"][0]["auth_path"], "existing_credentials_authenticated")

    @patch("api.main.setup_scanned_camera")
    def test_post_network_scan_onboard_needs_credentials(self, setup_scanned_camera):
        setup_scanned_camera.return_value = {
            "ok": False,
            "status": "needs_credentials",
            "auth_path": "existing_credentials_required",
            "errors": ["Enter the existing credentials for this camera to continue."],
        }

        response = self.client.post(
            "/api/network-scan/onboard",
            json={
                "devices": [
                    {
                        "ip": "192.168.1.41",
                        "hostname": "axis-configured",
                        "http_port": 80,
                        "discovery_sources": ["tcp:80"],
                        "confidence": "confirmed",
                        "auth_status": "unauthenticated",
                        "auth_path": "existing_credentials_required",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"][0]["status"], "needs_credentials")
        self.assertFalse(body["results"][0]["setup_verified"])
        self.assertEqual(body["results"][0]["connection"]["username"], "root")

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.setup_scanned_camera")
    def test_post_network_scan_onboard_marks_verification_failure(
        self,
        setup_scanned_camera,
        read_one_camera_payload,
    ):
        setup_scanned_camera.return_value = {
            "ok": True,
            "status": "ready",
            "auth_path": "first_time_initialized",
            "camera": {
                "ip": "192.168.1.40",
                "port": 443,
                "scheme": "https",
                "username": "root",
                "password": "new-password",
            },
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.40",
            "name": "axis-new",
            "error": "Authentication failed (wrong username or password).",
        }

        response = self.client.post(
            "/api/network-scan/onboard",
            json={
                "devices": [
                    {
                        "ip": "192.168.1.40",
                        "hostname": "axis-new",
                        "http_port": 80,
                        "https_port": 443,
                        "discovery_sources": ["tcp:80"],
                        "confidence": "confirmed",
                        "auth_status": "authenticated",
                        "auth_path": "initial_admin_required",
                    }
                ],
                "new_root_password": "new-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"][0]["status"], "verification_failed")
        self.assertFalse(body["results"][0]["setup_verified"])
        self.assertIsNone(body["results"][0]["connection"])
        self.assertEqual(body["results"][0]["auth_path"], "first_time_initialized")


if __name__ == "__main__":
    unittest.main()

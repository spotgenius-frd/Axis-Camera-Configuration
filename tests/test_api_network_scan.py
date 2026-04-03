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

    @patch("api.main.discover_axis_devices")
    def test_post_network_scan_success(self, discover_axis_devices):
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

        response = self.client.post(
            "/api/network-scan",
            json={"interface_name": "eth0", "cidr": "192.168.1.0/24"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["devices"]), 1)
        self.assertEqual(body["devices"][0]["model"], "AXIS M3215-LVE")

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


if __name__ == "__main__":
    unittest.main()

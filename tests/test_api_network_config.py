import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from api.main import app
except Exception:  # pragma: no cover - depends on optional api requirements
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi test dependencies are not installed")
class NetworkConfigApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main._read_one_camera_payload")
    @patch("api.main.apply_network_config_update")
    def test_post_network_config_success(self, apply_network_config_update, read_one_camera_payload):
        apply_network_config_update.return_value = {
            "ok": True,
            "errors": [],
            "previous_ip": "192.168.1.221",
            "target_ip": "192.168.1.230",
            "reachable": True,
            "elapsed_seconds": 4.5,
            "poll_attempts": 3,
        }
        read_one_camera_payload.return_value = {
            "camera_ip": "192.168.1.230",
            "name": None,
            "connection": {
                "ip": "192.168.1.230",
                "username": "root",
                "password": "pw",
            },
            "summary": {"model": "AXIS Q1786-LE Network Camera"},
        }
        response = self.client.post(
            "/api/network-config",
            json={
                "camera": {
                    "ip": "192.168.1.221",
                    "username": "root",
                    "password": "pw",
                },
                "ipv4_mode": "static",
                "ip_address": "192.168.1.230",
                "subnet_mask": "255.255.255.0",
                "gateway": "192.168.1.1",
                "dns_servers": ["8.8.8.8"],
                "use_dhcp_hostname": False,
                "hostname": "axis-parking-01",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["target_ip"], "192.168.1.230")
        self.assertEqual(body["result"]["camera_ip"], "192.168.1.230")

    @patch("api.main.apply_network_config_update")
    def test_post_network_config_validation_error_shape(self, apply_network_config_update):
        apply_network_config_update.return_value = {
            "ok": False,
            "errors": ["Static mode requires an IP address."],
            "previous_ip": "192.168.1.221",
            "target_ip": "192.168.1.221",
            "reachable": None,
            "elapsed_seconds": 0.0,
            "poll_attempts": 0,
        }
        response = self.client.post(
            "/api/network-config",
            json={
                "camera": {
                    "ip": "192.168.1.221",
                    "username": "root",
                    "password": "pw",
                },
                "ipv4_mode": "static",
                "dns_servers": [],
                "use_dhcp_hostname": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"], ["Static mode requires an IP address."])
        self.assertIsNone(body["result"])


if __name__ == "__main__":
    unittest.main()

import io
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from api.main import app
except Exception:  # pragma: no cover
    TestClient = None
    app = None


PARAM_GROUPS = ["Image", "ImageSource", "Network", "Storage", "Properties.System"]


def _payload_with_group_errors(error_message: str) -> dict:
    return {
        "camera_ip": "192.168.1.211",
        "device_info": {"data": {"propertyList": {}}},
        "params": {group: {"_error": error_message} for group in PARAM_GROUPS},
        "stream_profiles": None,
        "stream_status": None,
        "time_info": None,
        "summary": {
            "model": None,
            "firmware": None,
            "image": {},
            "stream": [],
            "overlay": {},
            "overlay_active": False,
            "sd_card": "unknown",
        },
        "time_zone_options": [],
        "stream_profiles_structured": [],
        "option_catalog": {},
        "web_settings_catalog": {},
        "capabilities": None,
        "network_summary": None,
        "network_config": None,
        "dynamic_overlays": None,
    }


@unittest.skipIf(TestClient is None or app is None, "fastapi test dependencies are not installed")
class ReadConfigApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main.get_latest_firmware")
    @patch("api.main.read_camera_config")
    def test_post_read_config_marks_unverified_host_as_failed(self, read_camera_config, get_latest_firmware):
        get_latest_firmware.return_value = None
        read_camera_config.return_value = _payload_with_group_errors("404 Client Error: Not Found")

        response = self.client.post(
            "/api/read-config",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.211",
                        "username": "root",
                        "password": "bad-password",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(
            result["error"],
            "This host did not respond like a supported Axis camera. Check the IP and credentials.",
        )
        self.assertIsNone(result["summary"]["model"])

    @patch("api.main.get_latest_firmware")
    @patch("api.main.read_camera_config")
    def test_post_read_config_keeps_verified_axis_read_ready(self, read_camera_config, get_latest_firmware):
        get_latest_firmware.return_value = {"version": "11.11.192"}
        read_camera_config.return_value = {
            "camera_ip": "192.168.1.240",
            "device_info": {
                "data": {
                    "propertyList": {
                        "Brand": "AXIS",
                        "ProdFullName": "AXIS Q1786-LE Network Camera",
                        "Version": "11.10.61",
                    }
                }
            },
            "params": {
                "Image": {"root.Image.I0.Appearance.Resolution": "1920x1080"},
                "ImageSource": {"_error": "401 Client Error: Unauthorized"},
                "Network": {"_error": "401 Client Error: Unauthorized"},
                "Storage": {"_error": "401 Client Error: Unauthorized"},
                "Properties.System": {"_error": "401 Client Error: Unauthorized"},
            },
            "stream_profiles": None,
            "stream_status": None,
            "time_info": None,
            "summary": {
                "model": "AXIS Q1786-LE Network Camera",
                "firmware": "11.10.61",
                "image": {"resolution": "1920x1080"},
                "stream": [],
                "overlay": {},
                "overlay_active": False,
                "sd_card": "unknown",
            },
            "time_zone_options": [],
            "stream_profiles_structured": [],
            "option_catalog": {},
            "web_settings_catalog": {},
            "capabilities": None,
            "network_summary": None,
            "network_config": None,
            "dynamic_overlays": None,
        }

        response = self.client.post(
            "/api/read-config",
            json={
                "cameras": [
                    {
                        "ip": "192.168.1.240",
                        "username": "root",
                        "password": "KnownPassword1!",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["summary"]["model"], "AXIS Q1786-LE Network Camera")

    @patch("api.main.get_latest_firmware")
    @patch("api.main.read_camera_config")
    def test_post_read_config_upload_marks_invalid_target_as_failed(self, read_camera_config, get_latest_firmware):
        get_latest_firmware.return_value = None
        read_camera_config.return_value = _payload_with_group_errors(
            "HTTPConnectionPool(host='192.168.1.250', port=80): Max retries exceeded"
        )

        response = self.client.post(
            "/api/read-config/upload",
            files={"file": ("cameras.csv", io.BytesIO(b"ip,password\n192.168.1.250,wrong\n"), "text/csv")},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(
            result["error"],
            "Camera could not be reached. Check the IP, port, and HTTP/HTTPS setting.",
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from api.main import app
except Exception:  # pragma: no cover
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi test dependencies are not installed")
class CameraPreviewApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main.make_client")
    def test_camera_preview_returns_image_bytes_for_authenticated_camera(self, make_client):
        fake_client = make_client.return_value
        fake_client.snapshot_image.return_value = (b"\xff\xd8jpeg", "image/jpeg")

        response = self.client.post(
            "/api/camera-preview",
            json={
                "camera": {
                    "ip": "192.168.1.240",
                    "port": 80,
                    "scheme": "http",
                    "username": "root",
                    "password": "KnownPassword1!",
                },
                "resolution": "320x180",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.content, b"\xff\xd8jpeg")
        fake_client.snapshot_image.assert_called_once_with(resolution="320x180")

    @patch("api.main.make_client")
    def test_camera_preview_uses_legacy_default_credentials_for_scan_row(self, make_client):
        fake_client = make_client.return_value
        fake_client.snapshot_image.return_value = (b"\xff\xd8jpeg", "image/jpeg")

        response = self.client.post(
            "/api/camera-preview",
            json={
                "scanned_device": {
                    "ip": "192.168.1.240",
                    "http_port": 80,
                    "https_port": 443,
                    "auth_status": "authenticated",
                    "auth_path": "legacy_root_pass",
                    "discovery_sources": ["tcp:80"],
                    "confidence": "confirmed",
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        args = make_client.call_args.args[0]
        self.assertEqual(args["username"], "root")
        self.assertEqual(args["password"], "pass")
        self.assertEqual(args["scheme"], "https")
        self.assertEqual(args["port"], 443)

    def test_camera_preview_requires_auth_for_unauthenticated_scan_row(self):
        response = self.client.post(
            "/api/camera-preview",
            json={
                "scanned_device": {
                    "ip": "192.168.1.240",
                    "http_port": 80,
                    "auth_status": "unauthenticated",
                    "auth_path": "existing_credentials_required",
                    "discovery_sources": ["tcp:80"],
                    "confidence": "confirmed",
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("authentication/setup", response.text)


if __name__ == "__main__":
    unittest.main()

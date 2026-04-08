import unittest

from axis_bulk_config.read_config import _detect_auth_error, _detect_read_error


class ReadAuthDetectionTest(unittest.TestCase):
    def test_detect_auth_error_when_only_unauthenticated_device_info_is_available(self):
        out = {
            "device_info": {
                "data": {
                    "propertyList": {
                        "ProdFullName": "AXIS M3215-LVE Network Camera",
                        "Version": "11.11.192",
                    }
                }
            },
            "params": {
                "Image": {"_error": "401 Client Error: Unauthorized"},
                "ImageSource": {"_error": "401 Client Error: Unauthorized"},
                "Network": {"_error": "401 Client Error: Unauthorized"},
                "Storage": {"_error": "401 Client Error: Unauthorized"},
                "Properties.System": {"_error": "401 Client Error: Unauthorized"},
            },
            "stream_profiles_error": "401 Client Error: Unauthorized",
            "time_info_error": "401 Client Error: Unauthorized",
            "network_info_error": "401 Client Error: Unauthorized",
        }
        self.assertEqual(
            _detect_auth_error(out),
            "Authentication failed (wrong username or password).",
        )

    def test_does_not_flag_auth_error_when_one_authenticated_read_succeeds(self):
        out = {
            "device_info": {"data": {"propertyList": {"ProdFullName": "Axis"}}},
            "params": {
                "Image": {"root.Image.I0.Appearance.Resolution": "1920x1080"},
                "ImageSource": {"_error": "401 Client Error: Unauthorized"},
                "Network": {"_error": "401 Client Error: Unauthorized"},
                "Storage": {"_error": "401 Client Error: Unauthorized"},
                "Properties.System": {"_error": "401 Client Error: Unauthorized"},
            },
            "network_info_error": "401 Client Error: Unauthorized",
        }
        self.assertIsNone(_detect_auth_error(out))

    def test_detect_read_error_for_unreachable_camera(self):
        out = {
            "device_info_error": (
                "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded "
                "with url: /axis-cgi/basicdeviceinfo.cgi (Caused by NewConnectionError)"
            ),
            "params": {
                "Image": {"_error": "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded"},
                "ImageSource": {"_error": "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded"},
                "Network": {"_error": "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded"},
                "Storage": {"_error": "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded"},
                "Properties.System": {"_error": "HTTPConnectionPool(host='192.168.1.211', port=80): Max retries exceeded"},
            },
        }

        self.assertEqual(
            _detect_read_error(out),
            "Camera could not be reached. Check the IP, port, and HTTP/HTTPS setting.",
        )

    def test_detect_read_error_for_non_axis_response(self):
        out = {
            "device_info": {"data": {"propertyList": {}}},
            "params": {
                "Image": {"_error": "404 Client Error: Not Found"},
                "ImageSource": {"_error": "404 Client Error: Not Found"},
                "Network": {"_error": "404 Client Error: Not Found"},
                "Storage": {"_error": "404 Client Error: Not Found"},
                "Properties.System": {"_error": "404 Client Error: Not Found"},
            },
            "stream_profiles_error": "404 Client Error: Not Found",
        }

        self.assertEqual(
            _detect_read_error(out),
            "This host did not respond like a supported Axis camera. Check the IP and credentials.",
        )

    def test_detect_read_error_for_partial_axis_read_without_authenticated_success(self):
        out = {
            "device_info": {
                "data": {
                    "propertyList": {
                        "Brand": "AXIS",
                        "ProdFullName": "AXIS Q1786-LE Network Camera",
                    }
                }
            },
            "params": {
                "Image": {"_error": "500 Server Error: Internal Server Error"},
                "ImageSource": {"_error": "500 Server Error: Internal Server Error"},
                "Network": {"_error": "500 Server Error: Internal Server Error"},
                "Storage": {"_error": "500 Server Error: Internal Server Error"},
                "Properties.System": {"_error": "500 Server Error: Internal Server Error"},
            },
            "stream_profiles_error": "500 Server Error: Internal Server Error",
        }

        self.assertEqual(
            _detect_read_error(out),
            "The camera did not complete an authenticated read. Check the credentials and try again.",
        )

    def test_detect_read_error_is_none_for_verified_axis_read(self):
        out = {
            "device_info": {
                "data": {
                    "propertyList": {
                        "Brand": "AXIS",
                        "ProdFullName": "AXIS M3215-LVE Network Camera",
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
        }

        self.assertIsNone(_detect_read_error(out))


if __name__ == "__main__":
    unittest.main()

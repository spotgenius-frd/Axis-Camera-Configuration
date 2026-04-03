import unittest

from axis_bulk_config.read_config import _detect_auth_error


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


if __name__ == "__main__":
    unittest.main()

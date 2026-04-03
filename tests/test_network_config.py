import unittest
from unittest.mock import patch

from axis_bulk_config.network_config import (
    normalize_network_config,
    poll_camera_reachable,
    prefix_length_to_subnet_mask,
    subnet_mask_to_prefix_length,
    validate_network_update,
    verify_network_update_result,
)


SAMPLE_NETWORK_INFO = {
    "apiVersion": "1.29",
    "data": {
        "system": {
            "hostname": {
                "useDhcpHostname": True,
                "hostname": "axis-b8a44f8f4867",
                "staticHostname": "axis-b8a44f8f4867",
            },
            "resolver": {
                "useDhcpResolverInfo": True,
                "nameServers": ["192.168.1.1"],
                "staticNameServers": ["75.75.75.75", "75.75.76.76"],
            },
        },
        "devices": [
            {
                "name": "eth0",
                "type": "wired",
                "state": "up",
                "macAddress": "b8:a4:4f:8f:48:67",
                "IPv4": {
                    "enabled": True,
                    "configurationMode": "dhcp",
                    "linkLocalMode": "on",
                    "addresses": [
                        {
                            "address": "169.254.237.81",
                            "prefixLength": 16,
                            "origin": "linkLocal",
                            "scope": "link",
                        },
                        {
                            "address": "192.168.1.221",
                            "prefixLength": 24,
                            "origin": "dhcp",
                            "scope": "global",
                            "broadcast": "192.168.1.255",
                        },
                    ],
                    "staticAddressConfigurations": [
                        {
                            "address": "192.168.1.221",
                            "prefixLength": 24,
                            "broadcast": "192.168.1.255",
                        }
                    ],
                    "defaultRouter": "192.168.1.1",
                    "staticDefaultRouter": "192.168.1.1",
                    "useStaticDHCPFallback": True,
                },
            }
        ],
    },
}


class NetworkConfigHelpersTest(unittest.TestCase):
    def test_subnet_mask_round_trip(self):
        self.assertEqual(subnet_mask_to_prefix_length("255.255.255.0"), 24)
        self.assertEqual(prefix_length_to_subnet_mask(24), "255.255.255.0")

    def test_normalize_network_config_uses_global_ipv4_address(self):
        config = normalize_network_config(SAMPLE_NETWORK_INFO)
        self.assertIsNotNone(config)
        self.assertEqual(config["interface_name"], "eth0")
        self.assertEqual(config["ipv4_mode"], "dhcp")
        self.assertEqual(config["ip_address"], "192.168.1.221")
        self.assertEqual(config["subnet_mask"], "255.255.255.0")
        self.assertEqual(config["gateway"], "192.168.1.1")
        self.assertEqual(config["dns_servers"], ["192.168.1.1"])
        self.assertTrue(config["use_dhcp_hostname"])
        self.assertEqual(config["ipv4_addresses"][1]["address"], "192.168.1.221")
        self.assertEqual(config["additional_ipv4_addresses"], [])

    def test_verify_network_update_result_flags_extra_ipv4_address(self):
        duplicated = {
            **SAMPLE_NETWORK_INFO,
            "data": {
                **SAMPLE_NETWORK_INFO["data"],
                "system": {
                    **SAMPLE_NETWORK_INFO["data"]["system"],
                    "hostname": {
                        "useDhcpHostname": False,
                        "hostname": "axis-test",
                        "staticHostname": "axis-test",
                    },
                    "resolver": {
                        **SAMPLE_NETWORK_INFO["data"]["system"]["resolver"],
                        "useDhcpResolverInfo": False,
                        "nameServers": ["192.168.1.1"],
                    },
                },
                "devices": [
                    {
                        **SAMPLE_NETWORK_INFO["data"]["devices"][0],
                        "IPv4": {
                            **SAMPLE_NETWORK_INFO["data"]["devices"][0]["IPv4"],
                            "configurationMode": "static",
                            "addresses": [
                                {
                                    "address": "169.254.237.81",
                                    "prefixLength": 16,
                                    "origin": "linkLocal",
                                    "scope": "link",
                                },
                                {
                                    "address": "192.168.1.221",
                                    "prefixLength": 24,
                                    "origin": "static",
                                    "scope": "nowhere",
                                },
                                {
                                    "address": "192.168.1.240",
                                    "prefixLength": 24,
                                    "origin": "static",
                                    "scope": "global",
                                },
                            ],
                            "staticAddressConfigurations": [
                                {
                                    "address": "192.168.1.240",
                                    "prefixLength": 24,
                                }
                            ],
                            "useStaticDHCPFallback": False,
                        },
                    }
                ],
            },
        }
        errors = verify_network_update_result(
            duplicated,
            ipv4_mode="static",
            ip_address="192.168.1.240",
            subnet_mask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["192.168.1.1"],
            use_dhcp_hostname=False,
            hostname="axis-test",
        )
        self.assertIn("Camera still reports additional IPv4 address(es): 192.168.1.221.", errors)

    def test_validate_network_update_requires_static_fields(self):
        errors = validate_network_update(
            ipv4_mode="static",
            ip_address="",
            subnet_mask="255.255.255.0",
            gateway="",
            dns_servers=[],
            use_dhcp_hostname=False,
            hostname="bad host!",
        )
        self.assertIn("Static mode requires an IP address.", errors)
        self.assertIn("Static mode requires a gateway IPv4 address.", errors)
        self.assertIn("Static mode requires at least one DNS server.", errors)
        self.assertIn("Hostname must be a valid DNS hostname.", errors)

    @patch("axis_bulk_config.network_config.time.sleep", return_value=None)
    @patch("axis_bulk_config.network_config.AxisCameraClient")
    def test_poll_camera_reachable_returns_success(self, client_cls, _sleep):
        client = client_cls.return_value
        client.network_settings_get_info.return_value = SAMPLE_NETWORK_INFO
        result = poll_camera_reachable(
            target_ip="192.168.1.221",
            username="root",
            password="secret",
            expected_mac_address="b8:a4:4f:8f:48:67",
            timeout_seconds=0.05,
            poll_interval_seconds=0.01,
        )
        self.assertTrue(result["reachable"])
        self.assertGreaterEqual(result["poll_attempts"], 1)
        self.assertEqual(result["network_config"]["ip_address"], "192.168.1.221")

    @patch("axis_bulk_config.network_config.time.sleep", return_value=None)
    @patch("axis_bulk_config.network_config.AxisCameraClient")
    def test_poll_camera_reachable_times_out_on_mac_mismatch(self, client_cls, _sleep):
        mismatched = {
            **SAMPLE_NETWORK_INFO,
            "data": {
                **SAMPLE_NETWORK_INFO["data"],
                "devices": [
                    {
                        **SAMPLE_NETWORK_INFO["data"]["devices"][0],
                        "macAddress": "00:11:22:33:44:55",
                    }
                ],
            },
        }
        client = client_cls.return_value
        client.network_settings_get_info.return_value = mismatched
        result = poll_camera_reachable(
            target_ip="192.168.1.221",
            username="root",
            password="secret",
            expected_mac_address="b8:a4:4f:8f:48:67",
            timeout_seconds=0.03,
            poll_interval_seconds=0.01,
        )
        self.assertFalse(result["reachable"])
        self.assertIn("expected b8:a4:4f:8f:48:67", result["last_error"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from axis_bulk_config.write_service import apply_network_config_update


SAMPLE_NETWORK_INFO = {
    "apiVersion": "1.29",
    "data": {
        "system": {
            "resolver": {
                "useDhcpResolverInfo": True,
                "nameServers": ["192.168.1.1"],
                "staticNameServers": ["75.75.75.75", "75.75.76.76"],
                "staticSearchDomains": [],
                "staticDomainName": "",
            },
            "hostname": {
                "useDhcpHostname": True,
                "hostname": "axis-b8a44f8f4867",
                "staticHostname": "axis-b8a44f8f4867",
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
                            "address": "192.168.1.221",
                            "prefixLength": 24,
                            "origin": "dhcp",
                            "scope": "global",
                            "broadcast": "192.168.1.255",
                        }
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
                    "useDHCPStaticRoutes": False,
                },
            }
        ],
    },
}


class RecordingClient:
    def __init__(self):
        self.calls = []

    def network_settings_get_info(self):
        return SAMPLE_NETWORK_INFO

    def network_settings_set_hostname_configuration(self, **kwargs):
        self.calls.append(("hostname", kwargs))
        return {"data": {}}

    def network_settings_set_resolver_configuration(self, **kwargs):
        self.calls.append(("resolver", kwargs))
        return {"data": {}}

    def network_settings_set_ipv4_address_configuration(self, **kwargs):
        self.calls.append(("ipv4", kwargs))
        return {"data": {}}


class ApplyNetworkConfigUpdateTest(unittest.TestCase):
    def test_validation_failure_returns_structured_error(self):
        result = apply_network_config_update(
            {"ip": "192.168.1.221", "username": "root", "password": "pw"},
            ipv4_mode="static",
            ip_address="",
            subnet_mask="255.255.255.0",
            gateway="",
            dns_servers=[],
            use_dhcp_hostname=False,
            hostname="bad host!",
        )
        self.assertFalse(result["ok"])
        self.assertIn("Static mode requires an IP address.", result["errors"])

    @patch("axis_bulk_config.write_service.poll_camera_reachable")
    @patch("axis_bulk_config.write_service.make_client")
    def test_static_payload_generation(self, make_client, poll_camera_reachable):
        client = RecordingClient()
        make_client.return_value = client
        poll_camera_reachable.return_value = {
            "reachable": True,
            "elapsed_seconds": 4.2,
            "poll_attempts": 3,
            "network_info": {
                **SAMPLE_NETWORK_INFO,
                "data": {
                    **SAMPLE_NETWORK_INFO["data"],
                    "system": {
                        **SAMPLE_NETWORK_INFO["data"]["system"],
                        "resolver": {
                            **SAMPLE_NETWORK_INFO["data"]["system"]["resolver"],
                            "useDhcpResolverInfo": False,
                            "nameServers": ["8.8.8.8", "8.8.4.4"],
                            "staticNameServers": ["8.8.8.8", "8.8.4.4"],
                        },
                        "hostname": {
                            "useDhcpHostname": False,
                            "hostname": "axis-parking-01",
                            "staticHostname": "axis-parking-01",
                        },
                    },
                    "devices": [
                        {
                            **SAMPLE_NETWORK_INFO["data"]["devices"][0],
                            "IPv4": {
                                **SAMPLE_NETWORK_INFO["data"]["devices"][0]["IPv4"],
                                "configurationMode": "static",
                                "useStaticDHCPFallback": False,
                                "addresses": [
                                    {
                                        "address": "192.168.1.230",
                                        "prefixLength": 24,
                                        "origin": "static",
                                        "scope": "global",
                                    }
                                ],
                                "staticAddressConfigurations": [
                                    {
                                        "address": "192.168.1.230",
                                        "prefixLength": 24,
                                    }
                                ],
                            },
                        }
                    ],
                },
            },
        }
        result = apply_network_config_update(
            {"ip": "192.168.1.221", "username": "root", "password": "pw"},
            ipv4_mode="static",
            ip_address="192.168.1.230",
            subnet_mask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            use_dhcp_hostname=False,
            hostname="axis-parking-01",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["target_ip"], "192.168.1.230")
        hostname_call = client.calls[0]
        resolver_call = client.calls[1]
        ipv4_call = client.calls[2]
        self.assertEqual(hostname_call[0], "hostname")
        self.assertEqual(hostname_call[1]["use_dhcp_hostname"], False)
        self.assertEqual(hostname_call[1]["static_hostname"], "axis-parking-01")
        self.assertEqual(resolver_call[0], "resolver")
        self.assertEqual(resolver_call[1]["use_dhcp_resolver_info"], False)
        self.assertEqual(resolver_call[1]["static_name_servers"], ["8.8.8.8", "8.8.4.4"])
        self.assertEqual(ipv4_call[0], "ipv4")
        self.assertEqual(ipv4_call[1]["configuration_mode"], "static")
        self.assertEqual(ipv4_call[1]["static_default_router"], "192.168.1.1")
        self.assertEqual(
            ipv4_call[1]["static_address_configurations"][0]["address"],
            "192.168.1.230",
        )
        self.assertEqual(
            ipv4_call[1]["static_address_configurations"][0]["prefixLength"],
            24,
        )
        self.assertNotIn("broadcast", ipv4_call[1]["static_address_configurations"][0])

    @patch("axis_bulk_config.write_service.poll_camera_reachable")
    @patch("axis_bulk_config.write_service.make_client")
    def test_dhcp_payload_generation_preserves_fallback(self, make_client, poll_camera_reachable):
        client = RecordingClient()
        make_client.return_value = client
        poll_camera_reachable.return_value = {
            "reachable": True,
            "elapsed_seconds": 2.0,
            "poll_attempts": 2,
            "network_info": SAMPLE_NETWORK_INFO,
        }
        result = apply_network_config_update(
            {"ip": "192.168.1.221", "username": "root", "password": "pw"},
            ipv4_mode="dhcp",
            ip_address=None,
            subnet_mask=None,
            gateway=None,
            dns_servers=[],
            use_dhcp_hostname=True,
            hostname=None,
        )
        self.assertTrue(result["ok"])
        resolver_call = client.calls[1]
        ipv4_call = client.calls[2]
        self.assertEqual(resolver_call[1]["use_dhcp_resolver_info"], True)
        self.assertEqual(ipv4_call[1]["configuration_mode"], "dhcp")
        self.assertTrue(ipv4_call[1]["use_static_dhcp_fallback"])
        self.assertEqual(ipv4_call[1]["static_default_router"], "192.168.1.1")

    @patch("axis_bulk_config.write_service.poll_camera_reachable")
    @patch("axis_bulk_config.write_service.make_client")
    def test_timeout_path_surfaces_poll_error(self, make_client, poll_camera_reachable):
        client = RecordingClient()
        make_client.return_value = client
        poll_camera_reachable.return_value = {
            "reachable": False,
            "elapsed_seconds": 90.0,
            "poll_attempts": 45,
            "last_error": "timed out",
        }
        result = apply_network_config_update(
            {"ip": "192.168.1.221", "username": "root", "password": "pw"},
            ipv4_mode="static",
            ip_address="192.168.1.221",
            subnet_mask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["8.8.8.8"],
            use_dhcp_hostname=True,
            hostname=None,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], ["timed out"])
        self.assertEqual(result["poll_attempts"], 45)

    @patch("axis_bulk_config.write_service.poll_camera_reachable")
    @patch("axis_bulk_config.write_service.make_client")
    def test_reachable_camera_can_still_fail_verification(self, make_client, poll_camera_reachable):
        client = RecordingClient()
        make_client.return_value = client
        poll_camera_reachable.return_value = {
            "reachable": True,
            "elapsed_seconds": 5.0,
            "poll_attempts": 4,
            "network_info": {
                **SAMPLE_NETWORK_INFO,
                "data": {
                    **SAMPLE_NETWORK_INFO["data"],
                    "system": {
                        **SAMPLE_NETWORK_INFO["data"]["system"],
                        "resolver": {
                            **SAMPLE_NETWORK_INFO["data"]["system"]["resolver"],
                            "useDhcpResolverInfo": False,
                            "nameServers": ["192.168.1.1"],
                        },
                        "hostname": {
                            "useDhcpHostname": False,
                            "hostname": "axis-test",
                            "staticHostname": "axis-test",
                        },
                    },
                    "devices": [
                        {
                            **SAMPLE_NETWORK_INFO["data"]["devices"][0],
                            "IPv4": {
                                **SAMPLE_NETWORK_INFO["data"]["devices"][0]["IPv4"],
                                "configurationMode": "static",
                                "useStaticDHCPFallback": False,
                                "addresses": [
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
                            },
                        }
                    ],
                },
            },
        }
        result = apply_network_config_update(
            {"ip": "192.168.1.221", "username": "root", "password": "pw"},
            ipv4_mode="static",
            ip_address="192.168.1.240",
            subnet_mask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["192.168.1.1"],
            use_dhcp_hostname=False,
            hostname="axis-test",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["reachable"])
        self.assertEqual(result["reachable_ip"], "192.168.1.240")
        self.assertIn("additional IPv4 address(es): 192.168.1.221.", result["errors"][0])


if __name__ == "__main__":
    unittest.main()

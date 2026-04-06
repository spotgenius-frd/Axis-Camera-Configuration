import unittest
import types
from unittest.mock import patch

from axis_bulk_config.network_scan import (
    dedupe_devices,
    discover_axis_devices,
    list_interface_options,
    resolve_scan_target,
)


class _FakeIp:
    def __init__(self, ip, network_prefix):
        self.ip = ip
        self.network_prefix = network_prefix


class _FakeAdapter:
    def __init__(self, name, nice_name, ips):
        self.name = name
        self.nice_name = nice_name
        self.ips = ips


class NetworkScanTest(unittest.TestCase):
    def test_list_interface_options_filters_loopback_and_sorts_private_interfaces_first(self):
        fake_ifaddr = types.SimpleNamespace(
            get_adapters=lambda: [
                _FakeAdapter("lo0", "lo0", [_FakeIp("127.0.0.1", 8)]),
                _FakeAdapter("utun3", "utun3", [_FakeIp("10.20.30.40", 24)]),
                _FakeAdapter("eth0", "eth0", [_FakeIp("192.168.1.15", 24)]),
            ]
        )

        with patch.dict("sys.modules", {"ifaddr": fake_ifaddr}):
            options = list_interface_options()

        self.assertEqual(len(options), 2)
        self.assertEqual(options[0]["name"], "eth0")
        self.assertEqual(options[0]["suggested_cidr"], "192.168.1.0/24")
        self.assertEqual(options[1]["name"], "utun3")

    def test_resolve_scan_target_defaults_to_first_interface_and_validates_cidr(self):
        options = [
            {
                "name": "eth0",
                "display_name": "eth0",
                "ip_address": "192.168.1.15",
                "network_cidr": "192.168.1.0/24",
                "suggested_cidr": "192.168.1.0/24",
                "is_private": True,
                "rank": 30,
            }
        ]

        target, errors = resolve_scan_target(options)
        self.assertEqual(errors, [])
        self.assertEqual(target["cidr"], "192.168.1.0/24")

        target, errors = resolve_scan_target(options, cidr="bad-cidr")
        self.assertIsNone(target)
        self.assertEqual(errors, ["CIDR 'bad-cidr' is not a valid IPv4 network."])

    def test_dedupe_devices_merges_by_serial_mac_and_ip(self):
        devices = [
            {
                "ip": "192.168.1.10",
                "serial": "ABC123",
                "mac": None,
                "model": "AXIS One",
                "firmware": None,
                "hostname": "axis-one",
                "http_port": 80,
                "https_port": None,
                "confidence": "probable",
                "discovery_sources": {"mdns:vapix-http"},
            },
            {
                "ip": "192.168.1.20",
                "serial": "ABC123",
                "mac": "AA:BB:CC:DD:EE:FF",
                "model": None,
                "firmware": "11.11.192",
                "hostname": None,
                "http_port": 80,
                "https_port": 443,
                "confidence": "confirmed",
                "discovery_sources": {"bdi:http"},
            },
        ]

        deduped = dedupe_devices(devices)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["confidence"], "confirmed")
        self.assertEqual(deduped[0]["firmware"], "11.11.192")
        self.assertIn("mdns:vapix-http", deduped[0]["discovery_sources"])
        self.assertIn("bdi:http", deduped[0]["discovery_sources"])

    @patch("axis_bulk_config.network_scan.probe_basic_device_info")
    @patch("axis_bulk_config.network_scan.sweep_candidate_ports")
    @patch("axis_bulk_config.network_scan.browse_mdns_candidates")
    @patch("axis_bulk_config.network_scan.list_interface_options")
    def test_discover_axis_devices_returns_confirmed_and_probable_results(
        self,
        list_interface_options_mock,
        browse_mdns_candidates,
        sweep_candidate_ports,
        probe_basic_device_info,
    ):
        list_interface_options_mock.return_value = [
            {
                "name": "eth0",
                "display_name": "eth0",
                "ip_address": "192.168.1.15",
                "network_cidr": "192.168.1.0/24",
                "suggested_cidr": "192.168.1.0/24",
                "is_private": True,
                "rank": 40,
            }
        ]
        browse_mdns_candidates.return_value = [
            {
                "ip": "192.168.1.30",
                "mac": None,
                "model": None,
                "serial": "MDNS123",
                "firmware": None,
                "hostname": "axis-mdns",
                "http_port": 80,
                "https_port": None,
                "confidence": "probable",
                "discovery_sources": {"mdns:vapix-http"},
            }
        ]
        sweep_candidate_ports.return_value = {
            "192.168.1.30": {80},
            "192.168.1.40": {80},
            "192.168.1.50": {80},
        }

        def _probe(ip_address, http_port, https_port):
            if ip_address == "192.168.1.40":
                return {
                    "brand": "AXIS",
                    "model": "AXIS M3215-LVE",
                    "serial": "CONF123",
                    "firmware": "11.11.192",
                    "mac": "B8:A4:4F:00:11:22",
                    "source": "bdi:http",
                }
            return None

        probe_basic_device_info.side_effect = _probe

        result = discover_axis_devices()

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["scan_target"]["cidr"], "192.168.1.0/24")
        self.assertEqual(len(result["devices"]), 2)
        confirmed = next(device for device in result["devices"] if device["ip"] == "192.168.1.40")
        probable = next(device for device in result["devices"] if device["ip"] == "192.168.1.30")
        self.assertEqual(confirmed["confidence"], "confirmed")
        self.assertIn("tcp:80", confirmed["discovery_sources"])
        self.assertIn("bdi:http", confirmed["discovery_sources"])
        self.assertEqual(probable["confidence"], "probable")
        self.assertEqual(probable["hostname"], "axis-mdns")
        self.assertNotIn("192.168.1.50", [device["ip"] for device in result["devices"]])

    @patch("axis_bulk_config.network_scan.list_interface_options", return_value=[])
    def test_discover_axis_devices_returns_error_when_no_interface_is_available(self, _list_interface_options):
        result = discover_axis_devices()
        self.assertIsNone(result["scan_target"])
        self.assertEqual(result["devices"], [])
        self.assertEqual(
            result["errors"],
            ["No usable non-loopback IPv4 interfaces found on this host."],
        )


if __name__ == "__main__":
    unittest.main()

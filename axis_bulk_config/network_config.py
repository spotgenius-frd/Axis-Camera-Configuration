"""Helpers for Axis network configuration read/write flows."""

from __future__ import annotations

import ipaddress
import time
from typing import Any

from axis_bulk_config.client import AxisCameraClient


def prefix_length_to_subnet_mask(prefix_length: int | None) -> str | None:
    """Convert an IPv4 prefix length to a dotted subnet mask."""
    if prefix_length is None:
        return None
    network = ipaddress.IPv4Network(f"0.0.0.0/{prefix_length}", strict=False)
    return str(network.netmask)


def subnet_mask_to_prefix_length(subnet_mask: str) -> int:
    """Convert an IPv4 subnet mask to prefix length."""
    network = ipaddress.IPv4Network(f"0.0.0.0/{subnet_mask}", strict=False)
    return int(network.prefixlen)


def is_valid_hostname(hostname: str) -> bool:
    """Return True if the hostname contains valid labels for Axis network APIs."""
    value = hostname.strip()
    if not value or len(value) > 253:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")
    if any(char not in allowed for char in value):
        return False
    labels = value.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
    return True


def _pick_primary_device(network_info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(network_info, dict):
        return None
    devices = ((network_info.get("data") or {}).get("devices") or [])
    if not isinstance(devices, list):
        return None
    wired_candidates: list[dict[str, Any]] = []
    ipv4_candidates: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        ipv4 = device.get("IPv4")
        if not isinstance(ipv4, dict) or not ipv4.get("enabled"):
            continue
        ipv4_candidates.append(device)
        if device.get("type") == "wired":
            wired_candidates.append(device)
    for pool in (wired_candidates, ipv4_candidates):
        for device in pool:
            if device.get("state") == "up":
                return device
    return wired_candidates[0] if wired_candidates else (ipv4_candidates[0] if ipv4_candidates else None)


def _extract_ipv4_addresses(ipv4: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(ipv4, dict):
        return []
    addresses = ipv4.get("addresses") or []
    if not isinstance(addresses, list):
        return []
    return [entry for entry in addresses if isinstance(entry, dict) and entry.get("address")]


def _is_non_link_local_ipv4(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return entry.get("origin") != "linkLocal" and entry.get("scope") != "link"


def _pick_active_ipv4_address(ipv4: dict[str, Any] | None) -> dict[str, Any] | None:
    addresses = _extract_ipv4_addresses(ipv4)
    global_candidates = [entry for entry in addresses if entry.get("scope") == "global"]
    if global_candidates:
        for entry in global_candidates:
            if entry.get("origin") != "linkLocal":
                return entry
        return global_candidates[0]
    non_link_local_candidates = [entry for entry in addresses if _is_non_link_local_ipv4(entry)]
    if non_link_local_candidates:
        return non_link_local_candidates[0]
    if isinstance(ipv4, dict):
        static_configs = ipv4.get("staticAddressConfigurations") or []
        if isinstance(static_configs, list):
            for entry in static_configs:
                if isinstance(entry, dict) and entry.get("address"):
                    return entry
    for entry in addresses:
        if isinstance(entry, dict):
            return entry
    return None


def _normalize_ipv4_addresses(ipv4: dict[str, Any] | None) -> list[dict[str, Any]]:
    active_address = _pick_active_ipv4_address(ipv4)
    active_key = None
    if isinstance(active_address, dict):
        active_key = (
            active_address.get("address"),
            active_address.get("prefixLength"),
            active_address.get("scope"),
            active_address.get("origin"),
        )
    entries: list[dict[str, Any]] = []
    for entry in _extract_ipv4_addresses(ipv4):
        prefix_length = entry.get("prefixLength")
        entries.append(
            {
                "address": entry.get("address"),
                "prefix_length": prefix_length,
                "subnet_mask": prefix_length_to_subnet_mask(prefix_length),
                "origin": entry.get("origin"),
                "scope": entry.get("scope"),
                "broadcast": entry.get("broadcast"),
                "is_active": (
                    (
                        entry.get("address"),
                        entry.get("prefixLength"),
                        entry.get("scope"),
                        entry.get("origin"),
                    )
                    == active_key
                ),
            }
        )
    return entries


def normalize_network_config(
    network_info: dict[str, Any] | None,
    params_network: dict[str, Any] | None = None,
    network_settings_v2: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Normalize network state into a camera-friendly object."""
    device = _pick_primary_device(network_info)
    system = ((network_info.get("data") or {}).get("system") or {}) if isinstance(network_info, dict) else {}
    resolver = system.get("resolver") if isinstance(system, dict) else {}
    hostname_data = system.get("hostname") if isinstance(system, dict) else {}
    if isinstance(device, dict):
        ipv4 = device.get("IPv4") or {}
        active_address = _pick_active_ipv4_address(ipv4)
        ipv4_addresses = _normalize_ipv4_addresses(ipv4)
        prefix_length = active_address.get("prefixLength") if isinstance(active_address, dict) else None
        dns_servers = resolver.get("nameServers") if isinstance(resolver, dict) else None
        if not dns_servers:
            dns_servers = resolver.get("staticNameServers") if isinstance(resolver, dict) else None
        return {
            "interface_name": device.get("name"),
            "mac_address": device.get("macAddress"),
            "ipv4_mode": ipv4.get("configurationMode"),
            "ip_address": active_address.get("address") if isinstance(active_address, dict) else None,
            "subnet_mask": prefix_length_to_subnet_mask(prefix_length),
            "prefix_length": prefix_length,
            "gateway": ipv4.get("defaultRouter") or ipv4.get("staticDefaultRouter"),
            "dns_servers": [str(value) for value in (dns_servers or []) if value],
            "hostname": hostname_data.get("hostname") if isinstance(hostname_data, dict) else None,
            "static_hostname": hostname_data.get("staticHostname") if isinstance(hostname_data, dict) else None,
            "use_dhcp_hostname": hostname_data.get("useDhcpHostname") if isinstance(hostname_data, dict) else None,
            "use_dhcp_resolver_info": (
                resolver.get("useDhcpResolverInfo")
                if isinstance(resolver, dict) and "useDhcpResolverInfo" in resolver
                else resolver.get("useDHCPResolverInfo") if isinstance(resolver, dict) else None
            ),
            "use_static_dhcp_fallback": ipv4.get("useStaticDHCPFallback"),
            "link_local_mode": ipv4.get("linkLocalMode"),
            "ipv4_addresses": ipv4_addresses,
            "additional_ipv4_addresses": [
                entry["address"]
                for entry in ipv4_addresses
                if entry.get("address")
                and entry.get("origin") != "linkLocal"
                and not entry.get("is_active")
            ],
        }

    params_network = params_network if isinstance(params_network, dict) else {}
    v2_system = (((network_settings_v2 or {}).get("data") or {}).get("system") or {}) if isinstance(network_settings_v2, dict) else {}
    hostname = v2_system.get("hostname") if isinstance(v2_system, dict) else None
    static_hostname = v2_system.get("staticHostname") if isinstance(v2_system, dict) else None
    use_dhcp_hostname = v2_system.get("useDhcpHostname") if isinstance(v2_system, dict) else None
    ip_address = params_network.get("root.Network.IPAddress")
    subnet_mask = params_network.get("root.Network.SubnetMask")
    gateway = params_network.get("root.Network.DefaultRouter")
    dns_servers = [
        value
        for value in [
            params_network.get("root.Network.DNSServer1"),
            params_network.get("root.Network.DNSServer2"),
        ]
        if value
    ]
    ipv4_mode = params_network.get("root.Network.BootProto")
    if ipv4_mode == "none" and ip_address:
        ipv4_mode = "static"
    return {
        "interface_name": "eth0" if ip_address else None,
        "mac_address": params_network.get("root.Network.eth0.MACAddress"),
        "ipv4_mode": ipv4_mode,
        "ip_address": ip_address,
        "subnet_mask": subnet_mask,
        "prefix_length": subnet_mask_to_prefix_length(subnet_mask) if subnet_mask else None,
        "gateway": gateway,
        "dns_servers": dns_servers,
        "hostname": hostname or params_network.get("root.Network.HostName"),
        "static_hostname": static_hostname or params_network.get("root.Network.HostName"),
        "use_dhcp_hostname": use_dhcp_hostname,
        "use_dhcp_resolver_info": None,
        "use_static_dhcp_fallback": None,
        "link_local_mode": None,
        "ipv4_addresses": (
            [
                {
                    "address": ip_address,
                    "prefix_length": subnet_mask_to_prefix_length(subnet_mask) if subnet_mask else None,
                    "subnet_mask": subnet_mask,
                    "origin": ipv4_mode,
                    "scope": "global",
                    "broadcast": None,
                    "is_active": True,
                }
            ]
            if ip_address
            else []
        ),
        "additional_ipv4_addresses": [],
    } if any([ip_address, hostname, static_hostname]) else None


def validate_network_update(
    *,
    ipv4_mode: str,
    ip_address: str | None,
    subnet_mask: str | None,
    gateway: str | None,
    dns_servers: list[str] | None,
    use_dhcp_hostname: bool,
    hostname: str | None,
) -> list[str]:
    """Validate network config request fields and return human-readable errors."""
    errors: list[str] = []
    mode = ipv4_mode.strip().lower()
    if mode not in {"dhcp", "static"}:
        errors.append("IPv4 mode must be 'dhcp' or 'static'.")
    cleaned_dns = [value.strip() for value in (dns_servers or []) if isinstance(value, str) and value.strip()]
    if mode == "static":
        if not ip_address or not ip_address.strip():
            errors.append("Static mode requires an IP address.")
        else:
            try:
                ipaddress.IPv4Address(ip_address.strip())
            except ipaddress.AddressValueError:
                errors.append("Static IP address must be a valid IPv4 address.")
        if not subnet_mask or not subnet_mask.strip():
            errors.append("Static mode requires a subnet mask.")
        else:
            try:
                subnet_mask_to_prefix_length(subnet_mask.strip())
            except ValueError:
                errors.append("Subnet mask must be a valid IPv4 subnet mask.")
        if not gateway or not gateway.strip():
            errors.append("Static mode requires a gateway IPv4 address.")
        else:
            try:
                ipaddress.IPv4Address(gateway.strip())
            except ipaddress.AddressValueError:
                errors.append("Gateway must be a valid IPv4 address.")
        if not cleaned_dns:
            errors.append("Static mode requires at least one DNS server.")
        for dns_server in cleaned_dns:
            try:
                ipaddress.IPv4Address(dns_server)
            except ipaddress.AddressValueError:
                errors.append(f"DNS server '{dns_server}' must be a valid IPv4 address.")
    if not use_dhcp_hostname:
        if not hostname or not hostname.strip():
            errors.append("Hostname is required when DHCP hostname is disabled.")
        elif not is_valid_hostname(hostname):
            errors.append("Hostname must be a valid DNS hostname.")
    return errors


def poll_camera_reachable(
    *,
    target_ip: str,
    username: str,
    password: str,
    expected_mac_address: str | None,
    port: int | None = None,
    timeout_seconds: float = 90.0,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    """Poll a camera until it is reachable and matches the expected MAC address."""
    started = time.monotonic()
    attempts = 0
    last_error: str | None = None
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            break
        attempts += 1
        try:
            base_url = f"http://{target_ip}:{port}" if port and port != 80 else f"http://{target_ip}"
            client = AxisCameraClient(base_url, username, password, timeout=min(5.0, poll_interval_seconds))
            network_info = client.network_settings_get_info()
            network_config = normalize_network_config(network_info)
            observed_mac = (network_config or {}).get("mac_address")
            if expected_mac_address:
                if observed_mac and observed_mac.lower() != expected_mac_address.lower():
                    last_error = (
                        f"Camera at {target_ip} responded with MAC {observed_mac}, "
                        f"expected {expected_mac_address}."
                    )
                else:
                    return {
                        "reachable": True,
                        "elapsed_seconds": round(elapsed, 1),
                        "poll_attempts": attempts,
                        "network_info": network_info,
                        "network_config": network_config,
                    }
            else:
                return {
                    "reachable": True,
                    "elapsed_seconds": round(elapsed, 1),
                    "poll_attempts": attempts,
                    "network_info": network_info,
                    "network_config": network_config,
                }
        except Exception as exc:  # pragma: no cover - exercised via service tests with mocks
            last_error = str(exc)
        time.sleep(poll_interval_seconds)
    return {
        "reachable": False,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "poll_attempts": attempts,
        "last_error": last_error,
    }


def verify_network_update_result(
    network_info: dict[str, Any] | None,
    *,
    ipv4_mode: str,
    ip_address: str | None,
    subnet_mask: str | None,
    gateway: str | None,
    dns_servers: list[str] | None,
    use_dhcp_hostname: bool,
    hostname: str | None,
) -> list[str]:
    """Verify that the camera's reported state matches the requested network update."""
    config = normalize_network_config(network_info)
    if not config:
        return ["Unable to verify the updated network configuration from the camera."]
    errors: list[str] = []
    requested_mode = ipv4_mode.strip().lower()
    observed_mode = str(config.get("ipv4_mode") or "").strip().lower()
    if observed_mode != requested_mode:
        errors.append(
            f"Camera reported IPv4 mode '{config.get('ipv4_mode') or 'unknown'}' after the update, expected '{requested_mode}'."
        )
    if requested_mode == "static":
        expected_ip = (ip_address or "").strip()
        expected_prefix = subnet_mask_to_prefix_length((subnet_mask or "").strip()) if subnet_mask else None
        if config.get("ip_address") != expected_ip:
            errors.append(
                f"Camera reported active IP '{config.get('ip_address') or 'unknown'}', expected '{expected_ip}'."
            )
        if expected_prefix is not None and config.get("prefix_length") != expected_prefix:
            errors.append(
                f"Camera reported subnet mask '{config.get('subnet_mask') or 'unknown'}', expected '{subnet_mask}'."
            )
        if gateway and config.get("gateway") != gateway:
            errors.append(
                f"Camera reported gateway '{config.get('gateway') or 'unknown'}', expected '{gateway}'."
            )
        requested_dns = [value.strip() for value in (dns_servers or []) if value and value.strip()]
        observed_dns = [str(value).strip() for value in (config.get("dns_servers") or []) if value]
        if requested_dns and observed_dns[: len(requested_dns)] != requested_dns:
            errors.append(
                f"Camera reported DNS servers '{', '.join(observed_dns) or 'none'}', expected '{', '.join(requested_dns)}'."
            )
        extra_addresses = [
            entry["address"]
            for entry in (config.get("ipv4_addresses") or [])
            if _is_non_link_local_ipv4(entry) and entry.get("address") != expected_ip
        ]
        if extra_addresses:
            errors.append(
                "Camera still reports additional IPv4 address(es): "
                + ", ".join(extra_addresses)
                + "."
            )
    if use_dhcp_hostname:
        if config.get("use_dhcp_hostname") is not True:
            errors.append("Camera did not keep DHCP hostname mode enabled.")
    else:
        expected_hostname = (hostname or "").strip()
        if config.get("use_dhcp_hostname") is not False:
            errors.append("Camera did not keep static hostname mode enabled.")
        if config.get("static_hostname") != expected_hostname:
            errors.append(
                f"Camera reported static hostname '{config.get('static_hostname') or 'unknown'}', expected '{expected_hostname}'."
            )
        if config.get("hostname") != expected_hostname:
            errors.append(
                f"Camera reported hostname '{config.get('hostname') or 'unknown'}', expected '{expected_hostname}'."
            )
    return errors

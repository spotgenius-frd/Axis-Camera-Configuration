"""Local-network Axis camera discovery helpers for on-site onboarding."""

from __future__ import annotations

import ipaddress
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
import urllib3


SCAN_SERVICE_TYPES = {
    "_vapix-http._tcp.local.": "vapix-http",
    "_vapix-https._tcp.local.": "vapix-https",
    "_axis-video._tcp.local.": "axis-video",
}

DEFAULT_SCAN_PORTS = (80, 443)
DEFAULT_SCAN_TIMEOUT = 0.3
DEFAULT_BDI_TIMEOUT = 1.5
DEFAULT_MDNS_SECONDS = 2.0
DEFAULT_MAX_WORKERS = 64
WIRED_HINTS = ("eth", "en", "lan", "eno", "ens", "enp", "thunderbolt", "usb")
WIRELESS_HINTS = ("wifi", "wi-fi", "wlan", "wl", "airport")
IGNORED_INTERFACE_HINTS = ("lo", "loopback", "utun", "awdl", "llw", "docker", "bridge", "veth")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _decode_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _is_private_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return isinstance(address, ipaddress.IPv4Address) and address.is_private and not address.is_loopback


def _looks_ignored_interface(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(hint) or hint in lower for hint in IGNORED_INTERFACE_HINTS)


def _interface_rank(name: str, ip_address: str) -> int:
    lower = name.lower()
    score = 0
    if _is_private_ipv4(ip_address):
        score += 30
    if any(hint in lower for hint in WIRED_HINTS):
        score += 20
    if any(hint in lower for hint in WIRELESS_HINTS):
        score -= 5
    if _looks_ignored_interface(name):
        score -= 50
    return score


def _suggested_cidr(ip_address: str) -> str:
    network = ipaddress.ip_network(f"{ip_address}/24", strict=False)
    return str(network)


def list_interface_options() -> list[dict[str, Any]]:
    """Return non-loopback IPv4 interfaces with suggested /24 scan targets."""
    import ifaddr

    options: list[dict[str, Any]] = []
    for adapter in ifaddr.get_adapters():
        for ip_info in adapter.ips:
            raw_ip = ip_info.ip
            if isinstance(raw_ip, tuple):
                continue
            ip_address = str(raw_ip).strip()
            if not ip_address or ip_address.startswith("127."):
                continue
            try:
                prefix = int(getattr(ip_info, "network_prefix", 24) or 24)
                current_cidr = str(ipaddress.ip_network(f"{ip_address}/{prefix}", strict=False))
            except Exception:
                current_cidr = _suggested_cidr(ip_address)
            options.append(
                {
                    "name": adapter.name,
                    "display_name": adapter.nice_name or adapter.name,
                    "ip_address": ip_address,
                    "network_cidr": current_cidr,
                    "suggested_cidr": _suggested_cidr(ip_address),
                    "is_private": _is_private_ipv4(ip_address),
                    "rank": _interface_rank(adapter.name, ip_address),
                }
            )
    options.sort(key=lambda item: (-int(item["rank"]), item["display_name"], item["ip_address"]))
    return options


def resolve_scan_target(
    interface_options: list[dict[str, Any]],
    interface_name: str | None = None,
    cidr: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Choose the interface and scan CIDR for a scan request."""
    if not interface_options:
        return None, ["No usable non-loopback IPv4 interfaces found on this host."]

    selected = None
    if interface_name:
        selected = next((item for item in interface_options if item["name"] == interface_name), None)
        if selected is None:
            return None, [f"Interface '{interface_name}' is not available on this host."]
    else:
        selected = interface_options[0]

    scan_cidr = (cidr or selected.get("suggested_cidr") or "").strip()
    if not scan_cidr:
        return None, ["Unable to determine a default scan CIDR."]
    try:
        network = ipaddress.ip_network(scan_cidr, strict=False)
    except ValueError:
        return None, [f"CIDR '{scan_cidr}' is not a valid IPv4 network."]
    if network.version != 4:
        return None, [f"CIDR '{scan_cidr}' must be an IPv4 network."]

    return (
        {
            "interface_name": selected["name"],
            "display_name": selected["display_name"],
            "interface_ip": selected["ip_address"],
            "cidr": str(network),
        },
        [],
    )


def _decode_mdns_properties(properties: dict[Any, Any] | None) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in (properties or {}).items():
        decoded[_decode_text(key) or ""] = _decode_text(value) or ""
    return decoded


def _mdns_port_field(service_type: str) -> str:
    if service_type == "vapix-https":
        return "https_port"
    return "http_port"


def _mdns_source(service_type: str) -> str:
    return f"mdns:{service_type}"


def _service_hostname(name: str, server: str | None) -> str | None:
    if server:
        cleaned = server.rstrip(".")
        return cleaned[:-6] if cleaned.endswith(".local") else cleaned
    instance = name.split("._", 1)[0].strip()
    return instance or None


def _add_source(candidate: dict[str, Any], source: str) -> None:
    candidate.setdefault("discovery_sources", set()).add(source)


def _add_mdns_candidate(
    devices_by_ip: dict[str, dict[str, Any]],
    *,
    ip_address: str,
    service_type: str,
    port: int | None,
    hostname: str | None,
    properties: dict[str, str],
) -> None:
    candidate = devices_by_ip.setdefault(
        ip_address,
        {
            "ip": ip_address,
            "mac": None,
            "model": None,
            "serial": None,
            "firmware": None,
            "hostname": None,
            "http_port": None,
            "https_port": None,
            "discovery_sources": set(),
            "confidence": "probable",
        },
    )
    port_key = _mdns_port_field(service_type)
    if isinstance(port, int) and port > 0:
        candidate[port_key] = port
    if hostname and not candidate.get("hostname"):
        candidate["hostname"] = hostname
    txt_serial = properties.get("sn") or properties.get("serial") or properties.get("serialnumber")
    txt_mac = properties.get("macaddress") or properties.get("mac") or properties.get("mac-address")
    if txt_serial and not candidate.get("serial"):
        candidate["serial"] = txt_serial
    if txt_mac and not candidate.get("mac"):
        candidate["mac"] = txt_mac
    _add_source(candidate, _mdns_source(service_type))


def browse_mdns_candidates(scan_target: dict[str, Any], timeout_seconds: float = DEFAULT_MDNS_SECONDS) -> list[dict[str, Any]]:
    """Browse Axis-relevant mDNS services and return probable candidates in the target CIDR."""
    from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf

    network = ipaddress.ip_network(scan_target["cidr"], strict=False)
    devices_by_ip: dict[str, dict[str, Any]] = {}

    class Listener(ServiceListener):
        def _record(self, zc: Zeroconf, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name, timeout=1000)
            if info is None:
                return
            service_type = SCAN_SERVICE_TYPES.get(type_)
            if service_type is None:
                return
            parsed_ips = [ip for ip in info.parsed_addresses() if ip]
            properties = _decode_mdns_properties(getattr(info, "properties", None))
            hostname = _service_hostname(name, getattr(info, "server", None))
            for ip_address in parsed_ips:
                try:
                    address = ipaddress.ip_address(ip_address)
                except ValueError:
                    continue
                if address.version != 4 or address not in network:
                    continue
                _add_mdns_candidate(
                    devices_by_ip,
                    ip_address=ip_address,
                    service_type=service_type,
                    port=getattr(info, "port", None),
                    hostname=hostname,
                    properties=properties,
                )

        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self._record(zc, type_, name)

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self._record(zc, type_, name)

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            return None

    zeroconf = Zeroconf(interfaces=[scan_target["interface_ip"]], ip_version=IPVersion.V4Only)
    browsers: list[ServiceBrowser] = []
    listener = Listener()
    try:
        for service_type in SCAN_SERVICE_TYPES:
            browsers.append(ServiceBrowser(zeroconf, service_type, listener=listener))
        time.sleep(timeout_seconds)
    finally:
        for browser in browsers:
            browser.cancel()
        zeroconf.close()
    return list(devices_by_ip.values())


def _check_host_port(ip_address: str, port: int, timeout_seconds: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout_seconds)
        return sock.connect_ex((ip_address, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def sweep_candidate_ports(
    cidr: str,
    ports: tuple[int, ...] = DEFAULT_SCAN_PORTS,
    timeout_seconds: float = DEFAULT_SCAN_TIMEOUT,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, set[int]]:
    """Return IPs in the CIDR with at least one reachable candidate port."""
    network = ipaddress.ip_network(cidr, strict=False)
    ports_by_ip: dict[str, set[int]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_check_host_port, str(host), port, timeout_seconds): (str(host), port)
            for host in network.hosts()
            for port in ports
        }
        for future in as_completed(futures):
            ip_address, port = futures[future]
            try:
                is_open = future.result()
            except Exception:
                is_open = False
            if is_open:
                ports_by_ip.setdefault(ip_address, set()).add(port)
    return ports_by_ip


def _add_port_sources(candidate: dict[str, Any], open_ports: set[int]) -> None:
    if 80 in open_ports:
        candidate["http_port"] = candidate.get("http_port") or 80
        _add_source(candidate, "tcp:80")
    if 443 in open_ports:
        candidate["https_port"] = candidate.get("https_port") or 443
        _add_source(candidate, "tcp:443")


def _bdi_url(ip_address: str, scheme: str, port: int) -> str:
    default_port = 80 if scheme == "http" else 443
    if port == default_port:
        return f"{scheme}://{ip_address}/axis-cgi/basicdeviceinfo.cgi"
    return f"{scheme}://{ip_address}:{port}/axis-cgi/basicdeviceinfo.cgi"


def probe_basic_device_info(ip_address: str, http_port: int | None, https_port: int | None) -> dict[str, Any] | None:
    """Probe anonymous basicdeviceinfo and return Axis identity data when available."""
    attempts: list[tuple[str, int]] = []
    if http_port:
        attempts.append(("http", http_port))
    if https_port:
        attempts.append(("https", https_port))
    for scheme, port in attempts:
        try:
            response = requests.post(
                _bdi_url(ip_address, scheme, port),
                json={"apiVersion": "1.2", "method": "getAllUnrestrictedProperties"},
                headers={"Content-Type": "application/json"},
                timeout=DEFAULT_BDI_TIMEOUT,
                verify=False if scheme == "https" else True,
            )
            response.raise_for_status()
            payload = response.json()
            properties = (((payload or {}).get("data") or {}).get("propertyList") or {})
            if str(properties.get("Brand") or "").strip().upper() != "AXIS":
                continue
            return {
                "brand": properties.get("Brand"),
                "model": properties.get("ProdFullName") or properties.get("ProdNbr"),
                "serial": properties.get("SerialNumber"),
                "firmware": properties.get("Version"),
                "mac": properties.get("MacAddress"),
                "source": f"bdi:{scheme}",
            }
        except Exception:
            continue
    return None


def _merge_device(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in ("ip", "mac", "model", "serial", "firmware", "hostname", "http_port", "https_port"):
        merged[key] = merged.get(key) or incoming.get(key)
    merged_sources = set(existing.get("discovery_sources", set()))
    merged_sources.update(incoming.get("discovery_sources", set()))
    merged["discovery_sources"] = merged_sources
    confidence = "confirmed" if "confirmed" in {existing.get("confidence"), incoming.get("confidence")} else "probable"
    merged["confidence"] = confidence
    return merged


def dedupe_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate devices across serial, MAC, and IP."""
    deduped: list[dict[str, Any]] = []
    for device in devices:
        match_index = None
        for index, current in enumerate(deduped):
            if (
                device.get("serial")
                and current.get("serial")
                and device["serial"] == current["serial"]
            ) or (
                device.get("mac")
                and current.get("mac")
                and str(device["mac"]).lower() == str(current["mac"]).lower()
            ) or device.get("ip") == current.get("ip"):
                match_index = index
                break
        if match_index is None:
            deduped.append(device)
        else:
            deduped[match_index] = _merge_device(deduped[match_index], device)
    for device in deduped:
        device["discovery_sources"] = sorted(set(device.get("discovery_sources", [])))
    deduped.sort(key=lambda item: (item.get("ip") or "", item.get("model") or ""))
    return deduped


def discover_axis_devices(
    interface_name: str | None = None,
    cidr: str | None = None,
) -> dict[str, Any]:
    """Scan a local subnet and return confirmed or probable Axis devices."""
    interface_options = list_interface_options()
    scan_target, errors = resolve_scan_target(interface_options, interface_name=interface_name, cidr=cidr)
    if scan_target is None:
        return {
            "scan_target": None,
            "interface_options": interface_options,
            "devices": [],
            "errors": errors,
        }

    devices_by_ip: dict[str, dict[str, Any]] = {}
    try:
        for device in browse_mdns_candidates(scan_target):
            devices_by_ip[device["ip"]] = _merge_device(devices_by_ip.get(device["ip"], {}), device)
    except Exception as exc:
        errors.append(f"mDNS browse failed: {exc}")

    try:
        ports_by_ip = sweep_candidate_ports(scan_target["cidr"])
    except Exception as exc:
        ports_by_ip = {}
        errors.append(f"Port sweep failed: {exc}")

    for ip_address, open_ports in ports_by_ip.items():
        candidate = devices_by_ip.setdefault(
            ip_address,
            {
                "ip": ip_address,
                "mac": None,
                "model": None,
                "serial": None,
                "firmware": None,
                "hostname": None,
                "http_port": None,
                "https_port": None,
                "discovery_sources": set(),
                "confidence": "probable",
            },
        )
        _add_port_sources(candidate, open_ports)

    discovered_devices: list[dict[str, Any]] = []
    for candidate in devices_by_ip.values():
        axis_info = probe_basic_device_info(
            candidate["ip"],
            candidate.get("http_port"),
            candidate.get("https_port"),
        )
        if axis_info:
            candidate["model"] = axis_info.get("model") or candidate.get("model")
            candidate["serial"] = axis_info.get("serial") or candidate.get("serial")
            candidate["firmware"] = axis_info.get("firmware") or candidate.get("firmware")
            candidate["mac"] = axis_info.get("mac") or candidate.get("mac")
            candidate["confidence"] = "confirmed"
            _add_source(candidate, axis_info.get("source") or "bdi")
            discovered_devices.append(candidate)
            continue
        mdns_sources = set(candidate.get("discovery_sources", set()))
        if any(source.startswith("mdns:") for source in mdns_sources):
            candidate["confidence"] = "probable"
            discovered_devices.append(candidate)

    return {
        "scan_target": scan_target,
        "interface_options": interface_options,
        "devices": dedupe_devices(discovered_devices),
        "errors": errors,
    }

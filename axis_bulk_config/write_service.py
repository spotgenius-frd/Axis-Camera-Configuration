"""
Shared backend write helpers for the CLI and FastAPI app.

This module centralizes write orchestration so the web API can reuse the same
camera-safe logic as the CLI without depending on private helpers.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from axis_bulk_config.client import (
    AxisCameraError,
    AxisCameraClient,
    check_param_update_response,
    param_update_key_variants,
)
from axis_bulk_config.network_config import (
    normalize_network_config,
    poll_camera_reachable,
    subnet_mask_to_prefix_length,
    validate_network_update,
    verify_network_update_result,
)
from axis_bulk_config.read_config import read_camera_config, _to_serializable


def base_url(camera_ip: str, port: int | None) -> str:
    if port and port != 80:
        return f"http://{camera_ip}:{port}"
    return f"http://{camera_ip}"


def _camera_name(camera: dict[str, Any]) -> str | None:
    name = camera.get("name")
    if isinstance(name, str):
        return name.strip() or None
    return None


def make_client(camera: dict[str, Any], timeout: float = 30.0) -> AxisCameraClient:
    return AxisCameraClient(
        base_url(str(camera.get("ip") or ""), camera.get("port")),
        str(camera.get("username") or "root"),
        str(camera.get("password") or ""),
        timeout=timeout,
    )


def refresh_camera(camera: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    data = read_camera_config(
        str(camera.get("ip") or ""),
        str(camera.get("username") or "root"),
        str(camera.get("password") or ""),
        port=camera.get("port"),
        timeout=timeout,
        fetch_param_options=True,
    )
    return _to_serializable(data)


def sanitize_secret(value: str, secret: str) -> str:
    """Redact a secret from any outbound message before it reaches the UI."""
    if not secret:
        return value
    return value.replace(secret, "[redacted]")


def apply_password_change(camera: dict[str, Any], new_password: str) -> dict[str, Any]:
    """Change the password for the current camera username via pwdgrp.cgi."""
    current_password = str(camera.get("password") or "")
    username = str(camera.get("username") or "root").strip()
    camera_ip = str(camera.get("ip") or "?")
    if not username:
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": ["A username is required to change the camera password."],
            "credential_status": "failed",
        }
    if not new_password:
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": ["A new password is required."],
            "credential_status": "failed",
        }

    client = make_client(camera)
    try:
        client.pwdgrp_get_accounts()
    except AxisCameraError as exc:
        if exc.status_code == 404:
            message = "User management API is not supported on this camera."
        elif exc.status_code == 403:
            message = "Administrator privileges are required to change the camera password."
        elif exc.status_code == 401:
            message = "Authentication failed while checking user-management access."
        else:
            message = str(exc)
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": [sanitize_secret(message, current_password)],
            "credential_status": "failed",
        }
    except Exception as exc:
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": [sanitize_secret(str(exc), current_password)],
            "credential_status": "failed",
        }

    try:
        client.pwdgrp_update_password(username, new_password)
    except AxisCameraError as exc:
        if exc.status_code == 404:
            message = "User management API is not supported on this camera."
        elif exc.status_code == 403:
            message = "Administrator privileges are required to change the camera password."
        elif exc.status_code == 401:
            message = "Authentication failed while changing the camera password."
        else:
            message = str(exc)
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": [sanitize_secret(message, new_password)],
            "credential_status": "failed",
        }
    except Exception as exc:
        return {
            "camera_ip": camera_ip,
            "name": _camera_name(camera),
            "ok": False,
            "errors": [sanitize_secret(str(exc), new_password)],
            "credential_status": "failed",
        }

    updated_camera = dict(camera)
    updated_camera["password"] = new_password
    return {
        "camera_ip": camera_ip,
        "name": _camera_name(camera),
        "ok": True,
        "errors": [],
        "credential_status": "verified",
        "camera": updated_camera,
    }


def apply_param_updates(client: AxisCameraClient, updates: dict[str, str]) -> tuple[bool, list[str]]:
    """Apply param.cgi updates; retry with and without root. prefix."""
    all_ok = True
    errors: list[str] = []
    for key, value in updates.items():
        k1, k2 = param_update_key_variants(key)
        try:
            body = client.param_update({k1: value})
            ok, errs = check_param_update_response(body)
            if ok:
                continue
            body2 = client.param_update({k2: value})
            ok2, errs2 = check_param_update_response(body2)
            if ok2:
                continue
            all_ok = False
            errors.extend([f"{k1}: {e}" for e in errs])
            errors.extend([f"{k2}: {e}" for e in errs2])
        except Exception as exc:
            all_ok = False
            errors.append(f"{key}: {exc}")
    return all_ok, errors


def apply_time_zone_update(client: AxisCameraClient, camera_data: dict[str, Any], time_zone: str) -> None:
    """Apply time zone using Time API v2 when supported, else fall back to legacy time.cgi."""
    capabilities = camera_data.get("capabilities") or {}
    dca = capabilities.get("dca") or {}
    known_time_zones = camera_data.get("time_zone_options") or []
    if known_time_zones and time_zone not in known_time_zones:
        raise ValueError(f"Unsupported time zone '{time_zone}' for this camera")
    if dca.get("time_v2"):
        client.time_v2_set_iana_time_zone(time_zone)
        return
    client.set_time_zone(time_zone)


def apply_stream_profile_updates(
    client: AxisCameraClient,
    profiles: list[dict[str, str]],
) -> tuple[bool, list[str]]:
    """Update existing stream profiles and create missing ones."""
    try:
        existing = client.streamprofile_list()
        names = {p.get("name") for p in existing.get("data", {}).get("streamProfile", []) or []}
        to_update = [p for p in profiles if p.get("name") in names]
        to_create = [p for p in profiles if p.get("name") not in names]
        if to_update:
            client.streamprofile_update(to_update)
        if to_create:
            client.streamprofile_create(to_create)
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def apply_stream_profile_removals(
    client: AxisCameraClient,
    names: list[str],
) -> tuple[bool, list[str]]:
    try:
        if names:
            client.streamprofile_remove(names)
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def apply_daynight_updates(
    client: AxisCameraClient,
    updates: dict[str, Any],
    *,
    channel: int = 0,
) -> dict[str, Any]:
    """Apply day/night configuration updates for a specific channel."""
    return client.daynight_set_configuration(channel, updates)


def apply_ir_cut_filter_update(
    client: AxisCameraClient,
    optics_id: str,
    state: str,
) -> dict[str, Any]:
    """Apply an IR cut filter state via the optics control API."""
    return client.opticscontrol_set_ir_cut_filter_state(optics_id, state)


def apply_light_updates(
    client: AxisCameraClient,
    light_id: str,
    updates: dict[str, Any],
) -> list[str]:
    """Apply supported light control updates and return any errors."""
    errors: list[str] = []
    try:
        if "enabled" in updates and updates["enabled"] is not None:
            client.lightcontrol_enable_light(light_id, bool(updates["enabled"]))
        if "light_state" in updates and updates["light_state"] is not None:
            client.lightcontrol_set_light_state(light_id, bool(updates["light_state"]))
        if "manual_intensity" in updates and updates["manual_intensity"] is not None:
            client.lightcontrol_set_manual_intensity(light_id, int(updates["manual_intensity"]))
        if "synchronize_day_night_mode" in updates and updates["synchronize_day_night_mode"] is not None:
            client.lightcontrol_set_daynight_sync(light_id, bool(updates["synchronize_day_night_mode"]))
    except Exception as exc:
        errors.append(str(exc))
    return errors


def apply_firmware_action(
    client: AxisCameraClient,
    action: str,
    *,
    factory_default_mode: str = "soft",
) -> dict[str, Any]:
    if action == "commit":
        return client.firmware_commit()
    if action == "rollback":
        return client.firmware_rollback()
    if action == "purge":
        return client.firmware_purge()
    if action == "reboot":
        return client.firmware_reboot()
    if action == "factory_default":
        return client.firmware_factory_default(factory_default_mode)
    raise ValueError(f"Unsupported firmware action: {action}")


def apply_firmware_upgrade(
    client: AxisCameraClient,
    file_path: str | Path,
    *,
    auto_rollback: str | int | None = None,
    auto_commit: str | None = None,
    factory_default_mode: str | None = None,
) -> dict[str, Any]:
    return client.firmware_upgrade(
        file_path,
        auto_rollback=auto_rollback,
        auto_commit=auto_commit,
        factory_default_mode=factory_default_mode,
    )


def apply_network_config_update(
    camera: dict[str, Any],
    *,
    ipv4_mode: str,
    ip_address: str | None,
    subnet_mask: str | None,
    gateway: str | None,
    dns_servers: list[str] | None,
    use_dhcp_hostname: bool,
    hostname: str | None,
    poll_timeout_seconds: float = 90.0,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    """Apply single-camera network settings using the legacy Axis network settings API."""
    errors = validate_network_update(
        ipv4_mode=ipv4_mode,
        ip_address=ip_address,
        subnet_mask=subnet_mask,
        gateway=gateway,
        dns_servers=dns_servers,
        use_dhcp_hostname=use_dhcp_hostname,
        hostname=hostname,
    )
    previous_ip = str(camera.get("ip") or "")
    if errors:
        return {
            "ok": False,
            "errors": errors,
            "previous_ip": previous_ip,
            "target_ip": ip_address or previous_ip,
            "reachable": None,
            "elapsed_seconds": 0.0,
            "poll_attempts": 0,
        }

    client = make_client(camera)
    network_info = client.network_settings_get_info()
    network_config = normalize_network_config(network_info)
    if not network_config:
        return {
            "ok": False,
            "errors": ["Unable to read current network configuration from the camera."],
            "previous_ip": previous_ip,
            "target_ip": previous_ip,
            "reachable": None,
            "elapsed_seconds": 0.0,
            "poll_attempts": 0,
        }

    api_version = str(network_info.get("apiVersion") or "1.0")
    data = network_info.get("data") or {}
    system = data.get("system") or {}
    resolver = system.get("resolver") or {}
    interface = network_config.get("interface_name") or "eth0"
    devices = data.get("devices") or []
    device = None
    for candidate in devices:
        if isinstance(candidate, dict) and candidate.get("name") == interface:
            device = candidate
            break
    if not isinstance(device, dict):
        device = next((candidate for candidate in devices if isinstance(candidate, dict)), None)
    ipv4_state = (device or {}).get("IPv4") or {}
    target_ip = previous_ip

    static_name_servers = deepcopy(resolver.get("staticNameServers") or [])
    static_search_domains = deepcopy(resolver.get("staticSearchDomains") or [])
    static_domain_name = resolver.get("staticDomainName") or ""
    if use_dhcp_hostname:
        client.network_settings_set_hostname_configuration(
            use_dhcp_hostname=True,
            static_hostname=network_config.get("static_hostname") or network_config.get("hostname"),
            api_version=api_version,
        )
    else:
        client.network_settings_set_hostname_configuration(
            use_dhcp_hostname=False,
            static_hostname=(hostname or "").strip(),
            api_version=api_version,
        )

    cleaned_dns = [value.strip() for value in (dns_servers or []) if value and value.strip()]
    if ipv4_mode == "static":
        target_ip = (ip_address or "").strip()
        client.network_settings_set_resolver_configuration(
            use_dhcp_resolver_info=False,
            static_name_servers=cleaned_dns,
            static_search_domains=static_search_domains,
            static_domain_name=static_domain_name,
            api_version=api_version,
        )
        client.network_settings_set_ipv4_address_configuration(
            device_name=interface,
            configuration_mode="static",
            enabled=ipv4_state.get("enabled"),
            link_local_mode=ipv4_state.get("linkLocalMode"),
            static_default_router=(gateway or "").strip(),
            static_address_configurations=[
                {
                    "address": target_ip,
                    "prefixLength": subnet_mask_to_prefix_length((subnet_mask or "").strip()),
                }
            ],
            use_static_dhcp_fallback=False,
            use_dhcp_static_routes=False,
            api_version=api_version,
        )
    else:
        client.network_settings_set_resolver_configuration(
            use_dhcp_resolver_info=True,
            static_name_servers=static_name_servers,
            static_search_domains=static_search_domains,
            static_domain_name=static_domain_name,
            api_version=api_version,
        )
        client.network_settings_set_ipv4_address_configuration(
            device_name=interface,
            configuration_mode="dhcp",
            enabled=ipv4_state.get("enabled"),
            link_local_mode=ipv4_state.get("linkLocalMode"),
            static_default_router=ipv4_state.get("staticDefaultRouter"),
            static_address_configurations=deepcopy(ipv4_state.get("staticAddressConfigurations") or []),
            use_static_dhcp_fallback=ipv4_state.get("useStaticDHCPFallback"),
            use_dhcp_static_routes=ipv4_state.get("useDHCPStaticRoutes"),
            api_version=api_version,
        )

    poll_result = poll_camera_reachable(
        target_ip=target_ip,
        username=str(camera.get("username") or "root"),
        password=str(camera.get("password") or ""),
        expected_mac_address=network_config.get("mac_address"),
        port=camera.get("port"),
        timeout_seconds=poll_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    if poll_result.get("reachable"):
        verification_errors = verify_network_update_result(
            poll_result.get("network_info"),
            ipv4_mode=ipv4_mode,
            ip_address=target_ip if ipv4_mode == "static" else None,
            subnet_mask=subnet_mask if ipv4_mode == "static" else None,
            gateway=gateway if ipv4_mode == "static" else None,
            dns_servers=cleaned_dns if ipv4_mode == "static" else [],
            use_dhcp_hostname=use_dhcp_hostname,
            hostname=hostname,
        )
        if verification_errors:
            return {
                "ok": False,
                "errors": verification_errors,
                "previous_ip": previous_ip,
                "target_ip": target_ip,
                "reachable": True,
                "reachable_ip": target_ip,
                "elapsed_seconds": poll_result.get("elapsed_seconds", 0.0),
                "poll_attempts": poll_result.get("poll_attempts", 0),
            }
        return {
            "ok": True,
            "errors": [],
            "previous_ip": previous_ip,
            "target_ip": target_ip,
            "reachable": True,
            "reachable_ip": target_ip,
            "elapsed_seconds": poll_result.get("elapsed_seconds", 0.0),
            "poll_attempts": poll_result.get("poll_attempts", 0),
        }

    error_message = poll_result.get("last_error") or (
        f"Camera did not return at {target_ip} within {poll_timeout_seconds:.0f} seconds."
    )
    recovered_ip: str | None = None
    if previous_ip and target_ip and previous_ip != target_ip:
        fallback_poll = poll_camera_reachable(
            target_ip=previous_ip,
            username=str(camera.get("username") or "root"),
            password=str(camera.get("password") or ""),
            expected_mac_address=network_config.get("mac_address"),
            port=camera.get("port"),
            timeout_seconds=10.0,
            poll_interval_seconds=max(1.0, poll_interval_seconds),
        )
        if fallback_poll.get("reachable"):
            recovered_ip = previous_ip
            error_message = (
                f"Target IP {target_ip} did not become reachable. "
                f"The camera is still reachable at {previous_ip}, which usually means the target IP is already in use "
                f"or the static address could not be activated."
            )
    return {
        "ok": False,
        "errors": [error_message],
        "previous_ip": previous_ip,
        "target_ip": target_ip,
        "reachable": False,
        "reachable_ip": recovered_ip,
        "elapsed_seconds": poll_result.get("elapsed_seconds", 0.0),
        "poll_attempts": poll_result.get("poll_attempts", 0),
    }

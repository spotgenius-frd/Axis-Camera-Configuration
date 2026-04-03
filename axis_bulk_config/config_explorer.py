"""
Single-camera config explorer: fetch current settings, list what can be changed,
export to JSON, and optionally apply changes (params, stream profiles, time zone).

Usage:
  python -m axis_bulk_config.config_explorer <camera_ip> --user root --password PASS [options]
  python -m axis_bulk_config.config_explorer <camera_ip> --output config.json
  python -m axis_bulk_config.config_explorer <camera_ip> --set-param "Image.I0.Appearance.Resolution=1920x1080" --set-timezone "America/New_York" --apply

Env: AXIS_IP, AXIS_USER, AXIS_PASSWORD (for camera and credentials).
"""

import argparse
import json
import os
import sys
from pathlib import Path

from axis_bulk_config.client import (
    AxisCameraClient,
    AxisCameraError,
    check_param_update_response,
    param_update_key_variants,
    parse_param_list,
)
from axis_bulk_config.firmware_lookup import get_latest_firmware
from axis_bulk_config.option_catalog import (
    format_catalog_entry_display,
    get_param_catalog_entry,
)
from axis_bulk_config.param_options import format_options_display
from axis_bulk_config.read_config import (
    PARAM_GROUPS,
    read_camera_config,
    _to_serializable,
)
from axis_bulk_config.stream_profiles import (
    COMMON_STREAM_PROFILE_FIELDS,
    build_stream_profile_payload,
    merge_stream_profile_values,
    normalize_stream_profiles_response,
)


def _base_url(camera_ip: str, port: int | None) -> str:
    if port and port != 80:
        return f"http://{camera_ip}:{port}"
    return f"http://{camera_ip}"


def _normalize_firmware_status(raw: dict) -> dict:
    """Normalize firmware API response to a consistent dict for display."""
    d = raw.get("data") or raw
    return {
        "active": d.get("activeFirmwareVersion") or d.get("active"),
        "inactive": d.get("inactiveFirmwareVersion") or d.get("inactive"),
        "committed": d.get("isCommitted") if "isCommitted" in d else d.get("committed"),
        "last_upgrade": d.get("lastUpgradeAt") or d.get("lastUpgrade"),
    }


def _print_firmware_block(
    data: dict,
    latest_info: dict | None = None,
    *,
    prefix: str = "  ",
) -> None:
    """Print installed firmware, optional latest official, and update availability."""
    summary = data.get("summary") or {}
    installed = summary.get("firmware") or "—"
    fw_raw = data.get("firmware_status")
    if fw_raw and "error" not in str(fw_raw).lower():
        norm = _normalize_firmware_status(fw_raw)
        active = norm.get("active") or installed
        inactive = norm.get("inactive")
        committed = norm.get("committed")
        last_upgrade = norm.get("last_upgrade")
        print(f"{prefix}Active:   {active}")
        if inactive:
            print(f"{prefix}Inactive (rollback): {inactive}")
        if committed is not None:
            print(f"{prefix}Committed: {committed}")
        if last_upgrade:
            print(f"{prefix}Last upgrade: {last_upgrade}")
    else:
        print(f"{prefix}{installed}")
    if latest_info:
        latest_ver = latest_info.get("version")
        url = latest_info.get("download_url")
        if latest_ver:
            print(f"{prefix}Latest official (Axis): {latest_ver}")
            print(f"{prefix}Update: {installed} → {latest_ver}")
            if url:
                print(f"{prefix}Download: {url}")
    print(f"{prefix}Use --interactive for upgrade, commit, rollback, reboot.\n")


def _get_param_option_meta(param_options: dict, param_key: str) -> dict | None:
    """Look up param_options by key; try root.X and X."""
    if not param_options:
        return None
    if param_key in param_options:
        return param_options[param_key]
    if param_key.startswith("root."):
        return param_options.get(param_key[5:])
    return param_options.get("root." + param_key)


# Curated high-value settings: (param_key, label). Only show when camera exposes them.
CURATED_STREAM = [
    ("root.Image.I0.Appearance.Resolution", "Resolution"),
    ("root.Image.I0.Stream.FPS", "FPS"),
    ("root.Image.I0.Appearance.Compression", "Compression"),
    ("root.Image.I0.RateControl.TargetBitrate", "Target bitrate"),
    ("root.Image.I0.RateControl.Mode", "Rate control mode"),
    ("root.Image.I0.MPEG.H264.Profile", "H.264 profile"),
]
CURATED_IMAGE = [
    ("root.Image.I0.Appearance.ColorEnabled", "Color"),
    ("root.Image.I0.Appearance.Brightness", "Brightness"),
    ("root.Image.I0.Appearance.Contrast", "Contrast"),
    ("root.Image.I0.Appearance.Saturation", "Saturation"),
    ("root.Image.I0.Appearance.Sharpness", "Sharpness"),
    ("root.Image.I0.Appearance.MirrorEnabled", "Mirror"),
    ("root.Image.I0.Appearance.Rotation", "Rotation"),
]
CURATED_OVERLAY = [
    ("root.Image.I0.Overlay.Enabled", "Overlay enabled"),
    ("root.Image.I0.Text.TextEnabled", "Text enabled"),
    ("root.Image.I0.Text.String", "Overlay text"),
    ("root.Image.I0.Text.ClockEnabled", "Show clock"),
    ("root.Image.I0.Text.DateEnabled", "Show date"),
    ("root.Image.I0.Text.Position", "Text position"),
    ("root.Image.I0.Text.TextSize", "Text size"),
]
CURATED_IMAGE_EXTRAS = [
    ("root.Image.I0.Focus.FocusMode", "Focus mode"),
    ("root.Image.I0.Zoom.Position", "Zoom position"),
    ("root.Image.I0.WDR.Enabled", "WDR enabled"),
]
CURATED_STORAGE = [
    ("root.Storage.S0.Enabled", "SD card enabled"),
    ("root.Storage.S0.CleanupLevel", "Cleanup level %"),
    ("root.Storage.S0.CleanupMaxAge", "Cleanup max age (days)"),
    ("root.Storage.S0.CleanupPolicyActive", "Cleanup policy"),
]


def _get_param_value(params: dict, param_key: str) -> str | None:
    """Get current value for param_key from params (Image or Storage); try root.X and X."""
    v = params.get(param_key)
    if v is not None:
        return str(v)
    if param_key.startswith("root."):
        v = params.get(param_key[5:])
    else:
        v = params.get("root." + param_key)
    return str(v) if v is not None else None


def build_curated_settings(data: dict) -> dict[str, list[dict]]:
    """
    Build a user-facing curated settings inventory from params and option_catalog (or param_options fallback).
    Returns dict: category -> list of {label, param_key, value, options_str, writable, inputKind, options, min, max}.
    Only includes settings the camera actually exposes (value present).
    """
    params_all = data.get("params") or {}
    option_catalog = data.get("option_catalog") or {}
    param_options = data.get("param_options") or {}
    img_params = params_all.get("Image") or {}
    storage_params = params_all.get("Storage") or {}
    if not isinstance(img_params, dict):
        img_params = {}
    if not isinstance(storage_params, dict):
        storage_params = {}

    def row(param_key: str, label: str, param_dict: dict) -> dict | None:
        value = _get_param_value(param_dict, param_key)
        if value is None:
            return None
        entry = get_param_catalog_entry(option_catalog, param_key)
        if entry is not None and entry.get("niceName") is not None:
            options_str = format_catalog_entry_display(entry)
            writable = entry.get("writable", True)
            input_kind = entry.get("inputKind", "text")
            options = entry.get("options")
            min_v = entry.get("min")
            max_v = entry.get("max")
            value = value or entry.get("value", "")
        else:
            meta = _get_param_option_meta(param_options, param_key)
            options_str = format_options_display(meta) if meta else ""
            writable = meta.get("writable", True) if meta else True
            input_kind = "text"
            options = meta.get("options") if meta else None
            min_v = meta.get("min") if meta else None
            max_v = meta.get("max") if meta else None
        return {
            "label": label,
            "param_key": param_key,
            "value": value,
            "options_str": options_str,
            "writable": writable,
            "inputKind": input_kind,
            "options": options,
            "min": min_v,
            "max": max_v,
        }

    out: dict[str, list[dict]] = {}
    for cat, key_label_list, param_dict in [
        ("stream", CURATED_STREAM, img_params),
        ("image", CURATED_IMAGE, img_params),
        ("overlay", CURATED_OVERLAY, img_params),
        ("image_extras", CURATED_IMAGE_EXTRAS, img_params),
        ("storage", CURATED_STORAGE, storage_params),
    ]:
        rows = []
        for param_key, label in key_label_list:
            r = row(param_key, label, param_dict)
            if r is not None:
                rows.append(r)
        if rows:
            out[cat] = rows
    return out


def _print_config_options(data: dict) -> None:
    """Print current value and allowed options for key configurable settings (option_catalog + param_options)."""
    option_catalog = data.get("option_catalog") or {}
    param_options = data.get("param_options") or {}
    if not option_catalog and not param_options:
        print("\n--- Config options ---\n  (No param definitions available; use default run to fetch.)\n")
        return
    print("\n--- Config options (current value and allowed values) ---\n")
    priority_keys = [
        "root.Image.I0.Appearance.Resolution",
        "root.Image.I0.Stream.FPS",
        "root.Image.I0.Appearance.Compression",
        "root.Image.I0.Overlay.Enabled",
        "root.Image.I0.Appearance.ColorEnabled",
    ]
    seen = set()
    for param_key in priority_keys:
        entry = get_param_catalog_entry(option_catalog, param_key)
        if entry:
            value = entry.get("value", "")
            nice = entry.get("niceName", param_key.split(".")[-1])
            opts_str = format_catalog_entry_display(entry)
            writable = entry.get("writable", True)
        else:
            meta = _get_param_option_meta(param_options, param_key)
            if not meta:
                continue
            value = meta.get("value", "")
            nice = meta.get("niceName", param_key.split(".")[-1])
            opts_str = format_options_display(meta)
            writable = meta.get("writable", True)
        ro = " [read-only]" if not writable else ""
        print(f"  {nice}: {value} {opts_str}{ro}")
        seen.add(param_key)
    # Show more from catalog then param_options that are writable and have options
    for full_key in sorted(option_catalog.keys()):
        if full_key.startswith("_"):
            continue
        if full_key in seen:
            continue
        entry = option_catalog[full_key]
        if not entry.get("writable"):
            continue
        opts_str = format_catalog_entry_display(entry)
        if not opts_str:
            continue
        if len(seen) >= 25:
            print("  ...")
            break
        value = entry.get("value", "")
        nice = entry.get("niceName", full_key.split(".")[-1])
        print(f"  {nice}: {value} {opts_str}")
        seen.add(full_key)
    for full_key, meta in sorted(param_options.items()):
        if full_key in seen:
            continue
        if not meta.get("writable"):
            continue
        opts_str = format_options_display(meta)
        if not opts_str:
            continue
        if len(seen) >= 25:
            print("  ...")
            break
        value = meta.get("value", "")
        nice = meta.get("niceName", full_key.split(".")[-1])
        print(f"  {nice}: {value} {opts_str}")
        seen.add(full_key)
    print()


def _print_capability_catalog(data: dict) -> None:
    """Print grouped capability report: supported, detected/read-only, additional VAPIX APIs."""
    summary = data.get("summary") or {}
    params = data.get("params") or {}
    capabilities = data.get("capabilities") or {}
    has_image = bool((params.get("Image") or {}).keys() and "_error" not in str(params.get("Image")))
    has_stream = bool(summary.get("stream"))
    has_time = bool((data.get("time_info") or {}).get("data"))
    has_fw = data.get("firmware_status") is not None and "error" not in str(data.get("firmware_status", ""))
    dca = capabilities.get("dca") or {}
    stream_caps = capabilities.get("stream_profiles") or {}

    print("\n--- Capability catalog ---\n")
    print("Supported in-script (read/write where implemented):")
    print("  • param.cgi: Image, Network, Storage, Properties.System")
    print("  • streamprofile.cgi: list, create, update, remove stream profiles")
    print("  • time.cgi: time zone, date/time")
    print("  • firmwaremanagement.cgi: status, upgrade, commit, rollback, purge, reboot, factory default")
    print()
    print("Detected / read from camera:")
    print(f"  • Image params: {'yes' if has_image else 'no'}")
    print(f"  • Stream profiles: {'yes' if has_stream else 'no'}")
    print(f"  • Time info: {'yes' if has_time else 'no'}")
    print(f"  • Firmware status: {'yes' if has_fw else 'no'}")
    print(f"  • DCA discovery: {'yes' if dca.get('discovery') else 'no'}")
    print(f"  • Time API v2: {'yes' if dca.get('time_v2') else 'no'}")
    print(f"  • Network Settings API v2: {'yes' if dca.get('network_settings_v2') else 'no'}")
    if stream_caps.get("supported_versions"):
        print(f"  • Stream Profiles API versions: {', '.join(stream_caps['supported_versions'])}")
    print()
    print("Additional VAPIX APIs (cataloged for future integration):")
    print("  • Imaging API: exposure, white balance, WDR, day/night, stabilization, focus/iris")
    print("  • Overlay API: text/image overlays, privacy masks")
    print("  • Network settings API: DHCP/static, DNS, IPv4/IPv6, 802.1X, proxy, VLAN")
    print("  • I/O port management: digital inputs/outputs, relays")
    print("  • PTZ / Guard tour API: presets, limits, tours, movement (PTZ models)")
    print("  • Edge storage API: SD / network recording, storage management")
    print()


def _print_curated_section(title: str, rows: list[dict], prefix: str = "  ") -> None:
    """Print one curated section: title then each row as label: value options_str [read-only]."""
    print(f"{title}")
    for r in rows:
        ro = " [read-only]" if not r.get("writable", True) else ""
        opts = f" {r.get('options_str', '')}" if r.get("options_str") else ""
        print(f"{prefix}{r['label']}: {r['value']}{opts}{ro}")
    print()


def _print_what_you_can_change(data: dict) -> None:
    """Print a curated summary of important changeable settings only (no raw param dump)."""
    summary = data.get("summary") or {}
    curated = build_curated_settings(data)
    utc_now, local_now = _current_time_fields(data)

    print("\n--- What you can change ---\n")

    # Firmware
    print("Firmware:")
    _print_firmware_block(data, data.get("latest_firmware"))

    # Primary stream / video
    if curated.get("stream"):
        _print_curated_section("Stream / video:", curated["stream"])

    # Stream profiles (names + key params)
    print("Stream profiles:")
    for p in summary.get("stream") or []:
        name = p.get("name", "?")
        parts = [f"{k}={v}" for k, v in p.items() if k != "name" and v]
        print(f"  {name}: " + ", ".join(parts[:6]) + (" ..." if len(parts) > 6 else ""))
    print("  (Manage via --interactive > Stream profiles)\n")

    # Overlay / text
    if curated.get("overlay"):
        _print_curated_section("Overlay / text:", curated["overlay"])

    # Image tuning
    if curated.get("image"):
        _print_curated_section("Image tuning:", curated["image"])

    # Focus / zoom / WDR when present
    if curated.get("image_extras"):
        _print_curated_section("Imaging (focus, zoom, WDR):", curated["image_extras"])

    # Storage
    if curated.get("storage"):
        _print_curated_section("Storage:", curated["storage"])
    print(f"  SD card: {summary.get('sd_card', '—')}\n")

    # Time zone
    print("Time:")
    print(f"  UTC: {utc_now}")
    print(f"  Local: {local_now}")
    print(f"  Time zone: {_current_time_zone(data)}")
    print("  Set via: --set-timezone IANA or --apply-from JSON with timeZone\n")


def _medium_export(data: dict) -> dict:
    """Build a JSON-serializable export suitable for --apply-from and web UI (includes option_catalog when present)."""
    out = {
        "camera_ip": data.get("camera_ip"),
        "summary": data.get("summary"),
        "params": data.get("params"),
        "stream_profiles": data.get("stream_profiles"),
        "stream_profiles_structured": data.get("stream_profiles_structured"),
        "time_info": data.get("time_info"),
        "time_info_v2": data.get("time_info_v2"),
        "time_zone_info_v2": data.get("time_zone_info_v2"),
        "time_zone_options": data.get("time_zone_options"),
        "network_summary": data.get("network_summary"),
        "capabilities": data.get("capabilities"),
    }
    if data.get("option_catalog"):
        out["option_catalog"] = data["option_catalog"]
    return out


def _apply_param_updates(client: AxisCameraClient, updates: dict[str, str]) -> tuple[bool, list[str]]:
    """Apply param updates; try both key variants (root. prefix) if needed."""
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
        except Exception as e:
            all_ok = False
            errors.append(f"{key}: {e}")
    return all_ok, errors


def _apply_stream_profile_updates(
    client: AxisCameraClient,
    profiles: list[dict],
) -> tuple[bool, list[str]]:
    """Update or create stream profiles. Each item: name, description?, parameters."""
    errors: list[str] = []
    try:
        existing = client.streamprofile_list()
        names = {
            p.get("name") for p in existing.get("data", {}).get("streamProfile", []) or []
        }
        to_update = [p for p in profiles if p.get("name") in names]
        to_create = [p for p in profiles if p.get("name") not in names]
        if to_update:
            client.streamprofile_update(to_update)
        if to_create:
            client.streamprofile_create(to_create)
        return True, []
    except Exception as e:
        return False, [str(e)]


def _apply_stream_profile_removals(
    client: AxisCameraClient,
    names: list[str],
) -> tuple[bool, list[str]]:
    """Remove stream profiles by name."""
    try:
        if names:
            client.streamprofile_remove(names)
        return True, []
    except Exception as e:
        return False, [str(e)]


# --- Interactive mode ---

def _prompt(text: str, default: str | None = None) -> str:
    """Read a line from stdin; return stripped or default if empty."""
    if default is not None:
        line = input(f"{text} [{default}]: ").strip()
        return line if line else default
    return input(f"{text}: ").strip()


def _confirm(text: str, default_no: bool = True) -> bool:
    """Ask yes/no; default_no=True means Enter = No."""
    suffix = " [y/N]" if default_no else " [Y/n]"
    line = input(text + suffix).strip().lower()
    if not line:
        return not default_no
    return line in ("y", "yes")


def _refresh_data(client: AxisCameraClient, data: dict, port: int) -> None:
    """Refresh the in-memory camera snapshot after an immediate write."""
    refreshed = read_camera_config(
        data.get("camera_ip") or "",
        client.username,
        client.password,
        port=port,
        timeout=client.timeout,
        fetch_param_options=bool(data.get("param_options")),
    )
    refreshed = _to_serializable(refreshed)
    data.clear()
    data.update(refreshed)


def _choose_from_options(label: str, options: list[str], current: str = "") -> str | None:
    """Prompt for a value from a list of options, allowing index or exact text."""
    if not options:
        return _prompt(label, current).strip()
    print("    Choose by number or type value:")
    for idx, option in enumerate(options, 1):
        marker = " (current)" if option == current else ""
        print(f"      {idx}. {option}{marker}")
    choice = _prompt(f"  Choice for {label}", current).strip()
    if not choice:
        return None
    if choice.isdigit():
        num = int(choice)
        if 1 <= num <= len(options):
            return options[num - 1]
    return choice


def _stream_profile_field_options(data: dict, field_name: str) -> list[str]:
    """Best-effort dropdown options for common stream profile fields."""
    option_catalog = data.get("option_catalog") or {}
    profiles = data.get("stream_profiles_structured") or []

    def unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                out.append(value)
        return out

    if field_name == "resolution":
        entry = get_param_catalog_entry(option_catalog, "root.Image.I0.Appearance.Resolution") or {}
        return unique([str(v) for v in (entry.get("options") or [])])
    if field_name == "rotation":
        entry = get_param_catalog_entry(option_catalog, "root.Image.I0.Appearance.Rotation") or {}
        return unique([str(v) for v in (entry.get("options") or [])])
    if field_name == "videocodec":
        existing = [
            str((profile.get("values") or {}).get("videocodec") or "")
            for profile in profiles
            if isinstance(profile, dict)
        ]
        return unique(existing + ["h264", "h265", "mjpeg"])
    if field_name == "audio":
        existing = [
            str((profile.get("values") or {}).get("audio") or "")
            for profile in profiles
            if isinstance(profile, dict)
        ]
        return unique(existing + ["0", "1"])
    if field_name == "text":
        return ["0", "1"]
    if field_name == "signedvideo":
        return ["off", "on"]
    return []


def _format_stream_profile(profile: dict) -> str:
    """Compact text summary for a normalized stream profile."""
    values = profile.get("values") or {}
    parts: list[str] = []
    for field_name, _label in COMMON_STREAM_PROFILE_FIELDS:
        value = values.get(field_name)
        if value not in (None, ""):
            parts.append(f"{field_name}={value}")
    if not parts:
        parts = [f"{key}={value}" for key, value in values.items() if value]
    return ", ".join(parts[:8]) + (" ..." if len(parts) > 8 else "")


def _pick_stream_profile(profiles: list[dict], action: str) -> dict | None:
    """Let the user pick one normalized stream profile by number."""
    if not profiles:
        print("  No stream profiles found.")
        return None
    print()
    for idx, profile in enumerate(profiles, 1):
        desc = _format_stream_profile(profile)
        print(f"  {idx:2}. {profile.get('name', '?')}: {desc}")
    line = _prompt(f"  Choose profile to {action}", "").strip()
    if not line:
        return None
    try:
        num = int(line)
    except ValueError:
        print("  Enter a profile number.")
        return None
    if 1 <= num <= len(profiles):
        return profiles[num - 1]
    print("  Invalid number.")
    return None


def _prompt_stream_profile_values(data: dict, existing_values: dict[str, str] | None = None) -> dict[str, str]:
    """Prompt for common stream profile fields and return the merged values map."""
    values = dict(existing_values or {})
    print("  Leave a field empty to keep the current value.")
    for field_name, label in COMMON_STREAM_PROFILE_FIELDS:
        current = str(values.get(field_name, ""))
        options = _stream_profile_field_options(data, field_name)
        if options:
            new_value = _choose_from_options(label, options, current)
        else:
            new_value = _prompt(f"  {label}", current).strip()
        if new_value is None:
            continue
        values = merge_stream_profile_values(values, {field_name: new_value})
    return values


def _current_time_zone(data: dict) -> str:
    """Return the best available current time zone string."""
    tz_v2 = (((data.get("time_zone_info_v2") or {}).get("data") or {}).get("timeZone") or {})
    if isinstance(tz_v2, dict) and tz_v2.get("activeTimeZone"):
        return str(tz_v2.get("activeTimeZone"))
    time_info = (data.get("time_info") or {}).get("data") or {}
    return str(time_info.get("timeZone") or time_info.get("posixTimeZone") or "—")


def _current_time_fields(data: dict) -> tuple[str, str]:
    """Return current UTC/local timestamps from Time API v2 or legacy time.cgi."""
    time_v2 = (((data.get("time_info_v2") or {}).get("data") or {}).get("time") or {})
    if isinstance(time_v2, dict) and (time_v2.get("dateTime") or time_v2.get("localDateTime")):
        return (
            str(time_v2.get("dateTime") or "—"),
            str(time_v2.get("localDateTime") or "—"),
        )
    time_info = (data.get("time_info") or {}).get("data") or {}
    return (
        str(time_info.get("dateTime") or "—"),
        str(time_info.get("localDateTime") or "—"),
    )


def _apply_time_zone_update(client: AxisCameraClient, data: dict, time_zone: str) -> None:
    """Apply time zone using Time API v2 when available, else fall back to time.cgi."""
    capabilities = data.get("capabilities") or {}
    dca = capabilities.get("dca") or {}
    known_time_zones = data.get("time_zone_options") or []
    if known_time_zones and time_zone not in known_time_zones:
        raise ValueError(f"Unsupported time zone '{time_zone}' for this camera")
    if dca.get("time_v2"):
        client.time_v2_set_iana_time_zone(time_zone)
        return
    client.set_time_zone(time_zone)


def _interactive_curated_section(
    client: AxisCameraClient,
    data: dict,
    category: str,
    section_title: str,
    pending: dict[str, str],
) -> None:
    """Edit only the curated settings in one category; show options before prompting."""
    curated = build_curated_settings(data)
    rows = curated.get(category) or []
    if not rows:
        print(f"  No {section_title.lower()} settings available on this camera.")
        return
    while True:
        print(f"\n  --- {section_title} ---")
        for i, r in enumerate(rows, 1):
            opts = f"  {r.get('options_str', '')}" if r.get("options_str") else ""
            ro = " [read-only]" if not r.get("writable", True) else ""
            val = r["value"]
            if len(val) > 36:
                val = val[:33] + "..."
            print(f"    {i:2}. {r['label']}: {val}{opts}{ro}")
        print("    Enter number to change a setting, or empty to back.")
        line = _prompt("  Choice", "").strip()
        if not line:
            break
        try:
            num = int(line)
            if 1 <= num <= len(rows):
                r = rows[num - 1]
                if not r.get("writable", True):
                    print("    Read-only; cannot change.")
                    continue
                opts = r.get("options")
                min_v, max_v = r.get("min"), r.get("max")
                if opts and isinstance(opts, list) and len(opts) > 0:
                    print(f"    Choose by number or type value:")
                    for j, opt in enumerate(opts, 1):
                        cur = " (current)" if opt == r["value"] else ""
                        print(f"      {j}. {opt}{cur}")
                    choice = _prompt(f"  Choice for {r['label']}", r["value"]).strip()
                    if not choice:
                        continue
                    if choice.isdigit() and 1 <= int(choice) <= len(opts):
                        new_val = opts[int(choice) - 1]
                    elif choice in opts:
                        new_val = choice
                    else:
                        new_val = choice
                    if new_val:
                        pending[r["param_key"]] = new_val
                        print(f"    Queued: {r['label']}={new_val}")
                elif min_v is not None or max_v is not None:
                    if r.get("options_str"):
                        print(f"    Allowed: {r['options_str']}")
                    new_val = _prompt(f"  New value for {r['label']}", r["value"]).strip()
                    if new_val:
                        pending[r["param_key"]] = new_val
                        print(f"    Queued: {r['label']}={new_val}")
                else:
                    if r.get("options_str"):
                        print(f"    Allowed: {r['options_str']}")
                    new_val = _prompt(f"  New value for {r['label']}", r["value"]).strip()
                    if new_val:
                        pending[r["param_key"]] = new_val
                        print(f"    Queued: {r['label']}={new_val}")
            else:
                print("    Invalid number.")
        except ValueError:
            print("    Enter a number or leave empty to back.")


def _interactive_param_group(
    client: AxisCameraClient,
    group: str,
    pending: dict[str, str],
    param_options: dict | None = None,
) -> None:
    """Let user browse and add param edits for one group (advanced: full raw param list). If param_options provided, show allowed values when editing."""
    options_map = param_options or {}
    try:
        text = client.param_list(group=group)
        params = parse_param_list(text)
    except Exception as e:
        print(f"  Error loading {group}: {e}")
        return
    if not params or "_error" in params:
        print(f"  No parameters or error for {group}.")
        return
    # Filter to a reasonable set; skip internal/source keys if too many
    keys = sorted(k for k in params if not k.endswith(".Source") and "_error" not in str(params.get(k)))[:80]
    if not keys:
        print("  No editable keys shown.")
        return
    while True:
        print(f"\n  --- {group} ({len(keys)} params) ---")
        for i, k in enumerate(keys[:20], 1):
            v = params.get(k, "")
            if len(v) > 40:
                v = v[:37] + "..."
            print(f"    {i:2}. {k}: {v}")
        if len(keys) > 20:
            print(f"    ... and {len(keys) - 20} more. Use key=value to set any.")
        print("    Enter key=value to queue a change, or param number then value, or empty to back.")
        line = _prompt("  Choice", "").strip()
        if not line:
            break
        if "=" in line:
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key in params or key.replace("root.", "", 1) in params or "root." + key in params:
                pending[key] = value
                print(f"  Queued: {key}={value}")
            else:
                pending[key] = value
                print(f"  Queued (key may be model-specific): {key}={value}")
        else:
            try:
                num = int(line)
                if 1 <= num <= len(keys):
                    key = keys[num - 1]
                    meta = _get_param_option_meta(options_map, key)
                    if meta:
                        opts_str = format_options_display(meta)
                        if opts_str:
                            print(f"    Allowed: {opts_str}")
                        if not meta.get("writable"):
                            print("    [read-only]")
                    value = _prompt(f"  New value for {key}", params.get(key, ""))
                    if value:
                        pending[key] = value
                        print(f"  Queued: {key}={value}")
                else:
                    print("  Invalid number.")
            except ValueError:
                print("  Enter key=value or number.")


def _interactive_stream_profiles(
    client: AxisCameraClient,
    data: dict,
    port: int,
) -> None:
    """Manage stream profiles: list, create, edit, and remove."""
    while True:
        profiles = data.get("stream_profiles_structured") or normalize_stream_profiles_response(data.get("stream_profiles"))
        versions = data.get("stream_profile_supported_versions") or []
        print("\n  --- Stream profiles ---")
        if versions:
            print(f"  API versions: {', '.join(str(v) for v in versions)}")
        print(f"  Profiles: {len(profiles)}")
        print("  1. List profiles")
        print("  2. Create profile")
        print("  3. Edit profile")
        print("  4. Remove profile")
        print("  0. Back")
        choice = _prompt("  Choice", "0").strip() or "0"

        if choice == "0":
            return
        if choice == "1":
            if not profiles:
                print("  No stream profiles found.")
                continue
            for profile in profiles:
                description = profile.get("description") or ""
                print(f"  {profile.get('name', '?')}: {_format_stream_profile(profile)}")
                if description:
                    print(f"    Description: {description}")
            continue
        if choice == "2":
            name = _prompt("  New profile name", "").strip()
            if not name:
                continue
            description = _prompt("  Description", "").strip()
            values = _prompt_stream_profile_values(data, {})
            payload = build_stream_profile_payload(name=name, description=description, values=values)
            print(f"  New profile payload: {payload['parameters'] or '(empty)'}")
            if not _confirm("  Create this profile on the camera?", default_no=True):
                continue
            ok, errs = _apply_stream_profile_updates(client, [payload])
            if not ok:
                for err in errs:
                    print(f"  Stream profile error: {err}")
                continue
            print(f"  Created profile: {name}")
            _refresh_data(client, data, port)
            continue
        if choice == "3":
            profile = _pick_stream_profile(profiles, "edit")
            if not profile:
                continue
            name = str(profile.get("name") or "")
            description = _prompt("  Description", str(profile.get("description") or "")).strip()
            values = _prompt_stream_profile_values(data, profile.get("values") or {})
            payload = build_stream_profile_payload(name=name, description=description, values=values)
            print(f"  Updated profile payload: {payload['parameters'] or '(empty)'}")
            if not _confirm(f"  Update stream profile '{name}'?", default_no=True):
                continue
            ok, errs = _apply_stream_profile_updates(client, [payload])
            if not ok:
                for err in errs:
                    print(f"  Stream profile error: {err}")
                continue
            print(f"  Updated profile: {name}")
            _refresh_data(client, data, port)
            continue
        if choice == "4":
            profile = _pick_stream_profile(profiles, "remove")
            if not profile:
                continue
            name = str(profile.get("name") or "")
            print(f"  Removing '{name}' will delete that named stream profile from the camera.")
            if not _confirm(f"  Really remove '{name}'?", default_no=True):
                continue
            ok, errs = _apply_stream_profile_removals(client, [name])
            if not ok:
                for err in errs:
                    print(f"  Stream profile error: {err}")
                continue
            print(f"  Removed profile: {name}")
            _refresh_data(client, data, port)
            continue
        print("  Invalid choice.")


def _interactive_time(data: dict, pending_time_zone: list[str | None]) -> None:
    """Show time and optionally set timezone, preferring Time API v2 options when available."""
    time_zones = data.get("time_zone_options") or []
    utc_now, local_now = _current_time_fields(data)
    print(f"  Current UTC: {utc_now}")
    print(f"  Local: {local_now}")
    print(f"  Time zone: {_current_time_zone(data)}")
    if pending_time_zone and pending_time_zone[0]:
        print(f"  Pending time zone: {pending_time_zone[0]}")
    if time_zones:
        print(f"  Device reported {len(time_zones)} valid IANA time zones.")
        filter_text = _prompt("  Filter time zones (e.g. Chicago, Europe) or empty to type exact value", "").strip()
        matches = time_zones
        if filter_text:
            matches = [tz for tz in time_zones if filter_text.lower() in tz.lower()]
            if not matches:
                print("  No matching time zones found.")
                return
        shown = matches[:30]
        if len(matches) > len(shown):
            print(f"  Showing first {len(shown)} matches; type the exact value to use another match.")
        tz = _choose_from_options("Time zone", shown, _current_time_zone(data))
        if tz and tz not in time_zones:
            print("  That value is not in the device's supported time zone list.")
            return
    else:
        print("  Enter new IANA time zone (e.g. America/New_York) or empty to keep.")
        tz = _prompt("  Time zone", "").strip()
    if tz:
        pending_time_zone.clear()
        pending_time_zone.append(tz)
        print(f"  Queued time zone: {tz}")


def _interactive_firmware(client: AxisCameraClient, data: dict) -> None:
    """Firmware submenu: status block (camera + latest official), then actions. All dangerous with confirm."""
    while True:
        print("\n  --- Firmware ---")
        # Status block first (camera + latest official)
        try:
            status = client.firmware_status()
            # Merge into data so _print_firmware_block can use it
            data_with_status = {**data, "firmware_status": status}
        except Exception:
            data_with_status = data
        summary = data.get("summary") or {}
        latest = get_latest_firmware(summary.get("model") or "")
        if latest:
            data_with_status["latest_firmware"] = latest
        _print_firmware_block(data_with_status, data_with_status.get("latest_firmware"), prefix="    ")
        print("    Actions:")
        print("    1. Status (raw)")
        print("    2. Upgrade from .bin file")
        print("    3. Commit (stop auto-rollback)")
        print("    4. Rollback to previous (dangerous)")
        print("    5. Purge inactive firmware (dangerous)")
        print("    6. Reboot")
        print("    7. Factory default (dangerous)")
        print("    0. Back")
        choice = _prompt("  Choice", "0").strip() or "0"
        if choice == "0":
            break
        if choice == "1":
            try:
                r = client.firmware_status()
                d = r.get("data") or r
                for k, v in d.items():
                    print(f"    {k}: {v}")
            except Exception as e:
                print(f"    Error: {e}")
            continue
        if choice == "2":
            path = _prompt("  Path to .bin file", "").strip()
            if not path:
                continue
            if not _confirm("  Really upgrade firmware? Device will reboot.", default_no=True):
                continue
            if not _confirm("  Type 'yes' to upload and upgrade.", default_no=True):
                continue
            try:
                client.firmware_upgrade(path)
                print("  Upgrade started; device rebooting.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        if choice == "3":
            if not _confirm("  Commit current firmware (stop rollback)?", default_no=True):
                continue
            try:
                client.firmware_commit()
                print("  Committed.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        if choice == "4":
            print("  WARNING: Rollback reverts to previous firmware. Device will reboot.")
            if not _confirm("  Really rollback?", default_no=True):
                continue
            if not _confirm("  Type 'yes' to rollback.", default_no=True):
                continue
            try:
                client.firmware_rollback()
                print("  Rollback started; device rebooting.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        if choice == "5":
            print("  WARNING: Purge removes inactive firmware; rollback will no longer be possible.")
            if not _confirm("  Really purge?", default_no=True):
                continue
            try:
                client.firmware_purge()
                print("  Purged.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        if choice == "6":
            if not _confirm("  Reboot device?", default_no=True):
                continue
            try:
                client.firmware_reboot()
                print("  Reboot sent.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        if choice == "7":
            print("  WARNING: Factory default resets all settings. soft=keep network, hard=full reset.")
            mode = _prompt("  Mode (soft/hard)", "soft").strip().lower() or "soft"
            if mode not in ("soft", "hard"):
                mode = "soft"
            if not _confirm(f"  Really factory default ({mode})? Device will reboot.", default_no=True):
                continue
            if not _confirm("  Type 'yes' to reset.", default_no=True):
                continue
            try:
                client.firmware_factory_default(mode)
                print("  Factory default sent; device rebooting.")
            except Exception as e:
                print(f"  Error: {e}")
            continue
        print("  Invalid choice.")


def _run_interactive(
    client: AxisCameraClient,
    data: dict,
    port: int,
) -> int:
    """Main interactive loop: curated settings first, advanced raw params last. Returns exit code."""
    pending_params: dict[str, str] = {}
    pending_time_zone: list[str | None] = [None]

    while True:
        print("\n--- Interactive configurator ---")
        print("  1. Stream settings (resolution, FPS, bitrate, compression)")
        print("  2. Image settings (brightness, contrast, color, etc.)")
        print("  3. Overlay / text settings")
        print("  4. Time zone")
        print("  5. Firmware (status, upgrade, reboot, ...)")
        print("  6. Storage settings")
        print("  7. Stream profiles (list, create, edit, remove)")
        print("  8. Advanced parameters (raw param browser)")
        print("  9. Show pending and apply changes")
        print("  0. Exit (discard pending)")
        choice = _prompt("Choice", "0").strip() or "0"

        if choice == "0":
            return 0
        if choice == "1":
            _interactive_curated_section(client, data, "stream", "Stream settings", pending_params)
            continue
        if choice == "2":
            _interactive_curated_section(client, data, "image", "Image settings", pending_params)
            curated = build_curated_settings(data)
            if curated.get("image_extras"):
                _interactive_curated_section(client, data, "image_extras", "Imaging (focus, zoom, WDR)", pending_params)
            continue
        if choice == "3":
            _interactive_curated_section(client, data, "overlay", "Overlay / text", pending_params)
            continue
        if choice == "4":
            _interactive_time(data, pending_time_zone)
            continue
        if choice == "5":
            _interactive_firmware(client, data)
            continue
        if choice == "6":
            _interactive_curated_section(client, data, "storage", "Storage settings", pending_params)
            continue
        if choice == "7":
            _interactive_stream_profiles(client, data, port)
            continue
        if choice == "8":
            print("\n  --- Advanced parameters (raw) ---")
            print("    1. Image (param.cgi)")
            print("    2. Network (param.cgi)")
            print("    3. Storage (param.cgi)")
            print("    4. Properties.System (param.cgi)")
            print("    0. Back")
            sub = _prompt("  Group", "0").strip() or "0"
            if sub == "1":
                _interactive_param_group(client, "Image", pending_params, data.get("param_options"))
            elif sub == "2":
                _interactive_param_group(client, "Network", pending_params, data.get("param_options"))
            elif sub == "3":
                _interactive_param_group(client, "Storage", pending_params, data.get("param_options"))
            elif sub == "4":
                _interactive_param_group(client, "Properties.System", pending_params, data.get("param_options"))
            continue
        if choice == "9":
            tz = pending_time_zone[0] if pending_time_zone else None
            if not pending_params and not tz:
                print("  No pending changes.")
                continue
            print("\n  Pending changes:")
            for k, v in pending_params.items():
                print(f"    param {k}={v}")
            if tz:
                print(f"    timeZone={tz}")
            if not _confirm("\n  Apply these changes to the camera?", default_no=True):
                continue
            if not _confirm("  Type 'yes' to write to camera.", default_no=True):
                continue
            any_err = False
            if pending_params:
                ok, errs = _apply_param_updates(client, pending_params)
                if not ok:
                    for e in errs:
                        print(f"  Param error: {e}")
                    any_err = True
                else:
                    print("  Params OK.")
            if tz:
                try:
                    _apply_time_zone_update(client, data, tz)
                    print(f"  Time zone set to {tz}.")
                except Exception as e:
                    print(f"  Time zone error: {e}")
                    any_err = True
            if not any_err:
                pending_params.clear()
                pending_time_zone[0] = None
                _refresh_data(client, data, port)
            return 1 if any_err else 0
        print("  Invalid choice.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch camera config, list changeable parameters, export or apply changes.",
    )
    parser.add_argument(
        "camera_ip",
        nargs="?",
        default=os.environ.get("AXIS_IP"),
        help="Camera IP (or set AXIS_IP)",
    )
    parser.add_argument("--user", "-u", default=os.environ.get("AXIS_USER", "root"), help="Username")
    parser.add_argument("--password", "-p", default=os.environ.get("AXIS_PASSWORD", ""), help="Password")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default 80)")
    parser.add_argument("--timeout", "-t", type=float, default=15.0, help="Request timeout (seconds)")
    parser.add_argument(
        "--output", "-o", type=Path, help="Write current config (medium subset) to this JSON file",
    )
    parser.add_argument(
        "--list-definitions",
        action="store_true",
        help="Dump param.cgi listdefinitions XML for Image, Network, Storage, Properties.System",
    )
    parser.add_argument(
        "--set-param",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        help="Param update (repeatable). Example: Image.I0.Appearance.Resolution=1920x1080",
    )
    parser.add_argument(
        "--set-timezone",
        metavar="IANA",
        help="Set time zone (IANA, e.g. America/New_York). Requires --apply to take effect.",
    )
    parser.add_argument(
        "--apply-from",
        type=Path,
        metavar="FILE",
        help="Apply changes from JSON file (params, timeZone, stream_profiles). Requires --apply.",
    )
    parser.add_argument(
        "--remove-stream-profile",
        action="append",
        metavar="NAME",
        default=[],
        help="Remove a named stream profile. Repeatable. Requires --apply.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes to the camera. Without this, only dry-run.",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run interactive menu to discover and change parameters, time zone, and firmware.",
    )
    parser.add_argument(
        "--firmware-info",
        action="store_true",
        help="Print firmware-only report (installed, latest official, update availability).",
    )
    parser.add_argument(
        "--check-latest-firmware",
        action="store_true",
        help="Force lookup of latest official firmware from Axis support pages.",
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Print expanded API capability catalog (supported, detected, future VAPIX areas).",
    )
    parser.add_argument(
        "--show-options",
        action="store_true",
        help="Print current value and allowed options for configurable settings (resolution, FPS, etc.).",
    )
    args = parser.parse_args()

    if not args.camera_ip:
        print("Error: camera_ip required (positional or AXIS_IP env)", file=sys.stderr)
        return 2
    if not args.password:
        print("Error: password required (--password or AXIS_PASSWORD env)", file=sys.stderr)
        return 2

    port = args.port if args.port is not None else 80

    # 1) Fetch current config (and param definitions when we need options)
    need_options = (
        not args.list_definitions
        and (args.interactive or args.show_options or (not args.firmware_info))
    )
    try:
        data = read_camera_config(
            args.camera_ip,
            args.user,
            args.password,
            port=port,
            timeout=args.timeout,
            fetch_param_options=need_options,
        )
        data = _to_serializable(data)
    except Exception as e:
        print(f"Error fetching config: {e}", file=sys.stderr)
        return 1

    summary = data.get("summary") or {}
    if not args.interactive and (args.firmware_info or args.check_latest_firmware or not args.output):
        data["latest_firmware"] = get_latest_firmware(summary.get("model") or "")

    # 2) Optional: list definitions
    if args.list_definitions:
        base_url = _base_url(args.camera_ip, port)
        client = AxisCameraClient(base_url, args.user, args.password, timeout=args.timeout)
        for group in PARAM_GROUPS:
            print(f"\n--- Param definitions: {group} ---\n", file=sys.stderr)
            try:
                xml = client.param_list_definitions(group=group)
                print(xml[:4096] + ("..." if len(xml) > 4096 else ""))
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
        return 0

    # 3) Interactive mode
    if args.interactive:
        base_url = _base_url(args.camera_ip, port)
        client = AxisCameraClient(base_url, args.user, args.password, timeout=args.timeout)
        return _run_interactive(client, data, port)

    # 4) Firmware-only report
    if args.firmware_info:
        print("\n--- Firmware ---\n")
        _print_firmware_block(data, data.get("latest_firmware"))
        if args.output:
            out = _medium_export(data)
            args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
            print(f"Wrote {args.output}", file=sys.stderr)
        return 0

    # 5) Config options only (current + allowed values)
    if args.show_options:
        _print_config_options(data)
        if args.output:
            out = _medium_export(data)
            args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
            print(f"Wrote {args.output}", file=sys.stderr)
        return 0

    # 6) Capability catalog
    if args.capabilities:
        _print_capability_catalog(data)

    # 7) Default: print what you can change
    _print_what_you_can_change(data)

    # 8) Export to file
    if args.output:
        out = _medium_export(data)
        args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)

    # 9) Collect and optionally apply changes
    param_updates: dict[str, str] = {}
    time_zone: str | None = None
    stream_profiles_from_file: list[dict] | None = None
    stream_profiles_to_remove: list[str] = list(args.remove_stream_profile or [])

    for s in args.set_param:
        if "=" in s:
            key, _, value = s.partition("=")
            param_updates[key.strip()] = value.strip()
        else:
            print(f"Warning: ignoring malformed --set-param '{s}' (expected KEY=VALUE)", file=sys.stderr)
    if args.set_timezone:
        time_zone = args.set_timezone.strip()

    if args.apply_from:
        if not args.apply_from.exists():
            print(f"Error: file not found: {args.apply_from}", file=sys.stderr)
            return 2
        try:
            payload = json.loads(args.apply_from.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading {args.apply_from}: {e}", file=sys.stderr)
            return 2
        param_updates.update(payload.get("params") or payload.get("param_updates") or {})
        if not time_zone:
            time_zone = payload.get("timeZone") or payload.get("time_zone")
        sp = payload.get("stream_profiles")
        if sp is None:
            sp = payload.get("stream_profiles_structured")
        if isinstance(sp, list):
            if sp and isinstance(sp[0], dict) and "values" in sp[0]:
                stream_profiles_from_file = [
                    build_stream_profile_payload(
                        name=str(p.get("name") or ""),
                        description=str(p.get("description") or ""),
                        values=(p.get("values") or {}),
                    )
                    for p in sp
                    if isinstance(p, dict) and p.get("name")
                ]
            else:
                stream_profiles_from_file = sp
        elif isinstance(sp, dict):
            # Raw API shape: {"data": {"streamProfile": [...]}}
            profiles = (sp.get("data") or {}).get("streamProfile") or []
            if isinstance(profiles, list):
                stream_profiles_from_file = profiles
        remove_names = payload.get("stream_profile_remove") or payload.get("remove_stream_profiles") or []
        if isinstance(remove_names, list):
            stream_profiles_to_remove.extend(str(name) for name in remove_names if name)

    if not param_updates and not time_zone and not stream_profiles_from_file and not stream_profiles_to_remove:
        return 0

    # Dry-run or apply
    if not args.apply:
        print("Dry-run: would apply the following (use --apply to write to camera):", file=sys.stderr)
        if param_updates:
            for k, v in param_updates.items():
                print(f"  param {k}={v}", file=sys.stderr)
        if time_zone:
            print(f"  timeZone={time_zone}", file=sys.stderr)
        if stream_profiles_from_file:
            for p in stream_profiles_from_file:
                print(f"  stream_profile {p.get('name', '?')}", file=sys.stderr)
        if stream_profiles_to_remove:
            for name in stream_profiles_to_remove:
                print(f"  remove_stream_profile {name}", file=sys.stderr)
        return 0

    base_url = _base_url(args.camera_ip, port)
    client = AxisCameraClient(base_url, args.user, args.password, timeout=args.timeout)
    any_error = False

    if param_updates:
        ok, errs = _apply_param_updates(client, param_updates)
        if not ok:
            any_error = True
            for e in errs:
                print(f"Param error: {e}", file=sys.stderr)
        else:
            print("Param updates OK", file=sys.stderr)

    if time_zone:
        try:
            _apply_time_zone_update(client, data, time_zone)
            print(f"Time zone set to {time_zone}", file=sys.stderr)
        except Exception as e:
            any_error = True
            print(f"Time zone error: {e}", file=sys.stderr)

    if stream_profiles_from_file:
        ok, errs = _apply_stream_profile_updates(client, stream_profiles_from_file)
        if not ok:
            any_error = True
            for e in errs:
                print(f"Stream profile error: {e}", file=sys.stderr)
        else:
            print("Stream profile updates OK", file=sys.stderr)

    if stream_profiles_to_remove:
        ok, errs = _apply_stream_profile_removals(client, stream_profiles_to_remove)
        if not ok:
            any_error = True
            for e in errs:
                print(f"Stream profile remove error: {e}", file=sys.stderr)
        else:
            print("Stream profile removals OK", file=sys.stderr)

    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())

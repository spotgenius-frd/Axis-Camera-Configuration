"""
Read current Axis camera config (read-only). No modifications.

Outputs: device info, params (Image, Network, Storage, System), stream profiles,
active streams, and time info. Uses the same APIs as discover plus streamstatus
and time.cgi.

Usage:
  python -m axis_bulk_config.read_config <camera_ip> --user USER --password PASS [--port PORT] [--output FILE]
  python -m axis_bulk_config.read_config --csv cameras.csv [--output-dir DIR]
  python -m axis_bulk_config.read_config --json cameras.json [--output-dir DIR]

Env: AXIS_IP, AXIS_USER, AXIS_PASSWORD (for single-camera mode).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from axis_bulk_config.client import (
    AxisCameraClient,
    parse_param_list,
)
from axis_bulk_config.network_config import normalize_network_config
from axis_bulk_config.option_catalog import build_option_catalog
from axis_bulk_config.param_options import parse_listdefinitions_xml
from axis_bulk_config.stream_profiles import normalize_stream_profiles_response

# Param groups to read (same as discover, plus ImageSource for Imaging API fields)
PARAM_GROUPS = ["Image", "ImageSource", "Network", "Storage", "Properties.System"]


def _has_dca_api(discovery: dict | None, api_id: str, major_version: str | None = None) -> bool:
    """Check whether a DCA API/version is present in /config/discover/apis output."""
    if not isinstance(discovery, dict):
        return False
    api_entry = discovery.get(api_id)
    if not isinstance(api_entry, dict):
        return False
    if major_version is None:
        return bool(api_entry)
    return major_version in api_entry


def _extract_time_zone_options(response: dict | None) -> list[str]:
    """Extract IANA time zones from Time API v2 getTimeZoneList output."""
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, dict):
            value = item.get("timeZone")
            if value:
                out.append(str(value))
    return out


def _build_network_summary(response: dict | None) -> dict[str, object] | None:
    """Normalize the network-settings.v2 system entity into a compact summary."""
    if not isinstance(response, dict):
        return None
    data = response.get("data") or {}
    if not isinstance(data, dict):
        return None
    system = data.get("system") or {}
    if not isinstance(system, dict) or not system:
        return None
    return {
        "hostname": system.get("hostname"),
        "static_hostname": system.get("staticHostname"),
        "use_dhcp_hostname": system.get("useDhcpHostname"),
    }


def _build_network_summary_from_config(network_config: dict[str, Any] | None) -> dict[str, object] | None:
    """Build the compact network summary from normalized network config."""
    if not isinstance(network_config, dict):
        return None
    if not any(
        network_config.get(key) is not None
        for key in ("hostname", "static_hostname", "use_dhcp_hostname")
    ):
        return None
    return {
        "hostname": network_config.get("hostname"),
        "static_hostname": network_config.get("static_hostname"),
        "use_dhcp_hostname": network_config.get("use_dhcp_hostname"),
    }


def _looks_like_auth_error(message: str | None) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return (
        "401" in lowered
        or "unauthorized" in lowered
        or "authentication failed" in lowered
    )


def _collect_authenticated_read_errors(out: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for group in PARAM_GROUPS:
        entry = (out.get("params") or {}).get(group)
        if isinstance(entry, dict) and isinstance(entry.get("_error"), str):
            messages.append(entry["_error"])
    for key in [
        "stream_profiles_error",
        "stream_profile_supported_versions_error",
        "stream_status_error",
        "time_info_error",
        "firmware_status_error",
        "dca_apis_error",
        "time_info_v2_error",
        "time_zone_info_v2_error",
        "time_zone_options_error",
        "network_info_error",
        "network_settings_error",
        "daynight_capabilities_error",
        "daynight_configuration_error",
        "optics_capabilities_error",
        "optics_state_error",
        "light_control_capabilities_error",
        "light_control_information_error",
        "dynamic_overlay_supported_versions_error",
        "dynamic_overlays_error",
    ]:
        value = out.get(key)
        if isinstance(value, str):
            messages.append(value)
    return messages


def _has_authenticated_read_success(out: dict[str, Any]) -> bool:
    for group in PARAM_GROUPS:
        entry = (out.get("params") or {}).get(group)
        if isinstance(entry, dict) and "_error" not in entry:
            return True
    for key in [
        "stream_profiles",
        "stream_status",
        "time_info",
        "firmware_status",
        "dca_apis",
        "time_info_v2",
        "time_zone_info_v2",
        "network_info",
        "network_settings",
        "daynight_capabilities",
        "daynight_configuration",
        "optics_capabilities",
        "optics_state",
        "light_control_capabilities",
        "light_control_information",
        "dynamic_overlay_supported_versions",
        "dynamic_overlays",
    ]:
        value = out.get(key)
        if value is not None:
            return True
    if out.get("time_zone_options"):
        return True
    return False


def _detect_auth_error(out: dict[str, Any]) -> str | None:
    if _has_authenticated_read_success(out):
        return None
    if any(_looks_like_auth_error(message) for message in _collect_authenticated_read_errors(out)):
        return "Authentication failed (wrong username or password)."
    return None


def _first_channel_item(response: dict | None) -> dict[str, Any] | None:
    """Return the first channel/item dict from APIs that respond with a data list."""
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
    return None


def _extract_intensity_range(response: dict | None) -> tuple[int | None, int | None]:
    """Return the first available intensity range from Light control getValidIntensity."""
    if not isinstance(response, dict):
        return (None, None)
    ranges = (response.get("data") or {}).get("ranges") or []
    if isinstance(ranges, list) and ranges:
        first = ranges[0]
        if isinstance(first, dict):
            return (first.get("low"), first.get("high"))
    return (None, None)


def _lookup_option_entry(option_catalog: dict[str, dict[str, Any]], *keys: str) -> dict[str, Any] | None:
    """Return the first available option_catalog entry for the provided keys."""
    for key in keys:
        if key in option_catalog:
            return option_catalog[key]
        if key.startswith("root.") and key[5:] in option_catalog:
            return option_catalog[key[5:]]
        prefixed = "root." + key
        if prefixed in option_catalog:
            return option_catalog[prefixed]
    return None


def _setting_from_option(
    option_catalog: dict[str, dict[str, Any]],
    label: str,
    group: str,
    *keys: str,
) -> dict[str, Any] | None:
    """Build a web setting entry from an option_catalog field if it exists."""
    entry = _lookup_option_entry(option_catalog, *keys)
    if not entry:
        return None
    return {
        "id": keys[0],
        "label": label,
        "group": group,
        "value": entry.get("value"),
        "inputKind": entry.get("inputKind"),
        "options": entry.get("options"),
        "min": entry.get("min"),
        "max": entry.get("max"),
        "writable": entry.get("writable", True),
        "writeType": "param",
        "writeKey": keys[0],
    }


def _setting_from_value(
    *,
    setting_id: str,
    label: str,
    group: str,
    value: Any,
    input_kind: str,
    options: list[str] | None = None,
    min_val: int | None = None,
    max_val: int | None = None,
    writable: bool = True,
    write_type: str = "param",
    write_key: str | None = None,
    guidance: str | None = None,
) -> dict[str, Any]:
    """Build a normalized web setting entry from explicit API values."""
    return {
        "id": setting_id,
        "label": label,
        "group": group,
        "value": value,
        "inputKind": input_kind,
        "options": options,
        "min": min_val,
        "max": max_val,
        "writable": writable,
        "writeType": write_type,
        "writeKey": write_key,
        "guidance": guidance,
    }


def _build_web_setting_catalog(out: dict) -> dict[str, list[dict[str, Any]]]:
    """Build curated, model-aware web settings grouped by function."""
    catalog = out.get("option_catalog") or {}
    settings: dict[str, list[dict[str, Any]]] = {
        "stream": [],
        "image": [],
        "exposure": [],
        "daynight": [],
        "light": [],
        "overlay": [],
        "storage": [],
        "focus_zoom": [],
        "firmware": [],
    }

    for item in [
        _setting_from_option(catalog, "Resolution", "stream", "root.Image.I0.Appearance.Resolution"),
        _setting_from_option(catalog, "Frame rate", "stream", "root.Image.I0.Stream.FPS"),
        _setting_from_option(catalog, "Compression", "stream", "root.Image.I0.Appearance.Compression"),
        _setting_from_option(catalog, "Bitrate", "stream", "root.Image.I0.RateControl.TargetBitrate"),
        _setting_from_option(catalog, "P-frames", "stream", "root.Image.I0.MPEG.PCount"),
        _setting_from_option(catalog, "Brightness", "image", "root.Image.I0.Appearance.Brightness", "root.ImageSource.I0.Sensor.Brightness"),
        _setting_from_option(catalog, "Contrast", "image", "root.Image.I0.Appearance.Contrast", "root.ImageSource.I0.Sensor.Contrast"),
        _setting_from_option(catalog, "Saturation", "image", "root.Image.I0.Appearance.Saturation", "root.ImageSource.I0.Sensor.ColorLevel"),
        _setting_from_option(catalog, "Sharpness", "image", "root.Image.I0.Appearance.Sharpness", "root.ImageSource.I0.Sensor.Sharpness"),
        _setting_from_option(catalog, "WDR", "image", "root.Image.I0.WDR.Enabled", "root.ImageSource.I0.Sensor.WDR"),
        _setting_from_option(catalog, "WDR level", "image", "root.ImageSource.I0.Sensor.WDRLevel"),
        _setting_from_option(catalog, "Local contrast", "image", "root.ImageSource.I0.Sensor.LocalContrast"),
        _setting_from_option(catalog, "Tone mapping", "image", "root.ImageSource.I0.Sensor.ToneMapping"),
        _setting_from_option(catalog, "White balance", "image", "root.ImageSource.I0.Sensor.WhiteBalance"),
        _setting_from_option(catalog, "Exposure mode", "exposure", "root.ImageSource.I0.Sensor.Exposure"),
        _setting_from_option(catalog, "Exposure value", "exposure", "root.ImageSource.I0.Sensor.ExposureValue"),
        _setting_from_option(catalog, "Exposure priority", "exposure", "root.ImageSource.I0.Sensor.ExposurePriority"),
        _setting_from_option(catalog, "Exposure responsiveness", "exposure", "root.ImageSource.I0.Sensor.ExposureResponsiveness"),
        _setting_from_option(catalog, "Exposure zone", "exposure", "root.ImageSource.I0.Sensor.ExposureWindow"),
        _setting_from_option(catalog, "Max shutter", "exposure", "root.ImageSource.I0.Sensor.MaxExposureTime"),
        _setting_from_option(catalog, "Min shutter", "exposure", "root.ImageSource.I0.Sensor.MinExposureTime"),
        _setting_from_option(catalog, "Max gain", "exposure", "root.ImageSource.I0.Sensor.MaxGain"),
        _setting_from_option(catalog, "Min gain", "exposure", "root.ImageSource.I0.Sensor.MinGain"),
        _setting_from_option(catalog, "Overlay enabled", "overlay", "root.Image.I0.Overlay.Enabled"),
        _setting_from_option(catalog, "Text enabled", "overlay", "root.Image.I0.Text.TextEnabled"),
        _setting_from_option(catalog, "Overlay text", "overlay", "root.Image.I0.Text.String"),
        _setting_from_option(catalog, "Show clock", "overlay", "root.Image.I0.Text.ClockEnabled"),
        _setting_from_option(catalog, "Show date", "overlay", "root.Image.I0.Text.DateEnabled"),
        _setting_from_option(catalog, "Text position", "overlay", "root.Image.I0.Text.Position"),
        _setting_from_option(catalog, "Text size", "overlay", "root.Image.I0.Text.TextSize"),
        _setting_from_option(catalog, "SD card enabled", "storage", "root.Storage.S0.Enabled"),
        _setting_from_option(catalog, "Cleanup level", "storage", "root.Storage.S0.CleanupLevel"),
        _setting_from_option(catalog, "Cleanup max age", "storage", "root.Storage.S0.CleanupMaxAge"),
        _setting_from_option(catalog, "Cleanup policy", "storage", "root.Storage.S0.CleanupPolicyActive"),
    ]:
        if item:
            settings[item["group"]].append(item)

    daynight_config = _first_channel_item(out.get("daynight_configuration"))
    if daynight_config:
        if "DayNightShiftLevel" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.DayNightShiftLevel",
                    label="Day to night threshold",
                    group="daynight",
                    value=daynight_config.get("DayNightShiftLevel"),
                    input_kind="range",
                    min_val=0,
                    max_val=100,
                    write_type="daynight",
                    write_key="DayNightShiftLevel",
                )
            )
        if "DayNightDwellTime" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.DayNightDwellTime",
                    label="Day to night dwell",
                    group="daynight",
                    value=daynight_config.get("DayNightDwellTime"),
                    input_kind="range",
                    min_val=1,
                    max_val=600,
                    write_type="daynight",
                    write_key="DayNightDwellTime",
                )
            )
        if "NightDayDwellTime" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.NightDayDwellTime",
                    label="Night to day dwell",
                    group="daynight",
                    value=daynight_config.get("NightDayDwellTime"),
                    input_kind="range",
                    min_val=1,
                    max_val=600,
                    write_type="daynight",
                    write_key="NightDayDwellTime",
                )
            )
        if "NightDayShiftLevel" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.NightDayShiftLevel",
                    label="Night to day threshold",
                    group="daynight",
                    value=daynight_config.get("NightDayShiftLevel"),
                    input_kind="range",
                    min_val=0,
                    max_val=100,
                    write_type="daynight",
                    write_key="NightDayShiftLevel",
                )
            )
        if "Autotune" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.Autotune",
                    label="Day/Night autotune",
                    group="daynight",
                    value=daynight_config.get("Autotune"),
                    input_kind="select",
                    options=["true", "false"],
                    write_type="daynight",
                    write_key="Autotune",
                )
            )
        if "NightFilter" in daynight_config:
            settings["daynight"].append(
                _setting_from_value(
                    setting_id="daynight.NightFilter",
                    label="Night filter",
                    group="daynight",
                    value=daynight_config.get("NightFilter"),
                    input_kind="select",
                    options=["clear", "irpass"],
                    write_type="daynight",
                    write_key="NightFilter",
                )
            )

    optics = (((out.get("optics_state") or {}).get("data") or {}).get("optics") or [])
    if isinstance(optics, list) and optics:
        first = optics[0]
        if isinstance(first, dict):
            settings["focus_zoom"].append(
                _setting_from_value(
                    setting_id="optics.zoom",
                    label="Zoom",
                    group="focus_zoom",
                    value=first.get("magnification"),
                    input_kind="text",
                    writable=False,
                    write_type="guided",
                    guidance="Log in to the camera UI to adjust zoom.",
                )
            )
            settings["focus_zoom"].append(
                _setting_from_value(
                    setting_id="optics.focus",
                    label="Focus",
                    group="focus_zoom",
                    value=first.get("focusPosition"),
                    input_kind="text",
                    writable=False,
                    write_type="guided",
                    guidance="Log in to the camera UI to adjust focus.",
                )
            )
            if first.get("irCutFilterState") is not None:
                settings["daynight"].append(
                    _setting_from_value(
                        setting_id="optics.irCutFilterState",
                        label="IR cut filter",
                        group="daynight",
                        value=first.get("irCutFilterState"),
                        input_kind="select",
                        options=["auto", "on", "off"],
                        write_type="ir_cut_filter",
                        write_key=str(first.get("opticsId") or "0"),
                    )
                )

    light_info = (((out.get("light_control_information") or {}).get("data") or {}).get("items") or [])
    if isinstance(light_info, list) and light_info:
        first_light = light_info[0]
        if isinstance(first_light, dict):
            light_id = str(first_light.get("lightID") or "")
            intensity_min, intensity_max = _extract_intensity_range(out.get("light_control_valid_intensity"))
            settings["light"].append(
                _setting_from_value(
                    setting_id="light.enabled",
                    label="IR / light enabled",
                    group="light",
                    value=first_light.get("enabled"),
                    input_kind="select",
                    options=["true", "false"],
                    write_type="light_enabled",
                    write_key=light_id,
                )
            )
            settings["light"].append(
                _setting_from_value(
                    setting_id="light.state",
                    label="IR / light state",
                    group="light",
                    value=first_light.get("lightState"),
                    input_kind="select",
                    options=["true", "false"],
                    write_type="light_state",
                    write_key=light_id,
                )
            )
            if intensity_min is not None or intensity_max is not None:
                settings["light"].append(
                    _setting_from_value(
                        setting_id="light.intensity",
                        label="Light intensity",
                        group="light",
                        value=((out.get("light_control_manual_intensity") or {}).get("data") or {}).get("intensity"),
                        input_kind="range",
                        min_val=intensity_min,
                        max_val=intensity_max,
                        write_type="light_intensity",
                        write_key=light_id,
                    )
                )
            if first_light.get("synchronizeDayNightMode") is not None:
                settings["light"].append(
                    _setting_from_value(
                        setting_id="light.daynightSync",
                        label="Light sync with day/night",
                        group="light",
                        value=first_light.get("synchronizeDayNightMode"),
                        input_kind="select",
                        options=["true", "false"],
                        write_type="light_sync",
                        write_key=light_id,
                    )
                )

    firmware = out.get("firmware_status") or {}
    fw_data = firmware.get("data") if isinstance(firmware, dict) else None
    if isinstance(fw_data, dict):
        settings["firmware"].append(
            _setting_from_value(
                setting_id="firmware.active",
                label="Installed firmware",
                group="firmware",
                value=fw_data.get("activeFirmwareVersion"),
                input_kind="text",
                writable=False,
                write_type="guided",
            )
        )

    return {group: values for group, values in settings.items() if values}


def _build_capabilities(out: dict) -> dict[str, object]:
    """Build a compact capabilities object for CLI/API consumers."""
    dca_apis = out.get("dca_apis")
    return {
        "legacy": {
            "param_cgi": True,
            "streamprofile_cgi": out.get("stream_profiles") is not None,
            "time_cgi": out.get("time_info") is not None,
            "firmware_cgi": out.get("firmware_status") is not None,
            "basicdeviceinfo_cgi": out.get("device_info") is not None,
        },
        "stream_profiles": {
            "supported_versions": out.get("stream_profile_supported_versions"),
            "has_profiles": bool(out.get("stream_profiles_structured")),
            "can_remove": out.get("stream_profile_supported_versions") is not None,
        },
        "features": {
            "daynight": out.get("daynight_configuration") is not None,
            "light_control": out.get("light_control_information") is not None,
            "optics": out.get("optics_state") is not None,
            "image_source": "_error" not in str((out.get("params") or {}).get("ImageSource", "")),
        },
        "dca": {
            "discovery": dca_apis is not None,
            "time_v2": _has_dca_api(dca_apis, "time", "v2") or out.get("time_info_v2") is not None,
            "network_settings_v2": _has_dca_api(dca_apis, "network-settings", "v2") or out.get("network_settings") is not None,
            "basic_device_info_v2beta": _has_dca_api(dca_apis, "basic-device-info"),
        },
        "identity": {
            "model_firmware_source": "basicdeviceinfo.cgi",
            "advisory": "Treat device identity as advisory metadata when gating newer DCA-only features.",
        },
    }


def _is_enabled_value(value: Any) -> bool:
    """Interpret common Axis enabled-state strings as booleans."""
    if value is None:
        return False
    return str(value).strip().lower() in {"yes", "true", "1", "on"}


def _derive_overlay_active(overlay_summary: dict[str, Any]) -> bool:
    """Return True when any visible overlay element is active on the primary channel."""
    if not isinstance(overlay_summary, dict):
        return False
    if any(
        _is_enabled_value(overlay_summary.get(key))
        for key in ("Enabled", "TextEnabled", "ClockEnabled", "DateEnabled")
    ):
        return True
    overlay_text = overlay_summary.get("String")
    return isinstance(overlay_text, str) and bool(overlay_text.strip())


def _visible_dynamic_overlays(response: dict | None) -> list[dict[str, Any]]:
    """Extract visible text/image overlays from the Dynamic Overlay API response."""
    if not isinstance(response, dict):
        return []
    data = response.get("data") or {}
    if not isinstance(data, dict):
        return []
    visible: list[dict[str, Any]] = []
    for kind in ("textOverlays", "imageOverlays"):
        overlays = data.get(kind) or []
        if not isinstance(overlays, list):
            continue
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            if overlay.get("visible", True) is False:
                continue
            visible.append({"kind": kind, **overlay})
    return visible


def _base_url(camera_ip: str, port: int | None, scheme: str = "http") -> str:
    normalized_scheme = "https" if str(scheme).lower() == "https" else "http"
    default_port = 443 if normalized_scheme == "https" else 80
    if port and port != default_port:
        return f"{normalized_scheme}://{camera_ip}:{port}"
    return f"{normalized_scheme}://{camera_ip}"


def read_camera_config(
    camera_ip: str,
    username: str,
    password: str,
    port: int | None = None,
    scheme: str = "http",
    timeout: float = 15.0,
    fetch_param_options: bool = False,
) -> dict:
    """Read all config from one camera. No writes. If fetch_param_options=True, also fetch listdefinitions and set out['param_options']."""
    base_url = _base_url(camera_ip, port or (443 if scheme == "https" else 80), scheme)
    client = AxisCameraClient(base_url, username, password, timeout=timeout)
    out = {
        "camera_ip": camera_ip,
        "device_info": None,
        "params": {},
        "stream_profiles": None,
        "stream_status": None,
        "time_info": None,
    }

    # Device info (no auth)
    try:
        out["device_info"] = client.basicdeviceinfo()
    except Exception as e:
        out["device_info_error"] = str(e)

    # Params per group
    for group in PARAM_GROUPS:
        try:
            text = client.param_list(group=group)
            out["params"][group] = parse_param_list(text)
        except Exception as e:
            out["params"][group] = {"_error": str(e)}

    # Stream profiles
    try:
        out["stream_profiles"] = client.streamprofile_list()
        out["stream_profiles_structured"] = normalize_stream_profiles_response(out["stream_profiles"])
    except Exception as e:
        out["stream_profiles_error"] = str(e)

    try:
        sp_versions = client.streamprofile_get_supported_versions()
        versions = ((sp_versions.get("data") or {}).get("apiVersions")) or []
        if isinstance(versions, list) and versions:
            out["stream_profile_supported_versions"] = versions
    except Exception as e:
        out["stream_profile_supported_versions_error"] = str(e)

    # Active streams
    try:
        out["stream_status"] = client.streamstatus_get_all()
    except Exception as e:
        out["stream_status_error"] = str(e)

    # Time (from reference script: time.cgi getDateTimeInfo)
    try:
        out["time_info"] = client.get_time_info()
    except Exception as e:
        out["time_info_error"] = str(e)

    # Firmware status (active/inactive/committed/last upgrade)
    try:
        out["firmware_status"] = client.firmware_status()
    except Exception as e:
        out["firmware_status_error"] = str(e)

    # DCA discovery and selected DCA APIs
    try:
        out["dca_apis"] = client.dca_discover_apis()
    except Exception as e:
        out["dca_apis_error"] = str(e)

    try:
        out["time_info_v2"] = client.time_v2_get_all()
    except Exception as e:
        out["time_info_v2_error"] = str(e)

    try:
        out["time_zone_info_v2"] = client.time_v2_get_time_zone()
    except Exception as e:
        out["time_zone_info_v2_error"] = str(e)

    try:
        out["time_zone_options"] = _extract_time_zone_options(client.time_v2_get_time_zone_list())
    except Exception as e:
        out["time_zone_options_error"] = str(e)

    try:
        out["network_info"] = client.network_settings_get_info()
    except Exception as e:
        out["network_info_error"] = str(e)

    try:
        out["network_settings"] = client.network_settings_v2_get()
        out["network_summary"] = _build_network_summary(out["network_settings"])
    except Exception as e:
        out["network_settings_error"] = str(e)

    out["network_config"] = normalize_network_config(
        out.get("network_info"),
        (out.get("params") or {}).get("Network"),
        out.get("network_settings"),
    )
    if out.get("network_summary") is None:
        out["network_summary"] = _build_network_summary_from_config(out.get("network_config"))

    try:
        out["daynight_capabilities"] = client.daynight_get_capabilities()
    except Exception as e:
        out["daynight_capabilities_error"] = str(e)

    try:
        out["daynight_configuration"] = client.daynight_get_configuration()
    except Exception as e:
        out["daynight_configuration_error"] = str(e)

    try:
        out["optics_capabilities"] = client.opticscontrol_get_capabilities()
    except Exception as e:
        out["optics_capabilities_error"] = str(e)

    try:
        out["optics_state"] = client.opticscontrol_get_optics()
    except Exception as e:
        out["optics_state_error"] = str(e)

    try:
        out["light_control_capabilities"] = client.lightcontrol_get_service_capabilities()
    except Exception as e:
        out["light_control_capabilities_error"] = str(e)

    try:
        out["light_control_information"] = client.lightcontrol_get_light_information()
        items = (((out.get("light_control_information") or {}).get("data") or {}).get("items") or [])
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict) and first.get("lightID"):
                out["light_control_valid_intensity"] = client.lightcontrol_get_valid_intensity(str(first.get("lightID")))
    except Exception as e:
        out["light_control_information_error"] = str(e)

    try:
        out["dynamic_overlay_supported_versions"] = client.dynamicoverlay_get_supported_versions()
    except Exception as e:
        out["dynamic_overlay_supported_versions_error"] = str(e)

    try:
        out["dynamic_overlays"] = client.dynamicoverlay_list()
    except Exception as e:
        out["dynamic_overlays_error"] = str(e)

    # Optional: parameter definitions (current value, type, options/range per param) + unified option catalog
    if fetch_param_options:
        merged: dict = {}
        for group in PARAM_GROUPS:
            try:
                xml_text = client.param_list_definitions(group=group)
                merged.update(parse_listdefinitions_xml(xml_text))
            except Exception:
                pass
        out["param_options"] = merged
        # Enrich with Properties.Image.Resolution and capturemode for dropdown-ready options
        supported_resolutions: list[str] = []
        capturemode_response: dict | None = None
        try:
            supported_resolutions = client.get_supported_resolutions()
        except Exception:
            pass
        try:
            capturemode_response = client.capturemode_get_modes()
        except Exception:
            pass
        out["option_catalog"] = build_option_catalog(
            merged,
            supported_resolutions,
            capturemode_response,
        )

    out["summary"] = build_summary(out)
    out["web_settings_catalog"] = _build_web_setting_catalog(out)
    out["capabilities"] = _build_capabilities(out)
    out["auth_error"] = _detect_auth_error(out)
    return out


def build_summary(out: dict) -> dict:
    """Build a structured summary from device_info, params, stream_profiles, and Storage.

    - summary.image: from params Image.I0 (primary/live view) – resolution, fps, compression.
    - summary.stream: list of all stream profiles (named presets); each can have different resolution/fps/codec.
    """
    summary: dict = {
        "model": None,
        "firmware": None,
        "image": {},
        "stream": [],
        "overlay": {},
        "overlay_active": False,
        "sd_card": "unknown",
    }
    # Model and firmware from device_info
    di = out.get("device_info") or {}
    pl = (di.get("data") or {}).get("propertyList") or {}
    if isinstance(pl, dict):
        summary["model"] = pl.get("ProdFullName") or pl.get("ProdNbr")
        summary["firmware"] = pl.get("Version")

    # Params: flat key-value, e.g. root.Image.I0.Appearance.Resolution=1920x1080
    params_image = (out.get("params") or {}).get("Image") or {}
    params_storage = (out.get("params") or {}).get("Storage") or {}
    if isinstance(params_image, dict) and "_error" not in params_image:
        # Image: resolution, FPS, compression, appearance; optional Zoom, Focus, WDR
        for k, v in params_image.items():
            if not k.startswith("root.Image."):
                continue
            rest = k.replace("root.Image.", "")
            if ".Appearance.Resolution" in rest:
                summary["image"]["resolution"] = summary["image"].get("resolution") or v
            if ".Appearance.Compression" in rest:
                summary["image"]["compression"] = summary["image"].get("compression") or v
            if ".Stream.FPS" in rest or "Stream.FPS" in rest:
                summary["image"]["fps"] = summary["image"].get("fps") or v
            if "Brightness" in rest or "Contrast" in rest or "Saturation" in rest or "Sharpness" in rest:
                summary["image"].setdefault("appearance", {})[rest.split(".")[-1]] = v
            if "Zoom" in k:
                summary["image"].setdefault("zoom", {})[k.split(".")[-1]] = v
            if "Focus" in k:
                summary["image"].setdefault("focus", {})[k.split(".")[-1]] = v
            if "WDR" in k:
                summary["image"].setdefault("wdr", {})[k.split(".")[-1]] = v
        # Overlay: Text.* and Overlay.Enabled
        for k, v in params_image.items():
            if not k.startswith("root.Image.I0."):
                continue
            if "Text." in k or (k.endswith("Overlay.Enabled") or ".Overlay.Enabled" in k):
                key = k.split(".")[-1] if "." in k else k
                summary["overlay"][key] = v
        summary["overlay_active"] = _derive_overlay_active(summary["overlay"])
        if _visible_dynamic_overlays(out.get("dynamic_overlays")):
            summary["overlay_active"] = True
    if isinstance(params_storage, dict) and "_error" not in params_storage:
        # SD: S0 with DiskID=SD_DISK or DeviceNode containing mmcblk/sd_disk; require Enabled=yes for "yes"
        found_s0_sd = False
        s0_enabled = None
        for k, v in params_storage.items():
            if "S0." not in k and ".S0." not in k:
                continue
            if "S0.Enabled" in k or k.endswith("Storage.S0.Enabled"):
                s0_enabled = str(v).lower() in ("yes", "true", "1")
            if "DiskID" in k and ("SD_DISK" in v or "sd_disk" in str(v).lower()):
                found_s0_sd = True
            if "DeviceNode" in k and ("mmcblk" in v or "sd_disk" in str(v).lower()):
                found_s0_sd = True
        if found_s0_sd:
            summary["sd_card"] = "yes" if s0_enabled else "no"
        # else remains "unknown"

    # Stream profiles: prefer structured normalized profiles when available.
    structured_profiles = out.get("stream_profiles_structured") or []
    if isinstance(structured_profiles, list) and structured_profiles:
        for profile in structured_profiles:
            if not isinstance(profile, dict):
                continue
            stream_entry = {"name": profile.get("name", "unknown")}
            values = profile.get("values") or {}
            if isinstance(values, dict):
                for key, value in values.items():
                    stream_entry[str(key)] = value
            summary["stream"].append(stream_entry)
    else:
        sp = out.get("stream_profiles") or {}
        profiles = (sp.get("data") or {}).get("streamProfile") or []
        if isinstance(profiles, list):
            for p in profiles:
                if not isinstance(p, dict):
                    continue
                name = p.get("name") or p.get("streamProfileName") or "unknown"
                params_qs = p.get("parameters") or ""
                parsed = parse_qs(params_qs) if isinstance(params_qs, str) else {}
                stream_entry = {"name": name}
                for pk, pv in parsed.items():
                    stream_entry[pk] = pv[0] if isinstance(pv, list) and len(pv) == 1 else pv
                summary["stream"].append(stream_entry)

    return summary


def _to_serializable(obj):
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(x) for x in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read current Axis camera config (read-only, no modifications)."
    )
    parser.add_argument(
        "camera_ip",
        nargs="?",
        default=os.environ.get("AXIS_IP"),
        help="Camera IP (or set AXIS_IP; omit if using --csv)",
    )
    parser.add_argument("--user", "-u", default=os.environ.get("AXIS_USER", "root"), help="Username")
    parser.add_argument("--password", "-p", default=os.environ.get("AXIS_PASSWORD", ""), help="Password")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default 80); use for VPN/remote access")
    parser.add_argument("--output", "-o", type=Path, help="Write JSON to this file")
    parser.add_argument("--summary-only", action="store_true", help="Print only summary (model, firmware, image, stream, overlay, sd_card)")
    parser.add_argument("--medium", action="store_true", help="Summary + time_info (balanced view; no full params or live stream list)")
    parser.add_argument("--csv", type=Path, help="Read cameras from CSV (ip,port,username,password); port optional")
    parser.add_argument("--json", type=Path, help="Read cameras from JSON array (ip,port,username,password); port optional")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="With --csv/--json, write files here (default: .)")
    parser.add_argument("--timeout", "-t", type=float, default=15.0, help="Request timeout")
    args = parser.parse_args()

    def _parse_port(v) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 80
        try:
            return int(v)
        except (ValueError, TypeError):
            return 80

    if args.csv or args.json:
        rows: list[dict] = []
        if args.csv:
            if not args.csv.exists():
                print(f"Error: CSV not found: {args.csv}", file=sys.stderr)
                return 2
            import csv as csv_module
            with open(args.csv, newline="", encoding="utf-8-sig") as f:
                reader = csv_module.DictReader(f)
                for row in reader:
                    row = {k.strip().lower().lstrip("\ufeff"): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                    if row.get("ip") and row.get("password"):
                        rows.append(row)
        else:
            if not args.json.exists():
                print(f"Error: JSON not found: {args.json}", file=sys.stderr)
                return 2
            raw = json.loads(args.json.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                print("Error: JSON must be an array of camera objects", file=sys.stderr)
                return 2
            for obj in raw:
                if isinstance(obj, dict) and obj.get("ip") and obj.get("password"):
                    rows.append({k.lower(): v for k, v in obj.items()})
        if not rows:
            print("Error: no valid rows (need ip, username, password)", file=sys.stderr)
            return 2
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for r in rows:
            ip = (r.get("ip") or "").strip()
            port = _parse_port(r.get("port"))
            user = (r.get("username") or r.get("user") or "root").strip()
            password = (r.get("password") or "").strip()
            print(f"Reading config from {ip}" + (f":{port}" if port != 80 else "") + "...", file=sys.stderr)
            try:
                data = read_camera_config(ip, user, password, port=port, timeout=args.timeout)
                out_path = args.output_dir / f"config_{ip.replace('.', '_')}.json"
                to_write = data
                if args.medium:
                    to_write = {
                        "camera_ip": data.get("camera_ip"),
                        "summary": data.get("summary"),
                        "time_info": data.get("time_info"),
                    }
                elif args.summary_only:
                    to_write = {"camera_ip": data.get("camera_ip"), "summary": data.get("summary")}
                out_path.write_text(json.dumps(_to_serializable(to_write), indent=2), encoding="utf-8")
                print(f"  Wrote {out_path}", file=sys.stderr)
            except Exception as e:
                print(f"  Error: {e}", file=sys.stderr)
        return 0

    if not args.camera_ip:
        print("Error: camera_ip required (positional, AXIS_IP, or use --csv)", file=sys.stderr)
        return 2
    if not args.password:
        print("Error: password required (--password or AXIS_PASSWORD)", file=sys.stderr)
        return 2

    port = (args.port if args.port is not None else 80)
    data = read_camera_config(args.camera_ip, args.user, args.password, port=port, timeout=args.timeout)
    data = _to_serializable(data)
    if args.medium:
        out = {
            "camera_ip": data.get("camera_ip"),
            "summary": data.get("summary"),
            "time_info": data.get("time_info"),
        }
        json_str = json.dumps(out, indent=2)
    elif args.summary_only:
        out = {"camera_ip": data.get("camera_ip"), "summary": data.get("summary")}
        json_str = json.dumps(out, indent=2)
    else:
        json_str = json.dumps(data, indent=2)
    if args.output:
        args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Config written to {args.output}", file=sys.stderr)
    if not args.output or args.summary_only or args.medium:
        print(json_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())

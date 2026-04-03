"""
Unified option catalog: merge listdefinitions, Properties.Image.Resolution,
and capturemode.cgi so curated settings get real selectable values (e.g. Resolution dropdown).
Output is JSON-friendly for CLI and future web UI.
"""

from __future__ import annotations

import re
from typing import Any

# Param key used for stream resolution (Image.I0.Appearance.Resolution).
RESOLUTION_PARAM_KEY = "root.Image.I0.Appearance.Resolution"


def _resolution_from_capture_description(description: str) -> str | None:
    """Extract resolution string from capture mode description, e.g. '1920x1080 (16:9) @ 30/60 fps' -> '1920x1080'."""
    if not description:
        return None
    # Match patterns like 1920x1080 or 1280x720
    m = re.match(r"(\d+\s*x\s*\d+)", description.strip(), re.IGNORECASE)
    if m:
        return m.group(1).replace(" ", "").lower()
    return None


def _capture_modes_to_resolution_options(capturemode_data: dict[str, Any] | None) -> list[str]:
    """Extract unique resolution strings from getCaptureModes response (descriptions)."""
    if not capturemode_data:
        return []
    data = capturemode_data.get("data")
    if not isinstance(data, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for channel_block in data:
        modes = channel_block.get("captureMode") if isinstance(channel_block, dict) else None
        if not isinstance(modes, list):
            continue
        for mode in modes:
            desc = mode.get("description") if isinstance(mode, dict) else None
            res = _resolution_from_capture_description(str(desc) if desc else "")
            if res and res not in seen:
                seen.add(res)
                result.append(res)
    return result


def build_option_catalog(
    param_options: dict[str, dict[str, Any]],
    supported_resolutions: list[str],
    capturemode_response: dict[str, Any] | None = None,
    resolution_param_key: str = RESOLUTION_PARAM_KEY,
) -> dict[str, dict[str, Any]]:
    """
    Build a unified option catalog from listdefinitions + Properties.Image.Resolution + capturemode.

    Priority for options:
      1. listdefinitions enum/bool options or int min/max
      2. For Resolution param: supported_resolutions (Properties.Image.Resolution)
      3. From capturemode: resolution strings parsed from descriptions (fallback)

    Returns dict: param_key -> {
      value, niceName, writable,
      inputKind: "select" | "range" | "text",
      options: list[str] | None,   # for select
      min: int | None, max: int | None,  # for range
      sources: list[str],  # e.g. ["listdefinitions"], ["properties"], ["listdefinitions","properties"]
    }
    """
    catalog: dict[str, dict[str, Any]] = {}
    capture_resolutions = _capture_modes_to_resolution_options(capturemode_response) if capturemode_response else []

    for param_key, meta in param_options.items():
        value = meta.get("value", "")
        nice_name = meta.get("niceName", param_key.split(".")[-1])
        writable = meta.get("writable", True)
        kind = meta.get("kind", "string")
        options = meta.get("options")
        min_val = meta.get("min")
        max_val = meta.get("max")
        sources: list[str] = ["listdefinitions"]

        # Override Resolution options when listdefinitions has no enum
        if param_key == resolution_param_key:
            if options and len(options) > 0:
                pass  # keep listdefinitions options
            elif supported_resolutions:
                options = list(supported_resolutions)
                if "listdefinitions" not in sources or not meta.get("options"):
                    sources = ["properties"]
                else:
                    sources = ["listdefinitions", "properties"]
            elif capture_resolutions:
                options = list(capture_resolutions)
                sources = ["capturemode"]

        # Determine inputKind and normalize options/range
        if options is not None and isinstance(options, list) and len(options) > 0:
            input_kind = "select"
            # ensure options are strings for JSON
            options = [str(x) for x in options]
        elif kind == "int" and (min_val is not None or max_val is not None):
            input_kind = "range"
            options = None
        else:
            input_kind = "text"
            options = None
            min_val = None
            max_val = None

        catalog[param_key] = {
            "value": value,
            "niceName": nice_name,
            "writable": writable,
            "inputKind": input_kind,
            "options": options,
            "min": min_val,
            "max": max_val,
            "sources": sources,
        }

    # Attach raw capture mode data for consumers that want FPS/resolution combos (e.g. future UI).
    if capturemode_response and isinstance(capturemode_response.get("data"), list):
        catalog["_capture_modes"] = {
            "value": None,
            "niceName": "Capture modes",
            "writable": False,
            "inputKind": "text",
            "options": None,
            "min": None,
            "max": None,
            "sources": ["capturemode"],
            "data": capturemode_response["data"],
        }

    return catalog


def get_param_catalog_entry(
    catalog: dict[str, dict[str, Any]],
    param_key: str,
) -> dict[str, Any] | None:
    """Look up catalog entry by param key; try with and without root. prefix."""
    if not catalog:
        return None
    if param_key in catalog:
        return catalog[param_key]
    if param_key.startswith("root."):
        return catalog.get(param_key[5:]) or catalog.get(param_key)
    return catalog.get("root." + param_key)


def format_catalog_entry_display(entry: dict[str, Any]) -> str:
    """Human-readable allowed values for a catalog entry, e.g. '(options: a, b, c)' or '(range: 0-100)'."""
    if not entry:
        return ""
    options = entry.get("options")
    if options is not None and isinstance(options, list) and len(options) <= 20:
        return f"(options: {', '.join(str(x) for x in options)})"
    min_v = entry.get("min")
    max_v = entry.get("max")
    if min_v is not None and max_v is not None:
        return f"(range: {min_v}-{max_v})"
    if min_v is not None:
        return f"(min: {min_v})"
    if max_v is not None:
        return f"(max: {max_v})"
    return ""

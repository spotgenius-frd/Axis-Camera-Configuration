"""
Helpers for Axis streamprofile.cgi payloads.

Stream profiles store their settings in a query-string-like "parameters" field.
This module keeps parsing/building logic in one place so both the CLI and web
API can work with structured profile data.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode


COMMON_STREAM_PROFILE_FIELDS: list[tuple[str, str]] = [
    ("resolution", "Resolution"),
    ("fps", "FPS"),
    ("compression", "Compression"),
    ("videocodec", "Video codec"),
    ("videobitrate", "Video bitrate"),
    ("rotation", "Rotation"),
    ("audio", "Audio"),
    ("text", "Text overlay"),
    ("textstring", "Overlay text"),
    ("signedvideo", "Signed video"),
]


def parse_stream_profile_parameters(parameters: str) -> dict[str, str]:
    """Parse a stream profile parameters string into a flat dict."""
    if not parameters:
        return {}
    return {k: v for k, v in parse_qsl(parameters, keep_blank_values=True)}


def build_stream_profile_parameters(values: dict[str, Any]) -> str:
    """
    Build a stream profile parameters string from a flat dict.

    Empty/None values are omitted except for explicitly empty overlay text fields.
    """
    items: list[tuple[str, str]] = []
    for key, raw_value in values.items():
        if raw_value is None:
            continue
        value = str(raw_value)
        if value == "" and key not in {"textstring"}:
            continue
        items.append((key, value))
    return urlencode(items)


def normalize_stream_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize one raw stream profile entry to a JSON-friendly structure."""
    name = str(profile.get("name") or profile.get("streamProfileName") or "unknown")
    description = str(profile.get("description") or "")
    parameters_raw = str(profile.get("parameters") or "")
    values = parse_stream_profile_parameters(parameters_raw)
    return {
        "name": name,
        "description": description,
        "parameters": parameters_raw,
        "values": values,
    }


def normalize_stream_profiles_response(response: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize a streamprofile.cgi list response into structured profiles."""
    if not isinstance(response, dict):
        return []
    profiles = (response.get("data") or {}).get("streamProfile") or []
    if not isinstance(profiles, list):
        return []
    return [normalize_stream_profile(profile) for profile in profiles if isinstance(profile, dict)]


def build_stream_profile_payload(
    *,
    name: str,
    description: str = "",
    values: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build one streamprofile.cgi payload object."""
    return {
        "name": name,
        "description": description,
        "parameters": build_stream_profile_parameters(values or {}),
    }


def merge_stream_profile_values(existing: dict[str, str], updates: dict[str, Any]) -> dict[str, str]:
    """Merge updates into an existing parameters map, dropping keys set to empty."""
    merged = dict(existing)
    for key, raw_value in updates.items():
        if raw_value is None:
            continue
        value = str(raw_value).strip()
        if value == "":
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged

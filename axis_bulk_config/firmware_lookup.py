"""
Look up latest official Axis firmware for a camera model from Axis support pages.
Used by config_explorer to show installed vs latest and optional download URL.
"""

import re
from typing import Any

import requests


def normalize_model_to_product_code(model: str) -> str | None:
    """
    Extract Axis product code from full model name.
    e.g. "AXIS Q1786-LE Network Camera" -> "Q1786-LE", "AXIS P3275-LVE" -> "P3275-LVE".
    """
    if not model or not isinstance(model, str):
        return None
    s = model.strip()
    # Match AXIS <Code> or just <Code> (e.g. ProdNbr "Q1786-LE")
    m = re.search(r"(?:AXIS\s+)?([A-Z0-9]+-[A-Z0-9]+(?:\s|$|,))", s, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(",")
    # Fallback: take first token that looks like CODE-NNN
    m = re.search(r"([A-Z]{1,3}\d+-[A-Z0-9]+)", s, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _support_url(product_code: str) -> str:
    """Build Axis product support page URL from product code."""
    slug = product_code.lower().replace(" ", "-")
    return f"https://www.axis.com/products/axis-{slug}/support"


def get_latest_firmware(model: str, timeout: float = 10) -> dict[str, Any] | None:
    """
    Look up latest official firmware for the given model from Axis support page.
    Returns dict with version, download_url, checksum (optional), or None if unavailable.
    """
    product_code = normalize_model_to_product_code(model)
    if not product_code:
        return None
    url = _support_url(product_code)
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Axis-Config-Tool/1.0"})
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return None
    # First "Version X.XX.XXX" is typically the latest
    version_m = re.search(r"Version\s+(\d+\.\d+\.\d+)\s*[-–]", text)
    if not version_m:
        return None
    version = version_m.group(1)
    # First .bin download link on axis.com
    bin_m = re.search(r"(https?://(?:www\.)?axis\.com/ftp/pub/axis/software/[^\s\"']+\.bin)", text)
    download_url = bin_m.group(1) if bin_m else None
    # Integrity checksum (SHA256 hex) near the first firmware block
    checksum_m = re.search(r"Integrity checksum:\s*([a-fA-F0-9]{64})", text)
    checksum = checksum_m.group(1) if checksum_m else None
    return {
        "version": version,
        "download_url": download_url,
        "checksum": checksum,
        "product_code": product_code,
    }

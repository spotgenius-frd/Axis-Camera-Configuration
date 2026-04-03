"""Preset data structures and registry."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Preset:
    """A named preset: param.cgi updates and stream profile create/update payloads."""

    id: str
    name: str
    description: str
    params: dict[str, str] = field(default_factory=dict)
    stream_profiles: list[dict[str, str]] = field(default_factory=list)
    # Optional: skip params that are read-only on some models (key = param name).
    skip_params_if_missing: bool = False


# Stream profile parameter strings (Axis streamprofile.cgi format).
# See: https://developer.axis.com/vapix/network-video/stream-profiles/

LPR_STREAM_PARAMS = (
    "resolution=1920x1080&fps=30&videocodec=h264"
    "&compression=30"
    "&signedvideo=off"
)
# Bitrate/zipstream may be in param.cgi or in stream parameters depending on model.
LPR_STREAM_PROFILE = {
    "name": "SpotGenius LPR",
    "description": "1080p 30fps H.264 for LPR",
    "parameters": LPR_STREAM_PARAMS,
}

PANORAMIC_STREAM_PARAMS = (
    "resolution=1920x1080&fps=30&videocodec=h265&camera=1"
)
PANORAMIC_STREAM_PROFILE = {
    "name": "SpotGenius Panoramic",
    "description": "1080p 30fps H.265 channel 1 for spot tracking",
    "parameters": PANORAMIC_STREAM_PARAMS,
}

# Param names are model-specific. These are common on many Axis models (Image.I0.*, Storage.S0.*).
# Run discover on a real camera and adjust keys to match your model.
LPR_PARAMS: dict[str, str] = {
    # Image – may need discovery to match exact names (e.g. Image.I0.Appearance.Resolution).
    "Image.I0.Appearance.Resolution": "1920x1080",
    "Image.I0.Appearance.Brightness": "50",
    "Image.I0.Appearance.ColorLevel": "50",
    "Image.I0.Appearance.Contrast": "50",
    "Image.I0.Appearance.Saturation": "50",
    "Image.I0.Appearance.Sharpness": "50",
    "Image.I0.Appearance.Compression": "30",
    # WDR off – name may be Image.I0.WDR or similar
    # "Image.I0.WDR.Enabled": "no",
    # Storage – SD card typically S0. Use disks/list.cgi to confirm group.
    "Storage.S0.CleanupPolicyActive": "fifo",
    "Storage.S0.CleanupMaxAge": "7",
}

PANORAMIC_PARAMS: dict[str, str] = {
    "Image.I0.Appearance.Resolution": "1920x1080",
    "Image.I0.Appearance.Brightness": "50",
    "Image.I0.Appearance.ColorLevel": "50",
    "Image.I0.Appearance.Contrast": "50",
    "Image.I0.Appearance.Saturation": "50",
    "Image.I0.Appearance.Sharpness": "50",
    "Storage.S0.CleanupPolicyActive": "fifo",
    "Storage.S0.CleanupMaxAge": "7",
}

PRESETS: dict[str, Preset] = {
    "lpr": Preset(
        id="lpr",
        name="LPR",
        description="SpotGenius LPR camera (e.g. AXIS P3275-LVE): 1080p 30fps H.264, storage 7 days",
        params=LPR_PARAMS.copy(),
        stream_profiles=[LPR_STREAM_PROFILE.copy()],
    ),
    "panoramic": Preset(
        id="panoramic",
        name="Panoramic",
        description="SpotGenius panoramic/spot tracking (e.g. P3727-PLE): 1080p 30fps H.265, camera=1",
        params=PANORAMIC_PARAMS.copy(),
        stream_profiles=[PANORAMIC_STREAM_PROFILE.copy()],
    ),
}


def get_preset(preset_id: str) -> Preset | None:
    """Return preset by id (e.g. 'lpr', 'panoramic')."""
    return PRESETS.get(preset_id.lower())

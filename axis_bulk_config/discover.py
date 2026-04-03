"""
Discovery script: connect to one camera and dump param.cgi (Image, Network, Storage)
and stream profiles to JSON/text for building or validating presets.

Usage:
  python -m axis_bulk_config.discover <camera_ip> [--user USER] [--password PASS] [--output FILE]
  Or set env: AXIS_IP, AXIS_USER, AXIS_PASSWORD
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from axis_bulk_config.client import (
    AxisCameraClient,
    AxisCameraError,
    parse_param_list,
)


GROUPS = ["Image", "Network", "Storage", "Properties.System"]


def discover(camera_ip: str, user: str, password: str, timeout: float = 15.0) -> dict:
    """Fetch param list for known groups and stream profiles from one camera."""
    base_url = f"http://{camera_ip}"
    client = AxisCameraClient(base_url, user, password, timeout=timeout)
    out: dict = {"camera_ip": camera_ip, "params": {}, "stream_profiles": None, "device_info": None}

    # Optional: basic device info (no auth)
    try:
        out["device_info"] = client.basicdeviceinfo()
    except Exception as e:
        out["device_info_error"] = str(e)

    # Param list per group
    for group in GROUPS:
        try:
            text = client.param_list(group=group)
            out["params"][group] = parse_param_list(text)
        except Exception as e:
            out["params"][group] = {"_error": str(e)}

    # Stream profiles
    try:
        out["stream_profiles"] = client.streamprofile_list()
    except Exception as e:
        out["stream_profiles_error"] = str(e)

    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover Axis camera params and stream profiles for preset building."
    )
    parser.add_argument(
        "camera_ip",
        nargs="?",
        default=os.environ.get("AXIS_IP"),
        help="Camera IP (or set AXIS_IP)",
    )
    parser.add_argument(
        "--user",
        "-u",
        default=os.environ.get("AXIS_USER", "root"),
        help="Camera user (or set AXIS_USER)",
    )
    parser.add_argument(
        "--password",
        "-p",
        default=os.environ.get("AXIS_PASSWORD", ""),
        help="Camera password (or set AXIS_PASSWORD)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write JSON to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=15.0,
        help="Request timeout in seconds",
    )
    args = parser.parse_args()

    if not args.camera_ip:
        print("Error: camera_ip required (positional or AXIS_IP env)", file=sys.stderr)
        return 2
    if not args.password:
        print("Error: password required (--password or AXIS_PASSWORD env)", file=sys.stderr)
        return 2

    try:
        data = discover(args.camera_ip, args.user, args.password, args.timeout)
    except AxisCameraError as e:
        print(f"Error: {e}", file=sys.stderr)
        if e.body:
            print(e.body, file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1

    # JSON-serializable: strip non-serializable if any
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(x) for x in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)

    data = sanitize(data)
    json_str = json.dumps(data, indent=2)

    if args.output:
        args.output.write_text(json_str, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(json_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())

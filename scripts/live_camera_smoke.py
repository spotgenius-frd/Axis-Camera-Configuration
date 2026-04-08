#!/usr/bin/env python3
"""Read-only live-camera smoke checks for a reachable sample Axis device."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from axis_bulk_config.client import AxisCameraClient
from axis_bulk_config.read_config import read_camera_config


def base_url(ip: str, scheme: str, port: int) -> str:
    default_port = 443 if scheme == "https" else 80
    if port != default_port:
        return f"{scheme}://{ip}:{port}"
    return f"{scheme}://{ip}"


def extract_model_name(bdi_payload: object) -> str:
    data = ((bdi_payload or {}).get("data") or {}) if isinstance(bdi_payload, dict) else {}
    properties = data.get("propertyList") or {}

    if isinstance(properties, dict):
        return (
            properties.get("ProdFullName")
            or properties.get("prodfullname")
            or properties.get("Brand")
            or "Axis camera"
        )

    if isinstance(properties, list):
        return next(
            (
                item.get("value")
                for item in properties
                if isinstance(item, dict) and item.get("property") == "ProdFullName"
            ),
            "Axis camera",
        )

    return "Axis camera"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-ip", default=os.environ.get("QA_SAMPLE_CAMERA_IP", "192.168.1.240"))
    parser.add_argument("--scheme", default=os.environ.get("QA_SAMPLE_CAMERA_SCHEME", "http"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QA_SAMPLE_CAMERA_PORT", "80")))
    parser.add_argument("--username", default=os.environ.get("QA_SAMPLE_CAMERA_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("QA_SAMPLE_CAMERA_PASSWORD", ""))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()

    client = AxisCameraClient(
        base_url(args.camera_ip, args.scheme, args.port),
        args.username,
        args.password,
        timeout=args.timeout,
    )

    try:
        bdi = client.basicdeviceinfo()
    except Exception as exc:
        print(f"SKIP live smoke: sample camera {args.camera_ip} is not reachable ({exc}).")
        return 0

    model = extract_model_name(bdi)
    print(f"Live smoke: discovered {model} at {args.camera_ip}.")

    if not args.password:
        print("SKIP credentialed live smoke: QA_SAMPLE_CAMERA_PASSWORD is not set.")
        return 0

    payload = read_camera_config(
        args.camera_ip,
        args.username,
        args.password,
        port=args.port,
        scheme=args.scheme,
        timeout=args.timeout,
        fetch_param_options=False,
    )
    auth_error = payload.get("auth_error")
    if auth_error:
        print(f"FAIL live read smoke: {auth_error}", file=sys.stderr)
        return 1
    if payload.get("error"):
        print(f"FAIL live read smoke: {payload['error']}", file=sys.stderr)
        return 1
    print(f"Live smoke: read-config succeeded for {args.camera_ip}.")

    try:
        image_bytes, content_type = client.snapshot_image(resolution="320x180")
    except Exception as exc:
        print(f"FAIL live preview smoke: {exc}", file=sys.stderr)
        return 1
    if not image_bytes or "image/" not in (content_type or "").lower():
        print("FAIL live preview smoke: snapshot did not return an image.", file=sys.stderr)
        return 1
    print(f"Live smoke: preview snapshot succeeded ({len(image_bytes)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

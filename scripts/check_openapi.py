#!/usr/bin/env python3
"""Validate that a running backend exposes required OpenAPI routes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to an OpenAPI JSON file.")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="A route path that must exist in the OpenAPI document.",
    )
    args = parser.parse_args()

    if args.file:
        payload = json.loads(Path(args.file).read_text())
    else:
        payload = json.load(sys.stdin)

    paths = set((payload or {}).get("paths", {}).keys())
    missing = [route for route in args.require if route not in paths]
    if missing:
        print("Missing required OpenAPI routes:", ", ".join(missing), file=sys.stderr)
        return 1
    print(f"OpenAPI check passed ({len(args.require)} required routes present).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

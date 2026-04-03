"""
Bulk apply preset to multiple Axis cameras from a CSV.

CSV columns: ip, username, password, type
  - type = lpr | panoramic (preset id)

Usage:
  python -m axis_bulk_config.apply cameras.csv [--report report.csv] [--dry-run]
"""

import argparse
import csv
import sys
from pathlib import Path

import requests

from axis_bulk_config.client import (
    AxisCameraClient,
    AxisCameraError,
    check_param_update_response,
)
from axis_bulk_config.presets import get_preset


def load_cameras(csv_path: Path) -> list[dict]:
    """Load camera list from CSV. Expected columns: ip, username, password, type."""
    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:  # utf-8-sig strips BOM
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows
        for row in reader:
            # Normalize keys: strip BOM and whitespace, lowercase
            row = {(k.strip().lstrip("\ufeff").lower()): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            if "ip" not in row and "camera_ip" in row:
                row["ip"] = row["camera_ip"]
            if "username" not in row and "user" in row:
                row["username"] = row["user"]
            rows.append(row)
    return rows


def apply_preset_to_camera(
    ip: str,
    username: str,
    password: str,
    preset_id: str,
    timeout: float = 15.0,
) -> dict:
    """
    Apply preset to one camera. Returns result dict with success, errors, and details.
    """
    preset = get_preset(preset_id)
    result: dict = {
        "ip": ip,
        "preset": preset_id,
        "success": False,
        "param_ok": False,
        "stream_profile_ok": False,
        "errors": [],
        "param_errors": [],
    }
    if not preset:
        result["errors"].append(f"Unknown preset: {preset_id}")
        return result

    base_url = f"http://{ip}"
    client = AxisCameraClient(base_url, username, password, timeout=timeout)

    def request_error_message(exc: Exception) -> str:
        if isinstance(exc, requests.exceptions.Timeout):
            return "timeout (check network or increase --timeout)"
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "connection failed (camera unreachable or wrong IP)"
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            if exc.response.status_code == 401:
                return "authentication failed (wrong username or password)"
            return f"HTTP {exc.response.status_code}"
        return str(exc)

    # 1. Param updates
    if preset.params:
        try:
            body = client.param_update(preset.params)
            ok, errs = check_param_update_response(body)
            result["param_ok"] = ok
            if errs:
                result["param_errors"] = errs
                result["errors"].extend([f"param: {e}" for e in errs])
        except requests.exceptions.Timeout as e:
            result["errors"].append(f"param: {request_error_message(e)}")
        except requests.exceptions.ConnectionError as e:
            result["errors"].append(f"param: {request_error_message(e)}")
        except requests.exceptions.HTTPError as e:
            result["errors"].append(f"param: {request_error_message(e)}")
        except requests.exceptions.RequestException as e:
            result["errors"].append(f"param: {request_error_message(e)}")
        except AxisCameraError as e:
            result["errors"].append(f"param: {e}")

    else:
        result["param_ok"] = True

    # 2. Stream profiles: update if exists, else create
    if preset.stream_profiles:
        try:
            existing = client.streamprofile_list()
            names = {
                p.get("name") for p in existing.get("data", {}).get("streamProfile", []) or []
            }
            to_update = [p for p in preset.stream_profiles if p.get("name") in names]
            to_create = [p for p in preset.stream_profiles if p.get("name") not in names]
            if to_update:
                client.streamprofile_update(to_update)
            if to_create:
                client.streamprofile_create(to_create)
            result["stream_profile_ok"] = True
        except requests.exceptions.Timeout:
            result["errors"].append("streamprofile: timeout (check network or increase --timeout)")
            result["stream_profile_ok"] = False
        except requests.exceptions.ConnectionError:
            result["errors"].append("streamprofile: connection failed (camera unreachable or wrong IP)")
            result["stream_profile_ok"] = False
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                result["errors"].append("streamprofile: authentication failed (wrong username or password)")
            else:
                result["errors"].append(f"streamprofile: {request_error_message(e)}")
            result["stream_profile_ok"] = False
        except requests.exceptions.RequestException as e:
            result["errors"].append(f"streamprofile: {request_error_message(e)}")
            result["stream_profile_ok"] = False
        except AxisCameraError as e:
            result["errors"].append(f"streamprofile: {e}")
            result["stream_profile_ok"] = False
    else:
        result["stream_profile_ok"] = True

    result["success"] = result["param_ok"] and result["stream_profile_ok"] and not result["errors"]
    return result


def _write_report(report_path: Path, results: list[dict]) -> None:
    report_rows = []
    for r in results:
        report_rows.append({
            "ip": r.get("ip", ""),
            "preset": r.get("preset", ""),
            "success": r.get("success", False),
            "param_ok": r.get("param_ok", ""),
            "stream_profile_ok": r.get("stream_profile_ok", ""),
            "errors": "; ".join(r.get("errors", [])),
        })
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ip", "preset", "success", "param_ok", "stream_profile_ok", "errors"])
        w.writeheader()
        w.writerows(report_rows)
    print(f"Report written to {report_path}", file=sys.stderr)


def main() -> int:
    import os
    parser = argparse.ArgumentParser(
        description="Bulk apply Axis camera preset (LPR or Panoramic) from CSV."
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        help="CSV with columns: ip, username, password, type (type = lpr | panoramic)",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=Path,
        default=None,
        help="Write result report to this CSV file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only load CSV and validate; do not call cameras",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=15.0,
        help="Request timeout per camera (seconds)",
    )
    args = parser.parse_args()

    if not args.csv_file.exists():
        print(f"Error: file not found: {args.csv_file}", file=sys.stderr)
        return 2

    cameras = load_cameras(args.csv_file)
    if not cameras:
        print("Error: no rows in CSV or missing header (ip, username, password, type)", file=sys.stderr)
        return 2

    required = {"ip", "username", "password", "type"}
    for i, row in enumerate(cameras):
        missing = required - set(k for k, v in row.items() if v)
        if missing:
            print(f"Warning: row {i+2} missing {missing}", file=sys.stderr)

    if args.dry_run:
        print(f"Dry run: would process {len(cameras)} camera(s).", file=sys.stderr)
        for i, c in enumerate(cameras):
            p = get_preset((c.get("type") or "").lower())
            print(f"  {c.get('ip')} -> preset '{c.get('type')}' ({p.name if p else 'UNKNOWN'})", file=sys.stderr)
        return 0

    results: list[dict] = []
    # Report path: same dir as CSV, then resolve so it's absolute and always writable
    report_path = (args.csv_file.parent / Path(args.report).name).resolve() if args.report else None
    # Also write to cwd with same name so cat report.csv always finds it
    report_path_cwd = Path(os.getcwd()) / Path(args.report).name if args.report else None

    print(f"Processing {len(cameras)} camera(s)...", file=sys.stderr, flush=True)
    try:
        for i, cam in enumerate(cameras):
            ip = (cam.get("ip") or "").strip()
            user = (cam.get("username") or cam.get("user") or "").strip()
            password = (cam.get("password") or "").strip()
            preset_id = (cam.get("type") or "").strip().lower()
            if not ip or not user or not password or not preset_id:
                results.append({
                    "ip": ip or "(missing)",
                    "preset": preset_id or "(missing)",
                    "success": False,
                    "errors": ["missing ip/username/password/type"],
                })
                continue
            print(f"[{i+1}/{len(cameras)}] {ip} ...", file=sys.stderr, end=" ", flush=True)
            res = apply_preset_to_camera(ip, user, password, preset_id, args.timeout)
            results.append(res)
            print("OK" if res["success"] else "FAIL", file=sys.stderr)
            if res.get("errors"):
                for e in res["errors"]:
                    print(f"    {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        if report_path:
            try:
                _write_report(report_path, results)
            except Exception as e:
                print(f"Could not write report to {report_path}: {e}", file=sys.stderr)
        if report_path_cwd and report_path_cwd != report_path:
            try:
                _write_report(report_path_cwd, results)
            except Exception:
                pass

    failed = sum(1 for r in results if not r.get("success"))
    if failed:
        print(f"Completed: {len(results) - failed} OK, {failed} failed", file=sys.stderr)
        return 1
    print(f"Completed: all {len(results)} camera(s) OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

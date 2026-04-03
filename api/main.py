"""
FastAPI backend for Axis Camera Config (read-only).
Run from repo root: uvicorn api.main:app --reload --host 0.0.0.0
"""

import csv
import io
import json
import sys
import tempfile
from pathlib import Path
import time
from typing import Any, Literal

# Ensure repo root is on path when running as uvicorn api.main:app
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from axis_bulk_config.firmware_lookup import get_latest_firmware
    from axis_bulk_config.network_scan import (
        discover_axis_devices,
        list_interface_options,
        resolve_scan_target,
    )
    from axis_bulk_config.read_config import read_camera_config, _to_serializable
    from axis_bulk_config.stream_profiles import build_stream_profile_payload
    from axis_bulk_config.write_service import (
        apply_daynight_updates,
        apply_firmware_action,
        apply_firmware_upgrade,
        apply_ir_cut_filter_update,
        apply_light_updates,
        apply_network_config_update,
        apply_password_change,
        apply_param_updates,
        apply_stream_profile_removals,
        apply_stream_profile_updates,
        apply_time_zone_update,
        make_client,
        refresh_camera,
    )
except ImportError as e:
    raise ImportError(
        "Run the server from the project root so axis_bulk_config is importable. "
        "Example: uvicorn api.main:app --reload"
    ) from e

app = FastAPI(title="Axis Camera Config API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow any origin (e.g. http://192.168.1.19:3000)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CameraInput(BaseModel):
    ip: str
    username: str
    password: str
    port: int | None = None
    name: str | None = None


class ReadConfigRequest(BaseModel):
    cameras: list[CameraInput]


class CameraTarget(BaseModel):
    ip: str
    username: str
    password: str
    port: int | None = None
    name: str | None = None


class WriteConfigRequest(BaseModel):
    cameras: list[CameraTarget]
    param_updates: dict[str, str] = {}
    time_zone: str | None = None
    daynight_updates: dict[str, Any] = {}
    ir_cut_filter_state: str | None = None
    ir_cut_filter_optics_id: str = "0"
    light_updates: dict[str, Any] = {}


class StreamProfilePayload(BaseModel):
    name: str
    description: str = ""
    parameters: str | None = None
    values: dict[str, str] | None = None


class StreamProfileApplyRequest(BaseModel):
    cameras: list[CameraTarget]
    action: Literal["create_or_update", "remove"]
    profiles: list[StreamProfilePayload] = []
    names: list[str] = []


class FirmwareActionRequest(BaseModel):
    cameras: list[CameraTarget]
    action: Literal["commit", "rollback", "purge", "reboot", "factory_default"]
    factory_default_mode: Literal["soft", "hard"] = "soft"


class FirmwareUpgradeMetadata(BaseModel):
    cameras: list[CameraTarget]
    auto_rollback: str | int | None = None
    auto_commit: str | None = None
    factory_default_mode: str | None = None


class NetworkConfigRequest(BaseModel):
    camera: CameraTarget
    ipv4_mode: Literal["dhcp", "static"]
    ip_address: str | None = None
    subnet_mask: str | None = None
    gateway: str | None = None
    dns_servers: list[str] = []
    use_dhcp_hostname: bool = True
    hostname: str | None = None


class PasswordChangeRequest(BaseModel):
    cameras: list[CameraTarget]
    new_password: str


class NetworkScanRequest(BaseModel):
    interface_name: str | None = None
    cidr: str | None = None


def _medium_payload(data: dict, name: str | None) -> dict:
    return {
        "camera_ip": data.get("camera_ip"),
        "name": name,
        "error": data.get("error"),
        "connection": {
            "ip": data.get("camera_ip"),
            "port": data.get("port", 80),
            "username": data.get("username"),
            "password": data.get("password"),
            "name": name,
        },
        "summary": data.get("summary"),
        "time_info": data.get("time_info"),
        "time_info_v2": data.get("time_info_v2"),
        "time_zone_options": data.get("time_zone_options"),
        "stream_profiles_structured": data.get("stream_profiles_structured"),
        "option_catalog": data.get("option_catalog"),
        "web_settings_catalog": data.get("web_settings_catalog"),
        "capabilities": data.get("capabilities"),
        "network_summary": data.get("network_summary"),
        "network_config": data.get("network_config"),
        "latest_firmware": data.get("latest_firmware"),
    }


def _build_target_dict(c: dict | CameraTarget) -> dict[str, Any]:
    if isinstance(c, CameraTarget):
        return c.model_dump()
    return dict(c)


def _camera_name(camera: dict[str, Any]) -> str | None:
    name = camera.get("name")
    if isinstance(name, str):
        return name.strip() or None
    return None


def _read_one_camera_payload(camera: dict[str, Any], cache: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    ip = str(camera.get("ip") or "").strip()
    port = camera.get("port")
    username = str(camera.get("username") or camera.get("user") or "root").strip()
    password = str(camera.get("password") or "").strip()
    name = _camera_name(camera)
    if not ip or not password:
        return {
            "camera_ip": ip or "?",
            "name": name,
            "error": "Missing ip or password",
        }
    data = read_camera_config(ip, username, password, port=port, fetch_param_options=True)
    data["port"] = port or 80
    data["username"] = username
    data["password"] = password
    data = _to_serializable(data)
    auth_error = data.get("auth_error")
    if auth_error:
        data["error"] = auth_error
        data["summary"] = {
            "model": None,
            "firmware": None,
            "image": {},
            "stream": [],
            "overlay": {},
            "sd_card": "unknown",
        }
        data["time_info"] = None
        data["time_info_v2"] = None
        data["time_zone_options"] = []
        data["stream_profiles_structured"] = []
        data["option_catalog"] = {}
        data["web_settings_catalog"] = {}
        data["capabilities"] = None
        data["network_summary"] = None
        data["network_config"] = None
        data["latest_firmware"] = None
        return _medium_payload(data, name)
    model = ((data.get("summary") or {}).get("model") or "").strip()
    if model:
        latest_cache = cache if cache is not None else {}
        if model not in latest_cache:
            latest_cache[model] = get_latest_firmware(model)
        data["latest_firmware"] = latest_cache.get(model)
    return _medium_payload(data, name)


def _write_result(camera: dict[str, Any], errors: list[str], refreshed: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "camera_ip": camera.get("ip") or "?",
        "name": _camera_name(camera),
        "ok": len(errors) == 0,
        "errors": errors,
    }
    if refreshed:
        refreshed_payload = _read_one_camera_payload(camera)
        result["result"] = refreshed_payload
    return result


def _run_read(cameras: list[dict]) -> list[dict]:
    results = []
    latest_cache: dict[str, dict[str, Any]] = {}
    for c in cameras:
        try:
            results.append(_read_one_camera_payload(c, latest_cache))
        except Exception as e:
            results.append({
                "camera_ip": (c.get("ip") or "").strip(),
                "name": _camera_name(c),
                "error": str(e),
            })
    return results


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        row = {k.strip().lower().lstrip("\ufeff"): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if row.get("ip") and row.get("password"):
            rows.append(row)
    return rows


def _parse_xlsx(content: bytes) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return []
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        return []
    keys = [str(h).strip().lower() if h is not None else "" for h in header]
    rows = []
    for row in rows_iter:
        if not any(cell is not None for cell in row):
            continue
        obj = dict(zip(keys, (cell if cell is None else str(cell).strip() for cell in row)))
        if obj.get("ip") and obj.get("password"):
            rows.append(obj)
    return rows


def _network_scan_metadata(interface_name: str | None = None, cidr: str | None = None) -> dict[str, Any]:
    interface_options = list_interface_options()
    scan_target, errors = resolve_scan_target(interface_options, interface_name=interface_name, cidr=cidr)
    return {
        "scan_target": scan_target,
        "interface_options": interface_options,
        "devices": [],
        "errors": errors,
    }


@app.post("/api/read-config")
def post_read_config(body: ReadConfigRequest):
    cameras = [
        {
            "ip": c.ip,
            "username": c.username,
            "password": c.password,
            "port": c.port,
            "name": c.name,
        }
        for c in body.cameras
    ]
    results = _run_read(cameras)
    return {"results": results}


@app.get("/api/network-scan/options")
def get_network_scan_options(interface_name: str | None = None, cidr: str | None = None):
    metadata = _network_scan_metadata(interface_name=interface_name, cidr=cidr)
    if cidr and metadata["scan_target"] is None:
        raise HTTPException(400, metadata["errors"][0])
    return metadata


@app.post("/api/network-scan")
def post_network_scan(body: NetworkScanRequest):
    scan = discover_axis_devices(interface_name=body.interface_name, cidr=body.cidr)
    if body.cidr and scan["scan_target"] is None:
        raise HTTPException(400, scan["errors"][0])
    return scan


@app.post("/api/read-config/upload")
async def post_read_config_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file selected")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".csv", ".xlsx"):
        raise HTTPException(400, "File must be .csv or .xlsx")
    content = await file.read()
    if ext == ".csv":
        cameras = _parse_csv(content)
    else:
        cameras = _parse_xlsx(content)
    if not cameras:
        raise HTTPException(400, "No valid rows (need ip and password columns)")
    results = _run_read(cameras)
    return {"results": results}


@app.post("/api/write-config")
def post_write_config(body: WriteConfigRequest):
    results: list[dict[str, Any]] = []
    for camera_model in body.cameras:
        camera = camera_model.model_dump()
        errors: list[str] = []
        try:
            data = refresh_camera(camera)
            client = make_client(camera)
            if body.param_updates:
                ok, errs = apply_param_updates(client, body.param_updates)
                if not ok:
                    errors.extend(errs)
            if body.time_zone:
                try:
                    apply_time_zone_update(client, data, body.time_zone)
                except Exception as exc:
                    errors.append(str(exc))
            if body.daynight_updates:
                try:
                    apply_daynight_updates(client, body.daynight_updates)
                except Exception as exc:
                    errors.append(str(exc))
            if body.ir_cut_filter_state:
                try:
                    apply_ir_cut_filter_update(
                        client,
                        body.ir_cut_filter_optics_id,
                        body.ir_cut_filter_state,
                    )
                except Exception as exc:
                    errors.append(str(exc))
            if body.light_updates:
                light_id = body.light_updates.get("light_id")
                if light_id:
                    errors.extend(
                        apply_light_updates(
                            client,
                            str(light_id),
                            {
                                "enabled": body.light_updates.get("enabled"),
                                "light_state": body.light_updates.get("light_state"),
                                "manual_intensity": body.light_updates.get("manual_intensity"),
                                "synchronize_day_night_mode": body.light_updates.get("synchronize_day_night_mode"),
                            },
                        )
                    )
            refreshed = refresh_camera(camera) if not errors else None
            results.append(_write_result(camera, errors, refreshed))
        except Exception as exc:
            results.append(_write_result(camera, [str(exc)]))
    return {"results": results}


@app.post("/api/stream-profiles/apply")
def post_stream_profiles_apply(body: StreamProfileApplyRequest):
    results: list[dict[str, Any]] = []
    profile_payloads: list[dict[str, str]] = []
    for profile in body.profiles:
        payload = profile.model_dump()
        if payload.get("values") is not None:
            profile_payloads.append(
                build_stream_profile_payload(
                    name=payload["name"],
                    description=payload.get("description") or "",
                    values=payload.get("values") or {},
                )
            )
        else:
            profile_payloads.append(
                {
                    "name": payload["name"],
                    "description": payload.get("description") or "",
                    "parameters": payload.get("parameters") or "",
                }
            )
    for camera_model in body.cameras:
        camera = camera_model.model_dump()
        try:
            client = make_client(camera)
            if body.action == "create_or_update":
                ok, errs = apply_stream_profile_updates(client, profile_payloads)
            else:
                ok, errs = apply_stream_profile_removals(client, body.names)
            refreshed = refresh_camera(camera) if ok else None
            results.append(_write_result(camera, errs, refreshed))
        except Exception as exc:
            results.append(_write_result(camera, [str(exc)]))
    return {"results": results}


@app.post("/api/firmware/action")
def post_firmware_action(body: FirmwareActionRequest):
    results: list[dict[str, Any]] = []
    for camera_model in body.cameras:
        camera = camera_model.model_dump()
        try:
            client = make_client(camera, timeout=300.0)
            apply_firmware_action(
                client,
                body.action,
                factory_default_mode=body.factory_default_mode,
            )
            results.append(_write_result(camera, []))
        except Exception as exc:
            results.append(_write_result(camera, [str(exc)]))
    return {"results": results}


@app.post("/api/firmware/upload-upgrade")
async def post_firmware_upload_upgrade(
    payload: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".bin"):
        raise HTTPException(400, "Firmware file must be a .bin file")
    try:
        metadata = FirmwareUpgradeMetadata.model_validate_json(payload)
    except Exception as exc:
        raise HTTPException(400, f"Invalid firmware payload: {exc}") from exc
    suffix = Path(file.filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            temp_file.write(chunk)
    results: list[dict[str, Any]] = []
    try:
        for camera_model in metadata.cameras:
            camera = camera_model.model_dump()
            try:
                client = make_client(camera, timeout=300.0)
                apply_firmware_upgrade(
                    client,
                    temp_path,
                    auto_rollback=metadata.auto_rollback,
                    auto_commit=metadata.auto_commit,
                    factory_default_mode=metadata.factory_default_mode,
                )
                results.append(_write_result(camera, []))
            except Exception as exc:
                results.append(_write_result(camera, [str(exc)]))
    finally:
        temp_path.unlink(missing_ok=True)
    return {"results": results}


@app.post("/api/network-config")
def post_network_config(body: NetworkConfigRequest):
    camera = body.camera.model_dump()
    try:
        result = apply_network_config_update(
            camera,
            ipv4_mode=body.ipv4_mode,
            ip_address=body.ip_address,
            subnet_mask=body.subnet_mask,
            gateway=body.gateway,
            dns_servers=body.dns_servers,
            use_dhcp_hostname=body.use_dhcp_hostname,
            hostname=body.hostname,
        )
        refreshed = None
        refresh_ip = result.get("reachable_ip") or (result.get("target_ip") if result.get("ok") else None)
        if refresh_ip:
            updated_camera = dict(camera)
            updated_camera["ip"] = refresh_ip
            refreshed = _read_one_camera_payload(updated_camera)
        return {
            **result,
            "result": refreshed,
        }
    except Exception as exc:
        return {
            "ok": False,
            "errors": [str(exc)],
            "previous_ip": camera.get("ip") or "?",
            "target_ip": body.ip_address or camera.get("ip") or "?",
            "reachable": None,
            "elapsed_seconds": 0.0,
            "poll_attempts": 0,
            "result": None,
        }


@app.post("/api/password-change")
def post_password_change(body: PasswordChangeRequest):
    latest_cache: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for target in body.cameras:
        camera = target.model_dump()
        started = time.monotonic()
        try:
            change_result = apply_password_change(camera, body.new_password)
            elapsed_seconds = round(time.monotonic() - started, 1)
            if not change_result.get("ok"):
                results.append(
                    {
                        "camera_ip": camera.get("ip") or "?",
                        "name": _camera_name(camera),
                        "ok": False,
                        "errors": change_result.get("errors") or ["Password change failed."],
                        "credential_status": "failed",
                        "elapsed_seconds": elapsed_seconds,
                        "result": None,
                    }
                )
                continue

            updated_camera = change_result.get("camera") or camera
            try:
                refreshed = _read_one_camera_payload(updated_camera, latest_cache)
                if refreshed.get("error"):
                    results.append(
                        {
                            "camera_ip": camera.get("ip") or "?",
                            "name": _camera_name(camera),
                            "ok": True,
                            "errors": [
                                "Password may have changed, but the camera could not be re-authenticated automatically. Re-enter the new password and refresh the camera."
                            ],
                            "credential_status": "needs_reauth",
                            "elapsed_seconds": elapsed_seconds,
                            "result": None,
                        }
                    )
                    continue
                results.append(
                    {
                        "camera_ip": camera.get("ip") or "?",
                        "name": _camera_name(camera),
                        "ok": True,
                        "errors": [],
                        "credential_status": "verified",
                        "elapsed_seconds": elapsed_seconds,
                        "result": refreshed,
                    }
                )
            except Exception:
                results.append(
                    {
                        "camera_ip": camera.get("ip") or "?",
                        "name": _camera_name(camera),
                        "ok": True,
                        "errors": [
                            "Password may have changed, but the camera could not be re-authenticated automatically. Re-enter the new password and refresh the camera."
                        ],
                        "credential_status": "needs_reauth",
                        "elapsed_seconds": elapsed_seconds,
                        "result": None,
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "camera_ip": camera.get("ip") or "?",
                    "name": _camera_name(camera),
                    "ok": False,
                    "errors": [str(exc)],
                    "credential_status": "failed",
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                    "result": None,
                }
            )
    return {"results": results}

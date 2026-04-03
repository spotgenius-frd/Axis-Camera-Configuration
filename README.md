# Axis Camera Configuration

Version: `0.1.0`

Axis Camera Configuration is a local-first toolkit for onboarding and configuring Axis IP cameras through Axis VAPIX APIs. It is designed for field and deployment workflows where an operator is on a customer site, connects to the same network as the cameras, discovers devices, applies credentials, changes network settings, and pushes the required SpotGenius camera configuration from one interface.

This project is **not hosted yet**. Today it runs locally as:

- a Python CLI in `axis_bulk_config/`
- a FastAPI backend in `api/`
- a Next.js web UI in `web/`

## Current `v0.1.0` Capabilities

- Manual camera entry by IP/hostname, username, password, and optional port
- CSV/XLSX upload for batch reads
- Local LAN discovery of Axis devices on the same subnet as the backend
- Readback of:
  - camera model
  - firmware
  - serial/basic identity
  - parameter groups
  - stream profiles
  - time and timezone data
  - firmware status
  - capability metadata
- Bulk configuration writes for:
  - image and stream parameters
  - overlays
  - day/night and IR-cut settings
  - light control
  - time zone
- Stream profile create, update, and remove
- Firmware upload and actions:
  - upgrade
  - commit
  - rollback
  - purge
  - reboot
  - factory default
- Single-camera network changes:
  - DHCP to static
  - static to DHCP
  - IP address
  - subnet mask
  - gateway
  - DNS
  - hostname
- Password change for the currently configured username on:
  - a single camera
  - selected cameras
  - all cameras of a chosen model in the current batch
- Improved auth handling so incorrect credentials are surfaced as authentication failures instead of partial camera reads

## Intended Operator Workflow

Typical on-site flow:

1. Connect the laptop to the same customer LAN as the new cameras.
2. Open the web app locally.
3. Use **Scan network** to discover Axis devices on the local subnet, or enter/upload known camera targets.
4. Import discovered devices into the batch.
5. Read current camera state using default or known credentials.
6. Change password, IP, hostname, and camera settings from the same application.
7. Refresh the camera or batch to verify the device came back with the expected state.

## Architecture

- `axis_bulk_config/`
  - Python client and service layer for Axis VAPIX operations
  - readback, writes, stream profiles, firmware, network config, password changes, and LAN scan
- `api/`
  - FastAPI backend used by the web app
- `web/`
  - Next.js operator UI
- `samples/`
  - reusable CSV templates and example inputs
- `tests/`
  - backend/unit and API-level tests

## Requirements

- Python `3.8+`
- Node.js `20+`
- Axis camera reachable from the machine running the backend
- Axis credentials with the required privileges for write actions
- Same-LAN access for LAN discovery

## Install

### Python backend environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt
```

### Web UI

```bash
cd web
npm install
```

## Run Locally

### 1. Start the backend

From the project root:

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the frontend

In a second terminal:

```bash
cd web
npm run dev
```

### 3. Open the application

By default:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

If the backend is hosted on another machine, create `web/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then restart the frontend.

## How To Use The Application Today

### Option A: Scan the local network

Use the **Scan** tab when the backend is running on a laptop or machine connected to the same customer LAN as the cameras.

1. Choose the active interface.
2. Confirm or edit the scan CIDR.
3. Run the scan.
4. Select discovered Axis devices.
5. Import them into the manual batch, or import and immediately read them using default credentials.

### Option B: Manual entry

Use the **Manual** tab for smaller batches or one-off devices:

- `name` optional
- `ip` or hostname required
- `port` optional, defaults to `80`
- `username` defaults to `root`
- `password` required

### Option C: Upload CSV / XLSX

Use the **Upload** tab for larger batches.

Supported columns:

- `ip`
- `port`
- `username`
- `password`
- `name`

## CLI Usage

### Read camera configuration

```bash
python -m axis_bulk_config.read_config 192.168.1.101 --user root --password your_password
python -m axis_bulk_config.read_config 192.168.1.101 --user root --password your_password --port 8080 -o outputs/config_reads/config_192_168_1_101.json
```

### Read from CSV / JSON

```bash
python -m axis_bulk_config.read_config --csv samples/cameras_read.csv --output-dir outputs/config_reads
python -m axis_bulk_config.read_config --json cameras.json --output-dir outputs/config_reads
```

### Model-specific parameter discovery

```bash
python -m axis_bulk_config.discover 192.168.1.101 --user root --password your_password -o discovery.json
```

### Bulk apply presets

```bash
python -m axis_bulk_config.apply samples/example_cameras.csv --dry-run
python -m axis_bulk_config.apply samples/cameras_edge.csv --report report.csv
```

## API Endpoints

Current backend endpoints:

- `POST /api/read-config`
- `POST /api/read-config/upload`
- `POST /api/write-config`
- `POST /api/stream-profiles/apply`
- `POST /api/firmware/action`
- `POST /api/firmware/upload-upgrade`
- `POST /api/network-config`
- `POST /api/password-change`
- `GET /api/network-scan/options`
- `POST /api/network-scan`

## Validation Commands

```bash
.venv/bin/python -m py_compile axis_bulk_config/*.py api/main.py
.venv/bin/python -m unittest discover -s tests
cd web && npm run lint
cd web && npm run build
```

## Current Constraints

- The app is not hosted yet; it must be run locally.
- LAN discovery is **same-subnet only** and depends on the backend being on the local network.
- LAN discovery is currently intended for **macOS and Linux** backend environments.
- Tailscale / Tailnet can provide routed access to remote private subnets, but this does not turn remote networks into a true local broadcast domain.
- Remote discovery over Tailscale should be treated as directed subnet probing, not broadcast-style LAN discovery.
- Username rename is not implemented; password change only targets the currently configured username.
- Bulk network configuration is not implemented; IP and hostname changes are single-camera only in this release.

## Common Errors

- Timeout: verify network reachability, subnet, firewall, or cable
- Authentication failed: invalid username or password
- Partial or stale device state after a network change: refresh the camera or batch after the device comes back online
- Parameter update errors: parameter may be read-only or model-specific; use discovery against the real camera model

## Notes

- `.venv/`, `node_modules/`, `web/.next/`, `outputs/`, and `archive/` are local or generated and are intentionally excluded from Git.
- `samples/` contains reusable input files for local testing.
- `tests/` covers the supported backend and API workflows that currently exist in the repo.

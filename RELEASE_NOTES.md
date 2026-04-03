# Release Notes

## `v0.1.0`

Initial GitHub import of the Axis Camera Configuration project.

### What this application is

Axis Camera Configuration is a local-first tool for SpotGenius field and deployment workflows. It combines a Python CLI, FastAPI backend, and Next.js web UI to read, configure, and validate Axis IP cameras through Axis VAPIX APIs.

### What is working in this release

- Manual camera entry
- CSV/XLSX batch upload
- Camera readback for model, firmware, parameters, stream profiles, capability data, and firmware status
- Bulk camera settings updates
- Stream profile create, update, and remove
- Firmware upload and firmware actions
- Single-camera network configuration:
  - DHCP/static mode
  - IP address
  - subnet mask
  - gateway
  - DNS
  - hostname
- Password change for the currently configured username
- LAN scan / Axis device discovery on the same local network
- Improved incorrect-credential handling in the UI and backend

### How this release is intended to be used

This release is intended to be run locally on a laptop or workstation that can reach the target cameras. It is not yet hosted as a public or internal web deployment.

Typical use:

1. Run the FastAPI backend locally.
2. Run the Next.js frontend locally.
3. Connect the machine to the same LAN as the customer cameras.
4. Discover or import cameras.
5. Read camera state.
6. Apply password, network, and configuration updates from the application.

### Current limitations

- Not hosted yet; local run only
- LAN discovery requires the backend to be on the same customer LAN
- LAN discovery is intended for macOS/Linux backend environments
- Bulk IP/hostname updates are not included in this release
- Username rename is not included in this release
- Tailscale access is useful for routed remote reachability, but it should not be treated as local broadcast discovery


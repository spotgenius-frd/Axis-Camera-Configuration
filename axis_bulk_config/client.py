"""Axis camera API client using HTTP Digest auth and param.cgi / streamprofile.cgi / firmwaremanagement.cgi."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import urllib3
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AxisCameraError(Exception):
    """Raised when an Axis API request fails."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class AxisCameraClient:
    """Client for Axis camera VAPIX APIs (param.cgi, streamprofile.cgi, basicdeviceinfo)."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 15.0,
    ):
        """
        Args:
            base_url: e.g. http://192.168.1.100 (no trailing slash).
            username: Camera user (operator or admin).
            password: Camera password.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = HTTPDigestAuth(username, password)
        self._session.headers["Accept"] = "*/*"
        if self.base_url.startswith("https://"):
            self._session.verify = False

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/axis-cgi/{path}"

    def _rest_url(self, path: str) -> str:
        """Build a full URL for non-axis-cgi REST-style endpoints."""
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"

    def _json_request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON request through the authenticated session."""
        resp = self._session.request(
            method,
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("status") == "error":
            err = data.get("error") or {}
            raise AxisCameraError(
                f"REST API error {err.get('code', 0)}: {err.get('message', 'Unknown error')}",
                status_code=resp.status_code,
                body=resp.text,
            )
        return data

    def _network_settings_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON request to network_settings.cgi and raise on Axis API errors."""
        url = self._url("network_settings.cgi")
        resp = self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            err = data.get("error") or {}
            raise AxisCameraError(
                f"Network settings API error {err.get('code', 0)}: {err.get('message', 'Unknown error')}",
                status_code=resp.status_code,
                body=resp.text,
            )
        return data

    def _pwdgrp_request(self, params: dict[str, str]) -> str:
        """Send a form-encoded request to pwdgrp.cgi and raise on obvious API failures."""
        url = self._url("pwdgrp.cgi")
        resp = self._session.post(
            url,
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        return _handle_pwdgrp_response(resp)

    def basicdeviceinfo(self) -> dict[str, Any]:
        """Get basic device info (no auth required). Returns JSON with data.propertyList."""
        url = self._url("/axis-cgi/basicdeviceinfo.cgi")
        resp = requests.post(
            url,
            json={
                "apiVersion": "1.2",
                "method": "getAllUnrestrictedProperties",
            },
            headers={"Content-Type": "application/json"},
            verify=not self.base_url.startswith("https://"),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def param_list(self, group: str | None = None) -> str:
        """
        List parameters. Returns plain text lines: root.Group.Param=value.
        If group is None, lists all parameters (can be large).
        """
        url = self._url("param.cgi")
        params: dict[str, str] = {"action": "list"}
        if group:
            params["group"] = group
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def param_list_definitions(self, group: str | None = None) -> str:
        """List parameter definitions (XML). Optional group to limit scope."""
        url = self._url("param.cgi")
        params: dict[str, str] = {"action": "listdefinitions", "listformat": "xmlschema"}
        if group:
            params["group"] = group
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def param_update(self, updates: dict[str, str]) -> str:
        """
        Update one or more parameters. Keys are param names (e.g. Image.I0.Appearance.Resolution).
        Returns response body ('OK' on success; may contain '# Error: ...' for failures).
        """
        url = self._url("param.cgi")
        params: dict[str, str] = {"action": "update"}
        params.update(updates)
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def snapshot_image(
        self,
        *,
        resolution: str | None = None,
        camera: int | None = None,
    ) -> tuple[bytes, str]:
        """Fetch a still JPEG snapshot through the authenticated session."""
        url = self._url("jpg/image.cgi")
        params: dict[str, str | int] = {}
        if resolution:
            params["resolution"] = resolution
        if camera is not None:
            params["camera"] = camera
        resp = self._session.get(url, params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            raise AxisCameraError(
                f"Snapshot request failed with HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text,
            )
        content_type = resp.headers.get("Content-Type", "")
        if "image/" not in content_type.lower() and not resp.content.startswith(b"\xff\xd8"):
            body_preview = resp.text[:200] if resp.text else ""
            raise AxisCameraError(
                "Snapshot endpoint did not return an image.",
                status_code=resp.status_code,
                body=body_preview,
            )
        return resp.content, content_type or "image/jpeg"

    def streamprofile_list(self) -> dict[str, Any]:
        """List all stream profiles. Returns JSON with data.streamProfile and data.maxProfiles."""
        url = self._url("streamprofile.cgi")
        resp = self._session.post(
            url,
            json={
                "apiVersion": "1.0",
                "method": "list",
                "params": {"streamProfileName": []},
            },
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamprofile_get_supported_versions(self) -> dict[str, Any]:
        """Get supported API versions for streamprofile.cgi."""
        url = self._url("streamprofile.cgi")
        resp = self._session.post(
            url,
            json={"method": "getSupportedVersions"},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamprofile_get(self, names: list[str]) -> dict[str, Any]:
        """Fetch one or more named stream profiles via the list method."""
        url = self._url("streamprofile.cgi")
        resp = self._session.post(
            url,
            json={
                "apiVersion": "1.0",
                "method": "list",
                "params": {
                    "streamProfileName": [{"name": name} for name in names],
                },
            },
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamprofile_create(self, profiles: list[dict[str, str]]) -> dict[str, Any]:
        """
        Create stream profiles. Each item: name, description, parameters (query string).
        """
        url = self._url("streamprofile.cgi")
        payload = {
            "apiVersion": "1.0",
            "method": "create",
            "params": {"streamProfile": profiles},
        }
        resp = self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamprofile_update(self, profiles: list[dict[str, str]]) -> dict[str, Any]:
        """Update existing stream profiles (same shape as create)."""
        url = self._url("streamprofile.cgi")
        payload = {
            "apiVersion": "1.0",
            "method": "update",
            "params": {"streamProfile": profiles},
        }
        resp = self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamprofile_remove(self, names: list[str]) -> dict[str, Any]:
        """Remove one or more stream profiles by name."""
        url = self._url("streamprofile.cgi")
        payload = {
            "apiVersion": "1.0",
            "method": "remove",
            "params": {
                "streamProfileName": [{"name": name} for name in names],
            },
        }
        resp = self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def streamstatus_get_all(self) -> dict[str, Any]:
        """Get active streams (read-only). Returns JSON with data.streams."""
        url = self._url("streamstatus.cgi")
        resp = self._session.post(
            url,
            json={"apiVersion": "1.0", "method": "getAllStreams"},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_time_info(self) -> dict[str, Any]:
        """Get date/time info (read-only). Returns JSON data from time.cgi getDateTimeInfo."""
        url = self._url("time.cgi")
        resp = self._session.post(
            url,
            json={"apiVersion": "1.0", "method": "getDateTimeInfo"},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def set_time_zone(self, timezone: str) -> dict[str, Any]:
        """Set system time zone (IANA format, e.g. America/New_York). Uses time.cgi setTimeZone."""
        url = self._url("time.cgi")
        resp = self._session.post(
            url,
            json={
                "apiVersion": "1.0",
                "method": "setTimeZone",
                "params": {"timeZone": timezone},
            },
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def set_date_time_utc(self, datetime_utc: str) -> dict[str, Any]:
        """Set system date/time in UTC (ISO 8601, e.g. 2018-12-24T14:28:53Z). Uses time.cgi setDateTime."""
        url = self._url("time.cgi")
        resp = self._session.post(
            url,
            json={
                "apiVersion": "1.0",
                "method": "setDateTime",
                "params": {"dateTime": datetime_utc},
            },
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Firmware management (firmwaremanagement.cgi) ---

    def _firmware_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON to firmwaremanagement.cgi; parse response and raise if error in body."""
        url = self._url("firmwaremanagement.cgi")
        resp = self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            code = err.get("code", 0)
            msg = err.get("message", str(err))
            raise AxisCameraError(f"Firmware API error {code}: {msg}", status_code=200, body=resp.text)
        return data

    def firmware_status(self) -> dict[str, Any]:
        """Retrieve current firmware status. Returns data with activeFirmwareVersion, inactiveFirmwareVersion, etc."""
        return self._firmware_request({"apiVersion": "1.0", "method": "status"})

    def firmware_get_supported_versions(self) -> dict[str, Any]:
        """Get supported API versions for firmware management."""
        return self._firmware_request({"method": "getSupportedVersions"})

    def firmware_upgrade(
        self,
        file_path: str | Path,
        *,
        auto_rollback: str | int | None = None,
        auto_commit: str | None = None,
        factory_default_mode: str | None = None,
    ) -> dict[str, Any]:
        """Upgrade firmware from a .bin file. Uses multipart form-data. Device reboots after upgrade."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Firmware file not found: {path}")
        url = self._url("firmwaremanagement.cgi")
        payload: dict[str, Any] = {"apiVersion": "1.0", "method": "upgrade"}
        if auto_rollback is not None or auto_commit is not None or factory_default_mode is not None:
            params: dict[str, str] = {}
            if auto_rollback is not None:
                params["autoRollback"] = str(auto_rollback)
            if auto_commit is not None:
                params["autoCommit"] = auto_commit
            if factory_default_mode is not None:
                params["factoryDefaultMode"] = factory_default_mode
            if params:
                payload["params"] = params
        with open(path, "rb") as f:
            files = [
                ("json", (None, json.dumps(payload), "application/json")),
                ("file", (path.name, f, "application/octet-stream")),
            ]
            resp = self._session.post(url, files=files, timeout=300)
        resp.raise_for_status()
        out = resp.json()
        if "error" in out:
            err = out["error"]
            raise AxisCameraError(
                f"Firmware upgrade error {err.get('code', 0)}: {err.get('message', str(err))}",
                status_code=200,
                body=resp.text,
            )
        return out

    def firmware_commit(self) -> dict[str, Any]:
        """Commit current firmware (stop automatic rollback)."""
        return self._firmware_request({"apiVersion": "1.0", "method": "commit"})

    def firmware_rollback(self) -> dict[str, Any]:
        """Rollback to previous firmware. Device reboots."""
        return self._firmware_request({"apiVersion": "1.0", "method": "rollback"})

    def firmware_purge(self) -> dict[str, Any]:
        """Purge inactive firmware (rollback no longer possible)."""
        return self._firmware_request({"apiVersion": "1.0", "method": "purge"})

    def firmware_reboot(self) -> dict[str, Any]:
        """Reboot the device."""
        return self._firmware_request({"apiVersion": "1.0", "method": "reboot"})

    def firmware_factory_default(self, mode: str = "soft") -> dict[str, Any]:
        """Reset to factory defaults. mode: 'soft' (keep network) or 'hard'. Device reboots."""
        return self._firmware_request({
            "apiVersion": "1.0",
            "method": "factoryDefault",
            "params": {"factoryDefaultMode": mode},
        })

    # --- Option discovery (read-only): Properties.Image, capturemode.cgi ---

    def properties_image_list(self) -> dict[str, str]:
        """
        List Properties.Image parameters (e.g. supported resolutions).
        Returns parsed key=value dict (keys like root.Properties.Image.Resolution).
        """
        text = self.param_list(group="Properties.Image")
        return parse_param_list(text)

    def get_supported_resolutions(self) -> list[str]:
        """
        Get supported resolution values from Properties.Image.Resolution.
        Returns list of strings (e.g. ['1920x1080', '1280x720']); empty if not available.
        """
        props = self.properties_image_list()
        raw = props.get("root.Properties.Image.Resolution", "").strip()
        if not raw:
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]

    def capturemode_get_modes(self) -> dict[str, Any] | None:
        """
        Get available capture modes (AXIS OS 8.50+). Returns JSON response or None on error/unsupported.
        Response has data: [{ channel, captureMode: [{ captureModeId, enabled, maxFPS?, description }] }].
        """
        url = self._url("capturemode.cgi")
        try:
            resp = self._session.post(
                url,
                json={"apiVersion": "1.0", "method": "getCaptureModes"},
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return None
            return data
        except Exception:
            return None

    # --- Device Configuration API discovery + selected APIs (read-only first) ---

    def dca_discover_root(self) -> dict[str, Any]:
        """Fetch the Device Configuration discovery root document."""
        return self._json_request("GET", self._rest_url("/config/discover"))

    def dca_discover_apis(self) -> dict[str, Any]:
        """Fetch all available Device Configuration APIs and versions."""
        return self._json_request("GET", self._rest_url("/config/discover/apis"))

    def time_v2_get_all(self) -> dict[str, Any]:
        """Fetch Time API v2 root data."""
        return self._json_request("GET", self._rest_url("/config/rest/time/v2"))

    def time_v2_get_time_zone(self) -> dict[str, Any]:
        """Fetch Time API v2 timeZone entity."""
        return self._json_request("GET", self._rest_url("/config/rest/time/v2/timeZone"))

    def time_v2_get_time_zone_list(self) -> dict[str, Any]:
        """Fetch the camera-provided IANA time zone list."""
        return self._json_request(
            "POST",
            self._rest_url("/config/rest/time/v2/timeZone/iana/getTimeZoneList"),
            payload={"data": {}},
        )

    def time_v2_set_iana_time_zone(self, time_zone: str) -> dict[str, Any]:
        """Set the active time zone via Time API v2 using an IANA string."""
        return self._json_request(
            "PATCH",
            self._rest_url("/config/rest/time/v2/timeZone/iana/timeZone"),
            payload={"data": time_zone},
        )

    def network_settings_v2_get(self) -> dict[str, Any]:
        """Fetch the Network Settings API v2 root object."""
        return self._json_request("GET", self._rest_url("/config/rest/network-settings/v2"))

    def network_settings_get_supported_versions(self) -> dict[str, Any]:
        """Get supported versions for the legacy network settings API."""
        return self._network_settings_request({"method": "getSupportedVersions"})

    def network_settings_get_info(self, api_version: str = "1.0") -> dict[str, Any]:
        """Fetch the legacy network settings document from network_settings.cgi."""
        return self._network_settings_request(
            {
                "apiVersion": api_version,
                "method": "getNetworkInfo",
            }
        )

    def network_settings_set_ipv4_address_configuration(
        self,
        *,
        device_name: str,
        configuration_mode: str,
        enabled: bool | None = None,
        link_local_mode: str | None = None,
        static_default_router: str | None = None,
        static_address_configurations: list[dict[str, Any]] | None = None,
        use_static_dhcp_fallback: bool | None = None,
        use_dhcp_static_routes: bool | None = None,
        api_version: str = "1.0",
    ) -> dict[str, Any]:
        """Configure IPv4 address mode and static values on a network interface."""
        params: dict[str, Any] = {
            "deviceName": device_name,
            "configurationMode": configuration_mode,
        }
        if enabled is not None:
            params["enabled"] = enabled
        if link_local_mode:
            params["linkLocalMode"] = link_local_mode
        if static_default_router is not None:
            params["staticDefaultRouter"] = static_default_router
        if static_address_configurations is not None:
            params["staticAddressConfigurations"] = static_address_configurations
        if use_static_dhcp_fallback is not None:
            params["useStaticDHCPFallback"] = use_static_dhcp_fallback
        if use_dhcp_static_routes is not None:
            params["useDHCPStaticRoutes"] = use_dhcp_static_routes
        return self._network_settings_request(
            {
                "apiVersion": api_version,
                "method": "setIPv4AddressConfiguration",
                "params": params,
            }
        )

    def network_settings_set_resolver_configuration(
        self,
        *,
        use_dhcp_resolver_info: bool,
        static_name_servers: list[str] | None = None,
        static_search_domains: list[str] | None = None,
        static_domain_name: str | None = None,
        api_version: str = "1.0",
    ) -> dict[str, Any]:
        """Configure DNS resolver behavior through network_settings.cgi."""
        params: dict[str, Any] = {
            "useDhcpResolverInfo": use_dhcp_resolver_info,
        }
        if static_name_servers is not None:
            params["staticNameServers"] = static_name_servers
        if static_search_domains is not None:
            params["staticSearchDomains"] = static_search_domains
        if static_domain_name is not None:
            params["staticDomainName"] = static_domain_name
        return self._network_settings_request(
            {
                "apiVersion": api_version,
                "method": "setResolverConfiguration",
                "params": params,
            }
        )

    def network_settings_set_hostname_configuration(
        self,
        *,
        use_dhcp_hostname: bool,
        static_hostname: str | None = None,
        api_version: str = "1.0",
    ) -> dict[str, Any]:
        """Configure whether the camera hostname comes from DHCP or a static value."""
        params: dict[str, Any] = {
            "useDhcpHostname": use_dhcp_hostname,
        }
        if static_hostname is not None:
            params["staticHostname"] = static_hostname
        return self._network_settings_request(
            {
                "apiVersion": api_version,
                "method": "setHostnameConfiguration",
                "params": params,
            }
        )

    def pwdgrp_get_accounts(self) -> str:
        """List configured user accounts and groups via pwdgrp.cgi."""
        return self._pwdgrp_request({"action": "get"})

    def pwdgrp_update_password(self, user: str, new_password: str) -> str:
        """Change the password of an existing user via pwdgrp.cgi."""
        return self._pwdgrp_request(
            {
                "action": "update",
                "user": user,
                "pwd": new_password,
            }
        )

    def dynamicoverlay_get_supported_versions(self) -> dict[str, Any]:
        """Get supported versions for the Dynamic Overlay API."""
        return self._json_request(
            "POST",
            self._url("dynamicoverlay/dynamicoverlay.cgi"),
            payload={"apiVersion": "1.0", "method": "getSupportedVersions"},
        )

    def dynamicoverlay_list(
        self,
        *,
        camera: int | None = None,
        identity: int | None = None,
        api_version: str = "1.0",
    ) -> dict[str, Any]:
        """List dynamic overlays configured on the camera."""
        params: dict[str, Any] = {}
        if camera is not None:
            params["camera"] = camera
        if identity is not None:
            params["identity"] = identity
        payload: dict[str, Any] = {
            "apiVersion": api_version,
            "method": "list",
            "params": params,
        }
        return self._json_request(
            "POST",
            self._url("dynamicoverlay/dynamicoverlay.cgi"),
            payload=payload,
        )


    # --- Imaging / day-night / optics / light control ---

    def daynight_get_capabilities(self) -> dict[str, Any]:
        """Fetch day/night capabilities for supported channels."""
        url = self._url("daynight.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.2", "method": "getCapabilities"},
        )

    def daynight_get_configuration(self) -> dict[str, Any]:
        """Fetch day/night configuration for supported channels."""
        url = self._url("daynight.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.2", "method": "getConfiguration"},
        )

    def daynight_set_configuration(self, channel: int, updates: dict[str, Any]) -> dict[str, Any]:
        """Apply day/night configuration updates for a channel."""
        url = self._url("daynight.cgi")
        params = {"channel": channel}
        params.update(updates)
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.2", "method": "setConfiguration", "params": params},
        )

    def opticscontrol_get_capabilities(self) -> dict[str, Any]:
        """Fetch optics capabilities such as zoom, focus, and IR-cut support."""
        url = self._url("opticscontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.1", "method": "getCapabilities"},
        )

    def opticscontrol_get_optics(self) -> dict[str, Any]:
        """Fetch current optics state such as magnification, focus, and IR-cut filter."""
        url = self._url("opticscontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.1", "method": "getOptics"},
        )

    def opticscontrol_set_ir_cut_filter_state(self, optics_id: str, state: str) -> dict[str, Any]:
        """Set the IR-cut filter state to auto/on/off for one optics object."""
        url = self._url("opticscontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={
                "apiVersion": "1.1",
                "method": "setIrCutFilterState",
                "params": {"optics": [{"opticsId": optics_id, "irCutFilterState": state}]},
            },
        )

    def lightcontrol_get_supported_versions(self) -> dict[str, Any]:
        """Fetch supported versions for the light control API."""
        url = self._url("lightcontrol.cgi")
        return self._json_request("POST", url, payload={"method": "getSupportedVersions"})

    def lightcontrol_get_service_capabilities(self) -> dict[str, Any]:
        """Fetch light control capabilities for device and light groups."""
        url = self._url("lightcontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.0", "method": "getServiceCapabilities"},
        )

    def lightcontrol_get_light_information(self) -> dict[str, Any]:
        """Fetch configured lights and their current states."""
        url = self._url("lightcontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.0", "method": "getLightInformation", "params": {}},
        )

    def lightcontrol_get_valid_intensity(self, light_id: str) -> dict[str, Any]:
        """Fetch valid manual intensity ranges for a specific light group."""
        url = self._url("lightcontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.0", "method": "getValidIntensity", "params": {"lightID": light_id}},
        )

    def lightcontrol_enable_light(self, light_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable a light group."""
        url = self._url("lightcontrol.cgi")
        method = "enableLight" if enabled else "disableLight"
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.0", "method": method, "params": {"lightID": light_id}},
        )

    def lightcontrol_set_light_state(self, light_id: str, active: bool) -> dict[str, Any]:
        """Activate or deactivate a light group."""
        url = self._url("lightcontrol.cgi")
        method = "activateLight" if active else "deactivateLight"
        return self._json_request(
            "POST",
            url,
            payload={"apiVersion": "1.0", "method": method, "params": {"lightID": light_id}},
        )

    def lightcontrol_set_manual_intensity(self, light_id: str, intensity: int) -> dict[str, Any]:
        """Set a manual light intensity value for a light group."""
        url = self._url("lightcontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={
                "apiVersion": "1.0",
                "method": "setManualIntensity",
                "params": {"lightID": light_id, "intensity": intensity},
            },
        )

    def lightcontrol_set_daynight_sync(self, light_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable light synchronization with day/night mode."""
        url = self._url("lightcontrol.cgi")
        return self._json_request(
            "POST",
            url,
            payload={
                "apiVersion": "1.0",
                "method": "setLightSynchronizeDayNightMode",
                "params": {"lightID": light_id, "enabled": enabled},
            },
        )


def _handle_pwdgrp_response(resp: requests.Response) -> str:
    """Validate a pwdgrp.cgi response and raise an AxisCameraError on failure."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        body = resp.text.strip()
        raise AxisCameraError(
            f"User management API error: {body or exc}",
            status_code=resp.status_code,
            body=body,
        ) from exc

    body = resp.text.strip()
    lower = body.lower()
    if (
        "error" in lower
        or "failed" in lower
        or "not authorized" in lower
        or "access denied" in lower
    ):
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), body)
        raise AxisCameraError(
            f"User management API error: {first_line}",
            status_code=resp.status_code,
            body=body,
        )
    return body


def pwdgrp_add_account_unauthenticated(
    base_url: str,
    user: str,
    password: str,
    timeout: float = 15.0,
) -> str:
    """Create the initial device account without prior auth when the device is factory-default."""
    url = base_url.rstrip("/") + "/axis-cgi/pwdgrp.cgi"
    resp = requests.post(
        url,
        data={
            "action": "add",
            "user": user,
            "pwd": password,
            "grp": "admin",
            "sgrp": "admin:operator:viewer:ptz",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
        verify=not base_url.startswith("https://"),
    )
    return _handle_pwdgrp_response(resp)


def pwdgrp_probe_initial_admin_required(
    base_url: str,
    timeout: float = 15.0,
) -> bool:
    """Best-effort read-only probe for first-time devices before an admin account exists."""
    url = base_url.rstrip("/") + "/axis-cgi/pwdgrp.cgi"
    resp = requests.post(
        url,
        data={"action": "get"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
        verify=not base_url.startswith("https://"),
    )
    if resp.status_code in {401, 403}:
        return False
    body = resp.text.strip().lower()
    if resp.ok and "not authorized" not in body and "access denied" not in body:
        return True
    return False


def parse_param_list(text: str) -> dict[str, str]:
    """Parse param.cgi action=list response into a dict of param -> value."""
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def check_param_update_response(text: str) -> tuple[bool, list[str]]:
    """
    Check param.cgi action=update response. Returns (all_ok, list of error messages).
    """
    errors: list[str] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if line.startswith("# Error:"):
            errors.append(line[8:].strip())
    return (len(errors) == 0, errors)


def param_update_key_variants(key: str) -> tuple[str, str]:
    """Return (key, key_alternate) for param_update retry. Some cameras use root. prefix, some not."""
    k = key.strip()
    if k.startswith("root."):
        return (k, k.replace("root.", "", 1))
    return (k, "root." + k)

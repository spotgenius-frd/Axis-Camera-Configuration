"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  Clock3Icon,
  HardDriveIcon,
  ImageIcon,
  LoaderCircleIcon,
  RefreshCwIcon,
  ScanSearchIcon,
  ServerIcon,
  ShieldCheckIcon,
  TriangleAlertIcon,
  UploadIcon,
  VideoIcon,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  CameraNetworkConfig,
  CameraConnection,
  CameraResult,
  FirmwareActionRequest,
  NetworkConfigRequest,
  NetworkConfigResponse,
  PasswordChangeResult,
  StreamProfileApplyRequest,
  StreamProfileInput,
  WebSettingEntry,
  WriteConfigRequest,
  WriteResult,
} from "@/lib/camera-types";
import {
  formatMetricLabel,
  getCameraDisplayName,
  getCameraStatus,
  getMetricRows,
  isOverlayActive,
} from "@/lib/camera-utils";
import { getSupportedUsTimeZones } from "@/lib/us-time-zones";

type CameraDetailSheetProps = {
  result: CameraResult | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  busy: boolean;
  refreshInProgress?: boolean;
  lastWriteResult?: WriteResult | null;
  lastWriteNeedsRefresh?: boolean;
  onRefreshCamera?: (camera: CameraConnection) => Promise<void>;
  onApplyConfig: (
    camera: CameraConnection,
    payload: Omit<WriteConfigRequest, "cameras">,
  ) => Promise<void>;
  onApplyNetworkConfig: (
    camera: CameraConnection,
    payload: Omit<NetworkConfigRequest, "camera">,
  ) => Promise<NetworkConfigResponse>;
  onApplyPasswordChange: (
    camera: CameraConnection,
    newPassword: string,
  ) => Promise<PasswordChangeResult>;
  onApplyStreamProfiles: (
    camera: CameraConnection,
    body: Omit<StreamProfileApplyRequest, "cameras">,
  ) => Promise<void>;
  onRunFirmwareAction: (
    camera: CameraConnection,
    body: Omit<FirmwareActionRequest, "cameras">,
  ) => Promise<void>;
  onUploadFirmware: (camera: CameraConnection, file: File) => Promise<void>;
};

const GROUP_ICONS: Record<string, typeof ImageIcon> = {
  stream: VideoIcon,
  image: ImageIcon,
  exposure: ImageIcon,
  daynight: HardDriveIcon,
  light: HardDriveIcon,
  overlay: HardDriveIcon,
  storage: HardDriveIcon,
  focus_zoom: ScanSearchIcon,
};

const GROUP_ORDER = ["stream", "image", "exposure", "daynight", "light", "overlay", "storage", "focus_zoom"];
const DEFAULT_OPEN_GROUPS = new Set(["stream", "image"]);

const STREAM_PROFILE_FIELDS: Array<{ key: string; label: string }> = [
  { key: "resolution", label: "Resolution" },
  { key: "fps", label: "FPS" },
  { key: "compression", label: "Compression" },
  { key: "videocodec", label: "Video codec" },
  { key: "videobitrate", label: "Video bitrate" },
  { key: "rotation", label: "Rotation" },
  { key: "audio", label: "Audio" },
  { key: "text", label: "Text overlay" },
  { key: "textstring", label: "Overlay text" },
  { key: "signedvideo", label: "Signed video" },
];

type DetailTabValue =
  | "settings"
  | "access"
  | "network"
  | "stream-profiles"
  | "firmware";

export function CameraDetailSheet({
  result,
  open,
  onOpenChange,
  busy,
  refreshInProgress,
  lastWriteResult,
  lastWriteNeedsRefresh,
  onRefreshCamera,
  onApplyConfig,
  onApplyNetworkConfig,
  onApplyPasswordChange,
  onApplyStreamProfiles,
  onRunFirmwareAction,
  onUploadFirmware,
}: CameraDetailSheetProps) {
  if (!result) {
    return null;
  }

  const status = getCameraStatus(result);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="max-w-3xl">
        <SheetHeader>
          <div className="flex items-center gap-2">
            <SheetTitle>{getCameraDisplayName(result)}</SheetTitle>
            <Badge variant={status === "error" ? "destructive" : "secondary"}>
              {status === "error" ? "Error" : "Ready"}
            </Badge>
          </div>
          <SheetDescription>
            {result.camera_ip || "No camera IP returned"}{" "}
            {currentTimeZone(result) !== "Not available"
              ? `· ${currentTimeZone(result)}`
              : ""}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {result.error ? (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {result.error}
            </div>
          ) : (
            <CameraDetailContent
              key={`${result.camera_ip}-${result.summary?.firmware ?? ""}-${result.summary?.model ?? ""}`}
              result={result}
              busy={busy}
              lastWriteResult={lastWriteResult}
              lastWriteNeedsRefresh={lastWriteNeedsRefresh}
              onRefreshCamera={
                onRefreshCamera && result.connection
                  ? () => onRefreshCamera!(result.connection!)
                  : undefined
              }
              refreshInProgress={refreshInProgress}
              onApplyConfig={onApplyConfig}
              onApplyNetworkConfig={onApplyNetworkConfig}
              onApplyPasswordChange={onApplyPasswordChange}
              onApplyStreamProfiles={onApplyStreamProfiles}
              onRunFirmwareAction={onRunFirmwareAction}
              onUploadFirmware={onUploadFirmware}
            />
          )}
        </div>

        <SheetFooter>
          <div className="flex justify-end gap-2">
            {onRefreshCamera && result.connection && (
              <Button
                type="button"
                variant="outline"
                onClick={() => onRefreshCamera(result.connection!)}
                disabled={busy || refreshInProgress}
              >
                <RefreshCwIcon className="size-4" />
                Refresh this camera
              </Button>
            )}
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

function CameraDetailContent({
  result,
  busy,
  lastWriteResult,
  lastWriteNeedsRefresh,
  onRefreshCamera,
  refreshInProgress,
  onApplyConfig,
  onApplyNetworkConfig,
  onApplyPasswordChange,
  onApplyStreamProfiles,
  onRunFirmwareAction,
  onUploadFirmware,
}: {
  result: CameraResult;
  busy: boolean;
  lastWriteResult?: WriteResult | null;
  lastWriteNeedsRefresh?: boolean;
  onRefreshCamera?: () => Promise<void>;
  refreshInProgress?: boolean;
  onApplyConfig: CameraDetailSheetProps["onApplyConfig"];
  onApplyNetworkConfig: CameraDetailSheetProps["onApplyNetworkConfig"];
  onApplyPasswordChange: CameraDetailSheetProps["onApplyPasswordChange"];
  onApplyStreamProfiles: CameraDetailSheetProps["onApplyStreamProfiles"];
  onRunFirmwareAction: CameraDetailSheetProps["onRunFirmwareAction"];
  onUploadFirmware: CameraDetailSheetProps["onUploadFirmware"];
}) {
  const initialDrafts = useMemo(() => {
    const nextDrafts: Record<string, string> = {};
    const catalog = result.web_settings_catalog ?? {};
    for (const entries of Object.values(catalog)) {
      for (const entry of entries) {
        if (entry.value !== undefined && entry.value !== null) {
          nextDrafts[entry.id] = String(entry.value);
        }
      }
    }
    return nextDrafts;
  }, [result.web_settings_catalog]);
  const [draftValues, setDraftValues] = useState<Record<string, string>>(initialDrafts);
  const [draftTimeZone, setDraftTimeZone] = useState(currentTimeZone(result));
  const [networkDraft, setNetworkDraft] = useState(() => buildNetworkDraft(result.network_config));
  const [networkStatus, setNetworkStatus] = useState<NetworkStatusState>({
    phase: "idle",
    elapsedSeconds: 0,
  });
  const [passwordDraft, setPasswordDraft] = useState<PasswordDraft>({
    newPassword: "",
    confirmPassword: "",
    showPassword: false,
  });
  const [passwordStatus, setPasswordStatus] = useState<PasswordStatusState>({
    phase: "idle",
    elapsedSeconds: 0,
  });
  const [settingsStatus, setSettingsStatus] = useState<DetailActionStatusState>({
    phase: "idle",
    elapsedSeconds: 0,
  });
  const [profileName, setProfileName] = useState("");
  const [profileDescription, setProfileDescription] = useState("");
  const [profileValues, setProfileValues] = useState<Record<string, string>>({});
  const [editingProfileName, setEditingProfileName] = useState<string | null>(null);
  const [showStreamProfileForm, setShowStreamProfileForm] = useState(false);
  const [streamProfileStatus, setStreamProfileStatus] = useState<DetailActionStatusState>({
    phase: "idle",
    elapsedSeconds: 0,
  });
  const [firmwareFile, setFirmwareFile] = useState<File | null>(null);
  const [firmwareStatus, setFirmwareStatus] = useState<DetailActionStatusState>({
    phase: "idle",
    elapsedSeconds: 0,
  });
  const [activeTab, setActiveTab] = useState<DetailTabValue>("settings");
  const [firmwareActionsOpen, setFirmwareActionsOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const out: Record<string, boolean> = {};
    for (const name of GROUP_ORDER) {
      out[name] = DEFAULT_OPEN_GROUPS.has(name);
    }
    return out;
  });

  const camera = result.connection;
  const networkConfig = result.network_config;
  const streamProfiles = result.stream_profiles_structured ?? [];
  const latestFirmware = result.latest_firmware;
  const visibleDynamicOverlays = useMemo(
    () => getVisibleDynamicOverlays(result.dynamic_overlays),
    [result.dynamic_overlays],
  );
  const editableGroups = useMemo(() => {
    const catalog = result.web_settings_catalog ?? {};
    const entries = Object.entries(catalog)
      .filter(([groupName]) => groupName !== "firmware")
      .map(([groupName, entries]) => ({
        title: groupName.replace("_", " / "),
        icon: GROUP_ICONS[groupName] ?? ImageIcon,
        groupName,
        items: entries,
      }));
    const orderMap = new Map(GROUP_ORDER.map((name, i) => [name, i]));
    entries.sort((a, b) => (orderMap.get(a.groupName) ?? 99) - (orderMap.get(b.groupName) ?? 99));
    return entries;
  }, [result.web_settings_catalog]);

  useEffect(() => {
    setDraftValues(initialDrafts);
  }, [initialDrafts]);

  useEffect(() => {
    setDraftTimeZone(currentTimeZone(result));
  }, [result]);

  useEffect(() => {
    setNetworkDraft(buildNetworkDraft(result.network_config));
    setNetworkStatus({ phase: "idle", elapsedSeconds: 0 });
    setPasswordDraft({ newPassword: "", confirmPassword: "", showPassword: false });
    setPasswordStatus({ phase: "idle", elapsedSeconds: 0 });
    setSettingsStatus({ phase: "idle", elapsedSeconds: 0 });
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    setFirmwareStatus({ phase: "idle", elapsedSeconds: 0 });
    setActiveTab("settings");
  }, [result.network_config, result.camera_ip]);

  useEffect(() => {
    if (networkStatus.phase !== "saving") {
      return;
    }
    const startedAt = networkStatus.startedAt ?? Date.now();
    const interval = window.setInterval(() => {
      setNetworkStatus((current) => {
        if (current.phase !== "saving") {
          return current;
        }
        return {
          ...current,
          elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        };
      });
    }, 250);
    return () => window.clearInterval(interval);
  }, [networkStatus.phase, networkStatus.startedAt]);

  useEffect(() => {
    if (passwordStatus.phase !== "saving") {
      return;
    }
    const startedAt = passwordStatus.startedAt ?? Date.now();
    const interval = window.setInterval(() => {
      setPasswordStatus((current) => {
        if (current.phase !== "saving") {
          return current;
        }
        return {
          ...current,
          elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        };
      });
    }, 250);
    return () => window.clearInterval(interval);
  }, [passwordStatus.phase, passwordStatus.startedAt]);

  useEffect(() => {
    if (settingsStatus.phase !== "saving") {
      return;
    }
    const startedAt = settingsStatus.startedAt ?? Date.now();
    const interval = window.setInterval(() => {
      setSettingsStatus((current) => {
        if (current.phase !== "saving") {
          return current;
        }
        return {
          ...current,
          elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        };
      });
    }, 250);
    return () => window.clearInterval(interval);
  }, [settingsStatus.phase, settingsStatus.startedAt]);

  useEffect(() => {
    if (streamProfileStatus.phase !== "saving") {
      return;
    }
    const startedAt = streamProfileStatus.startedAt ?? Date.now();
    const interval = window.setInterval(() => {
      setStreamProfileStatus((current) => {
        if (current.phase !== "saving") {
          return current;
        }
        return {
          ...current,
          elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        };
      });
    }, 250);
    return () => window.clearInterval(interval);
  }, [streamProfileStatus.phase, streamProfileStatus.startedAt]);

  useEffect(() => {
    if (firmwareStatus.phase !== "saving") {
      return;
    }
    const startedAt = firmwareStatus.startedAt ?? Date.now();
    const interval = window.setInterval(() => {
      setFirmwareStatus((current) => {
        if (current.phase !== "saving") {
          return current;
        }
        return {
          ...current,
          elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        };
      });
    }, 250);
    return () => window.clearInterval(interval);
  }, [firmwareStatus.phase, firmwareStatus.startedAt]);

  const updateDraftValue = (key: string, value: string) => {
    setSettingsStatus({ phase: "idle", elapsedSeconds: 0 });
    setDraftValues((current) => ({ ...current, [key]: value }));
  };

  const updateDraftTimeZone = (value: string) => {
    setSettingsStatus({ phase: "idle", elapsedSeconds: 0 });
    setDraftTimeZone(value);
  };

  const updatePasswordDraft = <K extends keyof PasswordDraft>(
    key: K,
    value: PasswordDraft[K],
  ) => {
    setPasswordStatus({ phase: "idle", elapsedSeconds: 0 });
    setPasswordDraft((current) => ({ ...current, [key]: value }));
  };

  const updateNetworkDraft = <K extends keyof NetworkDraft>(
    key: K,
    value: NetworkDraft[K],
  ) => {
    setNetworkStatus({ phase: "idle", elapsedSeconds: 0 });
    setNetworkDraft((current) => ({ ...current, [key]: value }));
  };

  const updateProfileName = (value: string) => {
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    setProfileName(value);
  };

  const updateProfileDescription = (value: string) => {
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    setProfileDescription(value);
  };

  const updateProfileValue = (key: string, value: string) => {
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    setProfileValues((current) => ({ ...current, [key]: value }));
  };

  const saveSettings = async () => {
    if (!camera) {
      return;
    }
    const payload: Omit<WriteConfigRequest, "cameras"> = {
      param_updates: {},
      daynight_updates: {},
      light_updates: {},
    };
    for (const [key, value] of Object.entries(draftValues)) {
      const current = Object.values(result.web_settings_catalog ?? {})
        .flat()
        .find((entry) => entry.id === key);
      if (!current) {
        continue;
      }
      const currentValue = current.value;
      if (String(currentValue ?? "") !== value) {
        if (current.writeType === "param" && current.writeKey) {
          payload.param_updates![current.writeKey] = value;
        } else if (current.writeType === "daynight" && current.writeKey) {
          payload.daynight_updates![current.writeKey] =
            value === "true" ? true : value === "false" ? false : /^\d+$/.test(value) ? Number(value) : value;
        } else if (current.writeType === "ir_cut_filter") {
          payload.ir_cut_filter_state = value;
          payload.ir_cut_filter_optics_id = current.writeKey ?? "0";
        } else if (current.writeType === "light_enabled") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: current.writeKey ?? undefined,
            enabled: value === "true",
          };
        } else if (current.writeType === "light_state") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: current.writeKey ?? undefined,
            light_state: value === "true",
          };
        } else if (current.writeType === "light_intensity") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: current.writeKey ?? undefined,
            manual_intensity: Number(value),
          };
        } else if (current.writeType === "light_sync") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: current.writeKey ?? undefined,
            synchronize_day_night_mode: value === "true",
          };
        }
      }
    }
    const nextTimeZone = draftTimeZone.trim();
    const currentTz = currentTimeZone(result);
    if (nextTimeZone && nextTimeZone !== currentTz) {
      payload.time_zone = nextTimeZone;
    }
    const startedAt = Date.now();
    setSettingsStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      title: "Saving settings",
      message: "Applying camera settings.",
    });
    try {
      await onApplyConfig(camera, payload);
      setSettingsStatus({
        phase: "success",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Settings updated",
        message: "Camera settings updated successfully.",
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Camera settings update failed.";
      setSettingsStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Settings update failed",
        message,
      });
    }
  };

  const saveNetworkConfig = async () => {
    if (!camera) {
      return;
    }
    const validationError = validateNetworkDraft(networkDraft);
    if (validationError) {
      setNetworkStatus({
        phase: "error",
        elapsedSeconds: 0,
        message: validationError,
      });
      toast.error("Network update blocked", {
        description: validationError,
      });
      return;
    }
    const confirmation = buildNetworkConfirmation(result.network_config, networkDraft);
    if (!window.confirm(confirmation)) {
      return;
    }
    const startedAt = Date.now();
    setNetworkStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      targetIp:
        networkDraft.ipv4_mode === "static"
          ? networkDraft.ip_address.trim()
          : result.network_config?.ip_address ?? camera.ip,
      message: "Applying network configuration and waiting for the camera to return.",
    });
    try {
      const response = await onApplyNetworkConfig(camera, {
        ipv4_mode: networkDraft.ipv4_mode,
        ip_address:
          networkDraft.ipv4_mode === "static" ? networkDraft.ip_address.trim() : undefined,
        subnet_mask:
          networkDraft.ipv4_mode === "static" ? networkDraft.subnet_mask.trim() : undefined,
        gateway:
          networkDraft.ipv4_mode === "static" ? networkDraft.gateway.trim() : undefined,
        dns_servers:
          networkDraft.ipv4_mode === "static"
            ? [networkDraft.dns1.trim(), networkDraft.dns2.trim()].filter(Boolean)
            : [],
        use_dhcp_hostname: networkDraft.use_dhcp_hostname,
        hostname: networkDraft.use_dhcp_hostname ? undefined : networkDraft.hostname.trim(),
      });
      if (response.ok) {
        setNetworkStatus({
          phase: "success",
          elapsedSeconds: response.elapsed_seconds,
          targetIp: response.target_ip,
          message: `Camera reachable at ${response.target_ip}.`,
          response,
        });
        toast.success("Network settings saved", {
          description: `Camera reachable at ${response.target_ip} after ${response.elapsed_seconds}s.`,
        });
      } else {
        const message = response.errors.join(" ") || "Camera did not return after the network change.";
        setNetworkStatus({
          phase: "error",
          elapsedSeconds: response.elapsed_seconds,
          targetIp: response.target_ip,
          message,
          response,
        });
        toast.error("Network settings failed", {
          description: message,
        });
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Network update failed unexpectedly.";
      setNetworkStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        targetIp:
          networkDraft.ipv4_mode === "static"
            ? networkDraft.ip_address.trim()
            : result.network_config?.ip_address ?? camera.ip,
        message,
      });
      toast.error("Network settings failed", {
        description: message,
      });
    }
  };

  const savePasswordChange = async () => {
    if (!camera) {
      return;
    }
    const validationError = validatePasswordDraft(passwordDraft);
    if (validationError) {
      setPasswordStatus({
        phase: "error",
        elapsedSeconds: 0,
        message: validationError,
      });
      toast.error("Password update blocked", {
        description: validationError,
      });
      return;
    }
    if (
      !window.confirm(
        `Change the password for ${camera.username} on ${result.camera_ip}?\n\nThe app will immediately try to re-authenticate with the new password. Manual rows and uploaded files are not updated automatically.`,
      )
    ) {
      return;
    }
    const startedAt = Date.now();
    setPasswordStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      message: "Updating the password and verifying the new credentials.",
    });
    try {
      const response = await onApplyPasswordChange(camera, passwordDraft.newPassword);
      if (response.credential_status === "verified") {
        setPasswordStatus({
          phase: "success",
          elapsedSeconds: response.elapsed_seconds,
          message: "Password changed and the camera verified with the new credential.",
          response,
        });
        setPasswordDraft({
          newPassword: "",
          confirmPassword: "",
          showPassword: false,
        });
        toast.success("Password changed", {
          description: "The camera re-authenticated with the new password.",
        });
      } else if (response.credential_status === "needs_reauth") {
        setPasswordStatus({
          phase: "warning",
          elapsedSeconds: response.elapsed_seconds,
          message:
            response.errors.join(" ") ||
            "Password may have changed, but the camera could not be re-authenticated automatically.",
          response,
        });
        toast.warning("Password may have changed", {
          description: "Re-enter the new password and refresh the camera if further actions fail.",
        });
      } else {
        setPasswordStatus({
          phase: "error",
          elapsedSeconds: response.elapsed_seconds,
          message: response.errors.join(" ") || "Password change failed.",
          response,
        });
        toast.error("Password change failed", {
          description: response.errors.join(" ") || "Password change failed.",
        });
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Password change failed unexpectedly.";
      setPasswordStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        message,
      });
      toast.error("Password change failed", {
        description: message,
      });
    }
  };

  const startEditingProfile = (name: string) => {
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    const profile = streamProfiles.find((item) => item.name === name);
    if (!profile) {
      return;
    }
    setShowStreamProfileForm(false);
    setEditingProfileName(profile.name);
    setProfileName(profile.name);
    setProfileDescription(profile.description);
    setProfileValues(profile.values ?? {});
  };

  const startCreateProfile = () => {
    setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
    setEditingProfileName(null);
    setProfileName("");
    setProfileDescription("");
    setProfileValues({});
    setShowStreamProfileForm(true);
  };

  const saveProfile = async () => {
    if (!camera || !profileName.trim()) {
      return;
    }
    const payload: StreamProfileInput = {
      name: profileName.trim(),
      description: profileDescription.trim(),
      values: profileValues,
    };
    const startedAt = Date.now();
    const displayName = profileName.trim();
    setStreamProfileStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      title: editingProfileName ? "Updating stream profile" : "Saving stream profile",
      message: editingProfileName ? `Updating ${displayName}.` : `Creating ${displayName}.`,
    });
    try {
      await onApplyStreamProfiles(camera, {
        action: "create_or_update",
        profiles: [payload],
      });
      setEditingProfileName(null);
      setProfileName("");
      setProfileDescription("");
      setProfileValues({});
      setShowStreamProfileForm(false);
      setStreamProfileStatus({
        phase: "success",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: editingProfileName ? "Stream profile updated" : "Stream profile saved",
        message: editingProfileName
          ? `${displayName} updated successfully.`
          : `${displayName} created successfully.`,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Stream profile save failed.";
      setStreamProfileStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: editingProfileName ? "Stream profile update failed" : "Stream profile save failed",
        message,
      });
    }
  };

  const removeProfile = async (name: string) => {
    if (!camera) {
      return;
    }
    const startedAt = Date.now();
    setStreamProfileStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      title: "Removing stream profile",
      message: `Removing ${name}.`,
    });
    try {
      await onApplyStreamProfiles(camera, {
        action: "remove",
        names: [name],
      });
      setStreamProfileStatus({
        phase: "success",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Stream profile removed",
        message: `${name} removed successfully.`,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Stream profile removal failed.";
      setStreamProfileStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Stream profile removal failed",
        message,
      });
    }
  };

  const uploadFirmware = async () => {
    if (!camera || !firmwareFile) {
      return;
    }
    const startedAt = Date.now();
    setFirmwareStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      title: "Uploading firmware",
      message: `Uploading ${firmwareFile.name}.`,
    });
    try {
      await onUploadFirmware(camera, firmwareFile);
      setFirmwareStatus({
        phase: "success",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Firmware command sent",
        message: "Firmware upload started successfully.",
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Firmware upload failed.";
      setFirmwareStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Firmware upload failed",
        message,
      });
    }
  };

  const runFirmwareAction = async (action: FirmwareActionRequest["action"]) => {
    if (!camera) {
      return;
    }
    const startedAt = Date.now();
    setFirmwareStatus({
      phase: "saving",
      startedAt,
      elapsedSeconds: 0,
      title: "Running firmware action",
      message: `Sending ${formatMetricLabel(action)} command.`,
    });
    try {
      await onRunFirmwareAction(camera, { action });
      setFirmwareStatus({
        phase: "success",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Firmware command sent",
        message: `${formatMetricLabel(action)} command sent successfully.`,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Firmware action failed.";
      setFirmwareStatus({
        phase: "error",
        elapsedSeconds: roundElapsedSeconds((Date.now() - startedAt) / 1000),
        title: "Firmware action failed",
        message,
      });
    }
  };

  return (
    <div className="space-y-6 pb-6">
      <CompactOverview result={result} latestFirmwareVersion={latestFirmware?.version} />
      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as DetailTabValue)}
        className="flex flex-col gap-4"
      >
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="access">Access</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="stream-profiles">Stream profiles</TabsTrigger>
          <TabsTrigger value="firmware">Firmware</TabsTrigger>
        </TabsList>
        <TabsContent value="settings" className="space-y-4 mt-0">
          <TimeSectionCompact
            result={result}
            value={draftTimeZone}
            onChange={updateDraftTimeZone}
          />
          {editableGroups.map((group) => (
            <EditableGroupSection
              key={group.groupName}
              title={group.title}
              icon={group.icon}
              items={group.items}
              groupName={group.groupName}
              dynamicOverlays={
                group.groupName === "overlay" ? visibleDynamicOverlays : []
              }
              values={draftValues}
              open={openGroups[group.groupName] ?? false}
              onToggleOpen={() =>
                setOpenGroups((prev) => ({
                  ...prev,
                  [group.groupName]: !(prev[group.groupName] ?? false),
                }))
              }
              onChange={updateDraftValue}
            />
          ))}
        </TabsContent>
        <TabsContent value="access" className="mt-0">
          <AccessSection
            username={camera?.username ?? "root"}
            draft={passwordDraft}
            busy={busy}
            onChange={updatePasswordDraft}
          />
        </TabsContent>
        <TabsContent value="network" className="mt-0">
          <NetworkSection
            networkConfig={networkConfig}
            draft={networkDraft}
            status={networkStatus}
            busy={busy}
            onChange={updateNetworkDraft}
          />
        </TabsContent>
        <TabsContent value="stream-profiles" className="mt-0">
          <StreamProfilesEditor
            profiles={streamProfiles}
            editingProfileName={editingProfileName}
            showCreateForm={showStreamProfileForm}
            profileName={profileName}
            description={profileDescription}
            values={profileValues}
            onEdit={startEditingProfile}
            onRemove={removeProfile}
            onCreateClick={startCreateProfile}
            onNameChange={updateProfileName}
            onDescriptionChange={updateProfileDescription}
            onValueChange={updateProfileValue}
            busy={busy}
          />
        </TabsContent>
        <TabsContent value="firmware" className="mt-0">
          <FirmwareSection
            installedFirmware={result.summary?.firmware ?? "Not available"}
            latestFirmware={latestFirmware?.version ?? "Not available"}
            supportPageUrl={latestFirmware?.support_page_url}
            latestDownloadUrl={latestFirmware?.download_url}
            fallbackSupportUrl="https://www.axis.com/support/firmware"
            file={firmwareFile}
            onFileChange={(file) => {
              setFirmwareStatus({ phase: "idle", elapsedSeconds: 0 });
              setFirmwareFile(file);
            }}
            onUpload={uploadFirmware}
            onAction={runFirmwareAction}
            busy={busy}
            actionsOpen={firmwareActionsOpen}
            onActionsOpenChange={setFirmwareActionsOpen}
            lastWriteResult={lastWriteResult}
            lastWriteNeedsRefresh={lastWriteNeedsRefresh}
            onRefreshCamera={onRefreshCamera}
            refreshInProgress={refreshInProgress}
          />
        </TabsContent>
      </Tabs>
      <StickyDetailActionBar
        activeTab={activeTab}
        settingsStatus={settingsStatus}
        passwordStatus={passwordStatus}
        networkStatus={networkStatus}
        streamProfileStatus={streamProfileStatus}
        firmwareStatus={firmwareStatus}
        showStreamProfileActions={showStreamProfileForm || editingProfileName !== null}
        showFirmwareBar={firmwareStatus.phase !== "idle"}
      >
        {activeTab === "settings" ? (
          <Button onClick={saveSettings} disabled={busy || !camera}>
            {settingsStatus.phase === "saving" ? (
              <>
                <LoaderCircleIcon className="size-4 animate-spin" />
                Saving settings...
              </>
            ) : (
              "Save camera settings"
            )}
          </Button>
        ) : activeTab === "access" ? (
          <Button onClick={savePasswordChange} disabled={busy || !camera}>
            {passwordStatus.phase === "saving" ? (
              <>
                <LoaderCircleIcon className="size-4 animate-spin" />
                Changing password...
              </>
            ) : (
              "Change password"
            )}
          </Button>
        ) : activeTab === "network" ? (
          <Button onClick={saveNetworkConfig} disabled={busy || !camera}>
            {networkStatus.phase === "saving" ? (
              <>
                <LoaderCircleIcon className="size-4 animate-spin" />
                Saving network...
              </>
            ) : (
              "Save network settings"
            )}
          </Button>
        ) : activeTab === "stream-profiles" && (showStreamProfileForm || editingProfileName !== null) ? (
          <>
            <Button
              variant="outline"
              onClick={() => {
                setStreamProfileStatus({ phase: "idle", elapsedSeconds: 0 });
                setEditingProfileName(null);
                setProfileName("");
                setProfileDescription("");
                setProfileValues({});
                setShowStreamProfileForm(false);
              }}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button onClick={saveProfile} disabled={busy || !profileName.trim()}>
              {streamProfileStatus.phase === "saving" ? (
                <>
                  <LoaderCircleIcon className="size-4 animate-spin" />
                  Saving profile...
                </>
              ) : (
                "Save stream profile"
              )}
            </Button>
          </>
        ) : null}
      </StickyDetailActionBar>
    </div>
  );
}

function currentTimeZone(result: CameraResult): string {
  const tzV2 = result.time_info_v2?.data?.timeZone?.activeTimeZone;
  if (tzV2) {
    return tzV2;
  }
  return result.time_info?.data?.timeZone ?? "Not available";
}

function CompactOverview({
  result,
  latestFirmwareVersion,
}: {
  result: CameraResult;
  latestFirmwareVersion?: string;
}) {
  const rows: Array<[string, string]> = [
    ["Model", result.summary?.model ?? "—"],
    ["IP", result.camera_ip ?? "—"],
    ["Firmware", result.summary?.firmware ?? "—"],
    ["Latest", latestFirmwareVersion ?? "—"],
    ["Time zone", currentTimeZone(result)],
    ["Overlay", isOverlayActive(result.summary) ? "On" : "Off"],
    ["SD card", result.summary?.sd_card ?? "—"],
  ];
  return (
    <div className="rounded-lg border bg-muted/20 p-3">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </dt>
            <dd className="break-words font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function getVisibleDynamicOverlays(result: CameraResult["dynamic_overlays"]) {
  const data = result?.data;
  if (!data) {
    return [];
  }
  const visible = [...(data.textOverlays ?? []), ...(data.imageOverlays ?? [])].filter(
    (overlay) => overlay && overlay.visible !== false,
  );
  return visible.map((overlay) => ({
    kind: overlay.kind ?? (overlay.text ? "textOverlays" : "imageOverlays"),
    text: overlay.text,
    indicator: overlay.indicator,
    position: overlay.position,
  }));
}

function EditableGroupSection({
  title,
  icon: Icon,
  items,
  groupName,
  dynamicOverlays,
  values,
  open,
  onToggleOpen,
  onChange,
}: {
  title: string;
  icon: typeof ImageIcon;
  items: WebSettingEntry[];
  groupName: string;
  dynamicOverlays: Array<{
    kind: string;
    text?: string;
    indicator?: string;
    position?: string | [number, number];
  }>;
  values: Record<string, string>;
  open: boolean;
  onToggleOpen: () => void;
  onChange: (key: string, value: string) => void;
}) {
  const guided = items.filter((i) => i.writeType === "guided");
  const editable = items.filter((i) => i.writeType !== "guided");
  return (
    <section className="rounded-lg border bg-muted/10">
      <button
        type="button"
        onClick={onToggleOpen}
        className="flex w-full items-center justify-between gap-2 p-3 text-left hover:bg-muted/20"
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDownIcon className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRightIcon className="size-4 text-muted-foreground" />
          )}
          <Icon className="size-4 text-primary" />
          <h3 className="font-medium">{title}</h3>
        </div>
        <Badge variant="outline" className="text-xs">
          {items.length} controls
        </Badge>
      </button>
      {open && (
        <div className="space-y-3 border-t px-3 pb-3 pt-2">
          {groupName === "overlay" && dynamicOverlays.length > 0 ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
              <p className="font-medium">Active dynamic overlays detected</p>
              <p className="mt-1 text-amber-900">
                The camera is drawing additional overlays through Axis dynamic overlays. These
                are separate from the legacy `Text enabled / Show clock / Show date` fields below.
              </p>
              <div className="mt-2 space-y-2">
                {dynamicOverlays.map((overlay, index) => (
                  <div key={`${overlay.kind}-${index}`} className="rounded border border-amber-200 bg-white/70 p-2">
                    <p className="font-medium">
                      {overlay.kind === "textOverlays" ? "Text overlay" : "Image overlay"}
                    </p>
                    {overlay.text ? <p className="mt-0.5 break-words">{overlay.text}</p> : null}
                    {overlay.indicator ? (
                      <p className="mt-0.5 text-xs text-amber-900/80">Indicator: {overlay.indicator}</p>
                    ) : null}
                    {overlay.position ? (
                      <p className="mt-0.5 text-xs text-amber-900/80">
                        Position: {Array.isArray(overlay.position) ? overlay.position.join(", ") : overlay.position}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {guided.length > 0 && (
            <div className="space-y-2">
              {guided.map((item) => (
                <div
                  key={item.id}
                  className="rounded-md border bg-card/60 p-2 text-sm text-muted-foreground"
                >
                  <span className="font-medium text-foreground">{item.label}</span>
                  <p className="mt-0.5">{item.guidance ?? "Set from the camera UI."}</p>
                </div>
              ))}
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {editable.map((item) => (
              <div key={item.id} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-sm font-medium">{item.label}</label>
                  {item.writable === false && (
                    <Badge variant="outline" className="text-xs">
                      Read only
                    </Badge>
                  )}
                </div>
                <FieldInput
                  entry={item}
                  value={values[item.id] ?? String(item.value ?? "")}
                  onChange={(value) => onChange(item.id, value)}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function FieldInput({
  entry,
  value,
  onChange,
}: {
  entry: WebSettingEntry | undefined;
  value: string;
  onChange: (value: string) => void;
}) {
  if (!entry) {
    return null;
  }
  const options = entry.options ?? [];
  if (entry.inputKind === "select" && options.length > 0) {
    return (
      <NativeSelect
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={entry.writable === false}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </NativeSelect>
    );
  }
  return (
    <div className="space-y-2">
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={entry.writable === false}
      />
      {(entry.min !== null && entry.min !== undefined) ||
      (entry.max !== null && entry.max !== undefined) ? (
        <p className="text-xs text-muted-foreground">
          Range: {entry.min ?? "—"} to {entry.max ?? "—"}
        </p>
      ) : null}
    </div>
  );
}

function TimeSectionCompact({
  result,
  value,
  onChange,
}: {
  result: CameraResult;
  value: string;
  onChange: (value: string) => void;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const currentTimeZoneValue = currentTimeZone(result);
  const timeZoneOptions = getSupportedUsTimeZones(result.time_zone_options);
  const selectedValue = timeZoneOptions.includes(value) ? value : "";
  const utc = result.time_info_v2?.data?.time?.dateTime ?? result.time_info?.data?.dateTime;
  const local =
    result.time_info_v2?.data?.time?.localDateTime ??
    result.time_info?.data?.localDateTime;
  return (
    <section className="space-y-2 rounded-lg border bg-muted/10 p-3">
      <div className="flex items-center gap-2">
        <Clock3Icon className="size-4 text-primary" />
        <h3 className="font-medium">Time zone</h3>
      </div>
      <NativeSelect
        value={selectedValue}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">
          {currentTimeZoneValue !== "Not available"
            ? `Keep current (${currentTimeZoneValue})`
            : "Select U.S. time zone"}
        </option>
        {timeZoneOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </NativeSelect>
      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        {showDetails ? "Hide" : "Show"} UTC / local time
      </button>
      {showDetails && (
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded border bg-background/70 p-2">
            <span className="text-xs text-muted-foreground">UTC</span>
            <p className="mt-0.5">{utc ?? "Not available"}</p>
          </div>
          <div className="rounded border bg-background/70 p-2">
            <span className="text-xs text-muted-foreground">Local</span>
            <p className="mt-0.5">{local ?? "Not available"}</p>
          </div>
        </div>
      )}
    </section>
  );
}

type NetworkDraft = {
  ipv4_mode: "dhcp" | "static";
  ip_address: string;
  subnet_mask: string;
  gateway: string;
  dns1: string;
  dns2: string;
  hostname: string;
  use_dhcp_hostname: boolean;
};

type NetworkStatusState = {
  phase: "idle" | "saving" | "success" | "error";
  startedAt?: number;
  elapsedSeconds: number;
  targetIp?: string;
  message?: string;
  response?: NetworkConfigResponse;
};

type PasswordDraft = {
  newPassword: string;
  confirmPassword: string;
  showPassword: boolean;
};

type PasswordStatusState = {
  phase: "idle" | "saving" | "success" | "warning" | "error";
  startedAt?: number;
  elapsedSeconds: number;
  message?: string;
  response?: PasswordChangeResult;
};

type DetailActionStatusState = {
  phase: "idle" | "saving" | "success" | "error";
  startedAt?: number;
  elapsedSeconds: number;
  title?: string;
  message?: string;
};

type StickyActionStatusState = {
  phase: "idle" | "saving" | "success" | "warning" | "error";
  elapsedSeconds: number;
  title?: string;
  message?: string;
};

function roundElapsedSeconds(value: number): number {
  return Math.round(value * 10) / 10;
}

function validatePasswordDraft(draft: PasswordDraft): string | null {
  if (!draft.newPassword.trim()) {
    return "A new password is required.";
  }
  if (!draft.confirmPassword.trim()) {
    return "Confirm the new password before saving.";
  }
  if (draft.newPassword !== draft.confirmPassword) {
    return "The new password and confirmation must match.";
  }
  return null;
}

function buildNetworkDraft(networkConfig?: CameraNetworkConfig | null): NetworkDraft {
  return {
    ipv4_mode: networkConfig?.ipv4_mode === "static" ? "static" : "dhcp",
    ip_address: networkConfig?.ip_address ?? "",
    subnet_mask: networkConfig?.subnet_mask ?? "",
    gateway: networkConfig?.gateway ?? "",
    dns1: networkConfig?.dns_servers?.[0] ?? "",
    dns2: networkConfig?.dns_servers?.[1] ?? "",
    hostname: networkConfig?.static_hostname ?? networkConfig?.hostname ?? "",
    use_dhcp_hostname: networkConfig?.use_dhcp_hostname ?? false,
  };
}

function isValidIpv4(value: string): boolean {
  const parts = value.trim().split(".");
  if (parts.length !== 4) {
    return false;
  }
  return parts.every((part) => {
    if (!/^\d+$/.test(part)) {
      return false;
    }
    const num = Number(part);
    return num >= 0 && num <= 255;
  });
}

function isValidSubnetMask(value: string): boolean {
  if (!isValidIpv4(value)) {
    return false;
  }
  const binary = value
    .split(".")
    .map((part) => Number(part).toString(2).padStart(8, "0"))
    .join("");
  return /^1+0+$/.test(binary) || binary === "1".repeat(32);
}

function isValidHostnameValue(value: string): boolean {
  const hostname = value.trim();
  if (!hostname || hostname.length > 253 || !/^[a-zA-Z0-9.-]+$/.test(hostname)) {
    return false;
  }
  const labels = hostname.split(".");
  return labels.every(
    (label) =>
      label.length > 0 &&
      label.length <= 63 &&
      !label.startsWith("-") &&
      !label.endsWith("-"),
  );
}

function validateNetworkDraft(draft: NetworkDraft): string | null {
  if (draft.ipv4_mode === "static") {
    if (!draft.ip_address.trim()) {
      return "Static mode requires an IP address.";
    }
    if (!isValidIpv4(draft.ip_address)) {
      return "Static IP address must be a valid IPv4 address.";
    }
    if (!draft.subnet_mask.trim()) {
      return "Static mode requires a subnet mask.";
    }
    if (!isValidSubnetMask(draft.subnet_mask)) {
      return "Subnet mask must be a valid IPv4 subnet mask.";
    }
    if (!draft.gateway.trim()) {
      return "Static mode requires a gateway IPv4 address.";
    }
    if (!isValidIpv4(draft.gateway)) {
      return "Gateway must be a valid IPv4 address.";
    }
    if (!draft.dns1.trim()) {
      return "Static mode requires DNS 1.";
    }
    if (!isValidIpv4(draft.dns1)) {
      return "DNS 1 must be a valid IPv4 address.";
    }
    if (draft.dns2.trim() && !isValidIpv4(draft.dns2)) {
      return "DNS 2 must be a valid IPv4 address.";
    }
  }
  if (!draft.use_dhcp_hostname) {
    if (!draft.hostname.trim()) {
      return "Hostname is required when DHCP hostname is disabled.";
    }
    if (!isValidHostnameValue(draft.hostname)) {
      return "Hostname must be a valid DNS hostname.";
    }
  }
  return null;
}

function buildNetworkConfirmation(
  currentConfig: CameraNetworkConfig | null | undefined,
  draft: NetworkDraft,
): string {
  const lines = [
    "Apply these network settings?",
    "",
    `IPv4 mode: ${currentConfig?.ipv4_mode ?? "unknown"} -> ${draft.ipv4_mode}`,
    `IP address: ${currentConfig?.ip_address ?? "—"} -> ${
      draft.ipv4_mode === "static" ? draft.ip_address.trim() || "—" : "DHCP"
    }`,
    `Subnet mask: ${currentConfig?.subnet_mask ?? "—"} -> ${
      draft.ipv4_mode === "static" ? draft.subnet_mask.trim() || "—" : "DHCP"
    }`,
    `Gateway: ${currentConfig?.gateway ?? "—"} -> ${
      draft.ipv4_mode === "static" ? draft.gateway.trim() || "—" : "DHCP"
    }`,
    `DNS: ${(currentConfig?.dns_servers ?? []).join(", ") || "—"} -> ${
      draft.ipv4_mode === "static"
        ? [draft.dns1.trim(), draft.dns2.trim()].filter(Boolean).join(", ") || "—"
        : "DHCP"
    }`,
    `Use DHCP hostname: ${currentConfig?.use_dhcp_hostname ? "Yes" : "No"} -> ${
      draft.use_dhcp_hostname ? "Yes" : "No"
    }`,
    `Hostname: ${currentConfig?.hostname ?? "—"} -> ${
      draft.use_dhcp_hostname ? "Network provided" : draft.hostname.trim() || "—"
    }`,
  ];
  return lines.join("\n");
}

function mapPasswordStatusToSticky(status: PasswordStatusState): StickyActionStatusState {
  return {
    phase: status.phase,
    elapsedSeconds: status.elapsedSeconds,
    title:
      status.phase === "saving"
        ? "Updating password"
        : status.phase === "success"
          ? "Password verified"
          : status.phase === "warning"
            ? "Re-authentication required"
            : status.phase === "error"
              ? "Password change failed"
              : undefined,
    message: status.message,
  };
}

function mapNetworkStatusToSticky(status: NetworkStatusState): StickyActionStatusState {
  return {
    phase: status.phase,
    elapsedSeconds: status.elapsedSeconds,
    title:
      status.phase === "saving"
        ? "Saving network settings"
        : status.phase === "success"
          ? "Camera reachable"
          : status.phase === "error"
            ? "Network update failed"
            : undefined,
    message: status.message,
  };
}

function StickyDetailActionBar({
  activeTab,
  settingsStatus,
  passwordStatus,
  networkStatus,
  streamProfileStatus,
  firmwareStatus,
  showStreamProfileActions,
  showFirmwareBar,
  children,
}: {
  activeTab: DetailTabValue;
  settingsStatus: DetailActionStatusState;
  passwordStatus: PasswordStatusState;
  networkStatus: NetworkStatusState;
  streamProfileStatus: DetailActionStatusState;
  firmwareStatus: DetailActionStatusState;
  showStreamProfileActions: boolean;
  showFirmwareBar: boolean;
  children?: ReactNode;
}) {
  const status: StickyActionStatusState =
    activeTab === "settings"
      ? settingsStatus
      : activeTab === "access"
        ? mapPasswordStatusToSticky(passwordStatus)
        : activeTab === "network"
          ? mapNetworkStatusToSticky(networkStatus)
          : activeTab === "stream-profiles"
            ? streamProfileStatus
            : firmwareStatus;

  const visible =
    activeTab === "settings" ||
    activeTab === "access" ||
    activeTab === "network" ||
    (activeTab === "stream-profiles" &&
      (showStreamProfileActions || status.phase !== "idle")) ||
    (activeTab === "firmware" && showFirmwareBar);

  if (!visible) {
    return null;
  }

  return (
    <div className="sticky bottom-0 z-20 -mx-6 mt-6 border-t bg-background/95 px-6 py-4 shadow-[0_-8px_24px_-16px_rgba(0,0,0,0.25)] backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        {status.phase === "idle" ? (
          <div className="text-sm text-muted-foreground">
            {activeTab === "settings"
              ? "Save changes when you are ready."
              : activeTab === "access"
                ? "Apply the new password when you are ready."
                : activeTab === "network"
                  ? "Apply the network changes when you are ready."
                  : activeTab === "stream-profiles"
                    ? "Review the profile details, then save."
                    : "Firmware progress will appear here while commands are running."}
          </div>
        ) : (
          <div className="flex items-start gap-3 text-sm">
            {status.phase === "saving" ? (
              <LoaderCircleIcon className="mt-0.5 size-4 shrink-0 animate-spin" />
            ) : status.phase === "success" ? (
              <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-600" />
            ) : (
              <TriangleAlertIcon
                className={`mt-0.5 size-4 shrink-0 ${
                  status.phase === "warning" ? "text-amber-600" : "text-destructive"
                }`}
              />
            )}
            <div className="space-y-0.5">
              <p className="font-medium">{status.title}</p>
              {status.message ? <p className="text-muted-foreground">{status.message}</p> : null}
              <p className="text-xs text-muted-foreground">
                Elapsed: {status.elapsedSeconds.toFixed(1)}s
              </p>
            </div>
          </div>
        )}
        {children ? (
          <div className="flex flex-wrap justify-end gap-2">{children}</div>
        ) : null}
      </div>
    </div>
  );
}

function AccessSection({
  username,
  draft,
  busy,
  onChange,
}: {
  username: string;
  draft: PasswordDraft;
  busy: boolean;
  onChange: <K extends keyof PasswordDraft>(key: K, value: PasswordDraft[K]) => void;
}) {
  return (
    <section className="space-y-4">
      <div className="rounded-lg border bg-muted/10 p-4">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheckIcon className="size-4 text-primary" />
          <h3 className="font-medium">Access</h3>
        </div>
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <InfoTile label="Current username" value={username || "—"} />
          <div className="rounded border bg-background/70 p-3">
            <span className="text-xs text-muted-foreground">Password change behavior</span>
            <p className="mt-0.5 font-medium">
              The app will try to re-authenticate immediately after the password update.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-lg border bg-card/60 p-4 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon className="size-4 text-primary" />
          <h3 className="font-medium">Change password</h3>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldGroup label="New password">
            <Input
              type={draft.showPassword ? "text" : "password"}
              value={draft.newPassword}
              onChange={(event) => onChange("newPassword", event.target.value)}
              disabled={busy}
              placeholder="New camera password"
            />
          </FieldGroup>
          <FieldGroup label="Confirm new password">
            <Input
              type={draft.showPassword ? "text" : "password"}
              value={draft.confirmPassword}
              onChange={(event) => onChange("confirmPassword", event.target.value)}
              disabled={busy}
              placeholder="Confirm new camera password"
            />
          </FieldGroup>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={draft.showPassword}
              onChange={(event) => onChange("showPassword", event.target.checked)}
              disabled={busy}
            />
            Show password text
          </label>
        </div>
      </div>
    </section>
  );
}

function NetworkSection({
  networkConfig,
  draft,
  status,
  busy,
  onChange,
}: {
  networkConfig?: CameraNetworkConfig | null;
  draft: NetworkDraft;
  status: NetworkStatusState;
  busy: boolean;
  onChange: <K extends keyof NetworkDraft>(key: K, value: NetworkDraft[K]) => void;
}) {
  if (!networkConfig) {
    return (
      <section className="rounded-lg border bg-muted/10 p-4 text-sm text-muted-foreground">
        Network configuration details were not available from this camera.
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="rounded-lg border bg-muted/10 p-4">
        <div className="mb-3 flex items-center gap-2">
          <ServerIcon className="size-4 text-primary" />
          <h3 className="font-medium">Current network state</h3>
        </div>
        {(networkConfig.additional_ipv4_addresses ?? []).length > 0 && (
          <div className="mb-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
            <p className="font-medium">Additional IPv4 address detected</p>
            <p className="mt-1">
              This camera is currently reporting more than one non-link-local IPv4 address:
              {" "}
              {(networkConfig.additional_ipv4_addresses ?? []).join(", ")}.
            </p>
          </div>
        )}
        <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <InfoTile label="Interface" value={networkConfig.interface_name ?? "—"} />
          <InfoTile label="IPv4 mode" value={networkConfig.ipv4_mode ?? "—"} />
          <InfoTile label="IP address" value={networkConfig.ip_address ?? "—"} />
          <InfoTile label="Subnet mask" value={networkConfig.subnet_mask ?? "—"} />
          <InfoTile label="Gateway" value={networkConfig.gateway ?? "—"} />
          <InfoTile label="DNS servers" value={(networkConfig.dns_servers ?? []).join(", ") || "—"} />
          <InfoTile label="Hostname" value={networkConfig.hostname ?? "—"} />
          <InfoTile label="Static hostname" value={networkConfig.static_hostname ?? "—"} />
          <InfoTile label="DHCP hostname" value={networkConfig.use_dhcp_hostname ? "Yes" : "No"} />
        </div>
        {(networkConfig.ipv4_addresses ?? []).length > 0 && (
          <div className="mt-3 rounded border bg-background/70 p-3 text-sm">
            <span className="text-xs text-muted-foreground">Reported IPv4 addresses</span>
            <div className="mt-2 space-y-1">
              {(networkConfig.ipv4_addresses ?? []).map((entry) => (
                <p key={`${entry.address}-${entry.prefix_length}-${entry.scope}`} className="font-medium">
                  {entry.address}
                  {entry.prefix_length != null ? ` / ${entry.prefix_length}` : ""}
                  {entry.origin ? ` · ${entry.origin}` : ""}
                  {entry.scope ? ` · ${entry.scope}` : ""}
                  {entry.is_active ? " · active" : ""}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>

      {status.phase !== "idle" && (
        <div
          className={`rounded-lg border p-4 text-sm ${
            status.phase === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : status.phase === "error"
                ? "border-destructive/30 bg-destructive/5 text-destructive"
                : "border-primary/20 bg-primary/5 text-foreground"
          }`}
        >
          <div className="flex items-start gap-3">
            {status.phase === "saving" ? (
              <LoaderCircleIcon className="mt-0.5 size-4 animate-spin" />
            ) : status.phase === "success" ? (
              <CheckCircle2Icon className="mt-0.5 size-4" />
            ) : (
              <TriangleAlertIcon className="mt-0.5 size-4" />
            )}
            <div className="space-y-1">
              <p className="font-medium">
                {status.phase === "saving"
                  ? "Waiting for camera to return"
                  : status.phase === "success"
                    ? "Camera reachable"
                    : "Network update failed"}
              </p>
              <p>{status.message}</p>
              <p className="text-xs opacity-80">
                Elapsed: {status.elapsedSeconds.toFixed(1)}s
                {status.targetIp ? ` · Target IP: ${status.targetIp}` : ""}
                {status.response ? ` · Poll attempts: ${status.response.poll_attempts}` : ""}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg border bg-card/60 p-4 space-y-4">
        <div className="flex items-center gap-2">
          <ServerIcon className="size-4 text-primary" />
          <h3 className="font-medium">Edit network settings</h3>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1.5 text-sm">
            <span className="font-medium">IPv4 mode</span>
            <NativeSelect
              value={draft.ipv4_mode}
              onChange={(event) => onChange("ipv4_mode", event.target.value as NetworkDraft["ipv4_mode"])}
              disabled={busy}
            >
              <option value="dhcp">DHCP</option>
              <option value="static">Static</option>
            </NativeSelect>
          </label>
          <div className="rounded border bg-background/70 p-3 text-sm">
            <span className="text-xs text-muted-foreground">MAC address</span>
            <p className="mt-0.5 font-medium">{networkConfig.mac_address ?? "Not available"}</p>
          </div>
        </div>

        {draft.ipv4_mode === "static" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldGroup label="IP address">
              <Input
                value={draft.ip_address}
                onChange={(event) => onChange("ip_address", event.target.value)}
                disabled={busy}
                placeholder="192.168.1.221"
              />
            </FieldGroup>
            <FieldGroup label="Subnet mask">
              <Input
                value={draft.subnet_mask}
                onChange={(event) => onChange("subnet_mask", event.target.value)}
                disabled={busy}
                placeholder="255.255.255.0"
              />
            </FieldGroup>
            <FieldGroup label="Gateway">
              <Input
                value={draft.gateway}
                onChange={(event) => onChange("gateway", event.target.value)}
                disabled={busy}
                placeholder="192.168.1.1"
              />
            </FieldGroup>
            <FieldGroup label="DNS 1">
              <Input
                value={draft.dns1}
                onChange={(event) => onChange("dns1", event.target.value)}
                disabled={busy}
                placeholder="8.8.8.8"
              />
            </FieldGroup>
            <FieldGroup label="DNS 2">
              <Input
                value={draft.dns2}
                onChange={(event) => onChange("dns2", event.target.value)}
                disabled={busy}
                placeholder="8.8.4.4"
              />
            </FieldGroup>
          </div>
        )}

        <div className="space-y-3 rounded-lg border bg-muted/10 p-3">
          <div>
            <p className="text-sm font-medium">Hostname</p>
            <p className="text-xs text-muted-foreground">
              Current effective hostname: {networkConfig.hostname ?? "Not available"}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">Use DHCP hostname</span>
              <NativeSelect
                value={draft.use_dhcp_hostname ? "true" : "false"}
                onChange={(event) => onChange("use_dhcp_hostname", event.target.value === "true")}
                disabled={busy}
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </NativeSelect>
            </label>
            <FieldGroup label="Hostname">
              <Input
                value={draft.hostname}
                onChange={(event) => onChange("hostname", event.target.value)}
                disabled={busy || draft.use_dhcp_hostname}
                placeholder="axis-parking-lpr-01"
              />
            </FieldGroup>
          </div>
        </div>
      </div>
    </section>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border bg-background/70 p-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="mt-0.5 font-medium break-words">{value}</p>
    </div>
  );
}

function FieldGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

function StreamProfilesEditor({
  profiles,
  editingProfileName,
  showCreateForm,
  profileName,
  description,
  values,
  onEdit,
  onRemove,
  onCreateClick,
  onNameChange,
  onDescriptionChange,
  onValueChange,
  busy,
}: {
  profiles: CameraResult["stream_profiles_structured"];
  editingProfileName: string | null;
  showCreateForm: boolean;
  profileName: string;
  description: string;
  values: Record<string, string>;
  onEdit: (name: string) => void;
  onRemove: (name: string) => Promise<void>;
  onCreateClick: () => void;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onValueChange: (key: string, value: string) => void;
  busy: boolean;
}) {
  const showForm = showCreateForm || editingProfileName !== null;
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <VideoIcon className="size-4 text-primary" />
          <h3 className="font-medium">Stream profiles</h3>
        </div>
        {!showForm && (
          <Button variant="outline" size="sm" onClick={onCreateClick} disabled={busy}>
            Create stream profile
          </Button>
        )}
      </div>
      <div className="space-y-3">
        {(profiles ?? []).map((profile) => (
          <div key={profile.name} className="rounded-lg border bg-card/60 p-3 space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{profile.name}</p>
                <p className="text-xs text-muted-foreground">{profile.description || "No description"}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => onEdit(profile.name)} disabled={busy}>
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    if (window.confirm(`Remove stream profile "${profile.name}"?`)) {
                      await onRemove(profile.name);
                    }
                  }}
                  disabled={busy}
                >
                  Remove
                </Button>
              </div>
            </div>
            <div className="grid gap-2 grid-cols-2 sm:grid-cols-4 text-sm">
              {getMetricRows(profile.values, ["resolution", "fps", "videocodec", "compression"]).map((row) => (
                <div key={`${profile.name}-${row.key}`} className="rounded border bg-background/70 px-2 py-1">
                  <span className="text-xs text-muted-foreground">{row.label}</span>
                  <p className="font-medium">{row.value}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
        {showForm && (
          <div className="rounded-lg border bg-card/60 p-4 space-y-3">
            <h4 className="font-medium">
              {editingProfileName ? `Edit ${editingProfileName}` : "Create stream profile"}
            </h4>
            <Input value={profileName} onChange={(event) => onNameChange(event.target.value)} placeholder="Profile name" />
            <Input
              value={description}
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder="Description"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              {STREAM_PROFILE_FIELDS.map((field) => (
                <div key={field.key} className="space-y-1">
                  <label className="text-sm font-medium">{field.label}</label>
                  <Input
                    value={values[field.key] ?? ""}
                    onChange={(event) => onValueChange(field.key, event.target.value)}
                    placeholder={formatMetricLabel(field.key)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function FirmwareSection({
  installedFirmware,
  latestFirmware,
  supportPageUrl,
  latestDownloadUrl,
  fallbackSupportUrl,
  file,
  onFileChange,
  onUpload,
  onAction,
  busy,
  actionsOpen,
  onActionsOpenChange,
  lastWriteResult,
  lastWriteNeedsRefresh,
  onRefreshCamera,
  refreshInProgress,
}: {
  installedFirmware: string;
  latestFirmware: string;
  supportPageUrl?: string;
  latestDownloadUrl?: string;
  fallbackSupportUrl: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  onUpload: () => Promise<void>;
  onAction: (action: FirmwareActionRequest["action"]) => Promise<void>;
  busy: boolean;
  actionsOpen: boolean;
  onActionsOpenChange: (open: boolean) => void;
  lastWriteResult?: WriteResult | null;
  lastWriteNeedsRefresh?: boolean;
  onRefreshCamera?: () => Promise<void>;
  refreshInProgress?: boolean;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon className="size-4 text-primary" />
          <h3 className="font-medium">Firmware</h3>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onActionsOpenChange(!actionsOpen)}
        >
          {actionsOpen ? "Hide" : "Show"} actions
        </Button>
      </div>
      <div className="rounded-lg border bg-card/60 p-3">
        {busy && (
          <p className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
            <span className="inline-block size-2 animate-pulse rounded-full bg-primary" />
            Uploading firmware or applying action…
          </p>
        )}
        {lastWriteResult && lastWriteNeedsRefresh && !busy && (
          <div className="mb-3 space-y-2">
            <p className="text-xs text-muted-foreground">
              {lastWriteResult.ok
                ? lastWriteNeedsRefresh
                  ? "Firmware command sent. Displayed version may stay stale until the camera reboots."
                  : "Last write: success."
                : `Last write failed: ${lastWriteResult.errors.join(", ") || "Unknown error"}.`}
            </p>
            {lastWriteNeedsRefresh && onRefreshCamera && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onRefreshCamera}
                disabled={busy || refreshInProgress}
              >
                <RefreshCwIcon className="size-4" />
                Refresh this camera
              </Button>
            )}
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded border bg-background/70 p-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Installed
            </p>
            <p className="mt-0.5 text-sm font-medium">{installedFirmware}</p>
          </div>
          <div className="rounded border bg-background/70 p-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Latest official
            </p>
            <p className="mt-0.5 text-sm font-medium">{latestFirmware}</p>
            <a
              className="mt-1 inline-block text-xs text-primary underline"
              href={supportPageUrl || fallbackSupportUrl}
              target="_blank"
              rel="noreferrer"
            >
              {supportPageUrl ? "Open Axis firmware page" : "Open Axis firmware portal"}
            </a>
            {latestDownloadUrl ? (
              <a
                className="mt-1 block text-xs text-primary underline"
                href={latestDownloadUrl}
                target="_blank"
                rel="noreferrer"
              >
                Direct download
              </a>
            ) : null}
          </div>
        </div>
        {actionsOpen && (
          <div className="mt-3 space-y-3 border-t pt-3">
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".bin"
                onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
                className="max-w-xs text-sm"
              />
              <Button
                onClick={async () => {
                  if (window.confirm("Upload this firmware file and start upgrade on this camera?")) {
                    await onUpload();
                  }
                }}
                disabled={busy || !file}
              >
                <UploadIcon className="size-4" />
                Upload and upgrade
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  if (window.confirm("Commit the current firmware and stop rollback?")) {
                    await onAction("commit");
                  }
                }}
                disabled={busy}
              >
                Commit
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  if (window.confirm("Rollback to previous firmware? The camera may reboot.")) {
                    await onAction("rollback");
                  }
                }}
                disabled={busy}
              >
                Rollback
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  if (window.confirm("Purge inactive firmware? Rollback will no longer be possible.")) {
                    await onAction("purge");
                  }
                }}
                disabled={busy}
              >
                Purge
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  if (window.confirm("Reboot this camera now?")) {
                    await onAction("reboot");
                  }
                }}
                disabled={busy}
              >
                Reboot
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

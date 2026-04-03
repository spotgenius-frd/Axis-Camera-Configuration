"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { InfoIcon, LoaderCircleIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react";
import { toast } from "sonner";

import { BatchSummaryBar } from "@/components/camera/batch-summary-bar";
import { BulkActionBar } from "@/components/camera/bulk-action-bar";
import { CameraDetailSheet } from "@/components/camera/camera-detail-sheet";
import { CameraPageHeader } from "@/components/camera/camera-page-header";
import { InputWorkspace } from "@/components/camera/input-workspace";
import { ResultsDataTable } from "@/components/camera/results-data-table";
import { ResultsEmptyState } from "@/components/camera/results-empty-state";
import { ResultsLoadingState } from "@/components/camera/results-loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type {
  BulkTargetMode,
  CameraConnection,
  NetworkConfigRequest,
  NetworkConfigResponse,
  NetworkScanRequest,
  NetworkScanResponse,
  PasswordChangeResponse,
  PasswordChangeResult,
  CameraRequestInput,
  CameraResult,
  CameraRow,
  FirmwareActionRequest,
  ScanInterfaceOption,
  ScanTarget,
  ScannedAxisDevice,
  StreamProfileApplyRequest,
  WriteConfigRequest,
  WriteResponse,
  WriteResult,
} from "@/lib/camera-types";
import {
  applyStreamProfiles,
  changeCameraPasswords,
  getNetworkScanOptions,
  readConfigFromManual,
  readConfigFromUpload,
  runNetworkScan,
  runFirmwareAction,
  updateNetworkConfig,
  uploadFirmwareAndUpgrade,
  writeCameraConfig,
} from "@/lib/api";
import {
  INITIAL_ROW_ID,
  defaultRow,
  getApiUrl,
  getFetchHint,
  getManualValidationSummary,
  getResultStats,
  isEmptyManualRow,
  validateUploadFile,
} from "@/lib/camera-utils";

function formatTimestamp(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function scannedDeviceToRow(
  device: ScannedAxisDevice,
  username: string,
  password: string,
): CameraRow {
  const row = defaultRow();
  row.name = (device.hostname || device.model || "").trim();
  row.ip = device.ip;
  row.port = String(device.http_port ?? 80);
  row.username = username.trim() || "root";
  row.password = password;
  return row;
}

function rowHostKey(row: Pick<CameraRow, "ip" | "port">): string {
  return `${row.ip.trim().toLowerCase()}:${row.port.trim() || "80"}`;
}

function mergeImportedRows(currentRows: CameraRow[], importedRows: CameraRow[]) {
  const nextRows = currentRows.map((row) => ({ ...row }));
  const emptyIndices = nextRows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => isEmptyManualRow(row))
    .map(({ index }) => index);
  const existingKeys = new Set(
    nextRows
      .filter((row) => !isEmptyManualRow(row) && row.ip.trim())
      .map((row) => rowHostKey(row)),
  );

  let added = 0;
  let skipped = 0;

  for (const row of importedRows) {
    const key = rowHostKey(row);
    if (existingKeys.has(key)) {
      skipped += 1;
      continue;
    }
    existingKeys.add(key);
    const emptyIndex = emptyIndices.shift();
    if (emptyIndex !== undefined) {
      nextRows[emptyIndex] = row;
    } else {
      nextRows.push(row);
    }
    added += 1;
  }

  return { rows: nextRows, added, skipped };
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<"manual" | "upload" | "scan">("manual");
  const [manualRows, setManualRows] = useState<CameraRow[]>(() => [
    defaultRow(INITIAL_ROW_ID),
  ]);
  const [results, setResults] = useState<CameraResult[] | null>(null);
  const [selectedResult, setSelectedResult] = useState<CameraResult | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [runningMode, setRunningMode] = useState<"manual" | "upload" | null>(
    null,
  );
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [writeBusy, setWriteBusy] = useState(false);
  const [networkBusy, setNetworkBusy] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [writeStatus, setWriteStatus] = useState<{
    label: string;
    targetSummary: string;
  } | null>(null);
  const [lastWriteResults, setLastWriteResults] = useState<WriteResult[] | null>(null);
  const [lastWriteNeedsRefresh, setLastWriteNeedsRefresh] = useState(false);
  const [lastPasswordChangeResults, setLastPasswordChangeResults] =
    useState<PasswordChangeResult[] | null>(null);
  const [refreshInProgress, setRefreshInProgress] = useState(false);
  const [selectedCameraIps, setSelectedCameraIps] = useState<string[]>([]);
  const [scanInterfaceOptions, setScanInterfaceOptions] = useState<ScanInterfaceOption[]>([]);
  const [scanTarget, setScanTarget] = useState<ScanTarget | null>(null);
  const [scanDevices, setScanDevices] = useState<ScannedAxisDevice[]>([]);
  const [scanErrors, setScanErrors] = useState<string[]>([]);
  const [scanSelectedIps, setScanSelectedIps] = useState<string[]>([]);
  const [scanInterfaceName, setScanInterfaceName] = useState("");
  const [scanCidr, setScanCidr] = useState("");
  const [scanDefaultUsername, setScanDefaultUsername] = useState("root");
  const [scanDefaultPassword, setScanDefaultPassword] = useState("");
  const [scanLoadingOptions, setScanLoadingOptions] = useState(false);
  const [scanOptionsLoaded, setScanOptionsLoaded] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanImportBusy, setScanImportBusy] = useState(false);
  const [inputWorkspaceCollapsed, setInputWorkspaceCollapsed] = useState(false);
  const [liveMessage, setLiveMessage] = useState(
    "Ready to read Axis camera configuration.",
  );
  const [lastRunAt, setLastRunAt] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const resolvedApiBase = apiBase ?? "http://localhost:8000";
  const isLoading = runningMode !== null;
  const uploadError = uploadFile ? validateUploadFile(uploadFile) : null;
  const { errorsByRow, readyCount, invalidCount } = useMemo(
    () => getManualValidationSummary(manualRows),
    [manualRows],
  );

  useEffect(() => {
    setApiBase(getApiUrl());
  }, []);

  const setScanResponse = useCallback((data: NetworkScanResponse) => {
    setScanInterfaceOptions(data.interface_options);
    setScanTarget(data.scan_target ?? null);
    setScanDevices(data.devices);
    setScanErrors(data.errors);
    setScanSelectedIps([]);
    setScanInterfaceName(
      data.scan_target?.interface_name ??
        data.interface_options[0]?.name ??
        "",
    );
    setScanCidr(data.scan_target?.cidr ?? scanCidr);
  }, [scanCidr]);

  const loadScanOptions = useCallback(async (params?: NetworkScanRequest) => {
    if (!apiBase || scanLoadingOptions) {
      return;
    }
    setScanLoadingOptions(true);
    try {
      const data = await getNetworkScanOptions(apiBase, params);
      setScanResponse(data);
      if (data.interface_options.length === 0 && data.errors.length === 0) {
        setScanErrors(["The backend did not return any usable IPv4 interfaces."]);
      }
      setScanOptionsLoaded(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load scan options.";
      setScanErrors([message]);
      setScanOptionsLoaded(true);
    } finally {
      setScanLoadingOptions(false);
    }
  }, [apiBase, scanLoadingOptions, setScanResponse]);

  useEffect(() => {
    if (!apiBase || scanOptionsLoaded) {
      return;
    }
    void loadScanOptions();
  }, [apiBase, scanOptionsLoaded, loadScanOptions]);

  const addCamera = () => {
    setManualRows((rows) => [...rows, defaultRow()]);
  };

  const updateRow = (id: string, field: keyof CameraRow, value: string) => {
    setManualRows((rows) =>
      rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
    );
  };

  const removeRow = (id: string) => {
    setManualRows((rows) => rows.filter((row) => row.id !== id));
  };

  const openResultDetails = (result: CameraResult) => {
    setSelectedResult(result);
    setDetailOpen(true);
  };

  const getSelectedScannedDevices = (): ScannedAxisDevice[] =>
    scanDevices.filter((device) => scanSelectedIps.includes(device.ip));

  const connectionToRequestInput = (c: CameraConnection): CameraRequestInput => ({
    ip: c.ip,
    username: c.username,
    password: c.password,
    port: c.port,
    name: c.name ?? undefined,
  });

  const refreshCameras = async (connections: CameraConnection[]) => {
    if (connections.length === 0) {
      return;
    }
    const startedAt = new Date();
    setRefreshInProgress(true);
    setRequestError(null);
    setLiveMessage(`Refreshing ${connections.length} camera(s).`);
    try {
      const cameras = connections.map(connectionToRequestInput);
      const data = await readConfigFromManual(resolvedApiBase, cameras);
      setResults((current) => {
        if (!current) {
          return data.results;
        }
        const byIp = new Map(data.results.map((r) => [r.camera_ip, r]));
        const next = current.map((r) => byIp.get(r.camera_ip) ?? r);
        return next;
      });
      const selectedIp = selectedResult?.camera_ip;
      if (selectedIp && connections.some((c) => c.ip === selectedIp)) {
        const updated = data.results.find((r) => r.camera_ip === selectedIp) ?? null;
        setSelectedResult(updated);
      }
      setLastWriteResults(null);
      setLastWriteNeedsRefresh(false);
      setLastPasswordChangeResults(null);
      setLastRunAt(formatTimestamp(startedAt));
      setLiveMessage(`Refreshed ${data.results.length} camera(s).`);
      toast.success("Refresh complete", {
        description: `${data.results.length} camera(s) re-read.`,
      });
    } catch (error) {
      handleFailure(error, "Refresh");
    } finally {
      setRefreshInProgress(false);
    }
  };

  const mergeWriteResponse = (response: WriteResponse) => {
    setResults((current) => {
      if (!current) {
        return current;
      }
      const next = current.map((result) => {
        const match = response.results.find((entry) => entry.camera_ip === result.camera_ip);
        return match?.result ?? result;
      });
      const selectedIp = selectedResult?.camera_ip;
      if (selectedIp) {
        const nextSelected = next.find((result) => result.camera_ip === selectedIp) ?? null;
        setSelectedResult(nextSelected);
      }
      return next;
    });
  };

  const getTargetConnections = (
    mode: BulkTargetMode,
    model: string | null,
  ): CameraConnection[] => {
    if (!results) {
      return [];
    }
    const filtered = results.filter((result) => {
      if (!result.connection) {
        return false;
      }
      if (mode === "selected") {
        return selectedCameraIps.includes(result.camera_ip);
      }
      return !!model && result.summary?.model === model;
    });
    return filtered
      .map((result) => result.connection)
      .filter((value): value is CameraConnection => !!value);
  };

  const toggleSelection = (cameraIp: string, checked: boolean) => {
    setSelectedCameraIps((current) =>
      checked
        ? Array.from(new Set([...current, cameraIp]))
        : current.filter((value) => value !== cameraIp),
    );
  };

  const toggleSelectAllVisible = (cameraIps: string[], checked: boolean) => {
    setSelectedCameraIps((current) => {
      if (checked) {
        return Array.from(new Set([...current, ...cameraIps]));
      }
      return current.filter((value) => !cameraIps.includes(value));
    });
  };

  const toggleScannedDevice = (ipAddress: string, checked: boolean) => {
    setScanSelectedIps((current) =>
      checked
        ? Array.from(new Set([...current, ipAddress]))
        : current.filter((value) => value !== ipAddress),
    );
  };

  const toggleAllScannedDevices = (checked: boolean) => {
    setScanSelectedIps(checked ? scanDevices.map((device) => device.ip) : []);
  };

  const submitWrite = async (
    label: string,
    request: Promise<WriteResponse>,
    options?: { targetSummary?: string; isFirmware?: boolean },
  ) => {
    const targetSummary = options?.targetSummary ?? "";
    setWriteBusy(true);
    setWriteStatus({ label, targetSummary });
    setRequestError(null);
    try {
      const data = await request;
      setLastWriteResults(data.results);
      setLastWriteNeedsRefresh(!!options?.isFirmware);
      setLastPasswordChangeResults(null);
      mergeWriteResponse(data);
      const failed = data.results.filter((item) => !item.ok);
      if (failed.length > 0) {
        throw new Error(
          failed
            .map((item) => `${item.camera_ip}: ${item.errors.join(", ") || "Unknown error"}`)
            .join(" | "),
        );
      }
      toast.success(label, {
        description: `${data.results.length} camera(s) updated.`,
      });
    } catch (error) {
      setLastWriteNeedsRefresh(false);
      handleFailure(error, label);
      throw error;
    } finally {
      setWriteBusy(false);
      setWriteStatus(null);
    }
  };

  const applyBulkSettings = async (
    mode: BulkTargetMode,
    model: string | null,
    payload: Omit<WriteConfigRequest, "cameras">,
  ) => {
    const cameras = getTargetConnections(mode, model);
    if (cameras.length === 0) {
      toast.error("No cameras targeted", {
        description: "Select cameras in the table or choose a model.",
      });
      return;
    }
    const body: WriteConfigRequest = {
      cameras,
      ...payload,
    };
    await submitWrite("Bulk settings applied", writeCameraConfig(resolvedApiBase, body), {
      targetSummary: `${cameras.length} camera${cameras.length === 1 ? "" : "s"}`,
    });
  };

  const uploadBulkFirmware = async (
    mode: BulkTargetMode,
    model: string | null,
    file: File,
  ) => {
    const cameras = getTargetConnections(mode, model);
    if (cameras.length === 0) {
      toast.error("No cameras targeted", {
        description: "Select cameras in the table or choose a model.",
      });
      return;
    }
    await submitWrite(
      "Firmware upload started",
      uploadFirmwareAndUpgrade(resolvedApiBase, { cameras }, file),
      { targetSummary: `${cameras.length} camera${cameras.length === 1 ? "" : "s"}`, isFirmware: true },
    );
  };

  const applySingleConfig = async (
    camera: CameraConnection,
    payload: Omit<WriteConfigRequest, "cameras">,
  ) => {
    await submitWrite(
      "Camera updated",
      writeCameraConfig(resolvedApiBase, {
        cameras: [camera],
        ...payload,
      }),
      { targetSummary: "1 camera" },
    );
  };

  const applyNetworkResult = (response: NetworkConfigResponse) => {
    if (!response.result) {
      return;
    }
    setResults((current) => {
      if (!current) {
        return current;
      }
      const next = current.map((result) =>
        result.camera_ip === response.previous_ip ? response.result! : result,
      );
      return next;
    });
    setSelectedResult(response.result);
    setSelectedCameraIps((current) =>
      current.map((value) =>
        value === response.previous_ip ? response.result!.camera_ip : value,
      ),
    );
    setLastWriteResults(null);
    setLastWriteNeedsRefresh(false);
    setLastPasswordChangeResults(null);
  };

  const mergePasswordChangeResponse = (response: PasswordChangeResponse) => {
    setResults((current) => {
      if (!current) {
        return current;
      }
      const verifiedByIp = new Map(
        response.results
          .filter(
            (item): item is PasswordChangeResult & { result: CameraResult } =>
              item.credential_status === "verified" && !!item.result,
          )
          .map((item) => [item.camera_ip, item.result]),
      );
      const next = current.map((result) => verifiedByIp.get(result.camera_ip) ?? result);
      const selectedIp = selectedResult?.camera_ip;
      if (selectedIp) {
        const nextSelected = next.find((result) => result.camera_ip === selectedIp) ?? null;
        setSelectedResult(nextSelected);
      }
      return next;
    });
    setLastWriteResults(null);
    setLastWriteNeedsRefresh(false);
    setLastPasswordChangeResults(response.results);
  };

  const applySingleNetworkConfig = async (
    camera: CameraConnection,
    body: Omit<NetworkConfigRequest, "camera">,
  ) => {
    setNetworkBusy(true);
    setRequestError(null);
    try {
      const response = await updateNetworkConfig(resolvedApiBase, {
        camera,
        ...body,
      });
      applyNetworkResult(response);
      return response;
    } catch (error) {
      handleFailure(error, "Network update");
      throw error;
    } finally {
      setNetworkBusy(false);
    }
  };

  const submitPasswordChange = async (
    label: string,
    request: Promise<PasswordChangeResponse>,
  ) => {
    setPasswordBusy(true);
    setWriteStatus({ label, targetSummary: "" });
    setRequestError(null);
    try {
      const data = await request;
      mergePasswordChangeResponse(data);
      const verifiedCount = data.results.filter((item) => item.credential_status === "verified").length;
      const needsReauthCount = data.results.filter((item) => item.credential_status === "needs_reauth").length;
      const failedCount = data.results.filter((item) => item.credential_status === "failed").length;
      if (failedCount > 0) {
        toast.error(label, {
          description: `${verifiedCount} verified, ${needsReauthCount} need re-authentication, ${failedCount} failed.`,
        });
      } else if (needsReauthCount > 0) {
        toast.warning(label, {
          description: `${verifiedCount} verified, ${needsReauthCount} need re-authentication.`,
        });
      } else {
        toast.success(label, {
          description: `${verifiedCount} camera${verifiedCount === 1 ? "" : "s"} verified with the new password.`,
        });
      }
      return data;
    } catch (error) {
      handleFailure(error, label);
      throw error;
    } finally {
      setPasswordBusy(false);
      setWriteStatus(null);
    }
  };

  const applyBulkPasswordChange = async (
    mode: BulkTargetMode,
    model: string | null,
    newPassword: string,
  ) => {
    const cameras = getTargetConnections(mode, model);
    if (cameras.length === 0) {
      toast.error("No cameras targeted", {
        description: "Select cameras in the table or choose a model.",
      });
      return;
    }
    await submitPasswordChange(
      "Password change sent",
      changeCameraPasswords(resolvedApiBase, {
        cameras,
        new_password: newPassword,
      }),
    );
  };

  const applySinglePasswordChange = async (
    camera: CameraConnection,
    newPassword: string,
  ) => {
    const response = await submitPasswordChange(
      "Password change sent",
      changeCameraPasswords(resolvedApiBase, {
        cameras: [camera],
        new_password: newPassword,
      }),
    );
    return response.results[0];
  };

  const applySingleStreamProfiles = async (
    camera: CameraConnection,
    body: Omit<StreamProfileApplyRequest, "cameras">,
  ) => {
    await submitWrite(
      "Stream profiles updated",
      applyStreamProfiles(resolvedApiBase, { ...body, cameras: [camera] }),
      { targetSummary: "1 camera" },
    );
  };

  const runSingleFirmwareAction = async (
    camera: CameraConnection,
    body: Omit<FirmwareActionRequest, "cameras">,
  ) => {
    await submitWrite(
      `Firmware ${body.action} sent`,
      runFirmwareAction(resolvedApiBase, { ...body, cameras: [camera] }),
      { targetSummary: "1 camera", isFirmware: true },
    );
  };

  const uploadSingleFirmware = async (camera: CameraConnection, file: File) => {
    await submitWrite(
      "Firmware upload started",
      uploadFirmwareAndUpgrade(resolvedApiBase, { cameras: [camera] }, file),
      { targetSummary: "1 camera", isFirmware: true },
    );
  };

  const handleSuccess = (nextResults: CameraResult[], startedAt: Date) => {
    const stats = getResultStats(nextResults);
    const completedAt = formatTimestamp(startedAt);

    setResults(nextResults);
    setSelectedCameraIps([]);
    setInputWorkspaceCollapsed(nextResults.length > 0);
    setRequestError(null);
    setLastWriteResults(null);
    setLastWriteNeedsRefresh(false);
    setLastPasswordChangeResults(null);
    setLastRunAt(completedAt);
    setLiveMessage(
      `Batch completed. ${stats.succeeded} succeeded and ${stats.failed} failed.`,
    );

    if (nextResults.length > 0) {
      setSelectedResult(nextResults[0]);
    }

    toast.success("Batch complete", {
      description: `${stats.succeeded} succeeded, ${stats.failed} failed.`,
    });
  };

  const handleFailure = (error: unknown, actionLabel: string) => {
    const baseMessage =
      error instanceof Error ? error.message : `${actionLabel} failed`;
    const message = baseMessage.toLowerCase().includes("fetch")
      ? `${baseMessage} ${getFetchHint(resolvedApiBase)}`
      : baseMessage;

    setRequestError(message);
    setLiveMessage(`${actionLabel} failed. ${baseMessage}`);
    toast.error(`${actionLabel} failed`, {
      description: message,
    });
  };

  const submitManual = async () => {
    const nonEmptyRows = manualRows.filter((row) => !isEmptyManualRow(row));

    if (nonEmptyRows.length === 0) {
      setLiveMessage("Add at least one camera before running a manual batch.");
      toast.error("No cameras ready", {
        description: "Add at least one camera with IP and password.",
      });
      return;
    }

    if (invalidCount > 0) {
      setLiveMessage("Manual input needs fixes before the batch can run.");
      toast.error("Fix invalid rows first", {
        description:
          "Resolve duplicate entries, invalid hosts, missing passwords, or invalid ports.",
      });
      return;
    }

    const cameras = nonEmptyRows.map((row) => ({
      ip: row.ip.trim(),
      username: row.username.trim() || "root",
      password: row.password.trim(),
      port: row.port.trim() ? Number.parseInt(row.port, 10) : undefined,
      name: row.name.trim() || undefined,
    }));

    const startedAt = new Date();
    setRunningMode("manual");
    setRequestError(null);
    setLiveMessage(`Reading ${cameras.length} cameras from manual entry.`);

    try {
      const data = await readConfigFromManual(resolvedApiBase, cameras);
      handleSuccess(data.results, startedAt);
    } catch (error) {
      handleFailure(error, "Manual batch");
    } finally {
      setRunningMode(null);
    }
  };

  const submitUpload = async () => {
    if (!uploadFile) {
      toast.error("Select a file first", {
        description: "Choose a CSV or XLSX file to upload.",
      });
      return;
    }

    if (uploadError) {
      setLiveMessage("Upload file needs attention before the batch can run.");
      toast.error("Upload blocked", {
        description: uploadError,
      });
      return;
    }

    const startedAt = new Date();
    setRunningMode("upload");
    setRequestError(null);
    setLiveMessage(`Reading cameras from uploaded file ${uploadFile.name}.`);

    try {
      const data = await readConfigFromUpload(resolvedApiBase, uploadFile);
      handleSuccess(data.results, startedAt);
    } catch (error) {
      handleFailure(error, "Upload batch");
    } finally {
      setRunningMode(null);
    }
  };

  const submitNetworkScan = async () => {
    if (!scanInterfaceName.trim()) {
      toast.error("Choose an interface first", {
        description: "Pick the local network interface that can reach the cameras.",
      });
      return;
    }
    if (!scanCidr.trim()) {
      toast.error("Enter a scan CIDR", {
        description: "Use a subnet such as 192.168.1.0/24.",
      });
      return;
    }

    setScanBusy(true);
    setScanErrors([]);
    setLiveMessage(`Scanning ${scanCidr} from ${scanInterfaceName}.`);
    try {
      const data = await runNetworkScan(resolvedApiBase, {
        interface_name: scanInterfaceName,
        cidr: scanCidr,
      } satisfies NetworkScanRequest);
      setScanResponse(data);
      setLiveMessage(`Network scan complete. ${data.devices.length} Axis device(s) found.`);
      toast.success("Network scan complete", {
        description: `${data.devices.length} device(s) found.`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Network scan failed.";
      setScanErrors([message]);
      setLiveMessage(`Network scan failed. ${message}`);
      toast.error("Network scan failed", {
        description: message,
      });
    } finally {
      setScanBusy(false);
    }
  };

  const importScannedDevices = async (readNow: boolean) => {
    const selectedDevices = getSelectedScannedDevices();
    if (selectedDevices.length === 0) {
      toast.error("No devices selected", {
        description: "Select at least one discovered camera to continue.",
      });
      return;
    }
    if (readNow && !scanDefaultPassword.trim()) {
      toast.error("Password required", {
        description: "Add the default password before using “Add selected and read now”.",
      });
      return;
    }

    setScanImportBusy(true);
    const importedRows = selectedDevices.map((device) =>
      scannedDeviceToRow(device, scanDefaultUsername, scanDefaultPassword),
    );
    const merged = mergeImportedRows(manualRows, importedRows);
    setManualRows(merged.rows);
    setActiveTab("manual");
    setInputWorkspaceCollapsed(false);

    if (!readNow) {
      setScanImportBusy(false);
      toast.success("Devices imported", {
        description:
          merged.skipped > 0
            ? `${merged.added} added, ${merged.skipped} skipped because they already exist in the manual batch.`
            : `${merged.added} device(s) added to the manual batch.`,
      });
      setLiveMessage(`Imported ${merged.added} camera(s) from network scan.`);
      return;
    }

    const startedAt = new Date();
    const cameras = selectedDevices.map((device) => ({
      ip: device.ip,
      username: scanDefaultUsername.trim() || "root",
      password: scanDefaultPassword.trim(),
      port: device.http_port ?? 80,
      name: (device.hostname || device.model || "").trim() || undefined,
    }));

    setRunningMode("manual");
    setRequestError(null);
    setLiveMessage(`Reading ${cameras.length} cameras from network scan.`);
    try {
      const data = await readConfigFromManual(resolvedApiBase, cameras);
      handleSuccess(data.results, startedAt);
      toast.success("Devices imported and read", {
        description:
          merged.skipped > 0
            ? `${data.results.length} camera(s) read. ${merged.skipped} manual row duplicates were skipped.`
            : `${data.results.length} camera(s) read successfully.`,
      });
    } catch (error) {
      handleFailure(error, "Network scan import");
    } finally {
      setRunningMode(null);
      setScanImportBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,oklch(0.985_0.008_155)_0%,oklch(0.992_0.004_155)_30%,oklch(1_0_0)_100%)]">
      <main className="mx-auto w-full max-w-[1760px] px-5 pt-8 pb-6 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">
        <p className="sr-only" aria-live="polite">
          {liveMessage}
        </p>

        <div className="space-y-8">
          <CameraPageHeader
            apiBase={apiBase}
            lastRunAt={lastRunAt}
            isLoading={isLoading}
            inputWorkspaceCollapsed={inputWorkspaceCollapsed}
            onExpandInputWorkspace={() => setInputWorkspaceCollapsed(false)}
          />

          <div
            className={
              inputWorkspaceCollapsed
                ? "min-w-0 space-y-5"
                : "grid gap-6 2xl:gap-8 xl:grid-cols-[minmax(460px,580px)_minmax(0,1fr)]"
            }
          >
            {!inputWorkspaceCollapsed && (
              <InputWorkspace
                collapsed={false}
                onCollapsedChange={setInputWorkspaceCollapsed}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                rows={manualRows}
                errorsByRow={errorsByRow}
                readyCount={readyCount}
                invalidCount={invalidCount}
                isSubmittingManual={runningMode === "manual"}
                isSubmittingUpload={runningMode === "upload"}
                isLoadingScanOptions={scanLoadingOptions}
                isScanningNetwork={scanBusy}
                isImportingScanSelection={scanImportBusy}
                uploadFile={uploadFile}
                uploadError={uploadError}
                lastResults={results}
                scanInterfaceOptions={scanInterfaceOptions}
                scanTarget={scanTarget}
                scanDevices={scanDevices}
                scanErrors={scanErrors}
                selectedScanIps={scanSelectedIps}
                scanInterfaceName={scanInterfaceName}
                scanCidr={scanCidr}
                scanDefaultUsername={scanDefaultUsername}
                scanDefaultPassword={scanDefaultPassword}
                onAddRow={addCamera}
                onUpdateRow={updateRow}
                onRemoveRow={removeRow}
                onSubmitManual={submitManual}
                onUploadFileChange={setUploadFile}
                onSubmitUpload={submitUpload}
                onScanInterfaceNameChange={(value) => {
                  setScanInterfaceName(value);
                  const match = scanInterfaceOptions.find((option) => option.name === value);
                  if (match) {
                    setScanCidr(match.suggested_cidr);
                  }
                }}
                onScanCidrChange={setScanCidr}
                onScanDefaultUsernameChange={setScanDefaultUsername}
                onScanDefaultPasswordChange={setScanDefaultPassword}
                onToggleScannedDevice={toggleScannedDevice}
                onToggleAllScannedDevices={toggleAllScannedDevices}
                onReloadScanOptions={() =>
                  loadScanOptions({
                    interface_name: scanInterfaceName || undefined,
                    cidr: scanCidr || undefined,
                  })
                }
                onSubmitNetworkScan={submitNetworkScan}
                onImportScannedDevices={() => importScannedDevices(false)}
                onImportScannedDevicesAndRead={() => importScannedDevices(true)}
              />
            )}

            <section className="min-w-0 space-y-5">
              {requestError && (
                <Alert variant="destructive">
                  <TriangleAlertIcon className="mb-2 size-4" />
                  <AlertTitle>Batch request failed</AlertTitle>
                  <AlertDescription>{requestError}</AlertDescription>
                </Alert>
              )}

              {writeStatus && (
                <Alert>
                  <LoaderCircleIcon className="mb-2 size-4 animate-spin shrink-0" />
                  <AlertTitle>{writeStatus.label}</AlertTitle>
                  <AlertDescription>
                    {writeStatus.targetSummary
                      ? `Applying to ${writeStatus.targetSummary}…`
                      : "Request in progress…"}
                  </AlertDescription>
                </Alert>
              )}

              {!writeStatus && lastWriteNeedsRefresh && lastWriteResults && lastWriteResults.length > 0 && (
                <Alert>
                  <InfoIcon className="mb-2 size-4 shrink-0" />
                  <AlertTitle>Firmware command sent</AlertTitle>
                  <AlertDescription>
                    Displayed firmware version may remain stale until the camera reboots. Use
                    &quot;Refresh this camera&quot; or &quot;Refresh batch&quot; after the device is back to see the new version.
                  </AlertDescription>
                </Alert>
              )}

              {!writeStatus && lastWriteResults && lastWriteResults.some((r) => !r.ok) && (
                <Alert variant="destructive">
                  <TriangleAlertIcon className="mb-2 size-4 shrink-0" />
                  <AlertTitle>Some cameras failed</AlertTitle>
                  <AlertDescription>
                    {lastWriteResults
                      .filter((r) => !r.ok)
                      .map((r) => `${r.camera_ip}: ${r.errors.join(", ") || "Unknown error"}`)
                      .join(" · ")}
                  </AlertDescription>
                </Alert>
              )}

              {!writeStatus && lastPasswordChangeResults && lastPasswordChangeResults.length > 0 && (
                <Alert
                  variant={
                    lastPasswordChangeResults.some((item) => item.credential_status === "failed")
                      ? "destructive"
                      : "default"
                  }
                >
                  {lastPasswordChangeResults.some((item) => item.credential_status === "failed") ? (
                    <TriangleAlertIcon className="mb-2 size-4 shrink-0" />
                  ) : (
                    <InfoIcon className="mb-2 size-4 shrink-0" />
                  )}
                  <AlertTitle>Password change results</AlertTitle>
                  <AlertDescription>
                    {(() => {
                      const verified = lastPasswordChangeResults.filter((item) => item.credential_status === "verified").length;
                      const needsReauth = lastPasswordChangeResults.filter((item) => item.credential_status === "needs_reauth").length;
                      const failed = lastPasswordChangeResults.filter((item) => item.credential_status === "failed").length;
                      return `${verified} verified, ${needsReauth} need re-authentication, ${failed} failed. Verified cameras were updated in memory only; manual rows and uploaded files still contain the old password.`;
                    })()}
                  </AlertDescription>
                </Alert>
              )}

              {isLoading && results && (
                <Alert>
                  <LoaderCircleIcon className="mb-2 size-4 animate-spin" />
                  <AlertTitle>Refreshing results</AlertTitle>
                  <AlertDescription>
                    The previous batch remains visible while the next request is
                    running.
                  </AlertDescription>
                </Alert>
              )}

              {!results && isLoading ? (
                <ResultsLoadingState />
              ) : results ? (
                <>
                  <BatchSummaryBar results={results} lastRunAt={lastRunAt} />
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        refreshCameras(
                          results
                            .filter((r): r is CameraResult & { connection: CameraConnection } => !!r.connection)
                            .map((r) => r.connection),
                        )
                      }
                      disabled={
                    refreshInProgress ||
                        writeBusy ||
                        networkBusy ||
                        passwordBusy ||
                        isLoading ||
                        results.every((r) => !r.connection)
                      }
                    >
                      <RefreshCwIcon
                        className={`size-4 ${refreshInProgress ? "animate-spin" : ""}`}
                      />
                      Refresh batch
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const conns = getTargetConnections("selected", null);
                        refreshCameras(conns);
                      }}
                      disabled={
                        refreshInProgress ||
                        writeBusy ||
                        networkBusy ||
                        passwordBusy ||
                        isLoading ||
                        selectedCameraIps.length === 0
                      }
                    >
                      <RefreshCwIcon className="size-4" />
                      Refresh selected
                    </Button>
                  </div>
                  <BulkActionBar
                    results={results}
                    selectedCameraIps={selectedCameraIps}
                    isBusy={writeBusy || networkBusy || passwordBusy || isLoading}
                    onApplySettings={applyBulkSettings}
                    onChangePassword={applyBulkPasswordChange}
                    onUploadFirmware={uploadBulkFirmware}
                  />
                  <ResultsDataTable
                    results={results}
                    lastWriteResults={lastWriteResults}
                    lastWriteNeedsRefresh={lastWriteNeedsRefresh}
                    onSelectResult={openResultDetails}
                    selectedCameraIps={selectedCameraIps}
                    onToggleSelection={toggleSelection}
                    onToggleSelectAllVisible={toggleSelectAllVisible}
                  />
                </>
              ) : (
                <div className="space-y-4">
                  <Alert>
                    <InfoIcon className="mb-2 size-4" />
                    <AlertTitle>Prepare a batch</AlertTitle>
                    <AlertDescription>
                      Start on the left with network scan, manual entry, or a
                      spreadsheet upload. Results will appear here in a
                      sortable review table.
                    </AlertDescription>
                  </Alert>
                  <ResultsEmptyState />
                </div>
              )}
            </section>
          </div>
        </div>
      </main>

      <CameraDetailSheet
        result={selectedResult}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        busy={writeBusy || networkBusy || passwordBusy}
        refreshInProgress={refreshInProgress}
        lastWriteResult={
          selectedResult && lastWriteResults
            ? lastWriteResults.find((r) => r.camera_ip === selectedResult.camera_ip) ?? null
            : null
        }
        lastWriteNeedsRefresh={lastWriteNeedsRefresh}
        onRefreshCamera={
          selectedResult?.connection
            ? () => refreshCameras([selectedResult.connection!])
            : undefined
        }
        onApplyConfig={applySingleConfig}
        onApplyNetworkConfig={applySingleNetworkConfig}
        onApplyPasswordChange={applySinglePasswordChange}
        onApplyStreamProfiles={applySingleStreamProfiles}
        onRunFirmwareAction={runSingleFirmwareAction}
        onUploadFirmware={uploadSingleFirmware}
      />
    </div>
  );
}

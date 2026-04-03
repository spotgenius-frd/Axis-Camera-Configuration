import type { CameraResult, CameraRow, ManualRowErrors } from "@/lib/camera-types";

export const INITIAL_ROW_ID = "initial";
export const MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024;

export function defaultRow(id?: string): CameraRow {
  return {
    id: id ?? crypto.randomUUID(),
    name: "",
    ip: "",
    port: "80",
    username: "root",
    password: "",
  };
}

export function getApiUrl(): string {
  if (
    typeof process.env.NEXT_PUBLIC_API_URL === "string" &&
    process.env.NEXT_PUBLIC_API_URL
  ) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return "http://localhost:8000";
}

export function getHostFromApiUrl(apiUrl: string): string {
  try {
    return new URL(apiUrl).host;
  } catch {
    return apiUrl.replace(/^https?:\/\//, "");
  }
}

export function isEmptyManualRow(row: CameraRow): boolean {
  return (
    !row.name.trim() &&
    !row.ip.trim() &&
    (!row.port.trim() || row.port.trim() === "80") &&
    (!row.username.trim() || row.username.trim() === "root") &&
    !row.password.trim()
  );
}

function isValidIpv4(value: string): boolean {
  const parts = value.split(".");
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

function isValidHostname(value: string): boolean {
  if (value.length > 253 || !/^[a-zA-Z0-9.-]+$/.test(value)) {
    return false;
  }

  const labels = value.split(".");
  return labels.every(
    (label) =>
      label.length > 0 &&
      label.length <= 63 &&
      !label.startsWith("-") &&
      !label.endsWith("-"),
  );
}

export function isValidHost(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }

  return isValidIpv4(normalized) || isValidHostname(normalized);
}

export function validateManualRows(rows: CameraRow[]): Record<string, ManualRowErrors> {
  const duplicates = new Map<string, string[]>();

  for (const row of rows) {
    if (isEmptyManualRow(row) || !row.ip.trim()) {
      continue;
    }

    const port = row.port.trim() || "80";
    const key = `${row.ip.trim().toLowerCase()}:${port}`;
    const entries = duplicates.get(key) ?? [];
    entries.push(row.id);
    duplicates.set(key, entries);
  }

  const result: Record<string, ManualRowErrors> = {};

  for (const row of rows) {
    const errors: ManualRowErrors = {};
    const hasAnyValue = !isEmptyManualRow(row);

    if (!hasAnyValue) {
      result[row.id] = errors;
      continue;
    }

    if (!row.ip.trim()) {
      errors.ip = "IP address or hostname is required.";
    } else if (!isValidHost(row.ip)) {
      errors.ip = "Enter a valid IPv4 address or hostname.";
    }

    if (row.port.trim()) {
      const port = Number(row.port);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        errors.port = "Port must be a whole number between 1 and 65535.";
      }
    }

    if (!row.password.trim()) {
      errors.password = "Password is required.";
    }

    const duplicateKey = `${row.ip.trim().toLowerCase()}:${row.port.trim() || "80"}`;
    if (row.ip.trim() && (duplicates.get(duplicateKey)?.length ?? 0) > 1) {
      errors.row = "Duplicate camera entry detected for this host and port.";
    }

    result[row.id] = errors;
  }

  return result;
}

export function getManualValidationSummary(rows: CameraRow[]) {
  const errorsByRow = validateManualRows(rows);
  let readyCount = 0;
  let invalidCount = 0;
  let filledCount = 0;

  for (const row of rows) {
    if (isEmptyManualRow(row)) {
      continue;
    }

    filledCount += 1;
    const rowErrors = errorsByRow[row.id];
    const hasErrors = !!rowErrors && Object.keys(rowErrors).length > 0;
    if (hasErrors) {
      invalidCount += 1;
    } else {
      readyCount += 1;
    }
  }

  return {
    errorsByRow,
    filledCount,
    readyCount,
    invalidCount,
  };
}

export function formatMetricLabel(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  return String(value);
}

export function getMetricRows(
  source: Record<string, unknown> | null | undefined,
  priorityKeys: string[] = [],
) {
  if (!source) {
    return [];
  }

  const orderedEntries: Array<[string, unknown]> = [];

  for (const key of priorityKeys) {
    if (key in source) {
      orderedEntries.push([key, source[key]]);
    }
  }

  for (const [key, value] of Object.entries(source)) {
    if (priorityKeys.includes(key)) {
      continue;
    }

    orderedEntries.push([key, value]);
  }

  return orderedEntries
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => ({
      key,
      label: formatMetricLabel(key),
      value: formatMetricValue(value),
    }));
}

export function getCameraDisplayName(result: CameraResult): string {
  return result.name || result.camera_ip || "Camera";
}

export function getCameraStatus(result: CameraResult): "error" | "success" {
  return result.error ? "error" : "success";
}

export function getResultStats(results: CameraResult[]) {
  const total = results.length;
  const failed = results.filter((result) => !!result.error).length;
  const succeeded = total - failed;
  const successRate = total === 0 ? 0 : Math.round((succeeded / total) * 100);

  return {
    total,
    failed,
    succeeded,
    successRate,
  };
}

export function getFetchHint(apiBase: string): string {
  return `Ensure the API is running at ${apiBase} and reachable from this browser session.`;
}

export function validateUploadFile(file: File | null): string | null {
  if (!file) {
    return "Choose a CSV or Excel file to continue.";
  }

  const name = file.name.toLowerCase();
  if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
    return "Only .csv and .xlsx files are supported.";
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return "File is too large. Keep uploads under 5 MB.";
  }

  return null;
}

import type {
  CameraPreviewRequest,
  CameraRequestInput,
  FirmwareActionRequest,
  NetworkConfigRequest,
  NetworkConfigResponse,
  NetworkScanRequest,
  NetworkScanOnboardRequest,
  NetworkScanOnboardResponse,
  NetworkScanResponse,
  PasswordChangeRequest,
  PasswordChangeResponse,
  FirmwareUpgradeRequest,
  ReadConfigResponse,
  StreamProfileApplyRequest,
  WriteConfigRequest,
  WriteResponse,
} from "@/lib/camera-types";

type ReadConfigRequest = {
  cameras: CameraRequestInput[];
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) {
        throw new Error(parsed.detail);
      }
    } catch (error) {
      if (error instanceof Error && error.message) {
        throw error;
      }
    }
    throw new Error(text || "Request failed");
  }

  return (await response.json()) as T;
}

const openApiRouteCache = new Map<string, Promise<Set<string>>>();

async function loadOpenApiRoutes(apiBase: string): Promise<Set<string>> {
  const cached = openApiRouteCache.get(apiBase);
  if (cached) {
    return cached;
  }
  const promise = fetch(`${apiBase}/openapi.json`)
    .then(async (response) => {
      if (!response.ok) {
        throw new Error("Unable to inspect the running backend API surface.");
      }
      const payload = (await response.json()) as { paths?: Record<string, unknown> };
      return new Set(Object.keys(payload.paths ?? {}));
    })
    .catch((error) => {
      openApiRouteCache.delete(apiBase);
      throw error;
    });
  openApiRouteCache.set(apiBase, promise);
  return promise;
}

export async function ensureApiRouteAvailable(apiBase: string, route: string): Promise<void> {
  const routes = await loadOpenApiRoutes(apiBase);
  if (!routes.has(route)) {
    throw new Error(
      `Setup API is not available on the running backend. Restart the backend so it matches the current code.`,
    );
  }
}

export async function readConfigFromManual(
  apiBase: string,
  cameras: CameraRequestInput[],
): Promise<ReadConfigResponse> {
  const response = await fetch(`${apiBase}/api/read-config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ cameras } satisfies ReadConfigRequest),
  });

  return parseResponse<ReadConfigResponse>(response);
}

export async function readConfigFromUpload(
  apiBase: string,
  file: File,
): Promise<ReadConfigResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${apiBase}/api/read-config/upload`, {
    method: "POST",
    body: formData,
  });

  return parseResponse<ReadConfigResponse>(response);
}

export async function writeCameraConfig(
  apiBase: string,
  body: WriteConfigRequest,
): Promise<WriteResponse> {
  const response = await fetch(`${apiBase}/api/write-config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<WriteResponse>(response);
}

export async function applyStreamProfiles(
  apiBase: string,
  body: StreamProfileApplyRequest,
): Promise<WriteResponse> {
  const response = await fetch(`${apiBase}/api/stream-profiles/apply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<WriteResponse>(response);
}

export async function runFirmwareAction(
  apiBase: string,
  body: FirmwareActionRequest,
): Promise<WriteResponse> {
  const response = await fetch(`${apiBase}/api/firmware/action`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<WriteResponse>(response);
}

export async function uploadFirmwareAndUpgrade(
  apiBase: string,
  body: FirmwareUpgradeRequest,
  file: File,
): Promise<WriteResponse> {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(body));
  formData.append("file", file);
  const response = await fetch(`${apiBase}/api/firmware/upload-upgrade`, {
    method: "POST",
    body: formData,
  });
  return parseResponse<WriteResponse>(response);
}

export async function updateNetworkConfig(
  apiBase: string,
  body: NetworkConfigRequest,
): Promise<NetworkConfigResponse> {
  const response = await fetch(`${apiBase}/api/network-config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<NetworkConfigResponse>(response);
}

export async function changeCameraPasswords(
  apiBase: string,
  body: PasswordChangeRequest,
): Promise<PasswordChangeResponse> {
  const response = await fetch(`${apiBase}/api/password-change`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<PasswordChangeResponse>(response);
}

export async function getNetworkScanOptions(
  apiBase: string,
  params?: NetworkScanRequest,
): Promise<NetworkScanResponse> {
  const url = new URL(`${apiBase}/api/network-scan/options`);
  if (params?.interface_name) {
    url.searchParams.set("interface_name", params.interface_name);
  }
  if (params?.cidr) {
    url.searchParams.set("cidr", params.cidr);
  }
  const response = await fetch(url.toString(), {
    method: "GET",
  });
  return parseResponse<NetworkScanResponse>(response);
}

export async function runNetworkScan(
  apiBase: string,
  body: NetworkScanRequest,
): Promise<NetworkScanResponse> {
  const response = await fetch(`${apiBase}/api/network-scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<NetworkScanResponse>(response);
}

export async function onboardScannedDevices(
  apiBase: string,
  body: NetworkScanOnboardRequest,
): Promise<NetworkScanOnboardResponse> {
  await ensureApiRouteAvailable(apiBase, "/api/network-scan/onboard");
  const response = await fetch(`${apiBase}/api/network-scan/onboard`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseResponse<NetworkScanOnboardResponse>(response);
}

export async function fetchCameraPreview(
  apiBase: string,
  body: CameraPreviewRequest,
): Promise<Blob> {
  const response = await fetch(`${apiBase}/api/camera-preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) {
        throw new Error(parsed.detail);
      }
    } catch (error) {
      if (error instanceof Error && error.message) {
        throw error;
      }
    }
    throw new Error(text || "Unable to fetch camera preview.");
  }
  return response.blob();
}

import type {
  CameraRequestInput,
  FirmwareActionRequest,
  NetworkConfigRequest,
  NetworkConfigResponse,
  NetworkScanRequest,
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
    const message = await response.text();
    throw new Error(message || "Request failed");
  }

  return (await response.json()) as T;
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

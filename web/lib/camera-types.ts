"use client";

export type CameraRow = {
  id: string;
  name: string;
  ip: string;
  port: string;
  username: string;
  password: string;
};

export type CameraImageSummary = {
  resolution?: string;
  fps?: number | string;
  compression?: string;
  [key: string]: string | number | undefined;
};

export type CameraStreamSummary = {
  name?: string;
  resolution?: string;
  fps?: number | string;
  videocodec?: string;
  [key: string]: string | number | undefined;
};

export type CameraOverlaySummary = {
  Enabled?: string;
  [key: string]: string | number | undefined;
};

export type CameraSummary = {
  model: string | null;
  firmware: string | null;
  image: CameraImageSummary;
  stream: CameraStreamSummary[];
  overlay: CameraOverlaySummary;
  sd_card: string | null;
};

export type CameraConnection = {
  ip: string;
  port?: number;
  username: string;
  password: string;
  name?: string | null;
};

export type CameraTimeInfo = {
  data?: {
    dateTime?: string;
    localDateTime?: string;
    timeZone?: string;
    posixTimeZone?: string;
  };
};

export type CameraTimeInfoV2 = {
  data?: {
    time?: {
      dateTime?: string;
      localDateTime?: string;
    };
    timeZone?: {
      activeTimeZone?: string;
    };
  };
};

export type LatestFirmwareInfo = {
  version?: string;
  download_url?: string;
  checksum?: string;
};

export type OptionCatalogEntry = {
  value?: string | null;
  niceName?: string;
  writable?: boolean;
  inputKind?: "select" | "range" | "text";
  options?: string[] | null;
  min?: number | null;
  max?: number | null;
  sources?: string[];
  data?: unknown;
};

export type WebSettingEntry = {
  id: string;
  label: string;
  group: string;
  value?: string | number | boolean | null;
  inputKind?: "select" | "range" | "text";
  options?: string[] | null;
  min?: number | null;
  max?: number | null;
  writable?: boolean;
  writeType?: string;
  writeKey?: string | null;
  guidance?: string | null;
};

export type StreamProfileStructured = {
  name: string;
  description: string;
  parameters: string;
  values: Record<string, string>;
};

export type CameraCapabilities = {
  legacy?: Record<string, boolean>;
  stream_profiles?: {
    supported_versions?: string[];
    has_profiles?: boolean;
    can_remove?: boolean;
  };
  dca?: {
    discovery?: boolean;
    time_v2?: boolean;
    network_settings_v2?: boolean;
    basic_device_info_v2beta?: boolean;
  };
  identity?: {
    model_firmware_source?: string;
    advisory?: string;
  };
};

export type NetworkSummary = {
  hostname?: string | null;
  static_hostname?: string | null;
  use_dhcp_hostname?: boolean | null;
};

export type CameraNetworkConfig = {
  interface_name?: string | null;
  mac_address?: string | null;
  ipv4_mode?: string | null;
  ip_address?: string | null;
  subnet_mask?: string | null;
  prefix_length?: number | null;
  gateway?: string | null;
  dns_servers?: string[];
  hostname?: string | null;
  static_hostname?: string | null;
  use_dhcp_hostname?: boolean | null;
  use_dhcp_resolver_info?: boolean | null;
  use_static_dhcp_fallback?: boolean | null;
  link_local_mode?: string | null;
  ipv4_addresses?: Array<{
    address?: string | null;
    prefix_length?: number | null;
    subnet_mask?: string | null;
    origin?: string | null;
    scope?: string | null;
    broadcast?: string | null;
    is_active?: boolean;
  }>;
  additional_ipv4_addresses?: string[];
};

export type CameraResult = {
  camera_ip: string;
  name: string | null;
  connection?: CameraConnection;
  error?: string;
  summary?: CameraSummary;
  time_info?: CameraTimeInfo;
  time_info_v2?: CameraTimeInfoV2;
  time_zone_options?: string[];
  stream_profiles_structured?: StreamProfileStructured[];
  option_catalog?: Record<string, OptionCatalogEntry>;
  web_settings_catalog?: Record<string, WebSettingEntry[]>;
  capabilities?: CameraCapabilities;
  network_summary?: NetworkSummary | null;
  network_config?: CameraNetworkConfig | null;
  latest_firmware?: LatestFirmwareInfo | null;
};

export type CameraRequestInput = {
  ip: string;
  username: string;
  password: string;
  port?: number;
  name?: string;
};

export type ReadConfigResponse = {
  results: CameraResult[];
};

export type WriteResult = {
  camera_ip: string;
  name: string | null;
  ok: boolean;
  errors: string[];
  result?: CameraResult;
};

export type WriteResponse = {
  results: WriteResult[];
};

export type WriteConfigRequest = {
  cameras: CameraConnection[];
  param_updates?: Record<string, string>;
  time_zone?: string;
  daynight_updates?: Record<string, string | number | boolean>;
  ir_cut_filter_state?: string;
  ir_cut_filter_optics_id?: string;
  light_updates?: {
    light_id?: string;
    enabled?: boolean;
    light_state?: boolean;
    manual_intensity?: number;
    synchronize_day_night_mode?: boolean;
  };
};

export type StreamProfileInput = {
  name: string;
  description?: string;
  parameters?: string;
  values?: Record<string, string>;
};

export type StreamProfileApplyRequest = {
  cameras: CameraConnection[];
  action: "create_or_update" | "remove";
  profiles?: StreamProfileInput[];
  names?: string[];
};

export type FirmwareActionRequest = {
  cameras: CameraConnection[];
  action: "commit" | "rollback" | "purge" | "reboot" | "factory_default";
  factory_default_mode?: "soft" | "hard";
};

export type FirmwareUpgradeRequest = {
  cameras: CameraConnection[];
  auto_rollback?: string | number | null;
  auto_commit?: string | null;
  factory_default_mode?: string | null;
};

export type NetworkConfigRequest = {
  camera: CameraConnection;
  ipv4_mode: "dhcp" | "static";
  ip_address?: string;
  subnet_mask?: string;
  gateway?: string;
  dns_servers?: string[];
  use_dhcp_hostname: boolean;
  hostname?: string | null;
};

export type NetworkConfigResponse = {
  ok: boolean;
  errors: string[];
  previous_ip: string;
  target_ip: string;
  reachable_ip?: string | null;
  reachable?: boolean | null;
  elapsed_seconds: number;
  poll_attempts: number;
  result?: CameraResult | null;
};

export type PasswordChangeRequest = {
  cameras: CameraConnection[];
  new_password: string;
};

export type PasswordChangeResult = {
  camera_ip: string;
  name: string | null;
  ok: boolean;
  errors: string[];
  credential_status: "verified" | "needs_reauth" | "failed";
  elapsed_seconds: number;
  result?: CameraResult | null;
};

export type PasswordChangeResponse = {
  results: PasswordChangeResult[];
};

export type BulkTargetMode = "selected" | "model";

export type ScanInterfaceOption = {
  name: string;
  display_name: string;
  ip_address: string;
  network_cidr: string;
  suggested_cidr: string;
  is_private: boolean;
  rank?: number;
};

export type ScanTarget = {
  interface_name: string;
  display_name: string;
  interface_ip: string;
  cidr: string;
};

export type ScannedAxisDevice = {
  ip: string;
  mac?: string | null;
  model?: string | null;
  serial?: string | null;
  firmware?: string | null;
  hostname?: string | null;
  http_port?: number | null;
  https_port?: number | null;
  discovery_sources: string[];
  confidence: "confirmed" | "probable";
};

export type NetworkScanRequest = {
  interface_name?: string;
  cidr?: string;
};

export type NetworkScanResponse = {
  scan_target?: ScanTarget | null;
  interface_options: ScanInterfaceOption[];
  devices: ScannedAxisDevice[];
  errors: string[];
};

export type ManualRowErrors = Partial<Record<keyof CameraRow, string>> & {
  row?: string;
};

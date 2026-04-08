"use client";

import { useState } from "react";

import {
  InfoIcon,
  LoaderCircleIcon,
  LockKeyholeIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldCheckIcon,
  TriangleAlertIcon,
  WifiIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { CameraPreviewThumbnail } from "@/components/camera/camera-preview";
import type {
  NetworkScanOnboardResult,
  ScanInterfaceOption,
  ScanTarget,
  ScannedAxisDevice,
} from "@/lib/camera-types";
import { cn } from "@/lib/utils";

type NetworkScanPanelProps = {
  apiBase: string;
  interfaceOptions: ScanInterfaceOption[];
  scanTarget: ScanTarget | null;
  devices: ScannedAxisDevice[];
  errors: string[];
  onboardingResults: NetworkScanOnboardResult[] | null;
  selectedDeviceIps: string[];
  interfaceName: string;
  cidr: string;
  loadingOptions: boolean;
  scanBusy: boolean;
  importBusy: boolean;
  onReloadOptions: () => void;
  onInterfaceNameChange: (value: string) => void;
  onCidrChange: (value: string) => void;
  onCredentialChange: (
    ipAddress: string,
    field: "username" | "password",
    value: string,
  ) => void;
  onToggleSelection: (ip: string, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onScan: () => void;
  onAddSelected: () => void;
  onStartSetup: (newRootPassword?: string) => Promise<boolean>;
};

function formatPorts(device: ScannedAxisDevice): string {
  const parts: string[] = [];
  if (device.http_port) {
    parts.push(`HTTP ${device.http_port}`);
  }
  if (device.https_port) {
    parts.push(`HTTPS ${device.https_port}`);
  }
  return parts.join(" · ") || "Not detected";
}

function getOnboardingBadgeLabel(result: NetworkScanOnboardResult): string {
  if (result.status === "ready") {
    return "Verified";
  }
  if (result.status === "verification_failed") {
    return "Verification failed";
  }
  if (result.status === "needs_credentials") {
    return "Needs credentials";
  }
  return "Setup failed";
}

function needsAutomaticSetup(device: ScannedAxisDevice): boolean {
  return (
    device.auth_status === "authenticated" &&
    (device.auth_path === "initial_admin_required" ||
      device.auth_path === "legacy_root_pass")
  );
}

function getAuthBadgeLabel(device: ScannedAxisDevice): string {
  return device.auth_status === "authenticated" ? "Authenticated" : "Unauthenticated";
}

export function NetworkScanPanel({
  apiBase,
  interfaceOptions,
  scanTarget,
  devices,
  errors,
  onboardingResults,
  selectedDeviceIps,
  interfaceName,
  cidr,
  loadingOptions,
  scanBusy,
  importBusy,
  onReloadOptions,
  onInterfaceNameChange,
  onCidrChange,
  onCredentialChange,
  onToggleSelection,
  onToggleSelectAll,
  onScan,
  onAddSelected,
  onStartSetup,
}: NetworkScanPanelProps) {
  const allSelected = devices.length > 0 && selectedDeviceIps.length === devices.length;
  const selectedCount = selectedDeviceIps.length;
  const confirmedCount = devices.filter((device) => device.confidence === "confirmed").length;
  const [setupOpen, setSetupOpen] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [setupError, setSetupError] = useState<string | null>(null);
  const needsCredentials = (onboardingResults ?? []).filter(
    (result) => result.status === "needs_credentials",
  );
  const verificationFailures = (onboardingResults ?? []).filter(
    (result) => result.status === "verification_failed",
  );
  const verifiedResults = (onboardingResults ?? []).filter(
    (result) => result.status === "ready" && result.setup_verified,
  );
  const selectedDevices = devices.filter((device) => selectedDeviceIps.includes(device.ip));
  const selectedNeedingAutoSetup = selectedDevices.filter((device) =>
    needsAutomaticSetup(device),
  );
  const selectedMissingCredentials = selectedDevices.filter(
    (device) =>
      device.auth_status === "unauthenticated" &&
      (!device.username?.trim() || !device.password?.trim()),
  );

  const submitSetup = async () => {
    if (!newPassword.trim()) {
      setSetupError("Enter the new root password that will be set on the selected camera(s).");
      return;
    }
    if (newPassword !== confirmPassword) {
      setSetupError("Password confirmation does not match.");
      return;
    }
    setSetupError(null);
    const ok = await onStartSetup(newPassword);
    if (ok) {
      setSetupOpen(false);
      setNewPassword("");
      setConfirmPassword("");
    }
  };

  const beginSetup = async () => {
    if (selectedNeedingAutoSetup.length > 0) {
      setSetupError(null);
      setSetupOpen(true);
      return;
    }
    await onStartSetup();
  };

  return (
    <>
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="space-y-1">
          <CardTitle>Scan network</CardTitle>
          <p className="text-sm text-muted-foreground">
            Discover Axis cameras on the same LAN as this backend, then add
            them to the batch and start first-time setup from this panel.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">Same LAN only</Badge>
          <Badge variant="secondary">macOS / Linux backend</Badge>
          <Badge variant="secondary">No credentials needed for discovery</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6 pb-6">
        <div className="rounded-2xl border bg-background px-4 py-4 shadow-sm">
          <div className="grid gap-4 xl:grid-cols-12">
            <div className="space-y-2 xl:col-span-5">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Interface
              </Label>
              <NativeSelect
                value={interfaceName}
                onChange={(event) => onInterfaceNameChange(event.target.value)}
                disabled={loadingOptions || scanBusy || interfaceOptions.length === 0}
              >
                {loadingOptions ? (
                  <option value="">Loading interfaces…</option>
                ) : interfaceOptions.length === 0 ? (
                  <option value="">No usable interface found</option>
                ) : (
                  interfaceOptions.map((option) => (
                    <option key={`${option.name}-${option.ip_address}`} value={option.name}>
                      {option.display_name} · {option.ip_address}
                    </option>
                  ))
                )}
              </NativeSelect>
            </div>
            <div className="space-y-2 xl:col-span-4">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                CIDR
              </Label>
              <Input
                placeholder="192.168.1.0/24"
                value={cidr}
                onChange={(event) => onCidrChange(event.target.value)}
                disabled={loadingOptions || scanBusy}
              />
            </div>
            <div className="space-y-2 xl:col-span-3">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Action
              </Label>
              <Button
                type="button"
                className="w-full"
                onClick={onScan}
                disabled={loadingOptions || scanBusy || !cidr.trim() || !interfaceName.trim()}
              >
                {scanBusy ? (
                  <LoaderCircleIcon className="size-4 animate-spin" />
                ) : (
                  <SearchIcon className="size-4" />
                )}
                {scanBusy ? "Scanning..." : "Scan network"}
              </Button>
            </div>
          </div>
        </div>

        {scanTarget ? (
          <Alert>
            <WifiIcon className="mb-2 size-4 shrink-0" />
            <AlertTitle>Current scan target</AlertTitle>
            <AlertDescription>
              {scanTarget.display_name} at {scanTarget.interface_ip} scanning {scanTarget.cidr}.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert>
            {loadingOptions ? (
              <LoaderCircleIcon className="mb-2 size-4 shrink-0 animate-spin" />
            ) : (
              <InfoIcon className="mb-2 size-4 shrink-0" />
            )}
            <AlertTitle>{loadingOptions ? "Loading scan targets" : "Choose a scan target"}</AlertTitle>
            <AlertDescription>
              {loadingOptions
                ? "The app is loading local interface information from the backend."
                : "The app will probe the selected local subnet for Axis cameras and confirm devices where anonymous Axis identity data is available."}
            </AlertDescription>
          </Alert>
        )}

        {!loadingOptions && interfaceOptions.length === 0 && (
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={onReloadOptions}>
              <RefreshCwIcon className="size-4" />
              Reload interfaces
            </Button>
          </div>
        )}

        {errors.length > 0 && (
          <Alert variant="destructive">
            <TriangleAlertIcon className="mb-2 size-4 shrink-0" />
            <AlertTitle>Scan warnings</AlertTitle>
            <AlertDescription>{errors.join(" · ")}</AlertDescription>
          </Alert>
        )}

        <div className="rounded-2xl border bg-muted/20 px-4 py-4">
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">Authentication readiness</p>
              <p className="text-xs text-muted-foreground">
                Discovery is credentialless. The app checks whether each camera
                can proceed through first-time/default Axis access or whether it
                needs existing credentials entered inline on that row.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{devices.length} discovered</Badge>
              <Badge variant="secondary">{selectedCount} selected</Badge>
              <Badge variant="secondary">{confirmedCount} confirmed</Badge>
            </div>
          </div>
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>
              The app probes for first-time Axis setup first, then the official
              legacy fallback <code>root/pass</code>. Rows marked
              <span className="font-medium text-foreground"> Unauthenticated</span>
              need the current credentials entered inline before setup can continue.
            </p>
            <p>
              If setup uses first-time or default access, the new
              <code>root</code> password is collected only when setup begins
              and will be changed on the camera itself.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border bg-card/70">
          <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">Discovered devices</p>
              <p className="text-xs text-muted-foreground">
                Confirmed devices passed Axis Basic Device Information. Probable
                devices were seen through Axis-specific mDNS only.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{devices.length} devices</Badge>
              <Badge variant="secondary">{confirmedCount} confirmed</Badge>
              {devices.length > 0 && (
                <>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onToggleSelectAll(true)}
                    disabled={allSelected}
                  >
                    Select all
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onToggleSelectAll(false)}
                    disabled={selectedCount === 0}
                  >
                    Clear
                  </Button>
                </>
              )}
            </div>
          </div>

          {devices.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 px-4 py-10 text-center">
              <div className="rounded-2xl bg-muted p-3 text-muted-foreground">
                <SearchIcon className="size-5" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">No discovered devices yet</p>
                <p className="text-sm text-muted-foreground">
                  Run a scan to populate this view with Axis devices on the local network.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3 px-4 py-4">
              {devices.map((device) => {
                const isSelected = selectedDeviceIps.includes(device.ip);
                return (
                  <div
                    key={device.ip}
                    className={cn(
                      "rounded-2xl border bg-background px-4 py-4 shadow-sm transition-colors",
                      isSelected
                        ? "border-primary/40 bg-primary/5"
                        : "border-border/70",
                    )}
                  >
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="flex min-w-0 gap-3">
                        <div className="pt-1">
                          <input
                            type="checkbox"
                            role="checkbox"
                            aria-label={`Select ${device.ip}`}
                            checked={isSelected}
                            onChange={(event) =>
                              onToggleSelection(device.ip, event.target.checked)
                            }
                          />
                        </div>
                        <CameraPreviewThumbnail
                          apiBase={apiBase}
                          scannedDevice={device}
                          placeholderText={
                            device.auth_status === "unauthenticated"
                              ? "Preview after authentication"
                              : device.auth_path === "legacy_root_pass"
                                ? "Loading preview"
                                : "Preview after initial setup"
                          }
                          className="w-32 shrink-0"
                        />
                        <div className="min-w-0 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-foreground">
                              {device.model || "Axis device"}
                            </p>
                            <Badge
                              variant={
                                device.confidence === "confirmed" ? "secondary" : "outline"
                              }
                              className="gap-1"
                            >
                              {device.confidence === "confirmed" ? (
                                <ShieldCheckIcon className="size-3.5" />
                              ) : (
                                <InfoIcon className="size-3.5" />
                              )}
                              {device.confidence === "confirmed" ? "Confirmed" : "Probable"}
                            </Badge>
                            <Badge
                              variant={
                                device.auth_status === "authenticated"
                                  ? "secondary"
                                  : "outline"
                              }
                              className="gap-1"
                            >
                              {device.auth_status === "authenticated" ? (
                                <ShieldCheckIcon className="size-3.5" />
                              ) : (
                                <LockKeyholeIcon className="size-3.5" />
                              )}
                              {getAuthBadgeLabel(device)}
                            </Badge>
                          </div>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                            <span className="font-medium text-foreground">{device.ip}</span>
                            <span className="text-muted-foreground">
                              {device.hostname || "Hostname not advertised"}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {device.auth_message ||
                              (device.auth_status === "authenticated"
                                ? "Automatic setup is available."
                                : "Existing credentials are required.")}
                          </p>
                        </div>
                      </div>
                      <div className="space-y-1 text-sm text-muted-foreground xl:text-right">
                        <p>{formatPorts(device)}</p>
                        <p>{device.discovery_sources.join(", ")}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-1 rounded-xl bg-muted/35 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          Serial
                        </p>
                        <p className="text-sm">{device.serial || "Unavailable"}</p>
                      </div>
                      <div className="space-y-1 rounded-xl bg-muted/35 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          MAC
                        </p>
                        <p className="text-sm">{device.mac || "Unavailable"}</p>
                      </div>
                      <div className="space-y-1 rounded-xl bg-muted/35 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          Firmware
                        </p>
                        <p className="text-sm">{device.firmware || "Unavailable"}</p>
                      </div>
                      <div className="space-y-1 rounded-xl bg-muted/35 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          Discovery
                        </p>
                        <p className="text-sm">{device.discovery_sources.join(", ")}</p>
                      </div>
                    </div>

                    {device.auth_status === "unauthenticated" && (
                      <div className="mt-4 rounded-xl border border-amber-300/60 bg-amber-50/60 px-3 py-3 dark:border-amber-900/60 dark:bg-amber-950/20">
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="space-y-2">
                            <Label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                              Existing username
                            </Label>
                            <Input
                              value={device.username ?? "root"}
                              onChange={(event) =>
                                onCredentialChange(device.ip, "username", event.target.value)
                              }
                              placeholder="root"
                              disabled={importBusy}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                              Existing password
                            </Label>
                            <Input
                              type="password"
                              value={device.password ?? ""}
                              onChange={(event) =>
                                onCredentialChange(device.ip, "password", event.target.value)
                              }
                              placeholder="Current camera password"
                              disabled={importBusy}
                            />
                          </div>
                        </div>
                        {isSelected && (!device.username?.trim() || !device.password?.trim()) && (
                          <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                            Enter the existing credentials before starting setup for this selected camera.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {onboardingResults && onboardingResults.length > 0 && (
          <div className="rounded-2xl border bg-card/70 px-4 py-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium">Setup results</p>
                <p className="text-xs text-muted-foreground">
                  Review which cameras were onboarded automatically and which
                  still need existing credentials.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">
                  {verifiedResults.length} verified
                </Badge>
                <Badge variant="outline">{verificationFailures.length} need attention</Badge>
                <Badge variant="outline">
                  {needsCredentials.length} need credentials
                </Badge>
                <Badge variant="destructive">
                  {onboardingResults.filter((result) => result.status === "failed").length} failed
                </Badge>
              </div>
            </div>
            <div className="space-y-3">
              {onboardingResults.map((result) => (
                <div
                  key={result.camera_ip}
                  className="rounded-xl border bg-background px-3 py-3 shadow-sm"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">{result.name || result.camera_ip}</p>
                      <p className="text-xs text-muted-foreground">{result.camera_ip}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={
                          result.status === "ready"
                            ? "secondary"
                            : result.status === "verification_failed"
                              ? "outline"
                            : result.status === "needs_credentials"
                              ? "outline"
                              : "destructive"
                        }
                      >
                        {getOnboardingBadgeLabel(result)}
                      </Badge>
                      {(result.setup_message || result.errors.length > 0) && (
                        <span className="text-xs text-muted-foreground">
                          {result.setup_message || result.errors.join(" · ")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="sticky bottom-4 z-10 rounded-2xl border bg-background/95 px-4 py-4 shadow-[0_-12px_30px_-18px_rgba(0,0,0,0.35)] backdrop-blur supports-[backdrop-filter]:bg-background/85">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {selectedCount === 0
                  ? "Select one or more devices to continue"
                  : `${selectedCount} device${selectedCount === 1 ? "" : "s"} selected`}
              </p>
              <p className="text-xs text-muted-foreground">
                Imported cameras land in the manual-entry batch. Start setup
                will use automatic Axis onboarding for authenticated rows and
                the inline credentials you entered for unauthenticated rows.
              </p>
              {selectedMissingCredentials.length > 0 && (
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  {selectedMissingCredentials.length} selected camera
                  {selectedMissingCredentials.length === 1 ? "" : "s"} still
                  need existing credentials entered before setup can continue.
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={onAddSelected}
                disabled={importBusy || selectedCount === 0}
              >
                Add selected to batch
              </Button>
              <Button
                type="button"
                onClick={beginSetup}
                disabled={importBusy || selectedCount === 0 || selectedMissingCredentials.length > 0}
              >
                {importBusy ? (
                  <LoaderCircleIcon className="size-4 animate-spin" />
                ) : (
                  <LockKeyholeIcon className="size-4" />
                )}
                Start setup for selected
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
    {setupOpen && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4">
        <div className="w-full max-w-md rounded-2xl border bg-background p-5 shadow-2xl">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold">Set a new root password</h3>
            <p className="text-sm text-muted-foreground">
              This password will be set on the selected camera device itself for
              first-time or legacy-default Axis setup. Cameras using the inline
              existing credentials will not have their passwords changed.
            </p>
          </div>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                New root password
              </Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                disabled={importBusy}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Confirm password
              </Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                disabled={importBusy}
              />
            </div>
            {setupError && (
              <p className="text-sm text-destructive">{setupError}</p>
            )}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setSetupOpen(false);
                setSetupError(null);
              }}
              disabled={importBusy}
            >
              Cancel
            </Button>
            <Button type="button" onClick={submitSetup} disabled={importBusy}>
              {importBusy ? <LoaderCircleIcon className="size-4 animate-spin" /> : <LockKeyholeIcon className="size-4" />}
              Start setup
            </Button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

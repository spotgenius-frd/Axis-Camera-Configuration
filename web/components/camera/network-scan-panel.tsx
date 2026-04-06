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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  NetworkScanOnboardResult,
  ScanInterfaceOption,
  ScanTarget,
  ScannedAxisDevice,
} from "@/lib/camera-types";

type NetworkScanPanelProps = {
  interfaceOptions: ScanInterfaceOption[];
  scanTarget: ScanTarget | null;
  devices: ScannedAxisDevice[];
  errors: string[];
  onboardingResults: NetworkScanOnboardResult[] | null;
  selectedDeviceIps: string[];
  interfaceName: string;
  cidr: string;
  followupUsername: string;
  followupPassword: string;
  loadingOptions: boolean;
  scanBusy: boolean;
  importBusy: boolean;
  onReloadOptions: () => void;
  onInterfaceNameChange: (value: string) => void;
  onCidrChange: (value: string) => void;
  onFollowupUsernameChange: (value: string) => void;
  onFollowupPasswordChange: (value: string) => void;
  onToggleSelection: (ip: string, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onScan: () => void;
  onAddSelected: () => void;
  onStartSetup: (onboardingPassword: string) => Promise<boolean>;
  onReadFlagged: (username: string, password: string) => Promise<boolean>;
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

export function NetworkScanPanel({
  interfaceOptions,
  scanTarget,
  devices,
  errors,
  onboardingResults,
  selectedDeviceIps,
  interfaceName,
  cidr,
  followupUsername,
  followupPassword,
  loadingOptions,
  scanBusy,
  importBusy,
  onReloadOptions,
  onInterfaceNameChange,
  onCidrChange,
  onFollowupUsernameChange,
  onFollowupPasswordChange,
  onToggleSelection,
  onToggleSelectAll,
  onScan,
  onAddSelected,
  onStartSetup,
  onReadFlagged,
}: NetworkScanPanelProps) {
  const allSelected = devices.length > 0 && selectedDeviceIps.length === devices.length;
  const selectedCount = selectedDeviceIps.length;
  const [setupOpen, setSetupOpen] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [setupError, setSetupError] = useState<string | null>(null);
  const needsCredentials = (onboardingResults ?? []).filter(
    (result) => result.status === "needs_credentials",
  );

  const submitSetup = async () => {
    if (!newPassword.trim()) {
      setSetupError("Enter the new root password to use for first-time onboarding.");
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
      <CardContent className="space-y-5">
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

        <div className="rounded-2xl border bg-muted/20 p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="space-y-1">
              <p className="text-sm font-medium">First-time onboarding</p>
              <p className="text-xs text-muted-foreground">
                Discovery itself does not require credentials. For first-time
                devices, the app will set a new <code>root</code> password once
                you start setup.
              </p>
            </div>
            <Badge variant="outline">{selectedCount} selected</Badge>
          </div>
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>
              The app will try modern first-time onboarding first, then the
              official legacy fallback <code>root/pass</code>. Devices that
              already have credentials will be added and flagged for manual
              credential entry.
            </p>
            <p>
              HTTPS is preferred automatically when the scan detects it.
            </p>
          </div>
        </div>

        {onboardingResults && onboardingResults.length > 0 && (
          <div className="rounded-2xl border bg-card/70 p-4">
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
                  {onboardingResults.filter((result) => result.status === "ready").length} ready
                </Badge>
                <Badge variant="outline">
                  {needsCredentials.length} need credentials
                </Badge>
                <Badge variant="destructive">
                  {onboardingResults.filter((result) => result.status === "failed").length} failed
                </Badge>
              </div>
            </div>
            <div className="space-y-2">
              {onboardingResults.map((result) => (
                <div
                  key={result.camera_ip}
                  className="flex flex-col gap-2 rounded-xl border px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{result.name || result.camera_ip}</p>
                    <p className="text-xs text-muted-foreground">{result.camera_ip}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={
                        result.status === "ready"
                          ? "secondary"
                          : result.status === "needs_credentials"
                            ? "outline"
                            : "destructive"
                      }
                    >
                      {result.status === "ready"
                        ? result.auth_path === "legacy_root_pass_updated"
                          ? "Legacy default normalized"
                          : result.auth_path === "existing_credentials_required"
                            ? "Read with existing credentials"
                            : "First-time setup complete"
                        : result.status === "needs_credentials"
                          ? "Needs existing credentials"
                          : "Setup failed"}
                    </Badge>
                    {result.errors.length > 0 && (
                      <span className="text-xs text-muted-foreground">
                        {result.errors.join(" · ")}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {needsCredentials.length > 0 && (
          <div className="rounded-2xl border bg-muted/10 p-4">
            <div className="mb-4 space-y-1">
              <p className="text-sm font-medium">Read flagged devices with credentials</p>
              <p className="text-xs text-muted-foreground">
                These cameras were discovered successfully, but they already had
                credentials set. Enter the current shared credentials to read
                them into the batch.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Username
                </Label>
                <Input
                  value={followupUsername}
                  onChange={(event) => onFollowupUsernameChange(event.target.value)}
                  placeholder="root"
                  disabled={importBusy}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Password
                </Label>
                <Input
                  type="password"
                  value={followupPassword}
                  onChange={(event) => onFollowupPasswordChange(event.target.value)}
                  placeholder="Current camera password"
                  disabled={importBusy}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button
                type="button"
                onClick={() => onReadFlagged(followupUsername, followupPassword)}
                disabled={importBusy || !followupPassword.trim()}
              >
                {importBusy ? <LoaderCircleIcon className="size-4 animate-spin" /> : <LockKeyholeIcon className="size-4" />}
                Read flagged devices
              </Button>
            </div>
          </div>
        )}

        <div className="rounded-2xl border bg-card/70">
          <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">Discovered devices</p>
              <p className="text-xs text-muted-foreground">
                Confirmed devices passed Axis Basic Device Information. Probable
                devices were seen through Axis-specific mDNS only.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{devices.length} devices</Badge>
              <Badge variant="secondary">
                {
                  devices.filter((device) => device.confidence === "confirmed")
                    .length
                }{" "}
                confirmed
              </Badge>
            </div>
          </div>

          {devices.length === 0 ? (
            <div className="p-4 text-sm text-muted-foreground">
              Run a scan to populate this table with Axis devices on the local network.
            </div>
          ) : (
            <div className="overflow-x-auto px-2 py-2">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        role="checkbox"
                        aria-label="Select all discovered devices"
                        checked={allSelected}
                        onChange={(event) => onToggleSelectAll(event.target.checked)}
                      />
                    </TableHead>
                    <TableHead className="w-36">IP</TableHead>
                    <TableHead>Device</TableHead>
                    <TableHead className="w-44">Identity</TableHead>
                    <TableHead className="w-40">Ports</TableHead>
                    <TableHead className="w-36">Confidence</TableHead>
                    <TableHead>Sources</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {devices.map((device) => (
                    <TableRow key={device.ip}>
                      <TableCell>
                        <input
                          type="checkbox"
                          role="checkbox"
                          aria-label={`Select ${device.ip}`}
                          checked={selectedDeviceIps.includes(device.ip)}
                          onChange={(event) => onToggleSelection(device.ip, event.target.checked)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{device.ip}</TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <p className="font-medium">{device.model || "Axis device"}</p>
                          <p className="text-xs text-muted-foreground">
                            {device.hostname || "Hostname not advertised"}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1 text-xs">
                          <p>Serial: {device.serial || "—"}</p>
                          <p>MAC: {device.mac || "—"}</p>
                          <p>Firmware: {device.firmware || "—"}</p>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatPorts(device)}
                      </TableCell>
                      <TableCell>
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
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {device.discovery_sources.join(", ")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            Imported cameras land in the manual-entry batch. Start setup to
            onboard first-time devices automatically, then continue with IP,
            password, and camera configuration from the main workflow.
          </p>
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
              onClick={() => {
                setSetupError(null);
                setSetupOpen(true);
              }}
              disabled={importBusy || selectedCount === 0}
            >
              {importBusy ? (
                <LoaderCircleIcon className="size-4 animate-spin" />
              ) : (
                <LockKeyholeIcon className="size-4" />
              )}
              Add selected and start setup
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
    {setupOpen && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4">
        <div className="w-full max-w-md rounded-2xl border bg-background p-5 shadow-2xl">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold">Start first-time setup</h3>
            <p className="text-sm text-muted-foreground">
              Enter the new <code>root</code> password to apply to all selected
              first-time Axis devices.
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

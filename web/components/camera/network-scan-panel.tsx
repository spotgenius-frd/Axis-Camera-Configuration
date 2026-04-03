"use client";

import {
  InfoIcon,
  LoaderCircleIcon,
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
  ScanInterfaceOption,
  ScanTarget,
  ScannedAxisDevice,
} from "@/lib/camera-types";

type NetworkScanPanelProps = {
  interfaceOptions: ScanInterfaceOption[];
  scanTarget: ScanTarget | null;
  devices: ScannedAxisDevice[];
  errors: string[];
  selectedDeviceIps: string[];
  interfaceName: string;
  cidr: string;
  defaultUsername: string;
  defaultPassword: string;
  loadingOptions: boolean;
  scanBusy: boolean;
  importBusy: boolean;
  onReloadOptions: () => void;
  onInterfaceNameChange: (value: string) => void;
  onCidrChange: (value: string) => void;
  onDefaultUsernameChange: (value: string) => void;
  onDefaultPasswordChange: (value: string) => void;
  onToggleSelection: (ip: string, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onScan: () => void;
  onAddSelected: () => void;
  onAddSelectedAndRead: () => void;
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
  selectedDeviceIps,
  interfaceName,
  cidr,
  defaultUsername,
  defaultPassword,
  loadingOptions,
  scanBusy,
  importBusy,
  onReloadOptions,
  onInterfaceNameChange,
  onCidrChange,
  onDefaultUsernameChange,
  onDefaultPasswordChange,
  onToggleSelection,
  onToggleSelectAll,
  onScan,
  onAddSelected,
  onAddSelectedAndRead,
}: NetworkScanPanelProps) {
  const allSelected = devices.length > 0 && selectedDeviceIps.length === devices.length;
  const selectedCount = selectedDeviceIps.length;

  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="space-y-1">
          <CardTitle>Scan network</CardTitle>
          <p className="text-sm text-muted-foreground">
            Discover Axis cameras on the same LAN as this backend, then add
            them directly to the existing batch workflow.
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
              <p className="text-sm font-medium">Import defaults</p>
              <p className="text-xs text-muted-foreground">
                These values are applied only when importing the selected
                cameras into the manual-entry batch.
              </p>
            </div>
            <Badge variant="outline">{selectedCount} selected</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Default username
              </Label>
              <Input
                value={defaultUsername}
                onChange={(event) => onDefaultUsernameChange(event.target.value)}
                placeholder="root"
                disabled={importBusy}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Default password
              </Label>
              <Input
                type="password"
                value={defaultPassword}
                onChange={(event) => onDefaultPasswordChange(event.target.value)}
                placeholder="Optional for import, required for read now"
                disabled={importBusy}
              />
            </div>
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
            Imported cameras land in the manual-entry batch. “Add selected and
            read now” requires a password because the existing read flow is authenticated.
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
              onClick={onAddSelectedAndRead}
              disabled={
                importBusy || selectedCount === 0 || !defaultPassword.trim()
              }
            >
              {importBusy ? (
                <LoaderCircleIcon className="size-4 animate-spin" />
              ) : (
                <SearchIcon className="size-4" />
              )}
              Add selected and read now
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

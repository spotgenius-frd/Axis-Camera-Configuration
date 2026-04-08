"use client";

import {
  CameraIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  FileSpreadsheetIcon,
  SearchIcon,
} from "lucide-react";

import { ManualCameraTable } from "@/components/camera/manual-camera-table";
import { NetworkScanPanel } from "@/components/camera/network-scan-panel";
import { UploadPanel } from "@/components/camera/upload-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  CameraResult,
  CameraRow,
  ManualRowErrors,
  NetworkScanOnboardResult,
  ScanInterfaceOption,
  ScanTarget,
  ScannedAxisDevice,
} from "@/lib/camera-types";

type InputWorkspaceProps = {
  apiBase: string;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  activeTab: "manual" | "upload" | "scan";
  onTabChange: (value: "manual" | "upload" | "scan") => void;
  rows: CameraRow[];
  errorsByRow: Record<string, ManualRowErrors>;
  readyCount: number;
  invalidCount: number;
  isSubmittingManual: boolean;
  isSubmittingUpload: boolean;
  isLoadingScanOptions: boolean;
  isScanningNetwork: boolean;
  isImportingScanSelection: boolean;
  uploadFile: File | null;
  uploadError: string | null;
  lastResults: CameraResult[] | null;
  scanInterfaceOptions: ScanInterfaceOption[];
  scanTarget: ScanTarget | null;
  scanDevices: ScannedAxisDevice[];
  scanErrors: string[];
  scanOnboardResults: NetworkScanOnboardResult[] | null;
  selectedScanIps: string[];
  scanInterfaceName: string;
  scanCidr: string;
  onAddRow: () => void;
  onUpdateRow: (id: string, field: keyof CameraRow, value: string) => void;
  onRemoveRow: (id: string) => void;
  onSubmitManual: () => void;
  onUploadFileChange: (file: File | null) => void;
  onSubmitUpload: () => void;
  onScanInterfaceNameChange: (value: string) => void;
  onScanCidrChange: (value: string) => void;
  onScanCredentialChange: (
    ipAddress: string,
    field: "username" | "password",
    value: string,
  ) => void;
  onToggleScannedDevice: (ip: string, checked: boolean) => void;
  onToggleAllScannedDevices: (checked: boolean) => void;
  onReloadScanOptions: () => void;
  onSubmitNetworkScan: () => void;
  onImportScannedDevices: () => void;
  onStartScanSetup: (newRootPassword?: string) => Promise<boolean>;
};

export function InputWorkspace({
  apiBase,
  collapsed,
  onCollapsedChange,
  activeTab,
  onTabChange,
  rows,
  errorsByRow,
  readyCount,
  invalidCount,
  isSubmittingManual,
  isSubmittingUpload,
  isLoadingScanOptions,
  isScanningNetwork,
  isImportingScanSelection,
  uploadFile,
  uploadError,
  lastResults,
  scanInterfaceOptions,
  scanTarget,
  scanDevices,
  scanErrors,
  scanOnboardResults,
  selectedScanIps,
  scanInterfaceName,
  scanCidr,
  onAddRow,
  onUpdateRow,
  onRemoveRow,
  onSubmitManual,
  onUploadFileChange,
  onSubmitUpload,
  onScanInterfaceNameChange,
  onScanCidrChange,
  onScanCredentialChange,
  onToggleScannedDevice,
  onToggleAllScannedDevices,
  onReloadScanOptions,
  onSubmitNetworkScan,
  onImportScannedDevices,
  onStartScanSetup,
}: InputWorkspaceProps) {
  const scanMode = activeTab === "scan";

  return (
    <div className={scanMode ? "space-y-4" : "space-y-4 2xl:sticky 2xl:top-6"}>
      <Card className="border-border/80 bg-card shadow-sm">
        <CardHeader className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-1">
              <CardTitle>Input workspace</CardTitle>
              <p className="text-sm leading-6 text-foreground/72">
                Prepare a batch using the method that best fits the number of
                cameras you need to audit.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{rows.length} rows</Badge>
              <button
                type="button"
                onClick={() => onCollapsedChange(!collapsed)}
                className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs text-muted-foreground hover:bg-muted"
              >
                {collapsed ? <ChevronDownIcon className="size-3.5" /> : <ChevronUpIcon className="size-3.5" />}
                {collapsed ? "Expand" : "Collapse"}
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs
            value={activeTab}
            onValueChange={(value) => onTabChange(value as "manual" | "upload" | "scan")}
            className="space-y-5"
          >
            <TabsList className="grid w-full grid-cols-3 rounded-xl bg-muted/70 p-1">
              <TabsTrigger value="manual">
                <CameraIcon className="size-4" />
                Manual
              </TabsTrigger>
              <TabsTrigger value="upload">
                <FileSpreadsheetIcon className="size-4" />
                Upload
              </TabsTrigger>
              <TabsTrigger value="scan">
                <SearchIcon className="size-4" />
                Scan
              </TabsTrigger>
            </TabsList>
            <TabsContent value="manual">
              <ManualCameraTable
                rows={rows}
                errorsByRow={errorsByRow}
                readyCount={readyCount}
                invalidCount={invalidCount}
                isSubmitting={isSubmittingManual}
                onAddRow={onAddRow}
                onUpdateRow={onUpdateRow}
                onRemoveRow={onRemoveRow}
                onSubmit={onSubmitManual}
              />
            </TabsContent>
            <TabsContent value="upload">
              <UploadPanel
                file={uploadFile}
                error={uploadError}
                isSubmitting={isSubmittingUpload}
                lastResults={lastResults}
                onFileChange={onUploadFileChange}
                onSubmit={onSubmitUpload}
              />
            </TabsContent>
            <TabsContent value="scan">
              <NetworkScanPanel
                apiBase={apiBase}
                interfaceOptions={scanInterfaceOptions}
                scanTarget={scanTarget}
                devices={scanDevices}
                errors={scanErrors}
                onboardingResults={scanOnboardResults}
                selectedDeviceIps={selectedScanIps}
                interfaceName={scanInterfaceName}
                cidr={scanCidr}
                loadingOptions={isLoadingScanOptions}
                scanBusy={isScanningNetwork}
                importBusy={isImportingScanSelection}
                onInterfaceNameChange={onScanInterfaceNameChange}
                onCidrChange={onScanCidrChange}
                onCredentialChange={onScanCredentialChange}
                onToggleSelection={onToggleScannedDevice}
                onToggleSelectAll={onToggleAllScannedDevices}
                onReloadOptions={onReloadScanOptions}
                onScan={onSubmitNetworkScan}
                onAddSelected={onImportScannedDevices}
                onStartSetup={onStartScanSetup}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

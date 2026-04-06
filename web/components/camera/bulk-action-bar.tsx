"use client";

import { useMemo, useState } from "react";

import type { BulkTargetMode, CameraResult, WebSettingEntry, WriteConfigRequest } from "@/lib/camera-types";
import { getCameraDisplayName } from "@/lib/camera-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { getSupportedUsTimeZones } from "@/lib/us-time-zones";

type BulkActionBarProps = {
  results: CameraResult[];
  selectedCameraIps: string[];
  isBusy: boolean;
  onApplySettings: (
    mode: BulkTargetMode,
    model: string | null,
    payload: Omit<WriteConfigRequest, "cameras">,
  ) => Promise<void>;
  onChangePassword: (
    mode: BulkTargetMode,
    model: string | null,
    newPassword: string,
  ) => Promise<void>;
  onUploadFirmware: (
    mode: BulkTargetMode,
    model: string | null,
    file: File,
  ) => Promise<void>;
};

export function BulkActionBar({
  results,
  selectedCameraIps,
  isBusy,
  onApplySettings,
  onChangePassword,
  onUploadFirmware,
}: BulkActionBarProps) {
  const [targetMode, setTargetMode] = useState<BulkTargetMode>("selected");
  const [model, setModel] = useState<string>("");
  const [timeZone, setTimeZone] = useState("");
  const [firmwareFile, setFirmwareFile] = useState<File | null>(null);
  const [settingValues, setSettingValues] = useState<Record<string, string>>({});
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const modelOptions = useMemo(() => {
    return Array.from(
      new Set(
        results
          .map((result) => result.summary?.model ?? "")
          .filter((value): value is string => !!value),
      ),
    ).sort();
  }, [results]);

  const selectedNames = useMemo(() => {
    return results
      .filter((result) => selectedCameraIps.includes(result.camera_ip))
      .map((result) => getCameraDisplayName(result));
  }, [results, selectedCameraIps]);

  const canSubmit =
    (targetMode === "selected" && selectedCameraIps.length > 0) ||
    (targetMode === "model" && !!model);

  const targetedResults = useMemo(() => {
    if (targetMode === "selected") {
      return results.filter((result) => selectedCameraIps.includes(result.camera_ip));
    }
    return results.filter((result) => result.summary?.model === model);
  }, [model, results, selectedCameraIps, targetMode]);

  const groupedSettings = useMemo(() => {
    if (targetedResults.length === 0) {
      return {} as Record<string, WebSettingEntry[]>;
    }
    const first = targetedResults[0].web_settings_catalog ?? {};
    const out: Record<string, WebSettingEntry[]> = {};
    for (const [groupName, entries] of Object.entries(first)) {
      const shared = entries.filter((entry) =>
        targetedResults.every((result) =>
          (result.web_settings_catalog?.[groupName] ?? []).some(
            (candidate) => candidate.id === entry.id,
          ),
        ),
      );
      if (shared.length > 0) {
        out[groupName] = shared;
      }
    }
    return out;
  }, [targetedResults]);

  const groupOrder = [
    "stream",
    "image",
    "exposure",
    "daynight",
    "light",
    "overlay",
    "storage",
    "focus_zoom",
  ];

  const orderedGroups = groupOrder.filter((groupName) => (groupedSettings[groupName] ?? []).length > 0);

  const commonTimeZones = useMemo(() => {
    if (targetedResults.length === 0) {
      return [];
    }
    const lists = targetedResults
      .map((result) => result.time_zone_options ?? [])
      .filter((values) => values.length > 0);
    if (lists.length === 0) {
      return getSupportedUsTimeZones();
    }
    const shared = lists[0].filter((value) => lists.every((list) => list.includes(value)));
    return getSupportedUsTimeZones(shared);
  }, [targetedResults]);

  const modelLatestFirmware = useMemo(() => {
    const first = targetedResults[0];
    return first?.latest_firmware?.version ?? null;
  }, [targetedResults]);

  const applySettings = async () => {
    const payload: Omit<WriteConfigRequest, "cameras"> = {
      param_updates: {},
      daynight_updates: {},
      light_updates: {},
    };
    for (const entries of Object.values(groupedSettings)) {
      for (const entry of entries) {
        const nextValue = settingValues[entry.id];
        if (nextValue === undefined || nextValue === "") {
          continue;
        }
        if (String(entry.value ?? "") === nextValue) {
          continue;
        }
        if (entry.writeType === "param" && entry.writeKey) {
          payload.param_updates![entry.writeKey] = nextValue;
        } else if (entry.writeType === "daynight" && entry.writeKey) {
          payload.daynight_updates![entry.writeKey] =
            nextValue === "true" ? true : nextValue === "false" ? false : /^\d+$/.test(nextValue) ? Number(nextValue) : nextValue;
        } else if (entry.writeType === "ir_cut_filter") {
          payload.ir_cut_filter_state = nextValue;
          payload.ir_cut_filter_optics_id = entry.writeKey ?? "0";
        } else if (entry.writeType === "light_enabled") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: entry.writeKey ?? undefined,
            enabled: nextValue === "true",
          };
        } else if (entry.writeType === "light_state") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: entry.writeKey ?? undefined,
            light_state: nextValue === "true",
          };
        } else if (entry.writeType === "light_intensity") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: entry.writeKey ?? undefined,
            manual_intensity: Number(nextValue),
          };
        } else if (entry.writeType === "light_sync") {
          payload.light_updates = {
            ...(payload.light_updates ?? {}),
            light_id: entry.writeKey ?? undefined,
            synchronize_day_night_mode: nextValue === "true",
          };
        }
      }
    }
    if (timeZone.trim()) {
      payload.time_zone = timeZone.trim();
    }
    if (
      Object.keys(payload.param_updates ?? {}).length === 0 &&
      Object.keys(payload.daynight_updates ?? {}).length === 0 &&
      !payload.ir_cut_filter_state &&
      (!payload.light_updates ||
        Object.keys(payload.light_updates).filter((key) => key !== "light_id").length === 0) &&
      !payload.time_zone
    ) {
      return;
    }
    if (
      !window.confirm(
        `Apply these settings to ${
          targetMode === "selected"
            ? `${selectedCameraIps.length} selected camera(s)`
            : `all cameras of model ${model}`
        }?`,
      )
    ) {
      return;
    }
    await onApplySettings(
      targetMode,
      model || null,
      payload,
    );
  };

  const applyFirmware = async () => {
    if (!firmwareFile) {
      return;
    }
    if (
      !window.confirm(
        `Upload firmware to ${
          targetMode === "selected"
            ? `${selectedCameraIps.length} selected camera(s)`
            : `all cameras of model ${model}`
        }?`,
      )
    ) {
      return;
    }
    await onUploadFirmware(targetMode, model || null, firmwareFile);
  };

  const applyPasswordChange = async () => {
    const trimmedPassword = newPassword.trim();
    const trimmedConfirmPassword = confirmPassword.trim();
    if (!trimmedPassword || !trimmedConfirmPassword) {
      return;
    }
    if (trimmedPassword !== trimmedConfirmPassword) {
      return;
    }
    if (
      !window.confirm(
        `Change the password for ${
          targetMode === "selected"
            ? `${selectedCameraIps.length} selected camera(s)`
            : `all cameras of model ${model}`
        }?\n\nThis updates the password for the currently configured username on each targeted camera. Cameras in this batch may use different usernames. The original manual rows and uploaded files will not be updated automatically.`,
      )
    ) {
      return;
    }
    await onChangePassword(targetMode, model || null, trimmedPassword);
    setNewPassword("");
    setConfirmPassword("");
  };

  return (
    <Card className="border-border/80 bg-card shadow-sm">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Bulk actions</CardTitle>
          <Badge variant="outline">
            {targetMode === "selected"
              ? `${selectedCameraIps.length} selected`
              : model
                ? `Model: ${model}`
                : "Choose a model"}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Apply curated settings or firmware to selected cameras or to all cameras
          of a chosen model. Controls only appear when the target cameras expose them.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Target scope</span>
            <NativeSelect
              value={targetMode}
              onChange={(event) => setTargetMode(event.target.value as BulkTargetMode)}
            >
              <option value="selected">Selected cameras</option>
              <option value="model">All cameras of a model</option>
            </NativeSelect>
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Model</span>
            <NativeSelect
              value={model}
              onChange={(event) => setModel(event.target.value)}
              disabled={targetMode !== "model"}
            >
              <option value="">Choose model</option>
              {modelOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </NativeSelect>
          </label>
          <div className="rounded-md border bg-muted/20 p-3 text-sm text-muted-foreground">
            {targetMode === "selected"
              ? selectedNames.length > 0
                ? selectedNames.slice(0, 3).join(", ") +
                  (selectedNames.length > 3 ? ` +${selectedNames.length - 3} more` : "")
                : "Select one or more cameras in the table."
              : model
                ? `Apply to all cameras in this batch that match the chosen model (${targetedResults.length} camera${targetedResults.length === 1 ? "" : "s"}).`
                : "Choose a model to target all cameras of that model in this batch."}
          </div>
        </div>

        {canSubmit && orderedGroups.map((groupName) => (
          <div key={groupName} className="space-y-3 rounded-lg border bg-muted/10 p-4">
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-medium capitalize">{groupName.replace("_", " / ")}</h4>
              <Badge variant="outline">{groupedSettings[groupName]?.length ?? 0} controls</Badge>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {(groupedSettings[groupName] ?? []).map((entry) =>
                entry.writeType === "guided" ? (
                  <div key={entry.id} className="rounded-lg border bg-background/70 p-3 text-sm text-muted-foreground">
                    <div className="font-medium text-foreground">{entry.label}</div>
                    <div className="mt-1">{entry.guidance ?? "Set from the camera UI."}</div>
                  </div>
                ) : (
                  <label key={entry.id} className="space-y-2 text-sm">
                    <span className="font-medium">{entry.label}</span>
                    {entry.inputKind === "select" && (entry.options ?? []).length > 0 ? (
                      <NativeSelect
                        value={settingValues[entry.id] ?? String(entry.value ?? "")}
                        onChange={(event) =>
                          setSettingValues((current) => ({
                            ...current,
                            [entry.id]: event.target.value,
                          }))
                        }
                      >
                        {(entry.options ?? []).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </NativeSelect>
                    ) : (
                      <Input
                        value={settingValues[entry.id] ?? String(entry.value ?? "")}
                        onChange={(event) =>
                          setSettingValues((current) => ({
                            ...current,
                            [entry.id]: event.target.value,
                          }))
                        }
                        placeholder={entry.label}
                      />
                    )}
                    {(entry.min !== null && entry.min !== undefined) ||
                    (entry.max !== null && entry.max !== undefined) ? (
                      <p className="text-xs text-muted-foreground">
                        Range: {entry.min ?? "—"} to {entry.max ?? "—"}
                      </p>
                    ) : null}
                  </label>
                ),
              )}
            </div>
          </div>
        ))}

        {canSubmit && (
          <>
            <div className="space-y-2 rounded-lg border bg-muted/10 p-4">
              <h4 className="font-medium">Time zone</h4>
              <NativeSelect
                value={timeZone}
                onChange={(event) => setTimeZone(event.target.value)}
              >
                <option value="">Keep current time zone</option>
                {commonTimeZones.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </NativeSelect>
              {commonTimeZones.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No shared U.S. time zones were reported by the targeted cameras.
                </p>
              ) : null}
            </div>

            <div className="space-y-3 rounded-lg border bg-muted/10 p-4">
              <div className="space-y-1">
                <h4 className="font-medium">Password change</h4>
                <p className="text-xs text-muted-foreground">
                  Update the password for the currently configured username on each targeted camera.
                  Targeted cameras may use different usernames in the current batch.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span className="font-medium">New password</span>
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="New camera password"
                  />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="font-medium">Confirm new password</span>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="Confirm new camera password"
                  />
                </label>
              </div>
              {newPassword && confirmPassword && newPassword !== confirmPassword ? (
                <p className="text-xs text-destructive">Passwords must match before applying the bulk change.</p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Verified cameras update in memory only. Manual rows and uploaded files keep the old password until you edit them yourself.
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={applySettings} disabled={!canSubmit || isBusy}>
                Apply bulk settings
              </Button>
              <Button
                variant="outline"
                onClick={applyPasswordChange}
                disabled={
                  !canSubmit ||
                  isBusy ||
                  !newPassword.trim() ||
                  !confirmPassword.trim() ||
                  newPassword.trim() !== confirmPassword.trim()
                }
              >
                Change passwords
              </Button>
              <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/10 px-3 py-2">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Firmware rollout</p>
                  <p className="text-xs text-muted-foreground">
                    {targetMode === "model" && model
                      ? `Apply a firmware file to all cameras of model ${model}.`
                      : `Apply a firmware file to ${selectedCameraIps.length} selected camera(s).`}
                    {modelLatestFirmware ? ` Latest official shown: ${modelLatestFirmware}.` : ""}
                  </p>
                </div>
                <input
                  type="file"
                  accept=".bin"
                  onChange={(event) => setFirmwareFile(event.target.files?.[0] ?? null)}
                  className="max-w-xs text-sm"
                />
                <Button
                  variant="outline"
                  onClick={applyFirmware}
                  disabled={!canSubmit || !firmwareFile || isBusy}
                >
                  Upload firmware
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

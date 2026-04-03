"use client";

import type { ReactNode } from "react";
import {
  AlertCircleIcon,
  GripVerticalIcon,
  PlusIcon,
  Rows4Icon,
  Trash2Icon,
  UploadCloudIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CameraRow, ManualRowErrors } from "@/lib/camera-types";

type ManualCameraTableProps = {
  rows: CameraRow[];
  errorsByRow: Record<string, ManualRowErrors>;
  readyCount: number;
  invalidCount: number;
  isSubmitting: boolean;
  onAddRow: () => void;
  onUpdateRow: (id: string, field: keyof CameraRow, value: string) => void;
  onRemoveRow: (id: string) => void;
  onSubmit: () => void;
};

export function ManualCameraTable({
  rows,
  errorsByRow,
  readyCount,
  invalidCount,
  isSubmitting,
  onAddRow,
  onUpdateRow,
  onRemoveRow,
  onSubmit,
}: ManualCameraTableProps) {
  return (
    <Card className="border-border/70 bg-card shadow-sm">
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle>Manual entry</CardTitle>
            <p className="text-sm leading-6 text-foreground/72">
              Best for smaller batches and quick spot checks. Blank rows are
              ignored; partially filled rows must be valid before you can run.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="gap-1">
              <Rows4Icon className="size-3.5" />
              {readyCount} ready
            </Badge>
            <Badge
              variant={invalidCount > 0 ? "destructive" : "secondary"}
              className="gap-1"
            >
              <AlertCircleIcon className="size-3.5" />
              {invalidCount} invalid
            </Badge>
          </div>
        </div>
        {invalidCount > 0 && (
          <Alert variant="destructive">
            <AlertTitle>Fix invalid rows before reading cameras</AlertTitle>
            <AlertDescription>
              The table currently contains {invalidCount} invalid{" "}
              {invalidCount === 1 ? "row" : "rows"}. Check highlighted cells for
              duplicate entries, host formatting, missing passwords, or port
              issues.
            </AlertDescription>
          </Alert>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {rows.map((row, index) => {
            const rowErrors = errorsByRow[row.id] ?? {};
            const hasRowError = Object.keys(rowErrors).length > 0;

            return (
              <div
                key={row.id}
                className={`rounded-2xl border p-4 shadow-sm transition-colors ${
                  hasRowError
                    ? "border-destructive/30 bg-destructive/5"
                    : "border-border/70 bg-background"
                }`}
              >
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-center gap-2">
                    <div className="rounded-lg bg-muted p-1.5 text-muted-foreground">
                      <GripVerticalIcon className="size-4" />
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-medium">Camera {index + 1}</p>
                      {rowErrors.row ? (
                        <p className="text-xs text-destructive">{rowErrors.row}</p>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          Enter host, credentials, and optional label.
                        </p>
                      )}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => onRemoveRow(row.id)}
                    disabled={rows.length <= 1}
                    aria-label={`Remove row ${index + 1}`}
                  >
                    <Trash2Icon className="size-4" />
                  </Button>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12">
                  <FieldWithError
                    label={`Name ${index + 1}`}
                    displayLabel="Name"
                    error={rowErrors.name}
                    className="xl:col-span-4"
                  >
                    <Input
                      aria-label={`Camera name for row ${index + 1}`}
                      placeholder="Optional"
                      value={row.name}
                      onChange={(event) =>
                        onUpdateRow(row.id, "name", event.target.value)
                      }
                    />
                  </FieldWithError>

                  <FieldWithError
                    label={`Camera host ${index + 1}`}
                    displayLabel="IP / Hostname"
                    error={rowErrors.ip}
                    className="xl:col-span-5"
                  >
                    <Input
                      aria-label={`Camera host for row ${index + 1}`}
                      placeholder="192.168.1.221"
                      value={row.ip}
                      onChange={(event) =>
                        onUpdateRow(row.id, "ip", event.target.value)
                      }
                    />
                  </FieldWithError>

                  <FieldWithError
                    label={`Camera port ${index + 1}`}
                    displayLabel="Port"
                    error={rowErrors.port}
                    className="xl:col-span-3"
                  >
                    <Input
                      aria-label={`Camera port for row ${index + 1}`}
                      inputMode="numeric"
                      placeholder="80"
                      value={row.port}
                      onChange={(event) =>
                        onUpdateRow(row.id, "port", event.target.value)
                      }
                    />
                  </FieldWithError>

                  <FieldWithError
                    label={`Camera username ${index + 1}`}
                    displayLabel="Username"
                    error={rowErrors.username}
                    className="xl:col-span-5"
                  >
                    <Input
                      aria-label={`Camera username for row ${index + 1}`}
                      placeholder="root"
                      value={row.username}
                      onChange={(event) =>
                        onUpdateRow(row.id, "username", event.target.value)
                      }
                    />
                  </FieldWithError>

                  <FieldWithError
                    label={`Camera password ${index + 1}`}
                    displayLabel="Password"
                    error={rowErrors.password}
                    className="xl:col-span-7"
                  >
                    <Input
                      aria-label={`Camera password for row ${index + 1}`}
                      type="password"
                      placeholder="Required"
                      value={row.password}
                      onChange={(event) =>
                        onUpdateRow(row.id, "password", event.target.value)
                      }
                    />
                  </FieldWithError>
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={onAddRow}>
              <PlusIcon className="size-4" />
              Add camera
            </Button>
            <Badge variant="secondary" className="gap-1 rounded-full px-3 py-1">
              <UploadCloudIcon className="size-3.5" />
              For larger batches, switch to CSV / Excel upload.
            </Badge>
          </div>
          <Button
            type="button"
            size="lg"
            onClick={onSubmit}
            disabled={isSubmitting || readyCount === 0 || invalidCount > 0}
          >
            {isSubmitting ? "Reading cameras..." : "Read config"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function FieldWithError({
  children,
  className,
  error,
  label,
  displayLabel,
}: {
  children: ReactNode;
  className?: string;
  error?: string;
  label: string;
  displayLabel: string;
}) {
  return (
    <div className={`space-y-2 ${className ?? ""}`}>
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {displayLabel}
      </Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive" aria-label={`${label} error`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

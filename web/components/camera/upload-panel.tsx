"use client";

import { useRef, type DragEvent } from "react";
import {
  FileSpreadsheetIcon,
  FileUpIcon,
  InfoIcon,
  UploadCloudIcon,
  XIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { CameraResult } from "@/lib/camera-types";
import { cn } from "@/lib/utils";

type UploadPanelProps = {
  file: File | null;
  error: string | null;
  isSubmitting: boolean;
  lastResults: CameraResult[] | null;
  onFileChange: (file: File | null) => void;
  onSubmit: () => void;
};

export function UploadPanel({
  file,
  error,
  isSubmitting,
  lastResults,
  onFileChange,
  onSubmit,
}: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFileSelection = (selectedFile: File | null) => {
    onFileChange(selectedFile);
  };

  const handleDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const selectedFile = event.dataTransfer.files?.[0] ?? null;
    handleFileSelection(selectedFile);
  };

  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="space-y-1">
          <CardTitle>Upload CSV / Excel</CardTitle>
          <p className="text-sm text-muted-foreground">
            Better for bulk reads. Upload a CSV or XLSX file with camera
            credentials, then run the batch in one step.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">Accepted: .csv, .xlsx</Badge>
          <Badge variant="secondary">Columns: ip, port, username, password, name</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <button
          type="button"
          className="flex w-full flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/30 px-6 py-10 text-center transition-colors hover:bg-muted/50"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <UploadCloudIcon className="size-5" />
          </div>
          <p className="text-sm font-medium">Drop a file here or click to browse</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Use a spreadsheet for faster bulk entry and fewer manual mistakes.
          </p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="sr-only"
            onChange={(event) => handleFileSelection(event.target.files?.[0] ?? null)}
          />
        </button>

        <div className="rounded-xl border bg-card/60">
          <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-muted p-2">
                <FileSpreadsheetIcon className="size-4" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {file ? file.name : "No file selected"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {file
                    ? `${Math.max(1, Math.round(file.size / 1024))} KB`
                    : "Choose a template-aligned file with one camera per row."}
                </p>
              </div>
            </div>
            {file && (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => handleFileSelection(null)}
                aria-label="Clear selected file"
              >
                <XIcon className="size-4" />
              </Button>
            )}
          </div>
          <Separator />
          <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              Download a clean sample if you need the expected column order.
            </div>
            <a
              href="/cameras_read_template.csv"
              download
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              <FileUpIcon className="size-4" />
              Download sample CSV
            </a>
          </div>
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Upload needs attention</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          <Alert>
            <InfoIcon className="mb-2 size-4" />
            <AlertTitle>Upload guidance</AlertTitle>
            <AlertDescription>
              The backend accepts rows that include at least `ip` and `password`.
              Use upload when you want to audit many devices at once without
              hand-editing table rows.
            </AlertDescription>
          </Alert>
        )}

        {lastResults && lastResults.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Previous results stay visible while new uploads are processed so you
            can keep context during repeat runs.
          </p>
        )}

        <div className="flex justify-end">
          <Button
            type="button"
            size="lg"
            onClick={onSubmit}
            disabled={isSubmitting || !file || !!error}
          >
            {isSubmitting ? "Reading cameras..." : "Run uploaded batch"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ExpandIcon,
  ImageIcon,
  LoaderCircleIcon,
  RefreshCwIcon,
  TriangleAlertIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { fetchCameraPreview } from "@/lib/api";
import type {
  CameraConnection,
  CameraPreviewRequest,
  ScannedAxisDevice,
} from "@/lib/camera-types";
import { cn } from "@/lib/utils";

type PreviewState = {
  phase: "idle" | "loading" | "ready" | "placeholder" | "error";
  objectUrl?: string | null;
  error?: string | null;
};

const THUMBNAIL_RESOLUTION = "320x180";
const DETAIL_RESOLUTION = "960x540";
const PREVIEW_CACHE_TTL_MS = 30_000;

const previewCache = new Map<string, { objectUrl: string; fetchedAt: number }>();

function buildPreviewKey(request: CameraPreviewRequest): string {
  return JSON.stringify(request);
}

function shouldUseCachedPreview(fetchedAt: number): boolean {
  return Date.now() - fetchedAt < PREVIEW_CACHE_TTL_MS;
}

function useCameraPreview(
  apiBase: string,
  request: CameraPreviewRequest | null,
  options: {
    enabled: boolean;
    refreshIntervalMs?: number;
  },
) {
  const { enabled, refreshIntervalMs = 0 } = options;
  const requestKey = useMemo(
    () => (request ? buildPreviewKey(request) : null),
    [request],
  );
  const hasRequest = Boolean(enabled && request && requestKey);
  const [reloadTick, setReloadTick] = useState(0);
  const [state, setState] = useState<
    PreviewState & { requestKey?: string | null }
  >({
    phase: enabled ? "loading" : "placeholder",
    requestKey,
  });
  const cachedPreview =
    requestKey && hasRequest
      ? previewCache.get(requestKey)
      : undefined;
  const canUseCachedPreview = Boolean(
    cachedPreview && shouldUseCachedPreview(cachedPreview.fetchedAt),
  );

  useEffect(() => {
    if (!hasRequest || !request || !requestKey) {
      return;
    }

    if (canUseCachedPreview && refreshIntervalMs <= 0 && reloadTick === 0) {
      return;
    }

    let active = true;

    void fetchCameraPreview(apiBase, request)
      .then((blob) => {
        if (!active) {
          return;
        }
        const objectUrl = URL.createObjectURL(blob);
        previewCache.set(requestKey, { objectUrl, fetchedAt: Date.now() });
        setState({ phase: "ready", objectUrl, requestKey });
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setState({
          phase: "error",
          error:
            error instanceof Error
              ? error.message
              : "Unable to load camera preview.",
          requestKey,
        });
      });

    return () => {
      active = false;
    };
  }, [
    apiBase,
    canUseCachedPreview,
    hasRequest,
    refreshIntervalMs,
    reloadTick,
    request,
    requestKey,
  ]);

  useEffect(() => {
    if (!hasRequest || refreshIntervalMs <= 0) {
      return;
    }
    const interval = window.setInterval(() => {
      setReloadTick((current) => current + 1);
    }, refreshIntervalMs);
    return () => window.clearInterval(interval);
  }, [hasRequest, refreshIntervalMs]);

  const previewState: PreviewState = !hasRequest
    ? { phase: "placeholder" }
    : state.requestKey === requestKey && state.phase === "error"
      ? { phase: "error", error: state.error }
      : canUseCachedPreview && cachedPreview
        ? { phase: "ready", objectUrl: cachedPreview.objectUrl }
        : state.requestKey === requestKey &&
            state.phase === "ready" &&
            state.objectUrl
          ? { phase: "ready", objectUrl: state.objectUrl }
          : { phase: "loading" };

  return {
    state: previewState,
    refresh: () => setReloadTick((current) => current + 1),
  };
}

type ThumbnailProps = {
  apiBase: string;
  camera?: CameraConnection | null;
  scannedDevice?: ScannedAxisDevice | null;
  placeholderText: string;
  className?: string;
};

export function CameraPreviewThumbnail({
  apiBase,
  camera,
  scannedDevice,
  placeholderText,
  className,
}: ThumbnailProps) {
  const enabled = Boolean(
    camera ||
      (scannedDevice &&
        (Boolean(scannedDevice.password?.trim()) ||
          scannedDevice.auth_path === "legacy_root_pass")),
  );
  const request = useMemo<CameraPreviewRequest | null>(() => {
    if (camera) {
      return { camera, resolution: THUMBNAIL_RESOLUTION };
    }
    if (scannedDevice && enabled) {
      return { scanned_device: scannedDevice, resolution: THUMBNAIL_RESOLUTION };
    }
    return null;
  }, [camera, enabled, scannedDevice]);
  const { state } = useCameraPreview(apiBase, request, { enabled });

  return (
    <div
      className={cn(
        "flex aspect-video w-full min-w-[112px] items-center justify-center overflow-hidden rounded-xl border bg-muted/20",
        className,
      )}
    >
      {state.phase === "ready" && state.objectUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={state.objectUrl}
          alt="Camera preview"
          className="h-full w-full object-cover"
        />
      ) : state.phase === "loading" ? (
        <div className="flex flex-col items-center gap-2 text-xs text-muted-foreground">
          <LoaderCircleIcon className="size-4 animate-spin" />
          Loading preview
        </div>
      ) : state.phase === "error" ? (
        <div className="flex flex-col items-center gap-2 px-3 text-center text-xs text-muted-foreground">
          <TriangleAlertIcon className="size-4 text-amber-600" />
          Preview unavailable
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 px-3 text-center text-xs text-muted-foreground">
          <ImageIcon className="size-4" />
          {placeholderText}
        </div>
      )}
    </div>
  );
}

type PreviewPanelProps = {
  apiBase: string;
  camera?: CameraConnection | null;
};

export function CameraPreviewPanel({ apiBase, camera }: PreviewPanelProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const request = useMemo<CameraPreviewRequest | null>(
    () => (camera ? { camera, resolution: DETAIL_RESOLUTION } : null),
    [camera],
  );
  const { state, refresh } = useCameraPreview(apiBase, request, {
    enabled: Boolean(camera),
    refreshIntervalMs: camera ? 10_000 : 0,
  });

  return (
    <>
      <section className="space-y-3 rounded-lg border bg-muted/10 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Camera preview</p>
            <p className="text-xs text-muted-foreground">
              Still-image preview from the primary live-view channel.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={!camera}>
              <RefreshCwIcon className="size-4" />
              Refresh
            </Button>
            {state.phase === "ready" && state.objectUrl ? (
              <Button type="button" variant="outline" size="sm" onClick={() => setLightboxOpen(true)}>
                <ExpandIcon className="size-4" />
                Enlarge
              </Button>
            ) : null}
          </div>
        </div>
        <div className="flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border bg-background/70">
          {state.phase === "ready" && state.objectUrl ? (
            <button
              type="button"
              className="h-full w-full"
              onClick={() => setLightboxOpen(true)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={state.objectUrl}
                alt="Camera preview"
                className="h-full w-full object-cover"
              />
            </button>
          ) : state.phase === "loading" ? (
            <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircleIcon className="size-5 animate-spin" />
              Loading preview…
            </div>
          ) : state.phase === "error" ? (
            <div className="flex max-w-md flex-col items-center gap-2 px-4 text-center text-sm text-muted-foreground">
              <TriangleAlertIcon className="size-5 text-amber-600" />
              <p className="font-medium">Preview unavailable</p>
              <p>{state.error || "Unable to fetch the current camera preview."}</p>
            </div>
          ) : (
            <div className="flex max-w-md flex-col items-center gap-2 px-4 text-center text-sm text-muted-foreground">
              <ImageIcon className="size-5" />
              <p>Preview available after the camera is authenticated.</p>
            </div>
          )}
        </div>
      </section>

      {lightboxOpen && state.phase === "ready" && state.objectUrl ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/80 px-4 py-6">
          <div className="relative flex max-h-full w-full max-w-5xl flex-col gap-3 rounded-2xl border bg-background p-4 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium">Camera preview</p>
              <Button type="button" variant="outline" onClick={() => setLightboxOpen(false)}>
                Close
              </Button>
            </div>
            <div className="overflow-hidden rounded-xl border bg-black">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={state.objectUrl}
                alt="Expanded camera preview"
                className="max-h-[78vh] w-full object-contain"
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

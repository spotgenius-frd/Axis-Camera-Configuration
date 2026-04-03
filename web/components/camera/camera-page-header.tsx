import { CameraIcon, Clock3Icon, PanelLeftOpenIcon, ShieldCheckIcon, WaypointsIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getHostFromApiUrl } from "@/lib/camera-utils";

type CameraPageHeaderProps = {
  apiBase: string | null;
  lastRunAt: string | null;
  isLoading: boolean;
  inputWorkspaceCollapsed?: boolean;
  onExpandInputWorkspace?: () => void;
};

export function CameraPageHeader({
  apiBase,
  lastRunAt,
  isLoading,
  inputWorkspaceCollapsed,
  onExpandInputWorkspace,
}: CameraPageHeaderProps) {
  const apiHost = apiBase ? getHostFromApiUrl(apiBase) : null;
  const showExpandInput = inputWorkspaceCollapsed === true && onExpandInputWorkspace;

  return (
    <div className="space-y-6">
      <div className="rounded-[28px] border border-border/80 bg-background/95 px-6 py-6 shadow-[0_16px_50px_-34px_rgba(15,23,42,0.32)] backdrop-blur sm:px-7 lg:px-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-1 border border-border/60">
              <ShieldCheckIcon className="size-3.5" />
              Read + write
            </Badge>
            {apiHost && (
              <Badge variant="outline" className="gap-1 border-border/70 bg-background">
                <WaypointsIcon className="size-3.5" />
                API target {apiHost}
              </Badge>
            )}
            {isLoading && (
              <Badge className="gap-1 shadow-sm">
                <Clock3Icon className="size-3.5" />
                Reading cameras
              </Badge>
            )}
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl 2xl:text-[2.8rem]">
              Axis Camera Config
            </h1>
            <p className="max-w-4xl text-base leading-7 text-foreground/78">
              Audit camera configuration across one or many Axis devices with a
              comparison-first interface built for operators. Discover cameras
              on the local LAN, enter them manually, or upload a spreadsheet,
              then review status, firmware, image, stream, overlay, storage,
              and timezone details in one place.
            </p>
          </div>
        </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            {showExpandInput && (
              <Button
                type="button"
                variant="outline"
                className="gap-2 border-border/70"
                onClick={onExpandInputWorkspace}
              >
                <PanelLeftOpenIcon className="size-4" />
                Add cameras
              </Button>
            )}
            <Card className="min-w-80 border-border/70 bg-card shadow-sm xl:max-w-sm">
              <CardContent className="flex items-center gap-4 p-5">
                <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                  <CameraIcon className="size-5" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-foreground">
                    Operations console
                  </p>
                  <p className="text-sm leading-6 text-foreground/72">
                    {lastRunAt
                      ? `Last successful refresh ${lastRunAt}`
                      : "No batch run yet. Start with network scan, manual entry, or a CSV/XLSX upload."}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
      <Separator />
    </div>
  );
}

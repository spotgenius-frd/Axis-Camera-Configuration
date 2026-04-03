import type { ComponentType } from "react";
import { AlertCircleIcon, CheckCircle2Icon, ListChecksIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { CameraResult } from "@/lib/camera-types";
import { getResultStats } from "@/lib/camera-utils";

type BatchSummaryBarProps = {
  results: CameraResult[];
  lastRunAt: string | null;
};

export function BatchSummaryBar({
  results,
  lastRunAt,
}: BatchSummaryBarProps) {
  const stats = getResultStats(results);

  return (
    <Card className="overflow-hidden border-border/70 shadow-sm">
      <CardContent className="space-y-5 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">Batch summary</p>
              {lastRunAt && (
                <Badge variant="outline" className="font-normal">
                  {lastRunAt}
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              Review success and failure distribution before opening individual
              camera details.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <SummaryStat
              icon={ListChecksIcon}
              label="Total"
              value={String(stats.total)}
            />
            <SummaryStat
              icon={CheckCircle2Icon}
              label="Succeeded"
              value={String(stats.succeeded)}
              tone="success"
            />
            <SummaryStat
              icon={AlertCircleIcon}
              label="Failed"
              value={String(stats.failed)}
              tone={stats.failed > 0 ? "error" : "neutral"}
            />
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-medium text-emerald-700">
            <span>Success rate</span>
            <span>{stats.successRate}%</span>
          </div>
          <Progress value={stats.successRate} variant="success" />
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryStat({
  icon: Icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "neutral" | "success" | "error";
}) {
  const iconClassName =
    tone === "success"
      ? "text-emerald-600"
      : tone === "error"
        ? "text-destructive"
        : "text-primary";

  return (
    <div className="rounded-xl border bg-muted/30 px-3 py-3">
      <div className="flex items-center gap-2">
        <Icon className={`size-4 ${iconClassName}`} />
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

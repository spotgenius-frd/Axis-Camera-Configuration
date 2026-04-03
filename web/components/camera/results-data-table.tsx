"use client";

import { useMemo, useState } from "react";
import {
  ArrowUpDownIcon,
  CircleAlertIcon,
  FilterIcon,
  SearchIcon,
} from "lucide-react";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ResultsEmptyState } from "@/components/camera/results-empty-state";
import type { CameraResult, WriteResult } from "@/lib/camera-types";
import {
  getCameraDisplayName,
  getCameraStatus,
  getResultStats,
} from "@/lib/camera-utils";

type ResultsDataTableProps = {
  results: CameraResult[];
  lastWriteResults?: WriteResult[] | null;
  lastWriteNeedsRefresh?: boolean;
  onSelectResult: (result: CameraResult) => void;
  selectedCameraIps: string[];
  onToggleSelection: (cameraIp: string, checked: boolean) => void;
  onToggleSelectAllVisible: (cameraIps: string[], checked: boolean) => void;
};

type ColumnMeta = {
  className?: string;
};

export function ResultsDataTable({
  results,
  lastWriteResults,
  lastWriteNeedsRefresh,
  onSelectResult,
  selectedCameraIps,
  onToggleSelection,
  onToggleSelectAllVisible,
}: ResultsDataTableProps) {
  const writeByIp = useMemo(() => {
    if (!lastWriteResults?.length) return new Map<string, WriteResult>();
    return new Map(lastWriteResults.map((r) => [r.camera_ip, r]));
  }, [lastWriteResults]);

  const [sorting, setSorting] = useState<SortingState>([
    { id: "status", desc: false },
    { id: "camera", desc: false },
  ]);
  const [query, setQuery] = useState("");
  const [failedOnly, setFailedOnly] = useState(false);

  const filteredResults = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return results.filter((result) => {
      if (failedOnly && !result.error) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      return [
        getCameraDisplayName(result),
        result.camera_ip,
        result.summary?.model,
        result.summary?.firmware,
        result.time_info?.data?.timeZone,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(normalizedQuery),
        );
    });
  }, [failedOnly, query, results]);
  const visibleCameraIps = filteredResults.map((result) => result.camera_ip);
  const selectedVisibleCount = visibleCameraIps.filter((ip) =>
    selectedCameraIps.includes(ip),
  ).length;
  const allVisibleSelected =
    visibleCameraIps.length > 0 && selectedVisibleCount === visibleCameraIps.length;

  const columns = useMemo<ColumnDef<CameraResult>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
        meta: {
          className: "w-[6%]",
        } satisfies ColumnMeta,
        header: () => (
          <input
            type="checkbox"
            checked={allVisibleSelected}
            onChange={(event) =>
              onToggleSelectAllVisible(visibleCameraIps, event.target.checked)
            }
            aria-label="Select visible cameras"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selectedCameraIps.includes(row.original.camera_ip)}
            onChange={(event) =>
              onToggleSelection(row.original.camera_ip, event.target.checked)
            }
            aria-label={`Select ${getCameraDisplayName(row.original)}`}
          />
        ),
      },
      {
        id: "camera",
        accessorFn: (row) => getCameraDisplayName(row),
        meta: {
          className: "w-[18%]",
        } satisfies ColumnMeta,
        header: ({ column }) => (
          <SortHeader
            label="Camera"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          />
        ),
        cell: ({ row }) => {
          const result = row.original;
          return (
            <div className="space-y-1">
              <div className="font-medium">{getCameraDisplayName(result)}</div>
              <div className="text-xs text-muted-foreground">{result.camera_ip}</div>
            </div>
          );
        },
      },
      {
        id: "status",
        accessorFn: (row) => getCameraStatus(row),
        meta: {
          className: "w-[10%]",
        } satisfies ColumnMeta,
        header: ({ column }) => (
          <SortHeader
            label="Status"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          />
        ),
        cell: ({ row }) => {
          const result = row.original;
          const write = writeByIp.get(result.camera_ip);
          return (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant={result.error ? "destructive" : "secondary"}>
                {result.error ? "Failed" : "Ready"}
              </Badge>
              {write && (
                <Badge
                  variant={write.ok ? "outline" : "destructive"}
                  className="text-xs"
                >
                  {write.ok
                    ? lastWriteNeedsRefresh
                      ? "Firmware started"
                      : "Updated"
                    : "Write failed"}
                </Badge>
              )}
            </div>
          );
        },
      },
      {
        id: "model",
        accessorFn: (row) => row.summary?.model ?? "",
        meta: {
          className: "w-[18%]",
        } satisfies ColumnMeta,
        header: ({ column }) => (
          <SortHeader
            label="Model"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          />
        ),
        cell: ({ row }) => row.original.summary?.model ?? "—",
      },
      {
        id: "firmware",
        accessorFn: (row) => row.summary?.firmware ?? "",
        meta: {
          className: "w-[12%]",
        } satisfies ColumnMeta,
        header: ({ column }) => (
          <SortHeader
            label="Firmware"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          />
        ),
        cell: ({ row }) => row.original.summary?.firmware ?? "—",
      },
      {
        id: "timezone",
        accessorFn: (row) => row.time_info?.data?.timeZone ?? "",
        meta: {
          className: "w-[14%]",
        } satisfies ColumnMeta,
        header: ({ column }) => (
          <SortHeader
            label="Time zone"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          />
        ),
        cell: ({ row }) => row.original.time_info?.data?.timeZone ?? "—",
      },
      {
        id: "overlay",
        accessorFn: (row) => row.summary?.overlay?.Enabled ?? "",
        meta: {
          className: "w-[8%]",
        } satisfies ColumnMeta,
        header: "Overlay",
        cell: ({ row }) =>
          row.original.summary?.overlay?.Enabled === "yes" ? "On" : "Off",
      },
      {
        id: "sdCard",
        accessorFn: (row) => row.summary?.sd_card ?? "",
        meta: {
          className: "w-[10%]",
        } satisfies ColumnMeta,
        header: "SD card",
        cell: ({ row }) => row.original.summary?.sd_card ?? "—",
      },
      {
        id: "action",
        enableSorting: false,
        meta: {
          className: "w-[10%]",
        } satisfies ColumnMeta,
        header: "",
        cell: ({ row }) => (
          <div className="text-right">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onSelectResult(row.original)}
            >
              View
            </Button>
          </div>
        ),
      },
    ],
    [
      allVisibleSelected,
      lastWriteNeedsRefresh,
      onSelectResult,
      onToggleSelectAllVisible,
      onToggleSelection,
      selectedCameraIps,
      visibleCameraIps,
      writeByIp,
    ],
  );

  // TanStack Table is the intended engine for a sortable shadcn review grid.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: filteredResults,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const stats = getResultStats(results);
  const hasFilters = !!query.trim() || failedOnly;

  return (
    <Card className="border-border/80 bg-card shadow-sm">
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <CardTitle>Batch review</CardTitle>
            <p className="text-sm text-muted-foreground">
              Sort and filter the latest batch, then open any camera for a
              detailed inspection panel.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{filteredResults.length} visible</Badge>
            <Badge variant="outline">{selectedCameraIps.length} selected</Badge>
            {stats.failed > 0 && (
              <Badge variant="destructive" className="gap-1">
                <CircleAlertIcon className="size-3.5" />
                {stats.failed} failed
              </Badge>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative w-full lg:max-w-sm">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by name, IP, model, firmware, timezone"
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={failedOnly ? "default" : "outline"}
              onClick={() => setFailedOnly((current) => !current)}
            >
              <FilterIcon className="size-4" />
              Failed only
            </Button>
            {hasFilters && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setQuery("");
                  setFailedOnly(false);
                }}
              >
                Reset filters
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {filteredResults.length === 0 ? (
          <ResultsEmptyState
            hasFilters={hasFilters}
            onResetFilters={() => {
              setQuery("");
              setFailedOnly(false);
            }}
          />
        ) : (
          <>
            <div className="hidden lg:block">
              <div className="overflow-hidden rounded-xl border">
                <Table className="w-full">
                  <TableHeader className="bg-muted/40">
                    {table.getHeaderGroups().map((headerGroup) => (
                      <TableRow
                        key={headerGroup.id}
                        className="hover:bg-muted/40"
                      >
                        {headerGroup.headers.map((header) => (
                          <TableHead
                            key={header.id}
                            className={
                              (
                                header.column.columnDef.meta as ColumnMeta | undefined
                              )?.className
                            }
                          >
                            {header.isPlaceholder
                              ? null
                              : flexRender(
                                  header.column.columnDef.header,
                                  header.getContext(),
                                )}
                          </TableHead>
                        ))}
                      </TableRow>
                    ))}
                  </TableHeader>
                  <TableBody>
                    {table.getRowModel().rows.map((row) => (
                      <TableRow key={row.id}>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell
                            key={cell.id}
                            className={
                              (
                                cell.column.columnDef.meta as ColumnMeta | undefined
                              )?.className
                            }
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div className="space-y-3 lg:hidden">
              <label className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={(event) =>
                    onToggleSelectAllVisible(visibleCameraIps, event.target.checked)
                  }
                  aria-label="Select all visible cameras"
                />
                <span className="font-medium">Select all visible</span>
                <span className="text-muted-foreground">
                  ({visibleCameraIps.length} camera{visibleCameraIps.length === 1 ? "" : "s"})
                </span>
              </label>
              {table.getRowModel().rows.map((row) => {
                const result = row.original;
                return (
                  <div key={row.id} className="rounded-xl border bg-background p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="font-medium">{getCameraDisplayName(result)}</p>
                        <p className="text-sm text-muted-foreground">
                          {result.camera_ip}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 justify-end">
                        <Badge
                          variant={result.error ? "destructive" : "secondary"}
                        >
                          {result.error ? "Failed" : "Ready"}
                        </Badge>
                        {writeByIp.get(result.camera_ip) && (
                          <Badge
                            variant={
                              writeByIp.get(result.camera_ip)!.ok ? "outline" : "destructive"
                            }
                            className="text-xs"
                          >
                            {writeByIp.get(result.camera_ip)!.ok
                              ? lastWriteNeedsRefresh
                                ? "Firmware started"
                                : "Updated"
                              : "Write failed"}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <label className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={selectedCameraIps.includes(result.camera_ip)}
                        onChange={(event) =>
                          onToggleSelection(result.camera_ip, event.target.checked)
                        }
                      />
                      Select for bulk actions
                    </label>
                    <dl className="mt-4 grid gap-3 text-sm">
                      <CompactRow
                        label="Model"
                        value={result.summary?.model ?? "—"}
                      />
                      <CompactRow
                        label="Firmware"
                        value={result.summary?.firmware ?? "—"}
                      />
                      <CompactRow
                        label="Time zone"
                        value={result.time_info?.data?.timeZone ?? "—"}
                      />
                    </dl>
                    <Button
                      type="button"
                      variant="outline"
                      className="mt-4 w-full"
                      onClick={() => onSelectResult(result)}
                    >
                      View details
                    </Button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SortHeader({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="-ml-2 h-auto px-2 py-1 font-medium"
      onClick={onClick}
    >
      {label}
      <ArrowUpDownIcon className="size-3.5" />
    </Button>
  );
}

function CompactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 rounded-lg border bg-muted/20 p-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd>{value}</dd>
    </div>
  );
}

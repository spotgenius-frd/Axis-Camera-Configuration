import { FileSearchIcon, UploadIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type ResultsEmptyStateProps = {
  hasFilters?: boolean;
  onResetFilters?: () => void;
};

export function ResultsEmptyState({
  hasFilters = false,
  onResetFilters,
}: ResultsEmptyStateProps) {
  return (
    <Card className="border-dashed bg-card/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          {hasFilters ? (
            <FileSearchIcon className="size-5" />
          ) : (
            <UploadIcon className="size-5" />
          )}
        </div>
        <div className="space-y-1">
          <CardTitle>
            {hasFilters ? "No cameras match the current filters" : "No results yet"}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {hasFilters
              ? "Try clearing the search or failed-only filter to see the full batch again."
              : "Run a network scan, manual batch, or file upload to populate a review table with sortable camera results."}
          </p>
        </div>
      </CardHeader>
      {hasFilters && onResetFilters && (
        <CardContent>
          <Button variant="outline" onClick={onResetFilters}>
            Clear filters
          </Button>
        </CardContent>
      )}
    </Card>
  );
}

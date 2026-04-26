import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { getHealth } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

export function AppHeader() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  return (
    <header className="border-b border-border bg-background/80 backdrop-blur sticky top-0 z-40">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-9 w-9 shrink-0 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="font-bold text-lg sm:text-xl leading-none tracking-tight">
              CareGrid AI
            </h1>
            <p className="text-xs text-muted-foreground mt-1 truncate">
              Agentic Healthcare Intelligence for India
            </p>
          </div>
        </div>
        <div className="shrink-0">
          {isLoading ? (
            <Skeleton className="h-7 w-44" />
          ) : isError || !data ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground rounded-full border border-border px-3 py-1.5">
              <span className="h-2 w-2 rounded-full bg-trust-low" />
              backend offline
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs rounded-full border border-border bg-surface px-3 py-1.5">
              <span className="h-2 w-2 rounded-full bg-trust-high animate-pulse" />
              <span className="font-semibold tabular-nums">
                {data.dataset_rows.toLocaleString()}
              </span>
              <span className="text-muted-foreground">records</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground font-mono truncate max-w-[12rem]">
                {data.embedding_model}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default AppHeader;

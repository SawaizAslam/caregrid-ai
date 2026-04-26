import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, MapPinned, Search, Sparkles, Zap } from "lucide-react";
import { toast } from "sonner";

import { search as apiSearch } from "@/lib/api";
import type { HospitalResult, SearchResponse } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { TrustBadge } from "@/components/TrustBadge";
import { TrustBreakdown } from "@/components/TrustBreakdown";
import { ScoreComponents } from "@/components/ScoreComponents";
import { ChainOfThought } from "@/components/ChainOfThought";
import { cn } from "@/lib/utils";

const PLACEHOLDERS = [
  "nearest ICU hospital in Bihar with oxygen",
  "dialysis center within 30 km of 800001",
  "trauma centre in Maharashtra open 24/7",
  "rural clinic in Odisha with maternity ward",
];

const EXAMPLE_PILLS = PLACEHOLDERS;

function ResultCard({ r }: { r: HospitalResult }) {
  const [open, setOpen] = useState(false);
  const locationLine =
    [r.district, r.state].filter(Boolean).join(", ") || r.location || r.state || "";

  return (
    <Card className="bg-surface border-border overflow-hidden">
      <CardContent className="p-4 sm:p-5">
        <div className="grid gap-4 md:grid-cols-[1fr_180px]">
          <div className="min-w-0 space-y-2">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-lg sm:text-xl font-bold leading-tight text-foreground">
                {r.hospital_name}
              </h3>
              <div className="md:hidden">
                <TrustBadge score={r.trust_score} size="sm" />
              </div>
            </div>

            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <MapPinned className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{locationLine || "Location unknown"}</span>
              {r.distance_km != null && (
                <span className="ml-1 text-foreground font-medium tabular-nums">
                  · {r.distance_km.toFixed(1)} km away
                </span>
              )}
            </div>

            {r.matched_features?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {r.matched_features.map((f) => (
                  <Badge
                    key={f}
                    variant="outline"
                    className="bg-accent text-accent-foreground border-primary/20 text-[10px] uppercase tracking-wide"
                  >
                    {f}
                  </Badge>
                ))}
              </div>
            )}

            {r.explanation && (
              <p className="text-sm text-muted-foreground leading-relaxed">
                {r.explanation}
              </p>
            )}

            <Collapsible open={open} onOpenChange={setOpen} className="pt-1">
              <CollapsibleTrigger className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">
                <ChevronDown
                  className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
                />
                Why this trust score?
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-3">
                <TrustBreakdown items={r.trust_breakdown} />
              </CollapsibleContent>
            </Collapsible>
          </div>

          <div className="hidden md:flex flex-col items-end gap-3">
            <TrustBadge score={r.trust_score} size="md" />
            <ScoreComponents components={r.score_components} className="w-full" />
          </div>

          <div className="md:hidden">
            <ScoreComponents components={r.score_components} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SearchPage() {
  const [text, setText] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [phIdx, setPhIdx] = useState(0);
  const [data, setData] = useState<SearchResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 3000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const mutation = useMutation({
    mutationFn: (q: string) => apiSearch(q, 10),
    onSuccess: (res) => setData(res),
    onError: (err: Error) => {
      toast.error("Search failed", { description: err.message });
    },
  });

  function submit(raw: string) {
    const q = raw.trim();
    if (!q) return;
    const finalQ = urgent && !/^nearest\b/i.test(q) ? `nearest ${q}` : q;
    mutation.mutate(finalQ);
  }

  function handlePill(p: string) {
    setText(p);
    submit(p);
  }

  const showLoading = mutation.isPending;
  const results = data?.results ?? [];

  const placeholder = useMemo(() => PLACEHOLDERS[phIdx], [phIdx]);

  return (
    <div className="space-y-6">
      {/* Search hero */}
      <Card className="bg-surface border-border">
        <CardContent className="p-5 sm:p-6 space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit(text);
            }}
            className="flex flex-col sm:flex-row gap-2"
          >
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={placeholder}
                className="h-12 pl-10 text-base bg-background"
                aria-label="Search hospitals, clinics and pharmacies"
              />
            </div>
            <Button
              type="submit"
              size="lg"
              className="h-12 px-6"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Searching…" : "Search"}
            </Button>
          </form>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground mr-1">Try:</span>
            {EXAMPLE_PILLS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => handlePill(p)}
                className="text-xs rounded-full border border-border bg-background px-3 py-1.5 hover:border-primary hover:text-primary transition-colors"
              >
                {p}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between gap-4 pt-1 border-t border-border">
            <label
              htmlFor="urgent"
              className="flex items-center gap-2.5 cursor-pointer select-none"
            >
              <Switch id="urgent" checked={urgent} onCheckedChange={setUrgent} />
              <Zap
                className={cn(
                  "h-4 w-4 transition-colors",
                  urgent ? "text-primary" : "text-muted-foreground",
                )}
              />
              <span className="text-sm font-medium">Try urgent mode</span>
              <span className="text-xs text-muted-foreground hidden sm:inline">
                — reweights for proximity
              </span>
            </label>
            {data && (
              <span className="text-xs text-muted-foreground">
                {data.total_candidates.toLocaleString()} candidates · top{" "}
                {results.length}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Chain of thought */}
      {data && <ChainOfThought query={data.query_understood} />}

      {/* Results */}
      {showLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="bg-surface border-border">
              <CardContent className="p-5 space-y-3">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!showLoading && data && results.length === 0 && (
        <Card className="bg-surface border-border">
          <CardContent className="p-10 text-center space-y-2">
            <AlertTriangle className="h-6 w-6 mx-auto text-muted-foreground" />
            <p className="font-semibold">No facilities matched</p>
            <p className="text-sm text-muted-foreground">
              Try one of the example queries above or broaden your search.
            </p>
          </CardContent>
        </Card>
      )}

      {!showLoading && !data && (
        <Card className="bg-surface border-border border-dashed">
          <CardContent className="p-10 text-center space-y-2">
            <Sparkles className="h-6 w-6 mx-auto text-primary" />
            <p className="font-semibold">Ask anything about Indian healthcare</p>
            <p className="text-sm text-muted-foreground">
              The agent parses your query, ranks ~10,000 facilities, and explains
              every trust signal it found.
            </p>
          </CardContent>
        </Card>
      )}

      {!showLoading && results.length > 0 && (
        <div className="space-y-3">
          {results.map((r) => (
            <ResultCard key={r.hospital_id} r={r} />
          ))}
        </div>
      )}
    </div>
  );
}

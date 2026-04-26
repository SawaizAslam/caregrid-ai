import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Search } from "lucide-react";

import { getContradictions, getHospital } from "@/lib/api";
import type { Contradiction, HospitalDetail } from "@/lib/types";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { TrustBadge } from "@/components/TrustBadge";
import { TrustBreakdown } from "@/components/TrustBreakdown";

function HospitalSheetBody({ id }: { id: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["hospital", id],
    queryFn: () => getHospital(id),
  });

  if (isLoading) {
    return (
      <div className="space-y-4 mt-6">
        <Skeleton className="h-12 w-32" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="mt-6 text-sm text-muted-foreground">
        Could not load hospital details.
      </div>
    );
  }

  const h: HospitalDetail = data;
  const locationLine = [h.district, h.state].filter(Boolean).join(", ");

  return (
    <div className="space-y-6 mt-4 pb-6">
      <div className="flex items-center gap-4">
        <TrustBadge score={h.trust_score} size="lg" />
        <div className="text-sm text-muted-foreground">
          {locationLine}
          {h.pin_code && <span className="ml-1">· {h.pin_code}</span>}
        </div>
      </div>

      <section>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Trust breakdown
        </h3>
        <TrustBreakdown items={h.trust_breakdown} />
      </section>

      {(h.specialty_tags?.length || h.equipment_tags?.length) ? (
        <section>
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Specialties &amp; equipment
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {h.specialty_tags?.map((s) => (
              <Badge key={`s-${s}`} variant="outline" className="bg-accent text-accent-foreground border-primary/20">
                {s}
              </Badge>
            ))}
            {h.equipment_tags?.map((e) => (
              <Badge key={`e-${e}`} variant="secondary" className="text-[11px]">
                {e}
              </Badge>
            ))}
          </div>
        </section>
      ) : null}

      {h.notes && (
        <section>
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Raw notes
          </h3>
          <pre className="text-xs leading-relaxed bg-muted rounded-md p-3 whitespace-pre-wrap break-words max-h-72 overflow-auto font-mono">
            {h.notes}
          </pre>
        </section>
      )}
    </div>
  );
}

export default function AuditPage() {
  const [filter, setFilter] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["contradictions", 50],
    queryFn: () => getContradictions(50),
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return data;
    return data.filter(
      (c) =>
        c.hospital_name?.toLowerCase().includes(q) ||
        (c.state || "").toLowerCase().includes(q),
    );
  }, [data, filter]);

  return (
    <div className="space-y-4">
      <Card className="bg-surface border-border">
        <CardContent className="p-4 sm:p-5 space-y-4">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 shrink-0 rounded-lg bg-trust-low/10 text-trust-low flex items-center justify-center">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="font-bold text-lg">Contradictions found by the trust scorer</h2>
              <p className="text-sm text-muted-foreground">
                Hospitals where evidence in the source text contradicts a stated
                claim. Click a row for the full record.
              </p>
            </div>
          </div>

          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by hospital or state…"
              className="pl-9 bg-background"
            />
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="text-sm text-muted-foreground">
              Could not load contradictions.
            </p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              No contradictions match the filter.
            </p>
          ) : (
            <div className="rounded-md border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead>Hospital</TableHead>
                    <TableHead className="hidden sm:table-cell">State</TableHead>
                    <TableHead>Trust</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead className="hidden md:table-cell">Evidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((c: Contradiction) => (
                    <TableRow
                      key={`${c.hospital_id}-${c.rule}`}
                      className="cursor-pointer"
                      onClick={() => setOpenId(c.hospital_id)}
                    >
                      <TableCell className="font-medium align-top">
                        <div className="line-clamp-2">{c.hospital_name}</div>
                        <div className="text-xs text-muted-foreground sm:hidden mt-1">
                          {c.state || "—"}
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm text-muted-foreground align-top">
                        {c.state || "—"}
                      </TableCell>
                      <TableCell className="align-top">
                        <TrustBadge score={c.trust_score} size="sm" />
                      </TableCell>
                      <TableCell className="font-semibold text-sm align-top max-w-[14rem]">
                        <div className="line-clamp-2">{c.rule}</div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell align-top max-w-md">
                        <blockquote className="border-l-2 border-border pl-3 text-xs italic text-muted-foreground line-clamp-3">
                          &ldquo;{c.evidence}&rdquo;
                        </blockquote>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={openId !== null} onOpenChange={(o) => !o && setOpenId(null)}>
        <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Hospital detail</SheetTitle>
            <SheetDescription>
              Full record with trust breakdown and source evidence.
            </SheetDescription>
          </SheetHeader>
          {openId !== null && <HospitalSheetBody id={openId} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { scaleLinear } from "d3-scale";
import { AlertTriangle, MapPinned } from "lucide-react";

import { getDeserts, getSpecialtyGaps } from "@/lib/api";
import type { StateDesert } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const TOPO_URL =
  "https://cdn.jsdelivr.net/gh/datameet/maps/States/Admin2.geojson";

function normState(s: string | null | undefined) {
  return (s || "").trim().toLowerCase().replace(/\s+/g, " ");
}

// Red (worst desert) → amber → green (well served)
const colorScale = scaleLinear<string>()
  .domain([0, 0.5, 1])
  .range(["hsl(152 76% 40%)", "hsl(38 92% 55%)", "hsl(350 89% 60%)"])
  .clamp(true);

function DesertLegend() {
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span>Well-served</span>
      <div
        className="h-2 w-32 rounded-full"
        style={{
          background:
            "linear-gradient(to right, hsl(152 76% 40%), hsl(38 92% 55%), hsl(350 89% 60%))",
        }}
      />
      <span>Worst desert</span>
    </div>
  );
}

function ChoroplethMap({ data }: { data: StateDesert[] }) {
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    state: StateDesert;
  } | null>(null);
  const [topoFailed, setTopoFailed] = useState(false);

  const byState = useMemo(() => {
    const m = new Map<string, StateDesert>();
    data.forEach((d) => m.set(normState(d.state), d));
    return m;
  }, [data]);

  if (topoFailed) {
    return <RankedFallback data={data} />;
  }

  return (
    <div className="relative">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ scale: 900, center: [82, 23] }}
        width={800}
        height={520}
        style={{ width: "100%", height: "auto" }}
      >
        <Geographies geography={TOPO_URL} parseGeographies={(geos) => geos}>
          {({ geographies }: { geographies: any[] }) => {
            if (!geographies?.length) {
              // fall back if topojson failed silently
              setTimeout(() => setTopoFailed(true), 0);
              return null;
            }
            return geographies.map((geo) => {
              const name =
                geo.properties?.NAME_1 ||
                geo.properties?.st_nm ||
                geo.properties?.STATE ||
                geo.properties?.name ||
                "";
              const match = byState.get(normState(name));
              const fill = match
                ? colorScale(match.desert_score)
                : "hsl(214 32% 91%)";
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={fill}
                  stroke="hsl(0 0% 100%)"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: "none" },
                    hover: { outline: "none", opacity: 0.85, cursor: "pointer" },
                    pressed: { outline: "none" },
                  }}
                  onMouseMove={(e) => {
                    if (!match) return;
                    setTooltip({
                      x: e.clientX,
                      y: e.clientY,
                      state: match,
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            });
          }}
        </Geographies>
      </ComposableMap>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded-md border border-border bg-popover p-3 shadow-lg text-xs space-y-1 min-w-[200px]"
          style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
        >
          <div className="font-semibold text-sm">{tooltip.state.state}</div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-muted-foreground">
            <span>Facilities</span>
            <span className="text-right tabular-nums text-foreground">
              {tooltip.state.facility_count.toLocaleString()}
            </span>
            <span>Avg trust</span>
            <span className="text-right tabular-nums text-foreground">
              {tooltip.state.avg_trust_score.toFixed(1)}
            </span>
            <span>Major specialty</span>
            <span className="text-right tabular-nums text-foreground">
              {(tooltip.state.major_specialty_share * 100).toFixed(1)}%
            </span>
            <span>Hospital share</span>
            <span className="text-right tabular-nums text-foreground">
              {(tooltip.state.hospital_share * 100).toFixed(1)}%
            </span>
            <span>Desert score</span>
            <span className="text-right tabular-nums text-foreground font-semibold">
              {tooltip.state.desert_score.toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function RankedFallback({ data }: { data: StateDesert[] }) {
  const sorted = [...data].sort((a, b) => b.desert_score - a.desert_score);
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-muted-foreground mb-2">
        Map unavailable — showing ranked list.
      </p>
      {sorted.map((d) => (
        <div
          key={d.state}
          className="flex items-center gap-3 rounded-md border border-border bg-background px-3 py-2"
        >
          <span className="text-sm font-medium w-32 truncate">{d.state}</span>
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${d.desert_score * 100}%`,
                background: colorScale(d.desert_score),
              }}
            />
          </div>
          <span className="text-xs text-muted-foreground tabular-nums w-24 text-right">
            {d.facility_count.toLocaleString()} fac.
          </span>
        </div>
      ))}
    </div>
  );
}

function SpecialtyMatrix() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["specialty-gaps"],
    queryFn: getSpecialtyGaps,
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError || !data) {
    return (
      <p className="text-sm text-muted-foreground">
        Could not load specialty gaps.
      </p>
    );
  }

  const cellMap = new Map<string, number>();
  data.cells.forEach((c) =>
    cellMap.set(`${c.specialty}|${c.state}`, c.facility_count),
  );

  // per-row max for normalization
  const rowMax = new Map<string, number>();
  data.specialties.forEach((sp) => {
    let m = 0;
    data.states.forEach((st) => {
      const v = cellMap.get(`${sp}|${st}`) ?? 0;
      if (v > m) m = v;
    });
    rowMax.set(sp, m || 1);
  });

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-card text-left p-2 font-semibold text-muted-foreground border-b border-border">
              Specialty
            </th>
            {data.states.map((st) => (
              <th
                key={st}
                className="p-2 font-medium text-muted-foreground border-b border-border whitespace-nowrap text-left"
              >
                {st}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.specialties.map((sp) => {
            const max = rowMax.get(sp) || 1;
            return (
              <tr key={sp}>
                <td className="sticky left-0 z-10 bg-card p-2 font-semibold capitalize border-b border-border">
                  {sp}
                </td>
                {data.states.map((st) => {
                  const v = cellMap.get(`${sp}|${st}`) ?? 0;
                  const intensity = v / max;
                  return (
                    <td
                      key={st}
                      className="p-2 border-b border-border tabular-nums text-center min-w-[56px]"
                      style={{
                        background: `hsl(239 84% 60% / ${intensity * 0.9})`,
                        color: intensity > 0.5 ? "white" : undefined,
                      }}
                      title={`${sp} in ${st}: ${v}`}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function MapPage() {
  const desertsQ = useQuery({
    queryKey: ["deserts", 36],
    queryFn: () => getDeserts(36),
  });

  const worst = useMemo(() => {
    if (!desertsQ.data?.length) return null;
    return [...desertsQ.data].sort((a, b) => b.desert_score - a.desert_score)[0];
  }, [desertsQ.data]);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <Card className="bg-surface border-border">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <MapPinned className="h-5 w-5 text-primary" />
                  Medical deserts across India
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  Each state coloured by composite desert score (low facility
                  count, low trust, low specialty share).
                </p>
              </div>
              {worst && (
                <div className="rounded-md border border-trust-low/30 bg-trust-low/10 px-3 py-2 text-xs">
                  <div className="text-muted-foreground">Worst desert</div>
                  <div className="font-bold text-foreground">{worst.state}</div>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {desertsQ.isLoading ? (
              <Skeleton className="h-[420px] w-full" />
            ) : desertsQ.isError || !desertsQ.data ? (
              <div className="rounded-md border border-border p-6 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Could not load desert stats.
              </div>
            ) : (
              <>
                <div className="hidden md:block">
                  <ChoroplethMap data={desertsQ.data} />
                </div>
                <div className="md:hidden">
                  <RankedFallback data={desertsQ.data} />
                </div>
                <div className="mt-3 flex justify-end">
                  <DesertLegend />
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="bg-surface border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Specialty gap matrix</CardTitle>
            <p className="text-sm text-muted-foreground">
              Facility counts by major specialty across top states. Darker =
              better-served (within row).
            </p>
          </CardHeader>
          <CardContent>
            <SpecialtyMatrix />
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}

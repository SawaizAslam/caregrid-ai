import type { ScoreComponentsT } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface ScoreComponentsProps {
  components: ScoreComponentsT;
  className?: string;
}

const labels: Array<{ key: keyof ScoreComponentsT; label: string }> = [
  { key: "semantic", label: "Semantic" },
  { key: "keyword", label: "Keyword" },
  { key: "trust", label: "Trust" },
  { key: "location", label: "Location" },
];

export function ScoreComponents({ components, className }: ScoreComponentsProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
        Score components
      </p>
      <div className="space-y-1">
        {labels.map(({ key, label }) => {
          const v = Math.max(0, Math.min(1, components?.[key] ?? 0));
          return (
            <Tooltip key={key}>
              <TooltipTrigger asChild>
                <div className="grid grid-cols-[64px_1fr] items-center gap-2 cursor-default">
                  <span className="text-xs text-muted-foreground">{label}</span>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${v * 100}%` }}
                    />
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent side="left">
                {label}: {v.toFixed(3)}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

export default ScoreComponents;

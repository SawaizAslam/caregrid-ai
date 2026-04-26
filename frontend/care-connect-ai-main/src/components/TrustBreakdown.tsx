import type { TrustBreakdownItem } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TrustBreakdownProps {
  items: TrustBreakdownItem[];
  className?: string;
}

export function TrustBreakdown({ items, className }: TrustBreakdownProps) {
  if (!items?.length) {
    return (
      <p className={cn("text-sm text-muted-foreground italic", className)}>
        No trust signals recorded.
      </p>
    );
  }
  return (
    <ul className={cn("space-y-3", className)}>
      {items.map((it, idx) => {
        const positive = it.delta >= 0;
        return (
          <li
            key={idx}
            className="rounded-md border border-border bg-surface p-3"
          >
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "shrink-0 inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-bold tabular-nums",
                  positive
                    ? "bg-trust-high text-trust-high-foreground"
                    : "bg-trust-low text-trust-low-foreground",
                )}
              >
                {positive ? "+" : ""}
                {it.delta}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-foreground leading-snug">
                  {it.rule}
                </p>
                {it.evidence && (
                  <blockquote className="mt-1.5 border-l-2 border-border pl-3 text-sm italic text-muted-foreground">
                    &ldquo;{it.evidence}&rdquo;
                  </blockquote>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default TrustBreakdown;

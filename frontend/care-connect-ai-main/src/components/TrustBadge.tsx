import { cn } from "@/lib/utils";

type Size = "sm" | "md" | "lg";

interface TrustBadgeProps {
  score: number;
  size?: Size;
  className?: string;
}

function tier(score: number) {
  if (score >= 80) return "high" as const;
  if (score >= 50) return "mid" as const;
  return "low" as const;
}

const sizes: Record<Size, string> = {
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-1",
  lg: "text-2xl px-4 py-2 font-bold",
};

export function TrustBadge({ score, size = "md", className }: TrustBadgeProps) {
  const t = tier(score);
  const palette = {
    high: "bg-trust-high text-trust-high-foreground",
    mid: "bg-trust-mid text-trust-mid-foreground",
    low: "bg-trust-low text-trust-low-foreground",
  }[t];
  const label = { high: "High trust", mid: "Moderate", low: "Low trust" }[t];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold leading-none whitespace-nowrap",
        palette,
        sizes[size],
        className,
      )}
      title={label}
    >
      <span className="opacity-80">Trust</span>
      <span>{Math.round(score)}</span>
    </span>
  );
}

export default TrustBadge;

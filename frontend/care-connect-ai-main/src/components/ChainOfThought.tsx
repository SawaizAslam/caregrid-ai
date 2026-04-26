import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { QueryUnderstood } from "@/lib/types";

interface ChainOfThoughtProps {
  query: QueryUnderstood | null | undefined;
  className?: string;
}

export function ChainOfThought({ query, className }: ChainOfThoughtProps) {
  const [open, setOpen] = useState(false);
  if (!query) return null;

  const json = JSON.stringify(query, null, 2);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div
        className={cn(
          "rounded-lg border border-primary/30 bg-accent/40 overflow-hidden",
          className,
        )}
      >
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-accent/60 transition-colors">
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="h-4 w-4 text-primary shrink-0" />
            <span className="font-semibold text-sm">Chain of thought</span>
            <span className="text-xs text-muted-foreground truncate">
              How the agent parsed your query
            </span>
          </div>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 transition-transform text-muted-foreground",
              open && "rotate-180",
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="px-4 pb-4 pt-0 text-xs font-mono leading-relaxed text-foreground whitespace-pre-wrap break-words max-h-72 overflow-auto">
            {json}
          </pre>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

export default ChainOfThought;

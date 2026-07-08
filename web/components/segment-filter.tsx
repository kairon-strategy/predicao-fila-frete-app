"use client";

import { SEGMENTS } from "@/lib/segments";
import { cn } from "@/lib/utils";

// Botões para filtrar por commodity. value="" = Todos.
export function SegmentFilter({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  const opts = [{ key: "", label: "Todos" }, ...SEGMENTS];
  return (
    <div className={cn("inline-flex flex-wrap gap-1 rounded-lg border border-border bg-card p-1", className)}>
      {opts.map((o) => {
        const active = value === o.key;
        return (
          <button
            key={o.key || "todos"}
            type="button"
            onClick={() => onChange(o.key)}
            aria-pressed={active}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              active
                ? "bg-gradient-to-r from-gold to-[#8f7648] text-[#0a0e1a] shadow-gold"
                : "text-muted-foreground hover:bg-gold/10 hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

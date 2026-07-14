"use client";

import { SEGMENTS } from "@/lib/segments";
import { cn } from "@/lib/utils";

// Botões para filtrar por commodity. value="" = Todos.
// Opções com `disabled` (ex.: açúcar sem dados) aparecem esmaecidas com "em breve".
export function SegmentFilter({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  const opts: { key: string; label: string; disabled?: boolean }[] = [
    { key: "", label: "Todos" },
    ...SEGMENTS,
  ];
  return (
    <div className={cn("inline-flex flex-wrap gap-1 rounded-lg border border-border bg-card p-1", className)}>
      {opts.map((o) => {
        const active = value === o.key;
        const disabled = !!o.disabled;
        return (
          <button
            key={o.key || "todos"}
            type="button"
            disabled={disabled}
            onClick={() => !disabled && onChange(o.key)}
            aria-pressed={active}
            title={disabled ? "Em breve (sem dados ainda)" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              disabled
                ? "cursor-not-allowed text-muted-foreground/40"
                : active
                  ? "bg-gradient-to-r from-gold to-[#8f7648] text-[#0a0e1a] shadow-gold"
                  : "text-muted-foreground hover:bg-gold/10 hover:text-foreground",
            )}
          >
            {o.label}
            {disabled && <span className="ml-1 opacity-70">· em breve</span>}
          </button>
        );
      })}
    </div>
  );
}

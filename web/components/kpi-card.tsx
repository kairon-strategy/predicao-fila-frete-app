import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  gold = false,
  tone = "muted",
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  gold?: boolean;
  tone?: "muted" | "up" | "down";
}) {
  return (
    <Card className="edge-gold-top gap-2 p-5">
      <div className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className={cn("font-serif text-3xl leading-none", gold && "text-gold")}>{value}</div>
      {hint && (
        <div
          className={cn(
            "text-[11.5px]",
            tone === "up" && "text-success",
            tone === "down" && "text-destructive",
            tone === "muted" && "text-muted-foreground",
          )}
        >
          {hint}
        </div>
      )}
    </Card>
  );
}

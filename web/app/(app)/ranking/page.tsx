"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";

import { FreightAreaChart } from "@/components/charts/freight-area-chart";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type RouteRankingItem } from "@/lib/api";
import { brl, num, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRODUTOS = ["Todos", "ureia", "MAP", "KCl", "NPK", "algodão"];

export default function RankingPage() {
  const [produto, setProduto] = useState("Todos");
  const [corredor, setCorredor] = useState("");
  const [selected, setSelected] = useState<RouteRankingItem | null>(null);

  const { data: routes, isLoading } = useSWR(["routes", produto, corredor], () =>
    api.getRoutes(produto === "Todos" ? undefined : produto, corredor || undefined),
  );

  const biggestRise = routes?.length
    ? [...routes].sort((a, b) => b.var_30d_pct - a.var_30d_pct)[0]
    : undefined;
  const bestEfficiency = routes?.length
    ? [...routes].sort((a, b) => a.r_per_ton_km - b.r_per_ton_km)[0]
    : undefined;

  return (
    <>
      <PageHeader
        title="Ranking de rotas"
        subtitle="Comparativo das rotas monitoradas · R$/t, banda, variação 30d"
      >
        <Badge variant="outline" className="border-gold/40 text-gold">
          {routes?.length ?? 0} rotas
        </Badge>
      </PageHeader>

      {/* Summary cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <Card className="edge-gold-top flex-row items-center justify-between p-5">
          <div>
            <div className="text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
              Maior alta · 30d
            </div>
            <div className="mt-1 font-medium">
              {biggestRise ? `${biggestRise.origem} → ${biggestRise.destino}` : "—"}
            </div>
          </div>
          <div className="flex items-center gap-1.5 font-serif text-2xl text-warning">
            <TrendingUp className="size-5" />
            {biggestRise ? pct(biggestRise.var_30d_pct) : "—"}
          </div>
        </Card>
        <Card className="edge-gold-top flex-row items-center justify-between p-5">
          <div>
            <div className="text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
              Melhor eficiência · R$/t·km
            </div>
            <div className="mt-1 font-medium">
              {bestEfficiency ? `${bestEfficiency.origem} → ${bestEfficiency.destino}` : "—"}
            </div>
          </div>
          <div className="flex items-center gap-1.5 font-serif text-2xl text-success">
            <TrendingDown className="size-5" />
            {bestEfficiency ? num(bestEfficiency.r_per_ton_km, 3) : "—"}
          </div>
        </Card>
      </div>

      {/* Filtros */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select value={produto} onValueChange={setProduto}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Produto" />
          </SelectTrigger>
          <SelectContent>
            {PRODUTOS.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={corredor}
          onChange={(e) => setCorredor(e.target.value)}
          placeholder="corredor (ex: MT-Norte)"
          className="w-[220px]"
        />
      </div>

      {/* Tabela */}
      <Card className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-10 text-gold">#</TableHead>
                <TableHead className="text-gold">Rota</TableHead>
                <TableHead className="text-gold">Produto</TableHead>
                <TableHead className="text-right text-gold">R$/t</TableHead>
                <TableHead className="text-right text-gold">R$/t·km</TableHead>
                <TableHead className="text-gold">Banda</TableHead>
                <TableHead className="text-right text-gold">Var 30d</TableHead>
                <TableHead className="text-right text-gold">MAPE</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading &&
                Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={8}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {routes?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                    Nenhuma rota para os filtros selecionados.
                  </TableCell>
                </TableRow>
              )}
              {routes?.map((r, i) => (
                <TableRow
                  key={r.route_id}
                  className="cursor-pointer"
                  onClick={() => setSelected(r)}
                >
                  <TableCell className="font-mono font-semibold text-gold">
                    {String(i + 1).padStart(2, "0")}
                  </TableCell>
                  <TableCell>
                    <span className="font-medium">{r.origem}</span>
                    <span className="text-muted-foreground"> → {r.destino}</span>
                  </TableCell>
                  <TableCell>
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
                      {r.produto}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-gold">
                    {brl(r.frete_r_per_ton)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    {num(r.r_per_ton_km, 3)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {brl(r.banda_p10)} – {brl(r.banda_p90)}
                  </TableCell>
                  <TableCell className="text-right">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 font-mono text-xs",
                        r.var_30d_pct >= 0
                          ? "bg-warning/15 text-warning"
                          : "bg-success/15 text-success",
                      )}
                    >
                      {pct(r.var_30d_pct)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    {r.mape === null ? "—" : `${num(r.mape, 1)}%`}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <RouteHistoryDialog route={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function RouteHistoryDialog({
  route,
  onClose,
}: {
  route: RouteRankingItem | null;
  onClose: () => void;
}) {
  // Extrai o id via optional chaining (sem deref de null) — evita crash sob o React Compiler.
  const routeId = route?.route_id ?? null;
  const { data: history } = useSWR(
    routeId ? ["history", routeId] : null,
    () => api.getRouteHistory(routeId as string, 12),
  );

  const values = history?.points.map((p) => p.frete_r_per_ton) ?? [];
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const avg = values.length ? values.reduce((s, v) => s + v, 0) / values.length : 0;

  return (
    <Dialog open={!!route} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-serif">
            {route ? (
              <>
                {route.origem} → {route.destino}
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {route.produto}
                </span>
              </>
            ) : (
              ""
            )}
          </DialogTitle>
        </DialogHeader>

        {!history ? (
          <Skeleton className="h-[260px] w-full" />
        ) : (
          <>
            <div className="mb-3 grid grid-cols-3 gap-3">
              {[
                { label: "Mínimo", v: min },
                { label: "Média", v: avg, gold: true },
                { label: "Máximo", v: max },
              ].map((k) => (
                <div key={k.label} className="rounded-lg border border-border bg-secondary/40 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {k.label}
                  </div>
                  <div className={cn("font-serif text-lg", k.gold && "text-gold")}>{brl(k.v)}</div>
                </div>
              ))}
            </div>
            <FreightAreaChart
              data={history.points.map((p) => ({
                label: p.month.slice(5),
                value: p.frete_r_per_ton,
                low: p.banda_p10,
                high: p.banda_p90,
              }))}
              height={240}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

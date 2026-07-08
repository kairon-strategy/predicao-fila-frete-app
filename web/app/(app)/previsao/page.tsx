"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import {
  TrendingDown,
  TrendingUp,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Route as RouteIcon,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { KpiCard } from "@/components/kpi-card";
import { FreightAreaChart } from "@/components/charts/freight-area-chart";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { api, ApiError } from "@/lib/api";
import type { RouteRankingItem, RouteHistory, RouteHistoryPoint } from "@/lib/api";
import { brl, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

function routeLabel(r: RouteRankingItem): string {
  return `${r.origem} → ${r.destino} · ${r.produto}`;
}

function formatMonth(month: string): string {
  // "YYYY-MM" → "mmm/aa"
  const [y, m] = month.split("-");
  const idx = Number(m) - 1;
  const meses = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
  ];
  if (Number.isNaN(idx) || idx < 0 || idx > 11 || !y) return month;
  return `${meses[idx]}/${y.slice(2)}`;
}

type Kpis = {
  min: { value: number; month: string };
  max: { value: number; month: string };
  avg: number;
  avgBand: number;
} | null;

function computeKpis(points: RouteHistoryPoint[]): Kpis {
  if (!points.length) return null;
  let min = points[0];
  let max = points[0];
  let sum = 0;
  let bandSum = 0;
  for (const p of points) {
    if (p.frete_r_per_ton < min.frete_r_per_ton) min = p;
    if (p.frete_r_per_ton > max.frete_r_per_ton) max = p;
    sum += p.frete_r_per_ton;
    bandSum += p.banda_p90 - p.banda_p10;
  }
  return {
    min: { value: min.frete_r_per_ton, month: min.month },
    max: { value: max.frete_r_per_ton, month: max.month },
    avg: sum / points.length,
    avgBand: bandSum / points.length,
  };
}

export default function PrevisaoPage() {
  const [selectedRouteId, setSelectedRouteId] = useState<string>("");

  const {
    data: routes,
    error: routesError,
    isLoading: routesLoading,
  } = useSWR<RouteRankingItem[]>("routes", () => api.getRoutes());

  // Default to first route once loaded.
  useEffect(() => {
    if (!selectedRouteId && routes && routes.length > 0) {
      setSelectedRouteId(routes[0].route_id);
    }
  }, [routes, selectedRouteId]);

  const {
    data: history,
    error: historyError,
    isLoading: historyLoading,
  } = useSWR<RouteHistory>(
    selectedRouteId ? ["history", selectedRouteId] : null,
    () => api.getRouteHistory(selectedRouteId, 12),
  );

  // Surface errors as toasts.
  useEffect(() => {
    if (routesError) {
      const msg =
        routesError instanceof ApiError
          ? routesError.message
          : "Falha ao carregar rotas.";
      toast.error(msg);
    }
  }, [routesError]);

  useEffect(() => {
    if (historyError) {
      const msg =
        historyError instanceof ApiError
          ? historyError.message
          : "Falha ao carregar a série histórica.";
      toast.error(msg);
    }
  }, [historyError]);

  const points = history?.points ?? [];

  const chartData = useMemo(
    () =>
      points.map((p) => ({
        month: p.month,
        value: p.frete_r_per_ton,
        low: p.banda_p10,
        high: p.banda_p90,
      })),
    [points],
  );

  const kpis = useMemo(() => computeKpis(points), [points]);

  const selectedRoute = routes?.find((r) => r.route_id === selectedRouteId);

  const routeSelect = (
    <Select
      value={selectedRouteId}
      onValueChange={setSelectedRouteId}
      disabled={routesLoading || !routes || routes.length === 0}
    >
      <SelectTrigger className="w-[300px]">
        <RouteIcon className="size-4 text-gold" />
        <SelectValue placeholder="Selecione uma rota" />
      </SelectTrigger>
      <SelectContent>
        {routes?.map((r) => (
          <SelectItem key={r.route_id} value={r.route_id}>
            {routeLabel(r)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );

  const noRoutes = !routesLoading && !routesError && routes && routes.length === 0;
  const chartLoading = routesLoading || historyLoading || (!!selectedRouteId && !history && !historyError);

  return (
    <div className="mx-auto w-full max-w-6xl">
      <PageHeader
        title="Previsão 12 meses"
        subtitle="Série mensal com banda de incerteza · janela de contrato"
      >
        {routeSelect}
      </PageHeader>

      {noRoutes ? (
        <Card className="edge-gold-top shadow-premium flex flex-col items-center justify-center gap-2 p-12 text-center">
          <RouteIcon className="size-8 text-muted-foreground" />
          <p className="font-serif text-lg">Nenhuma rota disponível</p>
          <p className="text-sm text-muted-foreground">
            Cadastre rotas para visualizar a projeção mensal de frete.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-6">
          {/* KPI row */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {chartLoading || !kpis ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="edge-gold-top gap-2 p-5">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-8 w-28" />
                  <Skeleton className="h-3 w-16" />
                </Card>
              ))
            ) : (
              <>
                <KpiCard
                  label="Mínimo projetado"
                  value={brl(kpis.min.value)}
                  hint={
                    <span className="inline-flex items-center gap-1">
                      <TrendingDown className="size-3.5 text-success" />
                      {formatMonth(kpis.min.month)}
                    </span>
                  }
                  tone="up"
                />
                <KpiCard
                  label="Pico projetado"
                  value={brl(kpis.max.value)}
                  gold
                  hint={
                    <span className="inline-flex items-center gap-1">
                      <TrendingUp className="size-3.5" />
                      {formatMonth(kpis.max.month)}
                    </span>
                  }
                />
                <KpiCard
                  label="Média 12m"
                  value={brl(kpis.avg)}
                  hint={
                    <span className="inline-flex items-center gap-1">
                      <Activity className="size-3.5" />
                      R$/t · média da série
                    </span>
                  }
                />
                <KpiCard
                  label="Amplitude média da banda"
                  value={brl(kpis.avgBand)}
                  hint="p90 − p10 · incerteza típica"
                />
              </>
            )}
          </div>

          {/* Main chart card */}
          <Card className="edge-gold-top shadow-premium gap-4 p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-serif text-xl text-gradient-gold">
                  Projeção mensal do frete
                </h2>
                {selectedRoute && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {selectedRoute.origem} → {selectedRoute.destino} ·{" "}
                    {selectedRoute.produto}
                  </p>
                )}
              </div>
            </div>

            {chartLoading ? (
              <Skeleton className="h-[320px] w-full rounded-lg" />
            ) : chartData.length === 0 ? (
              <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">
                Sem pontos de série para esta rota.
              </div>
            ) : (
              <FreightAreaChart data={chartData} height={320} />
            )}

          </Card>

          {/* Monthly table */}
          <Card className="edge-gold-top shadow-premium gap-4 p-6">
            <div>
              <h2 className="font-serif text-xl">Detalhamento mensal</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Valor projetado, banda de incerteza e variação mês a mês.
              </p>
            </div>

            {chartLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-9 w-full" />
                ))}
              </div>
            ) : points.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Sem dados mensais disponíveis.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Mês</TableHead>
                    <TableHead className="text-right">R$/t</TableHead>
                    <TableHead className="text-right">Banda (p10 – p90)</TableHead>
                    <TableHead className="text-right">vs mês anterior</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {points.map((p, i) => {
                    const prev = i > 0 ? points[i - 1] : null;
                    const change =
                      prev && prev.frete_r_per_ton !== 0
                        ? ((p.frete_r_per_ton - prev.frete_r_per_ton) /
                            prev.frete_r_per_ton) *
                          100
                        : null;
                    const up = change !== null && change > 0.05;
                    const down = change !== null && change < -0.05;
                    return (
                      <TableRow key={p.month}>
                        <TableCell className="font-medium">
                          {formatMonth(p.month)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-gold">
                          {brl(p.frete_r_per_ton)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs text-muted-foreground">
                          {brl(p.banda_p10)} – {brl(p.banda_p90)}
                        </TableCell>
                        <TableCell
                          className={cn(
                            "text-right font-mono",
                            up && "text-destructive",
                            down && "text-success",
                            !up && !down && "text-muted-foreground",
                          )}
                        >
                          {change === null ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            <span className="inline-flex items-center justify-end gap-1">
                              {up ? (
                                <ArrowUpRight className="size-3.5" />
                              ) : down ? (
                                <ArrowDownRight className="size-3.5" />
                              ) : (
                                <Minus className="size-3.5" />
                              )}
                              {pct(change)}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

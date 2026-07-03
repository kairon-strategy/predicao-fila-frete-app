"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import {
  Wheat,
  Package,
  Route as RouteIcon,
  Fuel,
  ArrowUpRight,
  ArrowDownRight,
  TrendingUp,
  Download,
  Ship,
  Warehouse,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/page-header";
import { KpiCard } from "@/components/kpi-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import type {
  RouteRankingItem,
  PredictResponse,
  RouteHistory,
  Driver,
} from "@/lib/api";
import { brl, num, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

/* --------------------------- constantes / mapas --------------------------- */

const GOLD = "#c5a572";
const BLUE = "#6ea9e5";
const BLUE_DARK = "#3b7fc4";

const TOOLTIP_STYLE = {
  background: "rgba(20,20,30,0.92)",
  border: "1px solid rgba(197,165,114,0.35)",
  borderRadius: 10,
  color: "#fff",
  fontSize: 12,
} as const;

const MESES = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

// espelha o backend
const SEASONALITY: Record<number, number> = {
  1: 1.12,
  2: 1.15,
  3: 1.18,
  4: 1.05,
  5: 0.98,
  6: 0.95,
  7: 1.02,
  8: 1.1,
  9: 1.08,
  10: 1.0,
  11: 0.97,
  12: 1.03,
};

type Produto = "soja" | "milho" | "algodão" | "ureia";

const PRODUTOS: {
  value: Produto;
  label: string;
  icon: typeof Wheat;
}[] = [
  { value: "soja", label: "Soja", icon: Wheat },
  { value: "milho", label: "Milho", icon: Wheat },
  { value: "algodão", label: "Algodão", icon: Package },
  { value: "ureia", label: "Fertilizante", icon: Package },
];

const PRODUTO_LABEL: Record<Produto, string> = {
  soja: "Soja",
  milho: "Milho",
  algodão: "Algodão",
  ureia: "Fertilizante",
};

// janela de safra por produto (texto + meses de pico)
const SAFRA: Record<Produto, { texto: string; meses: number[] }> = {
  soja: { texto: "Fev–Abr", meses: [2, 3, 4] },
  milho: { texto: "Jun–Ago", meses: [6, 7, 8] },
  algodão: { texto: "Jul–Set", meses: [7, 8, 9] },
  ureia: { texto: "Ano todo", meses: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
};

const isFertilizante = (p: Produto) => p === "ureia";

// tradução pt-BR dos drivers
const DRIVER_LABEL: Record<string, string> = {
  custo_combustivel: "Diesel / combustível",
  custo_operacional_distancia: "Distância / operacional",
  sazonalidade: "Sazonalidade",
  piso_antt: "Piso ANTT",
  produto_fertilizante: "Tipo de produto",
  diesel_price: "Diesel",
  distancia_km: "Distância",
  seasonality: "Sazonalidade",
  month: "Mês",
  produto_is_fertilizante: "Tipo de produto",
};

const DRIVER_HINT: Record<string, string> = {
  custo_combustivel: "Preço do diesel S-10 pressiona o custo por km.",
  custo_operacional_distancia: "Quanto maior a distância, maior o custo operacional.",
  sazonalidade: "Demanda por frete varia ao longo da safra.",
  piso_antt: "Tabela mínima de frete regula o piso da tarifa.",
  produto_fertilizante: "Fertilizante tem logística e retorno distintos dos grãos.",
  diesel_price: "Preço do diesel S-10 pressiona o custo por km.",
  distancia_km: "Quanto maior a distância, maior o custo operacional.",
  seasonality: "Demanda por frete varia ao longo da safra.",
  month: "O mês do embarque altera a demanda e o preço.",
  produto_is_fertilizante: "Fertilizante tem logística e retorno distintos dos grãos.",
};

function driverLabel(feature: string): string {
  return DRIVER_LABEL[feature] ?? feature;
}
function driverHint(feature: string): string {
  return DRIVER_HINT[feature] ?? "Contribui para o frete estimado.";
}

function formatMonth(month: string): string {
  const [y, m] = month.split("-");
  const idx = Number(m) - 1;
  if (Number.isNaN(idx) || idx < 0 || idx > 11 || !y) return month;
  return `${MESES[idx].toLowerCase()}/${y.slice(2)}`;
}

/* --------------------------------- página --------------------------------- */

export default function PredicaoPage() {
  const [produto, setProduto] = useState<Produto>("soja");
  const [selectedRouteId, setSelectedRouteId] = useState<string>("");
  const [diesel, setDiesel] = useState<number>(6.2);
  const [mes, setMes] = useState<number>(7);
  const [peso, setPeso] = useState<number>(32);

  const produtoLabel = PRODUTO_LABEL[produto];
  const mesLabel = MESES[mes - 1];

  /* --------------------------------- fetch -------------------------------- */

  const { data: allRoutes, error: allRoutesError } = useSWR<RouteRankingItem[]>(
    ["routes-all"],
    () => api.getRoutes(),
  );

  const {
    data: produtoRoutes,
    error: produtoRoutesError,
    isLoading: produtoRoutesLoading,
  } = useSWR<RouteRankingItem[]>(["routes", produto], () => api.getRoutes(produto));

  // Ao trocar de produto, reseta a rota selecionada e reaponta p/ a primeira.
  useEffect(() => {
    if (!produtoRoutes) return;
    const stillValid = produtoRoutes.some((r) => r.route_id === selectedRouteId);
    if (!stillValid) {
      setSelectedRouteId(produtoRoutes[0]?.route_id ?? "");
    }
  }, [produtoRoutes, selectedRouteId]);

  const selectedRoute = produtoRoutes?.find((r) => r.route_id === selectedRouteId);

  const {
    data: predict,
    error: predictError,
    isLoading: predictLoading,
  } = useSWR<PredictResponse>(
    selectedRoute ? ["predict", produto, selectedRouteId, diesel, mes, peso] : null,
    () =>
      api.predict({
        origem: selectedRoute!.origem,
        destino: selectedRoute!.destino,
        produto,
        data: `2026-${String(mes).padStart(2, "0")}-15`,
        carga_ton: peso,
        // diesel_price faz o slider afetar a predição (contrato aceita, tipo local omite)
        diesel_price: diesel,
      } as Parameters<typeof api.predict>[0] & { diesel_price: number }),
  );

  const { data: history, isLoading: historyLoading } = useSWR<RouteHistory>(
    selectedRouteId ? ["history", selectedRouteId] : null,
    () => api.getRouteHistory(selectedRouteId, 12),
  );

  /* ------------------------------- toasts --------------------------------- */

  useEffect(() => {
    if (!allRoutesError && !produtoRoutesError) return;
    toast.error("Falha ao carregar rotas.");
  }, [allRoutesError, produtoRoutesError]);

  useEffect(() => {
    if (!predictError) return;
    if (predictError instanceof ApiError && predictError.status === 403) {
      toast.error("Seu papel não permite gerar predições.");
    } else {
      const msg =
        predictError instanceof ApiError ? predictError.message : "Falha ao gerar a predição.";
      toast.error(msg);
    }
  }, [predictError]);

  /* ------------------------------- derivados ------------------------------ */

  // KPIs a partir de allRoutes filtrado pelo produto atual
  const kpiRoutes = useMemo(
    () => (allRoutes ?? []).filter((r) => r.produto === produto),
    [allRoutes, produto],
  );

  const avgFrete = useMemo(() => {
    if (!kpiRoutes.length) return 0;
    return kpiRoutes.reduce((s, r) => s + r.frete_r_per_ton, 0) / kpiRoutes.length;
  }, [kpiRoutes]);

  const avgVar = useMemo(() => {
    if (!kpiRoutes.length) return 0;
    return kpiRoutes.reduce((s, r) => s + r.var_30d_pct, 0) / kpiRoutes.length;
  }, [kpiRoutes]);

  const maxRoute = useMemo(() => {
    if (!kpiRoutes.length) return null;
    return kpiRoutes.reduce((a, b) => (b.frete_r_per_ton > a.frete_r_per_ton ? b : a));
  }, [kpiRoutes]);

  const safra = SAFRA[produto];
  const noPico = safra.meses.includes(mes);

  // média histórica da rota (p/ tendência)
  const histAvg = useMemo(() => {
    const pts = history?.points ?? [];
    if (!pts.length) return null;
    return pts.reduce((s, p) => s + p.frete_r_per_ton, 0) / pts.length;
  }, [history]);

  const fretePorTon = predict?.frete_r_per_ton ?? 0;

  const tendencia = useMemo<{
    label: string;
    tone: "warning" | "success" | "muted";
  }>(() => {
    if (!predict || histAvg === null || histAvg === 0)
      return { label: "estável", tone: "muted" };
    if (fretePorTon > histAvg * 1.03) return { label: "alta", tone: "warning" };
    if (fretePorTon < histAvg * 0.97) return { label: "baixa", tone: "success" };
    return { label: "estável", tone: "muted" };
  }, [predict, histAvg, fretePorTon]);

  const kpiLoading = !allRoutes && !allRoutesError;
  const noRoutes =
    !produtoRoutesLoading && !produtoRoutesError && produtoRoutes && produtoRoutes.length === 0;

  /* --------------------------------- charts ------------------------------- */

  const previsaoData = useMemo(() => {
    const pts = history?.points ?? [];
    const dist = selectedRoute?.distancia_km ?? 0;
    if (!dist) return [];
    return pts.map((p) => ({
      label: formatMonth(p.month),
      previsto: Number((p.frete_r_per_ton / dist).toFixed(4)),
    }));
  }, [history, selectedRoute]);

  const previsaoMean = useMemo(() => {
    if (!previsaoData.length) return 0;
    return previsaoData.reduce((s, d) => s + d.previsto, 0) / previsaoData.length;
  }, [previsaoData]);

  const previsaoWithRef = useMemo(
    () => previsaoData.map((d) => ({ ...d, media: Number(previsaoMean.toFixed(4)) })),
    [previsaoData, previsaoMean],
  );

  const rankingData = useMemo(() => {
    return [...(produtoRoutes ?? [])]
      .sort((a, b) => b.frete_r_per_ton - a.frete_r_per_ton)
      .slice(0, 6)
      .map((r) => ({
        name: `${r.origem} → ${r.destino}`,
        value: r.frete_r_per_ton,
      }));
  }, [produtoRoutes]);

  const driverSum = useMemo(() => {
    const ds = predict?.drivers ?? [];
    return ds.reduce((s, d) => s + Math.abs(d.shap_value), 0);
  }, [predict]);

  /* ------------------------------- export CSV ----------------------------- */

  function exportCsv() {
    const rows = produtoRoutes ?? [];
    if (!rows.length) {
      toast.error("Sem rotas para exportar.");
      return;
    }
    const header = ["Origem", "Destino", "Corredor", "Distancia_km", "R$/km", "R$/t"];
    const lines = rows.map((r) =>
      [
        r.origem,
        r.destino,
        r.corredor ?? "",
        num(r.distancia_km, 0),
        num(r.r_per_ton_km, 3),
        num(r.frete_r_per_ton, 2),
      ]
        .map((c) => `"${String(c).replace(/"/g, '""')}"`)
        .join(","),
    );
    const csv = [header.join(","), ...lines].join("\n");
    const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rotas-${produto}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast.success("CSV exportado.");
  }

  /* --------------------------------- render ------------------------------- */

  return (
    <div className="mx-auto w-full max-w-7xl">
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            <span>
              Predição de frete <span className="text-gradient-gold">rodoviário</span>
            </span>
            <Badge variant="outline" className="border-gold/40 text-gold">
              Beta
            </Badge>
          </span>
        }
        subtitle="Originação de grãos e algodão · Distribuição de fertilizantes · Rotas Brasil"
      >
        <Button variant="outline" onClick={() => toast("Comparar rotas — em breve")}>
          Comparar rotas
        </Button>
        <Button variant="outline" asChild>
          <a href="/simulacao">Nova simulação</a>
        </Button>
      </PageHeader>

      {/* --------------------------------- KPIs -------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpiLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="edge-gold-top gap-2 p-5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-8 w-28" />
              <Skeleton className="h-3 w-20" />
            </Card>
          ))
        ) : (
          <>
            <KpiCard
              label={`Frete médio · ${produtoLabel}`}
              value={brl(avgFrete)}
              gold
              tone={avgVar >= 0 ? "down" : "up"}
              hint={
                <span className="inline-flex items-center gap-1">
                  {avgVar >= 0 ? (
                    <ArrowUpRight className="size-3.5" />
                  ) : (
                    <ArrowDownRight className="size-3.5" />
                  )}
                  {pct(avgVar)} vs mês anterior
                </span>
              }
            />
            <KpiCard
              label={`${produtoLabel} · janela de safra`}
              value={safra.texto}
              hint={noPico ? "no pico" : "fora do pico"}
              tone={noPico ? "down" : "muted"}
            />
            <KpiCard
              label="Diesel S-10 (referência)"
              value={`R$ ${diesel.toFixed(2)}/L`}
              hint="referência de mercado"
            />
            <KpiCard
              label={`Maior frete · ${produtoLabel}`}
              value={maxRoute ? brl(maxRoute.frete_r_per_ton) : "—"}
              tone="down"
              hint={maxRoute ? `${maxRoute.origem} → ${maxRoute.destino}` : "sem rotas"}
            />
          </>
        )}
      </div>

      {/* ------------------------------ corpo 2 col ---------------------------- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* ------------------------------- ESQUERDA --------------------------- */}
        <Card className="edge-gold-top gap-5 p-6 lg:col-span-2">
          <div>
            <h2 className="text-lg font-semibold">Parâmetros da predição</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Configure a carga, rota e variáveis de mercado.
            </p>
          </div>

          {/* Tipo de carga */}
          <div className="flex flex-col gap-2.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Tipo de carga
            </Label>
            <div className="grid grid-cols-2 gap-2.5">
              {PRODUTOS.map((p) => {
                const Icon = p.icon;
                const active = produto === p.value;
                return (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setProduto(p.value)}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg border px-3.5 py-3 text-sm font-medium transition-colors",
                      active
                        ? "border-gold/60 bg-gold/10 text-gold shadow-gold"
                        : "border-border bg-card text-foreground hover:border-gold/30 hover:bg-secondary",
                    )}
                  >
                    <Icon className={cn("size-4", active ? "text-gold" : "text-muted-foreground")} />
                    {p.label}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="text-muted-foreground/70">Fluxo:</span>{" "}
              <span className="font-medium text-foreground">
                {isFertilizante(produto) ? (
                  <span className="inline-flex items-center gap-1">
                    <Ship className="size-3.5 text-gold" />
                    Porto → Interior
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1">
                    <Warehouse className="size-3.5 text-gold" />
                    Originação → Porto
                  </span>
                )}
              </span>
            </p>
          </div>

          <Separator className="opacity-40" />

          {/* Rota */}
          <div className="flex flex-col gap-2.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Rota</Label>
            <Select
              value={selectedRouteId}
              onValueChange={setSelectedRouteId}
              disabled={produtoRoutesLoading || !produtoRoutes || produtoRoutes.length === 0}
            >
              <SelectTrigger className="w-full">
                <RouteIcon className="size-4 text-gold" />
                <SelectValue placeholder="Selecione uma rota" />
              </SelectTrigger>
              <SelectContent>
                {produtoRoutes?.map((r) => (
                  <SelectItem key={r.route_id} value={r.route_id}>
                    {r.origem} → {r.destino}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedRoute && (
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{selectedRoute.corredor ?? "Corredor não informado"}</span>
                <span className="font-mono text-foreground">
                  {num(selectedRoute.distancia_km, 0)} km
                </span>
              </div>
            )}
          </div>

          {/* Diesel */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                <Fuel className="mr-1 inline size-3.5 text-gold" />
                Diesel S-10
              </Label>
              <span className="font-mono text-sm text-gold">R$ {diesel.toFixed(2)}/L</span>
            </div>
            <Slider
              min={4.5}
              max={9}
              step={0.05}
              value={[diesel]}
              onValueChange={(v) => setDiesel(v[0])}
            />
          </div>

          {/* Mês do embarque */}
          <div className="flex flex-col gap-2.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Mês do embarque
            </Label>
            <Select value={String(mes)} onValueChange={(v) => setMes(Number(v))}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MESES.map((m, i) => (
                  <SelectItem key={m} value={String(i + 1)}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Peso */}
          <div className="flex flex-col gap-2.5">
            <Label
              htmlFor="peso"
              className="text-xs uppercase tracking-wider text-muted-foreground"
            >
              Peso da carga (toneladas)
            </Label>
            <Input
              id="peso"
              type="number"
              min={1}
              value={peso}
              onChange={(e) => setPeso(Math.max(1, Number(e.target.value) || 0))}
              className="font-mono"
            />
          </div>
        </Card>

        {/* -------------------------------- DIREITA --------------------------- */}
        <Card className="edge-gold-top glass-gold gap-5 p-6 lg:col-span-3">
          {noRoutes ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <RouteIcon className="size-8 text-muted-foreground" />
              <p className="text-lg font-semibold">Nenhuma rota para {produtoLabel}</p>
              <p className="text-sm text-muted-foreground">
                Selecione outro tipo de carga para visualizar predições.
              </p>
            </div>
          ) : (
            <>
              {/* Cabeçalho da predição */}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-[10.5px] uppercase tracking-[0.2em] text-gold">
                    Predição de frete
                  </div>
                  <h2 className="mt-1 text-xl font-semibold">
                    {selectedRoute
                      ? `${selectedRoute.origem} → ${selectedRoute.destino}`
                      : "—"}
                  </h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {produtoLabel} · {mesLabel} · {peso} t
                  </p>
                </div>
                <TendenciaBadge
                  loading={predictLoading || historyLoading}
                  label={tendencia.label}
                  tone={tendencia.tone}
                />
              </div>

              {/* Números grandes */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <BigNumber
                  loading={predictLoading || !predict}
                  label="Frete total estimado"
                  value={predict ? brl(fretePorTon * peso, 0) : "—"}
                  sub={`por viagem (${peso} t)`}
                />
                <BigNumber
                  loading={predictLoading || !predict}
                  label="R$ por tonelada"
                  value={predict ? brl(fretePorTon) : "—"}
                  sub={predict ? `≈ ${brl(fretePorTon * 0.06)} / saca 60kg` : ""}
                  gold
                />
                <BigNumber
                  loading={predictLoading || !predict || !selectedRoute}
                  label="Tarifa por km"
                  value={
                    predict && selectedRoute
                      ? `R$ ${num(fretePorTon / selectedRoute.distancia_km, 3)}`
                      : "—"
                  }
                  sub={`Diesel ×${(diesel / 6.2).toFixed(2)} · Safra ×${SEASONALITY[mes].toFixed(2)}`}
                />
              </div>

              <Separator className="opacity-40" />

              {/* Tabs */}
              <Tabs defaultValue="previsao" className="w-full">
                <TabsList className="w-full">
                  <TabsTrigger value="previsao">Previsão 12 meses</TabsTrigger>
                  <TabsTrigger value="ranking">Ranking de rotas</TabsTrigger>
                  <TabsTrigger value="drivers">Fatores de preço</TabsTrigger>
                </TabsList>

                {/* -------------------- Previsão 12 meses -------------------- */}
                <TabsContent value="previsao" className="mt-4">
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold">
                      Evolução da tarifa (R$/km) —{" "}
                      {selectedRoute
                        ? `${selectedRoute.origem} → ${selectedRoute.destino}`
                        : "—"}
                    </h3>
                  </div>
                  {historyLoading || !history ? (
                    <Skeleton className="h-[280px] w-full rounded-lg" />
                  ) : previsaoWithRef.length === 0 ? (
                    <p className="py-16 text-center text-sm text-muted-foreground">
                      Sem série histórica para esta rota.
                    </p>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.4 }}
                    >
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart
                          data={previsaoWithRef}
                          margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(197,165,114,0.12)"
                            vertical={false}
                          />
                          <XAxis
                            dataKey="label"
                            tick={{ fill: "rgba(150,150,160,0.8)", fontSize: 11 }}
                            tickLine={false}
                            axisLine={{ stroke: "rgba(197,165,114,0.15)" }}
                          />
                          <YAxis
                            tick={{ fill: "rgba(150,150,160,0.8)", fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            width={48}
                            tickFormatter={(v) => num(Number(v), 2)}
                          />
                          <Tooltip
                            contentStyle={TOOLTIP_STYLE}
                            labelStyle={{ color: GOLD }}
                            formatter={(value, name) => [
                              `R$ ${num(Number(value), 3)}/km`,
                              name === "media" ? "Média histórica" : "Previsto",
                            ]}
                          />
                          <Legend
                            formatter={(v) => (v === "media" ? "Média histórica" : "Previsto")}
                            wrapperStyle={{ fontSize: 12 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="previsto"
                            name="previsto"
                            stroke={GOLD}
                            strokeWidth={2.5}
                            dot={{ r: 2.5, fill: GOLD }}
                            activeDot={{ r: 5 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="media"
                            name="media"
                            stroke={BLUE}
                            strokeWidth={1.75}
                            strokeDasharray="6 5"
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                      <p className="mt-2 text-xs italic text-muted-foreground">
                        Linha tracejada = média histórica de referência ({num(previsaoMean, 3)}{" "}
                        R$/km).
                      </p>
                    </motion.div>
                  )}
                </TabsContent>

                {/* ---------------------- Ranking de rotas ------------------- */}
                <TabsContent value="ranking" className="mt-4">
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold">Top rotas — {produtoLabel}</h3>
                    <p className="text-xs text-muted-foreground">
                      Custo total por tonelada nas principais rotas disponíveis.
                    </p>
                  </div>
                  {produtoRoutesLoading || !produtoRoutes ? (
                    <Skeleton className="h-[280px] w-full rounded-lg" />
                  ) : rankingData.length === 0 ? (
                    <p className="py-16 text-center text-sm text-muted-foreground">
                      Sem rotas para ranquear.
                    </p>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.4 }}
                    >
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart
                          data={rankingData}
                          layout="vertical"
                          margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(197,165,114,0.12)"
                            horizontal={false}
                          />
                          <XAxis
                            type="number"
                            tick={{ fill: "rgba(150,150,160,0.8)", fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(v) => num(Number(v), 0)}
                          />
                          <YAxis
                            type="category"
                            dataKey="name"
                            width={140}
                            tick={{ fill: "rgba(150,150,160,0.9)", fontSize: 10.5 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(v: string) =>
                              v.length > 22 ? `${v.slice(0, 21)}…` : v
                            }
                          />
                          <Tooltip
                            cursor={{ fill: "rgba(197,165,114,0.08)" }}
                            contentStyle={TOOLTIP_STYLE}
                            labelStyle={{ color: GOLD }}
                            formatter={(value) => [brl(Number(value)), "R$/t"]}
                          />
                          <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={26}>
                            {rankingData.map((_, i) => (
                              <Cell key={i} fill={i === 0 ? GOLD : "rgba(197,165,114,0.55)"} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </motion.div>
                  )}
                </TabsContent>

                {/* ---------------------- Drivers de preço ------------------- */}
                <TabsContent value="drivers" className="mt-4">
                  {predictLoading || !predict ? (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <Card key={i} className="gap-2 p-4">
                          <Skeleton className="h-4 w-32" />
                          <Skeleton className="h-3 w-full" />
                        </Card>
                      ))}
                    </div>
                  ) : predict.drivers.length === 0 ? (
                    <p className="py-16 text-center text-sm text-muted-foreground">
                      Sem fatores disponíveis.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {predict.drivers.map((d: Driver, i: number) => {
                        const share =
                          driverSum > 0
                            ? Math.round((Math.abs(d.shap_value) / driverSum) * 100)
                            : 0;
                        return (
                          <Card
                            key={`${d.feature}-${i}`}
                            className="edge-gold-top gap-2 p-4"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-semibold">
                                {driverLabel(d.feature)}
                              </span>
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 font-mono text-sm",
                                  d.direction === "up" ? "text-destructive" : "text-success",
                                )}
                              >
                                {d.direction === "up" ? (
                                  <ArrowUpRight className="size-3.5" />
                                ) : (
                                  <ArrowDownRight className="size-3.5" />
                                )}
                                {share}%
                              </span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                              <div
                                className="h-full rounded-full bg-gold"
                                style={{ width: `${share}%` }}
                              />
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {driverHint(d.feature)}
                            </p>
                          </Card>
                        );
                      })}
                    </div>
                  )}
                  {predict?.model_version && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Modelo {predict.model_version}
                    </p>
                  )}
                </TabsContent>
              </Tabs>
            </>
          )}
        </Card>
      </div>

      {/* ------------------------ Rotas monitoradas ---------------------------- */}
      <Card className="edge-gold-top mt-6 gap-4 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Rotas estratégicas monitoradas</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Principais corredores de originação.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={exportCsv}
            disabled={!produtoRoutes || produtoRoutes.length === 0}
          >
            <Download className="size-4" />
            Exportar CSV
          </Button>
        </div>

        {produtoRoutesLoading || !produtoRoutes ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : produtoRoutes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma rota disponível para {produtoLabel}.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rota</TableHead>
                <TableHead>Corredor</TableHead>
                <TableHead className="text-right">Distância</TableHead>
                <TableHead className="text-right">R$/km</TableHead>
                <TableHead className="text-right">R$/t</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {produtoRoutes.map((r) => (
                <TableRow key={r.route_id}>
                  <TableCell>
                    <div className="font-semibold">{r.origem}</div>
                    <div className="text-xs text-muted-foreground">→ {r.destino}</div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {r.corredor ?? "—"}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {num(r.distancia_km, 0)} km
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {num(r.r_per_ton_km, 3)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-gold">
                    {brl(r.frete_r_per_ton)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------ subcomponentes ----------------------------- */

function TendenciaBadge({
  loading,
  label,
  tone,
}: {
  loading: boolean;
  label: string;
  tone: "warning" | "success" | "muted";
}) {
  if (loading) return <Skeleton className="h-6 w-24 rounded-full" />;
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 capitalize",
        tone === "warning" && "border-warning/40 text-warning",
        tone === "success" && "border-success/40 text-success",
        tone === "muted" && "border-border text-muted-foreground",
      )}
    >
      <TrendingUp className="size-3.5" />
      Tendência {label}
    </Badge>
  );
}

function BigNumber({
  loading,
  label,
  value,
  sub,
  gold = false,
}: {
  loading: boolean;
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  gold?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10.5px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </div>
      {loading ? (
        <Skeleton className="h-8 w-28" />
      ) : (
        <div
          className={cn(
            "font-mono text-2xl font-semibold leading-none tracking-tight",
            gold && "text-gold",
          )}
        >
          {value}
        </div>
      )}
      {sub ? <div className="text-[11.5px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Dices, Play, Sparkles } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { ApiError, api, type SimulateResponse } from "@/lib/api";
import { brl, num } from "@/lib/format";

const GOLD = "#c5a572";

type ChartRow = { label: string; key: string; value: number };

export default function SimulacaoPage() {
  const [baseFreight, setBaseFreight] = useState<number>(200);
  const [iterations, setIterations] = useState<number>(2000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulateResponse | null>(null);

  async function runSimulation() {
    if (!Number.isFinite(baseFreight) || baseFreight <= 0) {
      toast.error("Informe um frete base válido (> 0).");
      return;
    }
    setLoading(true);
    try {
      const res = await api.simulate(baseFreight, iterations);
      setResult(res);
      toast.success(`Simulação concluída · ${num(res.iterations, 0)} iterações`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Falha ao rodar a simulação.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  const amplitude = result ? result.p90 - result.p10 : 0;

  const chartData: ChartRow[] = result
    ? [
        { label: "P10", key: "p10", value: result.p10 },
        { label: "Mediana", key: "p50", value: result.p50 },
        { label: "Média", key: "mean", value: result.mean },
        { label: "P90", key: "p90", value: result.p90 },
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Simulação Monte Carlo"
        subtitle="Estresse o frete base e veja a distribuição de cenários (p10 · mediana · p90)"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ------------------------------ Inputs ------------------------------ */}
        <Card className="edge-gold-top h-fit p-6 lg:col-span-1">
          <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-gold">
            <Dices className="size-3.5" />
            Parâmetros
          </div>
          <h3 className="mb-5 font-serif text-lg">Configurar cenário</h3>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void runSimulation();
            }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <Label htmlFor="base_freight">Frete base (R$/t)</Label>
              <Input
                id="base_freight"
                type="number"
                min={1}
                step={1}
                inputMode="decimal"
                className="font-mono"
                value={Number.isNaN(baseFreight) ? "" : baseFreight}
                onChange={(e) => setBaseFreight(e.target.valueAsNumber)}
              />
              <p className="text-[11.5px] text-muted-foreground">
                Valor de referência que será perturbado a cada iteração.
              </p>
            </div>

            <Separator className="bg-border" />

            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <Label htmlFor="iterations">Iterações</Label>
                <span className="font-mono text-sm text-gold">{num(iterations, 0)}</span>
              </div>
              <Slider
                id="iterations"
                min={100}
                max={10000}
                step={100}
                value={[iterations]}
                onValueChange={(v) => setIterations(v[0] ?? 100)}
                aria-label="Número de iterações"
              />
              <div className="flex justify-between text-[10.5px] text-muted-foreground">
                <span>100</span>
                <span>10.000</span>
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                "Rodando…"
              ) : (
                <>
                  <Play className="size-4" />
                  Rodar simulação
                </>
              )}
            </Button>
          </form>
        </Card>

        {/* ------------------------------ Results ------------------------------ */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {result ? (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="space-y-6"
              >
                {/* KPI row */}
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                  <KpiCard label="Mediana · p50" value={brl(result.p50)} gold hint="cenário central" />
                  <KpiCard label="Média" value={brl(result.mean)} hint="valor esperado" />
                  <KpiCard label="P10" value={brl(result.p10)} tone="up" hint="otimista" />
                  <KpiCard label="P90" value={brl(result.p90)} tone="down" hint="pessimista" />
                  <KpiCard
                    label="Amplitude"
                    value={brl(amplitude)}
                    hint="p90 − p10"
                  />
                </div>

                {/* Chart */}
                <Card className="p-6">
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-gold">
                        Distribuição · R$/t
                      </div>
                      <h3 className="font-serif text-lg">
                        Quantis sobre {num(result.iterations, 0)} iterações
                      </h3>
                    </div>
                  </div>

                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={chartData} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
                      <XAxis
                        dataKey="label"
                        tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
                        tickLine={false}
                        axisLine={{ stroke: "rgba(197,165,114,0.15)" }}
                      />
                      <YAxis
                        tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        width={48}
                        tickFormatter={(v) => `${Math.round(Number(v))}`}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(197,165,114,0.06)" }}
                        contentStyle={{
                          background: "#0e1424",
                          border: "1px solid rgba(197,165,114,0.3)",
                          borderRadius: 10,
                          color: "#fff",
                          fontSize: 12,
                        }}
                        labelStyle={{ color: GOLD }}
                        formatter={(value) => [brl(Number(value)), "R$/t"]}
                      />
                      <Bar dataKey="value" radius={[6, 6, 0, 0]} isAnimationActive maxBarSize={72}>
                        {chartData.map((row) => (
                          <Cell
                            key={row.key}
                            fill={GOLD}
                            fillOpacity={row.key === "p50" ? 1 : 0.55}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>

                  {result.note && (
                    <p className="mt-3 text-xs text-muted-foreground">{result.note}</p>
                  )}
                </Card>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="h-full"
              >
                <Card className="shadow-premium flex h-full min-h-[420px] flex-col items-center justify-center p-10 text-center">
                  <div className="mb-5 flex size-14 items-center justify-center rounded-full bg-secondary/60 ring-1 ring-gold/25">
                    <Sparkles className="size-6 text-gold" />
                  </div>
                  <h3 className="mb-2 font-serif text-xl text-gradient-gold">
                    Pronto para simular
                  </h3>
                  <p className="max-w-sm text-sm text-muted-foreground">
                    Defina o frete base e o número de iterações à esquerda e rode a
                    simulação de Monte Carlo para visualizar a distribuição de cenários
                    (p10, mediana e p90).
                  </p>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </>
  );
}

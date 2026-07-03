"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Dices, Droplet, Play, Scale, Sparkles, Wheat } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import useSWR from "swr";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { ApiError, api, type SimulateSegmentsResponse } from "@/lib/api";
import { brl, num } from "@/lib/format";

const GOLD = "#c5a572";

// produto -> segmento (espelha o backend).
const SEG_OF: Record<string, string> = {};
for (const p of ["ureia", "map", "kcl", "cloreto", "npk", "fertilizante", "nitrato"])
  SEG_OF[p] = "fertilizante";
for (const p of ["algodão", "algodao"]) SEG_OF[p] = "algodão";
for (const p of ["soja", "milho", "sorgo", "trigo", "grão", "grao"]) SEG_OF[p] = "grão";

const SEGMENTS = ["fertilizante", "algodão", "grão"] as const;
const SEG_LABEL: Record<string, string> = {
  fertilizante: "Fertilizante",
  algodão: "Algodão",
  grão: "Grão",
};

function signedPct(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export default function SimulacaoPage() {
  const [diesel, setDiesel] = useState(15); // %
  const [safra, setSafra] = useState(-10); // %
  const [piso, setPiso] = useState(5); // %
  const [iterations, setIterations] = useState(5000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulateSegmentsResponse | null>(null);

  // Bases por segmento = média do frete atual das rotas de cada segmento (ranking).
  const { data: routes } = useSWR("routes", () => api.getRoutes());
  const bases = useMemo(() => {
    const acc: Record<string, { sum: number; n: number }> = {};
    for (const r of routes ?? []) {
      const seg = SEG_OF[r.produto.trim().toLowerCase()];
      if (!seg) continue;
      acc[seg] ??= { sum: 0, n: 0 };
      acc[seg].sum += r.frete_r_per_ton;
      acc[seg].n += 1;
    }
    const defaults: Record<string, number> = {
      fertilizante: 320,
      algodão: 280,
      grão: 300,
    };
    return SEGMENTS.map((segment) => ({
      segment,
      base_freight: acc[segment]?.n ? acc[segment].sum / acc[segment].n : defaults[segment],
    }));
  }, [routes]);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.simulateSegments({
        diesel_pct: diesel / 100,
        safra_pct: safra / 100,
        piso_pct: piso / 100,
        iterations,
        bases,
      });
      setResult(res);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Falha ao rodar a simulação.");
    } finally {
      setLoading(false);
    }
  }, [diesel, safra, piso, iterations, bases]);

  // roda uma vez quando as bases carregam
  const basesReady = (routes?.length ?? 0) > 0;
  useEffect(() => {
    if (basesReady && !result) void runSimulation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basesReady]);

  const chartData = result
    ? result.segments.map((s) => ({
        segment: SEG_LABEL[s.segment] ?? s.segment,
        p10: s.p10,
        p50: s.p50,
        p90: s.p90,
      }))
    : [];

  return (
    <>
      <PageHeader
        title="Simulação Monte Carlo"
        subtitle="Estresse os drivers do agro (diesel · safra · piso ANTT) e veja o risco de frete por segmento"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ------------------------------ Drivers ------------------------------ */}
        <Card className="edge-gold-top h-fit p-6 lg:col-span-1">
          <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-gold">
            <Dices className="size-3.5" />
            Premissas de mercado
          </div>
          <h3 className="mb-5 text-lg font-medium">Configurar cenário</h3>

          <div className="space-y-6">
            <DriverSlider
              icon={<Droplet className="size-3.5" />}
              label="Diesel"
              value={diesel}
              min={-10}
              max={30}
              onChange={setDiesel}
              onCommit={runSimulation}
              hint="Combustível é custo direto — pesa em todos os segmentos."
            />
            <DriverSlider
              icon={<Wheat className="size-3.5" />}
              label="Safra"
              value={safra}
              min={-25}
              max={5}
              onChange={setSafra}
              onCommit={runSimulation}
              hint="Volume de safra move a demanda de frete — forte nos grãos."
            />
            <DriverSlider
              icon={<Scale className="size-3.5" />}
              label="Piso ANTT"
              value={piso}
              min={0}
              max={15}
              onChange={setPiso}
              onCommit={runSimulation}
              hint="Revisão do piso regulatório — só empurra o frete para cima."
            />

            <Separator className="bg-border" />

            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <Label>Iterações</Label>
                <span className="font-mono text-sm text-gold">{num(iterations, 0)}</span>
              </div>
              <Slider
                min={500}
                max={20000}
                step={500}
                value={[iterations]}
                onValueChange={(v) => setIterations(v[0] ?? 5000)}
                onValueCommit={() => void runSimulation()}
                aria-label="Número de iterações"
              />
            </div>

            <Button className="w-full" disabled={loading} onClick={() => void runSimulation()}>
              {loading ? (
                "Rodando…"
              ) : (
                <>
                  <Play className="size-4" />
                  Rodar simulação
                </>
              )}
            </Button>
          </div>
        </Card>

        {/* ------------------------------ Resultados ------------------------------ */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {result ? (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                className="space-y-6"
              >
                {/* premissas ativas */}
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="border-gold/40 text-gold">
                    Diesel {signedPct(diesel)}
                  </Badge>
                  <Badge variant="outline" className="border-gold/40 text-gold">
                    Safra {signedPct(safra)}
                  </Badge>
                  <Badge variant="outline" className="border-gold/40 text-gold">
                    Piso ANTT {signedPct(piso)}
                  </Badge>
                  <Badge variant="secondary" className="text-muted-foreground">
                    {num(result.iterations, 0)} iterações
                  </Badge>
                </div>

                {/* cards por segmento */}
                <div className="grid gap-4 sm:grid-cols-3">
                  {result.segments.map((s) => {
                    const up = s.delta_pct >= 0;
                    return (
                      <Card key={s.segment} className="p-5">
                        <div className="text-[10.5px] uppercase tracking-[0.18em] text-gold">
                          {SEG_LABEL[s.segment] ?? s.segment}
                        </div>
                        <div className="mt-1 flex items-baseline gap-2">
                          <span className="text-2xl font-semibold text-gold">{brl(s.mean)}</span>
                          <span
                            className={`font-mono text-xs ${up ? "text-warning" : "text-success"}`}
                          >
                            {signedPct(s.delta_pct)}
                          </span>
                        </div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          base {brl(s.base_freight)}
                        </div>
                        <Separator className="my-3 bg-border" />
                        <div className="grid grid-cols-3 gap-1 text-center">
                          <div>
                            <div className="font-mono text-sm text-success">{brl(s.p10)}</div>
                            <div className="text-[9.5px] uppercase tracking-wider text-muted-foreground">
                              P10
                            </div>
                          </div>
                          <div>
                            <div className="font-mono text-sm">{brl(s.p50)}</div>
                            <div className="text-[9.5px] uppercase tracking-wider text-muted-foreground">
                              P50
                            </div>
                          </div>
                          <div>
                            <div className="font-mono text-sm text-warning">{brl(s.p90)}</div>
                            <div className="text-[9.5px] uppercase tracking-wider text-muted-foreground">
                              P90
                            </div>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>

                {/* comparação de bandas por segmento */}
                <Card className="p-6">
                  <div className="mb-4">
                    <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-gold">
                      Banda de frete · R$/t
                    </div>
                    <h3 className="text-lg font-medium">P10 · mediana · P90 por segmento</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={chartData} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
                      <XAxis
                        dataKey="segment"
                        tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                        tickLine={false}
                        axisLine={{ stroke: "rgba(197,165,114,0.15)" }}
                      />
                      <YAxis
                        tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        width={48}
                        tickFormatter={(v) => `${Math.round(Number(v))}`}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(197,165,114,0.06)" }}
                        contentStyle={{
                          background: "var(--popover)",
                          border: "1px solid rgba(197,165,114,0.3)",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                        labelStyle={{ color: GOLD }}
                        formatter={(value, name) => [brl(Number(value)), String(name).toUpperCase()]}
                      />
                      <Bar dataKey="p10" radius={[4, 4, 0, 0]} maxBarSize={40} fill={GOLD} fillOpacity={0.4} />
                      <Bar dataKey="p50" radius={[4, 4, 0, 0]} maxBarSize={40} fill={GOLD} fillOpacity={0.85}>
                        {chartData.map((row) => (
                          <Cell key={row.segment} />
                        ))}
                      </Bar>
                      <Bar dataKey="p90" radius={[4, 4, 0, 0]} maxBarSize={40} fill={GOLD} fillOpacity={0.55} />
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="mt-3 text-xs text-muted-foreground">
                    Cada segmento reage de forma própria: grãos são mais sensíveis à safra;
                    fertilizante, ao diesel. Piso ANTT amortece a queda (frete não cai indefinidamente).
                  </p>
                </Card>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
                className="h-full"
              >
                <Card className="shadow-premium flex h-full min-h-[420px] flex-col items-center justify-center p-10 text-center">
                  <div className="mb-5 flex size-14 items-center justify-center rounded-full bg-secondary/60 ring-1 ring-gold/25">
                    <Sparkles className="size-6 text-gold" />
                  </div>
                  <h3 className="text-gradient-gold mb-2 text-xl font-medium">
                    Estressando os cenários…
                  </h3>
                  <p className="max-w-sm text-sm text-muted-foreground">
                    Ajuste diesel, safra e piso ANTT à esquerda para ver a distribuição de frete
                    de cada segmento do agro.
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

function DriverSlider({
  icon,
  label,
  value,
  min,
  max,
  onChange,
  onCommit,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  onCommit: () => void;
  hint: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label className="flex items-center gap-1.5 text-gold/90">
          {icon}
          {label}
        </Label>
        <span className="font-mono text-sm text-gold">{signedPct(value)}</span>
      </div>
      <Slider
        min={min}
        max={max}
        step={1}
        value={[value]}
        onValueChange={(v) => onChange(v[0] ?? 0)}
        onValueCommit={() => onCommit()}
        aria-label={label}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{signedPct(min)}</span>
        <span>{signedPct(max)}</span>
      </div>
      <p className="text-[11px] leading-snug text-muted-foreground">{hint}</p>
    </div>
  );
}

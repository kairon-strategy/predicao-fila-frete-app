"use client";

import { AlertTriangle, ArrowRight, Bell, Info, TrendingUp } from "lucide-react";
import Link from "next/link";
import useSWR from "swr";

import { FreightAreaChart } from "@/components/charts/freight-area-chart";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { brl, num, pct } from "@/lib/format";

function firstNameFromEmail(email?: string): string {
  if (!email) return "";
  const local = email.split("@")[0].split(/[._+-]/)[0];
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : "";
}

const sevTone: Record<string, string> = {
  critical: "text-destructive",
  warn: "text-warning",
  info: "text-info",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const nome = user?.name ? user.name.split(" ")[0] : firstNameFromEmail(user?.email);
  const { data: routes, isLoading: loadingRoutes } = useSWR("routes", () => api.getRoutes());
  const { data: alerts } = useSWR("alerts-active", () => api.getAlerts());

  const top = routes && routes.length ? [...routes].sort((a, b) => b.frete_r_per_ton - a.frete_r_per_ton) : [];
  const featured = top[0];
  const featuredId = featured?.route_id ?? null;
  const { data: history } = useSWR(
    featuredId ? ["history", featuredId] : null,
    () => api.getRouteHistory(featuredId as string, 12),
  );

  const avgFrete = routes?.length
    ? routes.reduce((s, r) => s + r.frete_r_per_ton, 0) / routes.length
    : 0;
  const biggestRise = routes?.length
    ? [...routes].sort((a, b) => b.var_30d_pct - a.var_30d_pct)[0]
    : undefined;

  return (
    <>
      <PageHeader title={<>Olá, <span className="text-gradient-gold">{nome || "bem-vindo"}</span>.</>} subtitle="Visão geral da operação">
        <Button asChild>
          <Link href="/consulta">Nova consulta <ArrowRight className="size-4" /></Link>
        </Button>
      </PageHeader>

      {/* KPIs */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Rotas monitoradas" value={loadingRoutes ? "…" : (routes?.length ?? 0)} hint="fertilizante + algodão + grão" />
        <KpiCard label="Frete médio" value={loadingRoutes ? "…" : brl(avgFrete)} gold hint="por tonelada" />
        <KpiCard
          label="Alertas ativos"
          value={alerts?.length ?? 0}
          gold={!!alerts?.length}
          tone={alerts?.length ? "down" : "muted"}
          hint={alerts?.length ? "requer atenção" : "tudo tranquilo"}
        />
        <KpiCard
          label="Maior alta · 30d"
          value={biggestRise ? pct(biggestRise.var_30d_pct) : "—"}
          tone="down"
          hint={biggestRise ? `${biggestRise.origem} → ${biggestRise.destino}` : ""}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Featured chart */}
        <Card className="p-6 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-gold">
                Rota em destaque · R$/t · 12 meses
              </div>
              <h3 className="font-serif text-lg">
                {featured ? `${featured.origem} → ${featured.destino}` : "—"}
              </h3>
            </div>
            {featured && <Badge variant="outline" className="border-gold/40 text-gold">{featured.produto}</Badge>}
          </div>
          {history ? (
            <FreightAreaChart
              data={history.points.map((p) => ({
                label: p.month.slice(5),
                value: p.frete_r_per_ton,
                low: p.banda_p10,
                high: p.banda_p90,
              }))}
              height={280}
            />
          ) : (
            <Skeleton className="h-[280px] w-full" />
          )}
        </Card>

        {/* Recent alerts */}
        <Card className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-serif text-lg">Alertas recentes</h3>
            <Link href="/alertas" className="text-xs text-gold hover:underline">
              ver todos
            </Link>
          </div>
          <div className="space-y-3">
            {alerts === undefined && <Skeleton className="h-24 w-full" />}
            {alerts?.length === 0 && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Nenhum alerta ativo.
              </div>
            )}
            {alerts?.slice(0, 4).map((a) => {
              const Icon = a.severity === "critical" ? AlertTriangle : a.severity === "warn" ? Bell : Info;
              return (
                <div key={a.id} className="flex gap-3 rounded-lg border border-border bg-secondary/40 p-3">
                  <Icon className={`mt-0.5 size-4 shrink-0 ${sevTone[a.severity]}`} />
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{a.title}</div>
                    <div className="mt-0.5 line-clamp-3 text-xs text-muted-foreground">{a.body}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Top routes */}
      <Card className="mt-6 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-serif text-lg">Rotas mais caras</h3>
          <Link href="/ranking" className="text-xs text-gold hover:underline">
            ranking completo <TrendingUp className="inline size-3" />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase tracking-[0.14em] text-gold">
                <th className="pb-2 pr-4 font-semibold">Rota</th>
                <th className="pb-2 pr-4 font-semibold">Produto</th>
                <th className="pb-2 pr-4 text-right font-semibold">R$/t</th>
                <th className="pb-2 pr-4 text-right font-semibold">R$/t·km</th>
                <th className="pb-2 text-right font-semibold">Var 30d</th>
              </tr>
            </thead>
            <tbody>
              {top.slice(0, 6).map((r) => (
                <tr key={r.route_id} className="border-b border-border/50">
                  <td className="py-2.5 pr-4">
                    <span className="font-medium">{r.origem}</span>
                    <span className="text-muted-foreground"> → {r.destino}</span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
                      {r.produto}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-gold">{brl(r.frete_r_per_ton)}</td>
                  <td className="py-2.5 pr-4 text-right font-mono text-muted-foreground">
                    {num(r.r_per_ton_km, 3)}
                  </td>
                  <td className={`py-2.5 text-right font-mono ${r.var_30d_pct >= 0 ? "text-warning" : "text-success"}`}>
                    {pct(r.var_30d_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

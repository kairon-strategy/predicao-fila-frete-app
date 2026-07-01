"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Info,
  Loader2,
  RadarIcon,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import useSWR, { mutate } from "swr";

import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError, type Alert } from "@/lib/api";
import { cn } from "@/lib/utils";

type Severity = Alert["severity"];
type Status = Alert["status"];

const ALL = "all";

const sevMeta: Record<
  Severity,
  { label: string; text: string; border: string; ring: string; Icon: typeof Info }
> = {
  critical: {
    label: "Crítico",
    text: "text-destructive",
    border: "border-l-destructive",
    ring: "bg-destructive/10 ring-destructive/20",
    Icon: AlertTriangle,
  },
  warn: {
    label: "Aviso",
    text: "text-warning",
    border: "border-l-warning",
    ring: "bg-warning/10 ring-warning/20",
    Icon: Bell,
  },
  info: {
    label: "Info",
    text: "text-info",
    border: "border-l-info",
    ring: "bg-info/10 ring-info/20",
    Icon: Info,
  },
};

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AlertasPage() {
  const [severity, setSeverity] = useState<Severity | typeof ALL>(ALL);
  const [status, setStatus] = useState<Status>("active");
  const [detecting, setDetecting] = useState(false);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const sevParam = severity === ALL ? undefined : severity;
  const swrKey = ["alerts", severity, status] as const;

  const {
    data: alerts,
    isLoading,
    error,
  } = useSWR<Alert[]>(swrKey, () => api.getAlerts(sevParam, undefined, status), {
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : "Falha ao carregar alertas.";
      toast.error(msg);
    },
  });

  const feed = alerts ?? [];
  const counts = {
    total: feed.length,
    critical: feed.filter((a) => a.severity === "critical").length,
    warn: feed.filter((a) => a.severity === "warn").length,
    info: feed.filter((a) => a.severity === "info").length,
  };

  async function handleDetect() {
    setDetecting(true);
    try {
      const res = await api.detectAlerts();
      if (res.created > 0) {
        toast.success(
          `${res.created} ${res.created === 1 ? "novo alerta" : "novos alertas"} detectado${
            res.created === 1 ? "" : "s"
          }.`,
          { description: res.detail },
        );
      } else {
        toast.info("Nenhum alerta novo.", { description: res.detail });
      }
      await mutate(swrKey);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Sem permissão", {
          description: "Seu perfil (viewer) não pode disparar a detecção.",
        });
      } else {
        toast.error(err instanceof ApiError ? err.message : "Falha ao detectar alertas.");
      }
    } finally {
      setDetecting(false);
    }
  }

  async function handleResolve(id: number) {
    setResolvingId(id);
    try {
      await api.resolveAlert(id);
      toast.success("Alerta resolvido.");
      await mutate(swrKey);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error("Sem permissão", {
          description: "Seu perfil (viewer) não pode resolver alertas.",
        });
      } else {
        toast.error(err instanceof ApiError ? err.message : "Falha ao resolver alerta.");
      }
    } finally {
      setResolvingId(null);
    }
  }

  const showEmpty = !isLoading && !error && feed.length === 0;

  return (
    <>
      <PageHeader
        title="Alertas"
        subtitle="Detecção de mudanças que impactam o frete (diesel, e futuramente ANTT/CONAB)"
      >
        <Button onClick={handleDetect} disabled={detecting}>
          {detecting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <RadarIcon className="size-4" />
          )}
          {detecting ? "Detectando…" : "Detectar agora"}
        </Button>
      </PageHeader>

      {/* KPIs */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Alertas ativos"
          value={isLoading ? "…" : counts.total}
          gold={counts.total > 0}
          hint={status === "active" ? "no feed atual" : "resolvidos no feed"}
        />
        <KpiCard
          label="Críticos"
          value={isLoading ? "…" : counts.critical}
          tone="down"
          hint={counts.critical ? "requer atenção imediata" : "nenhum crítico"}
        />
        <KpiCard
          label="Avisos"
          value={isLoading ? "…" : counts.warn}
          hint="monitorar tendência"
        />
        <KpiCard
          label="Informativos"
          value={isLoading ? "…" : counts.info}
          hint="contexto de mercado"
        />
      </div>

      {/* Filters */}
      <Card className="glass mb-6 flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
            Severidade
          </span>
          <Select
            value={severity}
            onValueChange={(v) => setSeverity(v as Severity | typeof ALL)}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Todas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todas</SelectItem>
              <SelectItem value="critical">Crítico</SelectItem>
              <SelectItem value="warn">Aviso</SelectItem>
              <SelectItem value="info">Info</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Tabs value={status} onValueChange={(v) => setStatus(v as Status)}>
          <TabsList>
            <TabsTrigger value="active">Ativos</TabsTrigger>
            <TabsTrigger value="resolved">Resolvidos</TabsTrigger>
          </TabsList>
        </Tabs>
      </Card>

      {/* Feed */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="border-l-4 border-l-border p-4">
              <div className="flex gap-4">
                <Skeleton className="size-10 shrink-0 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : showEmpty ? (
        <Card className="edge-gold-top shadow-premium flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-success/10 ring-1 ring-success/20">
            <ShieldCheck className="size-7 text-success" />
          </div>
          <h3 className="font-serif text-xl">
            {status === "active"
              ? "Nenhum alerta ativo — tudo sob controle."
              : "Nenhum alerta resolvido por aqui."}
          </h3>
          <p className="max-w-md text-sm text-muted-foreground">
            {status === "active"
              ? "O monitoramento está de olho no diesel e nos indicadores de mercado. Você será avisado assim que algo mudar."
              : "Alertas resolvidos aparecerão neste histórico."}
          </p>
          {status === "active" && (
            <Button variant="outline" onClick={handleDetect} disabled={detecting} className="mt-1">
              {detecting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RadarIcon className="size-4" />
              )}
              Rodar detecção
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-3">
          <AnimatePresence initial={false}>
            {feed.map((a) => {
              const meta = sevMeta[a.severity];
              const { Icon } = meta;
              const created = formatDate(a.created_at);
              const isResolving = resolvingId === a.id;
              return (
                <motion.div
                  key={a.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card
                    className={cn(
                      "shadow-premium border-l-4 p-4 transition-colors",
                      meta.border,
                      a.status === "resolved" && "opacity-70",
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className={cn(
                          "mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full ring-1",
                          meta.ring,
                        )}
                      >
                        <Icon className={cn("size-5", meta.text)} />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{a.title}</span>
                          <Badge
                            variant="outline"
                            className={cn("border-current/30 text-[10px] uppercase tracking-wide", meta.text)}
                          >
                            {meta.label}
                          </Badge>
                        </div>

                        <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{a.body}</p>

                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
                          <span className="rounded-full bg-secondary px-2 py-0.5 font-mono">
                            {a.alert_type}
                          </span>
                          {a.entity_id && (
                            <span className="font-mono text-gold/80">{a.entity_id}</span>
                          )}
                          {created && <span>{created}</span>}
                        </div>
                      </div>

                      <div className="shrink-0 self-center">
                        {a.status === "active" ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleResolve(a.id)}
                            disabled={isResolving}
                          >
                            {isResolving ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <CheckCircle2 className="size-4" />
                            )}
                            Resolver
                          </Button>
                        ) : (
                          <Badge variant="secondary" className="gap-1 text-muted-foreground">
                            <CheckCircle2 className="size-3.5" />
                            resolvido
                          </Badge>
                        )}
                      </div>
                    </div>
                  </Card>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </>
  );
}

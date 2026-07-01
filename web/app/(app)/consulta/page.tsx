"use client";

import { useState, useTransition } from "react";
import { motion } from "framer-motion";
import {
  Sparkles,
  TrendingUp,
  Loader2,
  Send,
  Package,
  MapPin,
  Calendar,
  Weight,
  Bot,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api, ApiError } from "@/lib/api";
import type { PredictResponse, ExplainResponse } from "@/lib/api";
import { brl } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRODUTOS = [
  { value: "ureia", label: "Ureia" },
  { value: "MAP", label: "MAP" },
  { value: "KCl", label: "KCl" },
  { value: "NPK", label: "NPK" },
  { value: "algodão", label: "Algodão" },
];

function todayPlus30(): string {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().slice(0, 10);
}

export default function ConsultaPage() {
  const [origem, setOrigem] = useState("Sinop-MT");
  const [destino, setDestino] = useState("Sorriso-MT");
  const [produto, setProduto] = useState("ureia");
  const [data, setData] = useState<string>(todayPlus30());
  const [cargaTon, setCargaTon] = useState<string>("30");

  const [result, setResult] = useState<PredictResponse | null>(null);
  const [predictionId, setPredictionId] = useState<string | null>(null);
  const [isPredicting, startPredict] = useTransition();

  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [question, setQuestion] = useState("");

  const carga = Number(cargaTon) || 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    startPredict(async () => {
      try {
        const payload = {
          origem: origem.trim(),
          destino: destino.trim(),
          produto,
          data,
          carga_ton: carga > 0 ? carga : null,
        };
        const res = await api.predict(payload);
        setResult(res);
        setPredictionId(res.prediction_id);
        setExplanation(null);
        void fetchExplanation(res.prediction_id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          toast.error("Seu papel (viewer) não pode gerar cotações");
          return;
        }
        toast.error(err instanceof ApiError ? err.message : "Erro");
      }
    });
  }

  async function fetchExplanation(id: string, q?: string) {
    setExplaining(true);
    try {
      const res = await api.explain(id, q);
      setExplanation(res);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Erro");
    } finally {
      setExplaining(false);
    }
  }

  function handleAsk() {
    if (!predictionId) return;
    const q = question.trim();
    void fetchExplanation(predictionId, q.length ? q : undefined);
  }

  return (
    <div>
      <PageHeader
        title="Nova consulta"
        subtitle="Cotação instantânea · baseline + LightGBM + banda + SHAP"
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ------------------------------- FORM ------------------------------- */}
        <div className="lg:col-span-1">
          <Card className="edge-gold-top shadow-premium sticky top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-serif text-lg">
                <Sparkles className="size-4 text-gold" />
                Parâmetros
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="grid gap-2">
                  <Label htmlFor="origem" className="flex items-center gap-1.5">
                    <MapPin className="size-3.5 text-muted-foreground" />
                    Origem
                  </Label>
                  <Input
                    id="origem"
                    value={origem}
                    onChange={(e) => setOrigem(e.target.value)}
                    placeholder="Cidade-UF"
                    required
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="destino" className="flex items-center gap-1.5">
                    <MapPin className="size-3.5 text-muted-foreground" />
                    Destino
                  </Label>
                  <Input
                    id="destino"
                    value={destino}
                    onChange={(e) => setDestino(e.target.value)}
                    placeholder="Cidade-UF"
                    required
                  />
                </div>

                <div className="grid gap-2">
                  <Label className="flex items-center gap-1.5">
                    <Package className="size-3.5 text-muted-foreground" />
                    Produto
                  </Label>
                  <Select value={produto} onValueChange={setProduto}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Selecione" />
                    </SelectTrigger>
                    <SelectContent>
                      {PRODUTOS.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="data" className="flex items-center gap-1.5">
                    <Calendar className="size-3.5 text-muted-foreground" />
                    Data
                  </Label>
                  <Input
                    id="data"
                    type="date"
                    value={data}
                    onChange={(e) => setData(e.target.value)}
                    required
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="carga" className="flex items-center gap-1.5">
                    <Weight className="size-3.5 text-muted-foreground" />
                    Carga (toneladas)
                  </Label>
                  <Input
                    id="carga"
                    type="number"
                    min={0}
                    step="0.1"
                    value={cargaTon}
                    onChange={(e) => setCargaTon(e.target.value)}
                  />
                </div>

                <Separator className="bg-border" />

                <Button
                  type="submit"
                  disabled={isPredicting}
                  className="w-full font-medium"
                >
                  {isPredicting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Prevendo…
                    </>
                  ) : (
                    <>
                      <TrendingUp className="size-4" />
                      Prever frete
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* ------------------------------ RESULT ------------------------------ */}
        <div className="lg:col-span-2">
          {!result ? (
            <EmptyState />
          ) : (
            <ResultView
              result={result}
              carga={carga}
              explanation={explanation}
              explaining={explaining}
              question={question}
              setQuestion={setQuestion}
              onAsk={handleAsk}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function EmptyState() {
  return (
    <Card className="flex min-h-[420px] items-center justify-center border-dashed">
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="glass flex size-16 items-center justify-center rounded-2xl">
          <TrendingUp className="size-7 text-gold" />
        </div>
        <div className="max-w-xs space-y-1">
          <p className="font-serif text-lg">Pronto para cotar</p>
          <p className="text-sm text-muted-foreground">
            Preencha os parâmetros e clique em Prever frete
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function ResultView({
  result,
  carga,
  explanation,
  explaining,
  question,
  setQuestion,
  onAsk,
}: {
  result: PredictResponse;
  carga: number;
  explanation: ExplainResponse | null;
  explaining: boolean;
  question: string;
  setQuestion: (v: string) => void;
  onAsk: () => void;
}) {
  const { frete_r_per_ton, banda_p10, banda_p90, model_version, drivers } = result;

  // posição do valor central dentro da banda p10–p90 (0–100%)
  const span = Math.max(banda_p90 - banda_p10, 1e-9);
  const centerPct = Math.min(
    100,
    Math.max(0, ((frete_r_per_ton - banda_p10) / span) * 100),
  );

  const total = carga > 0 ? frete_r_per_ton * carga : null;
  const maxAbs = Math.max(...drivers.map((d) => Math.abs(d.shap_value)), 1e-9);

  return (
    <motion.div
      key={result.prediction_id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="space-y-6"
    >
      {/* HERO */}
      <Card className="edge-gold-top glass-gold shadow-premium overflow-hidden">
        <CardContent className="p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
                Frete previsto
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-gradient-gold font-serif text-5xl leading-none">
                  {brl(frete_r_per_ton)}
                </span>
                <span className="text-sm text-muted-foreground">/tonelada</span>
              </div>
            </div>
            <Badge variant="outline" className="border-border text-muted-foreground">
              {model_version}
            </Badge>
          </div>

          {/* BANDA DE CONFIANÇA */}
          <div className="mt-7 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>Banda de confiança</span>
              <span>p10 – p90</span>
            </div>
            <div className="relative h-3 w-full overflow-visible rounded-full bg-muted">
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{
                  width: "100%",
                  background:
                    "linear-gradient(90deg, color-mix(in srgb, var(--gold) 30%, transparent), var(--gold), color-mix(in srgb, var(--gold) 30%, transparent))",
                }}
              />
              {/* marcador do valor central */}
              <div
                className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-gold shadow-premium"
                style={{ left: `${centerPct}%` }}
                title={brl(frete_r_per_ton)}
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-foreground">{brl(banda_p10)}</span>
              <span className="font-medium text-foreground">{brl(banda_p90)}</span>
            </div>
          </div>

          {total !== null && (
            <>
              <Separator className="my-6 bg-border" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
                  Total da carga · {carga} t
                </div>
                <div className="font-serif text-2xl text-gold">{brl(total)}</div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* DRIVERS (SHAP) */}
      <Card className="shadow-premium">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-serif text-lg">
            <Sparkles className="size-4 text-gold" />
            Drivers (SHAP)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {drivers.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem drivers disponíveis.</p>
          ) : (
            <div className="space-y-4">
              {drivers.map((d) => {
                const width = (Math.abs(d.shap_value) / maxAbs) * 100;
                const isUp = d.direction === "up";
                return (
                  <div key={d.feature} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-foreground">{d.feature}</span>
                      <span
                        className={cn(
                          "tabular-nums font-medium",
                          isUp ? "text-gold" : "text-info",
                        )}
                      >
                        {isUp ? "+" : "−"}
                        {Math.abs(d.shap_value).toFixed(2)}
                      </span>
                    </div>
                    <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                      <motion.div
                        className="h-full rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${width}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                        style={{
                          background: isUp ? "var(--gold)" : "var(--info)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* COPILOTO */}
      <Card className="edge-gold-top shadow-premium">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-serif text-lg">
            <Bot className="size-4 text-gold" />
            Copiloto
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Pergunte ao copiloto sobre esta cotação"
              className="min-h-[44px] flex-1 resize-none"
              rows={2}
            />
            <Button
              onClick={onAsk}
              disabled={explaining}
              className="sm:self-stretch"
            >
              {explaining ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
              Perguntar
            </Button>
          </div>

          {explaining && !explanation ? (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Consultando o copiloto…
            </div>
          ) : explanation ? (
            <motion.div
              key={explanation.explanation}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.35 }}
              className="glass space-y-3 rounded-xl border border-border p-5"
            >
              <p className="text-sm leading-relaxed whitespace-pre-line text-foreground">
                {explanation.explanation}
              </p>
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <ArrowRight className="size-3 text-gold" />
                Fonte:{" "}
                <span className="font-medium text-gold">
                  {explanation.source === "llm" ? "Claude" : "Template"}
                </span>
              </div>
            </motion.div>
          ) : null}
        </CardContent>
      </Card>
    </motion.div>
  );
}

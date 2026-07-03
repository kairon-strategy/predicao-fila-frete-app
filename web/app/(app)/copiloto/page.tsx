"use client";

import { AnimatePresence, motion } from "framer-motion";
import { MapPin, Send, Shield, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api, type PredictResponse } from "@/lib/api";
import { brl } from "@/lib/format";
import { cn } from "@/lib/utils";

type MsgSource = "llm" | "template";

type ChatMessage = {
  id: string;
  role: "bot" | "user";
  text: string;
  source?: MsgSource;
};

const PRODUTOS = ["ureia", "MAP", "KCl", "NPK", "algodão"] as const;

const SUGGESTIONS = [
  "Por que o frete está nesse nível?",
  "O que mais pesa nessa rota?",
  "Como a sazonalidade afeta?",
] as const;

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function plus30Days(): string {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().slice(0, 10);
}

function sourceCaption(source: MsgSource | undefined): string {
  if (source === "llm") return "Claude";
  if (source === "template")
    return "Template · defina ANTHROPIC_API_KEY para o copiloto completo";
  return "";
}

export default function CopilotoPage() {
  const [origem, setOrigem] = useState("Sinop-MT");
  const [destino, setDestino] = useState("Sorriso-MT");
  const [produto, setProduto] = useState<string>("ureia");
  const [data, setData] = useState<string>(plus30Days);

  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [typing, setTyping] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // smooth scroll to bottom on new message / typing indicator
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typing]);

  const chatEnabled = !!prediction && !loadingQuote;

  async function handleLoadQuote() {
    if (loadingQuote) return;
    setLoadingQuote(true);
    setTyping(false);
    try {
      const pred = await api.predict({
        origem: origem.trim(),
        destino: destino.trim(),
        produto,
        data,
        carga_ton: null,
      });
      setPrediction(pred);
      setMessages([]);
      toast.success("Cotação carregada. Pode conversar com o copiloto.");

      // auto first bot message = default explanation
      setTyping(true);
      try {
        const exp = await api.explain(pred.prediction_id);
        setMessages([
          {
            id: makeId(),
            role: "bot",
            text: exp.explanation,
            source: exp.source,
          },
        ]);
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "Falha ao carregar a explicação.";
        toast.error(msg);
      } finally {
        setTyping(false);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        toast.error(
          "Seu perfil não tem permissão para gerar cotações. Fale com um administrador.",
        );
      } else {
        const msg =
          err instanceof ApiError ? err.message : "Não foi possível carregar a cotação.";
        toast.error(msg);
      }
    } finally {
      setLoadingQuote(false);
    }
  }

  async function sendQuestion(raw: string) {
    const q = raw.trim();
    if (!q || !prediction || typing) return;

    setQuestion("");
    setMessages((prev) => [...prev, { id: makeId(), role: "user", text: q }]);
    setTyping(true);
    try {
      const exp = await api.explain(prediction.prediction_id, q);
      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: "bot", text: exp.explanation, source: exp.source },
      ]);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Não foi possível responder agora.";
      toast.error(msg);
    } finally {
      setTyping(false);
    }
  }

  return (
    <>
      <PageHeader
        title={
          <>
            Copiloto <span className="text-gradient-gold italic">Kairon</span>
          </>
        }
        subtitle="Claude Sonnet · sempre ancorado em dados · explica, nunca prevê"
      />

      {/* CONTEXT SETUP */}
      <Card className="edge-gold-top mb-6 p-5 shadow-premium">
        <div className="mb-4 flex items-center gap-2">
          <Sparkles className="size-4 text-gold" />
          <h2 className="font-serif text-lg">Contexto da conversa</h2>
        </div>

        <div className="grid gap-4 md:grid-cols-5">
          <div className="space-y-1.5">
            <Label htmlFor="origem" className="text-xs text-muted-foreground">
              Origem
            </Label>
            <Input
              id="origem"
              value={origem}
              onChange={(e) => setOrigem(e.target.value)}
              placeholder="Sinop-MT"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="destino" className="text-xs text-muted-foreground">
              Destino
            </Label>
            <Input
              id="destino"
              value={destino}
              onChange={(e) => setDestino(e.target.value)}
              placeholder="Sorriso-MT"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Produto</Label>
            <Select value={produto} onValueChange={setProduto}>
              <SelectTrigger className="w-full">
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
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="data" className="text-xs text-muted-foreground">
              Data
            </Label>
            <Input
              id="data"
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              className="w-full"
              onClick={handleLoadQuote}
              disabled={loadingQuote || !origem.trim() || !destino.trim()}
            >
              {loadingQuote ? "Carregando…" : "Carregar cotação"}
            </Button>
          </div>
        </div>

        {/* summary chip */}
        {prediction && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-gold mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border border-gold/30 px-4 py-2.5 text-sm"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <MapPin className="size-3.5 text-gold" />
              {prediction ? `${origem} → ${destino}` : ""}
            </span>
            <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
              {produto}
            </span>
            <span className="font-mono text-gold">
              {brl(prediction.frete_r_per_ton)}/t
            </span>
            <span className="text-xs text-muted-foreground">
              banda {brl(prediction.banda_p10)} – {brl(prediction.banda_p90)}
            </span>
            <Badge variant="outline" className="ml-auto border-border text-[10px]">
              {prediction.model_version}
            </Badge>
          </motion.div>
        )}
      </Card>

      {/* CHAT */}
      <Card className="flex h-[560px] flex-col overflow-hidden p-0 shadow-premium">
        {/* messages */}
        <div
          ref={scrollRef}
          className="flex-1 space-y-4 overflow-y-auto p-5"
        >
          {!prediction && !loadingQuote && (
            <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
              <div className="glass grid size-12 place-items-center rounded-full border border-gold/30">
                <Sparkles className="size-5 text-gold" />
              </div>
              <p className="mt-3 max-w-sm text-sm">
                Carregue uma cotação acima para começar a conversar com o copiloto.
              </p>
            </div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className={cn(
                  "flex gap-3",
                  m.role === "user" ? "flex-row-reverse" : "flex-row",
                )}
              >
                {m.role === "bot" && (
                  <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary font-serif text-sm font-semibold text-primary-foreground shadow-premium">
                    K
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    m.role === "bot"
                      ? "glass rounded-tl-sm border border-border"
                      : "rounded-tr-sm bg-primary text-primary-foreground",
                  )}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.role === "bot" && m.source && (
                    <p className="mt-1.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      {sourceCaption(m.source)}
                    </p>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* typing indicator */}
          {typing && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3"
            >
              <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary font-serif text-sm font-semibold text-primary-foreground">
                K
              </div>
              <div className="glass flex items-center gap-1 rounded-2xl rounded-tl-sm border border-border px-4 py-3">
                <span className="size-1.5 animate-bounce rounded-full bg-gold [animation-delay:-0.3s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-gold [animation-delay:-0.15s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-gold" />
                <span className="ml-1.5 text-xs text-muted-foreground">digitando…</span>
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* suggestions */}
        {chatEnabled && (
          <div className="flex flex-wrap gap-2 border-t border-border px-5 py-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                disabled={typing}
                onClick={() => void sendQuestion(s)}
                className={cn(
                  "rounded-full border border-gold/30 px-3 py-1 text-xs text-gold transition-colors hover:bg-gold/10",
                  typing && "cursor-not-allowed opacity-50",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* input */}
        <div className="border-t border-border p-4">
          <div className="flex items-end gap-2">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendQuestion(question);
                }
              }}
              disabled={!chatEnabled || typing}
              rows={1}
              placeholder={
                chatEnabled
                  ? "Pergunte algo sobre esta cotação…"
                  : "Carregue uma cotação para conversar"
              }
              className="max-h-32 min-h-[44px] resize-none"
            />
            <Button
              size="icon"
              className="size-11 shrink-0"
              disabled={!chatEnabled || typing || !question.trim()}
              onClick={() => void sendQuestion(question)}
              aria-label="Enviar pergunta"
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* drivers hint (optional context, subtle) */}
      {prediction && prediction.drivers.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-[0.14em] text-gold">
            Principais fatores
          </span>
          {prediction.drivers.slice(0, 5).map((d) => (
            <span
              key={d.feature}
              className="flex items-center gap-1 rounded-full border border-border bg-secondary/40 px-2.5 py-0.5 text-xs text-muted-foreground"
            >
              {d.direction === "up" ? (
                <TrendingUp className="size-3 text-warning" />
              ) : (
                <TrendingDown className="size-3 text-success" />
              )}
              {d.feature}
            </span>
          ))}
        </div>
      )}

      {/* guardrail footer */}
      <p className="mt-6 flex items-center justify-center gap-2 text-xs text-muted-foreground">
        <Shield className="size-3.5 text-gold" />
        Este copiloto explica predições — nunca gera uma nova predição de frete.
      </p>
    </>
  );
}

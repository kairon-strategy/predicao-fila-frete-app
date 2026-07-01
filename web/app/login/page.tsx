"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@kairon.dev");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  async function doLogin(em: string, pw: string) {
    setLoading(true);
    try {
      await login(em, pw);
      toast.success("Bem-vindo à Kairon Frete");
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Falha no login");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await doLogin(email, password);
  }

  return (
    <div className="grid min-h-screen place-items-center bg-[radial-gradient(ellipse_at_top,rgba(197,165,114,0.12),transparent_50%)] p-5">
      <div className="w-full max-w-[440px] rounded-2xl border border-border bg-card p-10 shadow-premium">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-gold to-[#8f7648] font-serif text-xl text-[#0a0e1a] shadow-gold">
            K
          </div>
          <div className="leading-tight">
            <div className="font-serif text-lg">Kairon</div>
            <div className="text-[9.5px] uppercase tracking-[0.22em] text-gold">
              Frete rodoviário
            </div>
          </div>
        </div>

        <h1 className="font-serif text-3xl leading-tight">
          Frete <span className="text-gradient-gold italic">previsto</span>,<br />
          margem protegida.
        </h1>
        <p className="mb-8 mt-2 font-serif text-sm italic text-muted-foreground">
          Predição · benchmark · compliance para o agro brasileiro
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Senha</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full font-medium">
            {loading ? "Entrando…" : "Entrar"}
          </Button>
        </form>

        <Button
          variant="outline"
          disabled={loading}
          onClick={() => doLogin("admin@kairon.dev", "demo1234")}
          className="mt-3 w-full border-gold/40 text-gold hover:bg-gold/10"
        >
          Entrar como demo
        </Button>

        <div className="mt-6 border-t border-border pt-5 text-center text-xs text-muted-foreground">
          Não tem conta?{" "}
          <Link href="/register" className="font-medium text-gold hover:underline">
            Criar conta
          </Link>
          <div className="mt-2 text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground/70">
            demo: admin@kairon.dev · demo1234
          </div>
        </div>
      </div>
    </div>
  );
}

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

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [tenant, setTenant] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("A senha precisa ter ao menos 8 caracteres");
      return;
    }
    setLoading(true);
    try {
      await register(tenant, email, password);
      toast.success("Conta criada — bem-vindo à Kairon Frete");
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Falha ao criar conta");
    } finally {
      setLoading(false);
    }
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
          Crie sua <span className="text-gradient-gold italic">conta</span>
        </h1>
        <p className="mb-8 mt-2 font-serif text-sm italic text-muted-foreground">
          Um novo workspace isolado para sua operação
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="tenant">Nome da empresa</Label>
            <Input
              id="tenant"
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              placeholder="Ex: Acme Agro"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="voce@empresa.com.br"
              autoComplete="username"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Senha</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="mínimo 8 caracteres"
              autoComplete="new-password"
              required
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full font-medium">
            {loading ? "Criando…" : "Criar conta"}
          </Button>
        </form>

        <div className="mt-6 border-t border-border pt-5 text-center text-xs text-muted-foreground">
          Já tem conta?{" "}
          <Link href="/login" className="font-medium text-gold hover:underline">
            Entrar
          </Link>
        </div>
      </div>
    </div>
  );
}

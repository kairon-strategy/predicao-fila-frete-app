import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-[radial-gradient(ellipse_at_top,rgba(197,165,114,0.12),transparent_50%)] p-5">
      <div className="w-full max-w-[440px] rounded-2xl border border-border bg-card p-10 text-center shadow-premium">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-gold to-[#8f7648] text-xl font-semibold text-[#0a0e1a] shadow-gold">
            K
          </div>
          <div className="text-left leading-tight">
            <div className="text-lg font-semibold">Kairon</div>
            <div className="text-[9.5px] uppercase tracking-[0.22em] text-gold">
              Frete rodoviário
            </div>
          </div>
        </div>

        <div className="text-gradient-gold text-5xl font-semibold">404</div>
        <h1 className="mt-3 text-xl font-medium">Página não encontrada</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          O endereço que você tentou acessar não existe ou foi movido.
        </p>

        <Button asChild className="mt-8 w-full">
          <Link href="/dashboard">Voltar ao dashboard</Link>
        </Button>
      </div>
    </div>
  );
}

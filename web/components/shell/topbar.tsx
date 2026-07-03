"use client";

import { LogOut, Menu, Moon, Sun, User as UserIcon } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { NAV_GROUPS } from "@/components/shell/sidebar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";

const TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/predicao": "Predição de frete",
  "/consulta": "Nova consulta",
  "/simulacao": "Simulação Monte Carlo",
  "/previsao": "Previsão 12 meses",
  "/ranking": "Ranking de rotas",
  "/copiloto": "Copiloto Kairon",
  "/alertas": "Alertas",
  "/rotas": "Rotas & corredores",
  "/configuracoes": "Configurações",
};

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Alternar tema"
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {mounted && isDark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </Button>
  );
}

export function Topbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const title = TITLES[pathname] ?? "Kairon Frete";

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border/60 bg-background/80 px-5 py-3 backdrop-blur-md md:px-8">
      <div className="flex items-center gap-3">
        {/* Mobile menu */}
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden">
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[260px] border-sidebar-border bg-sidebar p-0">
            <SheetTitle className="px-5 py-5 font-serif text-lg">Kairon Frete</SheetTitle>
            <nav className="px-3">
              {NAV_GROUPS.flatMap((g) => g.items)
                .filter((i) => !i.disabled)
                .map((i) => (
                  <Link
                    key={i.href}
                    href={i.href}
                    className="mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground hover:bg-gold/10"
                  >
                    <i.icon className="size-[18px] text-gold/80" />
                    {i.label}
                  </Link>
                ))}
            </nav>
          </SheetContent>
        </Sheet>

        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            Kairon Frete
          </div>
          <div className="-mt-0.5 font-serif text-lg leading-tight">{title}</div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                aria-label={`${user.email}, papel ${user.role}`}
                className="gap-2 rounded-full border-border bg-card px-3"
              >
                <span
                  aria-hidden
                  className="flex size-6 items-center justify-center rounded-full bg-gradient-to-br from-gold-2 to-[#7a6237] text-[11px] font-semibold text-[#0a0e1a]"
                >
                  {user.email.slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden text-xs sm:inline">{user.email}</span>
                <span className="rounded bg-gold/15 px-1.5 py-0.5 text-[10px] uppercase text-gold">
                  {user.role}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="truncate">{user.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout} className="text-destructive">
                <LogOut className="mr-2 size-4" /> Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button asChild variant="outline" className="gap-2 rounded-full border-gold/40">
            <Link href="/login">
              <UserIcon className="size-4 text-gold" /> Entrar
            </Link>
          </Button>
        )}
      </div>
    </header>
  );
}

"use client";

import {
  Bell,
  Bot,
  FileText,
  LayoutDashboard,
  LineChart,
  type LucideIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
  disabled?: boolean;
};
export type NavGroup = { title: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Operação",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/predicao", label: "Predição de frete", icon: Search },
      { href: "/simulacao", label: "Simulação", icon: LineChart },
      { href: "/previsao", label: "Previsão 12 meses", icon: TrendingUp },
      { href: "/ranking", label: "Ranking de rotas", icon: LayoutDashboard },
    ],
  },
  {
    title: "Inteligência",
    items: [
      { href: "/copiloto", label: "Copiloto Kairon", icon: Bot },
      { href: "/alertas", label: "Alertas", icon: Bell },
    ],
  },
  {
    title: "Compliance · v2",
    items: [
      { href: "#", label: "TaaS · Relatórios", icon: FileText, badge: "v2", disabled: true },
      { href: "#", label: "Contratos", icon: ShieldCheck, badge: "v2", disabled: true },
    ],
  },
];

export function Sidebar({
  collapsed = false,
  onToggle,
}: {
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 lg:flex",
        collapsed ? "w-[76px]" : "w-[260px]",
      )}
    >
      {/* Marca + toggle */}
      <div
        className={cn(
          "flex items-center gap-3 border-b border-sidebar-border py-5",
          collapsed ? "justify-center px-2" : "px-5",
        )}
      >
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-gold to-[#8f7648] text-xl font-semibold text-[#0a0e1a] shadow-gold">
          K
        </div>
        {!collapsed && (
          <div className="flex-1 leading-tight">
            <div className="text-lg font-semibold tracking-tight">Kairon Frete</div>
            <div className="text-[9.5px] uppercase tracking-[0.22em] text-gold">
              Frete rodoviário
            </div>
          </div>
        )}
        {onToggle && !collapsed && (
          <button
            onClick={onToggle}
            className="rounded-md p-1 text-muted-foreground hover:bg-gold/10 hover:text-gold"
            aria-label="Colapsar menu"
          >
            <PanelLeftClose className="size-5" />
          </button>
        )}
      </div>

      {onToggle && collapsed && (
        <button
          onClick={onToggle}
          className="mx-auto mt-2 rounded-md p-1.5 text-muted-foreground hover:bg-gold/10 hover:text-gold"
          aria-label="Expandir menu"
        >
          <PanelLeftOpen className="size-5" />
        </button>
      )}

      {/* Navegação */}
      <nav className={cn("flex-1 overflow-y-auto py-4", collapsed ? "px-2" : "px-3")}>
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mb-2">
            {!collapsed && (
              <div className="px-3 pb-1.5 pt-3 text-[9.5px] uppercase tracking-[0.22em] text-muted-foreground">
                {group.title}
              </div>
            )}
            {collapsed && <div className="my-2 border-t border-sidebar-border/60" />}
            {group.items.map((item) => {
              const active = !item.disabled && pathname.startsWith(item.href);
              const Icon = item.icon;
              const base = cn(
                "mb-0.5 flex items-center rounded-lg text-[13px] transition-all",
                collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2",
              );
              const cls = item.disabled
                ? cn(base, "cursor-not-allowed text-sidebar-foreground/40")
                : active
                  ? cn(
                      base,
                      "bg-gradient-to-r from-gold/[0.18] to-transparent text-gold",
                      !collapsed && "border-l-2 border-gold pl-2.5",
                    )
                  : cn(base, "text-sidebar-foreground hover:bg-gold/[0.08] hover:text-foreground");

              const inner = (
                <>
                  <Icon
                    className={cn("size-[18px] shrink-0", active ? "text-gold" : "text-gold/70")}
                  />
                  {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                  {!collapsed && item.badge && (
                    <span className="rounded-md bg-gold/15 px-1.5 py-0.5 text-[9.5px] tracking-wider text-gold">
                      {item.badge}
                    </span>
                  )}
                </>
              );

              const node = item.disabled ? (
                <div className={cls} title="Disponível na v2">
                  {inner}
                </div>
              ) : (
                <Link href={item.href} className={cls}>
                  {inner}
                </Link>
              );

              if (collapsed) {
                return (
                  <Tooltip key={item.label}>
                    <TooltipTrigger asChild>{node}</TooltipTrigger>
                    <TooltipContent side="right">
                      {item.label}
                      {item.badge ? ` · ${item.badge}` : ""}
                    </TooltipContent>
                  </Tooltip>
                );
              }
              return <div key={item.label}>{node}</div>;
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}

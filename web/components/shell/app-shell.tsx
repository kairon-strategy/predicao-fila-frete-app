"use client";

import { useEffect, useState } from "react";

import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";
import { cn } from "@/lib/utils";

const KEY = "kairon_sidebar_collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(localStorage.getItem(KEY) === "1");
  }, []);

  const toggle = () =>
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(KEY, next ? "1" : "0");
      return next;
    });

  return (
    <div className="min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div
        className={cn(
          "transition-[padding] duration-200",
          collapsed ? "lg:pl-[76px]" : "lg:pl-[260px]",
        )}
      >
        <Topbar />
        <main className="mx-auto w-full max-w-[1440px] px-5 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}

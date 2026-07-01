"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

function FullScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-[radial-gradient(ellipse_at_top,rgba(197,165,114,0.12),transparent_50%)]">
      {children}
    </div>
  );
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <FullScreen>
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <div className="size-8 animate-spin rounded-full border-2 border-gold border-t-transparent" />
          <span className="text-sm">Carregando sessão…</span>
        </div>
      </FullScreen>
    );
  }

  if (!user) {
    return (
      <FullScreen>
        <div className="text-sm text-muted-foreground">Redirecionando para o login…</div>
      </FullScreen>
    );
  }

  return <>{children}</>;
}

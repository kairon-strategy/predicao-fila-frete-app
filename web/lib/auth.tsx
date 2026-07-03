"use client";

/**
 * AuthProvider — estado de autenticação no client.
 * Token em localStorage; login opcional (anônimo funciona no MVP).
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, clearTokens, getToken, type Me, setTokens } from "@/lib/api";

type AuthState = {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (tenantName: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      clearTokens();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void refreshMe().finally(() => setLoading(false));
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    setUser(await api.me());
  }, []);

  const register = useCallback(async (tenantName: string, email: string, password: string) => {
    const tokens = await api.register(tenantName, email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    setUser(await api.me());
  }, []);

  const logout = useCallback(() => {
    // revoga a sessão no servidor (best-effort); não bloqueia o logout local
    void api.logout().catch(() => {});
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}

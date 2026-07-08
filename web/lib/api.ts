/**
 * Cliente da API Kairon Frete (tipado). Framework-agnóstico.
 * Base URL via NEXT_PUBLIC_API_URL (default http://localhost:8000).
 * Token JWT guardado em localStorage; injetado como Bearer quando presente.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

const TOKEN_KEY = "kairon_access_token";
const REFRESH_KEY = "kairon_refresh_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
  // flag (não o JWT) num cookie: só p/ o guard server-side (proxy.ts) redirecionar.
  document.cookie = `kairon_auth=1; path=/; max-age=604800; samesite=lax`;
}
export function clearTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  document.cookie = "kairon_auth=; path=/; max-age=0; samesite=lax";
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ReqOpts = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean; // injeta Bearer (default true)
};

// Refresh coalescido: várias chamadas 401 concorrentes disparam UM refresh só.
let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  if (!refreshing) {
    refreshing = fetch(`${API_BASE}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    })
      .then(async (r) => {
        if (!r.ok) return false;
        const d = (await r.json()) as TokenResponse;
        setTokens(d.access_token, d.refresh_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request<T>(path: string, opts: ReqOpts = {}, _retried = false): Promise<T> {
  const { method = "GET", body, headers = {}, auth = true } = opts;
  const h: Record<string, string> = { "Content-Type": "application/json", ...headers };
  if (auth) {
    const token = getToken();
    if (token) h["Authorization"] = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: h,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Não foi possível conectar à API. Ela está no ar?", 0);
  }

  // Token expirado: tenta renovar UMA vez e refaz a request.
  if (res.status === 401 && auth && !_retried && getToken()) {
    if (await tryRefresh()) return request<T>(path, opts, true);
    clearTokens();
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const msg =
      (data && (data.message || data.detail || data.error)) || `Erro ${res.status}`;
    throw new ApiError(typeof msg === "string" ? msg : JSON.stringify(msg), res.status);
  }
  return data as T;
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/* ----------------------------- Tipos ----------------------------- */
export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};
export type Me = {
  user_id: string;
  tenant_id: string;
  email: string;
  name: string | null;
  role: string;
  permissions: string[];
};
export type PermissionInfo = { key: string; group: string; label: string };
export type RoleRecord = {
  id: string;
  name: string;
  slug: string;
  is_system: boolean;
  permissions: string[];
  user_count: number;
};
export type UserResponse = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  tenant_id: string;
};
export type TenantResponse = { id: string; name: string; slug: string };
export type RouteRecord = {
  route_id: string;
  origem: string;
  destino: string;
  produto: string;
  distancia_km: number;
  corredor: string | null;
  piso_antt_r_per_ton: number | null;
};
export type RouteWrite = {
  origem: string;
  destino: string;
  produto: string;
  distancia_km: number;
  corredor?: string | null;
  piso_antt_r_per_ton?: number | null;
};

export type Driver = { feature: string; shap_value: number; direction: "up" | "down" };
export type PredictRequest = {
  origem: string;
  destino: string;
  produto: string;
  data: string; // YYYY-MM-DD
  carga_ton?: number | null;
  diesel_price?: number | null; // override de mercado (slider de diesel)
};
export type PredictResponse = {
  prediction_id: string;
  frete_r_per_ton: number;
  banda_p10: number;
  banda_p90: number;
  drivers: Driver[];
  model_version: string;
};
export type ExplainResponse = {
  prediction_id: string;
  explanation: string;
  source: "llm" | "template";
};
export type RouteRankingItem = {
  route_id: string;
  origem: string;
  destino: string;
  produto: string;
  corredor: string | null;
  distancia_km: number;
  frete_r_per_ton: number;
  r_per_ton_km: number;
  banda_p10: number;
  banda_p90: number;
  var_30d_pct: number;
  mape: number | null;
};
export type RouteHistoryPoint = {
  month: string;
  frete_r_per_ton: number;
  banda_p10: number;
  banda_p90: number;
};
export type RouteHistory = {
  route_id: string;
  origem: string;
  destino: string;
  produto: string;
  points: RouteHistoryPoint[];
  note: string;
};
export type SimulateResponse = {
  mean: number;
  p10: number;
  p50: number;
  p90: number;
  iterations: number;
  note: string;
};
export type SegmentSimResult = {
  segment: string;
  base_freight: number;
  mean: number;
  p10: number;
  p50: number;
  p90: number;
  delta_pct: number;
};
export type SimulateSegmentsResponse = {
  iterations: number;
  drivers: Record<string, number>;
  segments: SegmentSimResult[];
};
export type SegmentBase = { segment: string; base_freight: number };
export type Alert = {
  id: number;
  severity: "critical" | "warn" | "info";
  alert_type: string;
  entity_id: string | null;
  title: string;
  body: string;
  meta: Record<string, unknown>;
  status: "active" | "resolved";
  created_at: string | null;
  resolved_at: string | null;
};
export type Health = { status: string; version: string };

/* ----------------------------- Endpoints ----------------------------- */
export const api = {
  // auth
  login: (email: string, password: string) =>
    request<TokenResponse>("/v1/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  me: () => request<Me>("/v1/auth/me"),
  refresh: (refresh_token: string) =>
    request<TokenResponse>("/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token },
      auth: false,
    }),
  register: (tenant_name: string, email: string, password: string) =>
    request<TokenResponse>("/v1/auth/register", {
      method: "POST",
      body: { tenant_name, email, password },
      auth: false,
    }),
  // usuários (admin)
  listUsers: () => request<UserResponse[]>("/v1/auth/users"),
  createUser: (email: string, password: string, role: string, name?: string) =>
    request<UserResponse>("/v1/auth/users", {
      method: "POST",
      body: { email, password, role, name: name ?? null },
    }),
  updateUser: (id: string, patch: { role?: string; is_active?: boolean; password?: string }) =>
    request<UserResponse>(`/v1/auth/users/${id}`, { method: "PATCH", body: patch }),
  // encerra a sessão no servidor (revoga tokens via token_version)
  logout: () => request<void>("/v1/auth/logout", { method: "POST" }),

  // perfil próprio
  updateMe: (patch: { name?: string; password?: string }) =>
    request<UserResponse>("/v1/auth/me", { method: "PATCH", body: patch }),

  // empresa (tenant)
  getTenant: () => request<TenantResponse>("/v1/auth/tenant"),
  updateTenant: (name: string) =>
    request<TenantResponse>("/v1/auth/tenant", { method: "PATCH", body: { name } }),

  // perfis & permissões (RBAC dinâmico)
  listPermissions: () => request<PermissionInfo[]>("/v1/auth/permissions"),
  listRoles: () => request<RoleRecord[]>("/v1/auth/roles"),
  createRole: (name: string, permissions: string[]) =>
    request<RoleRecord>("/v1/auth/roles", { method: "POST", body: { name, permissions } }),
  updateRole: (id: string, patch: { name?: string; permissions?: string[] }) =>
    request<RoleRecord>(`/v1/auth/roles/${id}`, { method: "PATCH", body: patch }),
  deleteRole: (id: string) => request<void>(`/v1/auth/roles/${id}`, { method: "DELETE" }),

  // CRUD de rotas (gestão)
  listRoutesManage: () => request<RouteRecord[]>("/v1/routes/manage"),
  createRoute: (body: RouteWrite) =>
    request<RouteRecord>("/v1/routes", { method: "POST", body }),
  updateRoute: (id: string, body: RouteWrite) =>
    request<RouteRecord>(`/v1/routes/${id}`, { method: "PUT", body }),
  deleteRoute: (id: string) => request<void>(`/v1/routes/${id}`, { method: "DELETE" }),

  // prediction
  predict: (payload: PredictRequest) =>
    request<PredictResponse>("/v1/predict", {
      method: "POST",
      body: payload,
      headers: { "idempotency-key": uuid() },
    }),
  getRoutes: (produto?: string, corredor?: string) => {
    const qs = new URLSearchParams();
    if (produto) qs.set("produto", produto);
    if (corredor) qs.set("corredor", corredor);
    const q = qs.toString();
    return request<RouteRankingItem[]>(`/v1/routes${q ? `?${q}` : ""}`);
  },
  getRouteHistory: (routeId: string, months = 12) =>
    request<RouteHistory>(`/v1/routes/${routeId}/history?months=${months}`),

  // explanation
  explain: (prediction_id: string, question?: string) =>
    request<ExplainResponse>("/v1/explain", {
      method: "POST",
      body: { prediction_id, question: question ?? null },
    }),

  // simulation
  simulate: (base_freight: number, iterations: number) =>
    request<SimulateResponse>("/v1/simulate", {
      method: "POST",
      body: { base_freight, iterations },
    }),
  // Monte Carlo por segmento (diesel · safra · piso ANTT)
  simulateSegments: (body: {
    diesel_pct: number;
    safra_pct: number;
    piso_pct: number;
    iterations: number;
    bases: SegmentBase[];
  }) => request<SimulateSegmentsResponse>("/v1/simulate/segments", { method: "POST", body }),

  // alerts
  getAlerts: (severity?: string, alertType?: string, status = "active") => {
    const qs = new URLSearchParams({ status });
    if (severity) qs.set("severity", severity);
    if (alertType) qs.set("type", alertType);
    return request<Alert[]>(`/v1/alerts?${qs.toString()}`);
  },
  resolveAlert: (id: number) =>
    request<Alert>(`/v1/alerts/${id}/resolve`, { method: "POST" }),
  detectAlerts: () =>
    request<{ created: number; detail: string }>("/v1/alerts/detect", { method: "POST" }),

  // ops
  health: () => request<Health>("/health", { auth: false }),
};

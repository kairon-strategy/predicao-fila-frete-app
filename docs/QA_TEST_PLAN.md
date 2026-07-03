# Plano de Testes — Kairon Frete MVP (rodada 3)

**Build alvo:** `main` @ HEAD `8409585` (ou superior)
**Objetivo:** re-verificar correções da rodada 2, cobrir os itens que ficaram bloqueados por rate-limit, validar as features novas (Monte Carlo por segmento, alertas, auth endurecida) e medir performance **em modo produção**.
**Legenda de prioridade:** P0 (bloqueia lançamento) · P1 (antes do piloto pago) · P2 (polimento).

---

## 0. Pré-condições (fazer antes de começar)

> ⚠️ A rodada 2 esbarrou em ambiente saturado (FCP 8,3s, renderer travando). **Reinicie o terminal/Cursor (ou a máquina) antes de começar** para ter medições limpas.

1. Atualizar código:
   ```bash
   git checkout main && git pull        # confirmar HEAD >= 8409585
   ```
2. `.env` (raiz) para não travar o QA no rate-limit:
   ```
   LOGIN_WINDOW_MIN=1          # lockout de login expira em 60s
   ```
3. Banco + API:
   ```bash
   make db-migrate
   poetry run python scripts/seed_synthetic_data.py     # 62 rotas, 3 users, diesel
   poetry run python scripts/seed_demo_alerts.py        # 2 alertas (spike diesel)
   make run-api                                          # :8000
   ```
4. Front (cache limpo, evita o FCP alto por cache velho):
   ```bash
   cd web && rm -rf .next && npm install && npm run dev  # :3000
   ```
5. Browser: **hard refresh (Cmd+Shift+R)**, cookies/localStorage limpos.
6. Credenciais demo (dev): admin `admin@kairon.dev` · analyst `analyst@kairon.dev` · viewer `viewer@kairon.dev` — senha `demo1234`.

**URLs:** App `http://localhost:3000` · API `http://localhost:8000` · Swagger `http://localhost:8000/docs`.

---

## Suíte A — Autenticação & segurança (backend, determinístico)

Rodáveis por `curl` direto — não dependem da UI.

| ID | Prio | Passos | Resultado esperado |
|---|---|---|---|
| A1 | P0 | `POST /v1/auth/login` `{"email":"","password":""}` | **422** (`string_too_short`) |
| A2 | P0 | login `{"email":"not-an-email","password":"1"}` | **401** "credenciais inválidas" |
| A3 | P0 | login `{"email":"admin@kairon.dev","password":"errada"}` | **401** |
| A4 | P0 | login `{"email":"nao-existe@x.com","password":"demo1234"}` | **401** |
| A5 | P0 | login admin correto | **200** + `access_token`/`refresh_token` |
| A6 | P2 | Medir `time_total` de A3 (existe) vs A4 (não existe), 3× cada | **latências equivalentes** (timing attack mitigado — bcrypt roda nos dois) |
| A7 | P1 | 6 logins errados no mesmo email | 1–5 → **401**; 6º → **429** |
| A8 | P1 | Inspecionar headers do 429 | contém **`Retry-After`** (segundos) |
| A9 | P1 | Após `LOGIN_WINDOW_MIN=1`, esperar 60s e logar certo | **200** (lockout expirou) |
| A10 | P1 | `POST /v1/auth/register` com body **válido** (`tenant_name,email,password`) | **403** (invite-only). Sem `tenant_name` → 422 (validação antes do gate — esperado) |
| A11 | P0 | Qualquer `GET /v1/...` **sem** `Authorization` | **401** (autenticação obrigatória) |

---

## Suíte B — Autorização / RBAC & isolamento

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| B1 | P0 | Logar viewer → `POST /v1/routes` (criar rota) | **403** |
| B2 | P1 | viewer → `GET /v1/routes` (ranking) | **200** (leitura liberada) |
| B3 | P1 | Criar user com `role:"root"` (admin) | **422** (enum inválido) |
| B4 | P1 | Token de outro tenant → `GET /v1/alerts` | **200** e lista **vazia** (isolamento) |
| B5 | P1 | Logout (`POST /v1/auth/logout`) e reusar o `refresh_token` antigo em `/refresh` | **401** (sessão revogada) |
| B6 | P1 | Admin reseta senha de um user (`PATCH /v1/auth/users/{id}` com `password`) → user loga com a nova; refresh antigo dele | nova senha **200**; refresh antigo **401** |

---

## Suíte C — Telas & navegação (UI, autenticado)

Logar como **admin** antes.

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| C1 | P1 | Visitar as 11 rotas do menu (`/dashboard /predicao /simulacao /previsao /ranking /rotas /copiloto /alertas /configuracoes` + login/register) | Todas renderizam, sem 500/erro no console |
| C2 | P0 | **Logado**, acessar URL inexistente `…/rota-inexistente-99` | **404 branded Kairon** em PT, com "Voltar ao dashboard" (não a 404 nua do Next) |
| C3 | P0 | Itens "Compliance · v2" (TaaS, Contratos) no menu | Aparecem `disabled` (cinza), **não navegam** |
| C4 | P1 | Redimensionar para 375px (mobile) e 768px (tablet) | Sidebar **some**, aparece **hambúrguer**; conteúdo usa a largura toda |
| C5 | P1 | `/configuracoes` → aba Perfil | Campo **Email preenchido** com o email do usuário (não vazio) |
| C6 | P1 | `/configuracoes` → aba Usuários (admin) | Lista de usuários + ações (criar, mudar papel, ativar/desativar, **resetar senha**) |

---

## Suíte D — Dados & realismo

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| D1 | P1 | `GET /v1/routes` → contar valores distintos de `var_30d_pct` e `r_per_ton_km` | **~20** e **~34** distintos em 62 rotas (não mais constantes) |
| D2 | P1 | Dashboard → KPI "Rotas monitoradas" subtitle | "fertilizante + algodão + **grão**" |
| D3 | P1 | Dashboard → KPI "Alertas ativos" e card "Alertas recentes" | **2 alertas** (🔴 MT +13% crítico · 🟡 GO +7% aviso), texto **não cortado no meio** (line-clamp-3) |
| D4 | P0 | `/alertas` | Feed com os 2 alertas; filtro por severidade e tabs Ativos/Resolvidos funcionam |
| D5 | — | Ranking → coluna MAPE | **"—"** é **esperado** (modelo não treinado — não é bug; ver "Fora de escopo") |

---

## Suíte E — Simulação Monte Carlo por segmento (feature nova ⭐)

`/simulacao`, autenticado.

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| E1 | P1 | Abrir `/simulacao` | 3 sliders: **Diesel** (−10..+30%), **Safra** (−25..+5%), **Piso ANTT** (0..+15%) + iterações; roda automático ao abrir |
| E2 | P1 | Ajustar Diesel +20%, Safra −15%, Piso +5% | 3 cards por segmento (Fertilizante/Algodão/Grão) com média, Δ% e banda P10/P50/P90 |
| E3 | P1 | Comparar as reações entre segmentos | Reação **diferenciada**: grão mais sensível à safra (banda mais larga), fertilizante mais ao diesel (~+12%) |
| E4 | P2 | Backend direto `POST /v1/simulate/segments` (ver payload no Swagger) | JSON com `segments[]` (mean/p10/p50/p90/delta_pct) e `drivers` ecoados |
| E5 | P2 | Mover um slider e soltar | Resultado **re-roda** (onValueCommit) sem recarregar a página |

---

## Suíte F — Tema claro/escuro

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| F1 | P1 | Abrir `/login` em aba anônima | Abre em **tema claro** (creme `rgb(245,243,238)`) por padrão |
| F2 | P1 | Logado, botão de tema no topbar (Sol/Lua) | Alterna claro⇄escuro; **todos** os componentes trocam (KPI cards, sidebar, topbar) — sem componente bege preso no escuro |
| F3 | P2 | Recarregar após alternar | Preferência persiste (localStorage) |

---

## Suíte G — Acessibilidade

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| G1 | P1 | Inspecionar o chip de usuário no topbar (`aria-label`) | `aria-label="email, papel role"`; avatar com `aria-hidden` (screen reader não lê "Aadmin@…") |
| G2 | P2 | Botão de tema | `aria-label="Alternar tema"` presente |
| G3 | P2 | Login | inputs com `name`, `required`, `autocomplete` corretos; senha `minLength=8` |

---

## Suíte H — Performance (medir em PRODUÇÃO, não dev)

> A rodada 2 mediu **dev-mode** (Turbopack compila sob demanda) numa máquina saturada → FCP 8,3s. **Meça em build de produção.**

| ID | Prio | Passos | Esperado / critério |
|---|---|---|---|
| H1 | P0 | `cd web && npm run build && npm start` → Lighthouse em `/login` | **FCP < 2s**, **TTI < 3,5s** (se passar, o 8,3s era dev-mode — aceitável) |
| H2 | P1 | Lighthouse em `/dashboard` (logado, build prod) | Performance ≥ 80 |
| H3 | P1 | `@next/bundle-analyzer` (`ANALYZE=true npm run build`) | Nenhum chunk de rota > ~250KB gz; anexar report |
| H4 | P2 | Navegar para rota 404 em **build prod** | Responde rápido (< 500ms) — o custo de compile some no build |
| H5 | P0 | Repetir com o `next dev` **após restart da máquina** | Confirmar que o "renderer travando/CDP timeout" não reaparece (era saturação) |

**Se H1 falhar em prod (FCP > 2s):** aí sim é bug de código → abrir issue P0 de perf com o trace do Lighthouse.

---

## Suíte I — Regressão (confirmar que segue OK)

Já confirmados na rodada 2 — checagem rápida: A1–A5 (auth), form `method=post` + `required`/`name`/`minLength`, credenciais demo aparecem só em dev.

---

## Fora de escopo / NÃO flagar

- **Fonte serifada (DM Serif):** removida **por decisão de produto**. O Inter é intencional.
- **Valor do `/predict` e MAPE "—":** dependem do **modelo LightGBM treinado**, adiado de propósito. O baseline é honesto. Valor de negócio está em ranking + simulação + alertas.
- **Copiloto (chat + grounding):** depende do LLM ligado (`ANTHROPIC_API_KEY`), fora desta rodada.

## Backlog aberto (válido, próxima rodada — não bloqueia)

Filtro de período nos alertas (P2-3), breadcrumb (P2-4), CTA em empty states (P2-5), consumir `Retry-After` no toast do front, tornar o gate do `/register` anterior à validação de body.

---

## Critérios de saída (exit criteria)

- ✅ **Liberar para demo/piloto:** todos os **P0** das suítes A, B, C, D passam **e** H1 (FCP < 2s em prod) passa.
- ⚠️ **Bloqueia:** qualquer P0 de auth/RBAC falhando, ou H1 falhando em **build de produção** (não dev).
- Registrar cada caso como Pass/Fail + commit/screenshot; reportar no formato da rodada anterior.

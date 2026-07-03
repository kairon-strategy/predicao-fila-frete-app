# Kairon Frete

## O que é

**Kairon Frete** é um SaaS + TaaS de **predição de frete rodoviário** para o agro brasileiro (fertilizante e grãos). O motor combina um **baseline determinístico**, um **LightGBM** que prevê o resíduo, **bandas de quantil** (P10/P90), explicação por **SHAP** e um **copiloto Claude Sonnet** que só _explica_ a predição — nunca prevê frete. É um monólito modular (cada pasta em `src/kairon/` é um _bounded context_ que vira microserviço na v2).

> **Meta MVP (jul–out/2026):** 3 clientes, R$ 180–280k ARR, ~60 rotas ativas. Time: 1 engenheiro. Prioridade: **manutenibilidade sobre sofisticação**.

## Stack

- **Backend:** Python 3.12 · FastAPI (async) · SQLAlchemy 2.x + asyncpg · Alembic · LightGBM/SHAP · Claude SDK.
- **Frontend:** Next.js 16 (App Router, React 19) · Tailwind v4 · shadcn/ui — em [`web/`](./web/).
- **Banco:** Postgres 16 (local em dev) ou **Supabase** (Postgres gerenciado, prod). O Supabase é usado **só como banco + Auth/Storage** — nunca como camada de compute (ADR-012).

## Requisitos

- **Python 3.12** (`~3.12`, ver `.python-version`) + **Poetry**
- **Node 20+** (para o front Next.js em `web/`)
- **Postgres 16** local — ou uma connection string do Supabase em `DATABASE_URL`
- Docker é **opcional** (o `docker-compose` sobe API + Postgres para quem preferir)

## Setup rápido (clone → rodando)

```bash
# 1. Variáveis de ambiente
cp .env.example .env
#    - DATABASE_URL vazio => usa o Postgres local (POSTGRES_* do .env).
#    - Para apontar ao Supabase, preencha DATABASE_URL (forma asyncpg, pooler).
#    - ANTHROPIC_API_KEY e SENTRY_DSN são OPCIONAIS: sem eles a app degrada com
#      elegância (/v1/explain cai para template estático; Sentry fica desligado).

# 2. Dependências do backend + pre-commit hooks
make install

# 3. Migrations (cria/atualiza o schema)
make db-migrate            # alembic upgrade head

# 4. Popula com dados SINTÉTICOS (~60 rotas + diesel + histórico + 3 usuários demo)
make seed

# 5. Sobe a API (:8000)
make run-api

# 6. Sobe o front Next.js (:3000) — noutro terminal
cd web && npm install && npm run dev
```

- **App (UI Next.js):** http://localhost:3000
- **API docs (Swagger/OpenAPI):** http://localhost:8000/docs
- **Health / readiness:** http://localhost:8000/health · http://localhost:8000/ready

> **Dados são SINTÉTICOS em dev.** O histórico real da Eurochem (e de qualquer cliente) **nunca é comitado**. Todo dado de seed é gerado com semente fixa e claramente marcado como fictício.

## Comandos

Todos os alvos vivem no `Makefile` (rode `make help` para a lista viva).

| Alvo | O que faz |
|------|-----------|
| `make help` | Lista os alvos disponíveis |
| `make install` | Instala dependências (Poetry, grupos dev+ui) + pre-commit hooks |
| `make lint` | Ruff lint + checagem de formatação |
| `make fmt` | Ruff auto-format + `--fix` |
| `make typecheck` | mypy (strict) |
| `make test` | pytest com cobertura (falha se < 70%) |
| `make run-api` | Sobe a API FastAPI local com hot reload em `:8000` |
| `make etl-anp` | Roda o ETL ANP uma vez (baixa CSV do diesel, normaliza, grava) |
| `make db-migrate` | Aplica migrations Alembic (`upgrade head`) |
| `make db-revision` | Cria migration: `make db-revision m="mensagem"` |
| `make seed` | Popula o banco com dados sintéticos |
| `make docker-up` | Sobe API + Postgres via docker-compose (opcional) |
| `make docker-down` | Derruba a stack (mantém volumes) |
| `make docker-nuke` | Derruba a stack **e apaga volumes** (reset total) |

O front (Next.js) roda com `cd web && npm run dev` (dev) ou `npm run build && npm start` (prod).

## Endpoints

Superfície HTTP atual, agrupada por context. Prefixo `/v1` em tudo exceto os endpoints de ops. **Todo endpoint `/v1` exige autenticação** (sem token → `401`); o RBAC (`admin` | `analyst` | `viewer`) é aplicado por cima — ver [Autenticação e papéis](#autenticação-e-papéis).

### Ops (sem prefixo, sem auth)

| Método | Path | Auth | Propósito |
|--------|------|------|-----------|
| GET | `/health` | — | Liveness: o processo está de pé (não checa dependências). |
| GET | `/ready` | — | Readiness: Postgres obrigatório; reporta `llm_configured` sem bloquear. |
| GET | `/metrics` | — | Métricas Prometheus (contadores por path-template). |

### Auth — context `tenant`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/auth/login` | público (rate-limited) | `{email, password}` → `{access_token, refresh_token, token_type}`. |
| POST | `/v1/auth/refresh` | refresh token | `{refresh_token}` → novo par; **`401` se a sessão foi revogada**. |
| POST | `/v1/auth/register` | público **se habilitado** | Cria tenant + admin. **Invite-only por padrão → `403`** (`allow_open_registration`). |
| POST | `/v1/auth/logout` | Bearer | Revoga a sessão (invalida os refresh tokens). |
| GET | `/v1/auth/me` | Bearer | Dados do usuário autenticado. |
| PATCH | `/v1/auth/me` | Bearer | Edita o próprio nome/senha (trocar a senha revoga sessões). |
| GET | `/v1/auth/users` | `admin` | Lista usuários do tenant. |
| POST | `/v1/auth/users` | `admin` | Cria usuário no tenant (papel validado por enum). |
| PATCH | `/v1/auth/users/{id}` | `admin` | Edita papel/ativação **e reseta senha** (revoga sessões do alvo). |
| GET | `/v1/auth/tenant` | Bearer | Dados da empresa (tenant). |
| PATCH | `/v1/auth/tenant` | `admin` | Edita o nome da empresa. |

### Prediction — context `prediction`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/predict` | `admin`\|`analyst` + header `idempotency-key` | Prevê frete (R$/t) para uma rota. |
| GET | `/v1/routes` | qualquer papel (inclui `viewer`) | Ranking de rotas; filtros `?produto=&corredor=`. |
| GET | `/v1/routes/{route_id}/history` | qualquer papel | Série histórica da rota; `?months=` (1–36, default 12). |
| GET | `/v1/routes/manage` | qualquer papel | Lista rotas (gestão/CRUD). |
| POST | `/v1/routes` | `admin`\|`analyst` | Cria rota. |
| PUT | `/v1/routes/{id}` | `admin`\|`analyst` | Edita rota. |
| DELETE | `/v1/routes/{id}` | `admin`\|`analyst` | Exclui rota (204). |

### Explanation — context `explanation`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/explain` | qualquer papel | Explica uma predição (`{prediction_id, question?}` → `{prediction_id, explanation, source}`). |

### Simulation — context `simulation`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/simulate` | qualquer papel | Monte Carlo síncrono (`{base_freight, iterations}`). |

### Alerts — context `alerts`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| GET | `/v1/alerts` | qualquer papel | Feed de alertas do tenant; filtros `?severity=&type=&status=` (default `status=active`). |
| POST | `/v1/alerts/{id}/resolve` | qualquer papel | Marca um alerta como resolvido. |
| POST | `/v1/alerts/detect` | `admin`\|`analyst` | Roda os detectores (hoje: spike de diesel) e cria alertas novos. |

## Autenticação e papéis

Auth é **JWT** (access de 15 min + refresh de 7 dias), senha com **bcrypt**, RBAC de três papéis (`admin` | `analyst` | `viewer`) aplicado por `require_role`.

- **Autenticação obrigatória.** Todo endpoint `/v1` exige `Authorization: Bearer <token>`; sem token → **`401`**. (Não existe mais o "anônimo = admin".) Token inválido/expirado → `401`.
- **Registro por convite.** `POST /v1/auth/register` (cria tenant + admin) fica **desligado por padrão** (`allow_open_registration=False` → `403`). Novos usuários são criados por um `admin` via `POST /v1/auth/users`.
- **Papel validado por enum** (`admin`|`analyst`|`viewer`) na borda (schema) e no service — papel inválido → `422`.
- **Revogação de sessão.** O JWT carrega `tv` (token_version, coluna em `users`). **Logout** e **troca/reset de senha** incrementam o `tv` → os refresh tokens antigos param de valer imediatamente (`401` no `/refresh`); o access token atual expira em ≤15 min. Sem denylist/estado por request.
- **Reset de senha por admin** via `PATCH /v1/auth/users/{id}` (revoga as sessões do alvo). O próprio usuário troca a senha em `PATCH /v1/auth/me`.
- **Rate limit no login** (anti brute-force): `login_max_attempts` (5) por `login_window_min` (15) por IP+email → `429`.
- **Auditoria:** login, registro, criação de usuário, reset de senha e logout gravam em `audit_events` (append-only).

O `make seed` cria 3 usuários demo no tenant default (senha `demo1234`): `admin@kairon.dev`, `analyst@kairon.dev`, `viewer@kairon.dev`.

Fluxo com token:

```bash
# 1. Login → pega o access_token
ACCESS=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@kairon.dev","password":"demo1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Usa o token nos requests
curl -s http://localhost:8000/v1/auth/me \
  -H "Authorization: Bearer $ACCESS"
```

## Exemplos de API

### `POST /v1/predict` — prevê frete (R$/tonelada)

Exige token (`admin`\|`analyst`) e o header **`idempotency-key`** (mesma chave → mesma predição, **escopada por tenant**). Body: `origem`, `destino`, `produto`, `data`, `carga_ton` (opcional), `diesel_price` (opcional, override de mercado).

```bash
curl -X POST http://localhost:8000/v1/predict \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -H "idempotency-key: demo-2026-08-15-sinop-sorriso-ureia" \
  -d '{
    "origem": "Sinop-MT",
    "destino": "Sorriso-MT",
    "produto": "ureia",
    "data": "2026-08-15",
    "carga_ton": 30
  }'
```

Resposta (resumida): `prediction_id`, `frete_r_per_ton`, `banda_p10`, `banda_p90`, `drivers` (top-5 por |SHAP|), `model_version`.

### `GET /v1/routes` — ranking de rotas

```bash
curl -H "Authorization: Bearer $ACCESS" \
  "http://localhost:8000/v1/routes?produto=ureia&corredor=BR-163"
```

Resposta: lista de rotas com `route_id`, `origem`, `destino`, `frete_r_per_ton`, `r_per_ton_km`, banda P10/P90 e `var_30d_pct`.

### `POST /v1/explain` — copiloto Claude explica a predição

Recebe o `prediction_id` retornado por `/v1/predict` e uma `question` opcional (livre, sanitizada). **O LLM só explica; nunca prevê frete** (guardrail de saída bloqueia valores inventados).

```bash
curl -X POST http://localhost:8000/v1/explain \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{
    "prediction_id": "<COLE_O_PREDICTION_ID_AQUI>",
    "question": "Por que o frete subiu em relação ao mês passado?"
  }'
```

Resposta: `prediction_id`, `explanation`, `source` (`llm` | `template` — cai para `template` sem `ANTHROPIC_API_KEY`).

### Alertas — feed e detecção

O detector de **spike de diesel** roda sobre os preços já ingeridos (`raw_diesel_prices`) e cria alertas `warn`/`critical` por UF. Detectores ANTT/CONAB são follow-up (TODO #30).

```bash
# Dispara a detecção (requer admin|analyst se autenticado)
curl -X POST http://localhost:8000/v1/alerts/detect \
  -H "Authorization: Bearer $ACCESS"

# Lê o feed do tenant (filtros opcionais)
curl -H "Authorization: Bearer $ACCESS" \
  "http://localhost:8000/v1/alerts?severity=critical&status=active"
```

## Como adicionar uma nova rota

Rotas ficam na tabela `routes` (ORM em `src/kairon/prediction/db_models.py`). Cada rota tem: `origem`, `destino`, `distancia_km`, `produto`, `corredor` (opcional), `piso_antt_r_per_ton` (opcional) e `tenant_id`.

Duas opções:

1. **Via script de seed (recomendado em dev):** edite `scripts/seed_synthetic_data.py`. Adicione a perna (`origem`, `destino`, `distancia_km`, `corredor`) em `_FERTI_LEGS` ou `_ALGODAO_LEGS` e ajuste a contagem (`N_FERTILIZANTE_ROUTES` / `N_ALGODAO_ROUTES`) se necessário. O script é **idempotente** (apaga e reinsere as rotas do tenant de dev). Depois rode `make seed`.
2. **Insert direto na tabela `routes`:** insira uma linha com os campos acima (o `piso_antt_r_per_ton` alimenta o piso do baseline). Use para dados de cliente que não devem ir para o seed sintético.

## Estrutura de diretórios

```
src/kairon/
  main.py          # FastAPI app factory — único ponto que monta todos os routers
  core/            # cross-cutting: config, logging, database, exceptions
  prediction/      # baseline + LightGBM (resíduo) + quantil + SHAP — /v1/predict, /v1/routes*
  simulation/      # Monte Carlo síncrono — /v1/simulate
  explanation/     # copiloto Claude + guardrails — POST /v1/explain
  alerts/          # detector de spike de diesel + feed/resolve — /v1/alerts*
  ingestion/       # ETL ANP (diesel)
  tenant/          # auth JWT + RBAC + rate limit + revogação — /v1/auth/*
  audit/           # log append-only (audit_events)
web/               # front Next.js (App Router, Tailwind, shadcn/ui)
scripts/           # seed_synthetic_data.py, train_baseline_model.py
migrations/        # Alembic (0001..0006)
docker/            # Dockerfiles (api)
tests/             # testes (também há tests/ por context em src/)
ui/                # LEGADO: UI Streamlit inicial — substituída por web/ (ver ADR-006)
```

## Frontend (Next.js)

O front vive em [`web/`](./web/) — **Next.js 16** (App Router, React 19), **Tailwind v4** e **shadcn/ui**, tema claro/escuro (padrão claro). Fala com a API via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); JWT no `localStorage` com refresh automático em `401`. Telas: dashboard, predição, ranking, previsão, simulação, alertas, copiloto, rotas & corredores e configurações (perfil/empresa/usuários).

```bash
cd web
npm install
npm run dev      # dev em :3000  (ou: npm run build && npm start)
```

## Secrets do repositório (CI/CD)

Configure no GitHub (Settings → Secrets and variables → Actions). A CI roda lint + typecheck + testes contra um Postgres real e **mantém `ANTHROPIC_API_KEY` vazia de propósito** (para testar a degradação do `/v1/explain`). Os secrets abaixo são usados por CI/CD e runtime de prod:

- `ANTHROPIC_API_KEY` — Claude Sonnet (copiloto)
- `SENTRY_DSN` — observabilidade de erros
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` — auth + Postgres gerenciado (prod)
- `BACKBLAZE_KEY_ID`, `BACKBLAZE_APP_KEY` — data lake (Backblaze B2)
- `RENDER_DEPLOY_HOOK` — hook de deploy

## Arquitetura em 5 linhas

1. **Front Next.js** e clientes chamam a **API FastAPI** (async, OpenAPI, Pydantic); auth é **JWT + RBAC**, **autenticação obrigatória** em todo `/v1` (sem anônimo).
2. Middleware injeta **correlation-id** + logging estruturado JSON; erros de domínio viram JSON; observability via **Sentry** + `/health` `/ready` `/metrics` (Prometheus).
3. **Bounded contexts** (core, ingestion, prediction, simulation, explanation, tenant, audit, alerts) só conversam via `core` — **zero import cross-context**.
4. Pipeline de predição: **baseline → resíduo LightGBM → banda de quantil → SHAP**; alertas por **detector de spike de diesel** sobre dados locais.
5. **Postgres/Supabase** é a fonte da verdade (isolamento multi-tenant na aplicação **+ RLS no banco**); **Backblaze B2** é o data lake. Detalhes e ADRs em [`ARCHITECTURE.md`](./ARCHITECTURE.md).

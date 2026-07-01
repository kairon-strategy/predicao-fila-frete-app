# Kairon Frete

## O que é

**Kairon Frete** é um SaaS + TaaS de **predição de frete rodoviário** para o agro brasileiro (fertilizante e grãos). O motor combina um **baseline determinístico**, um **LightGBM** que prevê o resíduo, **bandas de quantil** (P10/P90), explicação por **SHAP** e um **copiloto Claude Sonnet** que só _explica_ a predição — nunca prevê frete. É um monólito modular (cada pasta em `src/kairon/` é um _bounded context_ que vira microserviço na v2).

> **Meta MVP (jul–out/2026):** 3 clientes, R$ 180–280k ARR, 55 rotas ativas. Time: 1 engenheiro. Prioridade: **manutenibilidade sobre sofisticação**.

## Requisitos

- **Docker** + Docker Compose
- **Poetry** (para dev fora do container)
- **Python 3.12** (`~3.12`, ver `.python-version`)

## Setup rápido (clone → rodando em ≤ 15 min)

```bash
# 1. Variáveis de ambiente
cp .env.example .env
#    Preencha ANTHROPIC_API_KEY e SENTRY_DSN se quiser LLM real + Sentry.
#    Ambos são OPCIONAIS: sem eles a app degrada com elegância
#    (/v1/explain cai para template estático; Sentry fica desligado).

# 2. Dependências + pre-commit hooks (dev fora do container)
make install

# 3. Sobe toda a stack (api, ui, worker, postgres, redis)
make docker-up
#    O container `api` roda `alembic upgrade head` no boot — as migrations
#    são aplicadas automaticamente. Rodando fora do docker, use `make db-migrate`.

# 4. Popula o Postgres com dados SINTÉTICOS (55 rotas + diesel + histórico)
make seed
```

- **UI (Streamlit):** http://localhost:8501
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
| `make run-ui` | Sobe a UI Streamlit local em `:8501` |
| `make etl-anp` | Roda o ETL ANP uma vez (baixa CSV do diesel, normaliza, grava) |
| `make db-migrate` | Aplica migrations Alembic (`upgrade head`) |
| `make db-revision` | Cria migration: `make db-revision m="mensagem"` |
| `make seed` | Popula o Postgres com dados sintéticos |
| `make docker-up` | Sobe toda a stack (api, ui, worker, postgres, redis) |
| `make docker-down` | Derruba a stack (mantém volumes) |
| `make docker-nuke` | Derruba a stack **e apaga volumes** (reset total) |

## Endpoints

Superfície HTTP atual, agrupada por context. Prefixo `/v1` em tudo exceto os endpoints de ops. RBAC (`admin` | `analyst` | `viewer`) só entra **quando há token**; sem token a request resolve para o tenant default com papel `admin` (compat MVP — ver [Autenticação e papéis](#autenticação-e-papéis)).

### Ops (sem prefixo, sem auth)

| Método | Path | Auth | Propósito |
|--------|------|------|-----------|
| GET | `/health` | — | Liveness: o processo está de pé (não checa dependências). |
| GET | `/ready` | — | Readiness: Postgres + Redis obrigatórios; reporta `llm_configured`. |
| GET | `/metrics` | — | Métricas Prometheus (contadores por path-template). |

### Auth — context `tenant` (US-001)

| Método | Path | Auth | Propósito |
|--------|------|------|-----------|
| POST | `/v1/auth/login` | — | `{email, password}` → `{access_token, refresh_token, token_type}`. |
| POST | `/v1/auth/refresh` | refresh token | `{refresh_token}` → novo par de tokens. |
| GET | `/v1/auth/me` | Bearer | Dados do usuário autenticado (404 se anônimo). |

### Prediction — context `prediction`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/predict` | header `idempotency-key` obrigatório; se autenticado exige `admin`\|`analyst` (US-006); anônimo = tenant default, papel `admin` | Prevê frete (R$/t) para uma rota. |
| GET | `/v1/routes` | qualquer papel (inclui `viewer`) | Ranking de rotas; filtros `?produto=&corredor=`. |
| GET | `/v1/routes/{route_id}/history` | qualquer papel | Série histórica da rota; `?months=` (1–36, default 12). |

### Explanation — context `explanation`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/explain` | qualquer papel | Explica uma predição (`{prediction_id, question?}` → `{prediction_id, explanation, source}`). |

### Simulation — context `simulation`

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| POST | `/v1/simulate` | qualquer papel | Monte Carlo síncrono (`{base_freight, iterations}`). |
| POST | `/v1/simulate/async` | qualquer papel | Dispara Monte Carlo assíncrono → `202 {job_id, status}` (US-023). |
| GET | `/v1/simulate/{job_id}` | qualquer papel | Status/resultado de um job de simulação. |

### Alerts — context `alerts` (EPIC 8)

| Método | Path | Auth / RBAC | Propósito |
|--------|------|-------------|-----------|
| GET | `/v1/alerts` | qualquer papel | Feed de alertas do tenant; filtros `?severity=&type=&status=` (default `status=active`). |
| POST | `/v1/alerts/{id}/resolve` | qualquer papel | Marca um alerta como resolvido. |
| POST | `/v1/alerts/detect` | `admin`\|`analyst` | Roda os detectores (hoje: spike de diesel) e cria alertas novos. |

## Autenticação e papéis

Auth é **JWT** (access de 15 min + refresh de 7 dias), senha com **bcrypt**, RBAC de três papéis (`admin` | `analyst` | `viewer`) aplicado por `require_role`.

> **MVP — anônimo funciona.** Sem header `Authorization`, a request resolve para um `Principal` anônimo no **tenant default** com papel **`admin`** — os endpoints públicos de predição continuam full para a cotação rápida do trader. Assim que um token é enviado, o RBAC passa a valer normalmente (ex.: um `viewer` autenticado recebe `403` em `POST /v1/predict`).

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

Requer o header **`idempotency-key`** (mesma chave → mesma predição, **escopada por tenant**). Body: `origem`, `destino`, `produto`, `data`, `carga_ton` (opcional). Funciona anônimo; com token exige papel `admin`\|`analyst`.

```bash
curl -X POST http://localhost:8000/v1/predict \
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
curl "http://localhost:8000/v1/routes?produto=ureia&corredor=BR-163"
```

Resposta: lista de rotas com `route_id`, `origem`, `destino`, `frete_r_per_ton`, `r_per_ton_km`, banda P10/P90 e `var_30d_pct`.

### `POST /v1/explain` — copiloto Claude explica a predição

Recebe o `prediction_id` retornado por `/v1/predict` e uma `question` opcional (livre, sanitizada). **O LLM só explica; nunca prevê frete** (guardrail de saída bloqueia valores inventados).

```bash
curl -X POST http://localhost:8000/v1/explain \
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
curl "http://localhost:8000/v1/alerts?severity=critical&status=active"
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
  core/            # cross-cutting: config, logging, database, events (Redis), exceptions
  prediction/      # baseline + LightGBM (resíduo) + quantil + SHAP — /v1/predict, /v1/routes
  simulation/      # Monte Carlo (sync + job assíncrono) — /v1/simulate*
  explanation/     # copiloto Claude + guardrails — POST /v1/explain
  alerts/          # detector de spike de diesel + feed/resolve — /v1/alerts*
  ingestion/       # ETL ANP (diesel) + flow Prefect
  tenant/          # auth JWT + RBAC (require_role) — /v1/auth/*
  audit/           # log append-only
ui/                # UI Streamlit (app.py, pages/, components/)
scripts/           # seed_synthetic_data.py, train_baseline_model.py
migrations/        # Alembic
docker/            # Dockerfiles (api, ui, worker)
tests/             # testes (também há tests/ por context em src/)
```

## Secrets do repositório (CI/CD)

Configure no GitHub (Settings → Secrets and variables → Actions). A CI roda lint + typecheck + testes contra Postgres/Redis reais e **mantém `ANTHROPIC_API_KEY` vazia de propósito** (para testar a degradação do `/v1/explain`). Os secrets abaixo são usados por CI/CD e runtime de prod:

- `ANTHROPIC_API_KEY` — Claude Sonnet (copiloto)
- `SENTRY_DSN` — observabilidade de erros
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` — auth + Postgres gerenciado (prod)
- `BACKBLAZE_KEY_ID`, `BACKBLAZE_APP_KEY` — data lake (Backblaze B2)
- `RENDER_DEPLOY_HOOK` — hook de deploy

## Arquitetura em 5 linhas

1. **UI Streamlit** e clientes chamam a **API FastAPI** (async, OpenAPI, Pydantic); auth é **JWT + RBAC**, com anônimo liberado no MVP.
2. Middleware injeta **correlation-id** + logging estruturado JSON; erros de domínio viram JSON; observability via **Sentry** + `/health` `/ready` `/metrics` (Prometheus).
3. **Bounded contexts** (core, ingestion, prediction, simulation, explanation, tenant, audit, alerts) só conversam via `core`/eventos — **zero import cross-context**.
4. Pipeline de predição: **baseline → resíduo LightGBM → banda de quantil → SHAP**; alertas por **detector de spike de diesel** sobre dados locais.
5. **Postgres** é a fonte da verdade (isolamento multi-tenant na camada de aplicação); **Redis** faz cache/streams; **Backblaze B2** é o data lake. Detalhes e ADRs em [`ARCHITECTURE.md`](./ARCHITECTURE.md).

# Arquitetura — Kairon Frete

Documento vivo das decisões e da forma do sistema. Objetivo: um engenheiro entender o "porquê" em poucos minutos. Prioridade permanente: **manutenibilidade sobre sofisticação** (time de 1 pessoa).

## Decisões de arquitetura (ADRs)

| # | Decisão |
|---|---------|
| 001 | **Python 3.12** como linguagem principal. |
| 002 | **FastAPI** como framework HTTP (async + OpenAPI + Pydantic). |
| 003 | **Postgres** como source-of-truth. Sem NoSQL no MVP. |
| 004 | **LightGBM** como modelo principal. Sem deep learning no v1 e v2. |
| 005 | **Claude Sonnet** como LLM. Guardrails hard: o LLM **nunca prevê frete, só explica**. |
| 006 | **Next.js** (App Router, Tailwind, shadcn/ui) como UI do produto, em `web/`. _(Substituiu o Streamlit, que era o plano inicial de MVP.)_ |
| 007 | **Backblaze B2** como data lake (Backblaze CLI para dev local). |
| 008 | **Monólito modular** no MVP (deploy único, módulos separados por bounded context). Microserviços na v2. |
| 009 | Sem Retool, sem low-code, sem no-code. |
| 010 | **IaC** (Terraform/Pulumi) e **CI/CD** obrigatórios desde o dia 1. |
| 011 | Sem LangChain no MVP. Use o **SDK `anthropic` direto + Instructor + pgvector**. |
| 012 | **Toda lógica de backend via API FastAPI. SEM Supabase Edge Functions.** O Supabase é usado só como **Postgres gerenciado (source-of-truth) + Auth/Storage** — nunca como camada de compute. Um único runtime/linguagem (Python) para lógica, regras, ML e integrações. |
| 013 | **Engenharia limpa, sem anti-padrões.** Mantém o **monólito modular** (ADR-008) — **sem microserviços prematuros** (fragmentar cedo é over-engineering para um MVP de 1 engenheiro). Qualidade imposta por ruff + mypy strict + testes (≥70%) + fronteiras de contexto (zero import cruzado). Extração de serviços só na v2, quando houver escala/time real. |

## Diagrama em camadas (topo → base)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. CLIENTES / UI                                                      │
│    Front Next.js (:3000)  ·  clientes HTTP  ·  curl / integrações     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ HTTP (JSON)
┌───────────────────────────────▼─────────────────────────────────────┐
│ 2. API FastAPI (:8000) + MIDDLEWARE                                   │
│    correlation-id  ·  logging estruturado JSON  ·  guardrails         │
│    exception handlers (KaironError → JSON)                            │
│    ops: /health · /ready · /metrics (Prometheus)                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ include_router (único ponto: main.py)
┌───────────────────────────────▼─────────────────────────────────────┐
│ 2b. AUTH / RBAC (dependency por request)                             │
│    get_principal: JWT (Bearer) → Principal(tenant_id, role)          │
│    sem token → 401 (autenticação obrigatória)                       │
│    require_role(admin|analyst|viewer)  ·  toda query filtra tenant_id│
└───────────────────────────────┬─────────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────────┐
│ 3. BOUNDED CONTEXTS  (zero import cross-context)                      │
│  ┌───────────┐ ┌────────────┐ ┌─────────────┐                        │
│  │ prediction│ │ simulation │ │ explanation │                        │
│  │/v1/predict│ │/v1/simulate│ │ /v1/explain │                        │
│  │ /v1/routes│ │            │ │             │                        │
│  └───────────┘ └────────────┘ └─────────────┘                        │
│  ┌───────────┐ ┌────────────┐ ┌─────────────┐                        │
│  │ ingestion │ │  tenant    │ │   alerts    │                        │
│  │ (ETL ANP) │ │ (auth JWT) │ │ /v1/alerts  │                        │
│  │           │ │ /v1/auth/* │ │ (diesel)    │                        │
│  └───────────┘ └────────────┘ └─────────────┘                        │
│  ┌───────────┐                                                       │
│  │   audit   │                                                       │
│  │(append-only)│                                                     │
│  └───────────┘                                                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ (contexts só falam via ↓)
┌───────────────────────────────▼─────────────────────────────────────┐
│ 4. CORE (cross-cutting)                                               │
│    config  ·  logging  ·  database  ·  exceptions                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────────┐
│ 5. DADOS                                                              │
│    Postgres / Supabase (source of truth, RLS)                       │
│    Backblaze B2 (data lake)                                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────────┐
│ 6. EXTERNOS                                                           │
│    ANP (diesel)  ·  Anthropic Claude  ·  Sentry                     │
└─────────────────────────────────────────────────────────────────────┘
```

## A regra do monólito modular (ADR-008)

O sistema é **um único deploy**, mas cada pasta em `src/kairon/` é um _bounded context_ autônomo. A regra dura:

- **Contexts NÃO se importam entre si** para lógica de negócio. `prediction` não faz `import kairon.simulation`, etc.
- A comunicação acontece via **`core`** (config, database, logging — infra compartilhada). O `audit` é um context de suporte com uma interface fina (`audit.writer.write_event`) que outros contexts chamam para gravar a trilha append-only.
- **`main.py` é o único lugar** que conhece todos os contexts — ele monta os routers (`include_router`). Isso é o "deploy único" do monólito.

> **Nota (corte de MVP):** o barramento de eventos via Redis Streams (`core/events.py`) e o worker Prefect foram **removidos** — eram over-engineering para o MVP. Cache/streams/filas voltam só quando houver necessidade real. Redis não faz parte da stack atual.

Consequência prática: na v2, extrair um context para microserviço é recortar a pasta + trocar a chamada in-process por rede. Manter a disciplina de import agora é o que torna isso barato depois.

## Autenticação, RBAC e isolamento de tenant

Auth vive no context `tenant` e é aplicada como **dependency por request**, não como middleware bloqueante:

- **JWT** (`python-jose`, HS256): access token de **15 min** + refresh de **7 dias**. Claims: `sub` (user_id), `tenant_id`, `role`, `type`, `tv` (token_version). Senha com **bcrypt** (`hash_password`/`verify_password`, sem passlib).
- **`get_principal`** decodifica o `Authorization: Bearer <token>` num `Principal(tenant_id, role, user_id, authenticated)`. **Sem token → `401` (autenticação obrigatória)**; token inválido/expirado → `401`. Não existe mais principal anônimo.
- **RBAC** via `require_role(*allowed)`: dependency factory que devolve `403` se `principal.role` não estiver na lista. Papéis: `admin` | `analyst` | `viewer` (validados por enum na borda). `POST /v1/predict`, escritas de rota e `POST /v1/alerts/detect` exigem `admin|analyst`; gestão de usuários/empresa exige `admin`; leituras aceitam qualquer papel autenticado.
- **Registro por convite:** `POST /v1/auth/register` fica desligado por padrão (`allow_open_registration=False` → `403`); admins criam usuários via `POST /v1/auth/users`.
- **Revogação de sessão (token_version):** o claim `tv` é comparado com `users.token_version` no `/refresh`. **Logout** e **troca/reset de senha** incrementam o `token_version` → refresh tokens antigos passam a dar `401`; o access token vigente expira em ≤15 min. Mantém o caminho de request **stateless** (sem denylist).
- **Rate limit no login:** janela deslizante in-memory por IP+email (`login_max_attempts`/`login_window_min`) → `429`. MVP single-instance; trocar por store compartilhado ao escalar.
- **Auditoria:** `audit.writer.write_event` grava login, registro, criação de usuário, reset de senha e logout em `audit_events` (append-only).
- Seed cria 3 usuários demo no tenant default (senha `demo1234`): `admin@kairon.dev`, `analyst@kairon.dev`, `viewer@kairon.dev`.

**Isolamento multi-tenant tem duas camadas.** (1) Na **aplicação**: todo serviço recebe o `tenant_id` do `Principal` e **filtra explicitamente todas as queries por `tenant_id`** (predições, rotas, alertas, idempotência) — há teste e2e que verifica ausência de vazamento cross-tenant. (2) No **banco**: **RLS ativo** (migration `0005`, `ENABLE + FORCE ROW LEVEL SECURITY` em todas as tabelas `public`).

> **Sobre o RLS:** o objetivo do RLS aqui é **fechar a exposição via PostgREST/anon key do Supabase** (schema `public` sem RLS é lido por qualquer um com a anon key). Com RLS habilitado e **sem policies**, os papéis do PostgREST (`anon`/`authenticated`) veem zero linhas; a API conecta com o papel `postgres` (`BYPASSRLS`), então segue com acesso total. O isolamento **por tenant** continua sendo feito na aplicação (as policies por-tenant no banco são follow-up). Nota: o harness de teste usa `create_all` (não as migrations), então RLS não afeta os testes.

A **idempotência** do `/v1/predict` também é escopada por tenant: `UniqueConstraint(tenant_id, idempotency_key)` na tabela `predictions`.

## Inventário de endpoints por context

| Context | Método | Path | Auth / RBAC |
|---------|--------|------|-------------|
| ops | GET | `/health` `/ready` `/metrics` | público |
| tenant | POST | `/v1/auth/login` `/v1/auth/refresh` | público / refresh token |
| tenant | POST | `/v1/auth/register` | público **se habilitado** (senão `403`) |
| tenant | POST | `/v1/auth/logout` | Bearer |
| tenant | GET·PATCH | `/v1/auth/me` | Bearer |
| tenant | GET·POST·PATCH | `/v1/auth/users`(`/{id}`) | `admin` |
| tenant | GET·PATCH | `/v1/auth/tenant` | Bearer / `admin` |
| prediction | POST | `/v1/predict` | `idempotency-key` + `admin\|analyst` |
| prediction | GET | `/v1/routes` · `/v1/routes/{id}/history` · `/v1/routes/manage` | qualquer papel |
| prediction | POST·PUT·DELETE | `/v1/routes`(`/{id}`) | `admin\|analyst` |
| explanation | POST | `/v1/explain` | qualquer papel |
| simulation | POST | `/v1/simulate` | qualquer papel |
| alerts | GET | `/v1/alerts` | qualquer papel |
| alerts | POST | `/v1/alerts/{id}/resolve` | qualquer papel |
| alerts | POST | `/v1/alerts/detect` | `admin\|analyst` |

## Detecção de alertas (context `alerts`, EPIC 8)

Novo bounded context. No MVP roda **um** detector: `detect_diesel_spikes`, sobre a tabela `raw_diesel_prices` (dados que a ingestion ANP já grava — sem fonte externa nova):

- Agrupa por UF; compara o preço mais recente contra a média dos registros anteriores (baseline), exige `MIN_SAMPLES` (5) de histórico.
- Emite alerta `warn` a partir de **+4%** e `critical` a partir de **+8%** de alta percentual.
- Alertas são persistidos por tenant (`Alert`, migration `0003`), consumidos via `GET /v1/alerts` (ordenado por severidade e recência) e resolvidos via `POST /v1/alerts/{id}/resolve`. `POST /v1/alerts/detect` dispara a rodada sob demanda.

> **Follow-up honesto:** os detectores **ANTT** (US-048) e **CONAB** (US-049) dependem de fontes externas e ainda **não existem** (TODO #30). **Não há e-mail nem agendamento de alertas** — a detecção só roda quando `POST /v1/alerts/detect` é chamado.

## Pipeline do modelo (context `prediction`)

Quatro etapas, cada uma com _fallback_ para a anterior (o baseline **sempre** funciona):

```
1. BASELINE (determinístico)   frete = (custo_combustível + custo_operacional) × sazonalidade,
   models/baseline.py          nunca abaixo do piso ANTT. Sem dependência de modelo treinado.
        │
        ▼
2. LightGBM RESIDUAL           prevê o RESÍDUO sobre o baseline (não o valor absoluto).
   models/lightgbm_residual.py frete_final = baseline + resíduo previsto.
        │
        ▼
3. BANDA DE QUANTIL            P10 / P90 em torno da predição (incerteza calibrada).
   models/quantile.py          → banda_p10, banda_p90.
        │
        ▼
4. SHAP                        top-5 drivers por |SHAP| (feature, valor, direção up/down).
   shap_explainer.py           Sem SHAP disponível → drivers derivam dos componentes do baseline.
```

Se LightGBM ou SHAP falharem, a resposta ainda sai (degrada para o baseline). Esse é o "piso de confiança" — coerente com "manutenibilidade sobre sofisticação".

Idempotência: `/v1/predict` exige o header `idempotency-key`. A tabela `predictions` tem `UniqueConstraint(tenant_id, idempotency_key)` — mesma chave devolve a mesma predição.

## O guardrail do LLM (ADR-005, context `explanation`)

O copiloto Claude Sonnet **só explica uma predição já existente; nunca prevê frete**. Isso é imposto por código (`explanation/guardrails.py`), não por confiança no prompt:

- **`sanitize_input`** — remove HTML, markdown e comandos de sistema do input livre (anti prompt-injection).
- **`enforce_output`** — valida a saída do LLM **antes** de devolver ao cliente:
  - máx. 500 palavras;
  - a resposta deve citar a rota (origem ou destino) **e** ao menos um valor fornecido pelo motor;
  - **qualquer valor monetário de frete (R$/t) que não bata com os valores fornecidos pelo motor é bloqueado** (`GuardrailViolation` + alerta via log de erro/Sentry).

Sem `ANTHROPIC_API_KEY`, o `/v1/explain` degrada para um **template estático** (`source: template`) em vez de crashar.

## Observações operacionais

- **Observability:** `structlog` (JSON) + `Sentry` (opcional) + `/health` (liveness, não checa deps), `/ready` (Postgres obrigatório; reporta `llm_configured` sem bloquear) e `/metrics` (Prometheus, contadores por path-template para evitar explosão de cardinalidade).
- **Migrations:** `0001` schema inicial · `0002` users · `0003` alerts · `0004` users.name · `0005` RLS (enable+force) · `0006` users.token_version. Aplicadas com `make db-migrate` (`alembic upgrade head`). Nota: o harness de teste usa `create_all`, não as migrations (por isso RLS e defaults de servidor não afetam os testes).
- **Banco em produção:** Supabase (Postgres gerenciado). A app conecta via pooler (asyncpg + `statement_cache_size=0`); DDL/migrations são aplicadas com a connection string do projeto. Ver ADR-012.
- **Qualidade:** Ruff (lint+format), mypy strict, pytest com cobertura mínima de 70% — ver [`CONTRIBUTING.md`](./CONTRIBUTING.md).

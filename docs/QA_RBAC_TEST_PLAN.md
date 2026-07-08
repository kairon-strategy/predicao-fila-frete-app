# Plano de Testes — RBAC dinâmico (Perfis & Permissões)

**Build alvo:** `main` @ HEAD `85ddde9` (ou superior)
**Feature:** perfis (roles) configuráveis por tenant + matriz de permissões; enforcement por permissão em todos os endpoints; tela admin em Configurações → **Perfis**.
**Prioridade:** P0 (bloqueia) · P1 (antes do piloto) · P2 (polimento).

---

## 0. Setup

1. `git checkout main && git pull` (HEAD ≥ `85ddde9`).
2. `.env` (raiz): `LOGIN_WINDOW_MIN=1` (evita travar no rate-limit).
3. Banco + API:
   ```bash
   make db-migrate                                    # inclui migration 0007 (roles)
   poetry run python scripts/seed_synthetic_data.py
   poetry run python scripts/seed_demo_users.py       # tenant B + confirma perfis
   make run-api                                        # :8000
   ```
4. Front: `cd web && rm -rf .next && npm run dev` (:3000) · hard refresh no browser.
5. Credenciais (senha `demo1234`, exceto onde indicado):
   - Tenant A `Kairon Dev`: `admin@kairon.dev` · `analyst@kairon.dev` · `viewer@kairon.dev`
   - Tenant B `Empresa Beta`: `beta@empresa.com` (senha `beta1234`)

> Dica p/ os testes de backend: pegue o token com
> `AT=$(curl -s -X POST localhost:8000/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@kairon.dev","password":"demo1234"}' | jq -r .access_token)`

---

## Suíte A — Catálogo & perfis padrão (backend)

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| A1 | P1 | `GET /v1/auth/permissions` (admin) | **200**, **14** permissões (key/group/label) |
| A2 | P0 | `GET /v1/auth/roles` (admin) | **200**; contém `admin`/`analyst`/`viewer` com `is_system=true`; `user_count` coerente (admin≥1) |
| A3 | P0 | `GET /v1/auth/roles` com token **viewer** | **403** (viewer não tem `roles:read`) |
| A4 | P1 | `GET /v1/auth/me` (admin) | inclui `permissions` (14 chaves) |

## Suíte B — CRUD de perfil (backend)

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| B1 | P0 | admin `POST /v1/auth/roles` `{"name":"Operador","permissions":["routes:read","predict:run"]}` | **201**, retorna `slug`, `is_system=false`, 2 permissões |
| B2 | P1 | admin `PATCH /v1/auth/roles/{id}` `{"permissions":["routes:read"]}` | **200**, permissões atualizadas |
| B3 | P1 | admin `DELETE /v1/auth/roles/{id}` (perfil custom **sem** usuários) | **204** |
| B4 | P0 | admin `DELETE` de um perfil **de sistema** (admin/analyst/viewer) | **422** ("não pode ser excluído") |
| B5 | P1 | admin `DELETE` de perfil custom **em uso** por 1 usuário | **422** ("em uso por N usuário(s)") |
| B6 | P1 | admin `POST /v1/auth/roles` com `permissions:["xxx:invalida"]` | **422** (permissão inválida) |
| B7 | P1 | **viewer** `POST /v1/auth/roles` | **403** (sem `roles:write`) |

## Suíte C — Enforcement por permissão (backend) ⭐

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| C1 | P0 | admin cria perfil `Leitor` só com `routes:read`; cria usuário com esse perfil; usuário loga; `GET /v1/auth/me` | `permissions == ["routes:read"]` |
| C2 | P0 | esse usuário: `GET /v1/routes` | **200** |
| C3 | P0 | esse usuário: `POST /v1/routes` (rota válida) e `POST /v1/predict` | **403** em ambos |
| C4 | P0 | admin concede `routes:write` ao perfil (`PATCH /roles`); o usuário faz `POST /v1/auth/refresh`; usa o novo access token em `POST /v1/routes` | **201** (permissão passou a valer após refresh) |
| C5 | P1 | **Regressão matriz**: admin/analyst/viewer nas ações-chave | admin=tudo; analyst=predict/rotas-escrita/alertas-detect ✔, users/tenant ✖(403); viewer=só leitura, escrita ✖(403) |

## Suíte D — Tela Perfis & Permissões (frontend) ⭐

Logar como **admin** → Configurações.

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| D1 | P0 | Ver as abas de Configurações | Aparece a aba **"Perfis"** (ícone chave) |
| D2 | P1 | Abrir aba Perfis | Tabela com admin/analyst/viewer, badge **"sistema"**, nº de permissões e nº de usuários |
| D3 | P0 | "Novo perfil" → nome "Operador Log" → marcar algumas permissões na **matriz** (agrupada por área) → Salvar | Toast de sucesso; perfil aparece na lista com a contagem certa |
| D4 | P1 | Editar um perfil → marcar/desmarcar permissões → Salvar | Persiste (reabrir mostra o novo conjunto) |
| D5 | P1 | Excluir o perfil custom (sem usuários) | Some da lista. Perfis de sistema **não têm** botão excluir |
| D6 | P0 | Aba **Usuários** → criar/editar usuário → dropdown de perfil | Lista os **perfis do tenant** (incluindo o novo "Operador Log"), não os 3 fixos |
| D7 | P0 | Deslogar → logar como **viewer** → Configurações | A aba **"Perfis" NÃO aparece** |

## Suíte E — Isolamento por tenant

| ID | Prio | Passos | Esperado |
|---|---|---|---|
| E1 | P0 | Logar `beta@empresa.com` (tenant B) → `GET /v1/auth/roles` | Só os perfis do **tenant B**; não vê perfis nem usuários do tenant A |
| E2 | P1 | Perfil custom criado no tenant A | **Não** existe no tenant B (perfis são por empresa) |

---

## NÃO flagar (por design / fora de escopo)

- **Propagação:** mudança de permissão de um perfil vale no **próximo login/refresh** do usuário (o access token carrega as permissões; expira em ≤15 min). É a decisão de arquitetura (hot path stateless). Trocar o **perfil de um usuário** já revoga a sessão dele na hora.
- **Perfis de sistema** (admin/analyst/viewer): nome fixo e não deletáveis — permissões editáveis. Proposital.
- **Catálogo de permissões é fixo** (14 chaves definidas pelo código): o usuário cria perfis e combina permissões existentes, não inventa permissões novas. Proposital.
- Valor do `/predict` (baseline) e MAPE "—": dependem do modelo treinado (adiado).

## Critérios de saída

- ✅ Liberar: todos os **P0** das suítes A–E passam (com destaque para C — enforcement — e D — tela).
- ⚠️ Bloqueia: qualquer falha de enforcement (permissão concedida/negada não refletindo no acesso) ou vazamento entre tenants.

---

**Cobertura automatizada já existente:** `tests/e2e/test_roles_rbac.py` (5 casos) cobre A/B/C no backend — rode `make test` para confirmar (82 testes verdes).

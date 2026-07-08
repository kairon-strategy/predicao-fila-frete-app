# Guia de Deploy — Kairon Frete (orientação para configurar tudo)

> Documento autossuficiente para **configurar o deploy de produção** do zero.
> Repo: `kairon-strategy/predicao-fila-frete-app` · branch `main`.
> Público-alvo: agente/pessoa que vai executar (ex.: Claude Cowork).

## Arquitetura do deploy (quem vai onde)

```
[ Navegador ] → Vercel (Next.js, pasta web/) → Render (FastAPI, Docker) → Supabase (Postgres)
```

| Componente | Onde | Origem no repo |
|---|---|---|
| **Front** (Next.js 16) | **Vercel** | `web/` |
| **API** (FastAPI) | **Render** (Docker) | `docker/Dockerfile.api` |
| **Banco** (Postgres) | **Supabase** | já existe — projeto `aoaaakqdjskxrvmbnyme` |

**Regras que não mudam (ADRs):** a API FastAPI é a única camada de lógica (ADR-012 — nada de Edge Functions); o Supabase é só Postgres gerenciado. NÃO deployar `docker/Dockerfile.ui` (Streamlit, **obsoleto**) nem `docker/Dockerfile.worker` (Prefect, **removido do MVP**). O `.github/workflows/deploy.yml` (Docker Hub → Render) é um pipeline **antigo** e **não** é usado neste guia (vamos de build direto do GitHub no Render).

---

## ⚠️ Ordem importa (dependência cruzada de URL)

O front precisa da URL da API, e a API precisa liberar o CORS pra URL do front. Sequência:

1. **API no Render** → gera `https://<api>.onrender.com`
2. **Front na Vercel** com `NEXT_PUBLIC_API_URL = https://<api>.onrender.com`
3. **Voltar no Render** e setar `CORS_ORIGINS = https://<front>.vercel.app` → redeploy da API
4. **Verificar** (seção final)

---

## Pré-requisitos / segredos a gerar

- Conta **Render** (com acesso ao repo GitHub `kairon-strategy/predicao-fila-frete-app`).
- Conta **Vercel** (time "Kairon Strategy") — projeto já sendo criado via import do GitHub.
- **Connection string do Supabase** (Session pooler): já está no `.env` local como `SUPABASE_DB_URL`. Formato asyncpg:
  `postgresql+asyncpg://postgres.aoaaakqdjskxrvmbnyme:<SENHA>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres`
- 🔑 **Gerar `JWT_SECRET`**: `openssl rand -hex 32`
- 🔑 **ROTACIONAR a senha do banco** no Supabase (Dashboard → Database → Reset password) — a atual já apareceu em chat. Usar a nova na `DATABASE_URL`.

O schema do Supabase **já está aplicado** (Alembic `0006`, RLS ativo, dados de demo populados). **Não precisa rodar migrations** a menos que criem um banco novo (aí: `alembic upgrade head` com a `DATABASE_URL` apontando pro Supabase).

---

## PARTE 1 — API no Render (Docker, build do GitHub)

1. Render → **New → Web Service** → conectar o repo `kairon-strategy/predicao-fila-frete-app`.
2. Configuração:
   - **Runtime:** Docker
   - **Dockerfile Path:** `docker/Dockerfile.api`
   - **Docker Build Context Directory:** `.` (raiz do repo)
   - **Branch:** `main`
   - **Region:** escolher a mais próxima do Supabase (o projeto está em **South America / São Paulo** → usar região equivalente para baixar latência; se o Render não tiver SA, usar a mais próxima).
   - **Health Check Path:** `/health`
   - **Instance Type:** Starter (o suficiente pro MVP).
3. **Start command / porta:** o Dockerfile expõe a porta **8000** com `uvicorn ... --port 8000`. O Render injeta `$PORT` e espera que o serviço escute nela. Fazer UMA das opções:
   - **(recomendado)** sobrescrever o Docker Command no Render para:
     `uvicorn kairon.main:app --host 0.0.0.0 --port $PORT`
   - ou setar a env `PORT=8000` e configurar a porta do serviço como 8000.
4. **Environment Variables** (Render → Environment):

   | Chave | Valor | Obrigatória |
   |---|---|---|
   | `APP_ENV` | `production` | sim |
   | `DATABASE_URL` | `postgresql+asyncpg://postgres.aoaaakqdjskxrvmbnyme:<SENHA_NOVA>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres` | **sim** |
   | `JWT_SECRET` | saída do `openssl rand -hex 32` | **sim** |
   | `CORS_ORIGINS` | `https://<front>.vercel.app` (preencher na PARTE 3) | **sim** |
   | `ALLOW_OPEN_REGISTRATION` | `false` | sim (invite-only) |
   | `LOG_LEVEL` | `INFO` | não |
   | `LOGIN_MAX_ATTEMPTS` | `5` | não (default) |
   | `LOGIN_WINDOW_MIN` | `5` | não (default) |
   | `ANTHROPIC_API_KEY` | chave da Anthropic | não (sem ela, `/v1/explain` cai p/ template) |
   | `ANTHROPIC_MODEL` | `claude-sonnet-5` | não |
   | `SENTRY_DSN` | DSN do Sentry | não |
   | `MODEL_VERSION` | `baseline-0.1.0` | não |

   > **Nota técnica (já resolvida no código):** o app detecta o pooler do Supabase e conecta com `statement_cache_size=0` + `ssl=require` (asyncpg + Supavisor). Não precisa configurar nada extra.

5. Deploy. Ao ficar verde, testar:
   `curl https://<api>.onrender.com/health` → `{"status":"ok",...}`
   `curl https://<api>.onrender.com/ready` → `{"ready":true,"postgres":true,...}`

---

## PARTE 2 — Front na Vercel (Next.js)

No dashboard "New Project" (import do GitHub):

1. **Root Directory:** clicar **Edit → selecionar `web`** ← crítico (senão a Vercel detecta FastAPI na raiz).
2. **Framework Preset:** **Next.js** (deve auto-detectar ao apontar root para `web`).
3. **Build & Output:** deixar o padrão (`next build`).
4. **Environment Variables:**

   | Chave | Valor |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<api>.onrender.com` (URL da PARTE 1, **sem barra no fim**) |

5. **Deploy.** Anotar a URL gerada (ex.: `https://predicao-fila-frete-app.vercel.app`).

> A cada `git push` na `main`, a Vercel redeploya sozinha (integração GitHub). O Vercel CLI é **opcional**.

---

## PARTE 3 — Amarrar CORS (fechar o ciclo)

1. Voltar no **Render → Environment** e setar `CORS_ORIGINS` = a URL da Vercel (da PARTE 2), ex.:
   `CORS_ORIGINS=https://predicao-fila-frete-app.vercel.app`
   (aceita lista separada por vírgula se houver domínio custom + preview).
2. **Redeploy** da API no Render (Manual Deploy → Deploy latest).
3. Se depois adicionarem **domínio próprio** na Vercel, incluir esse domínio no `CORS_ORIGINS` também.

> O CORS já expõe o header `Retry-After` (para o front ler o rate-limit). Nada a fazer.

---

## PARTE 4 — Verificação (smoke de produção)

Com `API=https://<api>.onrender.com` e `FRONT=https://<front>.vercel.app`:

```bash
# 1. API viva + banco
curl -s $API/health           # {"status":"ok",...}
curl -s $API/ready            # {"ready":true,"postgres":true,...}

# 2. Login funciona (usuário demo já existe no Supabase)
curl -s -X POST $API/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@kairon.dev","password":"demo1234"}'   # 200 + tokens

# 3. Sem token -> 401 (auth obrigatória)
curl -s -o /dev/null -w '%{http_code}\n' $API/v1/auth/users  # 401
```

No browser: abrir `$FRONT` → login `admin@kairon.dev` / `demo1234` → dashboard deve carregar (KPIs, 2 alertas, ranking), `/simulacao` deve rodar o Monte Carlo. Se o login falhar com erro de rede/CORS → revisar PARTE 3 (CORS_ORIGINS) e `NEXT_PUBLIC_API_URL`.

---

## Checklist final

- [ ] Senha do banco **rotacionada** no Supabase e refletida na `DATABASE_URL`
- [ ] `JWT_SECRET` forte gerado (não usar o default de dev)
- [ ] API Render verde: `/health` e `/ready` (postgres:true)
- [ ] Front Vercel com Root Directory = `web` e `NEXT_PUBLIC_API_URL` correto
- [ ] `CORS_ORIGINS` no Render = URL da Vercel, API redeployada
- [ ] Login end-to-end no browser funciona
- [ ] `ALLOW_OPEN_REGISTRATION=false` (invite-only) confirmado

## Notas / armadilhas conhecidas

- **NÃO** deployar `Dockerfile.ui` (Streamlit) nem `Dockerfile.worker` (Prefect) — obsoletos.
- **Vercel detecta FastAPI** se o Root Directory não for `web` — sempre `web`.
- **Free tier do Render dorme** após inatividade (cold start ~30-50s na 1ª request). Para demo/piloto, considerar plano pago ou um ping keep-alive.
- **Latência do banco:** manter API e Supabase na **mesma região** (ou próximas) — o pooler está em São Paulo.
- O `/v1/predict` usa **baseline heurístico** (modelo LightGBM ainda não treinado — decisão de produto). Estrutura pronta; valor real depende de treinar com dado do cliente.

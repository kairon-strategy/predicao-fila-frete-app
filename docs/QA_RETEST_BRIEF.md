# Re-teste do Kairon Frete MVP — build atualizado (correções + features novas)

> Referência: relatório `QA_Report_Kairon_Frete_MVP.md` (03/JUL/2026). HEAD atual: `8057d38`.

Obrigado pelo relatório de QA — foi muito útil. Um ponto importante antes de tudo:
**a auditoria anterior rodou num build desatualizado** (o relatório menciona "Next 15"
mas o projeto é Next **16**, e o P0-1 "auth aceita qualquer credencial" não se reproduz
no código atual). Provavelmente foi um `next dev` antigo em cache. Por isso peço um
**re-teste do zero**.

## Setup do re-teste (importante)

1. `git pull` na branch `main` (HEAD atual `8057d38`).
2. Backend: `make db-migrate && make run-api` (API em `:8000`, apontando pro Supabase).
3. Front: `cd web && rm -rf .next && npm run dev` (**apague o `.next`** para evitar cache velho) → `:3000`.
4. No browser: **hard refresh (Cmd+Shift+R)** e, se possível, aba anônima.
5. Login: `admin@kairon.dev` / `demo1234`.

## Itens para RE-VERIFICAR (corrigidos ou que eram falso-positivo)

| ID | Status | Como confirmar |
|---|---|---|
| **P0-1** auth aceita tudo | ❌ era falso (build velho) | login vazio → **422**; inválido → **401**; senha errada → **401**; correto → **200** |
| **P0-2** form GET / senha na URL | ✅ corrigido | `<form method="post">`, `preventDefault` no submit |
| **P0-3** inputs sem `required`/`name` | ✅ corrigido | email/senha têm `name`, `required`, senha `minLength=8` |
| **P0-4** itens v2 → `/taas` 404 | ❌ era falso | itens "Compliance · v2" são `disabled`, não navegam |
| **P0-5 / P1-12** 404 sem branding | ✅ corrigido | acesse uma URL inexistente **logado** → página 404 Kairon em PT + "Voltar ao dashboard" |
| **P0-6** credenciais demo expostas | ✅ corrigido | somem em produção (`NODE_ENV=production`); só aparecem em dev |
| **P1-4** KPI cards bege no dark | ❌ era falso | usam token `bg-card`; alternam com o tema |
| **P1-6 / P1-7** Var 30d / R$·t·km "constantes" | ✅ corrigido | agora **20** e **34** valores distintos em 62 rotas (efeito de corredor) |
| **P1-8** chip do usuário sem espaço/aria | ✅ corrigido | `aria-label="email, papel role"` + avatar `aria-hidden` |
| **P1-9** sidebar não responsiva | ❌ era falso | sidebar é `hidden lg:flex` + hamburger (Sheet) no mobile |
| **P1-10** email das Configurações vazio | ❌ era falso | campo puxa de `/v1/auth/me` (`value=user.email`) |
| **P2-6** subtitle "fertilizante + algodão" | ✅ corrigido | agora "fertilizante + algodão + grão" |

## FEATURES NOVAS para testar

- **P1-11 — Simulação Monte Carlo por segmento** (tela `/simulacao`): 3 sliders
  (**Diesel −10..+30%**, **Safra −25..+5%**, **Piso ANTT 0..+15%**). Verifique que
  cada segmento (fertilizante/algodão/grão) reage diferente e mostra banda
  P10/P50/P90. Ex.: diesel +20%, safra −15%, piso +5% → fertilizante ~+12%,
  algodão ~+7%, grão ~+2% (banda mais larga).
- **Alertas populados**: dashboard e `/alertas` mostram **2 alertas ativos**
  (crítico MT, aviso GO) gerados pelo detector real de spike de diesel.
- **Auth endurecida** (novo): registro por convite (`/register` → 403), logout
  revoga sessão, rate-limit no login (6ª tentativa errada → 429), reset de senha
  por admin em Configurações → Usuários.
- **Tema claro** agora é o **padrão** (era escuro).

## NÃO re-flagar (decisão de produto / adiado)

- **P1-1/2/3 (DM Serif Display / serif italic):** removemos a fonte serifada
  **por decisão de produto** — o Inter é intencional. Não é bug.
- **P1-5 (MAPE em "—") e o valor do `/predict`:** dependem do modelo LightGBM
  treinado, **adiado de propósito**. O baseline é honesto (não inventamos número).
  Ranking, simulação e alertas é que carregam o valor por ora.
- **P2-1/P2-2 (copiloto chat + grounding):** dependem do LLM ligado
  (`ANTHROPIC_API_KEY`), fora do escopo desta rodada.

## Ainda em aberto (válidos, próxima rodada)

P2-3 (filtro de período nos alertas), P2-4 (breadcrumb), P2-5 (CTA em empty states).
Sem pressa.

---

Qualquer coisa que reproduza com o build atualizado, manda o commit/screenshot.

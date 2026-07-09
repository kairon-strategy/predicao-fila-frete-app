# Governança e Segurança de IA — Kairon Frete

**Escopo:** uso da API da OpenAI (e do fallback Anthropic) pelo copiloto de
explicação (`context explanation`, endpoint `POST /v1/explain`).
**Última revisão:** 2026-07-09 · **Responsável:** Engenharia (solo) ·
**Classificação do documento:** interno.

> Este documento é a fonte de verdade dos critérios que autorizam (e limitam) o
> uso de LLM externo no produto. Toda mudança que amplie o que é enviado ao
> provedor exige atualização aqui **antes** do merge (ver §9).

---

## 1. Princípios

1. **Minimização de dados** — só sai do nosso ambiente o estritamente necessário
   para explicar uma cotação já calculada. Nunca "por conveniência".
2. **A IA não decide, só explica** — o LLM jamais gera número de frete. O motor
   estatístico prevê; o LLM traduz em linguagem de negócio.
3. **Degradação graciosa** — falha ou ausência de LLM nunca derruba o produto:
   OpenAI → Claude → template determinístico.
4. **Zero dado pessoal (PII)** no prompt — sem nome, e-mail, senha ou usuário.
5. **Auditável** — toda explicação servida é registrada.

---

## 2. Classificação de dados — o que PODE e o que NÃO PODE ir ao provedor

**Enviado ao LLM (dados operacionais, sem PII):** apenas os campos de **uma**
predição, buscada por `prediction_id` e filtrada por `tenant_id`:

| Campo | Sensibilidade |
|---|---|
| origem, destino, produto | Operacional |
| data_alvo | Operacional |
| frete_r_per_ton, banda_p10, banda_p90 | Comercial (do próprio tenant) |
| model_version | Técnico |
| drivers (feature, direction, shap_value) | Técnico |
| pergunta do usuário (sanitizada) | Livre — passa por §4 |

**Proibido enviar (bloqueado por design):**

- ❌ PII: `users` (nome, e-mail, hash de senha), qualquer dado de pessoa física.
- ❌ Identificadores internos: `tenant_id`, `prediction_id`, `idempotency_key`.
- ❌ Outras tabelas: `routes`, `roles`, preços ANP/diesel brutos, `alerts`.
- ❌ Dados de **outro tenant** (query travada por `tenant_id` — isolamento US-004).
- ❌ Campos não usados da predição: `carga_ton`, `distancia_km`, `created_at`.

Qualquer campo novo no prompt é uma **mudança de escopo** e segue §9.

---

## 3. Gestão de segredos (chaves de API)

| Critério | Status |
|---|---|
| Chave **fora do Git** (arquivo gitignored + `sync:false` no Render) | ✅ implementado |
| Chave **nunca** em código, log, print ou chat | ✅ política |
| Chave de produção definida só no painel do Render | ✅ implementado |
| Chave rotacionada imediatamente após qualquer exposição | ✅ executado (jul/2026) |
| Rotação periódica programada (ex.: a cada 90 dias) | ☐ definir cadência |
| Chave com **escopo mínimo** (project key, não admin key) | ✅ usar `sk-proj-…` |
| Chave separada por ambiente (dev ≠ prod) | ☐ recomendado |

**Procedimento de rotação/vazamento:** ver §10.

---

## 4. Guardrails técnicos (anti-injeção e anti-alucinação)

Implementados em `explanation/guardrails.py` — funções puras, testadas:

- **`sanitize_input`** (antes de montar o prompt): **redige PII/LGPD** (CPF, CNPJ,
  e-mail, telefone, CEP → `[dado pessoal removido]`), remove HTML, markdown e
  comandos de sistema (`ignore previous`, `jailbreak`, `sudo`, `rm -rf`, …).
- **`scan_pii`**: detecta o **tipo** de PII presente (para observabilidade — §8),
  sem nunca registrar o valor.
- **Prompt com regras invioláveis**: "NUNCA calcule/invente valor", "cite rota,
  data e valor", "máx. 180 palavras, sem markdown".
- **`enforce_output`** (antes de devolver/cachear) — bloqueia (`GuardrailViolation`
  + log de erro/Sentry) se a resposta:
  1. exceder 500 palavras;
  2. **não** citar a rota **e** ao menos um valor fornecido;
  3. contiver **qualquer** R$/t que divirja de `frete/p10/p90` (tolerância R$ 1,00)
     — impede o LLM de "prever" um número próprio.

---

## 5. Isolamento multi-tenant

- A predição só é lida se pertencer ao `tenant_id` do token (senão 404).
- O prompt só contém dados daquele tenant. **Não há caminho** para um tenant ver
  ou vazar dados de outro via copiloto.

---

## 6. Retenção, privacidade e LGPD

- **Papéis LGPD:** Kairon é **controlador**; OpenAI/Anthropic são **operadores**
  (sub-operadores de tratamento).
- **Redação de PII na entrada:** ✅ implementado — CPF, CNPJ, e-mail, telefone e
  CEP digitados na pergunta livre são redigidos **antes** de sair do nosso
  ambiente (§4), com observabilidade do tipo redigido (§8).
- **Base do baixo risco:** os dados enviados são **operacionais/comerciais do
  próprio cliente, sem dado pessoal** — não há tratamento de PII no LLM.
- **Retenção no provedor:** hoje a Responses API opera com `store` no default
  (~30 dias do lado da OpenAI). Decisão registrada: **mantido por ora**.
  - ☐ Opção de endurecer: `store=False` (uma linha em `openai_client.py`) e/ou
    negociar **ZDR (Zero Data Retention)** com a OpenAI.
- ☐ **DPA (Data Processing Agreement)** assinado com OpenAI e Anthropic — providenciar antes de onboarding de cliente pagante.
- ☐ Registrar o tratamento no **RIPD/registro de operações** quando escalar.

---

## 7. Disponibilidade, custo e limites

| Critério | Status |
|---|---|
| Fallback OpenAI → Claude → template | ✅ implementado |
| Retry com backoff (3 tentativas, tenacity) | ✅ implementado |
| Cache de explicação (TTL 1h) — corta custo e reexposição | ✅ implementado |
| `max_output_tokens` limitado (1024) | ✅ implementado |
| Teto de caracteres da pergunta (`llm_max_input_chars=800`) | ✅ implementado |
| **Timeout explícito** por chamada (`llm_timeout_seconds=30`) + retry do SDK off | ✅ implementado |
| **Rate limit por tenant** no `/v1/explain` (`explain_max_per_min=30`, 429) | ✅ implementado |
| **Teto de gasto / alerta de budget** na conta OpenAI | ☐ configurar no painel |

---

## 8. Observabilidade e auditoria

- **Auditoria:** cada explicação gera evento `explanation.served` em `audit_events`
  (source = `llm`/`template`, prediction_id, tenant_id). ✅
- **Observabilidade LGPD:** quando PII é redigida na entrada, gera log
  `explanation.pii_redacted` + evento de auditoria com o **tipo** de PII (nunca o
  valor). Permite medir exposição sem armazenar dado pessoal. ✅
- **Logs não contêm o conteúdo do prompt** — só `prediction_id` e `source`. ✅
- **Violações de guardrail** viram `log.error("guardrail.violation")` (captável no
  Sentry). ✅
- ☐ Dashboard de custo/uso por tenant (quando houver volume).

---

## 9. Processo de mudança (o que exige aprovação)

Exige atualizar este documento **e** revisão explícita **antes do merge**:

1. Enviar **qualquer campo novo** ao LLM (§2).
2. Trocar de provedor ou de modelo.
3. Mudar retenção (`store`), timeout, limites de token ou de custo.
4. Expor o copiloto a um novo tipo de dado/entidade.

Mudanças que **não** tocam o que sai para o provedor (ex.: ajuste de texto do
template dentro do escopo atual) seguem o fluxo normal de PR.

---

## 10. Resposta a incidentes — vazamento de chave

1. **Revogar** a chave exposta em platform.openai.com/api-keys (imediato).
2. **Gerar** chave nova (project-scoped) e atualizar no painel do Render (dispara redeploy).
3. Atualizar `deploy-secrets.local.env` (local, gitignored).
4. Conferir **uso/faturamento** na OpenAI por atividade anômala.
5. Registrar o incidente (data, causa, ação) — histórico abaixo.

**Histórico:** jul/2026 — chave `sk-proj-…` exposta em chat de desenvolvimento →
revogada e rotacionada no mesmo dia; nenhum uso anômalo detectado.

---

## 11. Checklist de conformidade (resumo)

**Implementado ✅:** minimização de dados · sem PII no prompt · **redação de PII
na entrada (LGPD)** · **observabilidade de PII redigida** · isolamento por tenant ·
sanitização de input · validação de output (anti-alucinação) · **fallback para
template se a saída violar guardrail** · degradação graciosa (OpenAI→Claude→template) ·
retry (tenacity, SDK off) · **timeout explícito (30s)** · cache · **cap de input
(800 chars)** · **rate limit por tenant no explain (30/min)** · auditoria · chave
fora do Git · rotação pós-exposição · limite de tokens.

**A fazer / decisões abertas ☐:** cadência de rotação de chave · chave por
ambiente · teto de custo + alertas na OpenAI · decisão sobre `store=False`/ZDR ·
DPA com OpenAI/Anthropic · registro LGPD (RIPD).

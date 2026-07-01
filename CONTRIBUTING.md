# Contribuindo — Kairon Frete

Time de 1 engenheiro, prioridade **manutenibilidade sobre sofisticação**. As regras abaixo existem para manter o repo previsível e o CI verde.

## Fluxo de trabalho: trunk-based development

- **`main` é sempre deployável.** A CI roda em todo push e PR; o deploy sai de `main`.
- **Branches curtos** (horas a poucos dias), integrados cedo e com frequência. Evite branches longevos.
- **Código incompleto entra atrás de feature flag**, não em branch parado. Prefira merges pequenos e frequentes a um branch gigante que diverge.
- Abra PR contra `main`. Rebase/atualize antes do merge.

## Commits: Conventional Commits

Formato: `tipo(escopo opcional): descrição no imperativo`.

Tipos usados:

| Tipo | Quando |
|------|--------|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `chore` | tarefa de manutenção (deps, config, tooling) |
| `docs` | só documentação |
| `refactor` | mudança de código sem alterar comportamento |
| `test` | adiciona/ajusta testes |

Exemplos:

```
feat(prediction): banda de quantil P10/P90 no /v1/predict
fix(explanation): guardrail bloqueia valor de frete inventado pelo LLM
chore(deps): bump anthropic para ~0.40
docs(readme): adiciona guia de nova rota
refactor(core): extrai montagem do DSN do Postgres
test(ingestion): cobre normalizador do CSV da ANP
```

## Pull Request — checklist

Cole no corpo do PR e marque antes de pedir merge:

```markdown
## O que muda
<descrição curta>

## Checklist
- [ ] `make lint` passa (Ruff lint + format)
- [ ] `make typecheck` passa (mypy strict)
- [ ] `make test` passa (cobertura ≥ 70%)
- [ ] Migration revisada (se houver mudança de schema)
- [ ] Sem secrets no diff (nenhuma chave/credencial)
- [ ] Sem dados reais de cliente (dados de dev são SINTÉTICOS)
- [ ] Docs atualizadas se o comportamento mudou
```

## Pre-commit hooks

`make install` instala os hooks (`pre-commit install`). Eles rodam antes de cada commit e replicam parte do gate da CI:

- **Ruff** (lint + autofix) e **Ruff format**
- **mypy** (em `src/` e `tests/`)
- **prettier** (yaml, json, markdown)
- higiene: arquivos grandes (>1 MB), conflito de merge, EOF/trailing whitespace, `check-yaml`
- **`detect-private-key`** — trava commit de chave privada

Rode manualmente com `poetry run pre-commit run --all-files` se precisar.

## Anti-padrões (não faça)

Boa parte é imposta por Ruff/mypy — o CI reprova. Os demais são disciplina:

- **Sem LangChain** (ADR-011). Use o SDK `anthropic` direto + Instructor + pgvector.
- **Sem `requirements.txt`.** Dependências só via Poetry (`pyproject.toml` + `poetry.lock`).
- **Sem `print()` em código de prod.** Ruff `T20` reprova (`src/`). Use logging estruturado (`kairon.core.logging`). Prints são liberados só em `tests/`, `scripts/` e `ui/`.
- **Sem `TODO` pelado.** Sempre referencie uma issue: `# TODO(#42): calibrar banda por corredor`.
- **Sem SQLAlchemy 1.x.** Só a API 2.x (`Mapped[...]`, `mapped_column`, sessions async com asyncpg).
- **Sem `time.sleep` em código async.** Ruff `ASYNC` pega isso; use `await asyncio.sleep(...)`.
- **Sem import cross-context.** Um bounded context não importa outro (ADR-008). Comunique via `core` ou eventos (`core/events.py`). Ver [`ARCHITECTURE.md`](./ARCHITECTURE.md).
- **O LLM nunca prevê frete** (ADR-005). Não afrouxe os guardrails de `explanation/guardrails.py`.
- **Sem dados reais comitados.** O histórico da Eurochem (e de qualquer cliente) nunca vai para o repo; dev usa dados sintéticos.
- **Sem NoSQL, sem deep learning, sem Retool/low-code/no-code** (ADRs 003, 004, 009).

## Comandos úteis

Ver `make help`. Antes de abrir PR, no mínimo: `make fmt && make lint && make typecheck && make test`.

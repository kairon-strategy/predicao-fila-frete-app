# Dados sintéticos (`data/synthetic/`)

> **ATENÇÃO:** todos os arquivos desta pasta são **SINTÉTICOS**, gerados por
> `scripts/seed_synthetic_data.py`. Servem **apenas para desenvolvimento e
> testes**. **NUNCA** representam dados reais da Eurochem, da Marquite ou de
> qualquer outro cliente.

Diferente do resto de `data/` (ignorado pelo git), esta pasta **é comitada** —
ver `.gitignore` (`!data/synthetic/**`). Isso mantém o repo utilizável sem exigir
acesso a dados reais.

## Dados reais NÃO ficam aqui

O histórico real de 5 anos da Eurochem (e de qualquer cliente) **NUNCA** é
comitado. Ele vive num bucket **privado no Backblaze B2**
(`settings.backblaze_bucket`, default `kairon-frete-datalake`). Os pipelines de
produção leem de lá; o repositório só carrega o equivalente sintético.

## Arquivos

### `sample_routes.csv` (comitado, ~20 linhas)

Amostra pequena de rotas para a pasta não ficar vazia no git antes de alguém
rodar o seed. Colunas:

| coluna                | descrição                                       |
| --------------------- | ----------------------------------------------- |
| `origem`              | município-UF de origem                          |
| `destino`             | município-UF de destino                         |
| `distancia_km`        | distância rodoviária aproximada (km)            |
| `produto`             | ureia / MAP / KCl / NPK / algodão               |
| `corredor`            | rótulo do corredor logístico (ex.: `MT-Santos`) |
| `piso_antt_r_per_ton` | piso ANTT plausível (R$/tonelada)               |

### `routes_daily_prices.csv` (gerado em runtime, NÃO comitado no dia a dia)

Série **diária** sintética de 5 anos (2021–2025) por rota, produzida pelo seed.
Pode ser grande; o seed amostra os dias para manter o arquivo abaixo de ~50k
linhas e informa o passo de amostragem usado. Colunas:

| coluna            | descrição                                              |
| ----------------- | ------------------------------------------------------ |
| `date`            | data (ISO `YYYY-MM-DD`)                                 |
| `origem`          | município-UF de origem                                 |
| `destino`         | município-UF de destino                                |
| `produto`         | ureia / MAP / KCl / NPK / algodão                      |
| `distancia_km`    | distância da rota (km)                                  |
| `diesel_lag30`    | preço do diesel (R$/L) defasado em 30 dias             |
| `preco_r_por_ton` | frete sintético alvo (R$/tonelada)                     |

## Modelo gerador (spec seção 9)

O preço-alvo é gerado por uma relação linear + ruído gaussiano:

```
preco = a + b·distancia + c·diesel_lag30 + d·(sazonalidade_mes − 1) + ruido
```

- `a` — custo fixo (intercepto, R$/ton)
- `b` — R$/ton por km
- `c` — sensibilidade ao diesel (R$/ton por R$/L), aplicada sobre o diesel com
  defasagem de 30 dias
- `d` — amplitude da sazonalidade mensal (usa `SEASONALITY` de
  `kairon.prediction.features`)
- `ruido` — gaussiano N(0, σ)

A geração usa `numpy.random.default_rng(SEED)` com **semente fixa**, então a
saída é **reproduzível**.

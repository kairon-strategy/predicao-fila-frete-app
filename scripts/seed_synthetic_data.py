"""Popula o Postgres de DEV com dados SINTÉTICOS (spec seção 9).

Cria:
  - 1 tenant default ("Kairon Dev").
  - 55 rotas (50 fertilizante flavor "Eurochem" + 5 algodão flavor "Marquite").
  - ~60 dias de raw_diesel_prices por UF {MT, BA, GO, SP, MG}, terminando "hoje".
  - Série DIÁRIA sintética de 5 anos (2021-2025) por rota, escrita em
    data/synthetic/routes_daily_prices.csv (amostrada p/ manter < ~50k linhas).

IMPORTANTE:
  - Dados 100% SINTÉTICOS. NÃO representam Eurochem/clientes reais.
  - Idempotente: apaga as linhas de seed antes de reinserir.
  - Usa numpy.random.default_rng(SEED) (semente fixa), nunca o random global.

Uso:
    poetry run python scripts/seed_synthetic_data.py
"""

from __future__ import annotations

import asyncio
import csv
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import delete, select

from kairon.core.database import SessionFactory
from kairon.ingestion.anp.models import RawDieselPrice
from kairon.prediction.db_models import Route
from kairon.prediction.features import SEASONALITY
from kairon.tenant.models import Tenant, User
from kairon.tenant.security import hash_password

# --------------------------------------------------------------------------- #
# Constantes de geração
# --------------------------------------------------------------------------- #
SEED = 42
DEV_TENANT_ID = uuid.UUID(int=0)
DEV_TENANT_NAME = "Kairon Dev"
DEV_TENANT_SLUG = "kairon-dev"

DIESEL_UFS = ("MT", "BA", "GO", "SP", "MG")
DIESEL_DAYS = 60
DIESEL_SEED_FONTE = "SEED"  # marca as linhas de seed p/ apagar de forma segura

N_FERTILIZANTE_ROUTES = 50
N_ALGODAO_ROUTES = 5

CSV_PATH = Path("data/synthetic/routes_daily_prices.csv")
HISTORY_START = date(2021, 1, 1)
HISTORY_END = date(2025, 12, 31)
# Amostragem: geramos série diária, mas escrevemos 1 a cada N dias para manter
# o CSV comitável abaixo de ~50k linhas. 55 rotas * 1826 dias = ~100k -> amostra.
CSV_MAX_ROWS = 50_000

# Coeficientes do modelo gerador (spec seção 9):
#   preco = a + b*distancia + c*diesel_lag30 + d*sazonalidade_mes + ruido
GEN_A = 25.0  # intercepto (custo fixo R$/ton)
GEN_B = 0.11  # R$/ton por km
GEN_C = 9.0  # sensibilidade ao diesel (R$/ton por R$/L)
GEN_D = 40.0  # amplitude da sazonalidade
GEN_NOISE_STD = 6.0  # desvio-padrão do ruído gaussiano


# --------------------------------------------------------------------------- #
# Composição de rotas (loop programático até 55)
# --------------------------------------------------------------------------- #
# Corredores agro Mato Grosso / Bahia / Goiás. (origem, destino, dist_km, corredor)
_FERTI_LEGS: list[tuple[str, str, float, str]] = [
    ("Rondonópolis-MT", "Sinop-MT", 480, "MT-Norte"),
    ("Rondonópolis-MT", "Sorriso-MT", 520, "MT-Norte"),
    ("Rondonópolis-MT", "Santos-SP", 1500, "MT-Santos"),
    ("Rondonópolis-MT", "Paranaguá-PR", 1650, "MT-Paranagua"),
    ("Cuiabá-MT", "Sinop-MT", 500, "MT-Norte"),
    ("Cuiabá-MT", "Sorriso-MT", 420, "MT-Norte"),
    ("Cuiabá-MT", "Rondonópolis-MT", 220, "MT-Sul"),
    ("Sorriso-MT", "Sinop-MT", 90, "MT-Norte"),
    ("Sorriso-MT", "Lucas do Rio Verde-MT", 55, "MT-Norte"),
    ("Sinop-MT", "Sorriso-MT", 90, "MT-Norte"),
    ("Sinop-MT", "Santos-SP", 1950, "MT-Santos"),
    ("Lucas do Rio Verde-MT", "Sorriso-MT", 55, "MT-Norte"),
    ("Nova Mutum-MT", "Cuiabá-MT", 250, "MT-Sul"),
    ("Primavera do Leste-MT", "Rondonópolis-MT", 150, "MT-Sul"),
    ("Campo Verde-MT", "Rondonópolis-MT", 130, "MT-Sul"),
    ("Luís Eduardo Magalhães-BA", "Salvador-BA", 900, "BA-Oeste"),
    ("Luís Eduardo Magalhães-BA", "Barreiras-BA", 90, "BA-Oeste"),
    ("Barreiras-BA", "Salvador-BA", 850, "BA-Oeste"),
    ("Barreiras-BA", "Ilhéus-BA", 950, "BA-Litoral"),
    ("Rio Verde-GO", "Goiânia-GO", 220, "GO-Sul"),
    ("Rio Verde-GO", "São Simão-GO", 120, "GO-Sul"),
    ("Jataí-GO", "Rio Verde-GO", 110, "GO-Sul"),
    ("Cristalina-GO", "Goiânia-GO", 300, "GO-Sul"),
    ("Uberlândia-MG", "Santos-SP", 800, "MG-Santos"),
    ("Uberaba-MG", "Santos-SP", 820, "MG-Santos"),
]
_FERTI_PRODUTOS = ("ureia", "MAP", "KCl", "NPK")

_ALGODAO_LEGS: list[tuple[str, str, float, str]] = [
    ("Sapezal-MT", "Rondonópolis-MT", 650, "MT-Oeste"),
    ("Campo Novo do Parecis-MT", "Cuiabá-MT", 380, "MT-Oeste"),
    ("São Desidério-BA", "Salvador-BA", 880, "BA-Oeste"),
    ("Luís Eduardo Magalhães-BA", "Salvador-BA", 900, "BA-Oeste"),
    ("Primavera do Leste-MT", "Santos-SP", 1700, "MT-Santos"),
]

# Grãos: originação -> porto (corredores de exportação). (origem, destino, dist, corredor, produto)
_GRAOS_LEGS: list[tuple[str, str, float, str, str]] = [
    ("Sorriso-MT", "Porto de Santos-SP", 2050, "Corredor Centro-Sul", "soja"),
    ("Sorriso-MT", "Porto de Paranaguá-PR", 2150, "Corredor Sul", "soja"),
    ("Rondonópolis-MT", "Porto de Santos-SP", 1620, "Corredor Centro-Sul", "soja"),
    ("Luís Eduardo Magalhães-BA", "Porto do Itaqui-MA", 1450, "Arco Norte / MATOPIBA", "soja"),
    ("Sinop-MT", "Miritituba-PA", 1080, "Arco Norte", "soja"),
    ("Sorriso-MT", "Porto de Santos-SP", 2050, "Corredor Centro-Sul", "milho"),
    ("Rondonópolis-MT", "Porto de Santos-SP", 1620, "Corredor Centro-Sul", "milho"),
]


def _piso_antt(distancia_km: float) -> float:
    """Piso ANTT plausível (R$/ton): componente fixo + por km."""
    return round(70.0 + 0.09 * distancia_km, 2)


def _build_routes() -> list[Route]:
    """Compõe 55 rotas de forma programática (loop sobre pernas x produtos)."""
    routes: list[Route] = []

    # 50 fertilizante: cicla pernas x produtos até atingir a contagem.
    i = 0
    while len(routes) < N_FERTILIZANTE_ROUTES:
        origem, destino, dist, corredor = _FERTI_LEGS[i % len(_FERTI_LEGS)]
        produto = _FERTI_PRODUTOS[i % len(_FERTI_PRODUTOS)]
        routes.append(
            Route(
                id=uuid.uuid5(DEV_TENANT_ID, f"ferti-{i}-{origem}-{destino}-{produto}"),
                tenant_id=DEV_TENANT_ID,
                origem=origem,
                destino=destino,
                distancia_km=float(dist),
                produto=produto,
                corredor=corredor,
                piso_antt_r_per_ton=_piso_antt(dist),
            )
        )
        i += 1

    # 5 algodão.
    for j, (origem, destino, dist, corredor) in enumerate(_ALGODAO_LEGS):
        routes.append(
            Route(
                id=uuid.uuid5(DEV_TENANT_ID, f"algodao-{j}-{origem}-{destino}"),
                tenant_id=DEV_TENANT_ID,
                origem=origem,
                destino=destino,
                distancia_km=float(dist),
                produto="algodão",
                corredor=corredor,
                piso_antt_r_per_ton=_piso_antt(dist),
            )
        )

    # Grãos originação -> porto (corredores de exportação).
    for k, (origem, destino, dist, corredor, produto) in enumerate(_GRAOS_LEGS):
        routes.append(
            Route(
                id=uuid.uuid5(DEV_TENANT_ID, f"graos-{k}-{origem}-{destino}-{produto}"),
                tenant_id=DEV_TENANT_ID,
                origem=origem,
                destino=destino,
                distancia_km=float(dist),
                produto=produto,
                corredor=corredor,
                piso_antt_r_per_ton=_piso_antt(dist),
            )
        )

    return routes


# --------------------------------------------------------------------------- #
# Diesel sintético
# --------------------------------------------------------------------------- #
def _build_diesel_rows(rng: np.random.Generator, today: date) -> list[RawDieselPrice]:
    rows: list[RawDieselPrice] = []
    for uf in DIESEL_UFS:
        # base por UF entre 6.00 e 6.60, drift lento + ruído diário.
        base = float(rng.uniform(6.00, 6.60))
        for d in range(DIESEL_DAYS):
            dia = today - timedelta(days=DIESEL_DAYS - 1 - d)
            drift = 0.0008 * d
            noise = float(rng.normal(0.0, 0.03))
            preco = round(min(max(base + drift + noise, 5.80), 6.90), 3)
            rows.append(
                RawDieselPrice(
                    data=dia,
                    uf=uf,
                    cidade=None,
                    preco_medio=preco,
                    fonte=DIESEL_SEED_FONTE,
                )
            )
    return rows


# --------------------------------------------------------------------------- #
# Série diária 5 anos -> CSV
# --------------------------------------------------------------------------- #
def _daterange(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=n) for n in range(days + 1)]


def _write_history_csv(rng: np.random.Generator, routes: list[Route]) -> tuple[int, int]:
    """Gera a série diária sintética 2021-2025 e escreve o CSV amostrado.

    Retorna (linhas_escritas, passo_de_amostragem).
    """
    all_days = _daterange(HISTORY_START, HISTORY_END)
    n_full = len(routes) * len(all_days)

    # Passo de amostragem: escreve 1 a cada `step` dias p/ ficar < CSV_MAX_ROWS.
    step = max(1, (n_full // CSV_MAX_ROWS) + 1)
    sampled_days = all_days[::step]

    # Curva base de diesel ao longo dos 5 anos (drift + sazonalidade suave),
    # depois aplicamos lag de 30 dias por linha.
    day_index = {d: i for i, d in enumerate(all_days)}
    n_days = len(all_days)
    t = np.arange(n_days)
    diesel_curve = (
        5.4
        + 1.1 * (t / n_days)  # tendência de alta em 5 anos
        + 0.20 * np.sin(2 * np.pi * t / 365.25)  # sazonalidade anual
        + rng.normal(0.0, 0.04, size=n_days)  # ruído diário
    )
    diesel_curve = np.clip(diesel_curve, 4.8, 8.0)

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "date",
                "origem",
                "destino",
                "produto",
                "distancia_km",
                "diesel_lag30",
                "preco_r_por_ton",
            ]
        )
        for r in routes:
            for d in sampled_days:
                idx = day_index[d]
                lag_idx = max(0, idx - 30)
                diesel_lag30 = float(diesel_curve[lag_idx])
                sazonalidade = SEASONALITY.get(d.month, 1.0)
                noise = float(rng.normal(0.0, GEN_NOISE_STD))
                preco = (
                    GEN_A
                    + GEN_B * r.distancia_km
                    + GEN_C * diesel_lag30
                    + GEN_D * (sazonalidade - 1.0)
                    + noise
                )
                preco = max(preco, 10.0)
                writer.writerow(
                    [
                        d.isoformat(),
                        r.origem,
                        r.destino,
                        r.produto,
                        f"{r.distancia_km:.1f}",
                        f"{diesel_lag30:.4f}",
                        f"{preco:.2f}",
                    ]
                )
                written += 1

    return written, step


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
async def main() -> None:
    rng = np.random.default_rng(SEED)
    today = datetime.now().date()

    print(f"[seed] usando semente fixa SEED={SEED}")
    print("[seed] AVISO: dados 100% SINTÉTICOS — nunca representam clientes reais.")

    routes = _build_routes()
    diesel_rows = _build_diesel_rows(rng, today)

    async with SessionFactory() as session:
        # --- tenant (idempotente via merge/get) ---
        existing_tenant = await session.get(Tenant, DEV_TENANT_ID)
        if existing_tenant is None:
            session.add(
                Tenant(
                    id=DEV_TENANT_ID,
                    name=DEV_TENANT_NAME,
                    slug=DEV_TENANT_SLUG,
                    is_active=True,
                )
            )
            print(f"[seed] tenant criado: {DEV_TENANT_NAME} ({DEV_TENANT_SLUG})")
        else:
            print(f"[seed] tenant já existe: {DEV_TENANT_NAME}")

        # Grava o tenant ANTES das rotas: a sessão tem autoflush=False e o
        # bulk-insert de rotas (FK -> tenants) rodaria antes do tenant existir.
        await session.flush()

        # --- usuários demo (idempotente por email) ---
        demo_users = [
            ("admin@kairon.dev", "admin", "Eduardo Vasconcellos"),
            ("analyst@kairon.dev", "analyst", "Ana Souza"),
            ("viewer@kairon.dev", "viewer", "Vitor Lima"),
        ]
        for email, role, uname in demo_users:
            exists = (
                (await session.execute(select(User).where(User.email == email))).scalars().first()
            )
            if exists is None:
                session.add(
                    User(
                        tenant_id=DEV_TENANT_ID,
                        email=email,
                        name=uname,
                        hashed_password=hash_password("demo1234"),
                        role=role,
                    )
                )
        print("[seed] usuários demo: admin/analyst/viewer @kairon.dev (senha: demo1234)")

        # --- rotas (idempotente: apaga as do tenant de dev e reinsere) ---
        await session.execute(delete(Route).where(Route.tenant_id == DEV_TENANT_ID))
        session.add_all(routes)
        print(
            f"[seed] {len(routes)} rotas inseridas "
            f"({N_FERTILIZANTE_ROUTES} fertilizante 'Eurochem' + "
            f"{N_ALGODAO_ROUTES} algodão 'Marquite')"
        )

        # --- diesel (idempotente: apaga só as linhas de seed) ---
        await session.execute(
            delete(RawDieselPrice).where(RawDieselPrice.fonte == DIESEL_SEED_FONTE)
        )
        session.add_all(diesel_rows)
        print(
            f"[seed] {len(diesel_rows)} linhas raw_diesel_prices "
            f"({len(DIESEL_UFS)} UFs x {DIESEL_DAYS} dias, fonte={DIESEL_SEED_FONTE})"
        )

        await session.commit()

        # contagens finais (para o resumo)
        n_routes = (
            (await session.execute(select(Route).where(Route.tenant_id == DEV_TENANT_ID)))
            .scalars()
            .all()
        )
        n_diesel = (
            (
                await session.execute(
                    select(RawDieselPrice).where(RawDieselPrice.fonte == DIESEL_SEED_FONTE)
                )
            )
            .scalars()
            .all()
        )

    # --- CSV histórico 5 anos ---
    print(f"[seed] gerando série diária 2021-2025 -> {CSV_PATH} ...")
    written, step = _write_history_csv(rng, routes)
    print(
        f"[seed] CSV: {written} linhas (amostragem 1 a cada {step} dia(s); " f"{len(routes)} rotas)"
    )

    print(
        "[seed] RESUMO: "
        f"tenants=1, routes={len(n_routes)}, diesel_rows={len(n_diesel)}, "
        f"csv_rows={written} em {CSV_PATH}"
    )


if __name__ == "__main__":
    asyncio.run(main())

"""Enriquecimento de DEMO: injeta spikes de diesel e roda o detector p/ gerar alertas.

Uso: DATABASE_URL apontando ao banco alvo (Supabase em prod-demo). Idempotente:
remove os spikes/alertas 'DEMO' anteriores antes de recriar. Dados 100% sintéticos.

    poetry run python scripts/seed_demo_alerts.py
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy import delete, select

from kairon.alerts.detectors import detect_diesel_spikes
from kairon.alerts.models import Alert
from kairon.core.database import SessionFactory, engine
from kairon.ingestion.anp.models import RawDieselPrice
from kairon.prediction.db_models import Route

# UF -> (multiplicador do spike no dia mais recente, rótulo esperado)
_SPIKES = {
    "MT": 1.13,  # +13% -> critical
    "GO": 1.07,  # +7%  -> warn
}
_DEMO_FONTE = "DEMO_SPIKE"


async def main() -> None:
    async with SessionFactory() as s:
        # tenant do demo = o dono das rotas seedadas
        tenant_id = (await s.execute(select(Route.tenant_id).limit(1))).scalar_one()

        # limpa demo anterior (idempotente)
        await s.execute(delete(RawDieselPrice).where(RawDieselPrice.fonte == _DEMO_FONTE))
        await s.execute(delete(Alert).where(Alert.tenant_id == tenant_id))
        await s.flush()

        today = date.today()
        for uf, mult in _SPIKES.items():
            # baseline = média dos preços recentes daquela UF
            recent = (
                (
                    await s.execute(
                        select(RawDieselPrice.preco_medio)
                        .where(RawDieselPrice.uf == uf)
                        .order_by(RawDieselPrice.data.desc())
                        .limit(20)
                    )
                )
                .scalars()
                .all()
            )
            base = sum(recent) / len(recent) if recent else 6.20
            # remove qualquer preço já existente em 'hoje' p/ essa UF e injeta o spike
            await s.execute(
                delete(RawDieselPrice).where(
                    RawDieselPrice.uf == uf, RawDieselPrice.data == today
                )
            )
            s.add(
                RawDieselPrice(
                    data=today,
                    uf=uf,
                    cidade=None,
                    preco_medio=round(base * mult, 3),
                    fonte=_DEMO_FONTE,
                )
            )
            print(f"[demo] spike {uf}: base {base:.2f} -> {base*mult:.2f} (x{mult})")
        await s.flush()

        alerts = await detect_diesel_spikes(s, tenant_id)
        await s.commit()

        for a in alerts:
            print(f"[demo] alerta: [{a.severity}] {a.title}")
        print(f"[demo] {len(alerts)} alerta(s) criado(s) para o tenant {tenant_id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

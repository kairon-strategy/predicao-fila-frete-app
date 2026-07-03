"""DEMO/QA: garante usuários para RBAC e um SEGUNDO tenant para testar isolamento.

- Tenant A (default, já criado pelo seed principal): admin/analyst/viewer @kairon.dev
- Tenant B ("Empresa Beta"): admin `beta@empresa.com` + 1 rota própria

Assim o QA prova: viewer 403 nas rotas admin, e que o tenant B NÃO enxerga os
dados do tenant A (ranking/alertas isolados). Dados sintéticos. Idempotente.

    poetry run python scripts/seed_demo_users.py
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from kairon.core.database import SessionFactory, engine
from kairon.prediction.db_models import Route
from kairon.tenant.models import Tenant, User
from kairon.tenant.security import hash_password

TENANT_B_SLUG = "empresa-beta"


async def main() -> None:
    async with SessionFactory() as s:
        # garante o tenant A (default) e os 3 papéis, caso o seed principal não tenha rodado
        default_tid = uuid.UUID(int=0)
        if await s.get(Tenant, default_tid) is None:
            s.add(Tenant(id=default_tid, name="Kairon Dev", slug="kairon-dev"))
            await s.flush()
        for email, role, name in [
            ("admin@kairon.dev", "admin", "Admin"),
            ("analyst@kairon.dev", "analyst", "Analista"),
            ("viewer@kairon.dev", "viewer", "Visualizador"),
        ]:
            exists = (
                await s.execute(select(User).where(User.email == email))
            ).scalars().first()
            if exists is None:
                s.add(
                    User(
                        tenant_id=default_tid,
                        email=email,
                        name=name,
                        hashed_password=hash_password("demo1234"),
                        role=role,
                    )
                )
        await s.flush()

        # tenant B (isolamento)
        tenant_b = (
            await s.execute(select(Tenant).where(Tenant.slug == TENANT_B_SLUG))
        ).scalars().first()
        if tenant_b is None:
            tenant_b = Tenant(id=uuid.uuid4(), name="Empresa Beta", slug=TENANT_B_SLUG)
            s.add(tenant_b)
            await s.flush()

        if (await s.execute(select(User).where(User.email == "beta@empresa.com"))).scalars().first() is None:
            s.add(
                User(
                    tenant_id=tenant_b.id,
                    email="beta@empresa.com",
                    name="Beta Admin",
                    hashed_password=hash_password("beta1234"),
                    role="admin",
                )
            )

        # 1 rota própria do tenant B (para provar isolamento no ranking)
        has_route = (
            await s.execute(select(Route).where(Route.tenant_id == tenant_b.id).limit(1))
        ).scalars().first()
        if has_route is None:
            s.add(
                Route(
                    tenant_id=tenant_b.id,
                    origem="Rio Verde-GO",
                    destino="Porto de Santos-SP",
                    produto="soja",
                    distancia_km=920,
                    corredor="BR-060",
                    piso_antt_r_per_ton=110,
                )
            )

        await s.commit()
        print("[demo] tenant A: admin/analyst/viewer @kairon.dev (senha demo1234)")
        print(f"[demo] tenant B '{tenant_b.name}': beta@empresa.com (senha beta1234) + 1 rota própria")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

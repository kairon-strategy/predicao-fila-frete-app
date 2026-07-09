"""Catálogo de permissões (RBAC dinâmico) e perfis padrão por tenant.

As PERMISSÕES são um catálogo FIXO definido pelo código — mapeiam o que a app
sabe fazer (cada endpoint exige uma chave). O usuário NÃO cria permissões; ele
cria PERFIS (roles) e marca quais permissões cada perfil tem. Os 3 perfis padrão
(`admin`/`analyst`/`viewer`) são semeados por tenant como `is_system` (não
deletáveis) mas têm as permissões editáveis.
"""

from __future__ import annotations

# key -> (grupo, rótulo legível). Ordem = ordem de exibição na matriz da UI.
PERMISSIONS: dict[str, tuple[str, str]] = {
    "routes:read": ("Rotas", "Ver rotas, ranking e histórico"),
    "routes:write": ("Rotas", "Criar, editar e excluir rotas"),
    "predict:run": ("Predição", "Rodar predição de frete"),
    "simulate:run": ("Simulação", "Rodar simulação Monte Carlo"),
    "explain:run": ("Copiloto", "Usar o copiloto de explicação"),
    "alerts:read": ("Alertas", "Ver o feed de alertas"),
    "alerts:resolve": ("Alertas", "Resolver alertas"),
    "alerts:detect": ("Alertas", "Disparar a detecção de alertas"),
    "users:read": ("Usuários", "Ver usuários do tenant"),
    "users:write": ("Usuários", "Criar e editar usuários"),
    "roles:read": ("Perfis", "Ver perfis e permissões"),
    "roles:write": ("Perfis", "Criar, editar e excluir perfis"),
    "tenant:read": ("Empresa", "Ver dados da empresa"),
    "tenant:write": ("Empresa", "Editar dados da empresa"),
    "copilot:read": ("Copiloto", "Ver a configuração do copiloto"),
    "copilot:write": ("Copiloto", "Editar prompts e configuração do copiloto"),
}

ALL_PERMISSIONS: frozenset[str] = frozenset(PERMISSIONS)


def is_valid_permission(key: str) -> bool:
    return key in PERMISSIONS


# Perfis padrão semeados em cada tenant. slug -> (nome, permissões).
# Preservam o comportamento atual: admin faz tudo; analyst opera mas não
# administra; viewer só lê/consulta.
DEFAULT_ROLES: dict[str, tuple[str, frozenset[str]]] = {
    "admin": ("Administrador", ALL_PERMISSIONS),
    "analyst": (
        "Analista",
        frozenset(
            {
                "routes:read",
                "routes:write",
                "predict:run",
                "simulate:run",
                "explain:run",
                "alerts:read",
                "alerts:resolve",
                "alerts:detect",
                "tenant:read",
            }
        ),
    ),
    "viewer": (
        "Visualizador",
        frozenset(
            {
                "routes:read",
                "simulate:run",
                "explain:run",
                "alerts:read",
                "tenant:read",
            }
        ),
    ),
}

SYSTEM_ROLE_SLUGS: frozenset[str] = frozenset(DEFAULT_ROLES)

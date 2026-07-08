"""Schemas do context tenant (auth + perfil + empresa + usuários)."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Perfil é um slug dinâmico (RBAC configurável por tenant); validado no service
# contra os perfis existentes do tenant.


class LoginRequest(BaseModel):
    # str simples (evita a dep email-validator); validação real fica no signup/v2.
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    """Auto-onboarding: cria um tenant novo + usuário admin."""

    tenant_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=200)
    name: str | None = Field(default=None, max_length=120)


class CreateUserRequest(BaseModel):
    """Admin cria um usuário dentro do próprio tenant (US-002, sem email)."""

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(default="viewer", max_length=50)
    name: str | None = Field(default=None, max_length=120)


class UpdateUserRequest(BaseModel):
    """Admin edita papel/ativação e/ou reseta a senha de um usuário do tenant."""

    role: str | None = Field(default=None, max_length=50)
    is_active: bool | None = Field(default=None)
    password: str | None = Field(default=None, min_length=8, max_length=200)


class UpdateMeRequest(BaseModel):
    """Usuário edita o próprio perfil (nome e/ou senha)."""

    name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=200)


class UpdateTenantRequest(BaseModel):
    """Admin edita dados da empresa (tenant)."""

    name: str = Field(..., min_length=2, max_length=255)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    is_active: bool
    tenant_id: str


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    name: str | None
    role: str
    permissions: list[str] = Field(default_factory=list)


# ---- Perfis & permissões (RBAC dinâmico) ----
class PermissionInfo(BaseModel):
    key: str
    group: str
    label: str


class RoleResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_system: bool
    permissions: list[str]
    user_count: int


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    permissions: list[str] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    permissions: list[str] | None = Field(default=None)

"""Router de auth + perfil + empresa + usuários (US-001/002/006)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.config import settings
from kairon.core.database import get_session
from kairon.core.exceptions import NotFoundError
from kairon.tenant import ratelimit, service
from kairon.tenant.auth import Principal, get_principal, require_role
from kairon.tenant.models import User
from kairon.tenant.schemas import (
    CreateUserRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TenantResponse,
    TokenResponse,
    UpdateMeRequest,
    UpdateTenantRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Guard de RBAC (singleton de módulo — evita chamada em default de argumento).
_admin_guard = require_role("admin")


def _client_ip(request: Request) -> str:
    """IP do cliente, respeitando X-Forwarded-For (atrás de proxy/load balancer)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse, summary="Login (email/senha) -> JWT")
async def login(
    req: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    # Rate limit anti brute-force (por IP+email). Estourou -> 429.
    key = f"{_client_ip(request)}:{req.email.strip().lower()}"
    if not ratelimit.hit(
        key,
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_min * 60,
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "muitas tentativas de login; tente novamente em alguns minutos",
        )
    tokens = await service.login(session, req.email, req.password)
    ratelimit.reset(key)  # login OK zera o contador
    return tokens


@router.post("/refresh", response_model=TokenResponse, summary="Renova access token")
async def refresh(
    req: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await service.refresh(session, req.refresh_token)


@router.post("/register", response_model=TokenResponse, summary="Cria tenant + admin e loga")
async def register(
    req: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    # Por convite: cadastro aberto de novos tenants é desligado por padrão.
    if not settings.allow_open_registration:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "cadastro por convite: peça a um admin para criar seu acesso",
        )
    return await service.register(session, req.tenant_name, req.email, req.password, req.name)


@router.post("/logout", status_code=204, summary="Encerra a sessão (revoga tokens)")
async def logout(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> Response:
    if principal.user_id is not None:
        await service.logout(session, principal.user_id)
    return Response(status_code=204)


# ---- Usuários (CRUD, admin) ----
@router.get("/users", response_model=list[UserResponse], summary="Lista usuários do tenant (admin)")
async def list_users(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_admin_guard),
) -> list[UserResponse]:
    return await service.list_users(session, principal.tenant_id)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    summary="Admin cria usuário no próprio tenant (US-002)",
)
async def create_user(
    req: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_admin_guard),
) -> UserResponse:
    return await service.create_user(
        session, principal.tenant_id, req.email, req.password, req.role, req.name
    )


@router.patch(
    "/users/{user_id}", response_model=UserResponse, summary="Edita papel/ativação (admin)"
)
async def update_user(
    user_id: uuid.UUID,
    req: UpdateUserRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_admin_guard),
) -> UserResponse:
    return await service.update_user(
        session,
        principal.tenant_id,
        user_id,
        role=req.role,
        is_active=req.is_active,
        password=req.password,
    )


# ---- Perfil próprio ----
@router.get("/me", response_model=MeResponse, summary="Dados do usuário autenticado")
async def me(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    if not principal.authenticated or principal.user_id is None:
        raise NotFoundError("nenhum usuário autenticado (request anônima)")
    user = (
        (await session.execute(select(User).where(User.id == principal.user_id))).scalars().first()
    )
    if user is None:
        raise NotFoundError("usuário não encontrado")
    return MeResponse(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        name=user.name,
        role=user.role,
    )


@router.patch("/me", response_model=UserResponse, summary="Edita o próprio perfil (nome/senha)")
async def update_me(
    req: UpdateMeRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> UserResponse:
    if not principal.authenticated or principal.user_id is None:
        raise NotFoundError("nenhum usuário autenticado")
    return await service.update_me(session, principal.user_id, name=req.name, password=req.password)


# ---- Empresa (tenant) ----
@router.get("/tenant", response_model=TenantResponse, summary="Dados da empresa (tenant)")
async def get_tenant(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> TenantResponse:
    return await service.get_tenant(session, principal.tenant_id)


@router.patch("/tenant", response_model=TenantResponse, summary="Edita a empresa (admin)")
async def update_tenant(
    req: UpdateTenantRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(_admin_guard),
) -> TenantResponse:
    return await service.update_tenant(session, principal.tenant_id, req.name)

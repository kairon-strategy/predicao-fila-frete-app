"""Router de autenticação: /v1/auth/login, /refresh, /me (US-001)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairon.core.database import get_session
from kairon.core.exceptions import NotFoundError
from kairon.tenant import service
from kairon.tenant.auth import Principal, get_principal, require_role
from kairon.tenant.models import User
from kairon.tenant.schemas import (
    CreateUserRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Guard de RBAC (singleton de módulo — evita chamada em default de argumento).
_admin_guard = require_role("admin")


@router.post("/login", response_model=TokenResponse, summary="Login (email/senha) -> JWT")
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    return await service.login(session, req.email, req.password)


@router.post("/refresh", response_model=TokenResponse, summary="Renova access token")
async def refresh(
    req: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await service.refresh(session, req.refresh_token)


@router.post("/register", response_model=TokenResponse, summary="Cria tenant + admin e loga")
async def register(
    req: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await service.register(session, req.tenant_name, req.email, req.password)


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
        session, principal.tenant_id, req.email, req.password, req.role
    )


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
        role=user.role,
    )

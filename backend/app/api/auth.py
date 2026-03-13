"""Authentication endpoints for SOSM panel."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session,
    hash_password,
    invalidate_session,
    mark_password_set,
    validate_session,
    verify_password,
)
from app.models.models import AppAuth

router = APIRouter(prefix="/auth", tags=["auth"])


class PasswordInput(BaseModel):
    password: str


class AuthStatus(BaseModel):
    authenticated: bool
    password_set: bool


@router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppAuth).limit(1))
    has_password = result.scalar_one_or_none() is not None

    token = request.cookies.get(SESSION_COOKIE)
    authenticated = bool(token and validate_session(token))

    return AuthStatus(authenticated=authenticated, password_set=has_password)


@router.post("/set-password")
async def set_password(
    data: PasswordInput,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Hasło musi mieć min. 4 znaki")

    result = await db.execute(select(AppAuth).limit(1))
    existing = result.scalar_one_or_none()

    if existing:
        # Changing password — require current session
        token = request.cookies.get(SESSION_COOKIE)
        if not token or not validate_session(token):
            raise HTTPException(status_code=403, detail="Zaloguj się, aby zmienić hasło")
        existing.password_hash = hash_password(data.password)
    else:
        # First-time setup
        db.add(AppAuth(password_hash=hash_password(data.password)))

    await db.commit()
    mark_password_set()

    # Auto-login after setting password
    session_token = create_session()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return {"status": "ok"}


@router.post("/login")
async def login(
    data: PasswordInput,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AppAuth).limit(1))
    auth = result.scalar_one_or_none()
    if not auth:
        raise HTTPException(status_code=400, detail="Hasło nie zostało ustawione")

    if not verify_password(data.password, auth.password_hash):
        raise HTTPException(status_code=401, detail="Nieprawidłowe hasło")

    session_token = create_session()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        invalidate_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}

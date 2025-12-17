from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select

from app.db.session import get_session
from app.models.models import User
from app.services import auth as auth_service
from app.redis_client import redis_client
from app.config import settings

router = APIRouter(tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str


@router.post("/register", status_code=201)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_session)):
    stmt = sa_select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = auth_service.hash_password(payload.password)
    user = User(email=payload.email, full_name=payload.full_name, phone=payload.phone, hashed_password=hashed)
    if payload.role:
        user.role = payload.role
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}


@router.post("/login", response_model=TokenOut)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_session)):
    identifier = form_data.username.lower()
    rl_key = f"rl:login:{identifier}"
    attempts = await redis_client.get(rl_key)
    if attempts and int(attempts) >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts, try later")

    stmt = sa_select(User).where(User.email == identifier)
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user or not auth_service.verify_password(form_data.password, user.hashed_password):
        # increment attempts
        await redis_client.incr(rl_key)
        await redis_client.expire(rl_key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # successful login: clear attempts
    await redis_client.delete(rl_key)
    access = auth_service.create_access_token(user.id)
    refresh_token, jti = await auth_service.create_refresh_token(user.id)
    return {"access_token": access, "refresh_token": refresh_token}


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn):
    try:
        user_id, old_jti = await auth_service.verify_refresh_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    # rotate
    new_refresh, new_jti = await auth_service.rotate_refresh_token(old_jti, user_id)
    access = auth_service.create_access_token(user_id)
    return {"access_token": access, "refresh_token": new_refresh}


class LogoutIn(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=204)
async def logout(payload: LogoutIn):
    try:
        _, jti = await auth_service.verify_refresh_token(payload.refresh_token)
    except Exception:
        # already invalid / revoked
        return None
    await auth_service.revoke_refresh_token(jti)
    return None
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def auth_root():
    return {"module": "auth", "status": "ok"}

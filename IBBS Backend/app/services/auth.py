import uuid
from datetime import datetime, timedelta
from typing import Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.redis_client import redis_client


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _now() -> datetime:
    return datetime.utcnow()


def create_access_token(user_id: int) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "type": "access", "exp": int(expire.timestamp())}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


async def create_refresh_token(user_id: int) -> Tuple[str, str]:
    # jti used for rotation and revocation
    jti = uuid.uuid4().hex
    expire = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "exp": int(expire.timestamp())}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    # store jti in redis with expiry
    key = f"refresh:{jti}"
    await redis_client.set(key, str(user_id), ex=int((expire - _now()).total_seconds()))
    return token, jti


def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise


def verify_access_token(token: str) -> int:
    payload = _decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return int(payload.get("sub"))


async def verify_refresh_token(token: str) -> Tuple[int, str]:
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type")
    user_id = int(payload.get("sub"))
    jti = payload.get("jti")
    key = f"refresh:{jti}"
    val = await redis_client.get(key)
    if not val or int(val) != user_id:
        raise JWTError("Refresh token revoked or not found")
    return user_id, jti


async def rotate_refresh_token(old_jti: str, user_id: int) -> Tuple[str, str]:
    # remove old jti and create a new one
    old_key = f"refresh:{old_jti}"
    await redis_client.delete(old_key)
    token, new_jti = await create_refresh_token(user_id)
    return token, new_jti


async def revoke_refresh_token(jti: str):
    key = f"refresh:{jti}"
    await redis_client.delete(key)

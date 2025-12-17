from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.models.models import User
from sqlalchemy import select as sa_select
from jose import JWTError
from app.services import auth as auth_service


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_session)) -> User:
    try:
        user_id = auth_service.verify_access_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    stmt = sa_select(User).where(User.id == int(user_id))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def role_required(allowed: List[str]):
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return _dep

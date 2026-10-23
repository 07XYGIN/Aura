from typing import Any

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.response import Result
from app.db.session import get_db
from app.models.user import UserMapper


async def get_current_user(
    authorization: str = Header(),
    db: AsyncSession = Depends(get_db),
) -> Result[Any] | None | Any:
    if not authorization.startswith("Bearer "):
        return Result.fail(code=500,message="未提供有效的认证信息")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return Result.fail(code=500, message="登录已过期,请重新登录")
    except jwt.InvalidTokenError:
        return Result.fail(code=500, message="无效的登录凭证")

    user_id = int(payload["sub"])

    stmt = select(UserMapper).where(UserMapper.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return Result.fail(code=500,message="用户不存在")

    return user
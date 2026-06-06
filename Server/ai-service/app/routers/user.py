from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.model.user import User
from app.schemas.response import SuccessResponse


router = APIRouter(
    prefix="/api/user",
    tags=['角色信息']
)


@router.get('/info', response_model=SuccessResponse, summary='获取用户信息', tags=['角色信息'])
async def get_user_info(db: AsyncSession = Depends(get_db), code: str | None = Header(None)):
    if not code:
        raise BusinessException("缺少邀请码")

    stmt = select(User.create_at, User.id, User.user_name).where(User.code == code)
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise BusinessException("用户不存在", status_code=404)

    create_time, user_id, username = row
    data = {
        "createTime": create_time,
        "userId": user_id,
        "userName": username,
    }
    return SuccessResponse(data=data)


@router.delete('/logout', response_model=SuccessResponse, summary='注销账户', tags=['角色信息'])
async def logout(userid: UUID, db: AsyncSession = Depends(get_db)):
    if userid is None:
        raise BusinessException('缺少用户 id 或 id 不合法')
    stmt = delete(User).where(User.id == userid)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise BusinessException('用户不存在或已注销', status_code=404)
    await db.commit()
    return SuccessResponse()

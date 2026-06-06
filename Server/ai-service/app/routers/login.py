import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BusinessException, LoginException
from app.model.user import User
from app.schemas.request import LoginRequest, RegisterRequest
from app.schemas.response import SuccessResponse
from app.utils.verify import get_password_hash, verify_password

router = APIRouter(
    prefix='/api',
    tags=['用户权限']
)


@router.post('/register', response_model=SuccessResponse, summary='注册')
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User.user_name).where(User.user_name == payload.user_name)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise BusinessException("用户已存在")

    user = User(
        user_name=payload.user_name,
        psd=get_password_hash(payload.password),
        code=payload.code,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return SuccessResponse()


@router.post('/login', response_model=SuccessResponse, summary='登录')
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    logging.info("用户 %s 尝试登录", payload.user_name)
    stmt = (
        select(User.psd, User.code)
        .where(User.user_name == payload.user_name)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise LoginException("用户不存在")

    base_psd, code_info = row
    if not verify_password(payload.password, base_psd):
        raise LoginException("密码错误")
    if code_info is None or payload.code != code_info:
        raise LoginException("邀请码错误")

    return SuccessResponse(data=code_info)

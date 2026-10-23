from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.Depends.auth import get_current_user
from app.core.response import Result
from app.db.session import get_db
from app.schemas.user import User
from app.models.user import UserMapper
from app.utlis.security import *
router = APIRouter(prefix="/user", tags=["user"])

@router.post("/register",response_model=Result,summary="注册")
async def register(user_info:User,db: AsyncSession = Depends(get_db)):
    new_user = UserMapper(
        username=user_info.username,
        age=user_info.age,
        password=hash_password(user_info.password)
    )
    db.add(new_user)
    await db.commit()
    return Result(code=200, message="成功")


@router.post(
    "/login",
    response_model=Result,
    summary="登录",
)

async def login(payload:User,db: AsyncSession = Depends(get_db),current_user: UserMapper = Depends(get_current_user)):
    stmt = select(UserMapper).where(UserMapper.username == payload.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        return Result.fail(code=500, message="用户名或密码错误")

    if not verify_password(payload.password, user.password):
        return Result.fail(code=500, message="用户名或密码错误")
    token:str = create_access_token(user_id=user.id, username=user.username)
    return Result(code=200,message="登录成功",data={"token":token,"userinfo":payload})
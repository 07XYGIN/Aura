from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.auth_store import (
    SessionDep,
    authenticate_user,
    create_access_token,
    delete_user,
    get_current_user_id,
    get_user_info,
    register_user,
    revoke_token,
    update_user_info,
)
from app.core.memory.service import list_memories_by_user
from app.schemas.user import UserLoginRequest, UserRegisterRequest, UserUpdateRequest

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")


@router.post("/register")
async def register(request: UserRegisterRequest, session: SessionDep):
    """创建用户账号，成功后返回统一响应。"""
    await register_user(session, request)
    return api_success(message="账号创建成功")


@router.post("/login")
async def login(request: UserLoginRequest, session: SessionDep):
    """验证账号密码并签发访问令牌。"""
    user = await authenticate_user(session, request)
    token = create_access_token(user["id"])
    return api_success(message="登录成功", token=token)


@router.get("/userInfo")
async def user_info(
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """返回当前 JWT 用户的基础资料。"""
    return api_success(data=await get_user_info(session, user_id))


@router.get("/memoryList")
async def memory_list(
    user_id: Annotated[str, Depends(get_current_user_id)],
    page: int = 1,
    pageSize: int = 10,
):
    """分页返回当前登录用户的长期记忆。"""
    return api_success(data=list_memories_by_user(user_id=user_id, page=page, page_size=pageSize))


@router.put("/updateInfo")
async def update_info(
    request: UserUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """更新当前 JWT 用户提供的资料字段。"""
    await update_user_info(session, user_id, request)
    return api_success(message="用户信息更新成功")


@router.delete("/{username}")
async def delete_current_user(
    username: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """核对路径中的用户名后删除当前 JWT 用户。"""
    await delete_user(session, user_id, username)
    return api_success(message="用户删除成功")


@router.get("/logout/{user_id}")
async def logout(
    user_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    """吊销当前请求的访问令牌，禁止代其他用户退出。"""
    if user_id != current_user_id:
        return {"code": 403, "message": "不能退出其他用户的登录状态", "msg": "无权限"}
    revoke_token(token)
    return api_success(message="退出登录成功")


def api_success(data=None, message="成功", token: str | None = None):
    """构造用户接口沿用的成功响应，并按需附带访问令牌。"""
    response = {
        "code": 200,
        "data": data,
        "msg": message,
        "message": message,
    }
    if token:
        response["token"] = token
    return response

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
from app.schemas.user import UserLoginRequest, UserRegisterRequest, UserUpdateRequest

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")


@router.post("/register")
async def register(request: UserRegisterRequest, session: SessionDep):
    await register_user(session, request)
    return api_success(message="Account created")


@router.post("/login")
async def login(request: UserLoginRequest, session: SessionDep):
    user = await authenticate_user(session, request)
    token = create_access_token(user["id"])
    return api_success(message="Login success", token=token)


@router.get("/userInfo")
async def user_info(
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    return api_success(data=await get_user_info(session, user_id))


@router.put("/updateInfo")
async def update_info(
    request: UserUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    await update_user_info(session, user_id, request)
    return api_success(message="User updated")


@router.delete("/{username}")
async def delete_current_user(
    username: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    await delete_user(session, user_id, username)
    return api_success(message="User deleted")


@router.get("/logout/{user_id}")
async def logout(
    user_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    if user_id != current_user_id:
        return {"code": 403, "message": "cannot logout another user", "msg": "forbidden"}
    revoke_token(token)
    return api_success(message="Logout success")


def api_success(data=None, message="success", token: str | None = None):
    response = {
        "code": 200,
        "data": data,
        "msg": message,
        "message": message,
    }
    if token:
        response["token"] = token
    return response

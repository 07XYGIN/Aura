from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from collections.abc import Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import Column, Integer, MetaData, SmallInteger, String, Table, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.user import UserLoginRequest, UserRegisterRequest, UserUpdateRequest

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY 必须配置为至少 32 个字符的随机密钥")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(milliseconds=int(os.getenv("JWT_EXPIRE_TIME", "86400000")))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")
password_hash = PasswordHash.recommended()
revoked_tokens: dict[str, int] = {}
metadata = MetaData()
users_table = Table(
    "users",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
    Column("username", String),
    Column("password", String),
    Column("email", String),
    Column("sex", SmallInteger),
    Column("age", Integer),
)


def create_access_token(subject: str, expires_delta: timedelta = ACCESS_TOKEN_EXPIRE) -> str:
    """为用户签发带过期时间和唯一 ID 的 JWT 访问令牌。

    Args:
        subject: 写入 ``sub`` 声明的用户 ID。
        expires_delta: 令牌从当前时间起的有效期。

    Returns:
        使用服务端密钥签名的 JWT 字符串。
    """
    expire = datetime.now(UTC) + expires_delta
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": str(uuid4()),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def hash_password(password: str) -> str:
    """校验密码字节长度并生成推荐算法的密码摘要。"""
    validate_password_length(password)
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码，兼容历史 bcrypt 摘要和当前推荐摘要格式。"""
    validate_password_length(plain_password)
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    return password_hash.verify(plain_password, hashed_password)


def validate_password_length(password: str) -> None:
    """限制密码 UTF-8 编码长度，超过 72 字节时返回 HTTP 400。

    Raises:
        HTTPException: 密码超过底层 bcrypt 可安全处理的长度。
    """
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="密码长度不能超过 72 字节")


async def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """校验 Bearer JWT 并返回其中的用户 ID。

    Args:
        token: FastAPI OAuth2 依赖从请求头提取的访问令牌。

    Returns:
        JWT ``sub`` 字段中的用户 ID。

    Raises:
        HTTPException: 令牌已吊销、过期、签名无效或缺少合法 ``sub``。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    clean_revoked_tokens()
    if token in revoked_tokens:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise credentials_exception
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    return user_id


def revoke_token(token: str) -> None:
    """将有效 JWT 加入进程内吊销表，记录到令牌原本的过期时间。

    无效令牌会被忽略；吊销状态不会跨进程或服务重启持久化。
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if isinstance(exp, int):
            revoked_tokens[token] = exp
    except InvalidTokenError:
        return


def clean_revoked_tokens() -> None:
    """从进程内吊销表移除已经自然过期的令牌。"""
    now = int(datetime.now(UTC).timestamp())
    expired = [token for token, exp in revoked_tokens.items() if exp <= now]
    for token in expired:
        revoked_tokens.pop(token, None)


async def register_user(session: AsyncSession, request: UserRegisterRequest) -> None:
    """校验注册信息、散列密码并创建用户。

    Args:
        session: 当前请求使用的异步数据库会话。
        request: 用户名、密码及可选资料。

    Raises:
        HTTPException: 输入不合法或用户名已经存在。

    Side Effects:
        插入用户并提交事务；数据库失败时回滚。
    """
    username = request.username.strip()
    password = request.password

    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空")
    if request.sex not in (0, 1):
        raise HTTPException(status_code=400, detail="性别字段只能是 0 或 1")

    password_digest = hash_password(password)

    try:
        result = await session.execute(
            insert(users_table)
            .values(
                username=username,
                password=password_digest,
                email=blank_to_none(request.email),
                sex=request.sex,
                age=request.age,
            )
            .returning(users_table.c.id)
        )

        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    except Exception:
        await session.rollback()
        raise


async def authenticate_user(session: AsyncSession, request: UserLoginRequest) -> dict[str, Any]:
    """按用户名查询并验证密码，成功时返回包含密码摘要的用户字典。

    Raises:
        HTTPException: 用户不存在或密码不匹配。
    """
    username = request.username.strip()
    user = await find_user_by_username(session, username)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    return user_to_dict(user, include_password=True)


async def get_user_info(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """读取用户公开资料，并用固定掩码替代密码字段。"""
    user = await get_user_record(session, user_id)
    return {
        **user_to_dict(user),
        "password": "****",
    }


async def update_user_info(
    session: AsyncSession,
    user_id: str,
    request: UserUpdateRequest,
) -> None:
    """合并并保存用户资料更新。

    未提供的字段保留原值；成功后提交事务。

    Raises:
        HTTPException: 用户不存在、字段不合法或用户名/邮箱发生唯一性冲突。
    """
    user = await get_user_record(session, user_id)
    username = request.username.strip() if request.username else user["username"]

    if request.sex is not None and request.sex not in (0, 1):
        raise HTTPException(status_code=400, detail="性别字段只能是 0 或 1")

    try:
        values = {
            "username": username,
            "email": blank_to_none(request.email) if request.email is not None else user["email"],
            "age": request.age if request.age is not None else user["age"],
            "sex": request.sex if request.sex is not None else user["sex"],
        }
        await session.execute(
            update(users_table)
            .where(users_table.c.id == UUID(user_id))
            .values(**values)
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在") from exc


async def delete_user(session: AsyncSession, user_id: str, username: str) -> None:
    """核对用户名后删除当前用户并提交事务。

    Raises:
        HTTPException: 用户不存在，或提交的用户名不属于当前用户。
    """
    user = await get_user_record(session, user_id)
    if user["username"] != username:
        raise HTTPException(status_code=403, detail="不能删除其他用户")

    await session.execute(delete(users_table).where(users_table.c.id == UUID(user_id)))
    await session.commit()


async def find_user_by_username(session: AsyncSession, username: str) -> Mapping[str, Any] | None:
    """按用户名查询一条原始用户记录，未找到时返回 ``None``。"""
    result = await session.execute(
        select(users_table).where(users_table.c.username == username).limit(1)
    )
    return result.mappings().first()


async def get_user_record(session: AsyncSession, user_id: str) -> Mapping[str, Any]:
    """校验用户 ID 并查询对应数据库记录。

    Raises:
        HTTPException: ID 格式无效或数据库中不存在该用户。
    """
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="用户 ID 无效") from exc

    result = await session.execute(select(users_table).where(users_table.c.id == parsed_user_id))
    user = result.mappings().first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def user_to_dict(user: Mapping[str, Any], include_password: bool = False) -> dict[str, Any]:
    """将数据库用户映射转换为 API 使用的字典，并按需保留密码摘要。"""
    data = {
        "id": str(user["id"]),
        "username": user["username"],
        "email": user["email"],
        "sex": user["sex"],
        "age": user["age"],
    }
    if include_password:
        data["password"] = user["password"]
    return data


def blank_to_none(value: str | None) -> str | None:
    """清理可选文本，将空字符串和纯空白统一为 ``None``。"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

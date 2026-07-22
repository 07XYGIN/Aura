from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from collections.abc import Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import Column, Integer, MetaData, SmallInteger, String, Table, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InvitationCode, InvitationCodeRedemption
from app.db.session import get_db_session
from app.schemas.user import UserLoginRequest, UserRegisterRequest, UserUpdateRequest

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-strong-32-byte-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(milliseconds=int(os.getenv("JWT_EXPIRE_TIME", "86400000")))
INVITE_REGISTRATION_REQUIRED = (
    os.getenv("INVITE_REGISTRATION_REQUIRED", "true").strip().lower() != "false"
)

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
    expire = datetime.now(UTC) + expires_delta
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": str(uuid4()),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def hash_password(password: str) -> str:
    validate_password_length(password)
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    validate_password_length(plain_password)
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    return password_hash.verify(plain_password, hashed_password)


def validate_password_length(password: str) -> None:
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="password must be 72 bytes or shorter")


async def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if isinstance(exp, int):
            revoked_tokens[token] = exp
    except InvalidTokenError:
        return


def clean_revoked_tokens() -> None:
    now = int(datetime.now(UTC).timestamp())
    expired = [token for token, exp in revoked_tokens.items() if exp <= now]
    for token in expired:
        revoked_tokens.pop(token, None)


async def register_user(session: AsyncSession, request: UserRegisterRequest) -> None:
    username = request.username.strip()
    password = request.password

    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not password:
        raise HTTPException(status_code=400, detail="password is required")
    if request.sex not in (0, 1):
        raise HTTPException(status_code=400, detail="sex must be 0 or 1")

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
    username = request.username.strip()
    user = await find_user_by_username(session, username)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="username or password is incorrect")
    return user_to_dict(user, include_password=True)


async def get_user_info(session: AsyncSession, user_id: str) -> dict[str, Any]:
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
    user = await get_user_record(session, user_id)
    username = request.username.strip() if request.username else user["username"]

    if request.sex is not None and request.sex not in (0, 1):
        raise HTTPException(status_code=400, detail="sex must be 0 or 1")

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
        raise HTTPException(status_code=409, detail="username or email already exists") from exc


async def delete_user(session: AsyncSession, user_id: str, username: str) -> None:
    user = await get_user_record(session, user_id)
    if user["username"] != username:
        raise HTTPException(status_code=403, detail="cannot delete another user")

    await session.execute(delete(users_table).where(users_table.c.id == UUID(user_id)))
    await session.commit()


async def get_available_invite_code(session: AsyncSession, invite_code: str) -> InvitationCode | None:
    result = await session.execute(
        select(InvitationCode)
        .where(
            InvitationCode.code == invite_code.upper(),
            InvitationCode.disabled_at.is_(None),
            or_(
                InvitationCode.expires_at.is_(None),
                InvitationCode.expires_at > datetime.now(UTC),
            ),
            InvitationCode.used_count < InvitationCode.max_uses,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def find_user_by_username(session: AsyncSession, username: str) -> Mapping[str, Any] | None:
    result = await session.execute(
        select(users_table).where(users_table.c.username == username).limit(1)
    )
    return result.mappings().first()


async def get_user_record(session: AsyncSession, user_id: str) -> Mapping[str, Any]:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid user id") from exc

    result = await session.execute(select(users_table).where(users_table.c.id == parsed_user_id))
    user = result.mappings().first()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


def user_to_dict(user: Mapping[str, Any], include_password: bool = False) -> dict[str, Any]:
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


def normalize_invite_code(invite_code: str | None) -> str | None:
    if not invite_code or not invite_code.strip():
        return None
    return invite_code.strip().upper()


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

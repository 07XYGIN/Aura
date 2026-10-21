from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.routers import user
from app.schemas.user import UserLoginRequest


class UserLoginTests(IsolatedAsyncioTestCase):
    """验证登录签发的 JWT 身份与认证端约定一致。"""

    async def test_login_uses_user_id_as_token_subject(self) -> None:
        user_id = "b65c9b54-9214-44b4-b8a7-5d7f834d60b0"
        request = UserLoginRequest(username="alice", password="correct-password")
        session = object()

        with (
            patch.object(
                user,
                "authenticate_user",
                new=AsyncMock(
                    return_value={
                        "id": user_id,
                        "username": "alice",
                        "password": "password-digest",
                    }
                ),
            ),
            patch.object(user, "create_access_token", return_value="signed-token") as create_token,
        ):
            response = await user.login(request, session)

        create_token.assert_called_once_with(user_id)
        self.assertEqual(response["token"], "signed-token")

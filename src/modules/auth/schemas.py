"""Схемы Pydantic для эндпоинтов аутентификации."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Схема запроса на регистрацию пользователя."""

    email: EmailStr = Field(
        ...,
        description="Email пользователя для входа в систему",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Пароль пользователя (минимум 8 символов)",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Отображаемое имя пользователя",
        examples=["Иван Петров"],
    )


class LoginRequest(BaseModel):
    """Схема запроса на вход в систему."""

    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Пароль пользователя",
    )


class RefreshRequest(BaseModel):
    """Схема запроса на обновление токена."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Токен обновления для получения новой пары токенов",
    )


class TokenResponse(BaseModel):
    """Схема ответа с токенами аутентификации.

    Возвращается после успешного входа или обновления токена.
    """

    access_token: str = Field(
        ...,
        description="JWT токен доступа",
    )
    refresh_token: str = Field(
        ...,
        description="JWT токен обновления",
    )
    token_type: str = Field(
        default="bearer",
        description="Тип токена (всегда 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Время жизни токена доступа в секундах",
    )


class MessageResponse(BaseModel):
    """Схема простого текстового ответа."""

    message: str = Field(
        ...,
        description="Текст сообщения",
    )

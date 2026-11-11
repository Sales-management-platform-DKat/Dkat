"""Request/response schemas for /auth (JSON uses camelCase)."""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.security import BCRYPT_MAX_BYTES

MIN_PASSWORD_LENGTH = 8


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username must not be blank")
        return v


class ChangePasswordIn(CamelModel):
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def check_bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
        return v


class BranchBrief(CamelModel):
    id: int
    name: str


class AuthUserOut(CamelModel):
    id: int
    full_name: str
    username: str
    role: str
    store_id: int
    branches: list[BranchBrief]


class LoginOut(CamelModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    user: AuthUserOut

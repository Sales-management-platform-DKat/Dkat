"""Request/response schemas for /auth (JSON uses camelCase)."""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(
        min_length=1,
        max_length=255,
        strip_whitespace=True,
        validation_alias=AliasChoices("username", "email"),
    )
    password: str = Field(min_length=1, max_length=256)


EmailAddress = Annotated[
    str,
    StringConstraints(
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        strip_whitespace=True,
        to_lower=True,
    ),
]


class UserCreate(BaseModel):
    username: Username
    email: EmailAddress | None = None
    full_name: str = Field(min_length=1, max_length=120, strip_whitespace=True)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["manager", "staff"]


class BranchBrief(CamelModel):
    id: int
    name: str


class AuthUserOut(CamelModel):
    id: int
    shop_id: int
    username: str
    email: str | None
    full_name: str
    username: str
    role: str
    store_id: int
    branches: list[BranchBrief]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserInfo

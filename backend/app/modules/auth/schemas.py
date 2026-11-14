from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


Username = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9._-]+$",
        strip_whitespace=True,
    ),
]


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


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    username: str
    email: str | None
    full_name: str
    role: Literal["owner", "manager", "staff"]
    shop_name: str
    plan: str
    subscription_expires_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserInfo

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
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
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    username: Username
    full_name: str = Field(min_length=1, max_length=120, strip_whitespace=True)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["manager", "staff"]


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    username: str
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
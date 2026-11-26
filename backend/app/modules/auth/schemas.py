from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, field_validator
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
    remember_me: bool = False
    # UI language at login; only used to name an auto-created default branch.
    locale: Literal["vi", "en"] | None = None


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
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["manager", "staff"]
    branch_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("branch_ids")
    @classmethod
    def validate_branch_ids(cls, value: list[int]) -> list[int]:
        if any(branch_id <= 0 for branch_id in value):
            raise ValueError("Branch ids must be positive")
        return sorted(set(value))


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
    # Branch the UI should select when it has no saved choice (owners get one auto-created).
    default_branch_id: int | None = None
    branch_setup: Literal["existing", "created", "inactive", "failed", "not_applicable"] = "not_applicable"

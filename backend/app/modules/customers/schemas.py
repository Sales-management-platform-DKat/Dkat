from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")] | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None

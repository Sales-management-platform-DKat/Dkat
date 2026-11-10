from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CategoryStatus = Literal["ACTIVE", "INACTIVE"]
CategoryId = Annotated[int, Field(gt=0, le=9223372036854775807)]


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    parentCategoryId: CategoryId | None = None
    description: str | None = Field(default=None, max_length=16000)


class CategoryStatusInput(BaseModel):
    status: CategoryStatus


class Category(BaseModel):
    categoryId: int
    parentCategoryId: int | None
    name: str
    description: str | None
    status: CategoryStatus


class CategoryNode(Category):
    children: list["CategoryNode"] = Field(default_factory=list)

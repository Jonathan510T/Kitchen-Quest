from pydantic import BaseModel, ConfigDict, Field
from .models import Role

class IngredientCreate(BaseModel):
    name: str


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class RecipeIngredientIn(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class RecipeIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingredient: IngredientOut
    quantity: float | None
    unit: str | None


class RecipeCreate(BaseModel):
    title: str
    description: str | None = None
    instructions: str | None = None
    servings: int | None = None
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    instructions: str | None
    servings: int | None
    ingredients: list[RecipeIngredientOut]

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
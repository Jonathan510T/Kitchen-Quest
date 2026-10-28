from typing import Any
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


# Gameplay & Challenge schemas
class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int | None = None
    title: str
    description: str | None = None
    difficulty: str = "Beginner"
    base_xp: int = 100
    time_limit_seconds: int = 120
    chef_tip: str | None = None
    ingredients: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    best_stars: int = 0
    best_score: float = 0.0


class PlayerActionIn(BaseModel):
    timestamp: float = 0.0
    station: str
    action_type: str
    ingredient_names: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AttemptSubmitIn(BaseModel):
    actions: list[PlayerActionIn] = Field(default_factory=list)
    time_taken_seconds: float = 0.0


class AttemptOut(BaseModel):
    challenge_id: int
    accuracy_score: float
    stars: int
    xp_earned: int
    time_taken_seconds: float
    passed: bool
    feedback: list[str] = Field(default_factory=list)
    category_scores: dict[str, float] = Field(default_factory=dict)
    new_total_xp: int
    new_level: int
    rank_title: str
    leveled_up: bool


class UserProgressOut(BaseModel):
    user_id: int
    total_xp: int
    current_level: int
    rank_title: str
    current_level_base_xp: int
    next_level_xp: int
    completed_challenges_count: int
    total_stars: int

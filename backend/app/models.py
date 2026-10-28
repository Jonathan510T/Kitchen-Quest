import enum
from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    recipe_links: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    servings: Mapped[int | None]

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
    )
    challenges: Mapped[list["Challenge"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (UniqueConstraint("recipe_id", "ingredient_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(String(30))

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_links")


class Role(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20), default=Role.user
    )

    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    progress: Mapped["UserProgress | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(30), default="Beginner")
    base_xp: Mapped[int] = mapped_column(Integer, default=100)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=120)
    chef_tip: Mapped[str | None] = mapped_column(Text)
    steps_json: Mapped[str] = mapped_column(Text)  # JSON-serialized steps
    ingredients_json: Mapped[str] = mapped_column(Text)  # JSON-serialized ingredients

    recipe: Mapped["Recipe | None"] = relationship(back_populates="challenges")
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    time_taken_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback_json: Mapped[str | None] = mapped_column(Text)
    actions_log_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="attempts")
    challenge: Mapped["Challenge"] = relationship(back_populates="attempts")


class UserProgress(Base):
    __tablename__ = "user_progress"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    rank_title: Mapped[str] = mapped_column(String(50), default="Prep Cook")

    user: Mapped["User"] = relationship(back_populates="progress")

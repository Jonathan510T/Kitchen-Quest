"""Core gameplay domain models for Kitchen Quest."""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class Station(str, Enum):
    PANTRY = "pantry"
    PREP = "prep"
    MIXING = "mixing"
    STOVE = "stove"
    PLATING = "plating"


class IngredientState(str, Enum):
    RAW = "raw"
    SLICED = "sliced"
    CHOPPED = "chopped"
    DICED = "diced"
    MINCED = "minced"
    MIXED = "mixed"
    COOKING = "cooking"
    PERFECT = "perfect"
    OVERCOOKED = "overcooked"
    BURNT = "burnt"


class ActionType(str, Enum):
    # Prep actions
    SLICE = "slice"
    CHOP = "chop"
    DICE = "dice"
    MINCE = "mince"
    # Mixing actions
    COMBINE = "combine"
    STIR = "stir"
    WHISK = "whisk"
    # Stove actions
    HEAT_SET = "heat_set"
    SAUTE = "saute"
    SIMMER = "simmer"
    BOIL = "boil"
    FRY = "fry"
    STOVE_REMOVE = "stove_remove"
    # Plating actions
    ADD_TO_PLATE = "add_to_plate"
    SEASON_SALT = "season_salt"
    SEASON_PEPPER = "season_pepper"
    SEASON_HERBS = "season_herbs"
    GARNISH = "garnish"
    SERVE = "serve"


class HeatLevel(str, Enum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class IngredientItem:
    id: str
    name: str
    state: IngredientState = IngredientState.RAW
    quantity: float = 1.0
    unit: str = "pcs"
    icon: str = "🥕"
    current_station: Station = Station.PANTRY

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "icon": self.icon,
            "current_station": self.current_station.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IngredientItem":
        return cls(
            id=data["id"],
            name=data["name"],
            state=IngredientState(data.get("state", "raw")),
            quantity=float(data.get("quantity", 1.0)),
            unit=data.get("unit", "pcs"),
            icon=data.get("icon", "🥕"),
            current_station=Station(data.get("current_station", "pantry")),
        )


@dataclass
class CookingStep:
    step_number: int
    title: str
    instruction: str
    station: Station
    required_action: ActionType
    target_ingredients: list[str]  # Ingredient names
    target_state: IngredientState | None = None
    target_heat: HeatLevel | None = None
    target_duration: float = 0.0  # Seconds for timed steps (e.g. simmer)
    duration_tolerance: float = 3.0  # Acceptable variance in seconds
    required_clicks: int = 3  # For cadence actions like chopping
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "title": self.title,
            "instruction": self.instruction,
            "station": self.station.value,
            "required_action": self.required_action.value,
            "target_ingredients": self.target_ingredients,
            "target_state": self.target_state.value if self.target_state else None,
            "target_heat": self.target_heat.value if self.target_heat else None,
            "target_duration": self.target_duration,
            "duration_tolerance": self.duration_tolerance,
            "required_clicks": self.required_clicks,
            "hint": self.hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CookingStep":
        return cls(
            step_number=data["step_number"],
            title=data["title"],
            instruction=data["instruction"],
            station=Station(data["station"]),
            required_action=ActionType(data["required_action"]),
            target_ingredients=data.get("target_ingredients", []),
            target_state=IngredientState(data["target_state"]) if data.get("target_state") else None,
            target_heat=HeatLevel(data["target_heat"]) if data.get("target_heat") else None,
            target_duration=float(data.get("target_duration", 0.0)),
            duration_tolerance=float(data.get("duration_tolerance", 3.0)),
            required_clicks=int(data.get("required_clicks", 3)),
            hint=data.get("hint", ""),
        )


@dataclass
class RecipeChallenge:
    id: int
    title: str
    description: str
    difficulty: str  # "Beginner", "Intermediate", "Advanced"
    servings: int
    base_xp: int
    time_limit_seconds: int
    ingredients: list[IngredientItem]
    steps: list[CookingStep]
    chef_tip: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "servings": self.servings,
            "base_xp": self.base_xp,
            "time_limit_seconds": self.time_limit_seconds,
            "ingredients": [item.to_dict() for item in self.ingredients],
            "steps": [step.to_dict() for step in self.steps],
            "chef_tip": self.chef_tip,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecipeChallenge":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            difficulty=data.get("difficulty", "Beginner"),
            servings=int(data.get("servings", 1)),
            base_xp=int(data.get("base_xp", 100)),
            time_limit_seconds=int(data.get("time_limit_seconds", 120)),
            ingredients=[IngredientItem.from_dict(i) for i in data.get("ingredients", [])],
            steps=[CookingStep.from_dict(s) for s in data.get("steps", [])],
            chef_tip=data.get("chef_tip", ""),
        )


@dataclass
class PlayerActionRecord:
    timestamp: float
    station: Station
    action_type: ActionType
    ingredient_names: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "station": self.station.value,
            "action_type": self.action_type.value,
            "ingredient_names": self.ingredient_names,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerActionRecord":
        return cls(
            timestamp=float(data.get("timestamp", time.time())),
            station=Station(data["station"]),
            action_type=ActionType(data["action_type"]),
            ingredient_names=data.get("ingredient_names", []),
            parameters=data.get("parameters", {}),
        )


@dataclass
class AttemptResult:
    challenge_id: int
    accuracy_score: float  # 0.0 to 100.0
    stars: int  # 0, 1, 2, or 3
    xp_earned: int
    time_taken_seconds: float
    passed: bool
    feedback: list[str]
    category_scores: dict[str, float]  # e.g. {"prep": 95.0, "cooking": 88.0, "seasoning": 100.0}
    new_total_xp: int = 0
    new_level: int = 1
    rank_title: str = "Prep Cook"
    leveled_up: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "accuracy_score": round(self.accuracy_score, 1),
            "stars": self.stars,
            "xp_earned": self.xp_earned,
            "time_taken_seconds": round(self.time_taken_seconds, 1),
            "passed": self.passed,
            "feedback": self.feedback,
            "category_scores": self.category_scores,
            "new_total_xp": self.new_total_xp,
            "new_level": self.new_level,
            "rank_title": self.rank_title,
            "leveled_up": self.leveled_up,
        }


@dataclass
class UserProgressData:
    user_id: int
    total_xp: int = 0
    current_level: int = 1
    rank_title: str = "Prep Cook"
    completed_challenges: dict[int, int] = field(default_factory=dict)  # challenge_id -> best stars

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "total_xp": self.total_xp,
            "current_level": self.current_level,
            "rank_title": self.rank_title,
            "completed_challenges": self.completed_challenges,
        }


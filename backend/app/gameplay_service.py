from datetime import datetime, timezone
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from gameplay.engine import CookingEvaluator
from gameplay.models import (
    ActionType,
    CookingStep,
    IngredientItem,
    PlayerActionRecord,
    RecipeChallenge,
    Station,
)
from gameplay.recipes import get_default_challenges

from . import models, schemas


def sync_challenge_id_sequence(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('challenges', 'id'), "
            "COALESCE((SELECT MAX(id) FROM challenges), 0) + 1, false)"
        )
    )
    db.commit()


def seed_default_challenges(db: Session) -> None:
    count = db.scalar(select(func.count(models.Challenge.id)))
    if count and count > 0:
        return

    for c in get_default_challenges():
        # Check if matching recipe exists
        recipe = db.scalar(
            select(models.Recipe).where(func.lower(models.Recipe.title) == c.title.lower())
        )
        recipe_id = recipe.id if recipe else None

        db_challenge = models.Challenge(
            id=c.id,
            recipe_id=recipe_id,
            title=c.title,
            description=c.description,
            difficulty=c.difficulty,
            servings=c.servings,
            base_xp=c.base_xp,
            time_limit_seconds=c.time_limit_seconds,
            chef_tip=c.chef_tip,
            ingredients_json=json.dumps([item.to_dict() for item in c.ingredients]),
            steps_json=json.dumps([step.to_dict() for step in c.steps]),
        )
        db.add(db_challenge)
    db.commit()
    sync_challenge_id_sequence(db)


def get_user_progress(db: Session, user_id: int) -> models.UserProgress:
    prog = db.get(models.UserProgress, user_id)
    if prog is None:
        prog = models.UserProgress(
            user_id=user_id,
            total_xp=0,
            current_level=1,
            rank_title="Prep Cook",
        )
        db.add(prog)
        db.commit()
        db.refresh(prog)
    return prog


def challenge_to_schema(
    challenge: models.Challenge, user_id: int, db: Session
) -> schemas.ChallengeOut:
    ingredients = json.loads(challenge.ingredients_json) if challenge.ingredients_json else []
    steps = json.loads(challenge.steps_json) if challenge.steps_json else []

    best = db.scalar(
        select(models.ChallengeProgress).where(
            models.ChallengeProgress.user_id == user_id,
            models.ChallengeProgress.challenge_id == challenge.id,
        )
    )

    return schemas.ChallengeOut(
        id=challenge.id,
        recipe_id=challenge.recipe_id,
        title=challenge.title,
        description=challenge.description,
        difficulty=challenge.difficulty,
        servings=challenge.servings,
        base_xp=challenge.base_xp,
        time_limit_seconds=challenge.time_limit_seconds,
        chef_tip=challenge.chef_tip,
        ingredients=ingredients,
        steps=steps,
        best_stars=best.best_stars if best else 0,
        best_score=float(best.best_score) if best else 0.0,
    )


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise _invalid("Title cannot be blank")
    return title


def _ensure_unique_title(db: Session, title: str, exclude_id: int | None = None) -> None:
    stmt = select(models.Challenge.id).where(func.lower(models.Challenge.title) == title.lower())
    if exclude_id is not None:
        stmt = stmt.where(models.Challenge.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="A challenge with this title already exists")


def _ensure_recipe_exists(db: Session, recipe_id: int | None) -> None:
    if recipe_id is not None and db.get(models.Recipe, recipe_id) is None:
        raise _invalid("Linked recipe does not exist")


def _validate_content(
    ingredients: list[dict[str, Any]], steps: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        items = [IngredientItem.from_dict(i) for i in ingredients]
        parsed = [CookingStep.from_dict(s) for s in steps]
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise _invalid(f"Invalid ingredient or step data: {exc}") from None

    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise _invalid("Ingredient ids must be unique")
    numbers = [s.step_number for s in parsed]
    if len(numbers) != len(set(numbers)):
        raise _invalid("Step numbers must be unique")

    names = {i.name.lower() for i in items}
    for step in parsed:
        unknown = [n for n in step.target_ingredients if n.lower() not in names]
        if unknown:
            raise _invalid(f"Step {step.step_number} targets unknown ingredients: {', '.join(unknown)}")
        if step.required_clicks < 1 or step.target_duration < 0 or step.duration_tolerance < 0:
            raise _invalid(f"Step {step.step_number} has invalid clicks or durations")

    return [i.to_dict() for i in items], [s.to_dict() for s in parsed]


def create_challenge(payload: schemas.ChallengeCreate, db: Session) -> models.Challenge:
    title = _clean_title(payload.title)
    _ensure_unique_title(db, title)
    _ensure_recipe_exists(db, payload.recipe_id)
    ingredients, steps = _validate_content(payload.ingredients, payload.steps)

    challenge = models.Challenge(
        recipe_id=payload.recipe_id,
        title=title,
        description=payload.description,
        difficulty=payload.difficulty,
        servings=payload.servings,
        base_xp=payload.base_xp,
        time_limit_seconds=payload.time_limit_seconds,
        chef_tip=payload.chef_tip,
        ingredients_json=json.dumps(ingredients),
        steps_json=json.dumps(steps),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def update_challenge(
    challenge: models.Challenge, payload: schemas.ChallengeUpdate, db: Session
) -> models.Challenge:
    changes = payload.model_dump(exclude_unset=True)

    for field in ("title", "difficulty", "servings", "base_xp", "time_limit_seconds", "ingredients", "steps"):
        if field in changes and changes[field] is None:
            raise _invalid(f"{field} cannot be null")

    if "title" in changes:
        changes["title"] = _clean_title(changes["title"])
        _ensure_unique_title(db, changes["title"], exclude_id=challenge.id)
    if "recipe_id" in changes:
        _ensure_recipe_exists(db, changes["recipe_id"])

    if "ingredients" in changes or "steps" in changes:
        ingredients = (
            changes.pop("ingredients") if "ingredients" in changes
            else json.loads(challenge.ingredients_json)
        )
        steps = changes.pop("steps") if "steps" in changes else json.loads(challenge.steps_json)
        ingredients, steps = _validate_content(ingredients, steps)
        changes["ingredients_json"] = json.dumps(ingredients)
        changes["steps_json"] = json.dumps(steps)

    for key, value in changes.items():
        setattr(challenge, key, value)
    db.commit()
    db.refresh(challenge)
    return challenge


def delete_challenge(challenge: models.Challenge, db: Session) -> None:
    db.delete(challenge)
    db.commit()


def update_challenge_progress(
    db: Session, user_id: int, challenge_id: int, attempt: models.Attempt
) -> models.ChallengeProgress:
    """Upsert the user's per-challenge record from a freshly scored attempt."""
    row = db.scalar(
        select(models.ChallengeProgress).where(
            models.ChallengeProgress.user_id == user_id,
            models.ChallengeProgress.challenge_id == challenge_id,
        )
    )
    if row is None:
        row = models.ChallengeProgress(
            user_id=user_id,
            challenge_id=challenge_id,
            best_stars=0,
            best_score=0.0,
            attempts_count=0,
            completed=False,
        )
        db.add(row)

    row.attempts_count += 1
    row.last_attempt_at = attempt.created_at
    if (attempt.stars, attempt.accuracy_score) > (row.best_stars, row.best_score):
        row.best_stars = attempt.stars
        row.best_score = attempt.accuracy_score
    if attempt.passed:
        row.completed = True
        if row.first_completed_at is None:
            row.first_completed_at = attempt.created_at
        if row.best_time_seconds is None or attempt.time_taken_seconds < row.best_time_seconds:
            row.best_time_seconds = attempt.time_taken_seconds
    return row


def process_attempt(
    challenge: models.Challenge,
    payload: schemas.AttemptSubmitIn,
    user: models.User,
    db: Session,
) -> schemas.AttemptOut:
    # 1. Parse Challenge domain object
    raw_ingredients = json.loads(challenge.ingredients_json) if challenge.ingredients_json else []
    raw_steps = json.loads(challenge.steps_json) if challenge.steps_json else []

    domain_challenge = RecipeChallenge(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description or "",
        difficulty=challenge.difficulty,
        servings=challenge.servings,
        base_xp=challenge.base_xp,
        time_limit_seconds=challenge.time_limit_seconds,
        chef_tip=challenge.chef_tip or "",
        ingredients=[IngredientItem.from_dict(i) for i in raw_ingredients],
        steps=[CookingStep.from_dict(s) for s in raw_steps],
    )

    # 2. Convert actions to domain PlayerActionRecord list
    domain_actions: list[PlayerActionRecord] = []
    for a in payload.actions:
        try:
            domain_actions.append(
                PlayerActionRecord(
                    timestamp=a.timestamp,
                    station=Station(a.station.lower()),
                    action_type=ActionType(a.action_type.lower()),
                    ingredient_names=a.ingredient_names,
                    parameters=a.parameters,
                )
            )
        except Exception:
            continue

    # 3. Retrieve user progress
    progress = get_user_progress(db, user.id)

    # 4. Evaluate attempt
    evaluator = CookingEvaluator()
    eval_result = evaluator.evaluate(
        domain_challenge,
        domain_actions,
        payload.time_taken_seconds,
        existing_total_xp=progress.total_xp,
    )

    # 5. Persist Attempt
    actions_data = [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in payload.actions]
    attempt = models.Attempt(
        user_id=user.id,
        challenge_id=challenge.id,
        accuracy_score=eval_result.accuracy_score,
        stars=eval_result.stars,
        xp_earned=eval_result.xp_earned,
        time_taken_seconds=eval_result.time_taken_seconds,
        passed=eval_result.passed,
        feedback_json=json.dumps(eval_result.feedback),
        actions_log_json=json.dumps(actions_data),
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)

    # 6. Update user progress and per-challenge best results (single transaction)
    progress.total_xp = eval_result.new_total_xp
    progress.current_level = eval_result.new_level
    progress.rank_title = eval_result.rank_title
    update_challenge_progress(db, user.id, challenge.id, attempt)
    db.commit()

    return schemas.AttemptOut(
        challenge_id=challenge.id,
        accuracy_score=eval_result.accuracy_score,
        stars=eval_result.stars,
        xp_earned=eval_result.xp_earned,
        time_taken_seconds=eval_result.time_taken_seconds,
        passed=eval_result.passed,
        feedback=eval_result.feedback,
        category_scores=eval_result.category_scores,
        new_total_xp=eval_result.new_total_xp,
        new_level=eval_result.new_level,
        rank_title=eval_result.rank_title,
        leveled_up=eval_result.leveled_up,
    )
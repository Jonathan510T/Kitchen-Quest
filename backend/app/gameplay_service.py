"""Backend gameplay evaluation, attempt persistence, and challenge seeding."""

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from gameplay.engine import CookingEvaluator, ProgressionManager
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
            base_xp=c.base_xp,
            time_limit_seconds=c.time_limit_seconds,
            chef_tip=c.chef_tip,
            ingredients_json=json.dumps([item.to_dict() for item in c.ingredients]),
            steps_json=json.dumps([step.to_dict() for step in c.steps]),
        )
        db.add(db_challenge)
    db.commit()


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

    best_attempt = db.scalar(
        select(models.Attempt)
        .where(models.Attempt.user_id == user_id, models.Attempt.challenge_id == challenge.id)
        .order_by(desc(models.Attempt.stars), desc(models.Attempt.accuracy_score))
    )

    return schemas.ChallengeOut(
        id=challenge.id,
        recipe_id=challenge.recipe_id,
        title=challenge.title,
        description=challenge.description,
        difficulty=challenge.difficulty,
        base_xp=challenge.base_xp,
        time_limit_seconds=challenge.time_limit_seconds,
        chef_tip=challenge.chef_tip,
        ingredients=ingredients,
        steps=steps,
        best_stars=best_attempt.stars if best_attempt else 0,
        best_score=float(best_attempt.accuracy_score) if best_attempt else 0.0,
    )


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
        servings=1,
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
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(attempt)

    # 6. Update User Progress
    progress.total_xp = eval_result.new_total_xp
    progress.current_level = eval_result.new_level
    progress.rank_title = eval_result.rank_title
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

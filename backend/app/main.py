from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from gameplay.engine import ProgressionManager

from . import auth, database, gameplay_service, models, schemas
from .database import get_db
from .security import get_current_user, require_admin

app = FastAPI(title="Kitchen Quest API")

# Ensure database tables exist
models.Base.metadata.create_all(bind=database.engine)

app.include_router(auth.router)


@app.get("/api/ingredients", response_model=list[schemas.IngredientOut])
def list_ingredients(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return db.scalars(select(models.Ingredient).order_by(models.Ingredient.name)).all()


@app.get("/api/recipes", response_model=list[schemas.RecipeOut])
def list_recipes(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    stmt = (
        select(models.Recipe)
        .options(
            selectinload(models.Recipe.ingredients).selectinload(
                models.RecipeIngredient.ingredient
            )
        )
        .order_by(models.Recipe.title)
    )
    return db.scalars(stmt).all()


@app.get("/api/recipes/{recipe_id}", response_model=schemas.RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.post("/api/recipes", response_model=schemas.RecipeOut, status_code=201)
def create_recipe(payload: schemas.RecipeCreate, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    title = payload.title.strip()
    existing = db.scalar(
        select(models.Recipe).where(func.lower(models.Recipe.title) == title.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A recipe with this title already exists")

    names = [item.name.strip().lower() for item in payload.ingredients]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=422, detail="Duplicate ingredient in recipe")

    recipe = models.Recipe(
        title=title,
        description=payload.description,
        instructions=payload.instructions,
        servings=payload.servings,
    )

    for item in payload.ingredients:
        name = item.name.strip().lower()
        ingredient = db.scalar(
            select(models.Ingredient).where(models.Ingredient.name == name)
        )
        if ingredient is None:
            ingredient = models.Ingredient(name=name)
        recipe.ingredients.append(
            models.RecipeIngredient(
                ingredient=ingredient, quantity=item.quantity, unit=item.unit
            )
        )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@app.delete("/api/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(recipe)
    db.commit()


# ==========================================
# GAMEPLAY & CHALLENGE ENDPOINTS
# ==========================================

@app.get("/api/challenges", response_model=list[schemas.ChallengeOut])
def list_challenges(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    gameplay_service.seed_default_challenges(db)
    challenges = db.scalars(select(models.Challenge).order_by(models.Challenge.id)).all()
    return [
        gameplay_service.challenge_to_schema(c, current_user.id, db)
        for c in challenges
    ]


@app.get("/api/challenges/{challenge_id}", response_model=schemas.ChallengeOut)
def get_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    gameplay_service.seed_default_challenges(db)
    challenge = db.get(models.Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Cooking challenge not found")
    return gameplay_service.challenge_to_schema(challenge, current_user.id, db)


@app.post("/api/challenges/{challenge_id}/attempts", response_model=schemas.AttemptOut)
def submit_challenge_attempt(
    challenge_id: int,
    payload: schemas.AttemptSubmitIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    challenge = db.get(models.Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Cooking challenge not found")

    return gameplay_service.process_attempt(challenge, payload, current_user, db)


@app.get("/api/progress", response_model=schemas.UserProgressOut)
def get_progress(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    prog = gameplay_service.get_user_progress(db, current_user.id)
    _, title, base_xp, next_xp = ProgressionManager.get_level_info(prog.total_xp)

    attempts = db.scalars(
        select(models.Attempt).where(models.Attempt.user_id == current_user.id)
    ).all()
    passed_attempts = [a for a in attempts if a.passed]
    total_stars = sum(a.stars for a in passed_attempts)

    return schemas.UserProgressOut(
        user_id=current_user.id,
        total_xp=prog.total_xp,
        current_level=prog.current_level,
        rank_title=title,
        current_level_base_xp=base_xp,
        next_level_xp=next_xp,
        completed_challenges_count=len(set(a.challenge_id for a in passed_attempts)),
        total_stars=total_stars,
    )

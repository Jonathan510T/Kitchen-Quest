from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import auth
from .security import get_current_user, require_admin
from . import models, schemas
from .database import get_db

app = FastAPI()

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
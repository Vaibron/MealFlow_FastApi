from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from apps.meal_planner.models import MealPlan, ExcludedIngredient
from apps.recipes.models import Recipe, RecipeIngredient, Ingredient, MealType, RecipeMealType
from fastapi import HTTPException
import random
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)

async def create_meal_plan(db: AsyncSession, user_id: int, start_date: datetime, days: int, persons: int,
                           excluded_ingredients: List[int], recipe_source: str = "both"):
    today = datetime.utcnow().date()
    max_date = today + timedelta(days=14)
    start_date_date = start_date.date()
    end_date = start_date_date + timedelta(days=days - 1)

    if start_date_date < today:
        raise HTTPException(status_code=400, detail="Нельзя генерировать меню на прошлые даты")
    if start_date_date > max_date:
        raise HTTPException(status_code=400, detail="Дата начала не может быть позже чем +14 дней от текущей")
    if end_date > max_date:
        raise HTTPException(status_code=400, detail="План не может заканчиваться позже чем +14 дней от текущей")

    existing_plan = await get_meal_plan(db, user_id)

    if existing_plan:
        db_plan = existing_plan
    else:
        db_plan = MealPlan(
            user_id=user_id,
            start_date=start_date,
            days=days,
            persons=persons,
            plan={},
            recipe_source=recipe_source
        )

    await db.execute(ExcludedIngredient.__table__.delete().where(ExcludedIngredient.user_id == user_id))
    for ing_id in excluded_ingredients:
        db_excluded = ExcludedIngredient(user_id=user_id, ingredient_id=ing_id)
        db.add(db_excluded)

    query = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.meal_types).selectinload(RecipeMealType.meal_type)
        )
    )
    if recipe_source == "mine":
        query = query.filter(Recipe.user_id == user_id)
    elif recipe_source == "mealflow":
        query = query.filter(Recipe.is_public == True)
    else:
        query = query.filter((Recipe.user_id == user_id) | (Recipe.is_public == True))

    result = await db.execute(query)
    all_recipes = result.unique().scalars().all()

    filtered_recipes = [
        r for r in all_recipes
        if not any(ri.ingredient_id in excluded_ingredients for ri in r.ingredients)
    ]
    if not filtered_recipes:
        raise HTTPException(status_code=400, detail="Нет доступных рецептов")

    meal_types_result = await db.execute(
        select(MealType).filter(MealType.is_active == True).order_by(MealType.order)
    )
    meal_types = meal_types_result.scalars().all()

    new_plan = {}
    for day in range(days):
        date_key = (start_date_date + timedelta(days=day)).strftime('%Y-%m-%d')
        day_plan = {}
        for mt in meal_types:
            mt_recipes = [r for r in filtered_recipes if any(rmt.meal_type_id == mt.id for rmt in r.meal_types)]
            if mt_recipes:
                selected_recipe = random.choice(mt_recipes)
                day_plan[str(mt.id)] = selected_recipe.id
        new_plan[date_key] = day_plan

    existing_plan_dict = db_plan.plan.copy() if db_plan.plan else {}

    for date_key in list(existing_plan_dict.keys()):
        existing_date = datetime.strptime(date_key, '%Y-%m-%d').date()
        if start_date_date <= existing_date <= end_date:
            del existing_plan_dict[date_key]

    existing_plan_dict.update(new_plan)
    db_plan.plan = existing_plan_dict

    cutoff_date = datetime.utcnow().date() - timedelta(days=14)
    db_plan.plan = {
        k: v for k, v in db_plan.plan.items()
        if datetime.strptime(k, '%Y-%m-%d').date() >= cutoff_date
    }

    if db_plan.plan:
        plan_dates = [datetime.strptime(k, '%Y-%m-%d').date() for k in db_plan.plan.keys()]
        db_plan.start_date = min(plan_dates)
        db_plan.days = (max(plan_dates) - min(plan_dates)).days + 1
    else:
        db_plan.start_date = start_date_date
        db_plan.days = days

    db_plan.persons = persons
    db_plan.recipe_source = recipe_source

    db.add(db_plan)
    await db.commit()
    await db.refresh(db_plan)

    db_plan.meal_types = [{"id": mt.id, "name": mt.name, "order": mt.order} for mt in meal_types]
    logger.info(f"Meal plan created/updated for user_id={user_id}, start_date={start_date_date}, days={days}")
    return db_plan

async def get_meal_plan(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(MealPlan).filter(MealPlan.user_id == user_id)
    )
    meal_plan = result.scalars().first()
    if meal_plan:
        cutoff_date = datetime.utcnow().date() - timedelta(days=14)
        meal_plan.plan = {
            k: v for k, v in meal_plan.plan.items()
            if datetime.strptime(k, '%Y-%m-%d').date() >= cutoff_date
        }

        if meal_plan.plan:
            plan_dates = [datetime.strptime(k, '%Y-%m-%d').date() for k in meal_plan.plan.keys()]
            meal_plan.start_date = min(plan_dates)
            meal_plan.days = (max(plan_dates) - min(plan_dates)).days + 1
        else:
            meal_plan.start_date = datetime.utcnow().date()
            meal_plan.days = 0

        meal_types_result = await db.execute(
            select(MealType).filter(MealType.is_active == True).order_by(MealType.order)
        )
        meal_types = meal_types_result.scalars().all()
        meal_plan.meal_types = [{"id": mt.id, "name": mt.name, "order": mt.order} for mt in meal_types]

        db.add(meal_plan)
        await db.commit()
        await db.refresh(meal_plan)
        logger.info(f"Meal plan retrieved for user_id={user_id}")
    return meal_plan

async def get_excluded_ingredients(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(ExcludedIngredient).filter(ExcludedIngredient.user_id == user_id)
    )
    excluded = result.scalars().all()
    logger.info(f"Retrieved {len(excluded)} excluded ingredients for user_id={user_id}")
    return excluded

async def replace_recipe(db: AsyncSession, user_id: int, date_str: str, meal_type_id: int, new_recipe_id: int | None):
    logger.info(f"Attempting to replace recipe for user_id={user_id}, date={date_str}, meal_type_id={meal_type_id}, new_recipe_id={new_recipe_id}")

    meal_plan = await get_meal_plan(db, user_id)
    if not meal_plan or not meal_plan.plan:
        logger.error("Meal plan not found or empty")
        raise ValueError("Меню не найдено или пустое")

    if date_str not in meal_plan.plan:
        logger.error(f"Date {date_str} not found in meal plan")
        raise ValueError("Указанная дата не входит в план меню")

    day_plan = meal_plan.plan[date_str]
    if str(meal_type_id) not in day_plan:
        logger.error(f"Meal type {meal_type_id} not found for date {date_str}")
        raise ValueError("Указанный тип блюда не найден для этой даты")

    excluded_ingredients = [ei.ingredient_id for ei in await get_excluded_ingredients(db, user_id)]
    logger.debug(f"Excluded ingredients: {excluded_ingredients}")

    existing_plan = await db.execute(
        select(MealPlan).filter(MealPlan.user_id == user_id)
    )
    db_plan = existing_plan.scalars().first()
    if not db_plan:
        logger.error("Meal plan not found in database")
        raise ValueError("Меню не найдено")

    query = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.meal_types).selectinload(RecipeMealType.meal_type)
        )
    )
    if db_plan.recipe_source == "mine":
        query = query.filter(Recipe.user_id == user_id)
    elif db_plan.recipe_source == "mealflow":
        query = query.filter(Recipe.is_public == True)
    else:
        query = query.filter((Recipe.user_id == user_id) | (Recipe.is_public == True))

    result = await db.execute(query)
    all_recipes = result.unique().scalars().all()

    filtered_recipes = [
        r for r in all_recipes
        if (
            not any(ri.ingredient_id in excluded_ingredients for ri in r.ingredients) and
            any(rmt.meal_type_id == meal_type_id for rmt in r.meal_types)
        )
    ]
    if not filtered_recipes:
        logger.error("No available recipes for replacement")
        raise ValueError("Нет доступных рецептов для замены с учетом ограничений")

    if new_recipe_id:
        selected_recipe = next((r for r in filtered_recipes if r.id == new_recipe_id), None)
        if not selected_recipe:
            logger.error(f"Recipe {new_recipe_id} not available or does not meet constraints")
            raise ValueError("Указанный рецепт недоступен или не соответствует ограничениям")
    else:
        selected_recipe = random.choice(filtered_recipes)

    logger.info(f"Selected recipe for replacement: {selected_recipe.id} ({selected_recipe.title})")

    # Обновляем план
    meal_plan.plan[date_str][str(meal_type_id)] = selected_recipe.id
    db_plan.plan = meal_plan.plan  # Избыточное присваивание, но оставлено для совместимости
    flag_modified(db_plan, "plan")  # Помечаем поле plan как измененное

    # Обновляем даты и количество дней
    if db_plan.plan:
        plan_dates = [datetime.strptime(k, '%Y-%m-%d').date() for k in db_plan.plan.keys()]
        db_plan.start_date = min(plan_dates)
        db_plan.days = (max(plan_dates) - min(plan_dates)).days + 1

    db.add(db_plan)
    await db.commit()
    await db.refresh(db_plan)

    meal_types_result = await db.execute(
        select(MealType).filter(MealType.is_active == True).order_by(MealType.order)
    )
    meal_types = meal_types_result.scalars().all()
    db_plan.meal_types = [{"id": mt.id, "name": mt.name, "order": mt.order} for mt in meal_types]

    logger.info(f"Recipe replaced successfully for date={date_str}, meal_type_id={meal_type_id}, new_recipe_id={selected_recipe.id}")
    return db_plan

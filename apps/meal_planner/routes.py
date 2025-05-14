from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from apps.meal_planner.schemas import MealPlanCreate, MealPlan, ExcludedIngredient
from apps.meal_planner.crud import create_meal_plan, get_meal_plan, get_excluded_ingredients, replace_recipe
from core.dependencies import get_db
from apps.auth.routes import get_current_user
from apps.auth.models import User
from typing import List
import logging

router = APIRouter(prefix="/meal-planner", tags=["meal-planner"])
logger = logging.getLogger(__name__)

MAX_DAYS = 7


@router.post("/generate", response_model=MealPlan)
async def generate_meal_plan(
        data: MealPlanCreate,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    logger.info(f"Generating meal plan for user_id={user.id}, days={data.days}, start_date={data.start_date}")
    if data.days > MAX_DAYS:
        logger.warning(f"Requested days ({data.days}) exceeds maximum ({MAX_DAYS})")
        raise HTTPException(status_code=400, detail=f"Максимальный период — {MAX_DAYS} дней")
    meal_plan = await create_meal_plan(
        db,
        user.id,
        data.start_date,
        data.days,
        data.persons,
        data.excluded_ingredients or [],
        data.recipe_source
    )
    logger.info(f"Meal plan generated successfully for user_id={user.id}")
    return meal_plan


@router.get("/current", response_model=MealPlan)
async def get_current_meal_plan(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    logger.info(f"Fetching current meal plan for user_id={user.id}")
    meal_plan = await get_meal_plan(db, user.id)
    if not meal_plan:
        logger.info(f"No meal plan found for user_id={user.id}, returning empty plan")
        return MealPlan(
            id=None,
            user_id=user.id,
            start_date=None,
            days=0,
            persons=0,
            plan={}
        )
    logger.info(f"Current meal plan retrieved for user_id={user.id}")
    return meal_plan


@router.get("/excluded-ingredients", response_model=List[ExcludedIngredient])
async def get_user_excluded_ingredients(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    logger.info(f"Fetching excluded ingredients for user_id={user.id}")
    excluded = await get_excluded_ingredients(db, user.id)
    logger.info(f"Retrieved {len(excluded)} excluded ingredients for user_id={user.id}")
    return excluded


@router.post("/replace-recipe", response_model=MealPlan)
async def replace_meal_plan_recipe(
        data: dict,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    date_str = data.get("date")
    meal_type_id = data.get("meal_type_id")
    new_recipe_id = data.get("new_recipe_id")
    logger.info(
        f"Replacing recipe for user_id={user.id}, date={date_str}, meal_type_id={meal_type_id}, new_recipe_id={new_recipe_id}")

    if not date_str or meal_type_id is None:
        logger.error("Missing required parameters: date or meal_type_id")
        raise HTTPException(status_code=400, detail="Не указаны дата или тип блюда")

    try:
        meal_plan = await replace_recipe(
            db,
            user.id,
            date_str,
            meal_type_id,
            new_recipe_id
        )
        logger.info(f"Recipe replaced successfully for user_id={user.id}")
        return meal_plan
    except ValueError as e:
        logger.error(f"Error replacing recipe: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error replacing recipe: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

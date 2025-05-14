from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from apps.recipes.models import Recipe, RecipeIngredient, Ingredient, RecipeMealType, MealType, RecipeDishCategory, DishCategory, RecipeTag, Tag
from apps.recipes.schemas import RecipeCreate, RecipeUpdate
from fastapi import HTTPException
import logging
from sqlalchemy.orm import selectinload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_recipe(db: AsyncSession, recipe: RecipeCreate, user_id: int, image_path: str = None):
    existing_recipe_query = (
        select(Recipe)
        .filter(
            Recipe.user_id == user_id,
            Recipe.title == recipe.title,
        )
    )
    result = await db.execute(existing_recipe_query)
    existing_recipe = result.scalars().first()

    if existing_recipe:
        logger.info(f"Рецепт '{recipe.title}' уже существует для user_id={user_id}, возвращаем существующий")
        await db.refresh(existing_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags"])
        for ri in existing_recipe.ingredients:
            await db.refresh(ri, attribute_names=["ingredient"])
        for mt in existing_recipe.meal_types:
            await db.refresh(mt, attribute_names=["meal_type"])
        for dc in existing_recipe.dish_categories:
            await db.refresh(dc, attribute_names=["dish_category"])
        for rt in existing_recipe.tags:
            await db.refresh(rt, attribute_names=["tag"])
        return existing_recipe

    steps_dict = [step.dict() for step in recipe.steps]

    db_recipe = Recipe(
        title=recipe.title,
        description=recipe.description,
        steps=steps_dict,
        total_time=recipe.total_time,
        servings=recipe.servings,
        calories=recipe.calories,
        proteins=recipe.proteins,
        fats=recipe.fats,
        carbohydrates=recipe.carbohydrates,
        user_id=user_id,
        is_public=recipe.is_public,
        image_path=image_path,
    )
    db.add(db_recipe)
    await db.flush()

    for ingredient in recipe.ingredients:
        existing_ingredient = await db.execute(
            select(Ingredient).filter(Ingredient.id == ingredient.ingredient_id)
        )
        ingredient_obj = existing_ingredient.scalars().first()
        if not ingredient_obj:
            raise HTTPException(status_code=400, detail=f"Ингредиент с ID {ingredient.ingredient_id} не найден")
        db_ingredient = RecipeIngredient(
            recipe_id=db_recipe.id,
            ingredient_id=ingredient.ingredient_id,
            amount=ingredient.amount
        )
        db.add(db_ingredient)

    for meal_type_id in recipe.meal_type_ids:
        existing_meal_type = await db.execute(
            select(MealType).filter(MealType.id == meal_type_id)
        )
        meal_type_obj = existing_meal_type.scalars().first()
        if not meal_type_obj:
            raise HTTPException(status_code=400, detail=f"Тип блюда с ID {meal_type_id} не найден")
        db_meal_type = RecipeMealType(
            recipe_id=db_recipe.id,
            meal_type_id=meal_type_id
        )
        db.add(db_meal_type)

    for dish_category_id in recipe.dish_category_ids:
        existing_dish_category = await db.execute(
            select(DishCategory).filter(DishCategory.id == dish_category_id)
        )
        dish_category_obj = existing_dish_category.scalars().first()
        if not dish_category_obj:
            raise HTTPException(status_code=400, detail=f"Категория блюда с ID {dish_category_id} не найдена")
        db_dish_category = RecipeDishCategory(
            recipe_id=db_recipe.id,
            dish_category_id=dish_category_id
        )
        db.add(db_dish_category)

    for tag_id in recipe.tag_ids:
        existing_tag = await db.execute(
            select(Tag).filter(Tag.id == tag_id)
        )
        tag_obj = existing_tag.scalars().first()
        if not tag_obj:
            raise HTTPException(status_code=400, detail=f"Тег с ID {tag_id} не найден")
        db_tag = RecipeTag(
            recipe_id=db_recipe.id,
            tag_id=tag_id
        )
        db.add(db_tag)

    await db.commit()
    await db.refresh(db_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags"])
    for ri in db_recipe.ingredients:
        await db.refresh(ri, attribute_names=["ingredient"])
    for mt in db_recipe.meal_types:
        await db.refresh(mt, attribute_names=["meal_type"])
    for dc in db_recipe.dish_categories:
        await db.refresh(dc, attribute_names=["dish_category"])
    for rt in db_recipe.tags:
        await db.refresh(rt, attribute_names=["tag"])
    logger.info(f"Создан новый рецепт: {db_recipe.title} для user_id={user_id}")
    return db_recipe

async def update_recipe(db: AsyncSession, recipe_id: int, recipe_update: RecipeUpdate, user_id: int, image_path: str = None):
    result = await db.execute(
        select(Recipe)
        .options(
            joinedload(Recipe.ingredients),
            joinedload(Recipe.meal_types),
            joinedload(Recipe.dish_categories),
            joinedload(Recipe.tags)
        )
        .filter(Recipe.id == recipe_id, Recipe.user_id == user_id)
    )
    db_recipe = result.scalars().first()

    if not db_recipe:
        raise HTTPException(status_code=404, detail="Рецепт не найден или не принадлежит вам")

    update_data = recipe_update.dict(exclude_unset=True, exclude={"ingredients", "meal_type_ids", "dish_category_ids", "tag_ids"})
    for key, value in update_data.items():
        if key == "steps" and value is not None:
            setattr(db_recipe, key, value)
        else:
            setattr(db_recipe, key, value)

    if image_path is not None:
        db_recipe.image_path = image_path

    if recipe_update.ingredients is not None:
        await db.execute(
            RecipeIngredient.__table__.delete().where(RecipeIngredient.recipe_id == recipe_id)
        )
        for ingredient in recipe_update.ingredients:
            existing_ingredient = await db.execute(
                select(Ingredient).filter(Ingredient.id == ingredient.ingredient_id)
            )
            ingredient_obj = existing_ingredient.scalars().first()
            if not ingredient_obj:
                raise HTTPException(status_code=400, detail=f"Ингредиент с ID {ingredient.ingredient_id} не найден")
            db_ingredient = RecipeIngredient(
                recipe_id=db_recipe.id,
                ingredient_id=ingredient.ingredient_id,
                amount=ingredient.amount
            )
            db.add(db_ingredient)

    if recipe_update.meal_type_ids is not None:
        await db.execute(
            RecipeMealType.__table__.delete().where(RecipeMealType.recipe_id == recipe_id)
        )
        for meal_type_id in recipe_update.meal_type_ids:
            existing_meal_type = await db.execute(
                select(MealType).filter(MealType.id == meal_type_id)
            )
            meal_type_obj = existing_meal_type.scalars().first()
            if not meal_type_obj:
                raise HTTPException(status_code=400, detail=f"Тип блюда с ID {meal_type_id} не найден")
            db_meal_type = RecipeMealType(
                recipe_id=db_recipe.id,
                meal_type_id=meal_type_id
            )
            db.add(db_meal_type)

    if recipe_update.dish_category_ids is not None:
        await db.execute(
            RecipeDishCategory.__table__.delete().where(RecipeDishCategory.recipe_id == recipe_id)
        )
        for dish_category_id in recipe_update.dish_category_ids:
            existing_dish_category = await db.execute(
                select(DishCategory).filter(DishCategory.id == dish_category_id)
            )
            dish_category_obj = existing_dish_category.scalars().first()
            if not dish_category_obj:
                raise HTTPException(status_code=400, detail=f"Категория блюда с ID {dish_category_id} не найдена")
            db_dish_category = RecipeDishCategory(
                recipe_id=db_recipe.id,
                dish_category_id=dish_category_id
            )
            db.add(db_dish_category)

    if recipe_update.tag_ids is not None:
        await db.execute(
            RecipeTag.__table__.delete().where(RecipeTag.recipe_id == recipe_id)
        )
        for tag_id in recipe_update.tag_ids:
            existing_tag = await db.execute(
                select(Tag).filter(Tag.id == tag_id)
            )
            tag_obj = existing_tag.scalars().first()
            if not tag_obj:
                raise HTTPException(status_code=400, detail=f"Тег с ID {tag_id} не найден")
            db_tag = RecipeTag(
                recipe_id=db_recipe.id,
                tag_id=tag_id
            )
            db.add(db_tag)

    await db.commit()
    await db.refresh(db_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags"])
    for ri in db_recipe.ingredients:
        await db.refresh(ri, attribute_names=["ingredient"])
    for mt in db_recipe.meal_types:
        await db.refresh(mt, attribute_names=["meal_type"])
    for dc in db_recipe.dish_categories:
        await db.refresh(dc, attribute_names=["dish_category"])
    for rt in db_recipe.tags:
        await db.refresh(rt, attribute_names=["tag"])
    logger.info(f"Обновлен рецепт: {db_recipe.title} для user_id={user_id}")
    return db_recipe

async def get_user_recipes(db: AsyncSession, user_id: int, show_mealflow: bool = False, search: str = "", skip: int = 0, limit: int = 10):
    query = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.meal_types).selectinload(RecipeMealType.meal_type),
            selectinload(Recipe.dish_categories).selectinload(RecipeDishCategory.dish_category),
            selectinload(Recipe.tags).selectinload(RecipeTag.tag)
        )
        .filter(Recipe.user_id == user_id)
    )
    if show_mealflow:
        query = (
            select(Recipe)
            .options(
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
                selectinload(Recipe.meal_types).selectinload(RecipeMealType.meal_type),
                selectinload(Recipe.dish_categories).selectinload(RecipeDishCategory.dish_category),
                selectinload(Recipe.tags).selectinload(RecipeTag.tag)
            )
            .filter((Recipe.user_id == user_id) | (Recipe.is_public == True))
        )
    if search:
        query = query.filter(Recipe.title.ilike(f"%{search}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    recipes = result.unique().scalars().all()
    logger.info(f"Recipes fetched: {[{k: v for k, v in r.__dict__.items() if k != '_sa_instance_state'} for r in recipes]}")
    return recipes

async def get_available_ingredients(db: AsyncSession):
    result = await db.execute(select(Ingredient).filter(Ingredient.is_public == True))
    return result.scalars().all()

async def create_ingredient(db: AsyncSession, ingredient_name: str, unit: str, is_public: bool):
    db_ingredient = Ingredient(ingredient_name=ingredient_name, unit=unit, is_public=is_public)
    db.add(db_ingredient)
    await db.commit()
    await db.refresh(db_ingredient)
    return db_ingredient

async def create_meal_type(db: AsyncSession, name: str, description: str = None, is_active: bool = True):
    db_meal_type = MealType(name=name, description=description, is_active=is_active)
    db.add(db_meal_type)
    await db.commit()
    await db.refresh(db_meal_type)
    return db_meal_type

async def get_available_meal_types(db: AsyncSession):
    result = await db.execute(select(MealType).filter(MealType.is_active == True))
    return result.scalars().all()

async def create_dish_category(db: AsyncSession, name: str, description: str = None, is_active: bool = True):
    db_dish_category = DishCategory(name=name, description=description, is_active=is_active)
    db.add(db_dish_category)
    await db.commit()
    await db.refresh(db_dish_category)
    return db_dish_category

async def get_available_dish_categories(db: AsyncSession):
    result = await db.execute(select(DishCategory).filter(DishCategory.is_active == True))
    return result.scalars().all()

async def create_tag(db: AsyncSession, name: str, is_active: bool = True):
    db_tag = Tag(name=name, is_active=is_active)
    db.add(db_tag)
    await db.commit()
    await db.refresh(db_tag)
    return db_tag

async def get_available_tags(db: AsyncSession):
    result = await db.execute(select(Tag).filter(Tag.is_active == True))
    return result.scalars().all()

async def delete_recipe(db: AsyncSession, recipe_id: int, user_id: int):
    try:
        result = await db.execute(
            select(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user_id)
        )
        db_recipe = result.scalars().first()

        if not db_recipe:
            raise HTTPException(status_code=404, detail="Рецепт не найден или не принадлежит вам")

        await db.delete(db_recipe)
        await db.commit()
        logger.info(f"Recipe with id={recipe_id} deleted for user_id={user_id}")
        return db_recipe
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in delete_recipe: {str(e)}", exc_info=True)
        raise

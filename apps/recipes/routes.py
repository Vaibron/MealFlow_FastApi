from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from apps.recipes.models import Recipe as RecipeModel, FavoriteRecipe, MealType, RecipeIngredient, RecipeMealType, DishCategory, RecipeDishCategory, Tag, RecipeTag
from apps.recipes.schemas import RecipeCreate, Recipe, IngredientBase, Ingredient, RecipeUpdate, MealType as MealTypeSchema, MealTypeBase, DishCategory as DishCategorySchema, DishCategoryBase, Tag as TagSchema, TagBase
from apps.recipes.crud import create_recipe, get_user_recipes, get_available_ingredients, create_ingredient, update_recipe, delete_recipe, create_meal_type, get_available_meal_types, create_dish_category, get_available_dish_categories, create_tag, get_available_tags
from core.dependencies import get_db
from apps.auth.routes import get_current_user
from apps.auth.models import User
from typing import List
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from datetime import timedelta, datetime
import os
import logging
from json import loads, dumps

router = APIRouter(prefix="/recipes", tags=["recipes"])
logger = logging.getLogger(__name__)

load_dotenv()
minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT").replace("http://", ""),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

recipes_bucket_name = os.getenv("MINIO_RECIPES_BUCKET_NAME", "recipes")
if not minio_client.bucket_exists(recipes_bucket_name):
    minio_client.make_bucket(recipes_bucket_name)

async def ensure_admin(user: User = Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Только администраторы могут выполнять это действие")
    return user

@router.post("/", response_model=Recipe)
async def create_user_recipe(
    title: str = Form(...),
    description: str = Form(None),
    steps: str = Form(...),
    total_time: int = Form(...),
    servings: int = Form(...),
    calories: float = Form(None),
    proteins: float = Form(None),
    fats: float = Form(None),
    carbohydrates: float = Form(None),
    is_public: bool = Form(False),
    ingredients: str = Form(...),
    meal_type_ids: str = Form("[]"),
    dish_category_ids: str = Form("[]"),
    tag_ids: str = Form("[]"),
    image: UploadFile = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    recipe_data = RecipeCreate(
        title=title,
        description=description,
        steps=loads(steps),
        total_time=total_time,
        servings=servings,
        calories=calories,
        proteins=proteins,
        fats=fats,
        carbohydrates=carbohydrates,
        is_public=is_public,
        ingredients=loads(ingredients),
        meal_type_ids=loads(meal_type_ids),
        dish_category_ids=loads(dish_category_ids),
        tag_ids=loads(tag_ids)
    )
    if not user.is_superuser and recipe_data.is_public:
        raise HTTPException(status_code=403, detail="Только администраторы могут делать рецепты общедоступными")

    image_path = None
    db_recipe = await create_recipe(db, recipe_data, user.id, image_path)
    if image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"{user.id}_{db_recipe.id}_{timestamp}.jpg"
        image_path = image_filename
        try:
            minio_client.put_object(
                recipes_bucket_name,
                image_path,
                image.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type="image/jpeg"
            )
            db_recipe.image_path = image_path
            await db.commit()
        except S3Error as e:
            logger.error(f"Ошибка загрузки в MinIO: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки изображения: {str(e)}")

    await db.refresh(db_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags"])
    for ri in db_recipe.ingredients:
        await db.refresh(ri, attribute_names=["ingredient"])
    for mt in db_recipe.meal_types:
        await db.refresh(mt, attribute_names=["meal_type"])
    for dc in db_recipe.dish_categories:
        await db.refresh(dc, attribute_names=["dish_category"])
    for rt in db_recipe.tags:
        await db.refresh(rt, attribute_names=["tag"])

    return Recipe.from_orm(db_recipe)

@router.put("/{recipe_id}", response_model=Recipe)
async def update_user_recipe(
    recipe_id: int,
    title: str = Form(None),
    description: str = Form(None),
    steps: str = Form(None),
    total_time: int = Form(None),
    servings: int = Form(None),
    calories: float = Form(None),
    proteins: float = Form(None),
    fats: float = Form(None),
    carbohydrates: float = Form(None),
    is_public: bool = Form(None),
    ingredients: str = Form(None),
    meal_type_ids: str = Form(None),
    dish_category_ids: str = Form(None),
    tag_ids: str = Form(None),
    image: UploadFile = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    recipe_update = RecipeUpdate(
        title=title,
        description=description,
        steps=loads(steps) if steps else None,
        total_time=total_time,
        servings=servings,
        calories=calories,
        proteins=proteins,
        fats=fats,
        carbohydrates=carbohydrates,
        is_public=is_public,
        ingredients=loads(ingredients) if ingredients else None,
        meal_type_ids=loads(meal_type_ids) if meal_type_ids else None,
        dish_category_ids=loads(dish_category_ids) if dish_category_ids else None,
        tag_ids=loads(tag_ids) if tag_ids else None
    )
    if not user.is_superuser and recipe_update.is_public:
        raise HTTPException(status_code=403, detail="Только администраторы могут делать рецепты общедоступными")

    image_path = None
    if image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"{user.id}_{recipe_id}_{timestamp}.jpg"
        image_path = image_filename
        try:
            existing_recipe = await db.execute(
                select(RecipeModel).filter(RecipeModel.id == recipe_id, RecipeModel.user_id == user.id)
            )
            old_recipe = existing_recipe.scalars().first()
            if old_recipe and old_recipe.image_path:
                minio_client.remove_object(recipes_bucket_name, old_recipe.image_path)
                logger.info(f"Removed old image {old_recipe.image_path} from MinIO")

            minio_client.put_object(
                recipes_bucket_name,
                image_path,
                image.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type="image/jpeg"
            )
        except S3Error as e:
            logger.error(f"Ошибка загрузки в MinIO: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки изображения: {str(e)}")

    db_recipe = await update_recipe(db, recipe_id, recipe_update, user.id, image_path)
    if image:
        db_recipe.image_version += 1
        await db.commit()
    return Recipe.from_orm(db_recipe)

@router.delete("/{recipe_id}", status_code=204)
async def delete_user_recipe(
        recipe_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    try:
        deleted_recipe = await delete_recipe(db, recipe_id, user.id)
        if deleted_recipe.image_path:
            try:
                minio_client.remove_object(recipes_bucket_name, deleted_recipe.image_path)
                logger.info(f"Removed image {deleted_recipe.image_path} from MinIO")
            except S3Error as e:
                logger.error(f"Ошибка удаления изображения из MinIO: {str(e)}")
        logger.info(f"Deleted recipe with id={recipe_id} for user_id={user.id}")
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting recipe {recipe_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/", response_model=List[Recipe])
async def read_user_recipes(
    show_mealflow: bool = False,
    search: str = "",
    skip: int = 0,
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(
        f"Fetching recipes for user_id={user.id}, show_mealflow={show_mealflow}, search={search}, skip={skip}, limit={limit}")
    recipes = await get_user_recipes(db, user.id, show_mealflow, search, skip, limit)
    return [Recipe.from_orm(r) for r in recipes]

@router.get("/ingredients/", response_model=List[Ingredient])
async def read_available_ingredients(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    ingredients = await get_available_ingredients(db)
    logger.info(f"Returning ingredients: {[i.__dict__ for i in ingredients]}")
    return ingredients

@router.post("/ingredients/", response_model=Ingredient)
async def create_new_ingredient(
        ingredient: IngredientBase,
        user: User = Depends(ensure_admin),
        db: AsyncSession = Depends(get_db)
):
    db_ingredient = await create_ingredient(db, ingredient.ingredient_name, ingredient.unit, ingredient.is_public)
    logger.info(f"Created ingredient: {db_ingredient.__dict__}")
    return db_ingredient

@router.get("/meal-types/", response_model=List[MealTypeSchema])
async def read_available_meal_types(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    meal_types = await get_available_meal_types(db)
    logger.info(f"Returning meal types: {[mt.__dict__ for mt in meal_types]}")
    return meal_types

@router.post("/meal-types/", response_model=MealTypeSchema)
async def create_new_meal_type(
        meal_type: MealTypeBase,
        user: User = Depends(ensure_admin),
        db: AsyncSession = Depends(get_db)
):
    db_meal_type = await create_meal_type(db, meal_type.name, meal_type.description, meal_type.is_active)
    logger.info(f"Created meal type: {db_meal_type.__dict__}")
    return db_meal_type

@router.get("/dish-categories/", response_model=List[DishCategorySchema])
async def read_available_dish_categories(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    dish_categories = await get_available_dish_categories(db)
    logger.info(f"Returning dish categories: {[dc.__dict__ for dc in dish_categories]}")
    return dish_categories

@router.post("/dish-categories/", response_model=DishCategorySchema)
async def create_new_dish_category(
        dish_category: DishCategoryBase,
        user: User = Depends(ensure_admin),
        db: AsyncSession = Depends(get_db)
):
    db_dish_category = await create_dish_category(db, dish_category.name, dish_category.description, dish_category.is_active)
    logger.info(f"Created dish category: {db_dish_category.__dict__}")
    return db_dish_category

@router.get("/tags/", response_model=List[TagSchema])
async def read_available_tags(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    tags = await get_available_tags(db)
    logger.info(f"Returning tags: {[t.__dict__ for t in tags]}")
    return tags

@router.post("/tags/", response_model=TagSchema)
async def create_new_tag(
        tag: TagBase,
        user: User = Depends(ensure_admin),
        db: AsyncSession = Depends(get_db)
):
    db_tag = await create_tag(db, tag.name, tag.is_active)
    logger.info(f"Created tag: {db_tag.__dict__}")
    return db_tag

@router.get("/image/{recipe_id}")
async def get_recipe_image(recipe_id: int, db: AsyncSession = Depends(get_db)):
    query = select(RecipeModel).where(RecipeModel.id == recipe_id)
    result = await db.execute(query)
    recipe = result.scalars().first()

    if not recipe or not recipe.image_path:
        raise HTTPException(status_code=404, detail="Изображение не найдено")

    try:
        image_url = minio_client.presigned_get_object(
            recipes_bucket_name,
            recipe.image_path,
            expires=timedelta(seconds=3600)
        )
        return {"image_url": image_url}
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения изображения из MinIO: {str(e)}")

@router.post("/favorites/{recipe_id}", status_code=200)
async def add_favorite_recipe(
        recipe_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(RecipeModel).filter(RecipeModel.id == recipe_id)
    )
    recipe = result.scalars().first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Рецепт не найден")

    existing_favorite = await db.execute(
        select(FavoriteRecipe).filter(FavoriteRecipe.user_id == user.id, FavoriteRecipe.recipe_id == recipe_id)
    )
    if existing_favorite.scalars().first():
        raise HTTPException(status_code=400, detail="Рецепт уже в избранном")

    favorite = FavoriteRecipe(user_id=user.id, recipe_id=recipe_id)
    db.add(favorite)
    await db.commit()
    logger.info(f"Added recipe {recipe_id} to favorites for user {user.id}")
    return {"message": "Добавлено в избранное"}

@router.delete("/favorites/{recipe_id}", status_code=204)
async def remove_favorite_recipe(
        recipe_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FavoriteRecipe).filter(FavoriteRecipe.user_id == user.id, FavoriteRecipe.recipe_id == recipe_id)
    )
    favorite = result.scalars().first()
    if not favorite:
        raise HTTPException(status_code=404, detail="Рецепт не найден в избранном")
    await db.delete(favorite)
    await db.commit()
    logger.info(f"Removed recipe {recipe_id} from favorites for user {user.id}")
    return None

@router.get("/favorites", response_model=List[int])
async def get_favorite_recipes(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    logger.info(f"Fetching favorites for user_id={user.id}")
    result = await db.execute(
        select(FavoriteRecipe.recipe_id).filter(FavoriteRecipe.user_id == user.id)
    )
    favorites = result.scalars().all()
    logger.info(f"Found {len(favorites)} favorites")
    return favorites

@router.get("/{recipe_id}", response_model=Recipe)
async def read_recipe_by_id(
    recipe_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(RecipeModel)
        .options(
            joinedload(RecipeModel.ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(RecipeModel.meal_types).joinedload(RecipeMealType.meal_type),
            joinedload(RecipeModel.dish_categories).joinedload(RecipeDishCategory.dish_category),
            joinedload(RecipeModel.tags).joinedload(RecipeTag.tag)
        )
        .filter(
            (RecipeModel.id == recipe_id) &
            ((RecipeModel.user_id == user.id) | (RecipeModel.is_public == True))
        )
    )
    recipe = result.scalars().first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Рецепт не найден или недоступен")
    return Recipe.from_orm(recipe)

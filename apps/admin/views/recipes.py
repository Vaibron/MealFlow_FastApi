from datetime import datetime
from sqladmin import ModelView
from apps.recipes.models import Recipe, RecipeIngredient, Ingredient, MealType, RecipeMealType, DishCategory, RecipeDishCategory, Tag, RecipeTag
from fastapi import Request, UploadFile, File, HTTPException
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
import wtforms
from wtforms.validators import DataRequired, NumberRange
import logging
from starlette.responses import RedirectResponse, JSONResponse
from starlette.status import HTTP_303_SEE_OTHER
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from io import BytesIO
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MinIO client setup
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

class IngredientForm(wtforms.Form):
    ingredient_id = wtforms.SelectField(
        "Ингредиент",
        coerce=int,
        validators=[DataRequired()],
        description="Выберите ингредиент из списка"
    )
    amount = wtforms.FloatField(
        "Количество",
        validators=[DataRequired(), NumberRange(min=0.1)],
        description="Укажите количество (например, 100 для 100 г)"
    )

class MealTypeForm(wtforms.Form):
    meal_type_id = wtforms.SelectField(
        "Тип блюда",
        coerce=int,
        validators=[DataRequired()],
        description="Выберите тип блюда из списка"
    )

class DishCategoryForm(wtforms.Form):
    dish_category_id = wtforms.SelectField(
        "Категория блюда",
        coerce=int,
        validators=[DataRequired()],
        description="Выберите категорию блюда из списка"
    )

class TagForm(wtforms.Form):
    tag_id = wtforms.SelectField(
        "Тег",
        coerce=int,
        validators=[DataRequired()],
        description="Выберите тег из списка"
    )

class RecipeForm(wtforms.Form):
    title = wtforms.StringField("Название", validators=[DataRequired()], description="Название рецепта (до 100 символов)")
    description = wtforms.TextAreaField("Описание", description="Описание рецепта (опционально)")
    total_time = wtforms.IntegerField("Общее время (мин)", validators=[DataRequired(), NumberRange(min=0)], description="Общее время приготовления в минутах")
    servings = wtforms.IntegerField("Количество порций", validators=[DataRequired(), NumberRange(min=1)], description="Количество порций")
    calories = wtforms.FloatField("Калории", validators=[NumberRange(min=0)], description="Калории на порцию (опционально)")
    proteins = wtforms.FloatField("Белки", validators=[NumberRange(min=0)], description="Белки на порцию (опционально)")
    fats = wtforms.FloatField("Жиры", validators=[NumberRange(min=0)], description="Жиры на порцию (опционально)")
    carbohydrates = wtforms.FloatField("Углеводы", validators=[NumberRange(min=0)], description="Углеводы на порцию (опционально)")
    is_public = wtforms.BooleanField("Общедоступный", default=False, description="Сделать рецепт видимым для всех")
    image = wtforms.FileField("Изображение", description="Загрузите изображение рецепта (опционально)")
    ingredients = wtforms.FieldList(
        wtforms.FormField(IngredientForm),
        min_entries=1,
        max_entries=None,
        description="Добавьте ингредиенты для рецепта"
    )
    meal_types = wtforms.FieldList(
        wtforms.FormField(MealTypeForm),
        min_entries=1,
        max_entries=None,
        description="Выберите типы блюд"
    )
    dish_categories = wtforms.FieldList(
        wtforms.FormField(DishCategoryForm),
        min_entries=1,
        max_entries=None,
        description="Выберите категории блюд"
    )
    tags = wtforms.FieldList(
        wtforms.FormField(TagForm),
        min_entries=1,
        max_entries=None,
        description="Выберите теги"
    )

    def __init__(self, *args, ingredient_choices=None, meal_type_choices=None, dish_category_choices=None, tag_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ingredient_choices is not None:
            for ingredient_field in self.ingredients:
                ingredient_field.ingredient_id.choices = ingredient_choices
        if meal_type_choices is not None:
            for meal_type_field in self.meal_types:
                meal_type_field.meal_type_id.choices = meal_type_choices
        if dish_category_choices is not None:
            for dish_category_field in self.dish_categories:
                dish_category_field.dish_category_id.choices = dish_category_choices
        if tag_choices is not None:
            for tag_field in self.tags:
                tag_field.tag_id.choices = tag_choices

class RecipeAdmin(ModelView, model=Recipe):
    column_list = [Recipe.id, Recipe.title, Recipe.user_id, Recipe.is_public, Recipe.total_time, Recipe.servings, Recipe.image_path]
    column_searchable_list = [Recipe.title]
    page_size = 20
    name = "Рецепт"
    name_plural = "Рецепты"
    icon = "fa fa-utensils"
    can_edit = True
    can_create = True

    create_template = "recipe_create.html"
    edit_template = "recipe_edit.html"
    form_excluded_columns = ["image_path"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"RecipeAdmin initialized with create_template: {self.create_template}, edit_template: {self.edit_template}")

    async def scaffold_form(self) -> type[wtforms.Form]:
        logger.info("Scaffolding form for RecipeAdmin")
        async with self.session_maker() as session:
            result = await session.execute(select(Ingredient))
            ingredients = result.scalars().all()
            ingredient_choices = [(ing.id, f"{ing.ingredient_name} ({ing.unit})") for ing in ingredients]

            result = await session.execute(select(MealType))
            meal_types = result.scalars().all()
            meal_type_choices = [(mt.id, mt.name) for mt in meal_types]

            result = await session.execute(select(DishCategory))
            dish_categories = result.scalars().all()
            dish_category_choices = [(dc.id, dc.name) for dc in dish_categories]

            result = await session.execute(select(Tag))
            tags = result.scalars().all()
            tag_choices = [(t.id, t.name) for t in tags]

            logger.info(f"Loaded ingredient choices: {ingredient_choices}")
            logger.info(f"Loaded meal type choices: {meal_type_choices}")
            logger.info(f"Loaded dish category choices: {dish_category_choices}")
            logger.info(f"Loaded tag choices: {tag_choices}")

        class DynamicRecipeForm(RecipeForm):
            def __init__(self, *args, **kwargs):
                super().__init__(
                    *args,
                    ingredient_choices=ingredient_choices,
                    meal_type_choices=meal_type_choices,
                    dish_category_choices=dish_category_choices,
                    tag_choices=tag_choices,
                    **kwargs
                )

        return DynamicRecipeForm

    async def create(self, request: Request) -> "Response":
        logger.info(f"Rendering create page with template: {self.create_template}")
        form_class = await self.scaffold_form()
        form = form_class()

        if request.method == "POST":
            form_data = await request.form()
            logger.info(f"POST request detected with form data: {dict(form_data)}")
            model = await self.insert_model(request, form_data)
            logger.info(f"Model created: {model.id}")
            return RedirectResponse(url="/admin/recipe/list", status_code=HTTP_303_SEE_OTHER)

        return self.templates.TemplateResponse(
            self.create_template,
            {"request": request, "form": form}
        )

    async def insert_model(self, request: Request, data: dict) -> Recipe:
        logger.info(f"Inserting new recipe with form data: {dict(data)}")
        user_id = request.session.get("user_id")
        if not user_id:
            raise ValueError("User ID not found in session. Ensure you are logged in as a superuser.")

        form_data = await request.form()
        logger.info(f"Raw form data in insert_model: {dict(form_data)}")

        async with self.session_maker() as session:
            db_recipe = Recipe(user_id=user_id)
            await self.on_model_change(form_data, db_recipe, is_created=True, request=request)

            session.add(db_recipe)
            await session.flush()

            image_file = form_data.get("image")
            if image_file and hasattr(image_file, "filename") and image_file.filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"{user_id}_{db_recipe.id}_{timestamp}.jpg"
                try:
                    image_content = await image_file.read()
                    image_stream = BytesIO(image_content)
                    minio_client.put_object(
                        recipes_bucket_name,
                        image_filename,
                        image_stream,
                        length=len(image_content),
                        content_type="image/jpeg"
                    )
                    db_recipe.image_path = image_filename
                    logger.info(f"Uploaded new image to MinIO at {image_filename}")
                except S3Error as e:
                    logger.error(f"Failed to upload image to MinIO: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Ошибка загрузки в MinIO: {str(e)}")

            ingredients_data = []
            i = 0
            while f"ingredients-{i}-ingredient_id" in form_data:
                ingredient_id = form_data[f"ingredients-{i}-ingredient_id"]
                amount = form_data[f"ingredients-{i}-amount"]
                if ingredient_id and amount:
                    ingredients_data.append({
                        "ingredient_id": int(ingredient_id),
                        "amount": float(amount)
                    })
                i += 1
            for ingredient_data in ingredients_data:
                db_ingredient = RecipeIngredient(
                    recipe_id=db_recipe.id,
                    ingredient_id=ingredient_data["ingredient_id"],
                    amount=ingredient_data["amount"]
                )
                session.add(db_ingredient)

            meal_types_data = []
            i = 0
            while f"meal_types-{i}-meal_type_id" in form_data:
                meal_type_id = form_data[f"meal_types-{i}-meal_type_id"]
                if meal_type_id:
                    meal_types_data.append({"meal_type_id": int(meal_type_id)})
                i += 1
            for meal_type_data in meal_types_data:
                db_meal_type = RecipeMealType(
                    recipe_id=db_recipe.id,
                    meal_type_id=meal_type_data["meal_type_id"]
                )
                session.add(db_meal_type)

            dish_categories_data = []
            i = 0
            while f"dish_categories-{i}-dish_category_id" in form_data:
                dish_category_id = form_data[f"dish_categories-{i}-dish_category_id"]
                if dish_category_id:
                    dish_categories_data.append({"dish_category_id": int(dish_category_id)})
                i += 1
            for dish_category_data in dish_categories_data:
                db_dish_category = RecipeDishCategory(
                    recipe_id=db_recipe.id,
                    dish_category_id=dish_category_data["dish_category_id"]
                )
                session.add(db_dish_category)

            tags_data = []
            i = 0
            while f"tags-{i}-tag_id" in form_data:
                tag_id = form_data[f"tags-{i}-tag_id"]
                if tag_id:
                    tags_data.append({"tag_id": int(tag_id)})
                i += 1
            for tag_data in tags_data:
                db_tag = RecipeTag(
                    recipe_id=db_recipe.id,
                    tag_id=tag_data["tag_id"]
                )
                session.add(db_tag)

            await session.commit()
            await session.refresh(db_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags", "steps"])
            return db_recipe

    async def edit(self, request: Request) -> "Response":
        logger.info(f"Rendering edit page with template: {self.edit_template}")
        pk = int(request.path_params.get("pk"))
        form_data = await request.form()

        if request.method == "POST" and form_data:
            logger.info(f"POST request detected with form data: {dict(form_data)}")
            model = await self.update_model(request, pk, form_data)
            logger.info(f"Model updated: {model.id}")
            return RedirectResponse(url="/admin/recipe/list", status_code=HTTP_303_SEE_OTHER)

        async with self.session_maker() as session:
            result = await session.execute(
                select(Recipe)
                .filter(Recipe.id == pk)
                .options(
                    joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient),
                    joinedload(Recipe.meal_types).joinedload(RecipeMealType.meal_type),
                    joinedload(Recipe.dish_categories).joinedload(RecipeDishCategory.dish_category),
                    joinedload(Recipe.tags).joinedload(RecipeTag.tag)
                )
            )
            obj = result.scalars().first()
            if not obj:
                return RedirectResponse(url="/admin/recipe/list", status_code=HTTP_303_SEE_OTHER)

            form_class = await self.scaffold_form()
            form = form_class(obj=obj)
            form.title.data = obj.title
            form.description.data = obj.description
            form.total_time.data = obj.total_time
            form.servings.data = obj.servings
            form.calories.data = obj.calories
            form.proteins.data = obj.proteins
            form.fats.data = obj.fats
            form.carbohydrates.data = obj.carbohydrates
            form.is_public.data = obj.is_public

            for i, ri in enumerate(obj.ingredients):
                if i >= len(form.ingredients):
                    form.ingredients.append_entry()
                form.ingredients[i].ingredient_id.data = ri.ingredient_id
                form.ingredients[i].amount.data = ri.amount

            for i, mt in enumerate(obj.meal_types):
                if i >= len(form.meal_types):
                    form.meal_types.append_entry()
                form.meal_types[i].meal_type_id.data = mt.meal_type_id

            for i, dc in enumerate(obj.dish_categories):
                if i >= len(form.dish_categories):
                    form.dish_categories.append_entry()
                form.dish_categories[i].dish_category_id.data = dc.dish_category_id

            for i, t in enumerate(obj.tags):
                if i >= len(form.tags):
                    form.tags.append_entry()
                form.tags[i].tag_id.data = t.tag_id

            return self.templates.TemplateResponse(
                self.edit_template,
                {"request": request, "form": form, "obj": obj, "steps": obj.steps}
            )

    async def on_model_change(self, data: dict, model: Recipe, is_created: bool, request: Request) -> None:
        logger.info(f"on_model_change called with data: {dict(data)}, is_created: {is_created}")
        form_data = await request.form()
        logger.info(f"Raw form data in on_model_change: {dict(form_data)}")

        model.title = form_data["title"]
        model.description = form_data.get("description", "")
        model.total_time = int(form_data["total_time"])
        model.servings = int(form_data["servings"])
        model.calories = float(form_data["calories"]) if form_data.get("calories") else None
        model.proteins = float(form_data["proteins"]) if form_data.get("proteins") else None
        model.fats = float(form_data["fats"]) if form_data.get("fats") else None
        model.carbohydrates = float(form_data["carbohydrates"]) if form_data.get("carbohydrates") else None
        model.is_public = "is_public" in form_data and form_data["is_public"] in ("y", "on")
        logger.info(f"Setting is_public to: {model.is_public}")

        steps_data = []
        i = 0
        while f"steps-{i}-description" in form_data:
            description = form_data.get(f"steps-{i}-description")
            step_number = form_data.get(f"steps-{i}-step_number")
            duration = form_data.get(f"steps-{i}-duration")
            if description and step_number:
                steps_data.append({
                    "step_number": int(step_number),
                    "description": description,
                    "duration": float(duration) if duration else None
                })
            else:
                logger.warning(f"Step {i} skipped: missing description or step_number")
            i += 1
        logger.info(f"Collected steps in on_model_change: {steps_data}")
        if steps_data:
            model.steps = steps_data
        elif is_created and not model.steps:
            model.steps = [{"step_number": 1, "description": "Default step", "duration": None}]

    async def update_model(self, request: Request, pk: int, data: dict) -> Recipe:
        form_data = await request.form()
        logger.info(f"Raw form data: {dict(form_data)}")
        user_id = request.session.get("user_id")
        if not user_id:
            raise ValueError("User ID not found in session. Ensure you are logged in as a superuser.")

        async with self.session_maker() as session:
            result = await session.execute(
                select(Recipe).filter(Recipe.id == int(pk), Recipe.user_id == user_id)
            )
            db_recipe = result.scalars().first()
            if not db_recipe:
                raise ValueError("Recipe not found or you don't have permission to edit it")

            await self.on_model_change(data, db_recipe, is_created=False, request=request)

            image_file = form_data.get("image")
            if image_file and hasattr(image_file, "filename") and image_file.filename:
                if db_recipe.image_path:
                    try:
                        minio_client.remove_object(recipes_bucket_name, db_recipe.image_path)
                        logger.info(f"Removed old image {db_recipe.image_path} from MinIO")
                    except S3Error as e:
                        logger.error(f"Ошибка удаления старого изображения: {str(e)}")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"{user_id}_{pk}_{timestamp}.jpg"
                try:
                    image_content = await image_file.read()
                    image_stream = BytesIO(image_content)
                    minio_client.put_object(
                        recipes_bucket_name,
                        image_filename,
                        image_stream,
                        length=len(image_content),
                        content_type="image/jpeg"
                    )
                    db_recipe.image_path = image_filename
                    logger.info(f"Uploaded new image to MinIO at {image_filename}")
                except S3Error as e:
                    logger.error(f"Failed to upload image to MinIO: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Ошибка загрузки в MinIO: {str(e)}")

            await session.execute(RecipeIngredient.__table__.delete().where(RecipeIngredient.recipe_id == int(pk)))
            ingredients_data = []
            i = 0
            while f"ingredients-{i}-ingredient_id" in form_data:
                ingredient_id = form_data[f"ingredients-{i}-ingredient_id"]
                amount = form_data[f"ingredients-{i}-amount"]
                if ingredient_id and amount:
                    ingredients_data.append({
                        "ingredient_id": int(ingredient_id),
                        "amount": float(amount)
                    })
                i += 1
            for ingredient_data in ingredients_data:
                db_ingredient = RecipeIngredient(
                    recipe_id=db_recipe.id,
                    ingredient_id=ingredient_data["ingredient_id"],
                    amount=ingredient_data["amount"]
                )
                session.add(db_ingredient)

            await session.execute(RecipeMealType.__table__.delete().where(RecipeMealType.recipe_id == int(pk)))
            meal_types_data = []
            i = 0
            while f"meal_types-{i}-meal_type_id" in form_data:
                meal_type_id = form_data[f"meal_types-{i}-meal_type_id"]
                if meal_type_id:
                    meal_types_data.append({"meal_type_id": int(meal_type_id)})
                i += 1
            for meal_type_data in meal_types_data:
                db_meal_type = RecipeMealType(
                    recipe_id=db_recipe.id,
                    meal_type_id=meal_type_data["meal_type_id"]
                )
                session.add(db_meal_type)

            await session.execute(RecipeDishCategory.__table__.delete().where(RecipeDishCategory.recipe_id == int(pk)))
            dish_categories_data = []
            i = 0
            while f"dish_categories-{i}-dish_category_id" in form_data:
                dish_category_id = form_data[f"dish_categories-{i}-dish_category_id"]
                if dish_category_id:
                    dish_categories_data.append({"dish_category_id": int(dish_category_id)})
                i += 1
            for dish_category_data in dish_categories_data:
                db_dish_category = RecipeDishCategory(
                    recipe_id=db_recipe.id,
                    dish_category_id=dish_category_data["dish_category_id"]
                )
                session.add(db_dish_category)

            await session.execute(RecipeTag.__table__.delete().where(RecipeTag.recipe_id == int(pk)))
            tags_data = []
            i = 0
            while f"tags-{i}-tag_id" in form_data:
                tag_id = form_data[f"tags-{i}-tag_id"]
                if tag_id:
                    tags_data.append({"tag_id": int(tag_id)})
                i += 1
            for tag_data in tags_data:
                db_tag = RecipeTag(
                    recipe_id=db_recipe.id,
                    tag_id=tag_data["tag_id"]
                )
                session.add(db_tag)

            await session.commit()
            await session.refresh(db_recipe, attribute_names=["ingredients", "meal_types", "dish_categories", "tags", "steps"])
            return db_recipe

    async def on_model_delete(self, obj: Recipe, request: Request) -> None:
        logger.info(f"Deleting recipe ID {obj.id}")
        if obj.image_path:
            try:
                minio_client.remove_object(recipes_bucket_name, obj.image_path)
                logger.info(f"Removed image {obj.image_path} from MinIO")
            except S3Error as e:
                logger.error(f"Ошибка удаления изображения из MinIO: {str(e)}")

async def upload_recipe_image(request: Request, recipe_id: int, image: UploadFile = File(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=403, detail="User ID not found in session.")

    async with request.app.state.db_session_maker() as session:
        try:
            result = await session.execute(
                select(Recipe).filter(Recipe.id == recipe_id)
            )
            recipe = result.scalars().first()
            if not recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")

            if image and image.filename:
                if recipe.image_path:
                    try:
                        minio_client.remove_object(recipes_bucket_name, recipe.image_path)
                        logger.info(f"Removed old image {recipe.image_path} from MinIO")
                    except S3Error as e:
                        logger.error(f"Ошибка удаления старого изображения: {str(e)}")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"{recipe.user_id}_{recipe_id}_{timestamp}.jpg"
                try:
                    image_content = await image.read()
                    image_stream = BytesIO(image_content)
                    minio_client.put_object(
                        recipes_bucket_name,
                        image_filename,
                        image_stream,
                        length=len(image_content),
                        content_type="image/jpeg"
                    )
                    recipe.image_path = image_filename
                    recipe.image_version += 1
                    logger.info(f"Uploaded new image to MinIO at {image_filename}, new version: {recipe.image_version}")
                except S3Error as e:
                    logger.error(f"Failed to upload image to MinIO: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Ошибка загрузки в MinIO: {str(e)}")

                await session.commit()
                await session.refresh(recipe)

            return JSONResponse(content={
                "message": "Image uploaded successfully",
                "image_path": recipe.image_path,
                "image_version": recipe.image_version
            })
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка в upload_recipe_image: {str(e)}")
            raise

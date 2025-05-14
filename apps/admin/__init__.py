# apps/admin/__init__.py
from fastapi import FastAPI
from sqladmin import Admin
from apps.admin.auth import AdminAuth
from apps.admin.views.users import UserAdmin
from apps.admin.views.news import NewsAdmin
from apps.admin.views.recipes import RecipeAdmin, upload_recipe_image
from apps.admin.views.ingredients import IngredientAdmin
from apps.admin.views.meal_types import MealTypeAdmin
from apps.admin.views.dish_categories import DishCategoryAdmin
from apps.admin.views.tags import TagAdmin
from core.database import engine
import logging
from sqlalchemy.ext.asyncio import async_sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_admin(app: FastAPI):
    logger.info("Initializing admin panel with templates_dir='templates/sqladmin'")

    # Create asynchronous session factory
    AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    app.state.db_session_maker = AsyncSessionLocal

    # Initialize SQLAdmin
    admin = Admin(
        app,
        engine,
        title="Админ-панель MealFlow",
        authentication_backend=AdminAuth(),
        templates_dir="templates/sqladmin"
    )

    # Register views
    admin.add_view(UserAdmin)
    admin.add_view(NewsAdmin)
    admin.add_view(RecipeAdmin)
    admin.add_view(IngredientAdmin)
    admin.add_view(MealTypeAdmin)
    admin.add_view(DishCategoryAdmin)
    admin.add_view(TagAdmin)

    # Register custom route for image upload
    app.post("/api/admin/recipe/upload-image/{recipe_id}")(upload_recipe_image)
    logger.info("Custom route /api/admin/recipe/upload-image/{recipe_id} registered")
    logger.info("Admin panel initialized")

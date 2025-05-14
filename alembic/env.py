from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from core.config import config as app_config
from core.database import Base
from apps.auth.models import User
from apps.news.models import News
from apps.recipes.models import Recipe, RecipeIngredient, Ingredient
from apps.meal_planner.models import MealPlan, ExcludedIngredient

# Целевые метаданные
target_metadata = Base.metadata

# Конфигурация Alembic
alembic_config = context.config

# Устанавливаем URL базы данных из core.config
alembic_config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

def run_migrations_offline():
    """Запуск миграций в оффлайн-режиме"""
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Запуск миграций с подключением"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """Запуск миграций в онлайн-режиме с асинхронным движком"""
    connectable = AsyncEngine(
        engine_from_config(
            alembic_config.get_section(alembic_config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool
        )
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())

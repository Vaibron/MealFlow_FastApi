from fastapi import FastAPI
from contextlib import asynccontextmanager
from apps.auth.routes import router as auth_router
from apps.parser.routes import router as parser_router
from apps.news.routes import router as news_router
from apps.recipes.routes import router as recipes_router
from apps.admin import init_admin
from core.database import Base, engine
from starlette.middleware.sessions import SessionMiddleware
from apps.meal_planner.routes import router as meal_planner_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="My Awesome Project", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")  # Используйте свой SECRET_KEY из .env

# Подключение маршрутов существующих приложений
app.include_router(auth_router)
app.include_router(parser_router)
app.include_router(news_router)
app.include_router(recipes_router)
app.include_router(meal_planner_router)

# Инициализация админки
init_admin(app)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the API"}

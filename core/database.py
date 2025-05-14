from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import config

# Определение декларативной базы
Base = declarative_base()

# Создание асинхронного движка
engine = create_async_engine(config.DATABASE_URL, echo=True)

# Настройка фабрики сессий
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
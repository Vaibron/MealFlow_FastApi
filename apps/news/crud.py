from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apps.news.models import News
from apps.auth.models import User

async def create_news(db: AsyncSession, title: str, content: str, image_path: str, user: User):
    db_news = News(
        title=title,
        content=content,
        image_path=image_path,
        user_id=user.id
    )
    db.add(db_news)
    await db.commit()
    await db.refresh(db_news)
    return db_news

async def get_news_by_id(db: AsyncSession, news_id: int):
    result = await db.execute(select(News).filter(News.id == news_id))
    return result.scalars().first()

async def get_all_news(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(News).offset(skip).limit(limit).order_by(News.created_at.desc()))
    return result.scalars().all()

async def update_news(db: AsyncSession, news: News, title: str | None, content: str | None, image_path: str | None):
    if title is not None:
        news.title = title
    if content is not None:
        news.content = content
    if image_path is not None:
        news.image_path = image_path
    await db.commit()
    await db.refresh(news)
    return news

async def delete_news(db: AsyncSession, news: News):
    await db.delete(news)
    await db.commit()
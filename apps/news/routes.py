from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from apps.news.schemas import NewsCreate, NewsOut, NewsUpdate
from apps.news.crud import create_news, get_news_by_id, get_all_news, update_news, delete_news
from apps.auth.routes import get_current_user
from apps.auth.models import User
from core.dependencies import get_db
from minio import Minio
from minio.error import S3Error
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# Загружаем переменные из .env
load_dotenv()

# Настройка клиента MinIO
minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT").replace("http://", ""),  # Убираем протокол из endpoint
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False  # Если используете HTTP, а не HTTPS
)

# Убедимся, что бакет существует
bucket_name = os.getenv("MINIO_NEWS_BUCKET_NAME")
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

router = APIRouter(prefix="/news", tags=["news"])

async def ensure_admin(user: User = Depends(get_current_user)):
    """Проверяет, является ли пользователь администратором."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Только администраторы могут выполнять это действие")
    return user

@router.post("/", response_model=NewsOut, status_code=status.HTTP_201_CREATED)
async def create_news_item(
        title: str = Form(...),
        content: str = Form(...),
        image: UploadFile = File(None),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(ensure_admin)
):
    """Создаёт новую новость с загрузкой изображения в MinIO."""
    image_path = None
    if image:
        image_filename = f"{current_user.id}_{image.filename}"
        image_path = f"{image_filename}"  # Путь в MinIO будет просто именем файла
        try:
            # Загружаем файл в MinIO
            minio_client.put_object(
                bucket_name,
                image_path,
                image.file,
                length=-1,  # -1 означает, что длина будет определена автоматически
                part_size=10*1024*1024,  # 10 MB части для загрузки
                content_type=image.content_type
            )
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки в MinIO: {str(e)}")

    news = await create_news(db, title, content, image_path, current_user)
    return news

@router.get("/{news_id}", response_model=NewsOut)
async def read_news(news_id: int, db: AsyncSession = Depends(get_db)):
    """Получает новость по её ID."""
    news = await get_news_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Новость не найдена")
    return news

@router.get("/", response_model=list[NewsOut])
async def read_all_news(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Получает список всех новостей с пагинацией."""
    news = await get_all_news(db, skip, limit)
    return news

@router.put("/{news_id}", response_model=NewsOut)
async def update_news_item(
        news_id: int,
        title: str = Form(None),
        content: str = Form(None),
        image: UploadFile = File(None),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(ensure_admin)
):
    """Обновляет существующую новость."""
    news = await get_news_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    image_path = news.image_path
    if image:
        # Удаляем старое изображение из MinIO, если оно существует
        if news.image_path:
            try:
                minio_client.remove_object(bucket_name, news.image_path)
                print(f"update_news_item: Removed old image {news.image_path} from MinIO")
            except S3Error as e:
                print(f"Ошибка удаления старого изображения: {str(e)}")

        # Загружаем новое изображение
        image_filename = f"{current_user.id}_{image.filename}"
        image_path = f"{image_filename}"
        try:
            minio_client.put_object(
                bucket_name,
                image_path,
                image.file,
                length=-1,
                part_size=10*1024*1024,
                content_type=image.content_type
            )
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки в MinIO: {str(e)}")

    updated_news = await update_news(db, news, title, content, image_path)
    return updated_news

@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news_item(
        news_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(ensure_admin)
):
    """Удаляет новость по её ID."""
    news = await get_news_by_id(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    # Удаляем изображение из MinIO
    if news.image_path:
        try:
            minio_client.remove_object(bucket_name, news.image_path)
            print(f"delete_news_item: Removed image {news.image_path} from MinIO")
        except S3Error as e:
            print(f"Ошибка удаления изображения: {str(e)}")

    await delete_news(db, news)
    return None

@router.get("/image/{news_id}")
async def get_news_image(news_id: int, db: AsyncSession = Depends(get_db)):
    """Возвращает изображение новости по её ID из MinIO."""
    news = await get_news_by_id(db, news_id)
    if not news or not news.image_path:
        raise HTTPException(status_code=404, detail="Изображение не найдено")

    try:
        # Получаем presigned URL для доступа к изображению
        image_url = minio_client.presigned_get_object(
            bucket_name,
            news.image_path,
            expires=timedelta(seconds=3600)  # Используем timedelta вместо int
        )
        return {"image_url": image_url}
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения изображения из MinIO: {str(e)}")

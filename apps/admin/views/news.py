from fastapi import Request
from sqladmin import ModelView
from wtforms import FileField
from apps.news.models import News
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
import os
from io import BytesIO

# Загружаем переменные окружения
load_dotenv()

# Инициализация клиента MinIO
minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT").replace("http://", ""),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False  # Используйте True, если у вас HTTPS
)

# Убедимся, что бакет существует
bucket_name = os.getenv("MINIO_BUCKET_NAME", "news")
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

class NewsAdmin(ModelView, model=News):
    column_list = [News.id, News.title, News.user_id, News.created_at]
    column_searchable_list = [News.title]
    form_excluded_columns = ["created_at", "updated_at"]
    page_size = 20
    name = "Новость"
    name_plural = "Новости"
    icon = "fa fa-newspaper"
    can_edit = False  # Отключаем редактирование

    form_overrides = {
        "image_path": FileField
    }

    async def insert_model(self, request: Request, data: dict) -> News:
        user_id = request.session.get("user_id")
        print(f"insert_model: Setting user_id = {user_id}")
        if user_id is None:
            raise ValueError("User ID not found in session. Ensure you are logged in as a superuser.")

        form_data = await request.form()
        title = form_data.get("title")
        content = form_data.get("content")
        image = form_data.get("image_path")

        news_obj = News(
            title=title,
            content=content,
            user_id=user_id,
        )

        if image and hasattr(image, "filename") and image.filename:
            image_filename = f"{user_id}_{image.filename}"
            try:
                # Читаем содержимое изображения в байты
                image_content = await image.read()
                # Создаём поток из байтов для MinIO
                image_stream = BytesIO(image_content)
                # Загружаем файл в MinIO
                minio_client.put_object(
                    bucket_name,
                    image_filename,
                    image_stream,
                    length=len(image_content),
                    content_type=image.content_type or "application/octet-stream"
                )
                news_obj.image_path = image_filename  # Сохраняем только имя файла в MinIO
                print(f"insert_model: Uploaded image to MinIO at {image_filename}")
            except S3Error as e:
                raise ValueError(f"Ошибка загрузки в MinIO: {str(e)}")
        else:
            news_obj.image_path = None

        async with self.session_maker() as session:
            session.add(news_obj)
            await session.commit()
            await session.refresh(news_obj)

        print(f"insert_model: Created news with id = {news_obj.id}, image_path = {news_obj.image_path}")
        return news_obj

    async def on_model_delete(self, obj: News, request: Request) -> None:
        """Удаляет файл изображения из MinIO при удалении новости."""
        if obj.image_path:
            try:
                minio_client.remove_object(bucket_name, obj.image_path)
                print(f"on_model_delete: Removed image from MinIO at {obj.image_path}")
            except S3Error as e:
                print(f"Ошибка удаления изображения из MinIO: {str(e)}")

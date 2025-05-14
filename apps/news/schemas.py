from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class NewsBase(BaseModel):
    title: str
    content: str

class NewsCreate(NewsBase):
    pass  # Пока без изображения, добавим его в маршруте через UploadFile

class NewsUpdate(NewsBase):
    title: Optional[str] = None
    content: Optional[str] = None

class NewsOut(NewsBase):
    id: int
    image_path: Optional[str] = None
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
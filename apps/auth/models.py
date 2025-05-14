from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from core.database import Base
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'comment': 'Users'}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    birth_date = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    notifications_enabled = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)  # Новое поле
    created_at = Column(DateTime, server_default=func.now())
    recipes = relationship("Recipe", back_populates="user")

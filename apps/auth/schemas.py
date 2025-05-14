from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum

class GenderEnum(str, Enum):
    MALE = "Мужской"
    FEMALE = "Женский"
    NOT_SPECIFIED = "Не указан"

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

    @field_validator("username", mode="before")
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    password_confirm: str
    birth_date: str | None = None
    gender: GenderEnum | None = None
    notifications_enabled: bool = False

    @field_validator("password", "password_confirm", mode="before")
    def strip_password_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("password_confirm")
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", "password", mode="before")
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int

class EmailCheck(BaseModel):
    email: EmailStr

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    gender: GenderEnum | None = None
    notifications_enabled: bool | None = None

    @field_validator("email", mode="before")
    def strip_email(cls, v: str | None) -> str | None:
        return v.strip() if v else None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    new_password_confirm: str

    @field_validator("current_password", "new_password", "new_password_confirm", mode="before")
    def strip_password_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("new_password_confirm")
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return v

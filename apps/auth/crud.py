from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apps.auth.models import User
from apps.auth.schemas import UserCreate, UserUpdate, PasswordChange
import bcrypt
from jose import jwt, JWTError
from core.config import config
from datetime import timedelta


async def get_user_by_email(db: AsyncSession, email: str):
    email = email.lower()
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()


async def create_verification_token(email: str) -> str:
    """Генерирует токен подтверждения email."""
    to_encode = {"sub": email, "type": "verify"}
    expire = timedelta(hours=24)  # Токен действителен 24 часа
    return jwt.encode(to_encode, config.SECRET_KEY, config.ALGORITHM)


async def create_user(db: AsyncSession, user: UserCreate):
    hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db_user = User(
        username=user.username,
        email=user.email.lower(),
        hashed_password=hashed_password,
        birth_date=user.birth_date,
        gender=user.gender.value if user.gender else None,
        notifications_enabled=user.notifications_enabled,
        is_verified=False  # По умолчанию не подтверждён
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Генерируем токен подтверждения
    verification_token = await create_verification_token(db_user.email)
    return db_user, verification_token


async def verify_user_email(db: AsyncSession, token: str):
    """Подтверждает email по токену."""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "verify":
            return None
        user = await get_user_by_email(db, email)
        if user and not user.is_verified:
            user.is_verified = True
            await db.commit()
            await db.refresh(user)
            return user
        return None
    except JWTError:
        return None


# Остальные функции остаются без изменений
async def update_user(db: AsyncSession, user: User, user_update: UserUpdate):
    if user_update.email is not None and user_update.email != user.email:
        if await get_user_by_email(db, user_update.email):
            raise ValueError("Этот email уже занят")
        user.email = user_update.email.lower()
        user.is_verified = False  # Сбрасываем подтверждение при смене email
    if user_update.gender is not None:
        user.gender = user_update.gender.value
    if user_update.notifications_enabled is not None:
        user.notifications_enabled = user_update.notifications_enabled
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, password_change: PasswordChange):
    if not bcrypt.checkpw(password_change.current_password.encode("utf-8"), user.hashed_password.encode("utf-8")):
        raise ValueError("Текущий пароль неверный")
    user.hashed_password = bcrypt.hashpw(password_change.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await db.commit()
    await db.refresh(user)
    return user

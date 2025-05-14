from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from apps.auth.schemas import UserCreate, UserLogin, Token, EmailCheck, UserUpdate, PasswordChange
from apps.auth.crud import get_user_by_email, create_user, update_user, change_password, create_verification_token, \
    verify_user_email
from apps.auth.models import User
from core.dependencies import get_db
from core.config import config
from core.email import send_email
from jose import jwt, JWTError
from datetime import datetime, timedelta, UTC
import bcrypt
import traceback

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, config.SECRET_KEY, config.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta = timedelta(days=30)):  # 30 дней по умолчанию
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, config.SECRET_KEY, config.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user


@router.post("/check-email")
async def check_email(request: EmailCheck, db: AsyncSession = Depends(get_db)):
    try:
        email = request.email
        user = await get_user_by_email(db, email.lower())
        if user:
            return JSONResponse(
                content={"exists": True, "message": "Email уже зарегистрирован"},
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        return JSONResponse(
            content={"exists": False, "message": "Email доступен"},
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    except Exception as e:
        print(f"Ошибка в check_email: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/register", response_model=Token)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        if await get_user_by_email(db, user.email):
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        db_user, verification_token = await create_user(db, user)

        # Отправляем письмо с подтверждением
        verification_link = f"{config.BASE_URL}/auth/verify?token={verification_token}"
        email_body = f"""
        Здравствуйте, {db_user.username}!

        Спасибо за регистрацию в MealFlow. Пожалуйста, подтвердите ваш email, перейдя по ссылке:
        {verification_link}

        Если вы не регистрировались, просто проигнорируйте это письмо.
        """
        await send_email(db_user.email, "Подтверждение регистрации в MealFlow", email_body)

        access_token = create_access_token(data={"sub": db_user.email})
        refresh_token = create_refresh_token(data={"sub": db_user.email})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": db_user.id
        }
    except Exception as e:
        print(f"Ошибка в register: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Подтверждает email по токену."""
    user = await verify_user_email(db, token)
    if not user:
        raise HTTPException(status_code=400, detail="Недействительный или истёкший токен подтверждения")
    return {"message": "Email успешно подтверждён"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification_email(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if current_user.is_verified:
        raise HTTPException(status_code=400, detail="Email уже подтверждён")

    verification_token = await create_verification_token(current_user.email)
    verification_link = f"{config.BASE_URL}/auth/verify?token={verification_token}"
    email_body = f"""
    Здравствуйте, {current_user.username}!

    Пожалуйста, подтвердите ваш email, перейдя по ссылке:
    {verification_link}

    Если вы не запрашивали это письмо, просто проигнорируйте его.
    """
    await send_email(current_user.email, "Подтверждение email в MealFlow", email_body)
    return {"message": "Письмо с подтверждением отправлено"}

@router.post("/login", response_model=Token)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        db_user = await get_user_by_email(db, user.email)
        if not db_user or not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="Неверный email или пароль")
        access_token = create_access_token(data={"sub": db_user.email})
        refresh_token = create_refresh_token(data={"sub": db_user.email})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": db_user.id
        }
    except Exception as e:
        print(f"Ошибка в login: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительный refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_email(db, email)
    if user is None:
        raise credentials_exception

    # Выдаём новый access_token и обновляем refresh_token
    new_access_token = create_access_token(data={"sub": user.email})
    new_refresh_token = create_refresh_token(data={"sub": user.email})  # Новый refresh_token с продлённым сроком

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user_id": user.id
    }


@router.delete("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        await db.delete(current_user)
        await db.commit()
        return None
    except Exception as e:
        print(f"Ошибка в delete_user: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/create-superuser", response_model=Token)
async def create_superuser(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if await get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    db_user = await create_user(db, user)
    db_user.is_superuser = True
    await db.commit()
    await db.refresh(db_user)
    access_token = create_access_token(
        data={"sub": db_user.email},
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def read_current_user(current_user: User = Depends(get_current_user)):
    """Возвращает данные текущего пользователя."""
    return {
        "message": "Добро пожаловать в MealFlow",
        "username": current_user.username,
        "email": current_user.email,
        "birth_date": current_user.birth_date,
        "gender": current_user.gender,
        "notifications_enabled": current_user.notifications_enabled,
        "is_superuser": current_user.is_superuser,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat()
    }


@router.put("/update")
async def update_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Обновляет данные профиля пользователя."""
    try:
        updated_user = await update_user(db, current_user, user_update)
        return {
            "message": "Профиль успешно обновлен",
            "username": updated_user.username,
            "email": updated_user.email,
            "gender": updated_user.gender,
            "notifications_enabled": updated_user.notifications_enabled
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Ошибка в update_profile: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.put("/change-password")
async def change_user_password(
        password_change: PasswordChange,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Меняет пароль пользователя."""
    try:
        await change_password(db, current_user, password_change)
        return {"message": "Пароль успешно изменен"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Ошибка в change_password: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

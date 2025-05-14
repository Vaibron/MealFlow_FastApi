from fastapi import Request
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncSession
from apps.auth.crud import get_user_by_email
from apps.auth.routes import verify_password
from core.config import config
from core.dependencies import get_db_session

class AdminAuth(AuthenticationBackend):
    def __init__(self):
        super().__init__(secret_key=config.SECRET_KEY)

    async def login(self, request: Request) -> bool:
        form_data = await request.form()
        email = form_data.get("username")
        password = form_data.get("password")
        session = await get_db_session()
        async with session as db_session:
            user = await get_user_by_email(db_session, email)
            if user and verify_password(password, user.hashed_password) and user.is_superuser:
                request.session["authenticated"] = True
                request.session["user_id"] = user.id
                print(f"login: Set user_id = {user.id}")
                return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        authenticated = request.session.get("authenticated", False)
        print(f"authenticate: authenticated = {authenticated}, user_id = {request.session.get('user_id')}")
        return authenticated
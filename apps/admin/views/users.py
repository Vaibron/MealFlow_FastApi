from sqladmin import ModelView
from apps.auth.models import User

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_superuser]
    column_searchable_list = [User.username, User.email]
    page_size = 20
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa fa-user"
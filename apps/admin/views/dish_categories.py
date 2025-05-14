from sqladmin import ModelView
from apps.recipes.models import DishCategory

class DishCategoryAdmin(ModelView, model=DishCategory):
    column_list = [DishCategory.id, DishCategory.name, DishCategory.description, DishCategory.is_active]
    column_searchable_list = [DishCategory.name]
    column_sortable_list = [DishCategory.id, DishCategory.name]
    page_size = 20
    name = "Категория блюда"
    name_plural = "Категории блюд"
    icon = "fa fa-folder"
    form_include = ["name", "description", "is_active"]
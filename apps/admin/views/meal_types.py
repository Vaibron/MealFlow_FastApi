from sqladmin import ModelView
from apps.recipes.models import MealType

class MealTypeAdmin(ModelView, model=MealType):
    column_list = [MealType.id, MealType.order, MealType.name, MealType.description, MealType.is_active]
    column_searchable_list = [MealType.name]
    column_sortable_list = [MealType.id, MealType.name, MealType.order]
    page_size = 20
    name = "Тип блюда"
    name_plural = "Типы блюд"
    icon = "fa fa-tag"
    form_include = ["name", "order", "description", "is_active"]
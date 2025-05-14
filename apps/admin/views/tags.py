from sqladmin import ModelView
from apps.recipes.models import Tag

class TagAdmin(ModelView, model=Tag):
    column_list = [Tag.id, Tag.name, Tag.is_active]
    column_searchable_list = [Tag.name]
    column_sortable_list = [Tag.id, Tag.name]
    page_size = 20
    name = "Тег"
    name_plural = "Теги"
    icon = "fa fa-tags"
    form_include = ["name", "is_active"]
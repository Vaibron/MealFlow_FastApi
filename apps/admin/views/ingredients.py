from sqladmin import ModelView
from apps.recipes.models import Ingredient

class IngredientAdmin(ModelView, model=Ingredient):
    column_list = [Ingredient.id, Ingredient.ingredient_name, Ingredient.unit, Ingredient.is_public]
    column_searchable_list = [Ingredient.ingredient_name]
    page_size = 20
    name = "Ингредиент"
    name_plural = "Ингредиенты"
    icon = "fa fa-carrot"
    form_include = ["ingredient_name", "unit", "is_public"]
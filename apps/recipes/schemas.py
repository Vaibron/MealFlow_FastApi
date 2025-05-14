from pydantic import BaseModel, Field
from typing import List, Optional

class MealTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = True

class MealType(MealTypeBase):
    id: int

    class Config:
        from_attributes = True

class DishCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = True

class DishCategory(DishCategoryBase):
    id: int

    class Config:
        from_attributes = True

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    is_active: Optional[bool] = True

class Tag(TagBase):
    id: int

    class Config:
        from_attributes = True

class RecipeMealType(BaseModel):
    id: int
    meal_type_id: int
    meal_type: Optional[MealType]

    class Config:
        from_attributes = True

class RecipeDishCategory(BaseModel):
    id: int
    dish_category_id: int
    dish_category: Optional[DishCategory]

    class Config:
        from_attributes = True

class RecipeTag(BaseModel):
    id: int
    tag_id: int
    tag: Optional[Tag]

    class Config:
        from_attributes = True

class Step(BaseModel):
    step_number: int = Field(..., gt=0)
    description: str = Field(..., min_length=1)
    duration: Optional[str] = None

class RecipeIngredientBase(BaseModel):
    ingredient_id: int = Field(..., gt=0)
    amount: float = Field(..., gt=0)

class RecipeIngredientCreate(RecipeIngredientBase):
    pass

class Ingredient(BaseModel):
    id: int
    ingredient_name: str
    unit: str
    is_public: bool

    class Config:
        from_attributes = True

class RecipeIngredient(RecipeIngredientBase):
    id: int
    ingredient: Optional[Ingredient]

    class Config:
        from_attributes = True

class RecipeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    steps: List[Step] = Field(..., min_items=1)
    total_time: int = Field(..., ge=0)
    servings: int = Field(..., ge=1)
    calories: Optional[float] = None
    proteins: Optional[float] = None
    fats: Optional[float] = None
    carbohydrates: Optional[float] = None
    is_public: Optional[bool] = False

class RecipeCreate(RecipeBase):
    ingredients: List[RecipeIngredientCreate]
    meal_type_ids: List[int] = Field(default=[])
    dish_category_ids: List[int] = Field(default=[])
    tag_ids: List[int] = Field(default=[])

class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    steps: Optional[List[Step]] = None
    total_time: Optional[int] = None
    servings: Optional[int] = None
    calories: Optional[float] = None
    proteins: Optional[float] = None
    fats: Optional[float] = None
    carbohydrates: Optional[float] = None
    is_public: Optional[bool] = None
    ingredients: Optional[List[RecipeIngredientCreate]] = None
    image_path: Optional[str] = None
    meal_type_ids: Optional[List[int]] = None
    dish_category_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None

    class Config:
        from_attributes = True

class Recipe(RecipeBase):
    id: int
    user_id: int
    image_path: Optional[str] = None
    image_version: int = 0
    ingredients: List[RecipeIngredient]
    meal_types: List[RecipeMealType]
    dish_categories: List[RecipeDishCategory]
    tags: List[RecipeTag]

    class Config:
        from_attributes = True

class IngredientBase(BaseModel):
    ingredient_name: str = Field(..., min_length=1, max_length=100)
    unit: str = Field(default="г", max_length=20)
    is_public: Optional[bool] = False

class Ingredient(IngredientBase):
    id: int

    class Config:
        from_attributes = True

from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class MealType(Base):
    __tablename__ = "meal_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)

class DishCategory(Base):
    __tablename__ = "dish_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)

class RecipeMealType(Base):
    __tablename__ = "recipe_meal_types"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    meal_type_id = Column(Integer, ForeignKey("meal_types.id"), nullable=False)
    recipe = relationship("Recipe", back_populates="meal_types")
    meal_type = relationship("MealType")

class RecipeDishCategory(Base):
    __tablename__ = "recipe_dish_categories"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    dish_category_id = Column(Integer, ForeignKey("dish_categories.id"), nullable=False)
    recipe = relationship("Recipe", back_populates="dish_categories")
    dish_category = relationship("DishCategory")

class RecipeTag(Base):
    __tablename__ = "recipe_tags"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    recipe = relationship("Recipe", back_populates="tags")
    tag = relationship("Tag")

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    steps = Column(JSON, nullable=False)
    total_time = Column(Integer, nullable=False, default=0)  # Total cooking time in minutes
    servings = Column(Integer, nullable=False, default=1)   # Number of servings
    calories = Column(Float, nullable=True)                # Calories per serving
    proteins = Column(Float, nullable=True)                # Proteins per serving
    fats = Column(Float, nullable=True)                    # Fats per serving
    carbohydrates = Column(Float, nullable=True)           # Carbohydrates per serving
    image_path = Column(String, nullable=True)
    image_version = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)
    user = relationship("User", back_populates="recipes")
    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")
    meal_types = relationship("RecipeMealType", back_populates="recipe", cascade="all, delete-orphan")
    dish_categories = relationship("RecipeDishCategory", back_populates="recipe", cascade="all, delete-orphan")
    tags = relationship("RecipeTag", back_populates="recipe", cascade="all, delete-orphan")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    amount = Column(Float, nullable=False)
    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient")

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True, index=True)
    ingredient_name = Column(String(100), nullable=False, unique=True)
    unit = Column(String(20), nullable=False, default="г")
    is_public = Column(Boolean, default=False)

class FavoriteRecipe(Base):
    __tablename__ = "favorite_recipes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    user = relationship("User", backref="favorites")
    recipe = relationship("Recipe")

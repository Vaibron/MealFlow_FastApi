from sqlalchemy import Column, Integer, ForeignKey, JSON, DateTime, String
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime

class MealPlan(Base):
    __tablename__ = "meal_plans"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    days = Column(Integer, nullable=False)  # Количество дней в плане
    persons = Column(Integer, nullable=False)  # Количество персон
    plan = Column(JSON, nullable=False)  # Сгенерированный план в формате JSON
    recipe_source = Column(String, default="both")  # Источник рецептов: mine, mealflow, both
    user = relationship("User", backref="meal_plans")

class ExcludedIngredient(Base):
    __tablename__ = "excluded_ingredients"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    user = relationship("User", backref="excluded_ingredients")
    ingredient = relationship("Ingredient")

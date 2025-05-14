from pydantic import BaseModel, Field, ConfigDict, validator
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
from fastapi import HTTPException

class MealType(BaseModel):
    id: int
    name: str
    order: int

    model_config = ConfigDict(from_attributes=True)

class ExcludedIngredientBase(BaseModel):
    ingredient_id: int = Field(..., gt=0)

class ExcludedIngredientCreate(ExcludedIngredientBase):
    pass

class ExcludedIngredient(ExcludedIngredientBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class MealPlanCreate(BaseModel):
    start_date: datetime = Field(..., description="Дата начала генерации меню")
    days: int = Field(..., ge=1, le=7)
    persons: int = Field(..., ge=1)
    excluded_ingredients: Optional[List[int]] = []
    recipe_source: str = Field(default="both", pattern="^(mine|mealflow|both)$")

    @validator("start_date")
    def validate_start_date(cls, v):
        today = datetime.utcnow().date()
        max_date = today + timedelta(days=14)
        start_date = v.date()
        if start_date < today:
            raise HTTPException(status_code=400, detail="Нельзя генерировать меню на прошлые даты")
        if start_date > max_date:
            raise HTTPException(status_code=400, detail="Дата начала не может быть позже чем +14 дней от текущей")
        return v

    @validator("days")
    def validate_days(cls, v, values):
        if "start_date" in values:
            start_date = values["start_date"].date()
            today = datetime.utcnow().date()
            max_days = (today + timedelta(days=14) - start_date).days + 1
            if v > max_days:
                raise HTTPException(status_code=400, detail=f"Количество дней не может превышать {max_days}")
        return v

class MealPlan(BaseModel):
    id: Optional[int] = None
    user_id: int
    start_date: Optional[datetime] = None
    days: int
    persons: int
    plan: Dict
    meal_types: List[MealType] = []
    recipe_source: str = "both"

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

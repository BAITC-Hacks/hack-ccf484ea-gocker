from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Expense amount, must be greater than 0")
    category: str = Field(..., min_length=1, max_length=50)
    date: date
    description: Optional[str] = Field(default="", max_length=200)

    @field_validator("category")
    @classmethod
    def clean_category(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Категория не может быть пустой")
        return cleaned

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Сумма расхода должна быть строго больше 0")
        return round(v, 2)


class Expense(BaseModel):
    id: int
    user_id: int
    amount: float
    category: str
    date: str
    description: str = ""
    created_at: str


class CategorySummary(BaseModel):
    category: str
    amount: float
    percentage: float


class MonthlySummary(BaseModel):
    month: str
    total: float
    count: int
    categories: list[CategorySummary]
    budget: Optional[float] = None
    remaining: Optional[float] = None


class BudgetSet(BaseModel):
    month: str
    amount: float = Field(..., gt=0)

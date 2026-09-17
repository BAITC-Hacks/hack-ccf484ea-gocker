from datetime import date
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import (
    add_expense,
    delete_expense,
    get_available_months,
    get_expenses_by_month,
    get_monthly_summary,
    set_budget,
)
from app.models import BudgetSet, Expense, ExpenseCreate, MonthlySummary

router = APIRouter()
STATIC_DIR = Path(__file__).parent / "static"


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/expenses", response_model=list[Expense])
async def list_expenses(
    user_id: int = Query(default=1),
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m")),
) -> list[Expense]:
    return await get_expenses_by_month(settings.db_path, user_id, month)


@router.post("/api/expenses", response_model=Expense)
async def create_expense(
    expense: ExpenseCreate,
    user_id: int = Query(default=1),
) -> Expense:
    return await add_expense(settings.db_path, user_id, expense)


@router.delete("/api/expenses/{expense_id}")
async def remove_expense(
    expense_id: int,
    user_id: int = Query(default=1),
) -> dict[str, bool]:
    deleted = await delete_expense(settings.db_path, user_id, expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Расход не найден")
    return {"success": True}


@router.get("/api/summary", response_model=MonthlySummary)
async def get_summary(
    user_id: int = Query(default=1),
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m")),
) -> MonthlySummary:
    return await get_monthly_summary(settings.db_path, user_id, month)


@router.post("/api/budget")
async def save_budget(
    budget: BudgetSet,
    user_id: int = Query(default=1),
) -> dict[str, bool]:
    await set_budget(settings.db_path, user_id, budget)
    return {"success": True}


@router.get("/api/months")
async def list_months(user_id: int = Query(default=1)) -> list[str]:
    months = await get_available_months(settings.db_path, user_id)
    current_month = date.today().strftime("%Y-%m")
    if current_month not in months:
        months.insert(0, current_month)
    return months


@router.post("/api/test_scenario")
async def run_test_scenario(user_id: int = Query(default=1)) -> dict:
    target_month = "2026-09"
    e1 = await add_expense(
        settings.db_path,
        user_id,
        ExpenseCreate(amount=1500, category="еда", date=date(2026, 9, 1), description="Обед"),
    )
    e2 = await add_expense(
        settings.db_path,
        user_id,
        ExpenseCreate(amount=600, category="транспорт", date=date(2026, 9, 2), description="Проездной"),
    )
    e3 = await add_expense(
        settings.db_path,
        user_id,
        ExpenseCreate(amount=900, category="еда", date=date(2026, 9, 3), description="Ужин"),
    )

    s1 = await get_monthly_summary(settings.db_path, user_id, target_month)
    await delete_expense(settings.db_path, user_id, e3.id)
    s2 = await get_monthly_summary(settings.db_path, user_id, target_month)

    return {
        "step1_total": s1.total,
        "step1_categories": {c.category: c.amount for c in s1.categories},
        "step2_total": s2.total,
        "step2_categories": {c.category: c.amount for c in s2.categories},
        "verified": s1.total == 3000.0 and s2.total == 2100.0,
    }


def setup_web_app(app):
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

import os
import tempfile
from datetime import date
import pytest
from pydantic import ValidationError

from app.database import (
    add_expense,
    delete_expense,
    get_expenses_by_month,
    get_monthly_summary,
    init_db,
    set_budget,
)
from app.models import BudgetSet, ExpenseCreate


@pytest.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    await init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_validation_positive_amount():
    with pytest.raises(ValidationError):
        ExpenseCreate(amount=-100, category="Еда", date=date(2026, 9, 1))

    with pytest.raises(ValidationError):
        ExpenseCreate(amount=0, category="Еда", date=date(2026, 9, 1))

    with pytest.raises(ValidationError):
        ExpenseCreate(amount=100, category="   ", date=date(2026, 9, 1))

    exp = ExpenseCreate(amount=150.555, category="Транспорт", date=date(2026, 9, 1))
    assert exp.amount == 150.56


@pytest.mark.asyncio
async def test_section_7_spec_scenario(temp_db):
    user_id = 12345
    m = "2026-09"

    e1 = await add_expense(
        temp_db,
        user_id,
        ExpenseCreate(amount=1500, category="еда", date=date(2026, 9, 1)),
    )
    e2 = await add_expense(
        temp_db,
        user_id,
        ExpenseCreate(amount=600, category="транспорт", date=date(2026, 9, 2)),
    )
    e3 = await add_expense(
        temp_db,
        user_id,
        ExpenseCreate(amount=900, category="еда", date=date(2026, 9, 3)),
    )

    summary = await get_monthly_summary(temp_db, user_id, m)
    assert summary.total == 3000.0
    assert summary.count == 3

    cat_map = {c.category: c.amount for c in summary.categories}
    assert cat_map.get("еда") == 2400.0
    assert cat_map.get("транспорт") == 600.0
    assert sum(cat_map.values()) == summary.total

    deleted = await delete_expense(temp_db, user_id, e3.id)
    assert deleted is True

    summary_after = await get_monthly_summary(temp_db, user_id, m)
    assert summary_after.total == 2100.0
    assert summary_after.count == 2

    cat_map_after = {c.category: c.amount for c in summary_after.categories}
    assert cat_map_after.get("еда") == 1500.0
    assert cat_map_after.get("транспорт") == 600.0
    assert sum(cat_map_after.values()) == summary_after.total


@pytest.mark.asyncio
async def test_empty_month_and_isolation(temp_db):
    summary = await get_monthly_summary(temp_db, user_id=999, month="2026-10")
    assert summary.total == 0.0
    assert summary.count == 0
    assert summary.categories == []

    not_deleted = await delete_expense(temp_db, user_id=999, expense_id=99999)
    assert not_deleted is False


@pytest.mark.asyncio
async def test_budget_tracking(temp_db):
    user_id = 42
    month = "2026-09"
    await set_budget(temp_db, user_id, BudgetSet(month=month, amount=10000))

    await add_expense(
        temp_db,
        user_id,
        ExpenseCreate(amount=2500, category="Жильё", date=date(2026, 9, 5)),
    )

    summary = await get_monthly_summary(temp_db, user_id, month)
    assert summary.budget == 10000.0
    assert summary.total == 2500.0
    assert summary.remaining == 7500.0


@pytest.mark.asyncio
async def test_fastapi_endpoints(temp_db, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from main import create_fastapi_app
    from app.config import settings

    monkeypatch.setattr(settings, "db_path", temp_db)
    app = create_fastapi_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        invalid_resp = await client.post(
            "/api/expenses?user_id=1",
            json={"amount": -50, "category": "Еда", "date": "2026-09-01"},
        )
        assert invalid_resp.status_code == 422

        create_resp = await client.post(
            "/api/expenses?user_id=1",
            json={"amount": 450.5, "category": "Кафе", "date": "2026-09-10", "description": "Кофе"},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["amount"] == 450.5
        assert created["category"] == "Кафе"

        summary_resp = await client.get("/api/summary?user_id=1&month=2026-09")
        assert summary_resp.status_code == 200
        summary_data = summary_resp.json()
        assert summary_data["total"] == 450.5

        scenario_resp = await client.post("/api/test_scenario?user_id=2")
        assert scenario_resp.status_code == 200
        sc_data = scenario_resp.json()
        assert sc_data["verified"] is True
        assert sc_data["step1_total"] == 3000.0
        assert sc_data["step2_total"] == 2100.0


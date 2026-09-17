from collections import defaultdict
from datetime import datetime
from typing import Optional
import aiosqlite
import asyncpg

from app.config import settings
from app.models import BudgetSet, CategorySummary, Expense, ExpenseCreate, MonthlySummary

_pg_pool: Optional[asyncpg.Pool] = None


def is_postgres(target: Optional[str] = None) -> bool:
    url = target or settings.database_url
    return bool(url and (url.startswith("postgresql://") or url.startswith("postgres://")))


async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pg_pool = await asyncpg.create_pool(dsn=url)
    return _pg_pool


async def init_db(db_path: Optional[str] = None) -> None:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    date VARCHAR(10) NOT NULL,
                    description VARCHAR(255) DEFAULT '',
                    created_at VARCHAR(30) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date);
                CREATE TABLE IF NOT EXISTS budgets (
                    user_id BIGINT NOT NULL,
                    month VARCHAR(7) NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (user_id, month)
                );
                """
            )
        return

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_expenses_user_date 
            ON expenses(user_id, date)
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                amount REAL NOT NULL,
                PRIMARY KEY (user_id, month)
            )
            """
        )
        await db.commit()


async def add_expense(
    db_path: Optional[str], user_id: int, expense_data: ExpenseCreate
) -> Expense:
    created_at = datetime.now().isoformat(timespec="seconds")
    date_str = expense_data.date.isoformat()

    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO expenses (user_id, amount, category, date, description, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                user_id,
                expense_data.amount,
                expense_data.category,
                date_str,
                expense_data.description or "",
                created_at,
            )
            expense_id = row["id"]
    else:
        path = db_path or settings.db_path
        async with aiosqlite.connect(path) as db:
            cursor = await db.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    expense_data.amount,
                    expense_data.category,
                    date_str,
                    expense_data.description or "",
                    created_at,
                ),
            )
            await db.commit()
            expense_id = cursor.lastrowid

    return Expense(
        id=expense_id,
        user_id=user_id,
        amount=expense_data.amount,
        category=expense_data.category,
        date=date_str,
        description=expense_data.description or "",
        created_at=created_at,
    )


async def get_expenses_by_month(
    db_path: Optional[str], user_id: int, month: str
) -> list[Expense]:
    pattern = f"{month}%"

    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, amount, category, date, description, created_at
                FROM expenses
                WHERE user_id = $1 AND date LIKE $2
                ORDER BY date DESC, id DESC
                """,
                user_id,
                pattern,
            )
            return [Expense(**dict(r)) for r in rows]

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, amount, category, date, description, created_at
            FROM expenses
            WHERE user_id = ? AND date LIKE ?
            ORDER BY date DESC, id DESC
            """,
            (user_id, pattern),
        )
        rows = await cursor.fetchall()
        return [Expense(**dict(row)) for row in rows]


async def get_expense_by_id(
    db_path: Optional[str], user_id: int, expense_id: int
) -> Optional[Expense]:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, amount, category, date, description, created_at
                FROM expenses
                WHERE user_id = $1 AND id = $2
                """,
                user_id,
                expense_id,
            )
            return Expense(**dict(row)) if row else None

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, amount, category, date, description, created_at
            FROM expenses
            WHERE user_id = ? AND id = ?
            """,
            (user_id, expense_id),
        )
        row = await cursor.fetchone()
        return Expense(**dict(row)) if row else None


async def delete_expense(db_path: Optional[str], user_id: int, expense_id: int) -> bool:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM expenses WHERE user_id = $1 AND id = $2",
                user_id,
                expense_id,
            )
            return res.endswith("1")

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "DELETE FROM expenses WHERE user_id = ? AND id = ?",
            (user_id, expense_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_monthly_summary(
    db_path: Optional[str], user_id: int, month: str
) -> MonthlySummary:
    expenses = await get_expenses_by_month(db_path, user_id, month)
    category_totals: dict[str, float] = defaultdict(float)

    for item in expenses:
        category_totals[item.category] += item.amount

    total = round(sum(category_totals.values()), 2)

    categories: list[CategorySummary] = []
    for cat, cat_amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        cat_amt_rounded = round(cat_amt, 2)
        pct = round((cat_amt_rounded / total) * 100, 1) if total > 0 else 0.0
        categories.append(
            CategorySummary(
                category=cat,
                amount=cat_amt_rounded,
                percentage=pct,
            )
        )

    budget = await get_budget(db_path, user_id, month)
    remaining = round(budget - total, 2) if budget is not None else None

    return MonthlySummary(
        month=month,
        total=total,
        count=len(expenses),
        categories=categories,
        budget=budget,
        remaining=remaining,
    )


async def set_budget(
    db_path: Optional[str], user_id: int, budget_data: BudgetSet
) -> None:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO budgets (user_id, month, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, month) DO UPDATE SET amount = EXCLUDED.amount
                """,
                user_id,
                budget_data.month,
                budget_data.amount,
            )
        return

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO budgets (user_id, month, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month) DO UPDATE SET amount = excluded.amount
            """,
            (user_id, budget_data.month, budget_data.amount),
        )
        await db.commit()


async def get_budget(db_path: Optional[str], user_id: int, month: str) -> Optional[float]:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT amount FROM budgets WHERE user_id = $1 AND month = $2",
                user_id,
                month,
            )
            return float(val) if val is not None else None

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT amount FROM budgets WHERE user_id = ? AND month = ?",
            (user_id, month),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else None


async def get_available_months(db_path: Optional[str], user_id: int) -> list[str]:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT SUBSTRING(date, 1, 7) as m
                FROM expenses
                WHERE user_id = $1
                ORDER BY m DESC
                """,
                user_id,
            )
            return [r["m"] for r in rows]

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT substr(date, 1, 7) as m
            FROM expenses
            WHERE user_id = ?
            ORDER BY m DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def clear_user_data(db_path: Optional[str], user_id: int) -> None:
    if is_postgres(db_path):
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM expenses WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM budgets WHERE user_id = $1", user_id)
        return

    path = db_path or settings.db_path
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
        await db.commit()

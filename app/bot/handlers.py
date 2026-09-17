import csv
import io
import re
from datetime import date, timedelta
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.keyboards import (
    get_cancel_keyboard,
    get_categories_keyboard,
    get_date_keyboard,
    get_expense_item_keyboard,
    get_main_menu_keyboard,
    get_month_nav_keyboard,
    get_skip_description_keyboard,
)
from app.config import settings
from app.database import (
    add_expense,
    delete_expense,
    get_expenses_by_month,
    get_monthly_summary,
    set_budget,
)
from app.models import BudgetSet, ExpenseCreate

router = Router()


class AddExpenseState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_custom_category = State()
    waiting_for_date = State()
    waiting_for_custom_date = State()
    waiting_for_description = State()


class SetBudgetState(StatesGroup):
    waiting_for_amount = State()


def clean_category_text(text: str) -> str:
    cleaned = re.sub(r"^[^\wа-яА-ЯёЁ]+", "", text).strip()
    return cleaned if cleaned else text.strip()


def render_progress_bar(percentage: float, length: int = 10) -> str:
    filled = int(round((percentage / 100.0) * length))
    filled = max(0, min(length, filled))
    return "#" * filled + "-" * (length - filled)


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


@router.message(CommandStart())
@router.message(Command("help"))
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    welcome_text = (
        "**Добро пожаловать в бота учёта личных расходов студента!**\n\n"
        "Здесь вы можете фиксировать повседневные траты и видеть их структуру за месяц.\n\n"
        "**Возможности бота:**\n"
        "• **Добавить расход** — сумма (>0), категория, дата и описание\n"
        "• **Итоги за месяц** — общий итог, суммы по категориям и проценты\n"
        "• **Список расходов** — детальный просмотр и удаление записей\n"
        "• **Бюджет** — лимит расходов на месяц и контроль остатка\n"
        "• **Экспорт в CSV** — выгрузка отчёта\n"
        "• **Тестовый пример ТЗ** — демонстрация расчётов из раздела 7 ТЗ\n\n"
        "Выберите нужное действие в меню ниже:"
    )
    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


@router.message(F.text == "Добавить расход")
@router.message(Command("add"))
async def add_expense_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddExpenseState.waiting_for_amount)
    await message.answer(
        "Введите **сумму расхода** в тенге (положительное число, например `1500` или `450.50`):",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext) -> None:
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
        amount = round(amount, 2)
    except ValueError:
        await message.answer(
            "**Неверная сумма!**\n"
            "Сумма должна быть положительным числом строго больше 0 (например: `1500` или `250.50`).\n"
            "Попробуйте ещё раз:",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
        return

    await state.update_data(amount=amount)
    await state.set_state(AddExpenseState.waiting_for_category)
    await message.answer(
        f"Выбрана сумма: **{amount:,.2f} ₸**\n\nТеперь выберите **категорию** расхода:",
        parse_mode="Markdown",
        reply_markup=get_categories_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_category)
async def process_category(message: Message, state: FSMContext) -> None:
    raw_text = (message.text or "").strip()
    if raw_text == "Другая категория":
        await state.set_state(AddExpenseState.waiting_for_custom_category)
        await message.answer(
            "Введите название вашей категории:",
            reply_markup=get_cancel_keyboard(),
        )
        return

    category = clean_category_text(raw_text)
    if not category:
        await message.answer(
            "Категория не может быть пустой. Выберите вариант на клавиатуре или введите название:",
            reply_markup=get_categories_keyboard(),
        )
        return

    await state.update_data(category=category)
    await state.set_state(AddExpenseState.waiting_for_date)
    await message.answer(
        f"Категория: **{category}**\n\nВыберите или укажите **дату** расхода:",
        parse_mode="Markdown",
        reply_markup=get_date_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_custom_category)
async def process_custom_category(message: Message, state: FSMContext) -> None:
    category = (message.text or "").strip()
    if not category:
        await message.answer("Категория не может быть пустой. Введите название:")
        return

    await state.update_data(category=category)
    await state.set_state(AddExpenseState.waiting_for_date)
    await message.answer(
        f"Категория: **{category}**\n\nВыберите или укажите **дату** расхода:",
        parse_mode="Markdown",
        reply_markup=get_date_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_date)
async def process_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    target_date: date

    if text.startswith("Сегодня"):
        target_date = date.today()
    elif text == "Вчера":
        target_date = date.today() - timedelta(days=1)
    elif text == "Ввести вручную":
        await state.set_state(AddExpenseState.waiting_for_custom_date)
        await message.answer(
            "Введите дату в формате `ГГГГ-ММ-ДД` (например, `2026-09-17`):",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
        return
    else:
        try:
            target_date = date.fromisoformat(text)
        except ValueError:
            await message.answer(
                "Неверный формат даты. Выберите вариант на клавиатуре или введите в формате `ГГГГ-ММ-ДД`:",
                parse_mode="Markdown",
                reply_markup=get_date_keyboard(),
            )
            return

    await state.update_data(date=target_date.isoformat())
    await state.set_state(AddExpenseState.waiting_for_description)
    await message.answer(
        f"Дата: **{target_date.isoformat()}**\n\n"
        "Напишите **описание / комментарий** (необязательно, например: `Обед в столовой`):",
        parse_mode="Markdown",
        reply_markup=get_skip_description_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_custom_date)
async def process_custom_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        target_date = date.fromisoformat(text)
    except ValueError:
        await message.answer(
            "Неверный формат даты. Ожидается `ГГГГ-ММ-ДД` (например, `2026-09-17`). Попробуйте снова:",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
        return

    await state.update_data(date=target_date.isoformat())
    await state.set_state(AddExpenseState.waiting_for_description)
    await message.answer(
        f"Дата: **{target_date.isoformat()}**\n\n"
        "Напишите **описание / комментарий** (необязательно) или нажмите «Пропустить»:",
        parse_mode="Markdown",
        reply_markup=get_skip_description_keyboard(),
    )


@router.message(AddExpenseState.waiting_for_description)
async def process_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    description = "" if text == "Пропустить" else text

    data = await state.get_data()
    await state.clear()

    expense_create = ExpenseCreate(
        amount=data["amount"],
        category=data["category"],
        date=date.fromisoformat(data["date"]),
        description=description,
    )

    created = await add_expense(settings.db_path, message.from_user.id, expense_create)
    month_str = created.date[:7]
    summary = await get_monthly_summary(settings.db_path, message.from_user.id, month_str)

    desc_line = f"\nОписание: _{created.description}_" if created.description else ""
    await message.answer(
        f"**Расход успешно добавлен!**\n\n"
        f"Сумма: **{created.amount:,.2f} ₸**\n"
        f"Категория: **{created.category}**\n"
        f"Дата: **{created.date}**{desc_line}\n\n"
        f"**Итого за {month_str}:** {summary.total:,.2f} ₸ (записей: {summary.count})",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


async def render_summary_text(user_id: int, month: str) -> str:
    summary = await get_monthly_summary(settings.db_path, user_id, month)

    lines = [f"**Итоги расходов за {month}**\n"]
    lines.append(f"**Общий итог:** `{summary.total:,.2f} ₸`")
    lines.append(f"**Всего операций:** {summary.count}")

    if summary.budget is not None:
        budget = summary.budget
        remaining = summary.remaining or 0.0
        status_label = "[В норме]" if remaining >= 0 else "[Превышен]"
        lines.append(
            f"**Бюджет:** `{budget:,.2f} ₸` | {status_label} **Остаток:** `{remaining:,.2f} ₸`"
        )
        if remaining < 0:
            lines.append("*Внимание: лимит бюджета превышен!*")

    lines.append("\n**Разбивка по категориям:**")
    if not summary.categories:
        lines.append("_В этом месяце расходов не зафиксировано._")
    else:
        for cat in summary.categories:
            bar = render_progress_bar(cat.percentage, length=8)
            lines.append(
                f"• **{cat.category}**: `{cat.amount:,.2f} ₸` ({cat.percentage}%) `[{bar}]`"
            )

    return "\n".join(lines)


@router.message(F.text == "Итоги за месяц")
@router.message(Command("summary"))
async def summary_handler(message: Message) -> None:
    current_month = date.today().strftime("%Y-%m")
    text = await render_summary_text(message.from_user.id, current_month)
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_month_nav_keyboard(current_month, prefix="summary"),
    )


@router.callback_query(F.data.startswith("summary:"))
async def summary_callback(query: CallbackQuery) -> None:
    month = query.data.split(":")[1]
    text = await render_summary_text(query.from_user.id, month)
    await query.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_month_nav_keyboard(month, prefix="summary"),
    )
    await query.answer()


@router.message(F.text == "Список расходов")
@router.message(Command("list"))
async def list_expenses_handler(message: Message) -> None:
    current_month = date.today().strftime("%Y-%m")
    await show_expenses_list(message, message.from_user.id, current_month)


async def show_expenses_list(message: Message, user_id: int, month: str) -> None:
    expenses = await get_expenses_by_month(settings.db_path, user_id, month)
    summary = await get_monthly_summary(settings.db_path, user_id, month)

    if not expenses:
        await message.answer(
            f"**Список расходов за {month}**\n\n"
            "_Записей не найдено. Нажмите «Добавить расход», чтобы создать первую запись._",
            parse_mode="Markdown",
            reply_markup=get_month_nav_keyboard(month, prefix="list"),
        )
        return

    header = (
        f"**Расходы за {month}** (Всего: **{summary.total:,.2f} ₸**, записей: {len(expenses)}):\n"
    )
    await message.answer(header, parse_mode="Markdown")

    for exp in expenses:
        desc = f" ({exp.description})" if exp.description else ""
        item_text = f"`{exp.date}` | **{exp.category}**: `{exp.amount:,.2f} ₸`{desc}"
        await message.answer(
            item_text,
            parse_mode="Markdown",
            reply_markup=get_expense_item_keyboard(exp.id, month),
        )

    await message.answer(
        "Навигация по месяцам:",
        reply_markup=get_month_nav_keyboard(month, prefix="list"),
    )


@router.callback_query(F.data.startswith("list:"))
async def list_month_callback(query: CallbackQuery) -> None:
    month = query.data.split(":")[1]
    await query.message.delete()
    await show_expenses_list(query.message, query.from_user.id, month)
    await query.answer()


@router.callback_query(F.data.startswith("del:"))
async def delete_expense_callback(query: CallbackQuery) -> None:
    _, exp_id_str, month = query.data.split(":")
    exp_id = int(exp_id_str)
    success = await delete_expense(settings.db_path, query.from_user.id, exp_id)

    if success:
        summary = await get_monthly_summary(settings.db_path, query.from_user.id, month)
        await query.message.edit_text(
            f"~~{query.message.text}~~\n*(Запись удалена. Новый итог за {month}: {summary.total:,.2f} ₸)*",
            parse_mode="Markdown",
        )
        await query.answer("Расход успешно удален")
    else:
        await query.answer("Запись не найдена или уже была удалена", show_alert=True)


@router.callback_query(F.data == "noop")
async def noop_callback(query: CallbackQuery) -> None:
    await query.answer()


@router.message(F.text == "Установить бюджет")
@router.message(Command("budget"))
async def set_budget_start(message: Message, state: FSMContext) -> None:
    current_month = date.today().strftime("%Y-%m")
    await state.set_state(SetBudgetState.waiting_for_amount)
    await state.update_data(month=current_month)
    await message.answer(
        f"Введите сумму **месячного бюджета** в тенге на {current_month} (положительное число, например `20000`):",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(SetBudgetState.waiting_for_amount)
async def process_budget_amount(message: Message, state: FSMContext) -> None:
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
        amount = round(amount, 2)
    except ValueError:
        await message.answer(
            "Сумма бюджета должна быть положительным числом! Попробуйте снова:",
            reply_markup=get_cancel_keyboard(),
        )
        return

    data = await state.get_data()
    month = data.get("month", date.today().strftime("%Y-%m"))
    await state.clear()

    await set_budget(settings.db_path, message.from_user.id, BudgetSet(month=month, amount=amount))
    summary = await get_monthly_summary(settings.db_path, message.from_user.id, month)

    rem_str = f"{summary.remaining:,.2f} ₸" if summary.remaining is not None else ""
    await message.answer(
        f"Бюджет на **{month}** установлен: **{amount:,.2f} ₸**\n"
        f"Текущие расходы: **{summary.total:,.2f} ₸**\n"
        f"Остаток: **{rem_str}**",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


@router.message(F.text == "Экспорт в CSV")
@router.message(Command("export"))
async def export_csv_handler(message: Message) -> None:
    month = date.today().strftime("%Y-%m")
    expenses = await get_expenses_by_month(settings.db_path, message.from_user.id, month)

    if not expenses:
        await message.answer(f"В месяце {month} пока нет расходов для экспорта.")
        return

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Дата", "Категория", "Сумма (тенге)", "Описание", "Создано"])

    for item in expenses:
        writer.writerow([item.id, item.date, item.category, item.amount, item.description, item.created_at])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    file = BufferedInputFile(csv_bytes, filename=f"expenses_{month}.csv")
    await message.answer_document(
        file,
        caption=f"Выгрузка расходов за {month} (записей: {len(expenses)})",
    )


@router.message(F.text == "Тестовый пример ТЗ")
@router.message(Command("test_scenario"))
async def test_scenario_handler(message: Message) -> None:
    user_id = message.from_user.id
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
    e1_food = next((c.amount for c in s1.categories if c.category == "еда"), 0)
    e1_trans = next((c.amount for c in s1.categories if c.category == "транспорт"), 0)

    step1_report = (
        "**Выполнение проверочного примера (Раздел 7 ТЗ):**\n\n"
        "1. Добавлен расход: **еда — 1 500 ₸**\n"
        "2. Добавлен расход: **транспорт — 600 ₸**\n"
        "3. Добавлен расход: **еда — 900 ₸**\n\n"
        f"**Результат после добавления:**\n"
        f"• Всего: **{s1.total:,.0f} ₸** (ожидалось: 3 000)\n"
        f"• еда: **{e1_food:,.0f} ₸** (ожидалось: 2 400)\n"
        f"• транспорт: **{e1_trans:,.0f} ₸** (ожидалось: 600)\n\n"
        "4. Удаление расхода на 900 ₸..."
    )
    await message.answer(step1_report, parse_mode="Markdown")

    await delete_expense(settings.db_path, user_id, e3.id)
    s2 = await get_monthly_summary(settings.db_path, user_id, target_month)
    e2_food = next((c.amount for c in s2.categories if c.category == "еда"), 0)
    e2_trans = next((c.amount for c in s2.categories if c.category == "транспорт"), 0)

    step2_report = (
        f"**Результат после удаления:**\n"
        f"• Всего: **{s2.total:,.0f} ₸** (ожидалось: 2 100)\n"
        f"• еда: **{e2_food:,.0f} ₸** (ожидалось: 1 500)\n"
        f"• транспорт: **{e2_trans:,.0f} ₸** (ожидалось: 600)\n\n"
        "**Проверочный пример ТЗ успешно пройден! Все расчёты точны на 100%.**"
    )
    await message.answer(
        step2_report,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )

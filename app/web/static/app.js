document.addEventListener("DOMContentLoaded", () => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const urlParams = new URLSearchParams(window.location.search);
  const userId = tg?.initDataUnsafe?.user?.id || urlParams.get("user_id") || 1;

  const monthSelect = document.getElementById("monthSelect");
  const refreshBtn = document.getElementById("refreshBtn");
  const totalAmountEl = document.getElementById("totalAmount");
  const operationCountEl = document.getElementById("operationCount");
  const budgetValueEl = document.getElementById("budgetValue");
  const budgetRemainingEl = document.getElementById("budgetRemaining");
  const budgetProgressBar = document.getElementById("budgetProgressBar");
  const categoriesTableBody = document.getElementById("categoriesTableBody");
  const expensesTableBody = document.getElementById("expensesTableBody");
  const statusBarMessage = document.getElementById("statusBarMessage");
  const statusBarPeriod = document.getElementById("statusBarPeriod");

  const expenseForm = document.getElementById("expenseForm");
  const amountInput = document.getElementById("amountInput");
  const amountError = document.getElementById("amountError");
  const categoryInput = document.getElementById("categoryInput");
  const categoryError = document.getElementById("categoryError");
  const dateInput = document.getElementById("dateInput");
  const dateError = document.getElementById("dateError");
  const descriptionInput = document.getElementById("descriptionInput");
  const quickCategoryBtns = document.getElementById("quickCategoryBtns");

  const budgetLimitInput = document.getElementById("budgetLimitInput");
  const saveBudgetBtn = document.getElementById("saveBudgetBtn");
  const runScenarioBtn = document.getElementById("runScenarioBtn");
  const menuScenario = document.getElementById("menuScenario");
  const menuHelp = document.getElementById("menuHelp");

  const winModal = document.getElementById("winModal");
  const modalTitle = document.getElementById("modalTitle");
  const modalMessage = document.getElementById("modalMessage");
  const modalCloseX = document.getElementById("modalCloseX");
  const modalOkBtn = document.getElementById("modalOkBtn");
  const toastWin = document.getElementById("toastWin");

  const now = new Date();
  const currentMonthStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const todayStr = now.toISOString().split("T")[0];

  monthSelect.value = currentMonthStr;
  dateInput.value = todayStr;
  statusBarPeriod.textContent = `Период: ${currentMonthStr}`;

  function setStatus(msg) {
    if (statusBarMessage) {
      statusBarMessage.textContent = msg;
    }
  }

  function showToast(msg, duration = 2500) {
    toastWin.textContent = msg;
    toastWin.classList.add("show");
    setTimeout(() => {
      toastWin.classList.remove("show");
    }, duration);
  }

  function showWinModal(title, text) {
    modalTitle.textContent = title;
    modalMessage.textContent = text;
    winModal.classList.add("open");
  }

  modalCloseX.addEventListener("click", () => winModal.classList.remove("open"));
  modalOkBtn.addEventListener("click", () => winModal.classList.remove("open"));

  document.querySelectorAll(".tab").forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      tabBtn.classList.add("active");
      const targetId = tabBtn.dataset.tab;
      document.getElementById(targetId)?.classList.add("active");
    });
  });

  quickCategoryBtns.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    categoryInput.value = btn.dataset.cat;
    categoryError.textContent = "";
  });

  function formatTenge(val) {
    const num = Number(val) || 0;
    return `${num.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₸`;
  }

  async function loadData() {
    const month = monthSelect.value || currentMonthStr;
    statusBarPeriod.textContent = `Период: ${month}`;
    setStatus("Загрузка данных...");

    try {
      const [summaryRes, expensesRes] = await Promise.all([
        fetch(`/api/summary?user_id=${userId}&month=${month}`),
        fetch(`/api/expenses?user_id=${userId}&month=${month}`),
      ]);

      if (summaryRes.ok && expensesRes.ok) {
        const summary = await summaryRes.json();
        const expenses = await expensesRes.json();
        renderSummary(summary);
        renderExpenses(expenses);
        setStatus("Готов");
      } else {
        setStatus("Ошибка загрузки данных");
      }
    } catch (err) {
      setStatus("Автономный режим");
    }
  }

  function renderSummary(summary) {
    totalAmountEl.textContent = formatTenge(summary.total);
    operationCountEl.textContent = `Записей: ${summary.count}`;

    if (summary.budget !== null && summary.budget !== undefined) {
      budgetValueEl.textContent = formatTenge(summary.budget);
      const pct = Math.min(100, Math.round((summary.total / summary.budget) * 100));
      budgetProgressBar.style.width = `${pct}%`;

      if (summary.remaining < 0) {
        budgetProgressBar.classList.add("danger");
        budgetRemainingEl.textContent = `Перерасход: ${formatTenge(Math.abs(summary.remaining))}`;
        budgetRemainingEl.style.color = "#800000";
      } else {
        budgetProgressBar.classList.remove("danger");
        budgetRemainingEl.textContent = `Остаток: ${formatTenge(summary.remaining)}`;
        budgetRemainingEl.style.color = "#404040";
      }
    } else {
      budgetValueEl.textContent = "Не задан";
      budgetRemainingEl.textContent = "Остаток: -";
      budgetProgressBar.style.width = "0%";
      budgetProgressBar.classList.remove("danger");
    }

    if (!summary.categories || summary.categories.length === 0) {
      categoriesTableBody.innerHTML =
        '<tr><td colspan="4" style="text-align: center; color: #606060;">Нет данных за период</td></tr>';
      return;
    }

    categoriesTableBody.innerHTML = summary.categories
      .map(
        (c) => `
        <tr>
          <td><strong>${c.category}</strong></td>
          <td>${formatTenge(c.amount)}</td>
          <td>${c.percentage}%</td>
          <td>
            <div class="win-progress-track" style="height: 10px;">
              <div class="win-progress-fill" style="width: ${c.percentage}%;"></div>
            </div>
          </td>
        </tr>
      `
      )
      .join("");
  }

  function renderExpenses(expenses) {
    if (!expenses || expenses.length === 0) {
      expensesTableBody.innerHTML =
        '<tr><td colspan="5" style="text-align: center; color: #606060; padding: 12px;">Записей не обнаружено</td></tr>';
      return;
    }

    expensesTableBody.innerHTML = expenses
      .map(
        (exp) => `
        <tr>
          <td>${exp.date}</td>
          <td><strong>${exp.category}</strong></td>
          <td>${formatTenge(exp.amount)}</td>
          <td>${exp.description || "-"}</td>
          <td style="text-align: center;">
            <button type="button" class="btn-win btn-win-sm btn-delete" data-id="${exp.id}">Удалить</button>
          </td>
        </tr>
      `
      )
      .join("");
  }

  expensesTableBody.addEventListener("click", async (e) => {
    const delBtn = e.target.closest(".btn-delete");
    if (!delBtn) return;
    const expId = delBtn.dataset.id;

    delBtn.disabled = true;
    delBtn.textContent = "...";
    try {
      const res = await fetch(`/api/expenses/${expId}?user_id=${userId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showToast("Запись удалена");
        await loadData();
      } else {
        showWinModal("Ошибка", "Не удалось удалить выбранную запись.");
      }
    } catch (err) {
      showWinModal("Ошибка связи", "Сервер базы данных недоступен.");
    }
  });

  expenseForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    let valid = true;
    amountError.textContent = "";
    categoryError.textContent = "";
    dateError.textContent = "";

    const amountVal = parseFloat(amountInput.value);
    if (isNaN(amountVal) || amountVal <= 0) {
      amountError.textContent = "Сумма должна быть числом больше 0";
      amountInput.classList.add("is-invalid");
      valid = false;
    } else {
      amountInput.classList.remove("is-invalid");
    }

    const catVal = categoryInput.value.trim();
    if (!catVal) {
      categoryError.textContent = "Укажите категорию";
      categoryInput.classList.add("is-invalid");
      valid = false;
    } else {
      categoryInput.classList.remove("is-invalid");
    }

    const dateVal = dateInput.value;
    if (!dateVal) {
      dateError.textContent = "Укажите дату";
      dateInput.classList.add("is-invalid");
      valid = false;
    } else {
      dateInput.classList.remove("is-invalid");
    }

    if (!valid) return;

    const payload = {
      amount: amountVal,
      category: catVal,
      date: dateVal,
      description: descriptionInput.value.trim(),
    };

    setStatus("Сохранение записи...");
    try {
      const res = await fetch(`/api/expenses?user_id=${userId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        showToast("Расход успешно сохранен");
        amountInput.value = "";
        descriptionInput.value = "";

        const expenseMonth = dateVal.slice(0, 7);
        if (monthSelect.value !== expenseMonth) {
          monthSelect.value = expenseMonth;
        }
        await loadData();

        document.querySelector('.tab[data-tab="tab-summary"]')?.click();
      } else {
        const errorData = await res.json();
        showWinModal("Ошибка сохранения", errorData.detail || "Не удалось сохранить расход.");
      }
    } catch (err) {
      showWinModal("Ошибка сети", "Не удалось отправить данные на сервер.");
    }
  });

  saveBudgetBtn.addEventListener("click", async () => {
    const amount = parseFloat(budgetLimitInput.value);
    if (isNaN(amount) || amount <= 0) {
      showWinModal("Ошибка ввода", "Введите положительную сумму бюджета.");
      return;
    }

    const month = monthSelect.value || currentMonthStr;
    try {
      const res = await fetch(`/api/budget?user_id=${userId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ month, amount }),
      });

      if (res.ok) {
        budgetLimitInput.value = "";
        showToast("Бюджет установлен");
        await loadData();
        document.querySelector('.tab[data-tab="tab-summary"]')?.click();
      }
    } catch (err) {
      showWinModal("Ошибка", "Не удалось сохранить бюджет.");
    }
  });

  async function executeTestScenario() {
    setStatus("Выполнение теста раздела 7...");
    try {
      const res = await fetch(`/api/test_scenario?user_id=${userId}`, {
        method: "POST",
      });
      const data = await res.json();
      monthSelect.value = "2026-09";
      await loadData();

      document.querySelector('.tab[data-tab="tab-summary"]')?.click();

      const resultMsg = data.verified
        ? `Проверка успешно пройдена!\n\nШаг 1: Добавлено 1500 (еда) + 600 (транспорт) + 900 (еда) = ${formatTenge(data.step1_total)}\nШаг 2: Удален расход на 900 -> Новый итог = ${formatTenge(data.step2_total)}\n\nВсе вычисления точны на 100%.`
        : "Тестовый сценарий завершился с несоответствием результатов.";

      showWinModal("Отчет проверки ТЗ (Раздел 7)", resultMsg);
    } catch (err) {
      showWinModal("Ошибка", "Не удалось запустить тестовый сценарий.");
    }
  }

  runScenarioBtn.addEventListener("click", executeTestScenario);
  menuScenario.addEventListener("click", executeTestScenario);
  menuHelp.addEventListener("click", () => {
    showWinModal(
      "Справка - Финансы v1.0",
      "Приложение учета личных расходов студента.\nИнтерфейс: Windows 98 Edition.\nВалюта: Тенге (₸).\nБаза данных: PostgreSQL / SQLite.\n\nРазработано в рамках хакатона без ИИ и внешних API."
    );
  });

  monthSelect.addEventListener("change", loadData);
  refreshBtn.addEventListener("click", loadData);

  loadData();
});

// Admin: the plan editor. Limits are per month in złoty; empty = no limit.
const PLAN_KINDS = ["impulse", "discretionary", "essential", "other"];

function recentAverages() {
  const done = D.series.filter(s => s.complete).slice(-3), avg = {};
  for (const s of done) for (const [name, v] of Object.entries(s.by_category)) avg[name] = (avg[name] || 0) + v / done.length;
  return { avg, months: done.map(s => s.month) };
}

function budgetsHtml() {
  const plan = ADMIN.budget || { goal: null, limits: {} }, { avg, months } = recentAverages();
  const rows = D.categories.filter(c => PLAN_KINDS.includes(c.kind))
    .sort((a, b) => PLAN_KINDS.indexOf(a.kind) - PLAN_KINDS.indexOf(b.kind) || (avg[b.name] || 0) - (avg[a.name] || 0))
    .map(c => {
      const limit = plan.limits[c.name];
      return `<tr data-limit-cat="${esc(c.name)}"><td><span class="dot" style="background:${kindColor(c.kind)}"></span>${esc(c.label)}</td>
        <td class="num">${zl(Math.max(0, avg[c.name] || 0))}</td>
        <td><input type="number" min="0" step="10" data-avg="${Math.round(Math.max(0, avg[c.name] || 0) / 100)}" value="${limit ? Math.round(limit / 100) : ""}" placeholder="без лимита" style="width:130px"> zł</td></tr>`;
    }).join("");
  return `<p class="hint">План для пользователя «${esc(D.user)}». Пустое поле — без лимита. Всё необязательно: без плана блок в отчёте не показывается.</p>
    <h2>Цель накоплений</h2>
    <div class="filters">Откладывать в месяц: <input type="number" id="goalInput" min="0" step="100" value="${plan.goal ? Math.round(plan.goal / 100) : ""}" placeholder="без цели" style="width:140px"> zł</div>
    <h2 style="margin-top:24px">Лимиты по категориям</h2>
    <p class="hint">Рядом — среднее за ${months.map(shortM).join(", ") || "последние месяцы"}. Кнопки ниже заполняют пустые поля импульсивных и необязательных трат подсказкой.</p>
    <div class="filters"><button data-plan="fill-10">Среднее −10%</button><button data-plan="fill-25">Среднее −25%</button><button data-plan="clear">Очистить все лимиты</button></div>
    <div class="table-scroll"><table class="edit"><thead><tr><th>Категория</th><th class="num">Среднее в месяц</th><th>Лимит</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="filters" style="margin-top:16px"><button data-plan="save">Сохранить план</button></div>`;
}

document.addEventListener("click", e => {
  const b = e.target.closest("button[data-plan]");
  if (!b) return;
  const inputs = [...document.querySelectorAll("tr[data-limit-cat] input")];
  const fill = cut => inputs.forEach(input => {
    const kind = catKind(input.closest("tr").dataset.limitCat), avg = Number(input.dataset.avg);
    if (!input.value && avg > 0 && (kind === "impulse" || kind === "discretionary")) input.value = Math.max(10, Math.round(avg * (1 - cut) / 10) * 10);
  });
  if (b.dataset.plan === "fill-10") fill(0.1);
  else if (b.dataset.plan === "fill-25") fill(0.25);
  else if (b.dataset.plan === "clear") inputs.forEach(input => { input.value = ""; });
  else if (b.dataset.plan === "save") {
    const limits = {};
    for (const input of inputs) if (Number(input.value) > 0) limits[input.closest("tr").dataset.limitCat] = Number(input.value);
    const goal = Number(byId("goalInput").value);
    act(api("/api/budgets", { user: ADMIN.current_user, goal: goal > 0 ? goal : null, limits }), b);
  }
});

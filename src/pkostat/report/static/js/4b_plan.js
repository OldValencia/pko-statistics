// The month against the plan: saving goal and category limits. Hidden when no plan is set.
const PLAN_STATUS = {
  ok: { icon: "✓", text: "в лимите", color: "var(--good)" },
  near: { icon: "●", text: "близко к лимиту", color: "var(--warn)" },
  over: { icon: "✕", text: "перерасход", color: "var(--bad-text)" },
};

function renderPlan(r) {
  const card = byId("planCard"), goal = r.goal, lines = r.budgets || [];
  card.hidden = !goal && !lines.length;
  if (card.hidden) return;
  const over = lines.filter(l => l.status === "over").length, near = lines.filter(l => l.status === "near").length;
  byId("planHint").textContent = !lines.length ? "" : over
    ? `Перерасход в ${pl(over, ["категории", "категориях", "категориях"])}` + (near ? `, ещё ${near} близко к лимиту.` : ".")
    : near ? `${pl(near, ["категория", "категории", "категорий"])} близко к лимиту, перерасхода нет.` : "Все категории в лимите.";
  byId("goalBox").innerHTML = goal ? goalHtml(goal) : "";
  byId("budgetTable").innerHTML = !lines.length ? "" :
    `<thead><tr><th>Категория</th><th style="width:30%"></th><th class="num">Потрачено</th><th class="num">Лимит</th>` +
    (r.summary.complete ? "" : `<th class="num hide-sm">Прогноз</th>`) + `<th>Статус</th></tr></thead><tbody>` +
    lines.map(l => {
      // One scale per row up to the largest of spent, limit and forecast, so a double overspend
      // looks double; the limit is a black tick, the forecast a ring, as in the comparison table.
      const st = PLAN_STATUS[l.status], scale = Math.max(l.limit, l.spent, l.forecast || 0);
      const at = v => (v / scale * 100).toFixed(1) + "%";
      const over = l.spent > l.limit ? ` на ${zl(l.spent - l.limit)}` : "";
      return `<tr><td><span class="dot" style="background:${kindColor(l.kind)}"></span>${esc(l.label)}</td>
        <td><div class="meter"><div class="meter-fill" style="width:${at(l.spent)};background:${st.color}"></div>
          <div class="meter-limit" style="left:${at(l.limit)}" title="Лимит"></div>
          ${l.forecast !== null && l.forecast > l.spent ? `<div class="meter-forecast" style="left:${at(l.forecast)}" title="Прогноз"></div>` : ""}</div></td>
        <td class="num"><b>${zl(l.spent)}</b></td><td class="num">${zl(l.limit)}</td>
        ${r.summary.complete ? "" : `<td class="num hide-sm">${zl(l.forecast)}</td>`}
        <td><span class="plan-status" style="color:${st.color}">${st.icon} ${st.text}${over}</span></td></tr>`;
    }).join("") + "</tbody>";
}

function goalHtml(g) {
  const head = `<b>Цель: отложить ${zl(g.target)} в месяц.</b> `;
  let text;
  if (g.complete) {
    text = g.met
      ? `<span class="delta good">✓ Выполнена: отложено ${zl(g.net)}</span>`
      : `<span class="delta bad">✕ Не выполнена: ${g.net >= 0 ? `отложено ${zl(g.net)}, не хватило ${zl(g.target - g.net)}` : `месяц в минусе на ${zl(-g.net)}`}</span>`;
  } else if (g.left_to_spend >= 0) {
    text = `До конца месяца можно потратить ещё <b>${zl(g.left_to_spend)}</b> — примерно <b>${zl(g.per_day)} в день</b> (${pl(g.days_left, ["день", "дня", "дней"])}).` +
      ` <span class="llm-meta">Расчёт по ожидаемому доходу ${zl(g.expected_income)}.</span>`;
  } else {
    text = `<span class="delta bad">✕ В этом месяце цель уже не выполнить: не хватает ${zl(-g.left_to_spend)}.</span>`;
  }
  return `<p class="goal">${head}${text}</p>`;
}

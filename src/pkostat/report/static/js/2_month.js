// The month's verdict, shares, leaks and wins, category comparison.

function renderVerdict(r) {
  const s = r.summary, prev = r.previous;
  byId("periodTitle").textContent = title(current);
  const base = r.baseline_months.slice().reverse().map(shortM).join(", ");
  byId("periodSub").textContent = s.complete
    ? (prev ? `Сравнение с ${MONTH_INSTR[mi(prev.month)]}` : "Сравнение") + (base ? ` и со средним за ${base}.` : ".")
    : `Месяц ещё идёт: данные по ${D.data_until}. Сравнивай осторожно.`;
  byId("headline").textContent = s.net >= 0
    ? `${cap(inMonth(current))} удалось отложить ${zl(s.net)}${s.savings_rate !== null ? ` — ${Math.round(s.savings_rate * 100)}% дохода` : ""}.`
    : `${cap(inMonth(current))} расходы превысили доход на ${zl(-s.net)}.`;
  const diff = prev ? s.net - prev.net : 0;
  byId("headlineDelta").innerHTML = !prev ? "" : Math.abs(diff) < 10000
    ? `<span class="delta flat">● примерно как ${inMonth(prev.month)}</span>`
    : `<span class="delta ${diff > 0 ? "good" : "bad"}">${diff > 0 ? "▲" : "▼"} на ${zl(Math.abs(diff))} ${diff > 0 ? "лучше" : "хуже"}, чем ${inMonth(prev.month)}</span>`;
  const delta = (d, upIsGood) => !prev ? "" : Math.abs(d) < 10000 ? `<span class="delta flat">● как в прошлом месяце</span>`
    : `<span class="delta ${(d > 0) === upIsGood ? "good" : "bad"}">${d > 0 ? "▲" : "▼"} ${zl(Math.abs(d))} к прошлому месяцу</span>`;
  const impulse = s.by_kind.impulse || 0;
  const tile = (name, value, note) => `<div class="tile"><div class="label">${name}</div><div class="value">${value}</div><div class="note">${note}</div></div>`;
  byId("tiles").innerHTML =
    tile("Доход", zl(s.income), delta(s.income - (prev ? prev.income : 0), true)) +
    tile("Расходы", zl(s.spend), delta(s.spend - (prev ? prev.spend : 0), false)) +
    tile("Норма сбережений", s.savings_rate === null ? "—" : Math.round(s.savings_rate * 100) + "%",
      s.savings_rate === null ? "" : s.savings_rate < 0.1 ? `<span class="delta bad">▼ ниже 10%</span>` : `<span class="delta good">▲ 10% и выше</span>`) +
    tile("Импульсивные траты", zl(impulse), `<span class="delta flat">${Math.round(impulse / Math.max(s.spend, 1) * 100)}% всех расходов</span>`);
  // Built by code from the month's numbers (pkostat.analytics.story), not by the LLM.
  byId("llmSummary").textContent = r.story ? r.story.summary : "";
}

function renderShare(r) {
  const s = r.summary, total = r.share.reduce((a, p) => a + p.total, 0) || 1;
  const parts = r.share.map((p, i) => ({ ...p, color: p.category ? css("--s" + (i + 1)) : css("--neutral-mark") }));
  const el = byId("donut"); el.innerHTML = "";
  const size = 200, R = 92, inner = 58, c = size / 2;
  const svg = svgEl("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img", "aria-label": "Доли расходов по категориям" }, el);
  svg.style.width = size + "px";
  let a0 = -Math.PI / 2;
  for (const p of parts) {
    const a1 = a0 + p.total / total * Math.PI * 2, s0 = a0 + 0.01, s1 = Math.max(s0 + 0.001, a1 - 0.01), large = s1 - s0 > Math.PI ? 1 : 0;
    const pt = (rad, ang) => `${c + rad * Math.cos(ang)},${c + rad * Math.sin(ang)}`;
    const path = svgEl("path", { d: `M${pt(R, s0)}A${R},${R} 0 ${large} 1 ${pt(R, s1)}L${pt(inner, s1)}A${inner},${inner} 0 ${large} 0 ${pt(inner, s0)}Z`, fill: p.color }, svg);
    hover(path, p.label, [["Сумма", zl(p.total)], ["Доля", Math.round(p.total / total * 100) + "%"]]);
    a0 = a1;
  }
  svgEl("text", { x: c, y: c - 2, "text-anchor": "middle", class: "ink", style: "font-size:18px;font-weight:650" }, svg).textContent = zl(s.spend);
  svgEl("text", { x: c, y: c + 18, "text-anchor": "middle" }, svg).textContent = "расходы";
  byId("donutList").innerHTML = parts.map(p => `<li><span class="sw" style="background:${p.color}"></span><span>${esc(p.label)}</span><span class="pct">${Math.round(p.total / total * 100)}%</span><span class="amt">${zl(p.total)}</span></li>`).join("");

  const other = Math.max(0, (s.by_kind.other || 0) + (s.by_kind.uncategorised || 0));
  const blocks = [...KINDS.map(k => [kindColor(k), Math.max(0, s.by_kind[k] || 0), k === "impulse" ? "#0b0b0b" : "#fff"]), [css("--neutral-mark"), other, "#0b0b0b"]].filter(b => b[1] > 0);
  const sum = blocks.reduce((a, b) => a + b[1], 0) || 1;
  byId("segbar").innerHTML = blocks.map(([color, v, ink]) => `<div style="background:${color};flex:${v} 1 0;color:${ink}">${v / sum >= 0.08 ? Math.round(v / sum * 100) + "%" : ""}</div>`).join("");
  byId("segLegend").innerHTML = legendHtml([...KINDS.map(k => [KIND_RU[k], { css: `background:${kindColor(k)}` }]), ["Прочее / без категории", { css: `background:${css("--neutral-mark")}` }]]);
  byId("splitNotes").innerHTML = KINDS.map(k => `<div><b>${zl(s.by_kind[k] || 0)}</b>${KIND_RU[k].toLowerCase()}</div>`).join("") +
    `<div style="grid-column:1/-1">Отдельно, не в расходах: переводы людям ${zl(s.to_people)}.</div>`;
}

function findingHtml(f) {
  const why = f.headline
    ? `Всё ещё главная импульсивная категория: ${Math.round(f.now / Math.max(SERIES[current].spend, 1) * 100)}% всех расходов, ${pl(f.payments, PAY)}. ` +
      (f.change === null ? "" : f.change < 0 ? `На ${pct(f.change).slice(1)} меньше среднего — это прогресс.` : `${pct(f.change)} к среднему.`)
    : (f.change === null ? "Новое в этом месяце." : `${pct(f.change)} к среднему ${zl(f.average)}.`) + (f.payments ? ` ${pl(f.payments, PAY)}.` : "");
  const top = f.top_merchants.length ? " В основном " + f.top_merchants.map(m => `${m.merchant} (${zl(m.total)}${m.count > 1 ? ", " + m.count + "×" : ""})`).join(", ") + "." : "";
  return `<div class="finding"><div class="name"><span class="dot" style="background:${kindColor(f.kind)}"></span>${esc(f.label)}</div><div class="amount">${zl(f.now)}</div>
    <div class="why">${esc(why + top)}</div><div class="spark chart" data-spark="${esc(f.category)}"></div></div>`;
}

function renderFindings(r) {
  byId("leaks").innerHTML = r.leaks.length ? r.leaks.map(findingHtml).join("") : `<p class="empty">Ничего заметно не выросло. Хороший месяц.</p>`;
  byId("wins").innerHTML = r.wins.length ? r.wins.map(findingHtml).join("") : `<p class="empty">Ничего заметно не снизилось.</p>`;
  for (const el of document.querySelectorAll("[data-spark]")) sparkline(el, el.dataset.spark);
}

function sparkline(el, category) {
  const points = MONTHS.filter(m => m <= current).slice(-10).map(m => ({ m, v: Math.max(0, SERIES[m].by_category[category] || 0) }));
  const w = el.clientWidth || 300, h = 36, max = Math.max(...points.map(p => p.v), 1), bw = w / points.length;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img", "aria-label": `${label(category)} по месяцам` }, el);
  points.forEach((p, i) => {
    const bh = Math.max(1, p.v / max * (h - 4));
    svgEl("path", { d: colBar(i * bw + 1, h - bh, Math.max(2, bw - 2), bh, 3), fill: p.m === current ? kindColor(catKind(category)) : css("--neutral-mark") }, svg);
    hover(svgEl("rect", { x: i * bw, y: 0, width: bw, height: h, fill: "transparent" }, svg), `${label(category)} · ${title(p.m)}`, [["Потрачено", zl(p.v)]]);
  });
}

function renderComparison(r) {
  const prev = r.previous ? r.previous.month : null;
  byId("cmpHint").textContent = `Столбец — ${MONTH_NOM[mi(current)]}` + (prev ? `, кружок — ${MONTH_NOM[mi(prev)]}` : "") + ", чёрная черта — среднее за 3 месяца. Клик по строке — мерчанты категории.";
  byId("cmpLegend").innerHTML = legendHtml([...KINDS.map(k => [KIND_RU[k], { css: `background:${kindColor(k)}` }]), ["Прошлый месяц", { css: "border:2px solid var(--ink);border-radius:50%;width:9px;height:9px" }], ["Среднее за 3 мес.", { cls: "tick" }]]);
  const rows = r.categories, max = Math.max(...rows.map(x => Math.max(x.now, x.average, x.previous)), 1);
  const w = v => (v / max * 100).toFixed(2) + "%";
  const d = x => { const v = x.now - x.average; return Math.abs(v) < 1000 ? `<span class="delta flat">≈</span>` : `<span class="${v > 0 ? "up" : "down"}">${v > 0 ? "▲" : "▼"} ${zl(Math.abs(v))}</span>`; };
  const table = byId("cmpTable");
  table.innerHTML = `<thead><tr><th>Категория</th><th style="width:30%"></th><th class="num">${cap(shortM(current))}</th><th class="num hide-sm">${prev ? cap(shortM(prev)) : "—"}</th><th class="num hide-sm">Среднее</th><th class="num">К среднему</th><th class="num hide-sm">Платежей</th><th class="num hide-sm">Ср. чек</th></tr></thead><tbody>` +
    rows.map((x, i) => `<tr class="cmp" data-i="${i}"><td><span class="dot" style="background:${kindColor(x.kind)}"></span>${esc(x.label)}</td>
      <td><div class="barcell"><div class="bar" style="width:${w(x.now)};background:${kindColor(x.kind)}"></div>${x.average ? `<div class="avg" style="left:${w(x.average)}"></div>` : ""}${x.previous ? `<div class="prev" style="left:${w(x.previous)}"></div>` : ""}</div></td>
      <td class="num"><b>${zl(x.now)}</b></td><td class="num hide-sm">${zl(x.previous)}</td><td class="num hide-sm">${zl(x.average)}</td><td class="num">${d(x)}</td>
      <td class="num hide-sm">${x.payments}</td><td class="num hide-sm">${x.payments ? zl(x.now / x.payments) : "—"}</td></tr>`).join("") + "</tbody>";
  table.onclick = e => {
    const tr = e.target.closest("tr.cmp"); if (!tr) return;
    if (tr.nextElementSibling && tr.nextElementSibling.classList.contains("cmp-detail")) { tr.nextElementSibling.remove(); return; }
    const x = rows[Number(tr.dataset.i)], row = document.createElement("tr");
    row.className = "cmp-detail";
    row.innerHTML = `<td colspan="8">${x.top_merchants.length ? x.top_merchants.map(m => `${esc(m.merchant)} — <b>${zl(m.total)}</b> (${m.count}×)`).join(" · ") : "В этом месяце платежей не было."}</td>`;
    tr.after(row);
  };
}

// Charts across months: heatmap, spending and income, net, pace, weekdays.

const SPEND_KINDS = new Set(["essential", "discretionary", "impulse", "other", "uncategorised"]);

function renderHeatmap() {
  const names = [...new Set(D.series.flatMap(s => Object.keys(s.by_category)))]
    .filter(c => SPEND_KINDS.has(catKind(c)) && MONTHS.some(m => (SERIES[m].by_category[c] || 0) >= 1000))
    .sort((a, b) => MONTHS.reduce((t, m) => t + (SERIES[m].by_category[b] || 0), 0) - MONTHS.reduce((t, m) => t + (SERIES[m].by_category[a] || 0), 0));
  const steps = [1, 2, 3, 4, 5].map(i => css("--h" + i));
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const cell = (v, max, sel) => {
    if (v < 100) return `<td class="cell ${sel ? "sel-col" : ""}" style="color:var(--muted)">·</td>`;
    const idx = Math.min(4, Math.floor(v / max * 4.999)), ink = (dark ? idx <= 2 : idx >= 3) ? "#fff" : "#0b0b0b";
    return `<td class="cell ${sel ? "sel-col" : ""}" style="background:${steps[idx]};color:${ink}">${kz(v)}</td>`;
  };
  const head = `<thead><tr><th></th>${MONTHS.map(m => `<th class="month ${m === current ? "sel" : ""}" data-m="${m}">${cap(shortM(m))}</th>`).join("")}</tr></thead>`;
  const body = names.map(c => {
    const vals = MONTHS.map(m => Math.max(0, SERIES[m].by_category[c] || 0)), max = Math.max(...vals, 1);
    return `<tr><td class="cat"><span class="dot" style="background:${kindColor(catKind(c))}"></span>${esc(label(c))}</td>${vals.map((v, i) => cell(v, max, MONTHS[i] === current)).join("")}</tr>`;
  }).join("");
  const line = (name, f, color) => `<tr class="total"><td class="cat">${name}</td>${MONTHS.map(m => { const v = f(SERIES[m]); return `<td class="${m === current ? "sel-col" : ""}" style="${color ? `color:${color(v)}` : ""}">${v < 0 ? "−" : ""}${kz(v)}</td>`; }).join("")}</tr>`;
  byId("heat").innerHTML = head + `<tbody>${body}` + line("Всего расходов", s => s.spend) + line("Доход", s => s.income) +
    line("Сальдо", s => s.net, v => (v >= 0 ? "var(--good-text)" : "var(--bad-text)")) + "</tbody>";
  document.querySelectorAll("#heat th.month").forEach(th => { th.onclick = () => openMonth(th.dataset.m); });
}

function renderTrend() {
  const el = byId("trendChart"); el.innerHTML = "";
  byId("trendLegend").innerHTML = legendHtml([...KINDS.map(k => [KIND_RU[k], { css: `background:${kindColor(k)}` }]), ["Прочее", { css: `background:${css("--neutral-mark")}` }], ["Доход", { cls: "line" }]]);
  const w = el.clientWidth, h = 240, left = 40, top = 8, plotH = h - top - 22, plotW = w - left;
  const max = Math.ceil(Math.max(...D.series.map(s => Math.max(s.spend, s.income)), 1) / 500000) * 500000;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img", "aria-label": "Расходы по типам и доход по месяцам" }, el);
  const y = axis(svg, w, left, top, plotH, max, 500000, v => v / 100000 + "к");
  const slot = plotW / D.series.length, bw = Math.min(30, slot * 0.62), pts = [];
  D.series.forEach((s, i) => {
    const x = left + i * slot + (slot - bw) / 2, g = svgEl("g", { opacity: s.month === current ? 1 : 0.5 }, svg);
    const parts = [...KINDS.map(k => [k, Math.max(0, s.by_kind[k] || 0)]), ["other", Math.max(0, (s.by_kind.other || 0) + (s.by_kind.uncategorised || 0))]].filter(p => p[1] > 0);
    let acc = 0;
    parts.forEach(([k, v], j) => {
      const y0 = y(acc), y1 = y(acc + v), last = j === parts.length - 1, hh = Math.max(0, y0 - y1 - (last ? 0 : 2));
      svgEl("path", { d: last ? colBar(x, y1, bw, hh, 4) : `M${x},${y1 + 2}h${bw}v${hh}h${-bw}Z`, fill: kindColor(k) }, g);
      acc += v;
    });
    svgEl("text", { x: x + bw / 2, y: h - 6, "text-anchor": "middle", style: s.month === current ? "fill:var(--ink);font-weight:600" : "" }, svg).textContent = monthLabel(s.month, slot);
    if (s.income > 0) pts.push([x + bw / 2, y(s.income)]);
    const hit = svgEl("rect", { x: left + i * slot, y: top, width: slot, height: plotH, fill: "transparent", style: "cursor:pointer" }, svg);
    hover(hit, title(s.month) + (s.complete ? "" : " (идёт)"), [["Доход", zl(s.income)], ["Расходы", zl(s.spend)], ...KINDS.map(k => [KIND_RU[k], zl(s.by_kind[k] || 0)])]);
    hit.onclick = () => openMonth(s.month);
  });
  if (pts.length > 1) svgEl("path", { d: "M" + pts.map(p => p.join(",")).join("L"), fill: "none", stroke: css("--ink"), "stroke-width": 2, "stroke-linejoin": "round" }, svg);
  pts.forEach(([cx, cy]) => svgEl("circle", { cx, cy, r: 4, fill: css("--ink"), stroke: css("--surface"), "stroke-width": 2 }, svg));
}

function renderNet() {
  const el = byId("netChart"); el.innerHTML = "";
  const done = D.series.filter(s => s.complete);
  const w = el.clientWidth, h = 274, left = 40, top = 16, plotH = h - top - 22, plotW = w - left;
  const biggest = Math.max(...done.map(s => Math.abs(s.net)), 1), lim = Math.ceil(biggest / 200000) * 200000;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img", "aria-label": "Сальдо по месяцам" }, el);
  const y = axis(svg, w, left, top, plotH, lim, 200000, v => (v < 0 ? "−" : "") + Math.abs(v) / 100000 + "к", -lim);
  const slot = plotW / D.series.length, bw = Math.min(30, slot * 0.62);
  D.series.forEach((s, i) => {
    const x = left + i * slot + (slot - bw) / 2, y0 = y(0), sel = s.month === current;
    if (!s.complete) svgEl("text", { x: x + bw / 2, y: y0 - 6, "text-anchor": "middle", class: "ink2" }, svg).textContent = "идёт";
    else {
      const yv = y(s.net);
      svgEl("path", { d: s.net >= 0 ? colBar(x, yv, bw, y0 - yv, 4) : colBarDown(x, y0, bw, yv - y0, 4), fill: s.net >= 0 ? css("--pos") : css("--neg"), opacity: sel ? 1 : 0.55 }, svg);
      if (sel || Math.abs(s.net) === biggest) svgEl("text", { x: x + bw / 2, y: s.net >= 0 ? yv - 5 : yv + 14, "text-anchor": "middle", class: "ink2" }, svg).textContent = (s.net < 0 ? "−" : "+") + kz(s.net);
    }
    svgEl("text", { x: x + bw / 2, y: h - 6, "text-anchor": "middle", style: sel ? "fill:var(--ink);font-weight:600" : "" }, svg).textContent = monthLabel(s.month, slot);
    const hit = svgEl("rect", { x: left + i * slot, y: top, width: slot, height: plotH, fill: "transparent", style: "cursor:pointer" }, svg);
    hover(hit, title(s.month), [["Доход", zl(s.income)], ["Расходы", zl(s.spend)], ["Переводы (сальдо)", zl(s.transfers)], ["Итог", (s.net >= 0 ? "+" : "") + zl(s.net)]]);
    hit.onclick = () => openMonth(s.month);
  });
}

function renderPace(r) {
  const el = byId("paceChart"); el.innerHTML = "";
  const p = r.pace, series = [
    { name: cap(MONTH_NOM[mi(current)]), vals: p.current, color: css("--s1"), w: 2.5 },
    ...(r.previous ? [{ name: cap(MONTH_NOM[mi(r.previous.month)]), vals: p.previous, color: css("--s2"), w: 2 }] : []),
    ...(r.baseline_months.length ? [{ name: "Среднее за 3 мес.", vals: p.average, color: css("--muted"), w: 2 }] : []),
  ];
  byId("paceLegend").innerHTML = legendHtml(series.map(s => [s.name, { cls: "line", css: `background:${s.color}` }]));
  const w = el.clientWidth, h = 240, left = 40, top = 8, plotH = h - top - 22, plotW = w - left - 8;
  const step = niceStep(Math.max(...series.flatMap(s => s.vals), 1) / 4), max = Math.ceil(Math.max(...series.flatMap(s => s.vals), 1) / step) * step;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img", "aria-label": "Накопленные расходы по дням месяца" }, el);
  const y = axis(svg, w, left, top, plotH, max, step, v => kz(v));
  const x = d => left + d / 30 * plotW;
  for (const d of [1, 5, 10, 15, 20, 25, 30]) svgEl("text", { x: x(d - 1), y: h - 6, "text-anchor": "middle" }, svg).textContent = d;
  for (const s of series.slice().reverse()) if (s.vals.length) svgEl("path", { d: "M" + s.vals.map((v, i) => `${x(i)},${y(v)}`).join("L"), fill: "none", stroke: s.color, "stroke-width": s.w, "stroke-linejoin": "round" }, svg);
  const cross = svgEl("line", { y1: top, y2: top + plotH, stroke: css("--axis"), "stroke-width": 1, visibility: "hidden" }, svg);
  const hit = svgEl("rect", { x: left, y: top, width: plotW, height: plotH, fill: "transparent" }, svg);
  hit.addEventListener("mousemove", e => {
    const box = svg.getBoundingClientRect(), d = Math.max(0, Math.min(30, Math.round((e.clientX - box.left - left) / plotW * 30)));
    cross.setAttribute("x1", x(d)); cross.setAttribute("x2", x(d)); cross.setAttribute("visibility", "visible");
    showTip(e, `${d + 1}-е число`, series.filter(s => s.vals[d] !== undefined).map(s => [s.name, zl(s.vals[d])]));
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
}

function renderWeekdays(r) {
  const el = byId("weekChart"); el.innerHTML = "";
  const avg = r.weekdays.average_per_day, worst = avg.indexOf(Math.max(...avg));
  byId("weekHint").textContent = `Импульсивные траты в среднем за день недели, ${r.weekdays.months.slice().reverse().map(shortM).join("–")}. Хуже всего — ${WEEKDAYS_LONG[worst]}.`;
  const w = el.clientWidth, h = 240, left = 40, top = 16, plotH = h - top - 22, plotW = w - left;
  const step = niceStep(Math.max(...avg, 1) / 4), max = Math.ceil(Math.max(...avg, 1) / step) * step;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, height: h, role: "img", "aria-label": "Импульсивные траты по дням недели" }, el);
  const y = axis(svg, w, left, top, plotH, max, step, v => Math.round(v / 100) + "");
  const slot = plotW / 7, bw = Math.min(40, slot * 0.6);
  avg.forEach((v, i) => {
    const x = left + i * slot + (slot - bw) / 2;
    svgEl("path", { d: colBar(x, y(v), bw, y(0) - y(v), 4), fill: i === worst ? css("--impulse") : css("--neutral-mark") }, svg);
    svgEl("text", { x: x + bw / 2, y: y(v) - 5, "text-anchor": "middle", class: "ink2" }, svg).textContent = zl(v);
    svgEl("text", { x: x + bw / 2, y: h - 6, "text-anchor": "middle" }, svg).textContent = WEEKDAYS[i];
    hover(svgEl("rect", { x: left + i * slot, y: top, width: slot, height: plotH, fill: "transparent" }, svg), WEEKDAYS_LONG[i], [["В среднем за день", zl(v)], ["Всего за период", zl(r.weekdays.totals[i])]]);
  });
}

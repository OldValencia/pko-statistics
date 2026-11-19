// Transactions page, navigation and start-up.

function renderReport() {
  const r = D.reports[current];
  renderVerdict(r);
  renderPlan(r);
  renderShare(r);
  renderFindings(r);
  renderComparison(r);
  renderHeatmap();
  renderTrend();
  renderNet();
  renderPace(r);
  renderWeekdays(r);
  renderTopMerchants(r);
  renderRecurring();
  renderRecs(r);
  renderWhatIf();
  renderYtd();
  renderNotes(r);
}

function openMonth(m) {
  current = m;
  renderReport();
  scrollTo({ top: 0, behavior: "smooth" });
}

const STATUS = { settled: "проведена", pending: "ещё не проведена", superseded: "заменена выпиской", unmatched: "не провелась" };

function renderTransactions() {
  const fMonth = byId("fMonth"), fCat = byId("fCategory");
  if (!fMonth.options.length) {
    fMonth.innerHTML = `<option value="">Все месяцы</option>` + MONTHS.slice().reverse().map(m => `<option value="${m}">${title(m)}</option>`).join("");
    fMonth.value = current;
    fCat.innerHTML = `<option value="">Все категории</option><option value="__none">Без категории</option>` + D.categories.map(c => `<option value="${esc(c.name)}">${esc(c.label)}</option>`).join("");
  }
  const q = byId("fSearch").value.toLowerCase(), all = byId("fStatus").value === "all";
  const list = D.transactions.filter(t =>
    (!fMonth.value || t.month === fMonth.value) &&
    (!fCat.value || (fCat.value === "__none" ? !t.category : t.category === fCat.value)) &&
    (all || COUNTED.has(t.status)) &&
    (!q || (t.merchant + " " + t.raw + " " + t.title).toLowerCase().includes(q))
  ).sort((a, b) => b.date.localeCompare(a.date));
  const total = list.filter(t => COUNTED.has(t.status)).reduce((a, t) => a + t.amount, 0);
  byId("txSummary").textContent = `${pl(list.length, OPS)} · итого ${total >= 0 ? "+" : ""}${zl(total, 2)}` + (list.length > 500 ? " · показаны первые 500" : "");
  const options = c => `<option value="">— выбрать —</option>` + D.categories.map(x => `<option value="${esc(x.name)}"${x.name === c ? " selected" : ""}>${esc(x.label)}</option>`).join("");
  byId("txBody").innerHTML = list.slice(0, 500).map(t => `<tr class="${t.category ? "" : "uncat"}" style="${COUNTED.has(t.status) ? "" : "opacity:.5"}">
    <td>${t.date}<span class="small">${t.source === "notification" ? "пуш" : "выписка"}</span></td>
    <td>${esc(t.merchant || t.raw)}<span class="small">${esc(t.title && t.type.startsWith("transfer") ? t.title : t.raw)}</span></td>
    <td>${MODE === "admin" ? `<select data-tx="${t.id}" data-merchant="${esc(t.merchant)}">${options(t.category)}</select>${typeof switchButton === "function" ? switchButton(t) : ""}<div class="apply-all" data-for="${t.id}"></div>` : esc(label(t.category))}</td>
    <td class="num" style="${t.amount > 0 ? "color:var(--good-text)" : ""}">${t.amount > 0 ? "+" : ""}${zl(t.amount, 2)}</td>
    <td class="hide-sm"><span class="badge ${t.status === "pending" ? "pending" : ""}">${STATUS[t.status]}</span></td></tr>`).join("");
}

function toast(text) {
  const t = byId("toast");
  t.textContent = text;
  t.style.display = "block";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.style.display = "none"; }, 2600);
}

function go(page, filter) {
  for (const p of ["report", "transactions", "admin"]) { const el = byId("page-" + p); if (el) el.hidden = p !== page; }
  for (const b of document.querySelectorAll(".nav button")) b.removeAttribute("aria-current");
  const btn = filter
    ? document.querySelector(`.nav [data-filter="${filter}"], .nav [data-admin="${filter}"]`)
    : document.querySelector(`.nav [data-page="${page}"]:not([data-filter]):not([data-admin])`);
  if (btn) btn.setAttribute("aria-current", "page");
  if (page === "transactions") {
    renderTransactions();
    byId("fCategory").value = filter === "uncategorised" ? "__none" : "";
    if (filter === "uncategorised") byId("fMonth").value = "";
    renderTransactions();
  } else if (page === "admin" && typeof renderAdmin === "function") renderAdmin(filter);
  else if (page === "report") renderReport();
  scrollTo(0, 0);
}

document.querySelector(".nav").addEventListener("click", e => {
  const b = e.target.closest("button[data-page]");
  if (b) go(b.dataset.page, b.dataset.filter || b.dataset.admin);
});
document.addEventListener("click", e => {
  if (e.target.matches("[data-goto-uncat]")) { e.preventDefault(); go("transactions", "uncategorised"); }
});
for (const id of ["fMonth", "fCategory", "fStatus", "fSearch"]) byId(id).addEventListener("input", renderTransactions);
byId("prevMonth").onclick = () => { const i = MONTHS.indexOf(current); if (i > 0) { current = MONTHS[i - 1]; renderReport(); } };
byId("nextMonth").onclick = () => { const i = MONTHS.indexOf(current); if (i < MONTHS.length - 1) { current = MONTHS[i + 1]; renderReport(); } };
const uncat = byId("uncatCount");
if (uncat) {
  const count = D.transactions.filter(t => COUNTED.has(t.status) && !t.category).length;
  uncat.textContent = count;
  uncat.hidden = count === 0;
}
let resizeTimer;
addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (!byId("page-report").hidden) renderReport(); }, 150); });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (!byId("page-report").hidden) renderReport(); });
if (MONTHS.length) renderReport();
// In admin mode the admin scripts come later and handle start-up themselves (9_start.js).
if (MODE !== "admin" && location.hash === "#transactions") go("transactions");

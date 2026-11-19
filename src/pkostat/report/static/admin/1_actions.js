// Admin only (never in the published page): talking to the local app's API.
const ADMIN = PAYLOAD.admin || {};
const VIEW_KEY = "pkostat-view", FLASH_KEY = "pkostat-flash";

async function api(path, body, raw) {
  const headers = { "X-PkoStat": "1" };
  if (raw) Object.assign(headers, { "Content-Type": "application/octet-stream" }, raw.headers || {});
  else headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method: "POST", headers, body: raw ? body : JSON.stringify(body || {}) });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}

// Every change rebuilds transactions on the server; the page reloads and comes back to the same
// place (page, filters, month, scroll) with a short message.
function rememberView() {
  const page = ["report", "transactions", "admin"].find(p => byId("page-" + p) && !byId("page-" + p).hidden);
  const current_nav = document.querySelector(".nav [aria-current]");
  try {
    sessionStorage.setItem(VIEW_KEY, JSON.stringify({
      page, filter: current_nav ? current_nav.dataset.filter || current_nav.dataset.admin : null, month: current,
      fMonth: byId("fMonth").value, fCategory: byId("fCategory").value, fSearch: byId("fSearch").value, scroll: scrollY,
    }));
  } catch (e) { /* private mode: the page simply opens at the top */ }
}

async function act(promise, button) {
  if (button) button.disabled = true;
  try {
    const result = await promise;
    rememberView();
    try { sessionStorage.setItem(FLASH_KEY, result.message || "Готово."); } catch (e) { /* ignore */ }
    location.reload();
  } catch (e) {
    if (button) button.disabled = false;
    toast("Ошибка: " + e.message);
  }
}

function restoreView() {
  let view = null, flash = null;
  try {
    view = JSON.parse(sessionStorage.getItem(VIEW_KEY) || "null");
    flash = sessionStorage.getItem(FLASH_KEY);
    sessionStorage.removeItem(VIEW_KEY);
    sessionStorage.removeItem(FLASH_KEY);
  } catch (e) { /* ignore */ }
  if (view) {
    if (view.month && MONTHS.includes(view.month)) current = view.month;
    if (view.page === "transactions") {
      go("transactions", view.filter);
      byId("fMonth").value = view.fMonth; byId("fCategory").value = view.fCategory; byId("fSearch").value = view.fSearch;
      renderTransactions();
    } else if (view.page) go(view.page, view.filter);
    scrollTo(0, view.scroll || 0);
  }
  if (flash) toast(flash);
}

// Category of an operation: this one only, or every operation of the merchant.
byId("txBody").addEventListener("change", e => {
  const sel = e.target.closest("select[data-tx]");
  if (!sel) return;
  const merchant = sel.dataset.merchant, category = sel.value || null;
  const same = D.transactions.filter(t => t.merchant === merchant && COUNTED.has(t.status)).length;
  const box = document.querySelector(`.apply-all[data-for="${sel.dataset.tx}"]`);
  box.innerHTML = `<button data-scope="one">Только эту</button>` +
    (merchant && category ? `<button data-scope="all">Все ${same} от ${esc(merchant)}</button>` : "") +
    `<button data-scope="cancel">Отмена</button>`;
  box.style.display = "block";
  box.onclick = ev => {
    const scope = ev.target.dataset.scope;
    if (!scope) return;
    if (scope === "cancel") { box.style.display = "none"; renderTransactions(); return; }
    act(scope === "all"
      ? api("/api/merchants/category", { merchant, category })
      : api(`/api/transactions/${encodeURIComponent(sel.dataset.tx)}/category`, { category }), ev.target);
  };
});

const userSwitch = byId("userSwitch");
if (userSwitch) userSwitch.onchange = () => { location.href = "/?user=" + encodeURIComponent(userSwitch.value); };
if (!MONTHS.length) {
  byId("page-report").innerHTML = `<div class="periodbar"><h1>Данных пока нет</h1></div>
    <p class="sub">Загрузи выписку на странице «Данные» или синхронизируй пуши.</p>`;
}

// The LLM suggestion button on the uncategorised page: up to a minute, then the page reloads with
// the suggestions pre-selected for the owner to check.
document.addEventListener("click", e => {
  const b = e.target.closest("button[data-llm]");
  if (!b) return;
  b.textContent = "LLM думает… это может занять минуту";
  act(api("/api/llm/suggest"), b);
});

// One-tap switch for merchants with two usual categories (Wolt: food or groceries). Saved as an
// override of that single operation; the row updates in place, the rest of the page on reload.
function switchButton(t) {
  const pair = (ADMIN.alternatives || {})[t.merchant];
  if (!pair || !COUNTED.has(t.status)) return "";
  const target = t.category === pair.alt ? pair.main : pair.alt;
  return ` <button class="switch-btn" data-switch="${t.id}" data-target="${esc(target)}" title="Только эта операция">→ ${esc(label(target))}</button>`;
}

byId("txBody").addEventListener("click", async e => {
  const b = e.target.closest("button[data-switch]");
  if (!b) return;
  const t = D.transactions.find(x => x.id === b.dataset.switch), pair = ADMIN.alternatives[t.merchant];
  const target = b.dataset.target;
  b.disabled = true;
  try {
    // Back to the merchant's main category = no override at all.
    await api(`/api/transactions/${encodeURIComponent(t.id)}/category`, { category: target === pair.main ? null : target });
    t.category = target;
    renderTransactions();
    toast(`${t.merchant} ${t.date}: ${label(target)}`);
  } catch (err) {
    b.disabled = false;
    toast("Ошибка: " + err.message);
  }
});

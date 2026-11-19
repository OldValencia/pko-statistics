// Admin pages: uncategorised merchants, categories, data, users.
const KIND_NAMES = { essential: "Необходимое", discretionary: "По желанию", impulse: "Импульсивное", income: "Доход", transfer: "Переводы", other: "Прочее" };
const ADMIN_TITLES = { uncategorised: "Без категории", budgets: "Бюджеты", categories: "Категории", data: "Данные", users: "Пользователи" };
const categoryOptions = (selected, empty = "— выбрать —") => `<option value="">${empty}</option>` +
  D.categories.map(c => `<option value="${esc(c.name)}"${c.name === selected ? " selected" : ""}>${esc(c.label)}</option>`).join("");

function renderAdmin(page) {
  byId("adminTitle").textContent = ADMIN_TITLES[page] || "";
  const body = byId("adminBody");
  body.innerHTML = ({ uncategorised: uncategorisedHtml, budgets: () => budgetsHtml(), categories: categoriesHtml, data: dataHtml, users: usersHtml }[page] || (() => ""))();
  body.onclick = e => adminClick(e, body);

}

function uncategorisedHtml() {
  const groups = {}, hints = ADMIN.suggestions || {};
  for (const t of D.transactions) {
    if (!COUNTED.has(t.status) || t.category) continue;
    const g = groups[t.merchant] || (groups[t.merchant] = { merchant: t.merchant, raw: new Set(), n: 0, total: 0, last: "" });
    g.raw.add(t.raw); g.n += 1; g.total += t.amount; if (t.date > g.last) g.last = t.date;
  }
  const list = Object.values(groups).sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  if (!list.length) return `<p>У всех операций есть категория.</p>`;
  const hint = g => {
    const h = hints[g.merchant];
    if (!h) return "";
    const sure = h.confidence >= 0.6 && h.category !== "Other";
    return `<span class="small">LLM: ${esc(label(h.category))} · ${sure ? "уверена" : "не уверена"} (${Math.round(h.confidence * 100)}%)</span>`;
  };
  const preselect = g => { const h = hints[g.merchant]; return h && h.confidence >= 0.6 && h.category !== "Other" ? h.category : null; };
  return `<p class="hint">Выбери категорию и сохрани — она применится ко всем операциям мерчанта, сейчас и в будущем.
      Подсказки LLM уже выбраны в списке, но ничего не сохраняется без тебя: проверь и нажми «Сохранить».</p>
    <div class="filters"><button data-llm="categorize">Подсказать с помощью LLM (${esc(ADMIN.llm_model)})</button>
      <button data-act="accept-all">Сохранить все выбранные</button></div>
    <div class="table-scroll"><table><thead><tr><th>Мерчант</th><th class="num">Сумма</th><th class="num">Раз</th><th class="hide-sm">Последняя</th><th>Категория</th><th></th></tr></thead><tbody>` +
    list.map(g => `<tr data-merchant-row="${esc(g.merchant)}"><td>${esc(g.merchant)}<span class="small">${esc([...g.raw].slice(0, 2).join(" · "))}</span></td>
      <td class="num">${zl(g.total, 2)}</td><td class="num">${g.n}</td><td class="hide-sm">${g.last}</td>
      <td><select data-merchant-choice>${categoryOptions(preselect(g))}</select>${hint(g)}</td>
      <td><button data-act="accept-one">Сохранить</button></td></tr>`).join("") + "</tbody></table></div>";
}

function categoriesHtml() {
  const kindSelect = k => `<select data-f="kind">${ADMIN.kinds.map(x => `<option value="${x}"${x === k ? " selected" : ""}>${KIND_NAMES[x] || x}</option>`).join("")}</select>`;
  const rows = ADMIN.categories.map(c => `<tr data-cat="${esc(c.name)}">
    <td><input data-f="label" value="${esc(c.label)}" maxlength="60"><span class="small">${esc(c.name)} · операций: ${c.transactions}</span></td>
    <td>${kindSelect(c.kind)}</td>
    <td class="hide-sm"><input data-f="description" value="${esc(c.description)}" style="width:100%"></td>
    <td><input data-f="shift" type="number" min="2" max="31" value="${c.month_shift_from_day || ""}" style="width:60px" title="Оплата с этого дня — за следующий месяц"></td>
    <td><button data-act="save-cat">Сохранить</button>${c.blockers.length ? "" : ` <button data-act="delete-cat">Удалить</button>`}</td></tr>`).join("");
  const rules = ADMIN.rules.length ? `<table><thead><tr><th>Мерчант</th><th>Категория</th><th>Кто задал</th><th></th></tr></thead><tbody>` +
    ADMIN.rules.map(r => `<tr><td>${esc(r.merchant)}</td><td>${esc(label(r.category))}</td><td>${r.source === "manual" ? "ты" : "LLM"}</td>
      <td><button data-act="delete-rule" data-merchant="${esc(r.merchant)}">Удалить</button></td></tr>`).join("") + "</tbody></table>"
    : `<p class="hint">Ручных правил пока нет.</p>`;
  return `<p class="hint">Название и тип можно менять в любой момент: операции пересчитаются. Внутреннее имя (мелким шрифтом) не меняется — на него ссылаются правила.</p>
    <div class="table-scroll"><table class="edit"><thead><tr><th>Название</th><th>Тип</th><th class="hide-sm">Описание (для LLM)</th><th>Сдвиг</th><th></th></tr></thead><tbody>${rows}
    <tr data-cat=""><td><input data-f="label" placeholder="Новая категория" maxlength="60"></td><td>${kindSelect("discretionary")}</td>
      <td class="hide-sm"><input data-f="description" placeholder="Что сюда входит" style="width:100%"></td><td></td><td><button data-act="save-cat">Добавить</button></td></tr>
    </tbody></table></div><h2 style="margin-top:24px">Правила мерчантов</h2><p class="hint">Какой мерчант в какую категорию — заданные тобой и (позже) локальной LLM.</p>${rules}`;
}

function dataHtml() {
  const s = ADMIN.statuses || {};
  const imports = ADMIN.imports.length ? `<table><thead><tr><th>Файл</th><th>Период</th><th class="hide-sm">Загружен</th><th class="num">Строк</th></tr></thead><tbody>` +
    ADMIN.imports.map(i => `<tr><td>${esc(i.file_name)}<span class="small">${esc(i.user_name)}</span></td><td>${i.period_from} — ${i.period_to}</td><td class="hide-sm">${i.imported_at.replace("T", " ")}</td><td class="num">${i.rows}</td></tr>`).join("") + "</tbody></table>"
    : `<p class="hint">Выписок пока нет.</p>`;
  return `<h2>Выписка из банка</h2><p class="hint">CSV «Zestawienie operacji» из iPKO. Повторная загрузка безопасна: уже известные строки пропускаются.</p>
    <div class="filters"><select id="importUser">${ADMIN.users.map(u => `<option value="${esc(u.name)}"${u.name === ADMIN.current_user ? " selected" : ""}>${esc(u.label)}</option>`).join("")}</select>
      <input type="file" id="importFile" accept=".csv,text/csv"><button data-act="import">Загрузить</button></div>
    ${imports}
    <h2 style="margin-top:24px">Пуш-уведомления</h2>
    <p class="hint">${ADMIN.supabase ? "Забрать новые уведомления из Supabase в локальную базу." : "Supabase не настроен: заполни SUPABASE_URL и SUPABASE_SECRET_KEY в .env."}</p>
    <div class="filters"><button data-act="sync"${ADMIN.supabase ? "" : " disabled"}>Синхронизировать</button><button data-act="rebuild">Пересобрать данные</button>
      <button data-act="run" title="Синк, пересборка, LLM, отчёты, резервная копия">Обновить всё</button></div>
    <ul class="notes"><li>Проведено банком: ${s.settled || 0}</li><li>Ждут выписки: ${s.pending || 0}</li><li>Заменены выпиской: ${s.superseded || 0}</li>
      <li>Не провелись: ${s.unmatched || 0}</li><li>Нераспознанных уведомлений: ${ADMIN.unparsed}</li></ul>
    <h2 style="margin-top:24px">Резервные копии</h2>
    <p class="hint">База и настройки категорий (без ключей из .env). Делаются сами раз в сутки при запуске и в «Обновить всё», хранятся 30 последних. Папка: ${esc(ADMIN.backups_dir)}. Восстановление — командой <code>pkostat restore &lt;файл&gt;</code> при закрытом приложении.</p>
    <div class="filters"><button data-act="backup">Сделать копию сейчас</button></div>
    ${ADMIN.backups.length ? `<table><thead><tr><th>Файл</th><th>Создана</th><th class="num">Размер</th></tr></thead><tbody>` +
      ADMIN.backups.map(b => `<tr><td>${esc(b.name)}</td><td>${b.created.replace("T", " ").slice(0, 16)}</td><td class="num">${Math.round(b.size / 1024)} КБ</td></tr>`).join("") + "</tbody></table>"
      : `<p class="hint">Копий пока нет.</p>`}`;
}

function usersHtml() {
  const rows = ADMIN.users.map(u => `<tr data-user="${esc(u.name)}"><td>${esc(u.name)}<span class="small">уведомлений: ${u.notifications}</span></td>
    <td><input data-f="display" value="${esc(u.display_name || "")}" placeholder="${esc(u.name)}" maxlength="64"> <button data-act="save-user">Сохранить</button></td>
    <td><code class="token" data-token="${esc(u.token)}">••••••••</code> <button data-act="show-token">Показать</button> <button data-act="copy-token">Копировать</button>
      <button data-act="rotate">Перевыпустить</button></td>
    <td>${u.share_link ? `<button data-act="copy-link" data-link="${esc(u.share_link)}">Копировать ссылку</button> <button data-act="share">Новая ссылка</button> <button data-act="unshare">Закрыть</button>`
      : u.shared ? `<button data-act="unshare">Закрыть</button>` : `<button data-act="share">Открыть доступ</button>`}</td></tr>`).join("");
  const pub = ADMIN.publish;
  return `<p class="hint">Токен — это token_id в iOS Shortcut. Перевыпуск: старый токен перестанет приниматься, Shortcut нужно обновить.</p>
    <div class="table-scroll"><table class="edit"><thead><tr><th>Имя</th><th>Отображаемое имя</th><th>Токен</th><th>Отчёт по ссылке</th></tr></thead><tbody>${rows}</tbody></table></div>
    <h2 style="margin-top:24px">Публикация</h2>
    <p class="hint">${pub.configured
      ? `Отчёты с открытым доступом публикуются зашифрованными на GitHub Pages: в «Обновить всё», в ежедневном запуске и этой кнопкой. Пароль — в самой ссылке, после первого открытия телефон его запоминает. ${pub.published_at ? "Последняя публикация: " + pub.published_at.replace("T", " ").slice(0, 16) + "." : "Ещё не публиковалось."}`
      : "Публикация выключена: укажи PKOSTAT_PUBLISH_REMOTE в .env (репозиторий для ветки gh-pages) и перезапусти приложение."}</p>
    <div class="filters"><button data-act="publish"${pub.configured ? "" : " disabled"}>Опубликовать сейчас</button></div>
    <h2 style="margin-top:24px">Новый пользователь</h2>
    <div class="filters" id="newUser"><input data-f="name" placeholder="имя латиницей, напр. anna" maxlength="32"><input data-f="display" placeholder="Отображаемое имя" maxlength="64">
      <input data-f="token" placeholder="Свой токен (необязательно)"><button data-act="add-user">Добавить</button></div>`;
}

function adminClick(e, body) {
  const b = e.target.closest("button[data-act]");
  if (!b) return;
  const row = b.closest("tr"), field = name => { const el = (row || body).querySelector(`[data-f="${name}"]`); return el ? el.value : ""; };
  const actions = {
    "save-cat": () => act(api("/api/categories", { name: row.dataset.cat || null, label: field("label"), kind: field("kind"), description: field("description"), month_shift_from_day: field("shift") ? Number(field("shift")) : null }), b),
    "delete-cat": () => confirmTwice(b, () => act(api("/api/categories/delete", { name: row.dataset.cat }), b)),
    "delete-rule": () => act(api("/api/rules/delete", { merchant: b.dataset.merchant }), b),
    "import": () => {
      const file = byId("importFile").files[0];
      if (!file) { toast("Выбери CSV-файл."); return; }
      act(file.arrayBuffer().then(buf => api("/api/import?user=" + encodeURIComponent(byId("importUser").value), buf, { headers: { "X-File-Name": encodeURIComponent(file.name) } })), b);
    },
    "accept-one": () => {
      const category = row.querySelector("select[data-merchant-choice]").value;
      if (!category) { toast("Сначала выбери категорию."); return; }
      act(api("/api/merchants/accept", { items: [{ merchant: row.dataset.merchantRow, category }] }), b);
    },
    "accept-all": () => {
      const items = [...body.querySelectorAll("tr[data-merchant-row]")]
        .map(tr => ({ merchant: tr.dataset.merchantRow, category: tr.querySelector("select[data-merchant-choice]").value }))
        .filter(x => x.category);
      if (!items.length) { toast("Ничего не выбрано."); return; }
      act(api("/api/merchants/accept", { items }), b);
    },
    "sync": () => act(api("/api/sync"), b),
    "rebuild": () => act(api("/api/rebuild"), b),
    "backup": () => act(api("/api/backup"), b),
    "run": () => { b.textContent = "Работает… с LLM это пара минут"; act(api("/api/run"), b); },
    "save-user": () => act(api(`/api/users/${encodeURIComponent(row.dataset.user)}/display-name`, { display_name: field("display") || null }), b),
    "rotate": () => confirmTwice(b, () => act(api(`/api/users/${encodeURIComponent(row.dataset.user)}/rotate`), b)),
    "show-token": () => { const t = row.querySelector(".token"); t.textContent = t.textContent.startsWith("•") ? t.dataset.token : "••••••••"; },
    "copy-token": () => navigator.clipboard.writeText(row.querySelector(".token").dataset.token).then(() => toast("Токен скопирован.")),
    "share": () => confirmTwice(b, () => act(api(`/api/users/${encodeURIComponent(row.dataset.user)}/share`), b)),
    "unshare": () => confirmTwice(b, () => act(api(`/api/users/${encodeURIComponent(row.dataset.user)}/share/delete`), b)),
    "copy-link": () => navigator.clipboard.writeText(b.dataset.link).then(() => toast("Ссылка скопирована: в ней и адрес, и пароль.")),
    "publish": () => act(api("/api/publish"), b),
    "add-user": () => { const box = byId("newUser"), v = n => box.querySelector(`[data-f="${n}"]`).value.trim(); act(api("/api/users", { name: v("name"), display_name: v("display") || null, token: v("token") || null }), b); },
  };
  actions[b.dataset.act]();
}

// Destructive buttons ask once more in place instead of a browser dialog.
function confirmTwice(button, run) {
  if (button.dataset.armed) { run(); return; }
  button.dataset.armed = "1";
  const text = button.textContent;
  button.textContent = "Точно?";
  setTimeout(() => { delete button.dataset.armed; button.textContent = text; }, 3000);
}


// Top merchants, recurring payments, recommendations, what if, year to date, data notes.

function renderTopMerchants(r) {
  const list = r.top_merchants, max = list.length ? list[0].total : 1, spend = Math.max(r.summary.spend, 1);
  byId("topMerchants").innerHTML = `<thead><tr><th>Мерчант</th><th style="width:28%"></th><th class="num">Сумма</th><th class="num">Раз</th><th class="num hide-sm">Ср. чек</th><th class="num hide-sm">Доля расходов</th></tr></thead><tbody>` +
    list.map(m => `<tr><td>${esc(m.merchant)}<span class="small">${esc(m.label)}</span></td><td><div class="barcell"><div class="bar" style="width:${(m.total / max * 100).toFixed(1)}%;background:${kindColor(m.kind)}"></div></div></td>
      <td class="num"><b>${zl(m.total)}</b></td><td class="num">${m.count}</td><td class="num hide-sm">${zl(m.total / m.count)}</td><td class="num hide-sm">${Math.round(m.total / spend * 100)}%</td></tr>`).join("") + "</tbody>";
}

function renderRecurring() {
  const list = D.recurring, active = list.filter(f => f.active).reduce((a, f) => a + f.price, 0);
  byId("recurring").innerHTML = !list.length ? `<p class="empty">Регулярных платежей не найдено.</p>` :
    `<table><thead><tr><th>Мерчант</th><th class="num">В месяц</th><th class="hide-sm">Последнее списание</th><th></th></tr></thead><tbody>` +
    list.map(f => `<tr><td>${esc(f.merchant)}<span class="small">${esc(f.label)} · ${pl(f.months, MON)}</span></td><td class="num">${zl(f.price, 2)}</td><td class="hide-sm">${f.last_charge}</td><td>${f.active ? '<span class="badge">активна</span>' : '<span class="badge">похоже, отменена</span>'}</td></tr>`).join("") +
    `</tbody></table><p style="margin:12px 0 0;font-size:14px">Активные: <b>${zl(active, 2)}</b> в месяц, <b>${zl(active * 12)}</b> в год.</p>`;
}

function renderRecs(r) {
  const advice = (r.story && r.story.advice) || [];
  byId("llmRecs").innerHTML = advice.length
    ? advice.map(x => `<p><b>${esc(x.action)}</b><br><span style="color:var(--ink-2)">${esc(x.reason)}</span>` +
        (x.saving ? `<br><span class="delta good">≈ ${zl(x.saving)} в месяц</span>` : "") + "</p>").join("")
    : `<p>${r.summary.complete ? "Явных мест для экономии в этом месяце нет." : "Пока всё в пределах лимитов."}</p>`;
  byId("recsSlot").classList.toggle("empty-slot", !advice.length);
}

function renderWhatIf() {
  const w = D.what_if;
  byId("whatIfCard").hidden = !w || !w.levers.length;
  if (!w || !w.levers.length) return;
  byId("whatIfHint").textContent = `Двигай ползунки. База — средний месяц за ${w.months.map(shortM).join(", ")}.`;
  const box = byId("levers");
  box.innerHTML = w.levers.map((l, i) => {
    const max = l.by_count ? l.payments : 100, value = l.by_count ? l.payments : 0;
    const meta = l.by_count ? `сейчас ${pl(l.payments, ORD)} в месяц × ${zl(l.monthly / Math.max(l.payments, 1))}` : `сейчас ${zl(l.monthly)} в месяц`;
    return `<div class="lever"><div class="top"><span>${esc(l.label)}${l.by_count ? ": раз в месяц" : ": урезать на"}</span><b id="lv-${i}"></b></div>
      <input type="range" min="0" max="${max}" value="${value}" data-lever="${i}" aria-label="${esc(l.label)}"><div class="meta">${esc(meta)}</div></div>`;
  }).join("");
  const update = () => {
    let total = 0;
    w.levers.forEach((l, i) => {
      const v = Number(box.querySelector(`[data-lever="${i}"]`).value);
      byId("lv-" + i).textContent = l.by_count ? pl(v, ORD) : v + " %";
      total += l.by_count ? (l.payments - v) * l.monthly / Math.max(l.payments, 1) : l.monthly * v / 100;
    });
    byId("saveMonth").textContent = "+" + zl(total);
    byId("saveYear").textContent = zl(total * 12) + " в год";
    byId("saveRate").innerHTML = w.income > 0 ? `Норма сбережений: ${Math.round(w.net / w.income * 100)}% сейчас → <b>${Math.round((w.net + total) / w.income * 100)}%</b>` : "";
  };
  box.oninput = update;
  update();
}

function renderYtd() {
  const y = D.ytd;
  byId("ytdCard").hidden = !y;
  if (!y) return;
  const n = y.months.length;
  byId("ytdHint").textContent = `${cap(shortM(y.months[0]))}–${shortM(y.months[n - 1])} ${y.months[0].slice(0, 4)}, ${pl(n, MON)}.`;
  const t = (name, value, note) => `<div class="tile"><div class="label">${name}</div><div class="value">${value}</div><div class="note" style="color:var(--ink-2)">${note}</div></div>`;
  const ratio = y.biggest_essential_monthly ? (y.top_impulse_total / y.biggest_essential_monthly).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) : null;
  byId("ytd").innerHTML =
    t("Заработано", zl(y.income), `в среднем ${zl(y.income / n)} в месяц`) +
    t("Потрачено", zl(y.spend), `в среднем ${zl(y.spend / n)} в месяц`) +
    t("Итог года", (y.net >= 0 ? "+" : "") + zl(y.net), y.net >= 0 ? "отложено" : "ушло больше, чем пришло") +
    (y.top_impulse_label ? t(esc(y.top_impulse_label), zl(y.top_impulse_total), `${pl(y.top_impulse_payments, PAY)}` + (ratio ? ` · это ${ratio} мес. «${esc(y.biggest_essential_label)}»` : "")) : "") +
    t("Импульсивное всего", zl(y.impulse), `${Math.round(y.impulse / Math.max(y.spend, 1) * 100)}% всех расходов`);
}

function renderNotes(r) {
  const n = r.notes;
  const notes = [
    `Данные по ${D.data_until}. Последние дни — из пуш-уведомлений и блокировок по карте, пока банк их не провёл.`,
    n.pending ? `${pl(n.pending, OPS)} этого месяца банк ещё не провёл, но они учтены.` : "Все операции месяца проведены банком.",
    n.shifted_dates.length ? `Платежи за аренду от ${n.shifted_dates.join(", ")} отнесены к этому месяцу: оплата после 25-го — за следующий месяц.` : null,
    n.uncategorised ? `${pl(n.uncategorised, OPS)} (${zl(n.uncategorised_total)}) без категории.` + (MODE === "admin" ? ` <a href="#" data-goto-uncat>Разобрать</a>.` : "") : "У всех операций есть категория.",
    "Переводы людям не считаются расходами, но входят в сальдо.",
    D.unmatched_holds ? `${pl(D.unmatched_holds, ["блокировка", "блокировки", "блокировок"])} по карте так и не провелась и не учтена.` : null,
  ].filter(Boolean);
  byId("notes").innerHTML = notes.map(x => `<li>${x}</li>`).join("");
}

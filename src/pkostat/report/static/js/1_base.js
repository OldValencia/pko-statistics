"use strict";
// Shared state and helpers. Numbers come ready from Python (pkostat.analytics); this code only
// formats and draws them. Money is integer grosze.
const PAYLOAD = JSON.parse(document.getElementById("data").textContent);
const D = PAYLOAD.report;
const MODE = PAYLOAD.mode;
const KINDS = ["essential", "discretionary", "impulse"];
const KIND_RU = { essential: "Необходимое", discretionary: "По желанию", impulse: "Импульсивное" };
const COUNTED = new Set(["settled", "pending"]);
const CATS = Object.fromEntries(D.categories.map(c => [c.name, c]));
const label = name => (CATS[name] ? CATS[name].label : "Без категории");
const catKind = name => (CATS[name] ? CATS[name].kind : "uncategorised");
const SERIES = Object.fromEntries(D.series.map(s => [s.month, s]));
const MONTHS = D.months;
const LAST = MONTHS[MONTHS.length - 1];  // the running month: limits and forecast matter now
let current = LAST;

const MONTH_NOM = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const MONTH_PREP = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре", "декабре"];
const MONTH_INSTR = ["январём", "февралём", "мартом", "апрелем", "маем", "июнем", "июлем", "августом", "сентябрём", "октябрём", "ноябрём", "декабрём"];
const MONTH_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const WEEKDAYS_LONG = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"];
const PAY = ["платёж", "платежа", "платежей"], ORD = ["раз", "раза", "раз"], OPS = ["операция", "операции", "операций"], MON = ["месяц", "месяца", "месяцев"];

const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const kindColor = k => (KINDS.includes(k) ? css("--" + k) : css("--neutral-mark"));
const mi = m => Number(m.slice(5)) - 1;
const cap = s => s[0].toUpperCase() + s.slice(1);
const title = m => cap(MONTH_NOM[mi(m)]) + " " + m.slice(0, 4);
const inMonth = m => "в " + MONTH_PREP[mi(m)];
const shortM = m => MONTH_SHORT[mi(m)];
const zl = (minor, digits = 0) => {
  const text = (Math.abs(minor) / 100).toLocaleString("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: true }).replace(/\s/g, "\u00a0");
  return (minor < 0 ? "−" : "") + text + "\u00a0zł";
};
const kz = minor => { const v = Math.abs(minor) / 100; return v >= 1000 ? (v / 1000).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "к" : Math.round(v).toString(); };
const pct = x => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(Math.round(x * 100)) + "%";
const plural = (n, one, few, many) => { const a = Math.abs(n) % 100, b = a % 10; return a > 10 && a < 20 ? many : b > 1 && b < 5 ? few : b === 1 ? one : many; };
const pl = (n, forms) => n + " " + plural(n, ...forms);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const byId = id => document.getElementById(id);

const tip = byId("tooltip");
function showTip(e, head, rows) {
  tip.innerHTML = `<div class="t-title">${esc(head)}</div>` + rows.map(([k, v]) => `<div class="t-row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("");
  tip.style.display = "block";
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8) + "px";
}
const hideTip = () => { tip.style.display = "none"; };
function hover(el, head, rows) {
  el.addEventListener("mousemove", e => showTip(e, head, rows));
  el.addEventListener("mouseleave", hideTip);
}
function svgEl(tag, attrs = {}, parent) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}
// Bars are rounded only at the data end, anchored square to the baseline.
function colBar(x, y, w, h, r) { r = Math.min(r, w / 2, h); return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`; }
function colBarDown(x, y, w, h, r) { r = Math.min(r, w / 2, h); return `M${x},${y}V${y + h - r}Q${x},${y + h} ${x + r},${y + h}H${x + w - r}Q${x + w},${y + h} ${x + w},${y + h - r}V${y}Z`; }
const legendHtml = items => items.map(([text, st]) => `<span class="key"><span class="${st.cls || "sw"}" style="${st.css || ""}"></span>${esc(text)}</span>`).join("");
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1)))), f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
}
function axis(svg, w, left, top, plotH, max, step, fmt, minV = 0) {
  const y = v => top + plotH - (v - minV) / (max - minV) * plotH;
  for (let v = minV; v <= max + 1; v += step) {
    svgEl("line", { x1: left, x2: w, y1: y(v), y2: y(v), stroke: v === 0 ? css("--axis") : css("--grid"), "stroke-width": 1 }, svg);
    svgEl("text", { x: left - 8, y: y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
  }
  return y;
}
const monthLabel = (m, slot) => (slot < 34 ? shortM(m)[0].toUpperCase() : shortM(m));

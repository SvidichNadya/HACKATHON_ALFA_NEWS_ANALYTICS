import { h, icon, mount, fmt, clear } from "./dom.js";
import { api, setCsrf, ApiError } from "./api.js";
import { S } from "./state.js";
import { toast, skeleton } from "./ui.js";
import { loginView } from "./views/login.js";
import { homeView } from "./views/home.js";
import { radarView } from "./views/radar.js";
import { insightView } from "./views/insight.js";
import { cascadeView } from "./views/cascade.js";
import { networkView } from "./views/network.js";
import { analyzeView } from "./views/analyze.js";
import { libraryView } from "./views/library.js";
import { qualityView } from "./views/quality.js";

const root = document.getElementById("app");
const ROUTES = [
  [/^#\/home$/, homeView], [/^#\/radar$/, radarView], [/^#\/event\/(\d+)$/, insightView("event")], [/^#\/insight\/(\d+)$/, insightView("insight")],
  [/^#\/cascades$/, cascadeView], [/^#\/network$/, networkView], [/^#\/analyze$/, analyzeView], [/^#\/library$/, libraryView], [/^#\/quality$/, qualityView],
];

export function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }
export async function refreshFeed(force = false) {
  if (!force && S.feed && S.feed.company.id === S.companyId && S.feed.role === S.role && Date.now() - S.feedAt < 60000) return S.feed;
  S.feed = await api(`/api/companies/${S.companyId}/feed?role=${S.role}`);
  S.feedAt = Date.now();
  return S.feed;
}

async function boot() {
  try {
    const me = await api("/api/me");
    if (!me.user) return mount(root, loginView(me, boot));
    S.me = me; setCsrf(me.csrf);
    const saved = sessionStorage.getItem("radar.company");
    S.companyId = me.companies.find((c) => c.id === saved)?.id || me.companies[0]?.id;
    S.role = sessionStorage.getItem("radar.role") || me.user.role;
    if (!location.hash || location.hash === "#/") location.hash = "#/home";
    render();
  } catch (e) { mount(root, h("div", { class: "page" }, h("div", { class: "err" }, e.message))); }
}

const NAV = [["#/home", "home", "Главная"], ["#/radar", "radar", "Бизнес-радар", true], ["#/cascades", "layers", "Каскады"], ["#/network", "network", "Связи"], ["#/analyze", "flask", "Проверить новость"]];
const NAV2 = [["#/library", "file", "Источники"], ["#/quality", "chart", "Качество"]];

function shell(content, active) {
  const badge = S.feed ? S.feed.cards.filter((c) => c.priority === "critical" || c.priority === "high").length : null;
  const link = ([href, ic, label, entry]) => h("a", { href, class: entry ? "entry" : "", "aria-current": active === href ? "page" : null }, icon(ic, 20), label, entry && badge ? h("span", { class: "badge", "aria-label": `${badge} важных событий` }, badge) : null);
  const co = S.me.companies.find((c) => c.id === S.companyId);
  const side = h("nav", { class: "side", "aria-label": "Основное меню" },
    h("a", { class: "brand", href: "#/home", "aria-label": "Альфа-Бизнес, главная" }, h("span", { class: "brand-mark" }, h("svg", { viewBox: "0 0 24 24", width: 20, height: 20 }, h("path", { d: "M5 19 12 5l7 14M8 14.500h8", fill: "none", stroke: "#fff", "stroke-width": "2.400", "stroke-linecap": "round", "stroke-linejoin": "round" }))), h("span", null, h("b", null, "Альфа-Бизнес"), h("small", null, "Интернет-банк"))),
    h("div", { class: "nav" }, NAV.slice(0, 1).map(link), h("a", { href: "#/accounts", class: "stub", onClick: (e) => { e.preventDefault(); toast("В прототипе доступен только сервис «Бизнес-радар»"); } }, icon("wallet"), "Счета и платежи"),
      h("a", { href: "#/loans", class: "stub", onClick: (e) => { e.preventDefault(); toast("В прототипе доступен только сервис «Бизнес-радар»"); } }, icon("bank"), "Кредиты и гарантии"), h("a", { href: "#/ved", class: "stub", onClick: (e) => { e.preventDefault(); toast("В прототипе доступен только сервис «Бизнес-радар»"); } }, icon("globe"), "ВЭД и валюта"),
      NAV.slice(1, 2).map(link), h("div", { class: "grp" }, "Радар"), NAV.slice(2).map(link), h("div", { class: "grp" }, "Прозрачность"), NAV2.map(link)),
    h("div", { class: "side-foot" }, h("b", null, S.me.user.name), h("div", { class: "muted small" }, S.me.user.role_label), h("button", { class: "btn ghost sm", style: { marginTop: "8px", paddingLeft: 0 }, onClick: logout }, icon("logout", 16), "Выйти")));
  const roleSel = h("select", { class: "sel inline", "aria-label": "Роль просмотра", onChange: (e) => { S.role = e.target.value; sessionStorage.setItem("radar.role", S.role); S.feed = null; render(); } },
    Object.entries(S.me.roles).map(([k, v]) => h("option", { value: k, selected: k === S.role }, v)));
  const coSel = S.me.companies.length > 1 ? h("select", { class: "sel inline", "aria-label": "Компания", onChange: (e) => { S.companyId = e.target.value; sessionStorage.setItem("radar.company", S.companyId); S.feed = null; render(); } },
    S.me.companies.map((c) => h("option", { value: c.id, selected: c.id === S.companyId }, c.display_name))) : h("b", null, co ? co.display_name : "");
  const top = h("header", { class: "top" }, h("div", { class: "grow row" }, coSel, S.me.user.is_admin ? companySearch() : null, co && co.is_synthetic ? h("span", { class: "pill demo", title: "Данные синтетические" }, "синтетические данные") : null),
    h("span", { class: "small muted" }, "Просмотр как"), roleSel);
  return h("div", { class: "shell" }, side, h("div", { class: "main" }, top, h("main", { class: "page", id: "page" }, content)));
}
function companySearch() {
  const inp = h("input", { class: "input", style: { width: "220px", minHeight: "40px", padding: "7px 12px" }, placeholder: "Найти компанию…", "aria-label": "Поиск компании" });
  const list = h("div", { class: "card tight", style: { position: "absolute", top: "46px", zIndex: 30, width: "420px", display: "none", maxHeight: "320px", overflow: "auto" } });
  let t;
  inp.addEventListener("input", () => { clearTimeout(t); t = setTimeout(async () => {
    if (inp.value.length < 2) return (list.style.display = "none");
    const r = await api(`/api/companies?q=${encodeURIComponent(inp.value)}`);
    mount(list, r.companies.length ? r.companies.slice(0, 12).map((c) => h("button", { class: "demo-acc", style: { width: "100%", marginBottom: "6px" }, onClick: () => { if (!S.me.companies.find((x) => x.id === c.id)) S.me.companies.push(c); S.companyId = c.id; sessionStorage.setItem("radar.company", c.id); S.feed = null; list.style.display = "none"; inp.value = ""; render(); } }, h("span", null, h("b", null, c.display_name), h("div", { class: "tiny muted" }, (c.okved_name || "").slice(0, 60))), h("span", { class: "tiny muted num" }, fmt.money(c.revenue)))) : h("div", { class: "muted small" }, "Ничего не найдено"));
    list.style.display = "block";
  }, 250); });
  return h("div", { style: { position: "relative" } }, inp, list);
}
async function logout() { await api("/api/logout", { method: "POST" }); S.me = null; S.feed = null; location.hash = ""; boot(); }

function updateBadge() {
  const a = document.querySelector(".nav a.entry");
  if (!a || !S.feed) return;
  const n = S.feed.cards.filter((c) => c.priority === "critical" || c.priority === "high").length;
  a.querySelector(".badge")?.remove();
  if (n) a.append(h("span", { class: "badge", "aria-label": `${n} важных событий` }, n));
}

let seq = 0;
async function render() {
  if (!S.me) return;
  const my = ++seq;
  const hash = location.hash || "#/home";
  const route = ROUTES.find(([re]) => re.test(hash));
  const [, view] = route || ROUTES[0];
  const m = route ? hash.match(route[0]) : [];
  const active = hash.startsWith("#/event") || hash.startsWith("#/insight") ? "#/radar" : hash;
  const slot = h("div", null, skeleton(3, 140));
  mount(root, shell(slot, active));
  try {
    const node = await view({ params: m.slice(1), go, refreshFeed, rerender: render });
    if (my !== seq) return;
    mount(slot, node);
    document.getElementById("page")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
    updateBadge();
  } catch (e) {
    if (my !== seq) return;
    if (e instanceof ApiError && e.status === 401) return boot();
    mount(slot, h("div", { class: "card" }, h("h2", null, "Не удалось загрузить раздел"), h("p", { class: "muted", style: { margin: "8px 0 16px" } }, e.message), h("button", { class: "btn dark", onClick: render }, "Повторить")));
  }
}
window.addEventListener("hashchange", render);
boot();

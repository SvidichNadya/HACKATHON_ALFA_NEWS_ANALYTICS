import { h, icon, fmt, FACTOR } from "../dom.js";
import { S } from "../state.js";
import { sweep, bars } from "../charts.js";
import { prio, demoPill } from "../ui.js";
import { api } from "../api.js";

export async function homeView({ go, refreshFeed }) {
  const feed = await refreshFeed();
  const c = feed.company, top = feed.cards.slice(0, 3);
  const crit = feed.cards.filter((x) => x.priority === "critical").length;
  const high = feed.cards.filter((x) => x.priority === "high").length;
  let net = null;
  try { net = await api(`/api/companies/${c.id}/network`); } catch { /* optional widget */ }
  const g = c.graph;
  return h("div", { class: "stack", style: { gap: "22px" } },
    h("div", null, h("h1", null, `Добрый день, ${S.me.user.name.split(" ")[0]}`), h("p", { class: "muted", style: { marginTop: "6px" } }, `${c.display_name} · ${c.sector_label || "отрасль не определена"}`)),
    h("section", { class: "hero rise", "aria-labelledby": "hero-t" },
      h("div", null, h("div", { class: "row small", style: { opacity: ".7" } }, icon("radar", 18), "Бизнес-радар"), h("h2", { id: "hero-t", style: { marginTop: "8px" } }, top.length ? `${crit + high} ${plural(crit + high, "событие требует", "события требуют", "событий требуют")} внимания` : "Новых значимых событий нет"),
        h("p", null, "Система сопоставила внешние новости и аналитику банка с профилем вашей компании и отобрала то, что может повлиять на бизнес."),
        h("div", { class: "items" }, top.map((x, i) => h("button", { class: "hero-item rise", style: { "--i": i + 2 }, onClick: () => go(`#/event/${x.event_id}`) }, prio(x.priority), h("span", null, h("b", null, x.headline), h("small", null, x.why.length > 110 ? x.why.slice(0, 108) + "…" : x.why))))),
        h("div", { class: "row" }, h("a", { class: "btn primary", href: "#/radar" }, "Открыть радар", icon("arrow", 18)), h("a", { class: "btn", style: { background: "transparent", color: "inherit", borderColor: "rgba(255,255,255,.35)" }, href: "#/cascades" }, `Каскады: ${feed.cascades.length}`))),
      sweep(feed.cards, 220)),
    h("div", { class: "kpis" },
      kpi(feed.counts.relevant, "событий отобрано из " + feed.counts.events_total), kpi(crit, "критических"), kpi(feed.cascades.length, "каскадов сигналов"), kpi(feed.changes.new, feed.changes.since ? "новых с прошлого визита" : "новых при первом просмотре")),
    h("div", { class: "grid g2" },
      h("section", { class: "card rise", style: { "--i": 3 } }, h("div", { class: "row between" }, h("h3", null, "Продукты банка"), h("span", { class: "small muted" }, "по данным банка")),
        c.products.length ? h("div", { class: "chips", style: { marginTop: "14px" } }, c.products.map((p) => h("span", { class: "chip" }, p))) : h("p", { class: "muted", style: { marginTop: "10px" } }, "Продукты не подключены"),
        h("p", { class: "small muted", style: { marginTop: "14px" } }, "От набора продуктов зависит, какие события для вас значимы: например, при наличии кредитов радар учитывает ставку, при депозитах — доходность размещений.")),
      h("section", { class: "card rise", style: { "--i": 4 } }, h("div", { class: "row between" }, h("h3", null, "Крупнейшие получатели платежей"), net ? h("a", { href: "#/network", class: "small" }, "Все связи") : null),
        g && g.available && g.recipients.top.length ? h("div", { style: { marginTop: "14px" } }, bars(g.recipients.top.slice(0, 5).map((t) => ({ label: t.known ? t.name : `Вне набора · ${t.id}`, value: t.share, text: fmt.pct(t.share), cls: t.in_group ? "" : "red", hint: t.okved_name })))) : h("p", { class: "muted", style: { marginTop: "10px" } }, "Платёжных связей в данных нет"),
        g && g.available ? h("p", { class: "tiny faint", style: { marginTop: "12px" } }, g.caveat) : null)));
}
const kpi = (n, l) => h("div", { class: "card tight kpi rise" }, h("b", { class: "num" }, n), h("span", null, l));
const plural = (n, a, b, c) => { const m = n % 10, k = n % 100; return m === 1 && k !== 11 ? a : m >= 2 && m <= 4 && (k < 10 || k >= 20) ? b : c; };

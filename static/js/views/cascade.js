import { h, icon, fmt, FACTOR, CONF, mount } from "../dom.js";
import { api } from "../api.js";
import { S } from "../state.js";
import { flow } from "../charts.js";

export async function cascadeView({ go, refreshFeed }) {
  const feed = await refreshFeed();
  const sel = { i: 0 };
  const stage = h("div");
  const draw = () => {
    const k = feed.cascades[sel.i];
    if (!k) return mount(stage);
    mount(stage, h("div", { class: "card rise" }, h("div", { class: "row between" }, h("div", null, h("h2", null, k.target_label), h("p", { class: "small muted" }, `${k.links.length} независимых сигнала сходятся на этом узле · уверенность ${CONF[k.confidence]}`)), h("div", { class: "kpi", style: { textAlign: "right" } }, h("b", { class: "num" }, Math.round(k.score)), h("span", null, "интенсивность"))),
      h("div", { style: { margin: "14px 0" } }, flow(k.graph, { width: 960 })),
      h("div", { class: "grid g2" }, h("div", null, h("b", { class: "small" }, "Сигналы"), h("div", { class: "stack", style: { marginTop: "8px" } }, k.links.map((l) => h("a", { class: "claim t-fact", href: `#/event/${l.event_id}`, style: { textDecoration: "none", display: "block" } }, h("div", { class: "tg" }, h("span", { class: "tag" }, l.factor_label), h("span", { class: "tiny faint" }, `влияние ${Math.round(l.strength * 100)}% · опора на данные ${Math.round(l.confidence * 100)}%`)), h("p", null, l.headline, " ", h("span", { class: "faint small" }, "— " + l.title)))))),
        h("div", null, h("b", { class: "small" }, "Как читать"), h("ul", { class: "list" }, h("li", null, "Каждый сигнал по отдельности умеренный: вместе они давят на один и тот же участок экономики компании."), h("li", null, `Самое слабое звено — «${(k.links.find((l) => l.mechanism_id === k.weakest.mechanism_id) || k.links[0]).headline}»: опора на данные ${Math.round(k.weakest.confidence * 100)}%.`), k.amplifiers.map((a) => h("li", null, a.label)), h("li", null, "Это гипотеза о механизме, а не доказанная причинность.")))),
      h("div", { class: "row", style: { marginTop: "18px" } }, h("button", { class: "btn primary", onClick: async (e) => { e.target.disabled = true; try { const ins = await api(`/api/companies/${S.companyId}/cascades/${k.key}/analyze`, { method: "POST", body: { role: S.role } }); go(`#/insight/${ins.insight_id}`); } catch (x) { e.target.disabled = false; alert(x.message); } } }, "Полный разбор с основаниями", icon("arrow", 18)))));
  };
  const tabs = h("div", { class: "seg", role: "tablist" }, feed.cascades.map((k, i) => h("button", { role: "tab", "aria-pressed": String(i === 0), onClick: (e) => { sel.i = i; [...tabs.children].forEach((b, j) => b.setAttribute("aria-pressed", String(i === j))); draw(); } }, k.target_label)));
  draw();
  return h("div", { class: "stack", style: { gap: "20px" } },
    h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Радар скрытых каскадных последствий"), h("p", null, "Несколько внешне независимых событий, которые вместе давят на один и тот же участок вашего бизнеса. Компания может не упоминаться ни в одной из новостей."))),
    feed.cascades.length ? [tabs, stage] : h("div", { class: "card empty" }, h("b", null, "Сейчас сходящихся сигналов нет"), h("p", { class: "small" }, "Каскад появляется, когда как минимум два независимых события затрагивают один узел вашего бизнеса с достаточными основаниями. Лучше показать ноль каскадов, чем выдумать связь.")));
}

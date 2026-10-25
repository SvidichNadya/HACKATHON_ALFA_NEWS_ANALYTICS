import { h, icon, fmt, FACTOR, PRIORITY, mount } from "../dom.js";
import { S } from "../state.js";
import { exposureRadar } from "../charts.js";
import { prio, kindLab, demoPill } from "../ui.js";
import { api } from "../api.js";

export async function radarView({ go, refreshFeed }) {
  const feed = await refreshFeed();
  const c = feed.company;
  const st = { prio: new Set(), factor: null, q: "" };
  const list = h("div", { class: "feed", "aria-live": "polite" });
  const casc = feed.cascades.length ? h("section", { class: "card" }, h("div", { class: "row between" }, h("h3", null, "Радар каскадных последствий"), h("a", { href: "#/cascades", class: "small" }, "Все")),
    h("p", { class: "small muted", style: { margin: "4px 0 12px" } }, "Сигналы из разных новостей, которые сходятся на одном узле вашего бизнеса."),
    h("div", { class: "cascade-strip" }, feed.cascades.slice(0, 2).map((k) => h("button", { class: "cs", onClick: () => go("#/cascades") }, h("span", null, h("b", null, k.target_label), h("span", { class: "small muted" }, `${k.links.length} независимых сигнала · уверенность ${({ high: "высокая", medium: "средняя", low: "низкая" })[k.confidence]}`), h("span", { class: "links" }, [...new Set(k.links.map((l) => l.factor_label))].map((f) => h("span", null, f)))), h("b", { class: "num", style: { fontSize: "24px" } }, Math.round(k.score)))))) : null;
  let limit = 10;
  const draw = () => {
    const all = feed.cards.filter((x) => (!st.prio.size || st.prio.has(x.priority)) && (!st.factor || x.factors.includes(st.factor)) && (!st.q || (x.title + x.headline + x.why).toLowerCase().includes(st.q.toLowerCase())));
    const rows = all.slice(0, limit);
    mount(list, rows.length ? [...rows.map((x, i) => card(x, i, go)), all.length > limit ? h("button", { class: "btn", onClick: () => { limit += 10; draw(); } }, `Показать ещё (${all.length - limit})`) : null] : h("div", { class: "card empty" }, h("b", null, "Нет событий по выбранным фильтрам"), h("p", { class: "small" }, "Снимите фильтры или проверьте собственную новость на вкладке «Проверить новость».")));
  };
  const factors = [...new Set(feed.cards.flatMap((x) => x.factors))];
  const filters = h("div", { class: "stack" },
    h("div", { class: "row" }, ...["critical", "high", "medium", "watch"].map((p) => { const n = feed.cards.filter((x) => x.priority === p).length; const b = h("button", { class: "chip", "aria-pressed": "false", onClick: () => { st.prio.has(p) ? st.prio.delete(p) : st.prio.add(p); b.setAttribute("aria-pressed", String(st.prio.has(p))); draw(); } }, `${PRIORITY[p]} · ${n}`); return b; })),
    h("div", { class: "row" }, h("input", { class: "input", style: { maxWidth: "280px" }, placeholder: "Поиск по событиям", "aria-label": "Поиск", onInput: (e) => { st.q = e.target.value; draw(); } }),
      h("select", { class: "sel inline", "aria-label": "Тема", onChange: (e) => { st.factor = e.target.value || null; draw(); } }, h("option", { value: "" }, "Все темы"), factors.map((f) => h("option", { value: f }, FACTOR[f] || f)))));
  draw();
  api(`/api/companies/${c.id}/seen`, { method: "POST" }).catch(() => {});
  return h("div", { class: "cols" },
    h("div", { class: "stack", style: { gap: "18px" } },
      h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Бизнес-радар"), h("p", null, `События, отобранные для «${c.display_name}». Порядок зависит от профиля компании и роли: ${feed.role_label.toLowerCase()}.`))),
      feed.changes.new && feed.changes.since ? h("div", { class: "notice" }, icon("info", 20), h("span", null, `С прошлого просмотра появилось ${feed.changes.new} новых или обновлённых событий.`)) : null,
      filters, casc, list, h("p", { class: "tiny faint" }, `Из ${feed.counts.events_total} событий за период ${feed.counts.dropped} не связаны с вашей компанией и скрыты.`)),
    h("aside", { class: "card profile rise", "aria-label": "Профиль компании" }, h("h3", null, "Что система знает о компании"), h("p", { class: "small muted" }, "Чувствительность к внешним факторам. Наведите на точку, чтобы увидеть основания."),
      exposureRadar(c.sens, 320),
      h("div", { class: "legend" }, h("span", null, h("i", { style: { background: "var(--red)" } }), "расчётная чувствительность"), h("span", null, "в подсказке: ● подтверждено данными, ○ типично для отрасли")),
      h("div", { class: "feat" }, c.features.slice(0, 9).map((f) => h("div", null, h("span", null, f.label), h("span", { title: f.source }, f.value)))),
      c.unknown.length ? h("div", { style: { marginTop: "14px" } }, h("b", { class: "small" }, "Чего система не знает"), h("ul", { class: "list" }, c.unknown.slice(0, 3).map((u) => h("li", null, u.text)))) : null));
}

function card(x, i, go) {
  return h("button", { class: `ev rise ${x.priority}`, style: { "--i": Math.min(i, 8) }, onClick: () => go(`#/event/${x.event_id}`) }, h("span", { class: "rail" }),
    h("div", null, h("div", { class: "meta" }, prio(x.priority), kindLab(x.kind), x.is_new ? h("span", { class: "new-dot", title: "Новое с прошлого просмотра" }) : null, demoPill(x.is_synthetic), x.contradictions ? h("span", { class: "pill p-watch", title: "Источники противоречат друг другу" }, "расхождение источников") : null),
      h("h3", null, x.headline), h("div", { class: "src" }, `${x.title} · ${fmt.date(x.last_seen)} · источников: ${x.sources}`), h("p", { class: "why" }, x.why),
      h("div", { class: "reasons" }, x.reasons.filter((r) => r.points > 0).map((r) => h("span", { title: "Вклад в оценку значимости" }, `${r.label.length > 58 ? r.label.slice(0, 56) + "…" : r.label}`)))),
    h("div", { class: "score" }, h("b", { class: "num" }, Math.round(x.importance)), h("small", null, "значимость"), h("div", { class: "meter" }, h("i", { style: { width: Math.round(x.importance) + "%" } })), h("small", { style: { display: "block", marginTop: "6px" } }, `уверенность: ${({ high: "высокая", medium: "средняя", low: "низкая" })[x.confidence]}`)));
}

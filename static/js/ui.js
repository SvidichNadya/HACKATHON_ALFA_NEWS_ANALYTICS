import { h, icon, fmt, FACTOR, PRIORITY, CONF, CLAIM, mount, clear } from "./dom.js";
import { api } from "./api.js";
import { S } from "./state.js";

export function toast(msg, ms = 3200) {
  const t = h("div", { class: "toast", role: "status" }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

export function drawer(title, body) {
  const close = () => { scrim.remove(); dr.remove(); document.removeEventListener("keydown", esc); };
  const esc = (e) => e.key === "Escape" && close();
  const scrim = h("div", { class: "scrim", onClick: close });
  const dr = h("aside", { class: "drawer", role: "dialog", "aria-label": title }, h("div", { class: "hd" }, h("h2", null, title), h("button", { class: "btn ghost sm", onClick: close, "aria-label": "Закрыть" }, icon("close"))), body);
  document.body.append(scrim, dr);
  document.addEventListener("keydown", esc);
  dr.querySelector("button").focus();
  return close;
}

export const prio = (p) => p ? h("span", { class: `pill p-${p}` }, p === "critical" ? h("i", { class: "dot" }) : null, PRIORITY[p]) : null;
export const demoPill = (is) => is ? h("span", { class: "pill demo", title: "Материал создан для демонстрации и не является публикацией реального источника" }, "демо-материал") : null;
export const kindLab = (k) => h("span", { class: `kind ${k}` }, k === "risk" ? "Риск" : k === "opportunity" ? "Возможность" : "На контроле");

export function evidenceView(ev) {
  const box = h("div", { class: "ev-box " + (ev.type === "bank" ? "bank" : "") });
  const typeName = { news: "Новость", bank: "Аналитика Альфа-Банка", profile: "Данные о компании", graph: "Платёжные связи" }[ev.type] || ev.type;
  box.append(h("div", { class: "row between" }, h("b", null, ev.title || typeName), ev.is_synthetic ? demoPill(true) : null),
    h("div", { class: "small muted" }, [typeName, ev.source, ev.locator, ev.published_at ? fmt.dateFull(ev.published_at) : null].filter(Boolean).join(" · ")));
  if (ev.text) box.append(h("blockquote", null, ev.text.length > 1400 ? ev.text.slice(0, 1400) + "…" : ev.text));
  if (ev.url && /^https?:\/\//.test(ev.url) && !ev.url.includes("demo.invalid")) box.append(h("a", { class: "btn sm", href: ev.url, target: "_blank", rel: "noopener noreferrer", style: { marginTop: "10px" } }, icon("link", 16), "Открыть первоисточник"));
  else if (ev.url) box.append(h("div", { class: "tiny faint", style: { marginTop: "8px" } }, "Первоисточник демо-материала недоступен: материал синтетический."));
  return box;
}

export function showEvidence(ins, ids, title = "Основания") {
  const body = h("div");
  ids.forEach((id) => ins.evidence[id] && body.append(evidenceView(ins.evidence[id])));
  if (!body.children.length) body.append(h("p", { class: "muted" }, "Для этого утверждения основания не требуются или недоступны."));
  drawer(title, body);
}

export function cites(ins, ids) {
  if (!ids || !ids.length) return null;
  ins._cn = ins._cn || {};
  const num = (id) => (ins._cn[id] ??= Object.keys(ins._cn).length + 1);
  return h("span", { class: "cites" }, ids.map((id) => h("button", { class: "cite " + (id.startsWith("bank:") ? "bank" : ""), title: ins.evidence[id]?.title || id, onClick: () => showEvidence(ins, [id]) }, ins.evidence[id] ? num(id) : "?")));
}

export function claim(ins, c, { hideTag = false } = {}) {
  const [label, cls] = CLAIM[c.type] || CLAIM.AI_INFERENCE;
  return h("div", { class: `claim ${cls}` },
    hideTag ? null : h("div", { class: "tg" }, h("span", { class: "tag" }, label), c.is_synthetic ? demoPill(true) : null, c.origin === "llm" ? h("span", { class: "tiny faint" }, "сформулировано моделью") : null, c.downgraded ? h("span", { class: "tiny faint", title: c.downgraded }, "понижено проверкой") : null),
    h("p", null, c.text, cites(ins, c.evidence)),
    c.type === "BANK_ANALYSIS" ? h("div", { class: "tiny faint", style: { marginTop: "4px" } }, [c.doc, c.locator].filter(Boolean).join(" · ")) : null);
}

export function gauge(v, label) {
  const r = 26, c = 2 * Math.PI * r;
  return h("div", { class: "suff" }, h("svg", { class: "gauge", viewBox: "0 0 64 64" }, h("circle", { class: "bg", cx: 32, cy: 32, r }), h("circle", { class: "fg", cx: 32, cy: 32, r, "stroke-dasharray": c, "stroke-dashoffset": c * (1 - v), transform: "rotate(-90 32 32)" })),
    h("div", null, h("b", { class: "num", style: { fontSize: "22px" } }, Math.round(v * 100) + "%"), h("div", { class: "small muted" }, label)));
}

export function skeleton(n = 3, hgt = 120) { return h("div", { class: "grid" }, Array.from({ length: n }, () => h("div", { class: "skel", style: { height: hgt + "px" } }))); }

export async function showTrace(runId) {
  const body = h("div", null, skeleton(4, 40));
  drawer("Трасса работы агента", body);
  try {
    const t = await api(`/api/runs/${runId}`);
    mount(body,
      h("div", { class: "row small muted", style: { marginBottom: "12px" } }, h("span", null, `Режим: ${t.mode === "llm" ? "модель + правила" : "детерминированный (правила)"}`), t.model ? h("span", null, t.model) : null, h("span", null, fmt.time(t.duration_ms)), h("span", null, `токенов: ${t.tokens_in + t.tokens_out}`), h("span", null, `перепланирований: ${t.replans}`)),
      h("div", { class: "trace" }, t.trace.map((s) => h("div", { class: `tr ${s.kind} ${s.status}` }, h("i"), h("div", null, h("b", null, stepName(s)), h("small", null, s.why), s.result ? h("small", null, "→ " + s.result) : null), h("small", { class: "num" }, s.ms ? fmt.time(s.ms) : "")))),
      h("p", { class: "tiny faint", style: { marginTop: "14px" } }, "Каждый вызов инструмента проходит серверную проверку прав и записывается в журнал аудита. Модель не имеет прямого доступа к базе данных и сети."));
  } catch (e) { mount(body, h("div", { class: "err" }, e.message)); }
}
const STEP = { plan: "План", tool: "Инструмент", draft: "Сборка вывода", verify: "Самопроверка", replan: "Корректировка", llm: "Модель", finalize: "Результат", skip: "Пропуск", error: "Ошибка" };
const TOOLN = { get_company_profile: "профиль компании", get_event: "событие", graph_exposure: "платёжные связи", match_mechanisms: "механизмы влияния", search_bank_analytics: "поиск по аналитике банка", search_news: "поиск связанных новостей" };
const stepName = (s) => (s.kind === "tool" ? `Инструмент: ${TOOLN[s.name] || s.name}` : `${STEP[s.kind] || s.kind}${s.kind === "replan" ? ": " + ({ bank_search: "повторный поиск", drop_claim: "отклонено утверждение модели", downgrade: "понижен статус" }[s.name] || s.name) : ""}`);

export function calcWidget(spec, companyId) {
  const inputs = {};
  const out = h("div", { "aria-live": "polite" });
  const fields = spec.fields.map((f) => {
    const inp = h("input", { class: "input num", inputmode: "decimal", placeholder: f.default != null ? String(f.default) : "введите значение", value: f.default != null ? String(f.default) : "" });
    inputs[f.key] = inp;
    return h("label", { class: "f" }, f.label, inp);
  });
  const run = async () => {
    const payload = {};
    for (const [k, el] of Object.entries(inputs)) if (el.value.trim() !== "") payload[k] = el.value.replace(/\s/g, "").replace(",", ".");
    try {
      const r = await api(`/api/companies/${companyId}/calc`, { method: "POST", body: { kind: spec.kind, inputs: payload } });
      mount(out, calcResult(r));
    } catch (e) { mount(out, h("div", { class: "err" }, e.message)); }
  };
  return h("div", { class: "card flat tight" }, h("h3", null, spec.title), h("p", { class: "small muted" }, "Расчёт по вашим допущениям: банк не знает условий ваших договоров, поэтому числа вводите вы."),
    h("div", { class: "calc-grid" }, fields), h("button", { class: "btn dark sm", onClick: run }, "Рассчитать"), out);
}
export function calcResult(r) {
  const unit = r.unit || "";
  return h("div", { class: "stack", style: { marginTop: "14px" } },
    h("div", { class: "calc-res" }, h("span", { class: "small muted" }, "Результат"), h("b", { class: "num" }, fmt.money(r.result), r.share_of_revenue_pct != null ? h("span", { class: "small muted" }, ` · ${r.share_of_revenue_pct.toFixed(2)}% выручки`) : null,
      r.share_of_revenue_pp != null ? h("span", { class: "small muted" }, ` · ${r.share_of_revenue_pp.toFixed(2)} п.п. выручки`) : null), h("span", { class: "small muted" }, unit)),
    h("div", { class: "small" }, h("b", null, "Формула: "), r.formula), h("ul", { class: "list" }, r.steps.map((s) => h("li", { class: "num" }, s))),
    h("div", { class: "small muted" }, h("b", null, "Допущения: "), r.assumptions.join("; ") + "."));
}

export function feedbackBar(iid) {
  const wrap = h("div", { class: "row" });
  const kinds = [["useful", "Полезно"], ["irrelevant", "Не относится к нам"], ["wrong", "Есть ошибка"], ["duplicate", "Дублирует другое"]];
  const set = async (k, b) => {
    try { await api(`/api/insights/${iid}/feedback`, { method: "POST", body: { kind: k } }); [...wrap.querySelectorAll("button")].forEach((x) => x.setAttribute("aria-pressed", String(x === b))); toast("Спасибо, оценка сохранена и попадёт в мониторинг качества"); } catch (e) { toast(e.message); }
  };
  kinds.forEach(([k, l]) => { const b = h("button", { class: "chip", "aria-pressed": "false", onClick: () => set(k, b) }, l); wrap.append(b); });
  return wrap;
}

export function chatBox(ins) {
  const msgs = h("div", { class: "msgs" });
  const input = h("input", { class: "input", placeholder: "Например: что если ставка вырастет на 2 п.п. при долге 5 млрд?", "aria-label": "Вопрос по событию", maxlength: 600 });
  const render = (a, meta) => {
    const box = h("div", { class: "m-bot" });
    (a.answer || a).forEach((x) => box.append(claim(ins, { id: "", type: x.type, text: x.text, evidence: x.evidence, origin: "rules" })));
    (a.blocks || meta?.blocks || []).forEach((b) => {
      if (b.type === "table") box.append(h("div", { class: "card flat tight" }, h("b", null, b.title), h("table", { class: "tbl" }, h("thead", null, h("tr", null, Object.keys(b.rows[0] || {}).map((k) => h("th", null, k)))), h("tbody", null, b.rows.map((r) => h("tr", null, Object.values(r).map((v) => h("td", null, v))))))));
      if (b.type === "calc") box.append(h("div", { class: "card flat tight" }, calcResult(b.result)));
      if (b.type === "form") box.append(calcWidget(b.calc, ins.company_id));
    });
    return box;
  };
  const send = async (q) => {
    q = (q || input.value).trim();
    if (q.length < 3) return;
    input.value = "";
    msgs.append(h("div", { class: "m-user" }, q));
    const wait = h("div", { class: "skel", style: { height: "56px" } });
    msgs.append(wait);
    msgs.scrollTop = msgs.scrollHeight;
    try {
      const r = await api(`/api/insights/${ins.insight_id}/chat`, { method: "POST", body: { question: q } });
      Object.assign(ins.evidence, r.evidence || {});
      wait.replaceWith(render(r));
    } catch (e) { wait.replaceWith(h("div", { class: "err" }, e.message)); }
    msgs.scrollTop = msgs.scrollHeight;
  };
  input.addEventListener("keydown", (e) => e.key === "Enter" && send());
  api(`/api/insights/${ins.insight_id}/chat`).then((r) => r.messages.forEach((m) => msgs.append(m.role === "user" ? h("div", { class: "m-user" }, m.content) : render({ answer: m.content, blocks: m.meta.blocks })))).catch(() => {});
  const sugg = ["Почему это важно для нас?", "На основании каких данных о компании?", "Каких данных не хватает?", "Что говорит банк?", "Покажи в разрезе контрагентов"];
  return h("div", { class: "chat" }, msgs, h("div", { class: "suggest" }, sugg.map((s) => h("button", { class: "chip", onClick: () => send(s) }, s))),
    h("div", { class: "compose" }, input, h("button", { class: "btn dark", onClick: () => send(), "aria-label": "Отправить" }, icon("send", 18))));
}

export function agentProgress(steps) {
  const items = steps.map((s, i) => h("div", { class: "al", style: { "--i": i } }, h("i"), s));
  const box = h("div", { class: "agent-live card flat" }, h("b", null, "Агент работает"), ...items);
  let i = 0;
  const t = setInterval(() => { if (items[i]) { items[i].classList.add("on"); if (i) items[i - 1].classList.add("done"); } i++; if (i > items.length) clearInterval(t); }, 420);
  box.stop = () => { clearInterval(t); items.forEach((x) => x.classList.add("on", "done")); };
  return box;
}

import { h, icon, fmt, FACTOR, PRIORITY, CONF, mount } from "../dom.js";
import { api } from "../api.js";
import { S } from "../state.js";
import { flow } from "../charts.js";
import { prio, kindLab, demoPill, claim, cites, showEvidence, showTrace, gauge, calcWidget, chatBox, feedbackBar, agentProgress, toast, drawer, evidenceView } from "../ui.js";

const STEPS = ["Загружаю профиль компании и признаки", "Читаю событие и источники", "Оцениваю платёжные связи и контрагентов", "Сопоставляю сигналы с экспозицией компании", "Ищу позицию банка в аналитике", "Собираю утверждения с основаниями", "Проверяю основания, числа и атрибуцию"];

export const insightView = (kind) => async ({ params, go }) => {
  const box = h("div");
  const prog = agentProgress(STEPS);
  mount(box, h("button", { class: "crumb", onClick: () => history.length > 1 ? history.back() : go("#/radar") }, icon("back", 18), "Назад"), prog);
  (async () => {
    try {
      const url = kind === "event" ? `/api/companies/${S.companyId}/events/${params[0]}/insight?role=${S.role}` : `/api/insights/${params[0]}`;
      const ins = await api(url);
      prog.stop();
      setTimeout(() => mount(box, render(ins, go, () => go(location.hash))), 250);
    } catch (e) { mount(box, h("div", { class: "card" }, h("h2", null, "Не удалось подготовить анализ"), h("p", { class: "muted", style: { margin: "8px 0 16px" } }, e.message), h("a", { class: "btn dark", href: "#/radar" }, "К ленте"))); }
  })();
  return box;
};

const sec = (title, ...kids) => h("section", { class: "sec rise" }, h("div", { class: "lab" }, title), ...kids);

export function render(ins, go, reload) {
  const C = Object.fromEntries(ins.claims.map((c) => [c.id, c]));
  const get = (ids) => (ids || []).map((i) => C[i]).filter(Boolean);
  const cascade = ins.kind === "cascade";
  const gen = ins.ai_view.generated_by;
  const llmClaims = get(ins.ai_view.claim_ids).filter((c) => c.type === "AI_INFERENCE");
  const unknown = get(ins.unknown_ids);
  const synthBank = ins.bank_view.synthetic;
  const head = h("div", { class: "ins-head" },
    h("button", { class: "crumb", onClick: () => history.length > 1 ? history.back() : go("#/radar") }, icon("back", 18), "Назад"),
    h("div", { class: "row" }, prio(ins.priority), cascade ? h("span", { class: "pill p-medium" }, "Каскад сигналов") : null, h("span", { class: "pill p-medium", title: "Насколько хорошо подтверждён вывод" }, `Уверенность: ${CONF[ins.confidence]}`), Object.values(ins.evidence).some((e) => e.is_synthetic) ? h("span", { class: "pill demo", title: "Часть оснований — синтетические демонстрационные материалы" }, "в основаниях есть демо-материалы") : null, ins.version > 1 ? h("span", { class: "tiny faint" }, `версия ${ins.version}`) : null),
    h("h1", null, ins.title), h("p", { class: "muted" }, `${ins.event_title}${ins.what_happened.date ? " · " + fmt.dateFull(ins.what_happened.date) : ""}`),
    h("div", { class: "row" }, ins.run_id ? h("button", { class: "btn sm", onClick: () => showTrace(ins.run_id) }, icon("trace", 16), "Как это получено") : null,
      ins.kind === "event" ? h("button", { class: "btn sm ghost", onClick: async () => { toast("Анализ пересчитывается…"); await api(`/api/companies/${ins.company_id}/events/${ins.event_ids[0]}/insight?role=${S.role}&refresh=1`); reload(); } }, icon("clock", 16), "Пересчитать") : null));

  const summary = sec("Коротко",
    h("div", { class: "ai-box" }, h("div", { class: "tg row", style: { marginBottom: "8px" } }, h("span", { class: "tag faint" }, "Вывод AI"), h("span", { class: "tiny faint" }, gen.startsWith("llm") ? `сформулировано моделью, каждый пункт проверен по основаниям` : "собрано по правилам из проверенных данных")),
      gen.startsWith("llm") && llmClaims.length ? llmClaims.map((c) => h("p", { style: { marginBottom: "8px" } }, c.text, cites(ins, c.evidence))) : h("p", null, ins.ai_view.narrative)));

  const what = sec("Что произошло",
    ...get(ins.what_happened.claim_ids).map((c) => claim(ins, c)),
    ins.contradictions.length ? h("div", { class: "notice red" }, icon("alert", 20), h("span", null, h("b", null, "Источники расходятся. "), ins.contradictions.map((x) => `${FACTOR[x.factor] || x.factor}: ${x.note}`).join(" "))) : null,
    ins.related?.length ? h("div", { class: "small", style: { marginTop: "10px" } }, h("div", { class: "muted", style: { marginBottom: "4px" } }, "Связанные события"), h("ul", { class: "list" }, ins.related.map((r) => h("li", null, h("a", { href: `#/event/${r.event_id}` }, r.title))))) : null);

  const why = sec("Почему это важно для вашей компании",
    ...get(ins.why_you.fact_ids).map((c) => claim(ins, c)), ...get(ins.why_you.inference_ids).map((c) => claim(ins, c)),
    !ins.why_you.fact_ids.length && !ins.why_you.inference_ids.length ? h("p", { class: "muted" }, "Связь с профилем компании по доступным данным не установлена.") : null);

  const chain = ins.chain.nodes.length > 1 ? sec(cascade ? "Как сигналы сходятся" : "Цепочка влияния", h("div", { class: "card flat tight" }, flow(ins.chain, { width: 940 }),
    h("p", { class: "tiny faint", style: { marginTop: "8px" } }, "Пунктир — признак компании, сплошная — расчётное звено. Веса связей — структурные допущения модели, а не оценка для вашей компании."))) : null;

  const scen = sec("Возможные последствия",
    ...ins.scenarios.map((s) => h("div", { class: `scen ${s.kind}` }, h("div", { class: "row between" }, kindLab(s.kind), h("span", { class: "tiny faint" }, `горизонт: ${s.horizon} · опора на данные ${Math.round(s.evidence_share * 100)}%`)),
      h("h3", null, s.title), h("p", null, s.how, " ", s.outcome, cites(ins, C[s.claim_id]?.evidence)),
      h("details", null, h("summary", null, "Условия и что не установлено"), s.conditions.length ? h("div", { class: "small" }, h("b", null, "При каких условиях: "), h("ul", { class: "list" }, s.conditions.map((x) => h("li", null, x)))) : null, s.unknowns.length ? h("div", { class: "small" }, h("b", null, "Чего не хватает: "), h("ul", { class: "list" }, s.unknowns.map((x) => h("li", null, x)))) : null))));

  const bank = sec("Как это оценивает банк",
    ins.bank_view.claim_ids.length ? [synthBank ? h("div", { class: "notice", style: { marginBottom: "10px" } }, icon("info", 20), h("span", null, "Это учебные образцы, а не публикации Альфа-Банка. Оригинальные материалы загружаются в раздел «Источники»; интерфейс и логика те же.")) : null, ...get(ins.bank_view.claim_ids).map((c) => claim(ins, c))] :
      h("div", { class: "claim t-unk" }, h("div", { class: "tg" }, h("span", { class: "tag" }, "Не установлено")), h("p", null, "В материалах Альфа-Банка нет аналитики, прямо относящейся к этому событию. Позиция банка не придумывается — вывод выше сформирован системой.")),
    h("p", { class: "tiny faint", style: { marginTop: "6px" } }, "Красная линия — позиция банка из его материалов; пунктир — вывод AI; точки — сценарий; штриховка — данных нет."));

  const checks = sec("Что стоит проверить", h("div", { class: "checks" }, ins.checks.slice(0, 6).map((c) => h("div", { class: "check" }, h("div", null, c.text, h("div", { class: "tiny faint" }, c.headline))))));
  const calcs = ins.calc_specs?.length ? sec("Оценка чувствительности", h("div", { class: "grid" }, ins.calc_specs.map((s) => calcWidget(s, ins.company_id)))) : null;
  const unk = sec("Чего не хватает для точного вывода", h("div", { class: "row", style: { marginBottom: "12px", alignItems: "flex-start" } }, gauge(ins.sufficiency.score, "достаточность данных"), h("p", { class: "small muted", style: { flex: 1, minWidth: "220px" } }, "Чем больше данных о долге, контрактах и валютной структуре, тем точнее вывод. Недостающее ниже не заменяется предположениями.")), ...unknown.map((c) => claim(ins, c)));
  const offers = ins.offers?.length ? sec("Решения банка по теме", ins.offers.map((o) => h("div", { class: "card flat tight" }, h("div", { class: "row between" }, h("b", null, o.title), h("span", { class: "pill p-watch" }, o.label)), h("p", { class: "small muted", style: { marginTop: "6px" } }, o.text)))) : null;
  const ev = sec("Основания", h("div", { class: "row" }, Object.values(ins.evidence).filter((e) => e.type === "news" || e.type === "bank").map((e) => h("button", { class: "chip", onClick: () => drawer(e.title, evidenceView(e)) }, (e.type === "bank" ? "Аналитика банка: " : "") + e.title.slice(0, 54)))));

  const reasons = h("div", { class: "card tight" }, h("h3", null, "Почему система выделила это"), h("div", { class: "stack", style: { marginTop: "10px" } }, ins.reasons.filter((r) => r.points > 0).map((r) => h("div", { class: "row between small" }, h("span", null, r.label), h("b", { class: "num" }, `+${r.points}`)))),
    h("div", { class: "row", style: { marginTop: "12px" } }, h("b", { class: "num", style: { fontSize: "26px" } }, Math.round(ins.importance)), h("span", { class: "small muted" }, "значимость из 100; уверенность отдельно: " + CONF[ins.confidence])));
  const verif = ins.verification;
  const ver = h("div", { class: "card tight" }, h("h3", null, "Самопроверка"), h("p", { class: "small muted", style: { margin: "6px 0 10px" } }, `Проверено утверждений: ${ins.claims.length}. Итераций: ${verif.iterations}, корректировок: ${verif.replans}. ${verif.issues.length ? "Остаточных замечаний: " + verif.issues.length + "." : "Замечаний нет."}`),
    ...verif.issues.slice(0, 4).map((i) => h("div", { class: "tiny muted" }, `• ${i.detail}`)), ins.run_id ? h("button", { class: "btn sm", style: { marginTop: "10px" }, onClick: () => showTrace(ins.run_id) }, "Открыть трассу") : null);

  return h("div", { class: "cols" },
    h("div", null, head, summary, what, why, chain, scen, bank, checks, calcs, unk, offers, ev),
    h("aside", { class: "stack", style: { position: "sticky", top: "84px" } }, reasons, h("div", { class: "card tight" }, h("h3", { style: { marginBottom: "10px" } }, "Спросить по этому событию"), chatBox(ins)), ver,
      h("div", { class: "card tight" }, h("h3", { style: { marginBottom: "10px" } }, "Оцените результат"), feedbackBar(ins.insight_id))));
}

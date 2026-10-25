import { h, fmt } from "../dom.js";
import { api } from "../api.js";
import { bars } from "../charts.js";

const NAMES = { metal: "Металлургический холдинг", trade: "Торговый дом", agro: "Агрохолдинг", build: "Строительная группа", digital: "Цифровая платформа", mining: "Горнодобывающая компания" };

export async function qualityView() {
  const [m, ev] = await Promise.all([api("/api/metrics"), api("/api/evaluation")]);
  const pct = (v) => (v == null ? "—" : Math.round(v * 100) + "%");
  const tile = (label, val, hint) => h("div", { class: "card tight kpi rise", title: hint }, h("b", { class: "num" }, val), h("span", null, label));
  const e = ev.mean || {};
  const claimTypes = { FACT: "Факт", BANK_ANALYSIS: "Позиция банка", AI_INFERENCE: "Вывод AI", SCENARIO: "Сценарий", UNKNOWN: "Не установлено" };
  return h("div", { class: "stack", style: { gap: "20px" } },
    h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Качество и прозрачность"), h("p", null, "Метрики контента, персонализации и AI-компонентов. Оценки экспертов в прототипе синтетические: они показывают, как измеряется качество, а не реальный уровень на клиентских данных."))),
    h("h3", null, "Персонализация и ранжирование"),
    h("div", { class: "kpis" }, tile("Precision@5", pct(e.precision_at_5), "Доля значимых событий среди первых пяти"), tile("nDCG@5", pct(e.ndcg_at_5), "Качество порядка"), tile("Recall@10", pct(e.recall_at_10), "Доля значимых событий в первой десятке"), tile("Пересечение топ-5 у разных компаний", pct(e.top5_overlap_between_companies), "Чем ниже, тем сильнее персонализация")),
    h("div", { class: "card" }, h("div", { class: "row between" }, h("b", null, "Precision@5 по компаниям"), h("span", { class: "small muted" }, "Precision@5, эксперты: событие значимо при оценке 2–3")), h("div", { style: { marginTop: "14px" } }, bars(ev.companies.map((c) => ({ label: NAMES[c.company] || c.company, value: c.p5, text: pct(c.p5), cls: "red", hint: `Хронологическая лента: ${pct(c.baseline_p5)}` })))),
      h("p", { class: "small muted", style: { marginTop: "10px" } }, `Радар: Precision@5 = ${pct(e.precision_at_5)}. Случайная лента (доля значимых в корпусе): ${pct(e.random_precision_at_5)}. Хронологическая лента: ${pct(e.baseline_precision_at_5)} (пять самых свежих событий). Корпус небольшой, поэтому абсолютные числа ориентировочные. Дублей карточек в топ-10: ${e.duplicate_pairs_in_top10}. ${ev.note || ""}`)),
    h("h3", null, "Достоверность и AI-компоненты"),
    h("div", { class: "kpis" }, tile("Утверждений с основанием", pct(m.insights.evidence_coverage)), tile("Прошли самопроверку", pct(m.insights.verification_pass_rate)), tile("Раскрыты ограничения", pct(m.insights.with_disclosed_unknowns)), tile("Полезных оценок", pct(m.feedback.useful_rate), `Всего оценок: ${m.feedback.total}`)),
    h("div", { class: "grid g2" },
      h("div", { class: "card" }, h("h3", null, "Структура утверждений"), h("div", { style: { marginTop: "12px" } }, bars(Object.entries(m.insights.claim_types).map(([k, v]) => ({ label: claimTypes[k] || k, value: v, text: v, cls: k === "BANK_ANALYSIS" ? "red" : "" }))))),
      h("div", { class: "card" }, h("h3", null, "Работа агента"), h("div", { class: "feat" }, [["Запусков", m.agent.runs], ["Среднее время", fmt.time(m.agent.avg_ms)], ["Перепланирований", m.agent.replans], ["Вызовов модели", m.agent.llm_calls], ["Токенов", m.agent.tokens], ["Ошибок", m.agent.errors], ["Режим модели", m.llm.configured ? m.llm.deep : "детерминированный"]].map(([a, b]) => h("div", null, h("span", null, a), h("span", { class: "num" }, b)))))),
    h("div", { class: "grid g2" },
      h("div", { class: "card" }, h("h3", null, "Корпус материалов"), h("div", { class: "feat" }, [["Документов", m.corpus.docs], ["Событий после дедупликации", m.corpus.events], ["Подтверждено несколькими источниками", m.corpus.multi_source_events], ["Событий с расхождением источников", m.corpus.contradictions], ["Документов с инъекциями (обезврежены)", m.corpus.injection_blocked], ["Компаний в данных", m.corpus.companies]].map(([a, b]) => h("div", null, h("span", null, a), h("span", { class: "num" }, b))))),
      h("div", { class: "card" }, h("h3", null, "Безопасность"), h("div", { class: "feat" }, [["Записей журнала аудита", m.security.audit_events], ["Отклонённых обращений", m.security.denied]].map(([a, b]) => h("div", null, h("span", null, a), h("span", { class: "num" }, b)))), h("p", { class: "small muted", style: { marginTop: "12px" } }, "Права проверяются на сервере при каждом вызове инструмента; обращения агента к данным и отказы пишутся в журнал."))));
}

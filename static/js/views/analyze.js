import { h, icon, mount } from "../dom.js";
import { api } from "../api.js";
import { S } from "../state.js";
import { agentProgress } from "../ui.js";
import { render } from "./insight.js";

const SAMPLE = "Минфин предложил ввести повышенные экспортные пошлины на минеральные удобрения. Ожидается, что решение вступит в силу со следующего квартала, цены на удобрения на внутреннем рынке могут снизиться на 4%, а экспортёры потеряют часть выручки.";

export async function analyzeView({ go }) {
  const title = h("input", { class: "input", placeholder: "Заголовок (необязательно)" });
  const url = h("input", { class: "input", placeholder: "https://… ссылка на статью (необязательно)", inputmode: "url" });
  const text = h("textarea", { class: "input", placeholder: "Вставьте текст новости или аналитической заметки…", "aria-label": "Текст материала" });
  const out = h("div");
  const run = async (btn) => {
    btn.disabled = true;
    const prog = agentProgress(["Извлекаю события, сигналы, даты и участников", "Определяю отрасли, регионы и страны", "Сопоставляю с профилем компании", "Ищу позицию банка", "Проверяю результат"]);
    mount(out, prog);
    try {
      const r = await api(`/api/companies/${S.companyId}/analyze`, { method: "POST", body: { title: title.value, text: text.value, url: url.value || null, role: S.role } });
      prog.stop();
      if (!r.relevant) mount(out, h("div", { class: "card" }, h("h2", null, "Прямой связи с вашей компанией не найдено"), h("p", { class: "muted", style: { margin: "8px 0" } }, r.message),
        h("div", { class: "row", style: { margin: "12px 0" } }, r.signals.map((s) => h("span", { class: "chip" }, `${s.factor}: ${s.direction}`)), r.sectors.map((s) => h("span", { class: "chip" }, "отрасль: " + s))),
        r.injection.length ? h("div", { class: "notice red" }, icon("alert", 20), h("span", null, "В тексте найдены фрагменты, похожие на инструкции для ИИ. Они исключены из анализа и не выполнялись.")) : null));
      else mount(out, r.insight ? render(r.insight, go, () => go(location.hash)) : null);
    } catch (e) { mount(out, h("div", { class: "err" }, e.message)); }
    btn.disabled = false;
  };
  return h("div", { class: "stack", style: { gap: "20px" } },
    h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Проверить новость"), h("p", null, "Вставьте любой материал, которого нет в ленте: система извлечёт события, сопоставит их с вашей компанией и покажет, влияют ли они на бизнес и почему. Заранее подготовленных сценариев нет."))),
    h("div", { class: "card stack" }, title, url, text, h("div", { class: "row" }, h("button", { class: "btn primary", onClick: (e) => run(e.target) }, "Проанализировать"), h("button", { class: "btn ghost", onClick: () => { text.value = SAMPLE; title.value = "Экспортные пошлины на удобрения"; } }, "Подставить пример"))), out);
}

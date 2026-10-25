import { h, icon, fmt, mount } from "../dom.js";
import { api } from "../api.js";
import { S } from "../state.js";
import { demoPill, toast } from "../ui.js";

export async function libraryView({ rerender }) {
  const lib = await api("/api/library");
  const admin = S.me.user.is_admin;
  const kind = h("select", { class: "sel inline" }, h("option", { value: "bank_analysis" }, "Аналитика Альфа-Банка"), h("option", { value: "news" }, "Новость / внешний материал"));
  const file = h("input", { type: "file", class: "input", accept: ".pdf,.docx,.md,.txt,.csv" });
  const feed = h("input", { class: "input", placeholder: "https://…/rss.xml", inputmode: "url" });
  const msg = h("div", { class: "small muted", "aria-live": "polite" });
  const up = async () => {
    if (!file.files[0]) return toast("Выберите файл");
    const fd = new FormData(); fd.append("file", file.files[0]); fd.append("kind", kind.value);
    msg.textContent = "Обработка…";
    try { const r = await api("/api/library/upload", { method: "POST", form: fd }); msg.textContent = r.dataset ? `Загружено (${r.dataset}): ${r.imported}` : `Загружено: фрагментов ${r.chunks}`; setTimeout(rerender, 900); } catch (e) { msg.textContent = e.message; }
  };
  const pull = async () => { msg.textContent = "Читаю ленту…"; try { const r = await api("/api/library/feed", { method: "POST", body: { url: feed.value } }); msg.textContent = `Новых материалов: ${r.added}, пропущено: ${r.skipped}`; setTimeout(rerender, 900); } catch (e) { msg.textContent = e.message; } };
  const group = (title, rows) => h("div", { class: "card" }, h("h3", null, title), rows.length ? rows.map((d) => h("div", { class: "docrow" }, h("div", null, h("b", null, d.title), h("div", { class: "small muted" }, `${d.source_name} · ${fmt.dateFull(d.published_at)}`), d.injection_findings ? h("div", { class: "tiny", style: { color: "var(--red)" } }, `Из текста исключено фрагментов, похожих на инструкции для ИИ: ${d.injection_findings}`) : null), h("div", { class: "row" }, demoPill(d.is_synthetic), d.url && !d.url.includes("demo.invalid") ? h("a", { class: "btn sm", href: d.url, target: "_blank", rel: "noopener noreferrer" }, icon("link", 14)) : null))) : h("p", { class: "muted" }, "Нет материалов"));
  return h("div", { class: "stack", style: { gap: "20px" } },
    h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Источники"), h("p", null, "Всё, на чём строятся выводы. Аналитика банка хранится отдельно от внешних новостей, чтобы позиция банка не смешивалась с синтезом AI."))),
    h("div", { class: "notice" }, icon("info", 20), h("span", null, lib.llm.configured ? `Языковая модель подключена: ${lib.llm.light} (извлечение, ответы) и ${lib.llm.deep} (интерпретация). Токенов сегодня: ${lib.llm.tokens_today}.` : "Языковая модель не подключена: работает детерминированный режим — извлечение, ранжирование, цепочки и проверки по правилам. Укажите LLM_API_BASE_URL и LLM_API_KEY, чтобы включить модельную интерпретацию.")),
    admin ? h("div", { class: "card stack" }, h("h3", null, "Добавить материалы"), h("div", { class: "grid g2" }, h("div", { class: "stack" }, h("div", { class: "row" }, kind, file, h("button", { class: "btn dark", onClick: up }, icon("upload", 16), "Загрузить")), h("p", { class: "tiny faint" }, "PDF, DOCX, MD, TXT. CSV в формате конкурсного набора (компании, физлица, платежи) определяется автоматически.")),
      h("div", { class: "stack" }, h("div", { class: "row" }, feed, h("button", { class: "btn", onClick: pull }, "Собрать RSS")), h("p", { class: "tiny faint" }, "Только HTTPS; внутренние адреса блокируются, ответы ограничены по размеру."))), msg) : null,
    h("div", { class: "grid g2" }, group(`Аналитика Альфа-Банка · ${lib.counts.bank}`, lib.docs.filter((d) => d.kind === "bank_analysis")), group(`Внешние новости · ${lib.counts.news}`, lib.docs.filter((d) => d.kind === "news").slice(0, 40))));
}

import { h, fmt, mount } from "../dom.js";
import { api } from "../api.js";
import { S } from "../state.js";
import { egoNetwork, bars } from "../charts.js";
import { drawer } from "../ui.js";

export async function networkView({ refreshFeed }) {
  const [net, feed] = await Promise.all([api(`/api/companies/${S.companyId}/network`), refreshFeed()]);
  const g = feed.company.graph;
  const detail = (n) => drawer(n.name || "Компания", h("div", { class: "stack" }, h("p", { class: "muted" }, n.okved_name || "Вид деятельности не указан"), h("p", null, n.in_group ? "Входит в вашу группу компаний." : "Не входит в вашу группу."), h("p", { class: "small muted" }, "Наличие платежей не означает договорной зависимости: даты и условия расчётов в данных отсутствуют.")));
  return h("div", { class: "stack", style: { gap: "20px" } },
    h("div", { class: "page-head", style: { marginBottom: 0 } }, h("div", null, h("h1", null, "Платёжные связи"), h("p", null, "Наблюдаемое окружение компании по агрегированным платежам. Используется, чтобы находить косвенные связи с событиями: через отрасли ваших контрагентов."))),
    net.nodes.length > 1 ? h("div", { class: "card" }, egoNetwork(net, { onNode: detail }), h("p", { class: "tiny faint" }, "Толщина линии — доля в потоке платежей. " + (g?.caveat || ""))) : h("div", { class: "card empty" }, "Платёжных связей этой компании в данных нет."),
    g && g.available ? h("div", { class: "grid g2" }, side("Получатели платежей компании", "вероятные поставщики", g.recipients), side("Плательщики компании", "вероятные покупатели", g.payers)) : null);
}
const side = (title, sub, s) => h("div", { class: "card" }, h("h3", null, title), h("p", { class: "small muted", style: { marginBottom: "14px" } }, `${sub}; контрагентов: ${s.n}`),
  s.n ? [h("div", { class: "row small", style: { marginBottom: "12px" } }, h("span", null, "Крупнейший: ", h("b", null, fmt.pct(s.top1_share))), h("span", null, "Три крупнейших: ", h("b", null, fmt.pct(s.top3_share))), h("span", null, "Внутри группы: ", h("b", null, fmt.pct(s.intra_group_share)))),
    h("div", { class: "small muted", style: { marginBottom: "6px" } }, "Отрасли контрагентов"), bars(Object.entries(s.sectors).slice(0, 6).map(([k, v]) => ({ label: SECT[k] || k, value: v, text: fmt.pct(v) })))] : h("p", { class: "muted" }, "Нет данных"));
const SECT = { agri: "Сельское хозяйство", mining_energy: "Нефть, газ, уголь", mining_metals: "Добыча руд", food: "Пищевая пром.", light: "Лёгкая пром.", wood_paper: "Дерево и бумага", refining: "Нефтепереработка", chem_pharma: "Химия, фарма", build_materials: "Стройматериалы", metallurgy: "Металлургия", machinery: "Машиностроение", other_mfg: "Прочее произв.", energy_util: "Энергетика, ЖКХ", construction: "Строительство", trade: "Торговля", transport: "Транспорт", hospitality: "Гостиницы, общепит", it_telecom: "ИТ и связь", finance: "Финансы", real_estate: "Недвижимость", prof_services: "Проф. услуги", admin_support: "Адм. услуги", public_social: "Гос. сектор", other: "Прочее" };

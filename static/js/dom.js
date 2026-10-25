const SVGNS = "http://www.w3.org/2000/svg";
const SVG_TAGS = new Set(["svg", "g", "path", "circle", "rect", "line", "text", "tspan", "defs", "marker", "polygon", "polyline", "title", "ellipse", "linearGradient", "stop", "clipPath", "pattern"]);

export function h(tag, attrs, ...kids) {
  const svg = SVG_TAGS.has(tag);
  const el = svg ? document.createElementNS(SVGNS, tag) : document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") el.setAttribute("class", v);
      else if (k === "style" && typeof v === "object") for (const [p, val] of Object.entries(v)) p.startsWith("--") ? el.style.setProperty(p, val) : (el.style[p] = val);
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "html") el.innerHTML = v;
      else if (v === true) el.setAttribute(k, "");
      else el.setAttribute(k, v);
    }
  }
  append(el, kids);
  return el;
}
function append(el, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false) continue;
    el.append(k.nodeType ? k : document.createTextNode(String(k)));
  }
}
export const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
export const mount = (el, ...kids) => { clear(el); append(el, kids); return el; };

const ICONS = {
  home: "M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10",
  radar: "M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6.5-6.5M12 12h.01",
  wallet: "M4 7.5A2.5 2.5 0 0 1 6.5 5H19v3.5M4 7.5V17a2 2 0 0 0 2 2h13.5V8.5H6.5A2.5 2.5 0 0 1 4 7.5ZM16 13.5h.01",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 19.5c.5-3.2 3-5 6.5-5s6 1.8 6.5 5M16.5 5a3 3 0 0 1 0 6M18 14.5c2 .5 3.200 2 3.500 5",
  bank: "M3 9.5 12 4l9 5.5M5 10.5V18M9.5 10.5V18M14.5 10.5V18M19 10.5V18M3.5 20h17",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3 12h18M12 3c2.500 2.500 3.500 5.500 3.500 9S14.500 18.500 12 21c-2.500-2.500-3.500-5.500-3.500-9S9.500 5.500 12 3Z",
  chart: "M4 19.500V5M4 19.500h16M8 16v-4M12 16V8M16 16v-6",
  shield: "M12 3 4.500 6v5.500c0 4.500 3 7.800 7.500 9.500 4.500-1.700 7.500-5 7.500-9.500V6L12 3Z",
  file: "M7 3.500h7l4 4V20a.5.5 0 0 1-.5.500h-10.500A.5.5 0 0 1 6.500 20V4a.5.5 0 0 1 .5-.5ZM14 3.500v4h4M9 12h6M9 15.500h6",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-4-4",
  alert: "M12 4 3 19.500h18L12 4ZM12 10v4.500M12 17h.01",
  arrow: "M5 12h14M13 6l6 6-6 6",
  back: "M19 12H5M11 6l-6 6 6 6",
  check: "m5 12.500 4.500 4.500L19 7.500",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 8h.01",
  link: "M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1",
  network: "M12 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM5.500 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM18.500 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM10.500 8.800 6.800 15.200M13.500 8.800l3.700 6.400",
  layers: "m12 4 9 5-9 5-9-5 9-5ZM3 14l9 5 9-5",
  close: "M6 6l12 12M18 6 6 18",
  send: "M4 12 20 4l-4 16-4.500-6.500L4 12ZM11.500 13.500 20 4",
  up: "M12 19V5M6 11l6-6 6 6",
  logout: "M14 4h4.500a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H14M10 8l-4 4 4 4M6 12h10",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
  trace: "M5 6h4v4H5zM15 14h4v4h-4zM9 8h3a3 3 0 0 1 3 3v3",
  flask: "M9.500 3.500h5M10.500 3.500v6L5 19a1.500 1.500 0 0 0 1.300 2.200h11.400A1.500 1.500 0 0 0 19 19l-5.500-9.500v-6",
  thumbs: "M7 11v8.500H4V11h3ZM7 11l3.500-7a2 2 0 0 1 3 1.800L13 9h5.500a2 2 0 0 1 2 2.400l-1.300 6.500a2 2 0 0 1-2 1.600H7",
};
export function icon(name, size = 20, cls = "") {
  return h("svg", { viewBox: "0 0 24 24", width: size, height: size, class: "ico " + cls, "aria-hidden": "true", fill: "none", stroke: "currentColor", "stroke-width": "1.7", "stroke-linecap": "round", "stroke-linejoin": "round" },
    h("path", { d: ICONS[name] || ICONS.info }));
}

export const fmt = {
  money(v) {
    if (v == null) return "—";
    const a = Math.abs(v), s = v < 0 ? "−" : "";
    if (a >= 1e12) return s + (a / 1e12).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "\u00a0трлн\u00a0₽";
    if (a >= 1e9) return s + (a / 1e9).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "\u00a0млрд\u00a0₽";
    if (a >= 1e6) return s + (a / 1e6).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "\u00a0млн\u00a0₽";
    return s + Math.round(a).toLocaleString("ru-RU") + "\u00a0₽";
  },
  pct(v, d = 0) { return v == null ? "—" : (v * 100).toLocaleString("ru-RU", { maximumFractionDigits: d }) + "%"; },
  date(iso) {
    if (!iso) return "";
    const d = new Date(iso), n = new Date();
    const days = Math.floor((n - d) / 864e5);
    if (days <= 0) return "сегодня";
    if (days === 1) return "вчера";
    if (days < 8) return `${days} дн. назад`;
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  },
  dateFull(iso) { return iso ? new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" }) : ""; },
  time(ms) { return ms < 1000 ? ms + " мс" : (ms / 1000).toFixed(1) + " с"; },
};
export const FACTOR = {
  rate: "Ставки и кредит", inflation: "Инфляция", input_costs: "Затраты", fx: "Курс", foreign_trade: "Внешняя торговля", logistics: "Логистика",
  demand: "Спрос", labor: "Рынок труда", regulation: "Регулирование", commodity: "Сырьё и цены", competition: "Конкуренция", tech: "Киберриски", liquidity: "Финансирование", cascade: "Каскад",
};
export const PRIORITY = { critical: "Критический", high: "Высокий", medium: "Средний", watch: "Наблюдение" };
export const CONF = { high: "высокая", medium: "средняя", low: "низкая" };
export const CLAIM = {
  FACT: ["Факт", "t-fact"], BANK_ANALYSIS: ["Позиция банка", "t-bank"], AI_INFERENCE: ["Вывод AI", "t-ai"], SCENARIO: ["Сценарий", "t-scen"], UNKNOWN: ["Не установлено", "t-unk"],
};

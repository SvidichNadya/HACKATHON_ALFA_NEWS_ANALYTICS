import { h, FACTOR } from "./dom.js";

const AXES = ["rate", "input_costs", "fx", "foreign_trade", "logistics", "demand", "labor", "regulation"];

/** Exposure radar: sensitivity of the company to each factor. Provenance of the number is in the tooltip. */
export function exposureRadar(sens, size = 300) {
  const c = size / 2, r = size / 2 - 46;
  const pt = (i, v) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / AXES.length; return [c + Math.cos(a) * r * v, c + Math.sin(a) * r * v]; };
  const grid = [0.25, 0.5, 0.75, 1].map((lv) => h("polygon", { class: "rd-grid", points: AXES.map((_, i) => pt(i, lv).join(",")).join(" ") }));
  const spokes = AXES.map((_, i) => { const [x, y] = pt(i, 1); return h("line", { class: "rd-spoke", x1: c, y1: c, x2: x, y2: y }); });
  const vals = AXES.map((k) => (sens[k] ? sens[k].value : 0));
  const poly = h("polygon", { class: "rd-area", points: vals.map((v, i) => pt(i, Math.max(v, 0.04)).join(",")).join(" ") });
  const dots = AXES.map((k, i) => {
    const [x, y] = pt(i, Math.max(vals[i], 0.04));
    const parts = (sens[k]?.parts || []).filter((p) => p.delta > 0.06).map((p) => `${p.kind === "observed" ? "● " : "○ "}${p.label} (+${p.delta.toFixed(2)})`).join("\n");
    return h("circle", { class: "rd-dot", cx: x, cy: y, r: 4.5, tabindex: 0 }, h("title", null, `${FACTOR[k]}: ${vals[i].toFixed(2)}\n${parts}`));
  });
  const labels = AXES.map((k, i) => {
    const [x, y] = pt(i, 1.2);
    const anchor = Math.abs(x - c) < 8 ? "middle" : x > c ? "start" : "end";
    return h("text", { class: "rd-label", x, y: y + 4, "text-anchor": anchor }, FACTOR[k]);
  });
  return h("svg", { class: "radar-chart", viewBox: `-70 0 ${size + 140} ${size}`, role: "img", "aria-label": "Чувствительность компании к внешним факторам" },
    ...grid, ...spokes, poly, ...dots, ...labels);
}

/** Large decorative-but-meaningful radar sweep for the home widget: blips are the current priority events. */
export function sweep(blips, size = 220) {
  const c = size / 2;
  const rings = [0.33, 0.66, 1].map((k) => h("circle", { class: "sw-ring", cx: c, cy: c, r: (c - 6) * k }));
  const dots = blips.slice(0, 7).map((b, i) => {
    const a = (i * 137.5 * Math.PI) / 180, rad = (c - 14) * (0.28 + 0.62 * (1 - Math.min(1, b.importance / 100)));
    return h("circle", { class: "sw-blip " + (b.priority || ""), cx: c + Math.cos(a) * rad, cy: c + Math.sin(a) * rad, r: b.priority === "critical" ? 6 : 4.5, style: { "--d": `${i * 0.35}s` } });
  });
  return h("svg", { class: "sweep", viewBox: `0 0 ${size} ${size}`, "aria-hidden": "true" },
    ...rings, h("line", { class: "sw-axis", x1: c, y1: 6, x2: c, y2: size - 6 }), h("line", { class: "sw-axis", x1: 6, y1: c, x2: size - 6, y2: c }),
    h("g", { class: "sw-arm" }, h("path", { class: "sw-sector", d: `M${c} ${c} L${c} 6 A${c - 6} ${c - 6} 0 0 1 ${c + (c - 6) * Math.sin(0.7)} ${c - (c - 6) * Math.cos(0.7)} Z` }), h("line", { class: "sw-beam", x1: c, y1: c, x2: c, y2: 6 })),
    ...dots, h("circle", { class: "sw-core", cx: c, cy: c, r: 4 }));
}

function wrap(text, n) {
  const words = String(text).split(/\s+/), lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > n && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 4).map((l, i, a) => (i === 3 && words.join(" ").length > a.join(" ").length ? l.replace(/.{1,2}$/, "…") : l));
}

/** Layered flow diagram (events -> effects -> outcome). Edges animate in the direction of influence. */
export function flow(graph, { width = 920, onNode } = {}) {
  const nodes = graph.nodes.map((n) => ({ ...n })), edges = graph.edges.filter((e) => nodes.find((n) => n.id === e.from) && nodes.find((n) => n.id === e.to));
  const layer = new Map(nodes.map((n) => [n.id, 0]));
  for (let it = 0; it < nodes.length; it++) for (const e of edges) layer.set(e.to, Math.max(layer.get(e.to), layer.get(e.from) + 1));
  const L = Math.max(...layer.values(), 0) + 1, cols = Array.from({ length: L }, () => []);
  nodes.forEach((n) => cols[layer.get(n.id)].push(n));
  const bw = Math.min(210, (width - 40) / L - 38), bh = 62, gapY = 22;
  const H = Math.max(...cols.map((c) => c.length)) * (bh + gapY) + gapY;
  const pos = new Map();
  cols.forEach((col, ci) => {
    const x = 20 + ci * ((width - 40 - bw) / Math.max(1, L - 1));
    const total = col.length * bh + (col.length - 1) * gapY;
    col.forEach((n, ri) => pos.set(n.id, { x: L === 1 ? (width - bw) / 2 : x, y: (H - total) / 2 + ri * (bh + gapY) }));
  });
  const defs = h("defs", null, h("marker", { id: "arw", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, h("path", { d: "M0 0 10 5 0 10z", class: "fl-arrow" })));
  const paths = edges.map((e, i) => {
    const a = pos.get(e.from), b = pos.get(e.to), x1 = a.x + bw, y1 = a.y + bh / 2, x2 = b.x, y2 = b.y + bh / 2, dx = Math.max(30, (x2 - x1) / 2);
    const w = 1.4 + (e.strength || 0.3) * 3;
    return h("g", null, h("path", { class: "fl-edge", d: `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`, "marker-end": "url(#arw)", style: { strokeWidth: w } }, e.text ? h("title", null, e.text) : null),
      h("path", { class: "fl-flow", d: `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`, style: { "--i": i } }));
  });
  const boxes = nodes.map((n, i) => {
    const p = pos.get(n.id), lines = wrap(n.label, Math.floor(bw / 6.6));
    return h("g", { class: `fl-node k-${n.kind}`, transform: `translate(${p.x},${p.y})`, style: { "--i": i }, tabindex: 0, onClick: () => onNode && onNode(n) },
      h("rect", { width: bw, height: bh, rx: 12 }), n.kind === "amplifier" ? h("rect", { class: "fl-amp", width: 5, height: bh, rx: 2 }) : null,
      ...lines.map((l, k) => h("text", { x: 12, y: bh / 2 + 4 + (k - (lines.length - 1) / 2) * 15 }, l)), h("title", null, n.label));
  });
  return h("svg", { class: "flow", viewBox: `0 0 ${width} ${H}`, role: "img", "aria-label": "Цепочка влияния события на компанию" }, defs, ...paths, ...boxes);
}

/** Ego network of observed payments. Edge width is the share of the company's payment flow. */
export function egoNetwork(net, { width = 920, height = 520, onNode } = {}) {
  const cx = width / 2, cy = height / 2 - 6;
  const rec = net.nodes.filter((n) => n.role === "recipient"), pay = net.nodes.filter((n) => n.role === "payer"), grp = net.nodes.filter((n) => n.role === "group");
  const pos = new Map([[net.nodes.find((n) => n.role === "self").id, [cx, cy]]]);
  const column = (list, x) => list.forEach((n, i) => pos.set(n.id, [x, list.length === 1 ? cy : 64 + (i * (height - 150)) / (list.length - 1)]));
  column(pay, cx - 215); column(rec, cx + 215);
  grp.forEach((n, i) => pos.set(n.id, [cx - ((grp.length - 1) * 215) / 2 + i * 215, height - 40]));
  const side = (n) => (n.role === "payer" ? -1 : n.role === "recipient" ? 1 : 0);
  const trim = (t, k) => {
    const i = t.lastIndexOf(" · ");           // keep the id readable, shorten only the activity part
    const [a, id] = i > 0 ? [t.slice(0, i), t.slice(i)] : [t, ""];
    return a.length > k ? a.slice(0, k - 1).trimEnd() + "…" + id : t;
  };
  const edgeEls = net.edges.map((e, i) => {
    const a = pos.get(e.from), b = pos.get(e.to);
    if (!a || !b) return null;
    const mx = (a[0] + b[0]) / 2;
    return h("path", { class: "ne-edge", d: `M${a[0]} ${a[1]} C${mx} ${a[1]} ${mx} ${b[1]} ${b[0]} ${b[1]}`, style: { strokeWidth: 1 + Math.sqrt(e.share || 0.02) * 12 } }, h("title", null, `Доля потока: ${(e.share * 100).toFixed(0)}%`));
  });
  const nodeEls = net.nodes.map((n, i) => {
    const [x, y] = pos.get(n.id) || [0, 0], self = n.role === "self", r = self ? 34 : 14, sd = side(n);
    const name = n.known === false ? `Вне набора данных · ${n.id}` : n.name || "";
    return h("g", { class: `ne-node r-${n.role}`, transform: `translate(${x},${y})`, style: { "--i": i }, tabindex: 0, onClick: () => onNode && onNode(n) },
      h("circle", { r }), self ? h("text", { class: "ne-self", y: 5, "text-anchor": "middle" }, "Вы") : null,
      !self ? h("text", { class: "ne-name", x: sd ? sd * (r + 10) : 0, y: sd ? 4 : r + 16, "text-anchor": sd < 0 ? "end" : sd > 0 ? "start" : "middle" }, trim(name, n.role === "group" ? 18 : 26)) : null,
      h("title", null, `${n.name || ""}${n.okved_name ? "\n" + n.okved_name : ""}${n.in_group ? "\nВходит в группу" : ""}`));
  });
  const legend = [["Плательщики компании (слева)", "r-payer", 20], ["Получатели платежей компании (справа)", "r-recipient", 270], ["Группа компаний", "r-group", 600]].map(([t, c, x]) =>
    h("g", { class: "ne-leg " + c, transform: `translate(${x},${20})` }, h("circle", { r: 6 }), h("text", { x: 14, y: 4 }, t)));
  return h("svg", { class: "ego", viewBox: `-90 0 ${width + 180} ${height}`, role: "img", "aria-label": "Платёжные связи компании" }, ...legend, ...edgeEls, ...nodeEls);
}

export function bars(rows, { max } = {}) {
  const m = max || Math.max(...rows.map((r) => r.value), 0.001);
  return h("div", { class: "bars" }, rows.map((r, i) => h("div", { class: "bar-row", title: r.hint || "" },
    h("span", { class: "bar-label" }, r.label), h("span", { class: "bar-track" }, h("span", { class: "bar-fill " + (r.cls || ""), style: { width: `${(r.value / m) * 100}%`, "--i": i } })),
    h("span", { class: "bar-val" }, r.text ?? r.value))));
}

"""Deterministic assembly of an insight: evidence registry, typed claims, chain, checks. The LLM only adds to this."""
import re
from collections import deque

from ..knowledge.ontology import EDGES, NODES, ROLE_WEIGHTS
from ..knowledge.sectors import COMMODITIES, FACTOR_LABELS
from ..nlp.ru import sentences, stems

OFFERS = {
    "refinancing": ("Рефинансирование и пересмотр условий кредитов", "Условия действующих кредитов можно обсудить с персональным менеджером банка: структура ставок, сроки, возможность перехода на другие инструменты."),
    "deposit": ("Размещение свободных средств", "Депозиты и неснижаемый остаток на срок под фиксированную доходность: подходит, если ликвидность планируется заранее."),
    "factoring": ("Факторинг и торговое финансирование", "Сравнение условий факторинга и кредитных линий с учётом сроков оплаты ваших покупателей."),
    "fx": ("Валютные операции и конверсия", "Условия конверсии и инструменты фиксации курса на ближайшие платежи."),
}


class Claims:
    def __init__(self):
        self.items = []

    def add(self, ctype, text, evidence=(), features=(), origin="rules", confidence=None, **extra):
        c = {"id": f"c{len(self.items) + 1}", "type": ctype, "text": text.strip(), "evidence": list(dict.fromkeys(evidence)),
             "features": list(dict.fromkeys(features)), "origin": origin, "confidence": confidence}
        c.update(extra)
        self.items.append(c)
        return c


def best_excerpt(text, query, maxlen=340):
    q = set(stems(query))
    best, score = None, -1
    sents = sentences(text)
    for i, s in enumerate(sents):
        sc = len(q & set(stems(s)))
        if sc > score:
            best, score = i, sc
    if best is None:
        return text[:maxlen]
    out = sents[best]
    if len(out) < 140 and best + 1 < len(sents):
        out += " " + sents[best + 1]
    return out[:maxlen].rstrip()


def registry(db, profile, event, bank_hits, graph):
    ev = {}
    for did in event["doc_ids"]:
        d = db.one("SELECT id,kind,title,source_name,url,published_at,body,is_synthetic FROM docs WHERE id=?", (did,))
        if d:
            ev[f"doc:{did}"] = {"id": f"doc:{did}", "type": "news", "title": d["title"], "source": d["source_name"], "url": d["url"],
                                "published_at": d["published_at"], "text": d["body"][:4000], "is_synthetic": bool(d["is_synthetic"])}
    for h in bank_hits:
        ev[f"bank:{h['chunk_id']}"] = {"id": f"bank:{h['chunk_id']}", "type": "bank", "title": h["title"], "source": h["source"], "url": h["url"],
                                       "published_at": h["published_at"], "locator": h["locator"], "text": h["text"], "is_synthetic": h["is_synthetic"], "doc_id": h["doc_id"]}
    for f in profile["features"]:
        ev[f"profile:{f['id']}"] = {"id": f"profile:{f['id']}", "type": "profile", "title": f["label"], "text": f"{f['label']}: {f['value']}", "source": f["source"], "kind": f["kind"]}
    if graph and graph["available"]:
        r, p = graph["recipients"], graph["payers"]
        ev["graph:recipients"] = {"id": "graph:recipients", "type": "graph", "title": "Получатели платежей компании", "source": "payments",
                                  "text": f"Получателей: {r['n']}; крупнейший — {r['top1_share']:.0%}; три крупнейших — {r['top3_share']:.0%}; отрасли: " + ", ".join(f"{k} {v:.0%}" for k, v in list(r["sectors"].items())[:4]) if r["n"] else "нет данных"}
        ev["graph:payers"] = {"id": "graph:payers", "type": "graph", "title": "Плательщики компании", "source": "payments",
                              "text": f"Плательщиков: {p['n']}; крупнейший — {p['top1_share']:.0%}; три крупнейших — {p['top3_share']:.0%}; отрасли: " + ", ".join(f"{k} {v:.0%}" for k, v in list(p["sectors"].items())[:4]) if p["n"] else "нет данных"}
    return ev


def downstream_path(nodes_from, target="liquidity", max_depth=3):
    adj = {}
    for a, b, w, t in EDGES:
        adj.setdefault(a, []).append((b, w, t))
    best = None
    for start in nodes_from:
        q = deque([(start, [start], [])])
        while q:
            n, path, txt = q.popleft()
            if n == target:
                if best is None or len(path) < len(best[0]):
                    best = (path, txt)
                break
            if len(path) > max_depth:
                continue
            for b, w, t in adj.get(n, []):
                if b not in path:
                    q.append((b, path + [b], txt + [t]))
    return best


def chain_for(event, mech, profile):
    nodes = [{"id": "event", "label": event["title"][:90], "kind": "event"}]
    edges = []
    ex = [e for e in mech["exposure"]][:2]
    prev = "event"
    for i, e in enumerate(ex):
        nid = f"exp{i}"
        nodes.append({"id": nid, "label": e["text"].rstrip(".")[:110], "kind": "exposure", "evidence": e["kind"], "feature": e["feature"]})
        edges.append({"from": prev if i == 0 else "event", "to": nid, "text": "затрагивает" if i == 0 else ""})
    tier1 = [x["node"] for x in mech["nodes"] if x["sign"] > 0] or [x["node"] for x in mech["nodes"]]
    last = f"exp{len(ex) - 1}" if ex else "event"
    first_node = tier1[0] if tier1 else None
    if first_node:
        nodes.append({"id": first_node, "label": NODES[first_node]["label"], "kind": "effect"})
        edges.append({"from": "exp0" if ex else "event", "to": first_node, "text": mech["how"][:140]})
        path = downstream_path([first_node])
        if path:
            for a, b, t in zip(path[0], path[0][1:], path[1]):
                if not any(n["id"] == b for n in nodes):
                    nodes.append({"id": b, "label": NODES[b]["label"], "kind": "outcome" if NODES[b]["tier"] == 3 else "effect"})
                edges.append({"from": a, "to": b, "text": t})
    return {"nodes": nodes, "edges": edges}


def ordered_checks(mechs, role):
    w = ROLE_WEIGHTS.get(role, {})
    seen, out = set(), []
    for m in sorted(mechs, key=lambda m: -(m["impact"] * w.get(m["factor"], 1.0))):
        for c in m["checks"]:
            if c not in seen:
                seen.add(c)
                out.append({"text": c, "mechanism": m["id"], "factor": m["factor"], "headline": m["headline"]})
    return out


def deterministic_narrative(profile, event, mechs, bank_claims):
    if not mechs:
        return f"Событие «{event['title']}» не имеет подтверждённой связи с профилем компании по доступным данным; оно оставлено для наблюдения."
    m = mechs[0]
    paras = [f"{m['why']} {m['how']}"]
    paras.append(f"Возможное следствие: {m['outcome'][0].lower() + m['outcome'][1:]}")
    if len(mechs) > 1:
        m2 = mechs[1]
        link = "Одновременно" if m2["kind"] == m["kind"] else "При этом действует и противоположный эффект:"
        paras.append(f"{link} {m2['headline'][0].lower() + m2['headline'][1:]}.")
    if m["checks"]:
        paras.append(f"Первая проверка: {m['checks'][0][0].lower() + m['checks'][0][1:]}.")
    return " ".join(paras)


def offers_for(mechs):
    out, seen = [], set()
    for m in mechs[:2]:
        h = m.get("product_hint")
        if h and h in OFFERS and h not in seen and m["kind"] != "watch":
            seen.add(h)
            t, d = OFFERS[h]
            out.append({"id": h, "title": t, "text": d, "mechanism": m["id"], "label": "Реклама · решения банка по теме"})
    return out

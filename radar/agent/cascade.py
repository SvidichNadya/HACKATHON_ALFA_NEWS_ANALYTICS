"""Radar of hidden cascading consequences: independent events converging on one company bottleneck."""
import math
from collections import defaultdict

from ..knowledge.ontology import EDGES, NODES

STRUCT_CONF = 0.75
ADJ = defaultdict(list)
for a, b, w, t in EDGES:
    ADJ[a].append((b, w, t))


def _paths(start, max_edges=3):
    out = []
    stack = [(start, [start], [], 1.0)]
    while stack:
        n, path, texts, w = stack.pop()
        if len(path) > 1:
            out.append((path, texts, w))
        if len(path) - 1 >= max_edges:
            continue
        for b, ew, t in ADJ.get(n, []):
            if b not in path:
                stack.append((b, path + [b], texts + [t], w * ew))
    return out


def detect(profile, scored, min_events=2, limit=3):
    """scored: list of ranking.score() results (each with mechanisms) for events in the window."""
    reach = defaultdict(list)  # target -> list of path records
    for s in scored:
        for m in s["mechanisms"]:
            if m["kind"] == "watch" and m["impact"] < .25:
                continue
            for eff in m["nodes"]:
                if eff["sign"] <= 0:
                    continue
                for path, texts, w in _paths(eff["node"]):
                    tgt = path[-1]
                    if NODES[tgt]["tier"] < 2:
                        continue
                    strength = m["impact"] * w
                    link_conf = m["evidence_share"] * (STRUCT_CONF ** (len(path) - 1))
                    reach[tgt].append({"event_id": s["event_id"], "mechanism": m, "path": path, "texts": texts, "strength": strength, "conf": link_conf})
        for m in s["mechanisms"]:
            pass
    cascades = []
    g = profile.get("graph") or {}
    top1 = (g.get("recipients") or {}).get("top1_share") or 0
    for tgt, recs in reach.items():
        by_event = {}
        for r in recs:
            cur = by_event.get(r["event_id"])
            if cur is None or r["strength"] > cur["strength"]:
                by_event[r["event_id"]] = r
        best = sorted(by_event.values(), key=lambda r: -r["strength"])
        best = [b for b in best if b["strength"] >= .08]
        if len(best) < min_events:
            continue
        sources = {b["path"][0] for b in best}
        factors = {b["mechanism"]["factor"] for b in best}
        if len(factors) < 2 and len(sources) < 2:
            continue
        top = best[:3]
        combined = .88 * (1 - math.prod(1 - b["strength"] for b in top))
        amplifiers = []
        if top1 >= .4 and tgt in ("wc_need", "liquidity", "margin"):
            combined = min(1.0, combined + .06)
            amplifiers.append({"label": f"Концентрация платежей: крупнейший получатель — {top1:.0%}", "evidence": "graph:recipients", "kind": "graph"})
        conf = math.exp(sum(math.log(max(b["conf"], .05)) for b in best) / len(best))
        weakest = min(best, key=lambda b: b["conf"])
        if conf < .25 or combined < .2:
            continue
        cascades.append({
            "target": tgt, "target_label": NODES[tgt]["label"], "score": round(combined * 100, 1), "confidence_score": round(conf, 3),
            "confidence": "high" if conf >= .6 else "medium" if conf >= .4 else "low",
            "links": [{"event_id": b["event_id"], "mechanism_id": b["mechanism"]["id"], "headline": b["mechanism"]["headline"], "factor": b["mechanism"]["factor"],
                       "path": b["path"], "path_texts": b["texts"], "strength": round(b["strength"], 3), "confidence": round(b["conf"], 3),
                       "evidence_share": b["mechanism"]["evidence_share"]} for b in best[:4]],
            "weakest": {"event_id": weakest["event_id"], "mechanism_id": weakest["mechanism"]["id"], "confidence": round(weakest["conf"], 3)},
            "amplifiers": amplifiers,
        })
    cascades.sort(key=lambda c: -(c["score"] * (.5 + c["confidence_score"])))
    used, out = [], []
    for c in cascades:
        ev = frozenset(l["event_id"] for l in c["links"])
        if any(ev <= u for u in used):
            continue
        used.append(ev)
        out.append(c)
        if len(out) >= limit:
            break
    return out


def graph_of(cascade, event_titles):
    nodes, edges, seen = {}, [], set()
    for l in cascade["links"]:
        eid = f"e{l['event_id']}"
        nodes[eid] = {"id": eid, "label": event_titles.get(l["event_id"], "Событие")[:80], "kind": "event", "factor": l["factor"]}
        for a, b, t in zip(l["path"], l["path"][1:], l["path_texts"]):
            for n in (a, b):
                nodes.setdefault(n, {"id": n, "label": NODES[n]["label"], "kind": "outcome" if NODES[n]["tier"] == 3 else "effect", "tier": NODES[n]["tier"]})
            if (a, b) not in seen:
                seen.add((a, b))
                edges.append({"from": a, "to": b, "text": t})
        first = l["path"][0]
        edges.append({"from": eid, "to": first, "text": l["headline"], "strength": l["strength"]})
    for a in cascade["amplifiers"]:
        nodes["amp"] = {"id": "amp", "label": a["label"], "kind": "amplifier"}
        edges.append({"from": "amp", "to": cascade["target"], "text": "усиливает чувствительность", "strength": .3})
    return {"nodes": list(nodes.values()), "edges": edges}

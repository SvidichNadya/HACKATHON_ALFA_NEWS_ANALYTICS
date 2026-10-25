"""Offline ranking quality against expert grades stored with the synthetic corpus (0..3 per demo company)."""
import math
from itertools import combinations

from .db import loads
from .ingest.store import load_event
from .nlp.dedup import jaccard
from .nlp.ru import stems
from .profile import build_profile
from .ranking import diversify, score
from . import retrieval

DEMO = {"metal": "U-DEMO-0001", "trade": "U-DEMO-0002", "agro": "U-DEMO-0003", "build": "U-DEMO-0004", "digital": "U-DEMO-0005", "mining": "U-DEMO-0006"}


def _grades(db):
    g = {}
    for d in db.q("SELECT id, meta FROM docs WHERE kind='news'"):
        gold = loads(d["meta"], {}).get("gold")
        if gold is None:
            continue
        ev = db.one("SELECT id FROM events WHERE doc_ids LIKE ?", (f"%{d['id']}%",))
        if ev:
            cur = g.setdefault(ev["id"], {})
            for k, v in gold.items():
                cur[k] = max(cur.get(k, 0), v)
    return g


def ndcg(rels, k=5, ideal=None):
    dcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))
    ideal = sorted(ideal if ideal is not None else rels, reverse=True)
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal[:k]))
    return dcg / idcg if idcg else 0.0


_BENCH = {}


def benchmark_db(db):
    """Expert grades exist only for the synthetic demo companies. With a real export loaded, evaluate on a private synthetic copy."""
    if db.one("SELECT 1 FROM companies WHERE id='U-DEMO-0001'"):
        return db
    if "db" not in _BENCH:
        import tempfile
        from pathlib import Path
        from .db import DB
        from .seed import loader
        tmp = DB(Path(tempfile.mkdtemp(prefix="radar-bench-")) / "bench.sqlite3")
        loader.bootstrap(tmp, dataset="synthetic")
        _BENCH["db"] = tmp
    return _BENCH["db"]


def run(db, days=60):
    db = benchmark_db(db)
    grades = _grades(db)
    evs = [r["id"] for r in db.q("SELECT id FROM events WHERE last_seen >= datetime('now', ?)", (f"-{days} days",))]
    if not evs or not grades:
        return None
    rows, tops, base_p5 = [], {}, []
    for key, cid in DEMO.items():
        p = build_profile(db, cid)
        if not p:
            continue
        sc = []
        for eid in evs:
            ev = load_event(db, eid)
            bank = retrieval.search(db, ev["title"], kind="bank_analysis", factors=[s["factor"] for s in ev["signals"]], k=3)
            sc.append(score(p, ev, bank, None))
        ranked = diversify(sc)
        rel = [grades.get(s["event_id"], {}).get(key, 0) for s in ranked]
        all_rel = [grades.get(e, {}).get(key, 0) for e in evs]
        last = {r["id"]: r["last_seen"] for r in db.q("SELECT id,last_seen FROM events")}
        recency = sorted(evs, key=lambda e: last[e], reverse=True)  # chronological feed: the non-personalised baseline
        base = [grades.get(e, {}).get(key, 0) for e in recency]
        top5 = rel[:5]
        n_rel = sum(1 for r in all_rel if r >= 2)
        rows.append({"company": key, "p5": sum(1 for r in top5 if r >= 2) / 5, "ndcg5": ndcg(rel, 5, all_rel), "recall10": (sum(1 for r in rel[:10] if r >= 2) / n_rel) if n_rel else None,
                     "baseline_p5": sum(1 for r in base[:5] if r >= 2) / 5, "baseline_ndcg5": ndcg(base, 5, all_rel),
                     "random_p5": n_rel / len(evs), "relevant_share": n_rel / len(evs)})
        tops[key] = [s["event_id"] for s in ranked[:5]]
        titles = [load_event(db, s["event_id"])["title"] for s in ranked[:10]]
        sets = [set(stems(t)) for t in titles]
        dup = sum(1 for a, b in combinations(range(len(sets)), 2) if jaccard(sets[a], sets[b]) >= .5)
        rows[-1]["dup_pairs_top10"] = dup
    pair = [jaccard(set(tops[a]), set(tops[b])) for a, b in combinations(tops, 2)]
    avg = lambda k: round(sum(r[k] for r in rows if r[k] is not None) / max(1, sum(1 for r in rows if r[k] is not None)), 3)
    return {"companies": rows, "mean": {"precision_at_5": avg("p5"), "ndcg_at_5": avg("ndcg5"), "recall_at_10": avg("recall10"), "baseline_precision_at_5": avg("baseline_p5"), "random_precision_at_5": avg("random_p5"),
                                        "baseline_ndcg_at_5": avg("baseline_ndcg5"), "top5_overlap_between_companies": round(sum(pair) / len(pair), 3) if pair else None,
                                        "duplicate_pairs_in_top10": avg("dup_pairs_top10")},
            "note": "Оценки экспертов синтетические (v0) и задают лишь рабочий ориентир; пороги приёмки фиксируются после разметки реальной выборки."}

"""Document ingestion: dedup, extraction, chunking, event clustering."""
import re
from datetime import datetime, timedelta, timezone

from ..db import dumps, loads
from ..nlp.dedup import content_hash, hamming, jaccard, shingles, simhash
from ..nlp.extract import analyze_text
from ..nlp.ru import stems
from .files import chunk_blocks
from .sources import authority

_VERSION = {"n": 0}


def index_version():
    return _VERSION["n"]


def _bump():
    _VERSION["n"] += 1


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _iso(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def add_document(db, kind, title, body, source_name, url=None, published_at=None, is_synthetic=False,
                 meta=None, blocks=None, author=None):
    """Insert a document if new. Returns (doc_id, created, event_id)."""
    title = (title or "").strip()[:400]
    body = (body or "").strip()
    if not title or len(body) < 40:
        raise ValueError("Материал слишком короткий для анализа")
    h = content_hash(title, body)
    dup = db.one("SELECT id FROM docs WHERE content_hash=?", (h,))
    if dup:
        ev = db.one("SELECT id FROM events WHERE doc_ids LIKE ?", (f"%{dup['id']}%",))
        return dup["id"], False, ev["id"] if ev else None
    analysis = analyze_text(title, body)
    meta = dict(meta or {})
    if analysis["injection_findings"]:
        meta["injection_findings"] = analysis["injection_findings"]
    pub = published_at or now_iso()
    event_at = (analysis["dates"][0] + "T00:00:00+00:00") if analysis["dates"] else None
    with db.tx():
        doc_id = db.x(
            "INSERT INTO docs(kind,title,source_name,url,author,published_at,event_at,fetched_at,body,content_hash,simhash,is_synthetic,meta) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kind, title, source_name, url, author, pub, event_at, now_iso(), body, h, str(simhash(title + " " + body)), int(is_synthetic), dumps(meta)))
        if kind == "bank_analysis":
            blk = blocks or [("документ", p) for p in re.split(r"\n\s*\n", body) if p.strip()]
            for i, (loc, text) in enumerate(chunk_blocks(blk)):
                a = analyze_text("", text)
                db.x("INSERT INTO chunks(doc_id,ord,locator,text,factors) VALUES (?,?,?,?,?)",
                     (doc_id, i, loc, text, dumps(sorted({s["factor"] + (":" + s["commodity"] if s.get("commodity") else "") for s in a["signals"]}))))
        else:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()] or [body]
            for i, (loc, text) in enumerate(chunk_blocks([(f"абз. {j + 1}", p) for j, p in enumerate(paras)], target=900)):
                db.x("INSERT INTO chunks(doc_id,ord,locator,text,factors) VALUES (?,?,?,?,'[]')", (doc_id, i, loc, text))
    event_id = None
    if kind == "news":
        event_id = cluster_into_event(db, doc_id, analysis, authority(kind, source_name, is_synthetic), pub)
    _bump()
    return doc_id, True, event_id


def _top_sig(signals):
    return (signals[0]["factor"], signals[0].get("commodity")) if signals else None


def _same_event(doc_analysis, doc_sim, doc_title, doc_pub, ev, member_docs):
    pub_a, pub_b = _iso(doc_pub), _iso(ev["last_seen"])
    if pub_a and pub_b and abs((pub_a - pub_b).days) > 5:
        return False
    for md in member_docs:
        if hamming(doc_sim, int(md["simhash"] or 0)) <= 8:
            return True
    ev_sigs = loads(ev["signals"], [])
    if not doc_analysis["signals"] or not ev_sigs or _top_sig(doc_analysis["signals"]) != _top_sig(ev_sigs):
        return False
    vals_a = {v for s in doc_analysis["signals"] for v in s["values"]}
    vals_b = {v for s in ev_sigs for v in s.get("values", [])}
    dates_a, dates_b = set(doc_analysis["dates"]), {d[:10] for d in loads(ev["facts"], []) if isinstance(d, str)}
    ja = jaccard(set(stems(doc_title)), set(stems(ev["title"])))
    return bool((vals_a & vals_b) or ja >= 0.35 or (doc_analysis["dates"] and ev["event_at"] and ev["event_at"][:10] in doc_analysis["dates"]))


def cluster_into_event(db, doc_id, analysis, auth, pub):
    doc = db.one("SELECT * FROM docs WHERE id=?", (doc_id,))
    cands = db.q("SELECT * FROM events WHERE last_seen >= ? ORDER BY last_seen DESC LIMIT 300",
                 ((_iso(pub) - timedelta(days=6)).isoformat() if _iso(pub) else "0000",))
    sim = int(doc["simhash"] or 0)
    for ev in cands:
        ids = loads(ev["doc_ids"], [])
        members = db.q(f"SELECT simhash FROM docs WHERE id IN ({','.join('?' * len(ids))})", ids) if ids else []
        if _same_event(analysis, sim, doc["title"], pub, ev, members):
            ids.append(doc_id)
            return rebuild_event(db, ev["id"], ids)
    return rebuild_event(db, None, [doc_id])


def rebuild_event(db, event_id, doc_ids):
    docs = db.q(f"SELECT * FROM docs WHERE id IN ({','.join('?' * len(doc_ids))}) ORDER BY published_at", doc_ids)
    analyses = [(d, analyze_text(d["title"], d["body"])) for d in docs]
    sources = {d["source_name"] for d in docs}
    auths = [authority(d["kind"], d["source_name"], bool(d["is_synthetic"])) for d in docs]
    merged = {}
    contradictions = []
    for d, a in analyses:
        for s in a["signals"]:
            key = (s["factor"], s.get("commodity"))
            cur = merged.get(key)
            if cur and cur["direction"] != s["direction"] and "flat" not in (cur["direction"], s["direction"]):
                contradictions.append({"factor": s["factor"], "commodity": s.get("commodity"), "a": {"doc": cur["_doc"], "direction": cur["direction"]},
                                       "b": {"doc": d["id"], "direction": s["direction"]},
                                       "note": "Публикации расходятся в направлении изменения; различия могут объясняться датой, охватом или определением показателя."})
            if cur is None or s["strength"] > cur["strength"]:
                merged[key] = {**s, "_doc": d["id"]}
    signals = []
    for s in sorted(merged.values(), key=lambda x: -x["strength"]):
        s = dict(s)
        s["source_doc"] = s.pop("_doc")
        s["strength"] = round(min(0.97, s["strength"] + 0.05 * (len(sources) - 1)), 3)
        signals.append(s)

    def agg(key):
        return sorted({x for _, a in analyses for x in a[key]})

    best = max(analyses, key=lambda da: (authority(da[0]["kind"], da[0]["source_name"], bool(da[0]["is_synthetic"])), len(da[0]["body"])))
    d0, a0 = best
    facts = a0["facts"]
    first = min((d["published_at"] for d in docs), default=None)
    last = max((d["published_at"] for d in docs), default=None)
    event_at = next((d["event_at"] for d in docs if d["event_at"]), None)
    rec = (d0["title"], a0["summary"], dumps(sorted({c for _, a in analyses for c in a["categories"]})), dumps(signals),
           dumps({"orgs": agg("orgs")}), dumps(facts), dumps(agg("sectors")), dumps(agg("regions")), dumps(agg("countries")), dumps(agg("commodities")),
           first, last, event_at, dumps([d["id"] for d in docs]), len(sources), max(auths), dumps(contradictions),
           int(all(d["is_synthetic"] for d in docs)), now_iso())
    cols = "title=?,summary=?,categories=?,signals=?,entities=?,facts=?,sectors=?,regions=?,countries=?,commodities=?,first_seen=?,last_seen=?,event_at=?,doc_ids=?,source_count=?,authority=?,contradictions=?,is_synthetic=?,updated_at=?"
    with db.tx():
        if event_id:
            db.x(f"UPDATE events SET {cols}, version=version+1 WHERE id=?", rec + (event_id,))
        else:
            event_id = db.x("INSERT INTO events(title,summary,categories,signals,entities,facts,sectors,regions,countries,commodities,first_seen,last_seen,event_at,doc_ids,source_count,authority,contradictions,is_synthetic,updated_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rec)
    return event_id


def load_event(db, event_id):
    r = db.one("SELECT * FROM events WHERE id=?", (event_id,))
    if not r:
        return None
    for k in ("categories", "signals", "entities", "facts", "sectors", "regions", "countries", "commodities", "doc_ids", "contradictions"):
        r[k] = loads(r[k], [] if k != "entities" else {})
    return r

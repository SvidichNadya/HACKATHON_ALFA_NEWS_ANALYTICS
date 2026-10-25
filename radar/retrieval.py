"""BM25 retrieval over chunks of news and bank analytics, with factor-tag boosting."""
import threading

from .db import loads
from .ingest.store import index_version
from .nlp.bm25 import BM25

_lock = threading.Lock()
_cache = {}


def _index(db):
    key = (db.path, index_version(), db.one("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM chunks")["n"])
    with _lock:
        if _cache.get("key") == key:
            return _cache["idx"]
        idx = BM25()
        for c in db.q("SELECT c.id, c.text, c.locator, c.factors, d.kind, d.title, d.id doc_id FROM chunks c JOIN docs d ON d.id=c.doc_id"):
            idx.add(c["id"], c["title"] + " " + c["text"], {"kind": c["kind"], "doc_id": c["doc_id"], "factors": loads(c["factors"], [])})
        _cache.update(key=key, idx=idx)
        return idx


def search(db, query, kind=None, factors=None, k=6, doc_ids=None):
    idx = _index(db)
    allow = {cid for cid, (_, _, m) in idx.docs.items() if (kind is None or m["kind"] == kind) and (doc_ids is None or m["doc_id"] in doc_ids)}
    boost = {}
    if factors:
        fs = set(factors)
        for cid in allow:
            cf = set(idx.docs[cid][2]["factors"])
            if cf & fs:
                boost[cid] = 1.6 if len(cf & fs) > 1 else 1.35
    hits = idx.search(query, k=k, allow=allow, boost=boost)
    if not hits:
        return []
    rows = {r["id"]: r for r in db.q(
        f"SELECT c.id, c.text, c.locator, c.doc_id, d.title, d.source_name, d.url, d.published_at, d.kind, d.is_synthetic FROM chunks c JOIN docs d ON d.id=c.doc_id WHERE c.id IN ({','.join('?' * len(hits))})",
        [h["key"] for h in hits])}
    out = []
    for h in hits:
        r = rows[h["key"]]
        out.append({"chunk_id": r["id"], "doc_id": r["doc_id"], "title": r["title"], "source": r["source_name"], "url": r["url"],
                    "published_at": r["published_at"], "kind": r["kind"], "locator": r["locator"], "text": r["text"],
                    "score": h["score"], "norm": h["norm"], "terms": h["terms"], "is_synthetic": bool(r["is_synthetic"]),
                    "factor_match": bool(boost.get(h["key"]))})
    return out

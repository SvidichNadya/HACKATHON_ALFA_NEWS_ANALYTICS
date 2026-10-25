"""In-process BM25 over stemmed chunks. Built lazily, invalidated on ingest."""
import math
from collections import Counter, defaultdict

from .ru import stems


class BM25:
    def __init__(self, k1=1.4, b=0.72):
        self.k1, self.b = k1, b
        self.docs = {}
        self.df = Counter()
        self.inv = defaultdict(set)
        self.total_len = 0

    def add(self, key, text, meta=None):
        toks = stems(text)
        c = Counter(toks)
        self.docs[key] = (c, len(toks), meta or {})
        self.total_len += len(toks)
        for t in c:
            self.df[t] += 1
            self.inv[t].add(key)

    def search(self, query, k=8, allow=None, boost=None):
        q = stems(query) if isinstance(query, str) else list(query)
        if not q or not self.docs:
            return []
        n = len(self.docs)
        avg = self.total_len / n or 1
        scores = defaultdict(float)
        matched = defaultdict(set)
        for t in set(q):
            df = self.df.get(t, 0)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for key in self.inv[t]:
                if allow is not None and key not in allow:
                    continue
                tf, ln, _ = self.docs[key]
                f = tf[t]
                scores[key] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / avg))
                matched[key].add(t)
        if boost:
            for key in list(scores):
                scores[key] *= boost.get(key, 1.0)
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        best = top[0][1] if top else 1
        return [
            {"key": key, "score": round(s, 4), "norm": round(s / best, 4), "terms": sorted(matched[key]), "meta": self.docs[key][2]}
            for key, s in top
        ]

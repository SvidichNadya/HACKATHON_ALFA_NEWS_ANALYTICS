"""Near-duplicate detection: 64-bit simhash on stem bigrams plus shingle Jaccard."""
import hashlib

from .ru import stems


def _h64(s):
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")


def simhash(text):
    toks = stems(text)
    if not toks:
        return 0
    grams = toks if len(toks) < 3 else [" ".join(toks[i:i + 2]) for i in range(len(toks) - 1)]
    v = [0] * 64
    for g in grams:
        h = _h64(g)
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    return sum(1 << i for i in range(64) if v[i] > 0)


def hamming(a, b):
    return bin(a ^ b).count("1")


def shingles(text, n=3):
    t = stems(text)
    if len(t) < n:
        return {" ".join(t)} if t else set()
    return {" ".join(t[i:i + n]) for i in range(len(t) - n + 1)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def content_hash(title, body):
    norm = " ".join(((title or "") + " " + (body or "")).lower().split())
    return hashlib.sha256(norm.encode()).hexdigest()

"""Rule-based event extraction: factor signals with direction, numbers, dates, geography, sectors, commodities.

The extractor is deterministic and explainable: each signal keeps the sentence that triggered it. It is the
baseline the LLM may refine, never a replacement that can silently overwrite it.
"""
import re
from collections import defaultdict

from ..config import settings
from ..knowledge import lexicon as L
from ..knowledge.sectors import COMMODITIES, SECTORS
from .ru import sentences, stem, tokens

_NUM = re.compile(r"(\d{1,3}(?:[\s\u00a0]\d{3})+|\d+)(?:[.,](\d+))?\s*(%|процент\w*|п\.\s?п\.|млрд|млн|трлн|тыс\.?)?(?:\s*(руб\w*|долл\w*|евро|юан\w*))?", re.I)
_PCT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|процент\w*)", re.I)
_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(L.MONTHS) + r")(?:\s+(\d{4}))?", re.I)
_QUOTED = re.compile(r"«([^»]{2,60})»")
_LEGAL = re.compile(r"\b((?:ООО|АО|ПАО|ОАО|НПО)\s+[«\"]?[А-ЯЁA-Z][\w\-]+(?:\s+[А-ЯЁA-Z][\w\-]+){0,2}[»\"]?)")

_COMMODITY_KW = {k: [w.strip().split()[0] for w in v[1]] for k, v in COMMODITIES.items()}
_SECTOR_KW = {k: [w.split()[0] for w in v["kw"]] for k, v in SECTORS.items()}


def _kw_hit(tok, kws):
    for kw in kws:
        if tok == kw or (tok.startswith(kw) and (len(kw) > 4 or len(tok) - len(kw) <= 2)):
            return True
    return False
_PRICE_VERBS = {stem(w) for w in "подорожание подорожал подорожала подорожали удорожание удорожал подешевел подешевела подешевели удешевление".split()}
_WINDOW = 7
_STEEL_VERB_FORMS = {"стал", "стала", "стало", "стали", "стану", "станет"}
_STEEL_CONTEXT = {"на", "цены", "цен", "рынок", "рынке", "производство", "выплавка", "тонн", "стоимость", "прокат"}


_RATE_OF_CHANGE = {stem(w) for w in "ускорение ускорилась ускорился замедление замедлилась замедлился".split()}


def _cue(st, j, extra_up, extra_down):
    """Returns (sign, is_hold, weight, specific). `specific` cues already speak in the factor's own direction."""
    s = st[j]
    specific = s in extra_up or s in extra_down
    if s in extra_up:
        sign = 1
    elif s in extra_down:
        sign = -1
    elif s in L.UP:
        sign = 1
    elif s in L.DOWN:
        sign = -1
    elif s in L.HOLD:
        return 0, True, 1.0, False
    else:
        return 0, False, 1.0, False
    if any(st[k] in L.NEG for k in range(max(0, j - 3), j)):
        return 0, True, 1.0, False   # "не снизил", "не ждут повышения": the move did not happen -> hold, never the opposite
    return sign, False, (2.0 if s in _RATE_OF_CHANGE else 1.0), specific


def _sentence_signals(si, sent):
    toks = tokens(sent, drop_stop=False)
    st = [stem(t) for t in toks]
    out = []
    st_set = set(st)
    for factor, rule in L.FACTOR_RULES.items():
        net = hold = 0.0
        subj = []
        for i, s in enumerate(st):
            if s not in rule["subjects"]:
                continue
            needs = rule["needs"].get(s)
            if needs and not (needs & (st_set - {s})):
                continue
            subj.append(i)
        subj_hits = len(subj)
        for j in range(len(st)):
            if j in subj or not subj_hits:
                continue
            i = min(subj, key=lambda x: abs(x - j))   # every cue belongs to its nearest subject only
            if abs(j - i) > _WINDOW:
                continue
            sign, is_hold, cw, specific = _cue(st, j, rule["extra_up"], rule["extra_down"])
            w = cw / (1 + abs(j - i) / 4.0)
            if is_hold:
                hold += w
            elif sign:
                net += sign * (1 if specific else rule["polarity"].get(st[i], 1)) * w
        if not subj_hits:
            continue
        if net > 0.35:
            direction = "up"
        elif net < -0.35:
            direction = "down"
        elif hold > 0.25:
            direction = "flat"
        else:
            continue
        pcts = [float(x.replace(",", ".")) for x in _PCT.findall(sent)]
        strength = 0.45 + (0.15 if pcts else 0) + min(0.2, 0.08 * subj_hits) + (0.1 if st_set & L.ORG_WORDS else 0)
        out.append({"factor": factor, "direction": direction, "strength": min(0.95, strength), "sentence": si,
                    "quote": sent[:420], "values": pcts[:3], "net": round(net, 3)})
    # commodities
    for cid, kws in _COMMODITY_KW.items():
        for i, tk in enumerate(toks):
            if not _kw_hit(tk, kws):
                continue
            if cid == "steel" and tk in _STEEL_VERB_FORMS and not (i and toks[i - 1] in _STEEL_CONTEXT):
                continue
            up = down = 0.0
            has_price_word = bool(st_set & L.PRICE_WORDS)
            for j in range(max(0, i - _WINDOW), min(len(st), i + _WINDOW + 1)):
                sign, _, _, _ = _cue(st, j, set(), set())
                if sign and (has_price_word or st[j] in _PRICE_VERBS):
                    w = 1.0 / (1 + abs(j - i) / 4.0)
                    up += w if sign > 0 else 0
                    down += w if sign < 0 else 0
            if abs(up - down) > 0.35:
                pcts = [float(x.replace(",", ".")) for x in _PCT.findall(sent)]
                out.append({"factor": "commodity", "commodity": cid, "direction": "up" if up > down else "down",
                            "strength": min(0.9, 0.5 + (0.15 if pcts else 0) + (0.1 if has_price_word else 0)),
                            "sentence": si, "quote": sent[:420], "values": pcts[:3], "net": round(up - down, 3)})
                break
    return out


def _aggregate(raw):
    groups = defaultdict(list)
    for r in raw:
        groups[(r["factor"], r.get("commodity"))].append(r)
    signals = []
    for (factor, commodity), items in groups.items():
        score = defaultdict(float)
        for r in items:
            score[r["direction"]] += r["strength"]
        direction = max(score, key=score.get)
        opposing = [d for d in score if d != direction and score[d] >= 0.6 * score[direction]]
        best = max((r for r in items if r["direction"] == direction), key=lambda r: r["strength"])
        strength = min(0.97, best["strength"] + 0.05 * (len([r for r in items if r["direction"] == direction]) - 1))
        sig = {"factor": factor, "direction": direction, "strength": round(strength, 3), "quote": best["quote"],
               "sentence": best["sentence"], "values": best["values"], "mixed": bool(opposing)}
        if commodity:
            sig["commodity"] = commodity
        signals.append(sig)
    return sorted(signals, key=lambda s: -s["strength"])


_ALIAS_CACHE = {}


def _alias_stems(a):
    if a not in _ALIAS_CACHE:
        _ALIAS_CACHE[a] = tuple(stem(t) for t in tokens(a, drop_stop=False))
    return _ALIAS_CACHE[a]


def _find_phrases(text_l, table):
    """Match aliases on stems so that case forms (Свердловской областью, Китая) are recognised."""
    seq = [stem(t) for t in tokens(text_l, drop_stop=False)]
    found = []
    for canon, aliases in table.items():
        for a in aliases:
            sa = _alias_stems(a)
            n = len(sa)
            if n and any(tuple(seq[i:i + n]) == sa for i in range(len(seq) - n + 1)):
                found.append(canon)
                break
    return found


def parse_dates(text):
    out = []
    for m in _DATE.finditer(text or ""):
        day, month, year = int(m.group(1)), L.MONTHS[m.group(2).lower()], m.group(3)
        if year and 1 <= day <= 31:
            out.append(f"{int(year):04d}-{month:02d}-{day:02d}")
    return out


def sanitize_untrusted(text):
    """Strip sentences that look like instructions aimed at an AI reader. Returns (clean_text, findings)."""
    findings = []
    keep = []
    for s in sentences(text):
        hit = next((p for p in L.INJECTION_PATTERNS if re.search(p, s, re.I)), None)
        if hit:
            findings.append(s[:200])
        else:
            keep.append(s)
    return " ".join(keep), findings


def analyze_text(title, body):
    clean_body, injections = sanitize_untrusted(body or "")
    full = (title or "").strip().rstrip(".") + ". " + clean_body
    sents = sentences(full)
    raw = []
    for i, s in enumerate(sents[:120]):
        raw.extend(_sentence_signals(i, s))
    signals = _aggregate(raw)

    low = full.lower()
    all_toks = tokens(full, drop_stop=False)
    stems_all = [stem(t) for t in all_toks]
    title_toks = set(tokens(title or "", drop_stop=False))
    sector_hits = defaultdict(float)
    for t in all_toks:
        for sk, kws in _SECTOR_KW.items():
            if _kw_hit(t, kws):
                sector_hits[sk] += 1.0 + (1.5 if t in title_toks else 0)
    sectors = [k for k, v in sorted(sector_hits.items(), key=lambda kv: -kv[1]) if v >= 1.0][:4]

    regions = _find_phrases(low, {**L.REGIONS, **L.FED_DISTRICTS})
    countries = _find_phrases(low, L.COUNTRIES)
    commodities = sorted({s["commodity"] for s in signals if s.get("commodity")})
    orgs = [name for name, pat in L.ORG_ALIASES.items() if re.search(pat, low)]
    orgs += [q for q in _QUOTED.findall(full)][:6] + [m for m in _LEGAL.findall(full)][:4]

    hawk = sum(1 for s in stems_all if s in L.HAWKISH)
    dove = sum(1 for s in stems_all if s in L.DOVISH)
    for sig in signals:
        if sig["factor"] in ("rate", "liquidity"):
            sig["tone"] = "hawkish" if hawk > dove and hawk >= 1 else "dovish" if dove > hawk and dove >= 1 else "neutral"
        if sig["factor"] == "rate" and sig["values"] and max(sig["values"]) >= settings.rate_elevated_pct:
            sig["level"] = "elevated"
            sig["level_value"] = max(sig["values"])

    cats = defaultdict(float)
    for sig in signals:
        cats[L.CATEGORIES[sig["factor"]]] += sig["strength"]
    if sum(1 for s in stems_all if s in L.CORPORATE) >= 1:
        cats["Корпоративные события"] += 0.5
    categories = [c for c, _ in sorted(cats.items(), key=lambda kv: -kv[1])][:3] or ["Отраслевые изменения"]

    facts = []
    seen = set()
    for sig in signals[:6]:
        if sig["sentence"] in seen:
            continue
        seen.add(sig["sentence"])
        facts.append({"text": sig["quote"], "sentence": sig["sentence"], "factors": [sig["factor"]], "values": sig["values"]})
    if not facts:
        facts = [{"text": s[:420], "sentence": i, "factors": [], "values": []} for i, s in enumerate(sents[:2])]
    dates = parse_dates(full)
    summary = " ".join(f["text"] for f in facts[:2])[:600] or (sents[0] if sents else "")
    return {
        "signals": signals, "categories": categories, "facts": facts[:6], "sectors": sectors, "regions": regions,
        "countries": countries, "commodities": commodities, "orgs": list(dict.fromkeys(orgs))[:12],
        "dates": dates, "summary": summary, "injection_findings": injections, "clean_body": clean_body,
    }

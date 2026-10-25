"""Personalised, explainable ranking. Importance (how much it may matter) and confidence (how well founded) are separate."""
import math
from datetime import datetime, timezone

from .knowledge.lexicon import FED_DISTRICTS, REGIONS
from .knowledge.mechanisms import mechanisms_for
from .knowledge.ontology import ROLE_WEIGHTS
from .nlp.ru import stem


def _now():
    return datetime.now(timezone.utc)


def _age_days(iso):
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        return max(0.0, (_now() - d).total_seconds() / 86400)
    except (TypeError, ValueError):
        return 30.0


def region_match(profile, event_regions):
    if not event_regions:
        return None
    mine = " ".join(x for x in (profile.get("region"), profile.get("city")) if x).lower()
    if not mine:
        return None
    for name in event_regions:
        aliases = {**REGIONS, **FED_DISTRICTS}.get(name, [name.lower()])
        if name.lower() in mine or any(a in mine for a in aliases):
            return name
        if stem(name.split()[0]) == stem(mine.split()[0]) if mine.split() else False:
            return name
    return None


def score(profile, event, bank_hits=None, role=None, mechs=None):
    mechs = mechs if mechs is not None else mechanisms_for(profile, event)
    top = mechs[:3]
    base = 1 - math.prod(1 - m["impact"] for m in top) if top else 0.0
    reasons = [{"label": m["headline"], "points": round(m["impact"] * 100), "kind": m["kind"], "mechanism": m["id"],
                "features": [e["feature"] for e in m["exposure"]]} for m in top]
    bonus = 0.0
    sector_hit = profile.get("sector") in set(event.get("sectors") or [])
    if sector_hit and mechs:
        bonus += .06
        reasons.append({"label": f"Событие относится к вашей отрасли: {profile['sector_label']}", "points": 6, "kind": "direct", "features": ["okved"]})
    reg = region_match(profile, event.get("regions"))
    if reg:
        bonus += .05
        reasons.append({"label": f"Событие упоминает ваш регион: {reg}", "points": 5, "kind": "direct", "features": ["region"]})
    bank_hits = bank_hits or []
    bank_factor = any(h["factor_match"] for h in bank_hits)
    if bank_factor and mechs:
        bonus += .04
        reasons.append({"label": "По теме есть аналитика банка", "points": 4, "kind": "bank", "features": []})
    if not mechs and (sector_hit or reg):
        base = .12 if sector_hit else .08
    fresh = .55 + .45 * math.exp(-_age_days(event["last_seen"]) / 7.0)
    auth = .85 + .15 * float(event.get("authority") or .5)
    role_w = 1.0
    if role and mechs:
        role_w = ROLE_WEIGHTS.get(role, {}).get(mechs[0]["factor"], 1.0)
    importance = 100 * min(1.0, (base + bonus) * fresh * auth * role_w)
    fact_conf = .1 + .6 * float(event.get("authority") or .5) + min(.3, .1 * (event.get("source_count", 1) - 1)) - (.2 if event.get("contradictions") else 0)
    fact_conf = max(0.05, min(1.0, fact_conf))
    exposure_ev = (sum(m["evidence_share"] * m["impact"] for m in top) / (sum(m["impact"] for m in top) or 1)) if top else .3
    bank_c = 1.0 if bank_factor else (.5 if bank_hits else 0.0)
    conf = round(.4 * exposure_ev + .4 * fact_conf + .2 * bank_c, 3)
    label = "high" if conf >= .72 else "medium" if conf >= .5 else "low"
    if importance >= 78 and conf >= .6 and (event.get("source_count", 1) >= 2 or (event.get("authority") or 0) >= .85):
        prio = "critical"
    elif importance >= 58:
        prio = "high"
    elif importance >= 38:
        prio = "medium"
    elif importance >= 18:
        prio = "watch"
    else:
        prio = None
    if prio in ("critical", "high") and conf < .35:
        prio = "watch"
    return {"event_id": event["id"], "importance": round(importance, 1), "confidence_score": conf, "confidence": label, "priority": prio,
            "mechanisms": mechs, "reasons": reasons, "components": {"base": round(base, 3), "bonus": round(bonus, 3), "freshness": round(fresh, 3),
                                                                  "authority": round(auth, 3), "role": role_w, "fact_confidence": round(fact_conf, 3),
                                                                  "exposure_evidence": round(exposure_ev, 3), "bank_support": bank_c}}


def diversify(scored):
    """Penalise cards that repeat the same lead mechanism so the top of the feed is not five versions of one story."""
    seen = {}
    out = []
    for s in sorted(scored, key=lambda x: -x["importance"]):
        lead = s["mechanisms"][0]["id"] if s["mechanisms"] else None
        n = seen.get(lead, 0) if lead else 0
        s = dict(s)
        if n:
            s["importance"] = round(s["importance"] * (0.62 ** n), 1)
            s["reasons"] = s["reasons"] + [{"label": "Тема уже представлена выше: понижено, чтобы не дублировать", "points": 0, "kind": "dedup", "features": []}]
        if lead:
            seen[lead] = n + 1
        out.append(s)
    return sorted(out, key=lambda x: -x["importance"])

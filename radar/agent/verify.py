"""Self-check of a drafted insight: grounding, attribution, disclosure. Returns issues, never edits silently."""
import re

from ..knowledge.lexicon import INJECTION_PATTERNS
from ..nlp.ru import stems

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_BANK_VOICE = re.compile(r"(по\s+мнению|по\s+оценк\w+|считает|прогнозирует|ожидает)\s+(аналитик\w+\s+)?(банка|альфа)|аналитик\w+\s+(альфа|банка)|позици\w+\s+банка", re.I)


def _nums(text):
    out = set()
    for m in _NUM.findall(text or ""):
        v = float(m.replace(",", "."))
        if v >= 10 or "." in m or "," in m:
            out.add(round(v, 2))
    return out


def verify(insight):
    ev = insight["evidence"]
    issues = []
    claims = insight["claims"]
    for c in claims:
        cid = c["id"]
        if c["type"] != "UNKNOWN" and not c["evidence"]:
            issues.append({"code": "missing_evidence", "severity": "high", "claim": cid, "detail": "Утверждение без основания"})
        missing = [e for e in c["evidence"] if e not in ev]
        if missing:
            issues.append({"code": "unknown_evidence_id", "severity": "high", "claim": cid, "detail": "Ссылка на несуществующее основание: " + ", ".join(missing)})
        cited = [ev[e] for e in c["evidence"] if e in ev]
        if c["type"] == "BANK_ANALYSIS" and not any(x["type"] == "bank" for x in cited):
            issues.append({"code": "bank_without_bank_evidence", "severity": "high", "claim": cid, "detail": "Позиция банка без фрагмента аналитики банка"})
        if c["type"] in ("AI_INFERENCE", "SCENARIO", "FACT") and _BANK_VOICE.search(c["text"]) and not any(x["type"] == "bank" for x in cited):
            issues.append({"code": "bank_attribution_in_ai", "severity": "high", "claim": cid, "detail": "Формулировка приписывает вывод банку без источника"})
        if any(re.search(p, c["text"], re.I) for p in INJECTION_PATTERNS):
            issues.append({"code": "injection_artifact", "severity": "high", "claim": cid, "detail": "В тексте найден шаблон инструкции"})
        if c["type"] == "FACT" and cited:
            src = " ".join(x["text"] for x in cited)
            st, ss = set(stems(c["text"])), set(stems(src))
            if st and len(st & ss) / len(st) < .5 and c.get("origin") not in ("rules", "computed"):
                issues.append({"code": "fact_not_in_source", "severity": "high", "claim": cid, "detail": "Факт слабо подтверждается цитируемым источником"})
        if c["type"] in ("FACT", "BANK_ANALYSIS") or c.get("origin") == "llm":
            src_nums = set()
            for x in cited:
                src_nums |= _nums(x["text"]) | _nums(str(x.get("title", "")))
            for n in insight.get("calc_numbers", []):
                src_nums.add(round(n, 2))
            bad = sorted(_nums(c["text"]) - src_nums)
            if bad and cited:
                issues.append({"code": "ungrounded_number", "severity": "high" if c.get("origin") == "llm" else "medium", "claim": cid, "detail": "Числа не найдены в основаниях: " + ", ".join(f"{x:g}" for x in bad)})
        for f in c.get("features", []):
            if f"profile:{f}" not in ev and f not in ("graph", "okved"):
                issues.append({"code": "company_feature_mismatch", "severity": "medium", "claim": cid, "detail": f"Признак «{f}» отсутствует в профиле"})
    if insight.get("contradictions") and not any("противореч" in c["text"].lower() or "расходятся" in c["text"].lower() for c in claims if c["type"] == "UNKNOWN"):
        issues.append({"code": "contradiction_not_disclosed", "severity": "high", "claim": None, "detail": "Публикации противоречат друг другу, но в выводе это не раскрыто"})
    shares = [m["evidence_share"] for m in insight.get("scenarios", [])]
    if shares and sum(shares) / len(shares) < .75 and not any(c["type"] == "UNKNOWN" for c in claims):
        issues.append({"code": "no_unknowns_with_weak_evidence", "severity": "medium", "claim": None, "detail": "Основания слабые, а ограничения не названы"})
    if not insight.get("bank_view", {}).get("claim_ids") and insight.get("bank_view", {}).get("status") == "found":
        issues.append({"code": "bank_gap", "severity": "low", "claim": None, "detail": "Релевантная аналитика банка не найдена"})
    if insight.get("scenarios") and not insight.get("checks"):
        issues.append({"code": "no_checks", "severity": "medium", "claim": None, "detail": "Нет конкретных проверок"})
    sev = {"high": 3, "medium": 1, "low": .3}
    score = max(0.0, 1.0 - sum(sev[i["severity"]] for i in issues) / max(3.0, len(claims) * .8))
    return {"issues": issues, "score": round(score, 3), "passed": not any(i["severity"] == "high" for i in issues)}

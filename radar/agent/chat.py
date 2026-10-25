"""Follow-up dialogue over a prepared insight: intent routing, retrieval, calculator, grounded answers."""
import re

from .. import calc as calcmod
from ..db import dumps
from ..ingest.store import now_iso
from ..profile import build_profile
from ..retrieval import search
from .draft import best_excerpt
from .llm import BudgetExceeded, LLMError
from .verify import _nums

_MONEY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(трлн|млрд|млн|тыс)", re.I)
_PP = re.compile(r"([+-]?\d+(?:[.,]\d+)?)\s*(?:п\.?\s?п\.?|процентн\w+\s+пункт\w*)", re.I)
_PCT = re.compile(r"([+-]?\d+(?:[.,]\d+)?)\s*%")
_MULT = {"трлн": 1e12, "млрд": 1e9, "млн": 1e6, "тыс": 1e3}

INTENTS = [
    ("whatif", r"что\s+(будет\s+)?если|а\s+если|при\s+ставк|сколько\s+(это\s+)?(будет\s+)?стоит|рассчита|посчита|оцени\s+в\s+рубл"),
    ("breakdown", r"в\s+разрезе|по\s+(поставщик|контрагент|отрасл|получател|плательщик|покупател)|концентрац|структур\w+\s+платеж"),
    ("sources", r"источник|подтвержда|где\s+написано|ссылк|первоисточник|откуда"),
    ("bank", r"банк\w*\s+(считает|оценива|думает)|позици\w+\s+банка|аналитик\w+\s+(банка|альфа)|что\s+говорит\s+(банк|альфа)"),
    ("missing", r"не\s+хватает|каких\s+данных|какие\s+данные|что\s+неизвестно|уточнить|недостат"),
    ("features", r"признак|на\s+основании\s+чего|какие\s+данные\s+о\s+компан|что\s+вы\s+знаете\s+о\s+нас"),
    ("related", r"связанн|друг\w+\s+событ|похож|ещё\s+событ"),
    ("checks", r"что\s+(мне\s+)?(делать|проверить)|какие\s+шаги|действи|проверк"),
    ("why", r"почему|чем\s+важн|зачем|почему\s+это\s+важн|как\s+это\s+влия"),
]


def route(q):
    ql = q.lower()
    for name, pat in INTENTS:
        if re.search(pat, ql):
            return name
    return "open"


def _money(q):
    m = _MONEY.search(q)
    return float(m.group(1).replace(",", ".")) * _MULT[m.group(2).lower()] if m else None


def _num(rx, q):
    m = rx.search(q)
    return float(m.group(1).replace(",", ".")) if m else None


def _ans(text, ev=(), typ="AI_INFERENCE"):
    return {"text": text, "evidence": list(ev), "type": typ}


def answer(db, llm, insight, profile, question, run_budget=None):
    intent = route(question)
    ev = insight["evidence"]
    claims = {c["id"]: c for c in insight["claims"]}
    out = {"intent": intent, "answer": [], "blocks": [], "generated_by": "rules"}
    A = out["answer"]
    if intent == "why":
        for cid in insight["why_you"]["fact_ids"][:3]:
            c = claims[cid]
            A.append(_ans(c["text"], c["evidence"], "FACT"))
        for cid in insight["why_you"]["inference_ids"][:2]:
            c = claims[cid]
            A.append(_ans(c["text"], c["evidence"], "AI_INFERENCE"))
        top = max(((f, v["value"]) for f, v in profile["sens"].items()), key=lambda x: x[1])
        if not A:
            A.append(_ans("По доступным данным прямой связи события с профилем компании не установлено; оно оставлено для наблюдения.", [], "UNKNOWN"))
    elif intent == "features":
        for f in profile["features"][:10]:
            A.append(_ans(f"{f['label']}: {f['value']} ({'подтверждено данными' if f['kind'] == 'observed' else 'выведено'}; {f['source']})", [f"profile:{f['id']}"], "FACT"))
    elif intent == "sources":
        for k, e in list(ev.items())[:10]:
            if e["type"] in ("news", "bank"):
                A.append(_ans(f"{e['title']} — {e['source']}" + (f", {e['locator']}" if e.get("locator") else "") + (f" · {e['url']}" if e.get("url") else ""), [k], "FACT" if e["type"] == "news" else "BANK_ANALYSIS"))
        if not A:
            A.append(_ans("Первоисточники не сохранены.", [], "UNKNOWN"))
    elif intent == "bank":
        ids = insight["bank_view"]["claim_ids"]
        if ids:
            for cid in ids:
                A.append(_ans(claims[cid]["text"], claims[cid]["evidence"], "BANK_ANALYSIS"))
        else:
            A.append(_ans("В материалах банка нет аналитики, прямо относящейся к этому событию. Позиция банка не придумывается: ниже можно запросить поиск по другим формулировкам.", [], "UNKNOWN"))
    elif intent == "missing":
        for cid in insight["unknown_ids"][:6]:
            A.append(_ans(claims[cid]["text"], [], "UNKNOWN"))
    elif intent == "related":
        for r in insight.get("related", []):
            A.append(_ans(f"{r['title']} (темы: {', '.join(r['factors'])})", [], "FACT"))
        if not A:
            A.append(_ans("Связанных событий в загруженных материалах не найдено.", [], "UNKNOWN"))
    elif intent == "checks":
        for c in insight["checks"][:5]:
            A.append(_ans(c["text"], [], "AI_INFERENCE"))
    elif intent == "breakdown":
        g = profile.get("graph")
        if not g or not g["available"]:
            A.append(_ans("Платёжных связей этой компании в данных нет — разрез построить нельзя.", [], "UNKNOWN"))
        else:
            from ..graph import company_graph
            full = company_graph(db, profile["id"])
            q = question.lower()
            side = "payers" if re.search(r"покупател|плательщик", q) else "recipients"
            part = full[side]
            if re.search(r"отрасл", q):
                rows = [{"Отрасль": k, "Доля": f"{v:.0%}"} for k, v in part["sectors"].items()][:8]
            else:
                rows = [{"Контрагент": i["name"], "Отрасль": (i["okved_name"] or "—")[:40], "Доля": f"{i['share']:.0%}", "В группе": "да" if i["in_group"] else "нет"} for i in part["top"]]
            out["blocks"].append({"type": "table", "title": "Получатели платежей компании" if side == "recipients" else "Плательщики компании", "rows": rows})
            A.append(_ans(f"Концентрация: крупнейший контрагент — {part['top1_share']:.0%}, три крупнейших — {part['top3_share']:.0%}. {full['caveat']}", [f"graph:{side}"], "FACT"))
    elif intent == "whatif":
        kind = next((c for c in insight.get("calc", [])), None)
        q = question
        if re.search(r"ставк|кредит|долг|п\.?\s?п\.?|процентн", q.lower()):
            kind = "debt_service"
        if kind == "debt_service":
            debt, pp = _money(q), _num(_PP, q)
            fl = _num(re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:плавающ|долга)"), q)
            if debt and pp is not None:
                r = calcmod.run("debt_service", {"debt": debt, "floating_share": fl if fl is not None else 100, "rate_delta_pp": pp, "months": 12}, profile.get("revenue"))
                out["blocks"].append({"type": "calc", "result": r})
                fmt = lambda v: f"{v:,.0f}".replace(",", "\u00a0")
                A.append(_ans(f"При долге {fmt(debt)} ₽, изменении ставки на {pp:+g} п.п. и доле плавающей ставки {fl if fl is not None else 100:g}% годовой эффект составит {fmt(r['result'])} ₽. Допущения указаны в расчёте.", [], "AI_INFERENCE"))
            else:
                out["blocks"].append({"type": "form", "calc": calcmod.spec_for("debt_service", profile.get("revenue"))})
                A.append(_ans("Чтобы посчитать, нужны объём долга, доля плавающей ставки и изменение ставки — заполните форму или укажите их в вопросе, например: «что если ставка +2 п.п. при долге 5 млрд».", [], "UNKNOWN"))
        elif kind:
            out["blocks"].append({"type": "form", "calc": calcmod.spec_for(kind, profile.get("revenue"))})
            A.append(_ans("Для расчёта нужны ваши допущения: заполните форму. Данных банка о ваших договорах для этого недостаточно.", [], "UNKNOWN"))
        else:
            A.append(_ans("Для этого события количественный расчёт требует данных, которых нет в профиле; можно оценить условия вручную по списку проверок.", [], "UNKNOWN"))
    else:
        hits = search(db, question, k=4)
        from ..nlp.ru import stems as _stems
        qn = len(set(_stems(question))) or 1
        hits = [h for h in hits if len(h["terms"]) >= 2 and len(h["terms"]) / qn >= .4]
        for h in hits[:3]:
            key = ("bank:" if h["kind"] == "bank_analysis" else "doc:") + (str(h["chunk_id"]) if h["kind"] == "bank_analysis" else str(h["doc_id"]))
            if key not in ev:
                ev[key] = {"id": key, "type": "bank" if h["kind"] == "bank_analysis" else "news", "title": h["title"], "source": h["source"], "url": h["url"],
                           "locator": h["locator"], "published_at": h["published_at"], "text": h["text"], "is_synthetic": h["is_synthetic"]}
            A.append(_ans(best_excerpt(h["text"], question), [key], "BANK_ANALYSIS" if h["kind"] == "bank_analysis" else "FACT"))
        if not A:
            A.append(_ans("В загруженных материалах нет сведений для ответа на этот вопрос. Уточните формулировку или откройте список проверок по событию.", [], "UNKNOWN"))
    if llm and llm.configured and intent in ("why", "open", "checks", "missing") and A and A[0]["type"] != "UNKNOWN":
        try:
            pack = {"вопрос": question, "роль": insight.get("role"), "черновик_ответа": [a["text"] for a in A],
                    "основания": {k: {"type": e["type"], "text": e["text"][:500]} for k, e in ev.items()},
                    "схема": {"answer": [{"text": "ответ", "evidence": ["id оснований"]}]}}
            from .orchestrator import SYSTEM_PROMPT
            data, usage, model = llm.chat_json("light", SYSTEM_PROMPT, dumps(pack), max_tokens=700, run_budget=run_budget)
            new = []
            ok = True
            for it in data.get("answer", [])[:5]:
                e = [x for x in (it.get("evidence") or []) if x in ev]
                src = set()
                for x in e:
                    src |= _nums(ev[x]["text"])
                if not e or (_nums(str(it.get("text", ""))) - src):
                    ok = False
                    break
                new.append(_ans(str(it["text"])[:800], e, "AI_INFERENCE"))
            if ok and new:
                out["answer"], out["generated_by"] = new, "llm:" + model
        except (LLMError, BudgetExceeded):
            pass
    return out

"""Tool layer. The model never touches the database or network; it asks the orchestrator, which enforces scope."""
import time

from ..db import dumps
from ..graph import company_graph
from ..ingest.store import load_event, now_iso
from ..knowledge.mechanisms import mechanisms_for
from ..profile import build_profile
from ..retrieval import search

MAX_RESULT_CHARS = 24_000


class Forbidden(Exception):
    pass


class Context:
    """Per-request security context: who is asking, which companies they may see."""

    def __init__(self, db, user_id, role, allowed_companies, company_id, run_id=None, allowed_tools=None):
        self.db, self.user_id, self.role = db, user_id, role
        self.allowed_companies = set(allowed_companies)
        self.company_id, self.run_id = company_id, run_id
        self.allowed_tools = allowed_tools

    def audit(self, action, target="", allowed=True, detail=""):
        self.db.x("INSERT INTO audit(ts,user_id,run_id,actor,action,target,allowed,detail) VALUES (?,?,?,?,?,?,?,?)",
                  (now_iso(), self.user_id, self.run_id, "agent" if self.run_id else "user", action, str(target)[:200], int(allowed), str(detail)[:500]))


def _trim_graph(g, n=40):
    """Aggregates stay exact; only the long tail of individual counterparties is cut before it reaches the agent."""
    if not g:
        return g
    g = dict(g)
    for side in ("recipients", "payers"):
        g[side] = {**g[side], "items": g[side]["items"][:n]}
    return g


def _profile(ctx, **_):
    p = build_profile(ctx.db, ctx.company_id)
    p["graph"] = _trim_graph(p.get("graph"))
    return {"profile": p, "summary": f"{p['display_name']}; отрасль {p['sector_label']}; признаков: {len(p['features'])}; неизвестного: {len(p['unknown'])}"}


def _event(ctx, event_id, **_):
    ev = load_event(ctx.db, int(event_id))
    if not ev:
        raise ValueError("Событие не найдено")
    return {"event": ev, "summary": f"{ev['title'][:80]}; сигналов: {len(ev['signals'])}; источников: {ev['source_count']}"}


def _graph(ctx, **_):
    g = _trim_graph(company_graph(ctx.db, ctx.company_id))
    return {"graph": g, "summary": f"получателей {g['recipients']['n']}, плательщиков {g['payers']['n']}; группа: {len(g['group_members'])}"}


def _mechs(ctx, event_id, **_):
    p = build_profile(ctx.db, ctx.company_id)   # full graph aggregates are needed here; nothing but mechanisms leaves the tool
    ev = load_event(ctx.db, int(event_id))
    m = mechanisms_for(p, ev)
    return {"mechanisms": m, "summary": f"механизмов: {len(m)}; лидер: {m[0]['id'] if m else '—'}"}


def _bank(ctx, query, factors=None, k=4, **_):
    hits = search(ctx.db, query, kind="bank_analysis", factors=factors, k=int(k))
    return {"hits": hits, "summary": f"фрагментов банка: {len(hits)}" + (f"; лучший: {hits[0]['title'][:50]}" if hits else "")}


def _news(ctx, query, exclude_event_id=None, k=5, **_):
    hits = [h for h in search(ctx.db, query, kind="news", k=int(k) + 4)]
    ev_ids = []
    for h in hits:
        r = ctx.db.one("SELECT id FROM events WHERE doc_ids LIKE ?", (f'%{h["doc_id"]}%',))
        h["event_id"] = r["id"] if r else None
    hits = [h for h in hits if not exclude_event_id or h["event_id"] != int(exclude_event_id)][: int(k)]
    return {"hits": hits, "summary": f"связанных публикаций: {len(hits)}"}


def _recent_events(ctx, days=21, **_):
    rows = ctx.db.q("SELECT id FROM events WHERE last_seen >= datetime('now', ?) ORDER BY last_seen DESC LIMIT 200", (f"-{int(days)} days",))
    return {"event_ids": [r["id"] for r in rows], "summary": f"событий за {days} дн.: {len(rows)}"}


TOOLS = {
    "get_company_profile": (_profile, "read"), "get_event": (_event, "read"), "graph_exposure": (_graph, "read"),
    "match_mechanisms": (_mechs, "read"), "search_bank_analytics": (_bank, "read"), "search_news": (_news, "read"),
    "recent_events": (_recent_events, "read"),
}


def call(ctx, name, **args):
    t0 = time.time()
    if name not in TOOLS or (ctx.allowed_tools is not None and name not in ctx.allowed_tools):
        ctx.audit("tool", name, False, "инструмент не разрешён")
        raise Forbidden(f"Инструмент «{name}» не разрешён")
    if ctx.company_id not in ctx.allowed_companies:
        ctx.audit("tool", name, False, "нет доступа к компании")
        raise Forbidden("Нет доступа к данным этой компании")
    fn, _ = TOOLS[name]
    out = fn(ctx, **args)
    size = len(dumps({k: v for k, v in out.items() if k != "summary"}))
    if size > MAX_RESULT_CHARS * 4:
        ctx.audit("tool", name, False, "результат слишком велик")
        raise Forbidden("Результат инструмента превышает допустимый размер")
    ctx.audit("tool", name, True, dumps({k: (v if isinstance(v, (int, float, str)) else "…") for k, v in args.items()}))
    out["_ms"] = int((time.time() - t0) * 1000)
    return out

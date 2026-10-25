"""Application services: feed composition, insight lifecycle, cascades, ad-hoc analysis, quality metrics."""
import hashlib
import re
import time
from datetime import datetime, timezone

from .agent import chat as chat_mod
from .agent import cascade as cascade_mod
from .agent import orchestrator as orch
from .agent.llm import LLM
from .agent.tools import Context, Forbidden
from .db import dumps, loads
from .graph import network_view
from .ingest import files as files_mod
from .ingest import store, web
from .knowledge.mechanisms import mechanisms_for
from .knowledge.ontology import ROLE_LABELS
from .knowledge.sectors import FACTOR_LABELS
from .nlp.extract import analyze_text
from .profile import build_profile, public_profile
from .ranking import diversify, score
from . import calc as calcmod
from . import retrieval

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "watch": 3, None: 4}
_score_cache = {}


class NotFound(Exception):
    pass


class Service:
    def __init__(self, db):
        self.db = db
        self.llm = LLM(db)

    # ---------------------------------------------------------------- access
    def user_companies(self, user):
        if user["is_admin"]:
            raise RuntimeError("administrators are checked by existence, not by enumeration")
        return [r["id"] for r in self.db.q("SELECT company_id id FROM user_company WHERE user_id=?", (user["id"],))]

    def ctx(self, user, company_id, role=None):
        allowed = set(self.user_companies(user)) if not user["is_admin"] else {company_id}
        if not user["is_admin"] and company_id not in allowed:
            self.db.x("INSERT INTO audit(ts,user_id,actor,action,target,allowed,detail) VALUES (?,?,?,?,?,?,?)",
                      (store.now_iso(), user["id"], "user", "access_company", company_id, 0, "нет доступа"))
            raise Forbidden("Нет доступа к этой компании")
        if user["is_admin"] and not self.db.one("SELECT 1 FROM companies WHERE id=?", (company_id,)):
            raise NotFound("Компания не найдена")
        return Context(self.db, user["id"], role or user["role"], allowed, company_id)

    def companies_for(self, user, q=None, limit=40):
        cols = "id,display_name,okved_name,revenue,region,is_synthetic,client_type"
        if user["is_admin"]:
            if q:
                return self.db.q(f"SELECT {cols} FROM companies WHERE display_name LIKE ? OR id LIKE ? OR okved_name LIKE ? OR region LIKE ? ORDER BY revenue DESC LIMIT ?", (f"%{q}%",) * 4 + (limit,))
            return self.db.q(f"SELECT {cols} FROM companies ORDER BY revenue DESC LIMIT ?", (limit,))
        ids = self.user_companies(user)[:limit]
        if not ids:
            return []
        return self.db.q(f"SELECT {cols} FROM companies WHERE id IN ({','.join('?' * len(ids))}) ORDER BY revenue DESC", ids)

    # ---------------------------------------------------------------- feed
    def _scored(self, profile, role, days):
        events = self.db.q("SELECT id, version FROM events WHERE last_seen >= datetime('now', ?) ORDER BY last_seen DESC", (f"-{int(days)} days",))
        out = []
        for e in events:
            key = (profile["id"], e["id"], e["version"], role, int(time.time() // 120), store.index_version())
            hit = _score_cache.get(key)
            if hit is None:
                ev = store.load_event(self.db, e["id"])
                bank = retrieval.search(self.db, ev["title"], kind="bank_analysis", factors=[s["factor"] + (":" + s["commodity"] if s.get("commodity") else "") for s in ev["signals"]], k=3)
                bank = [h for h in bank if h["norm"] >= .3 or h["factor_match"]]
                hit = (score(profile, ev, bank, role), ev)
                _score_cache[key] = hit
                if len(_score_cache) > 20000:
                    _score_cache.clear()
            out.append(hit)
        return out

    def feed(self, user, company_id, role=None, days=21):
        role = role or user["role"]
        self.ctx(user, company_id, role)
        profile = build_profile(self.db, company_id)
        if not profile:
            raise NotFound("Компания не найдена")
        pairs = self._scored(profile, role, days)
        by_id = {s["event_id"]: ev for s, ev in pairs}
        ranked = [s for s in diversify([s for s, _ in pairs]) if s["priority"]]
        seen = self.db.one("SELECT last_seen FROM seen_state WHERE user_id=? AND company_id=?", (user["id"], company_id))
        last = seen["last_seen"] if seen else None
        cards = []
        for s in ranked[:40]:
            ev = by_id[s["event_id"]]
            lead = s["mechanisms"][0] if s["mechanisms"] else None
            ins = self.db.one("SELECT id FROM insights WHERE company_id=? AND kind='event' AND event_ids=? AND status='active' AND IFNULL(role,'')=? ORDER BY id DESC", (company_id, dumps([ev["id"]]), role or ""))
            cards.append({
                "event_id": ev["id"], "title": ev["title"], "headline": lead["headline"] if lead else ev["title"], "kind": lead["kind"] if lead else "watch",
                "summary": lead["how"] if lead else ev["summary"], "why": lead["why"] if lead else "Связь с профилем компании по доступным данным не установлена.",
                "importance": s["importance"], "priority": s["priority"], "confidence": s["confidence"], "confidence_score": s["confidence_score"],
                "reasons": s["reasons"][:3], "factors": sorted({x["factor"] for x in ev["signals"]}), "sources": ev["source_count"], "first_seen": ev["first_seen"], "last_seen": ev["last_seen"],
                "is_synthetic": bool(ev["is_synthetic"]), "contradictions": bool(ev["contradictions"]), "insight_id": ins["id"] if ins else None,
                "is_new": bool(last is None or ev["last_seen"] > last), "mechanisms": [m["id"] for m in s["mechanisms"][:3]],
                "bank_support": s["components"]["bank_support"] > 0, "role_label": ROLE_LABELS.get(role),
            })
        casc = self._cascade_cards(profile, [s for s in diversify([s for s, _ in pairs])], by_id)
        changes = self._changes(cards, last)
        return {"company": public_profile(profile), "role": role, "role_label": ROLE_LABELS.get(role), "cards": cards, "cascades": casc, "changes": changes,
                "counts": {"events_total": len(pairs), "relevant": len(ranked), "dropped": len(pairs) - len(ranked)}, "generated_at": store.now_iso()}

    def _changes(self, cards, last):
        if not last:
            return {"since": None, "new": len(cards), "items": [], "note": "Первый просмотр: показаны текущие события."}
        new = [c for c in cards if c["last_seen"] > last]
        return {"since": last, "new": len(new), "items": [{"event_id": c["event_id"], "title": c["headline"], "priority": c["priority"]} for c in new[:6]]}

    def mark_seen(self, user, company_id):
        self.ctx(user, company_id)
        self.db.x("INSERT INTO seen_state(user_id,company_id,last_seen) VALUES (?,?,?) ON CONFLICT(user_id,company_id) DO UPDATE SET last_seen=excluded.last_seen", (user["id"], company_id, store.now_iso()))

    # ---------------------------------------------------------------- insights
    def _cascade_cards(self, profile, scored, by_id):
        found = cascade_mod.detect(profile, [s for s in scored if s["mechanisms"]])
        titles = {i: e["title"] for i, e in by_id.items()}
        cards = []
        for c in found:
            key = hashlib.sha1((c["target"] + "|" + ",".join(str(x) for x in sorted(l["event_id"] for l in c["links"]))).encode()).hexdigest()[:12]
            c["key"] = key
            prev = self.db.one("SELECT id FROM insights WHERE company_id=? AND kind='cascade' AND status='active' AND event_ids=? ORDER BY id DESC", (profile["id"], dumps(sorted(l["event_id"] for l in c["links"]))))
            cards.append({"key": key, "target": c["target"], "target_label": c["target_label"], "score": c["score"], "confidence": c["confidence"], "confidence_score": c["confidence_score"],
                          "links": [{"event_id": l["event_id"], "mechanism_id": l["mechanism_id"], "title": titles.get(l["event_id"], ""), "headline": l["headline"], "factor": l["factor"], "factor_label": FACTOR_LABELS.get(l["factor"], l["factor"]),
                                     "strength": l["strength"], "confidence": l["confidence"], "path": l["path"]} for l in c["links"]],
                          "weakest": c["weakest"], "amplifiers": c["amplifiers"], "graph": cascade_mod.graph_of(c, titles), "insight_id": prev["id"] if prev else None, "_raw": c})
        return cards

    def event_insight(self, user, company_id, event_id, role=None, refresh=False):
        role = role or user["role"]
        ctx = self.ctx(user, company_id, role)
        ev = self.db.one("SELECT id, version, updated_at FROM events WHERE id=?", (event_id,))
        if not ev:
            raise NotFound("Событие не найдено")
        if not refresh:
            prev = self.db.one("SELECT id, created_at FROM insights WHERE company_id=? AND kind='event' AND event_ids=? AND status='active' AND IFNULL(role,'')=? ORDER BY id DESC",
                               (company_id, dumps([event_id]), role or ""))
            if prev and prev["created_at"] >= (ev["updated_at"] or ""):
                return orch.load_insight(self.db, prev["id"])
        return orch.analyze_event(ctx, self.llm, event_id, role)

    def cascade_insight(self, user, company_id, key, role=None):
        role = role or user["role"]
        ctx = self.ctx(user, company_id, role)
        profile = build_profile(self.db, company_id)
        pairs = self._scored(profile, role, 21)
        scored = [s for s, _ in pairs]
        by_id = {s["event_id"]: ev for s, ev in pairs}
        cards = self._cascade_cards(profile, diversify(scored), by_id)
        card = next((c for c in cards if c["key"] == key), None)
        if not card:
            raise NotFound("Каскад больше не актуален: сигналы изменились")
        if card["insight_id"]:
            return orch.load_insight(self.db, card["insight_id"])
        scored_by_event = {s["event_id"]: s for s in scored}
        return orch.analyze_cascade(ctx, self.llm, card["_raw"], scored_by_event, profile, role)

    def adhoc(self, user, company_id, title, text, url=None, role=None):
        role = role or user["role"]
        ctx = self.ctx(user, company_id, role)
        if url and not text:
            data, ctype = web.fetch(url, "text/html,*/*")
            t, body = web.extract_article(data)
            title, text = title or t, body
        if not text or len(text.strip()) < 60:
            raise ValueError("Вставьте текст новости (не менее нескольких предложений) или укажите ссылку")
        doc_id, created, event_id = store.add_document(self.db, "news", title or text[:90], text, "Материал пользователя", url=url, published_at=store.now_iso(),
                                                       meta={"adhoc": True, "user_id": user["id"], "company_id": company_id})
        if not event_id:
            raise ValueError("Материал не удалось отнести к событию")
        ev = store.load_event(self.db, event_id)
        profile = build_profile(self.db, company_id)
        mechs = mechanisms_for(profile, ev)
        if not mechs:
            return {"relevant": False, "event_id": event_id, "created": created, "title": ev["title"], "signals": ev["signals"], "sectors": ev["sectors"],
                    "message": "Система не нашла механизма влияния на эту компанию по её профилю. Сигналы и отрасли события показаны ниже — это можно проверить вручную.",
                    "injection": loads(self.db.one("SELECT meta FROM docs WHERE id=?", (doc_id,))["meta"], {}).get("injection_findings", [])}
        ins = orch.analyze_event(ctx, self.llm, event_id, role, ad_hoc=True)
        ins["adhoc"] = True
        return {"relevant": True, "event_id": event_id, "created": created, "insight": ins}

    # ---------------------------------------------------------------- chat & feedback
    def ask(self, user, insight_id, question):
        ins = orch.load_insight(self.db, insight_id)
        if not ins:
            raise NotFound("Инсайт не найден")
        self.ctx(user, ins["company_id"])
        profile = build_profile(self.db, ins["company_id"])
        self.db.x("INSERT INTO chat(insight_id,user_id,role,content,created_at) VALUES (?,?,?,?,?)", (insight_id, user["id"], "user", question, store.now_iso()))
        out = chat_mod.answer(self.db, self.llm, ins, profile, question, run_budget={"left": 6000})
        self.db.x("INSERT INTO chat(insight_id,user_id,role,content,citations,created_at) VALUES (?,?,?,?,?,?)",
                  (insight_id, user["id"], "assistant", dumps(out["answer"]), dumps({"intent": out["intent"], "blocks": out["blocks"]}), store.now_iso()))
        self.db.x("INSERT INTO audit(ts,user_id,actor,action,target,allowed,detail) VALUES (?,?,?,?,?,?,?)", (store.now_iso(), user["id"], "user", "chat", insight_id, 1, out["intent"]))
        out["evidence"] = {k: ins["evidence"][k] for a in out["answer"] for k in a["evidence"] if k in ins["evidence"]}
        return out

    def history(self, user, insight_id):
        ins = orch.load_insight(self.db, insight_id)
        if not ins:
            raise NotFound("Инсайт не найден")
        self.ctx(user, ins["company_id"])
        rows = self.db.q("SELECT role,content,citations,created_at FROM chat WHERE insight_id=? AND user_id=? ORDER BY id", (insight_id, user["id"]))
        return [{"role": r["role"], "content": loads(r["content"], r["content"]) if r["role"] == "assistant" else r["content"], "meta": loads(r["citations"], {}), "at": r["created_at"]} for r in rows]

    def feedback(self, user, insight_id, kind, comment=""):
        if kind not in {"useful", "irrelevant", "wrong", "duplicate", "not_my_company"}:
            raise ValueError("Неизвестный тип отзыва")
        ins = orch.load_insight(self.db, insight_id)
        if not ins:
            raise NotFound("Инсайт не найден")
        self.ctx(user, ins["company_id"])
        self.db.x("DELETE FROM feedback WHERE insight_id=? AND user_id=?", (insight_id, user["id"]))
        self.db.x("INSERT INTO feedback(insight_id,user_id,kind,comment,created_at) VALUES (?,?,?,?,?)", (insight_id, user["id"], kind, (comment or "")[:500], store.now_iso()))
        return {"ok": True}

    def calc(self, user, company_id, kind, inputs):
        self.ctx(user, company_id)
        p = self.db.one("SELECT revenue FROM companies WHERE id=?", (company_id,))
        return calcmod.run(kind, inputs, p["revenue"] if p else None)

    def calc_specs(self, user, company_id, kinds):
        self.ctx(user, company_id)
        p = self.db.one("SELECT revenue FROM companies WHERE id=?", (company_id,))
        return [calcmod.spec_for(k, p["revenue"]) for k in kinds if k in calcmod.CALCS]

    def trace(self, user, run_id):
        r = self.db.one("SELECT * FROM agent_runs WHERE id=?", (run_id,))
        if not r:
            raise NotFound("Запуск не найден")
        self.ctx(user, r["company_id"])
        return {"id": r["id"], "kind": r["kind"], "status": r["status"], "mode": r["mode"], "model": r["model"], "plan": loads(r["plan"], []), "trace": loads(r["trace"], []),
                "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"], "llm_calls": r["llm_calls"], "replans": r["replans"], "duration_ms": r["duration_ms"], "error": r["error"], "created_at": r["created_at"]}

    def network(self, user, company_id):
        self.ctx(user, company_id)
        return network_view(self.db, company_id)

    # ---------------------------------------------------------------- library
    def library(self, user):
        docs = self.db.q("SELECT id,kind,title,source_name,url,published_at,is_synthetic,status,meta FROM docs ORDER BY published_at DESC LIMIT 300")
        for d in docs:
            m = loads(d.pop("meta"), {})
            d["injection_findings"] = len(m.get("injection_findings", []))
            d["adhoc"] = bool(m.get("adhoc"))
        docs = [d for d in docs if not d["adhoc"] or user["is_admin"]]
        return {"docs": docs, "llm": self.llm_status(), "counts": {"news": sum(d["kind"] == "news" for d in docs), "bank": sum(d["kind"] == "bank_analysis" for d in docs)}}

    def llm_status(self):
        return {"configured": self.llm.configured, "light": self.llm.light, "deep": self.llm.deep, "tokens_today": self.llm.tokens_today() if self.llm.configured else 0}

    def upload_doc(self, user, name, raw, kind):
        if not user["is_admin"]:
            raise Forbidden("Загрузка материалов доступна администратору")
        low = name.lower()
        if low.endswith(".csv"):
            from .ingest import datasets
            k = datasets.detect_kind(raw)
            fn = {"companies": datasets.import_companies, "persons": datasets.import_persons, "payments": datasets.import_payments}.get(k)
            if not fn:
                raise ValueError("Не удалось определить тип CSV по заголовкам")
            res = fn(self.db, raw, name)
            store._bump()
            _score_cache.clear()
            return {"dataset": k, **res}
        title, blocks = files_mod.read_blocks(name, raw)
        body = "\n\n".join(t for _, t in blocks)
        if kind == "bank_analysis":
            pub = files_mod.guess_date(body[:3000])
            did, created, _ = store.add_document(self.db, "bank_analysis", re.sub(r"\.\w+$", "", name).replace("_", " "), body, "Альфа-Банк, Центр макроэкономических исследований", published_at=pub, blocks=blocks, meta={"file": name})
        else:
            did, created, _ = store.add_document(self.db, "news", title, body, "Загруженный материал", published_at=store.now_iso(), meta={"file": name})
        _score_cache.clear()
        return {"doc_id": did, "created": created, "chunks": len(files_mod.chunk_blocks(blocks))}

    def pull_feed(self, user, url):
        if not user["is_admin"]:
            raise Forbidden("Сбор новостей доступен администратору")
        data, _ = web.fetch(url, "application/rss+xml,application/atom+xml,text/xml,*/*")
        items = web.parse_feed(data)
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        added = skipped = 0
        for it in items[:60]:
            try:
                _, created, _ = store.add_document(self.db, "news", it["title"], it["body"] or it["title"] + ". " + it["title"], host, url=it["url"], published_at=it["published_at"], author=it["author"])
                added += int(created)
                skipped += int(not created)
            except ValueError:
                skipped += 1
        _score_cache.clear()
        return {"items": len(items), "added": added, "skipped": skipped}

    # ---------------------------------------------------------------- quality
    def metrics(self, user):
        q = self.db.one
        runs = q("SELECT COUNT(*) n, COALESCE(AVG(duration_ms),0) ms, COALESCE(SUM(tokens_in+tokens_out),0) tok, COALESCE(SUM(llm_calls),0) calls, COALESCE(SUM(replans),0) replans, "
                 "SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) errs, SUM(CASE WHEN mode='llm' THEN 1 ELSE 0 END) llm_runs FROM agent_runs")
        ins = self.db.q("SELECT payload FROM insights WHERE status='active' ORDER BY id DESC LIMIT 200")
        types, grounded, total, vscore, passed, unknown_cov = {}, 0, 0, [], 0, 0
        for r in ins:
            p = loads(r["payload"], {})
            for c in p.get("claims", []):
                types[c["type"]] = types.get(c["type"], 0) + 1
                if c["type"] != "UNKNOWN":
                    total += 1
                    grounded += int(bool(c["evidence"]))
            v = p.get("verification", {})
            vscore.append(v.get("score", 0))
            passed += int(v.get("passed", False))
            unknown_cov += int(bool(p.get("unknown_ids")))
        fb = {r["kind"]: r["n"] for r in self.db.q("SELECT kind, COUNT(*) n FROM feedback GROUP BY kind")}
        fb_total = sum(fb.values())
        n = len(ins) or 1
        audit = q("SELECT COUNT(*) n, SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) denied FROM audit")
        docs = q("SELECT COUNT(*) n, SUM(CASE WHEN meta LIKE '%injection_findings%' THEN 1 ELSE 0 END) inj FROM docs")
        return {
            "corpus": {"docs": docs["n"], "events": q("SELECT COUNT(*) n FROM events")["n"], "multi_source_events": q("SELECT COUNT(*) n FROM events WHERE source_count>1")["n"],
                       "contradictions": q("SELECT COUNT(*) n FROM events WHERE contradictions<>'[]'")["n"], "companies": q("SELECT COUNT(*) n FROM companies")["n"],
                       "injection_blocked": docs["inj"] or 0},
            "insights": {"active": len(ins), "claim_types": types, "evidence_coverage": round(grounded / total, 3) if total else None,
                         "verification_avg": round(sum(vscore) / n, 3) if vscore else None, "verification_pass_rate": round(passed / n, 3) if ins else None,
                         "with_disclosed_unknowns": round(unknown_cov / n, 3) if ins else None},
            "agent": {"runs": runs["n"], "avg_ms": int(runs["ms"]), "tokens": runs["tok"], "llm_calls": runs["calls"], "replans": runs["replans"], "errors": runs["errs"] or 0,
                      "llm_share": round((runs["llm_runs"] or 0) / runs["n"], 3) if runs["n"] else None},
            "feedback": {"total": fb_total, "by_kind": fb, "useful_rate": round(fb.get("useful", 0) / fb_total, 3) if fb_total else None},
            "security": {"audit_events": audit["n"], "denied": audit["denied"] or 0},
            "llm": self.llm_status(),
        }

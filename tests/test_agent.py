import unittest

from radar.agent import chat, orchestrator as orch
from radar.agent.cascade import detect
from radar.agent.llm import LLM, BudgetExceeded, LLMError, parse_json
from radar.agent.tools import Context, Forbidden, call
from radar.agent.verify import verify
from radar.config import settings
from radar.ingest.store import load_event
from radar.knowledge.mechanisms import mechanisms_for
from radar.profile import build_profile
from radar.ranking import score
from tests.helpers import fake_llm, seeded_db


def ctx(db, company="U-DEMO-0001", allowed=None):
    return Context(db, 1, "cfo", allowed or {company}, company)


def event_with(db, factor, commodity=None):
    return next(r["id"] for r in db.q("SELECT id FROM events ORDER BY id") if any(s["factor"] == factor and s.get("commodity") == commodity for s in load_event(db, r["id"])["signals"]))


class AgentLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = seeded_db()
        cls.rate = event_with(cls.db, "rate")

    def run_event(self, llm=None, company="U-DEMO-0001", eid=None):
        return orch.analyze_event(ctx(self.db, company), llm, eid or self.rate, "cfo")

    def test_trace_shows_plan_tools_verify_and_finalize(self):
        ins = self.run_event()
        run = self.db.one("SELECT * FROM agent_runs WHERE id=?", (ins["run_id"],))
        import json
        kinds = [s["kind"] for s in json.loads(run["trace"])]
        names = [s["name"] for s in json.loads(run["trace"]) if s["kind"] == "tool"]
        self.assertEqual(kinds[0], "plan")
        self.assertIn("verify", kinds)
        self.assertEqual(kinds[-1], "finalize")
        self.assertTrue({"get_company_profile", "get_event", "match_mechanisms", "search_bank_analytics"} <= set(names))

    def test_every_non_unknown_claim_has_evidence_that_exists(self):
        ins = self.run_event()
        for c in ins["claims"]:
            if c["type"] != "UNKNOWN":
                self.assertTrue(c["evidence"], c)
                self.assertTrue(all(e in ins["evidence"] for e in c["evidence"]), c)

    def test_bank_view_uses_only_bank_evidence(self):
        ins = self.run_event()
        bank = [c for c in ins["claims"] if c["type"] == "BANK_ANALYSIS"]
        self.assertTrue(bank)
        for c in bank:
            self.assertTrue(all(e.startswith("bank:") for e in c["evidence"]))
        self.assertFalse(any(c["type"] == "AI_INFERENCE" and any(e.startswith("bank:") for e in c["evidence"]) and c["origin"] == "rules" for c in ins["claims"]))

    def test_missing_bank_view_is_disclosed_not_invented(self):
        eid = event_with(self.db, "tech")
        ins = self.run_event(eid=eid, company="U-DEMO-0005")
        self.assertEqual(ins["bank_view"]["status"], "none")
        self.assertTrue(any("нет аналитики" in c["text"] for c in ins["claims"] if c["type"] == "UNKNOWN"))

    def test_contradiction_is_disclosed(self):
        eid = event_with(self.db, "inflation")
        ev = load_event(self.db, eid)
        self.assertTrue(ev["contradictions"])
        ins = self.run_event(eid=eid)
        self.assertTrue(any("расходятся" in c["text"] for c in ins["claims"] if c["type"] == "UNKNOWN"))
        self.assertTrue(ins["verification"]["passed"])

    def test_scoped_tool_denies_foreign_company_and_logs(self):
        c = ctx(self.db, "U-DEMO-0002", allowed={"U-DEMO-0001"})
        with self.assertRaises(Forbidden):
            call(c, "get_company_profile")
        self.assertTrue(self.db.one("SELECT 1 FROM audit WHERE allowed=0 AND action='tool' ORDER BY id DESC"))

    def test_unknown_tool_is_refused(self):
        with self.assertRaises(Forbidden):
            call(ctx(self.db), "run_sql", q="select 1")

    def test_deterministic_mode_works_without_llm(self):
        ins = self.run_event(llm=None)
        self.assertEqual(ins["ai_view"]["generated_by"], "rules")


class WithModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = seeded_db()
        cls.rate = event_with(cls.db, "rate")

    def llm(self, tr):
        return LLM(self.db, base_url="http://fake", api_key="k", transport=tr)

    def run_event(self, tr, **kw):
        return orch.analyze_event(ctx(self.db), self.llm(tr), self.rate, "cfo", **kw)

    def good(self):
        return fake_llm([{"text": "У компании подтверждены кредитные продукты, а ставка остаётся 14%: стоимость обслуживания долга не снижается.", "evidence": ["profile:p_loa", "doc:%d" % self.db.one("SELECT id FROM docs WHERE title LIKE 'Банк России сохранил%'")["id"]]}])

    def test_grounded_model_output_is_accepted(self):
        ins = self.run_event(self.good())
        self.assertTrue(ins["ai_view"]["generated_by"].startswith("llm"))
        self.assertTrue(ins["ai_view"]["claim_ids"])

    def test_model_inventing_numbers_is_dropped_with_trace(self):
        tr = fake_llm([{"text": "Нагрузка вырастет на 37 млрд рублей в год.", "evidence": ["profile:p_loa"]}])
        ins = self.run_event(tr)
        self.assertEqual(ins["ai_view"]["generated_by"], "rules")
        self.assertFalse(any("37" in c["text"] for c in ins["claims"]))
        run = self.db.one("SELECT trace FROM agent_runs WHERE id=?", (ins["run_id"],))
        self.assertIn("drop_claim", run["trace"])

    def test_model_citing_missing_evidence_is_dropped(self):
        ins = self.run_event(fake_llm([{"text": "Вывод без основания.", "evidence": ["doc:99999"]}]))
        self.assertFalse(any(c["origin"] == "llm" for c in ins["claims"]))

    def test_model_attributing_stance_to_bank_without_source_is_dropped(self):
        ins = self.run_event(fake_llm([{"text": "По мнению аналитиков банка, ставка будет снижена.", "evidence": ["profile:p_loa"]}]))
        self.assertFalse(any(c["origin"] == "llm" for c in ins["claims"]))

    def test_gateway_failure_falls_back(self):
        ins = self.run_event(fake_llm(fail=True))
        self.assertEqual(ins["ai_view"]["generated_by"], "rules")
        self.assertTrue(ins["claims"])

    def test_garbage_json_falls_back(self):
        ins = self.run_event(fake_llm(bad_json=True))
        self.assertEqual(ins["ai_view"]["generated_by"], "rules")

    def test_only_allowed_models(self):
        with self.assertRaises(LLMError):
            LLM(self.db, base_url="http://x", api_key="k", light="gpt-4o")

    def test_run_token_budget_is_enforced(self):
        llm = self.llm(fake_llm([], usage=900))
        budget = {"left": 500}
        llm.chat_json("deep", "s", "u", run_budget=budget)
        with self.assertRaises(BudgetExceeded):
            llm.chat_json("deep", "s", "u", run_budget=budget)

    def test_external_text_is_not_sent_with_injection_phrases(self):
        tr = self.good()
        ev = self.db.one("SELECT id FROM events WHERE title LIKE 'Обзор рынка металлов%'")
        orch.analyze_event(ctx(self.db), self.llm(tr), ev["id"], "ceo")
        sent = " ".join(m["content"] for p in tr.calls for m in p["messages"])
        self.assertNotIn("Игнорируй все предыдущие", sent)

    def test_parse_json_tolerates_fences_and_thinking(self):
        self.assertEqual(parse_json("<think>x</think>```json\n{\"a\": 1}\n```"), {"a": 1})


class Cascade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = seeded_db()

    def scored(self, cid):
        p = build_profile(self.db, cid)
        return p, [score(p, load_event(self.db, r["id"]), [], None) for r in self.db.q("SELECT id FROM events WHERE last_seen >= datetime('now','-21 days')")]

    def test_at_least_two_independent_events_converge(self):
        p, sc = self.scored("U-DEMO-0001")
        found = detect(p, sc)
        self.assertTrue(found)
        for c in found:
            self.assertGreaterEqual(len({l["event_id"] for l in c["links"]}), 2)
            self.assertTrue(c["weakest"])

    def test_single_event_never_forms_a_cascade(self):
        p, sc = self.scored("U-DEMO-0001")
        self.assertEqual(detect(p, sc[:1]), [])

    def test_company_without_exposure_gets_none(self):
        p, sc = self.scored("U-DEMO-0005")
        found = detect(p, [s for s in sc if not s["mechanisms"] or s["mechanisms"][0]["factor"] == "tech"])
        self.assertEqual(found, [])


class Dialogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = seeded_db()
        eid = event_with(cls.db, "rate")
        cls.ins = orch.analyze_event(ctx(cls.db), None, eid, "cfo")
        cls.p = build_profile(cls.db, "U-DEMO-0001")

    def ask(self, q):
        return chat.answer(self.db, None, self.ins, self.p, q)

    def test_whatif_is_computed_not_guessed(self):
        r = self.ask("что если ставка +2 п.п. при долге 5 млрд")
        self.assertEqual(r["intent"], "whatif")
        self.assertTrue(any(b["type"] == "calc" and abs(b["result"]["result"] - 100e6) < 1 for b in r["blocks"]))

    def test_whatif_without_numbers_asks_for_them(self):
        r = self.ask("что если ставка вырастет")
        self.assertTrue(any(b["type"] == "form" for b in r["blocks"]))

    def test_breakdown_returns_table_from_graph(self):
        r = self.ask("покажи в разрезе контрагентов")
        self.assertTrue(any(b["type"] == "table" and b["rows"] for b in r["blocks"]))

    def test_unanswerable_question_says_so(self):
        r = self.ask("какой прогноз погоды на завтра в Париже?")
        self.assertEqual(r["answer"][0]["type"], "UNKNOWN")

    def test_missing_data_question_lists_unknowns(self):
        r = self.ask("каких данных не хватает?")
        self.assertTrue(all(a["type"] == "UNKNOWN" for a in r["answer"]))


class LargeNetwork(unittest.TestCase):
    def test_company_with_thousands_of_counterparties_still_analyses(self):
        from radar.ingest import datasets, store
        from tests.helpers import fresh_db
        db = fresh_db()
        rows = "SYNTHETIC_U;MAINOKVED_CODE;MAINOKVED_NAME;REVENUE_COMPANY;CL_TYPE;CL_PRODUCT_LOA_MARK\nBIG;46.90;Торговля оптовая;90000000000;CLIENT;1\n" + "".join(f"S{i};24.10;Сталь;1000000;CLIENT;0\n" for i in range(3000))
        datasets.import_companies(db, rows.encode())
        pay = "PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\n" + "".join(f"BIG;S{i};{1000 + i};3\n" for i in range(3000)) + "".join(f"X{i};BIG;500;2\n" for i in range(2000))
        datasets.import_payments(db, pay.encode())
        _, _, eid = store.add_document(db, "news", "Банк России сохранил ключевую ставку на уровне 14,0%", "Банк России сохранил ключевую ставку на уровне 14,0% годовых. Риторика регулятора стала жёстче.", "Банк России", published_at=None)
        c = Context(db, 1, "cfo", {"BIG"}, "BIG")
        ins = orch.analyze_event(c, None, eid, "cfo")
        self.assertTrue(ins["verification"]["passed"])
        self.assertIn("graph:recipients", ins["evidence"])

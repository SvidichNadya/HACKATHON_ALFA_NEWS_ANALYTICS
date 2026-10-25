import unittest
from datetime import datetime, timedelta, timezone

from radar.ingest import store
from radar.ingest.store import load_event
from radar.knowledge.mechanisms import mechanisms_for
from radar.profile import build_profile
from radar.ranking import diversify, score
from radar import retrieval, calc
from tests.helpers import fresh_db, seeded_db

NOW = datetime.now(timezone.utc)


def pub(days=1):
    return (NOW - timedelta(days=days)).isoformat()


class Clustering(unittest.TestCase):
    def test_rewrites_merge_and_contradictions_are_kept(self):
        db = fresh_db()
        _, _, e1 = store.add_document(db, "news", "Инфляция ускорилась: цены выросли на 0,3%", "Недельная инфляция ускорилась, потребительские цены выросли на 0,3% по данным Росстата.", "Росстат", published_at=pub())
        _, _, e2 = store.add_document(db, "news", "Инфляция замедлилась: цены выросли на 0,1%", "Недельная инфляция замедлилась, потребительские цены выросли на 0,1% по данным Росстата.", "Деловой курс", published_at=pub())
        self.assertEqual(e1, e2)
        ev = load_event(db, e1)
        self.assertEqual(ev["source_count"], 2)
        self.assertTrue(ev["contradictions"], "opposite directions must be disclosed, not silently resolved")

    def test_exact_duplicate_is_idempotent(self):
        db = fresh_db()
        a = store.add_document(db, "news", "Цены на сталь выросли на 6%", "Цены на сталь и прокат выросли на 6% за месяц на фоне спроса.", "A", published_at=pub())
        b = store.add_document(db, "news", "Цены на сталь выросли на 6%", "Цены на сталь и прокат выросли на 6% за месяц на фоне спроса.", "A", published_at=pub())
        self.assertEqual(a[0], b[0])
        self.assertFalse(b[1])
        self.assertEqual(db.one("SELECT COUNT(*) n FROM events")["n"], 1)

    def test_unrelated_stories_stay_separate_and_old_story_is_not_merged(self):
        db = fresh_db()
        _, _, a = store.add_document(db, "news", "Цены на сталь выросли на 6%", "Цены на сталь и прокат выросли на 6% за месяц на фоне спроса.", "A", published_at=pub(1))
        _, _, b = store.add_document(db, "news", "Цены на сталь выросли на 2% в июле", "Цены на сталь выросли на 2% по итогам июля, сезонный спрос на прокат.", "B", published_at=pub(60))
        self.assertNotEqual(a, b)

    def test_too_short_material_rejected(self):
        with self.assertRaises(ValueError):
            store.add_document(fresh_db(), "news", "Заголовок", "коротко", "A")


class Personalisation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = seeded_db()
        cls.rate = next(r["id"] for r in cls.db.q("SELECT id FROM events") if any(s["factor"] == "rate" for s in load_event(cls.db, r["id"])["signals"]))

    def mech_ids(self, cid, eid=None):
        return {m["id"] for m in mechanisms_for(build_profile(self.db, cid), load_event(self.db, eid or self.rate))}

    def test_borrower_sees_debt_risk_depositor_sees_opportunity(self):
        borrower = self.mech_ids("U-DEMO-0001")
        depositor = self.mech_ids("U-DEMO-0005")
        self.assertIn("rate_debt_high", borrower)
        self.assertNotIn("rate_debt_high", depositor)
        self.assertIn("rate_deposit_high", depositor)

    def test_same_event_different_sign_for_producer_and_consumer(self):
        steel = next(r["id"] for r in self.db.q("SELECT id FROM events") if any(s.get("commodity") == "steel" for s in load_event(self.db, r["id"])["signals"]))
        self.assertIn("commodity_seller_steel", self.mech_ids("U-DEMO-0001", steel))
        self.assertIn("commodity_buyer_steel", self.mech_ids("U-DEMO-0004", steel))
        self.assertNotIn("commodity_buyer_steel", self.mech_ids("U-DEMO-0001", steel))

    def test_no_exposure_means_no_invented_mechanism(self):
        noise = next(r["id"] for r in self.db.q("SELECT id,title FROM events") if "Футбольный" in r["title"])
        for cid in ("U-DEMO-0001", "U-DEMO-0005"):
            ev = load_event(self.db, noise)
            self.assertEqual(mechanisms_for(build_profile(self.db, cid), ev), [])
            self.assertIsNone(score(build_profile(self.db, cid), ev, [], None)["priority"])

    def test_top_lists_differ_between_companies(self):
        tops = {}
        for cid in ("U-DEMO-0001", "U-DEMO-0003", "U-DEMO-0005"):
            p = build_profile(self.db, cid)
            sc = [score(p, load_event(self.db, r["id"]), [], None) for r in self.db.q("SELECT id FROM events")]
            tops[cid] = [s["event_id"] for s in diversify(sc)[:5]]
        self.assertNotEqual(set(tops["U-DEMO-0001"]), set(tops["U-DEMO-0005"]))
        self.assertNotEqual(set(tops["U-DEMO-0003"]), set(tops["U-DEMO-0005"]))

    def test_importance_and_confidence_are_separate(self):
        p = build_profile(self.db, "U-DEMO-0001")
        one = score(p, load_event(self.db, self.rate), [], None)
        self.assertIn("confidence_score", one)
        weak = dict(load_event(self.db, self.rate), authority=.3, source_count=1)
        two = score(p, weak, [], None)
        self.assertLess(two["confidence_score"], one["confidence_score"])

    def test_freshness_decays(self):
        p = build_profile(self.db, "U-DEMO-0001")
        ev = load_event(self.db, self.rate)
        old = dict(ev, last_seen=pub(90))
        self.assertLess(score(p, old, [], None)["importance"], score(p, ev, [], None)["importance"])

    def test_profile_marks_unknowns_instead_of_guessing(self):
        p = build_profile(self.db, "U-DEMO-0001")
        self.assertTrue(any("Условия финансирования" in u["text"] or "график" in u["text"] for u in p["unknown"]))
        self.assertTrue(all(f["kind"] in ("observed", "derived") for f in p["features"]))


class Retrieval(unittest.TestCase):
    def test_bank_search_returns_locator_and_kind(self):
        db = seeded_db()
        hits = retrieval.search(db, "ключевая ставка пауза риторика", kind="bank_analysis", k=3)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["kind"], "bank_analysis")
        self.assertTrue(hits[0]["locator"])
        self.assertIn("ставк", hits[0]["title"].lower() + hits[0]["text"].lower())


class Calculator(unittest.TestCase):
    def test_debt_service(self):
        r = calc.run("debt_service", {"debt": 5e9, "floating_share": 60, "rate_delta_pp": 1, "months": 12})
        self.assertAlmostEqual(r["result"], 30e6)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            calc.run("debt_service", {"debt": "abc", "floating_share": 60, "rate_delta_pp": 1})
        with self.assertRaises(ValueError):
            calc.run("debt_service", {"debt": 1, "floating_share": 160, "rate_delta_pp": 1})

    def test_pass_through(self):
        r = calc.run("input_cost", {"purchases": 1e9, "price_change_pct": 10, "passthrough_pct": 50})
        self.assertAlmostEqual(r["result"], -50e6)


class Importers(unittest.TestCase):
    def test_contest_csv_roundtrip_and_tolerance(self):
        from pathlib import Path
        from radar.ingest import datasets
        db = fresh_db()
        root = Path(__file__).resolve().parent.parent / "data" / "samples"
        c = (root / "df_Uid_data_hack.csv").read_bytes()
        self.assertEqual(datasets.detect_kind(c), "companies")
        n = datasets.import_companies(db, c)["imported"]
        self.assertGreater(n, 400)
        p = (root / "df_Payments_hack.csv").read_bytes()
        self.assertEqual(datasets.detect_kind(p), "payments")
        self.assertGreater(datasets.import_payments(db, p)["imported"], 1000)
        self.assertEqual(datasets.detect_kind((root / "df_Fid_link_hack.csv").read_bytes()), "persons")
        # semicolon-separated cp1251 file with missing columns must still import
        raw = "SYNTHETIC_U;MAINOKVED_CODE;MAINOKVED_NAME;REVENUE_COMPANY\nX1;24.10;Производство стали;1 200 000 000,5\nX2;;;\n".encode("cp1251")
        db2 = fresh_db()
        self.assertEqual(datasets.import_companies(db2, raw)["imported"], 2)
        p2 = build_profile(db2, "X1")
        self.assertEqual(p2["sector"], "metallurgy")
        self.assertAlmostEqual(p2["revenue"], 1200000000.5)
        self.assertTrue(any(u["id"] == "okved" for u in build_profile(db2, "X2")["unknown"]))

    def test_payments_keep_external_counterparties_but_drop_unrelated_rows(self):
        from radar.ingest import datasets
        from radar.graph import company_graph
        db = fresh_db()
        datasets.import_companies(db, "SYNTHETIC_U;MAINOKVED_CODE;MAINOKVED_NAME;REVENUE_COMPANY\nA;24.10;Сталь;100\nB;46.90;Торговля;50\n".encode())
        r = datasets.import_payments(db, "PAYER;BENEFICIARY;PAY_AMT;PAY_CNT\nA;B;100;2\nA;ZZ;300;1\nQQ;WW;9;1\nA;A;5000;9\n".encode())
        self.assertEqual((r["imported"], r["skipped_both_unknown"], r["self_flows"]), (3, 1, 1))
        g = company_graph(db, "A")
        self.assertEqual(g["recipients"]["n"], 2, "self-payments are not counterparties")
        self.assertAlmostEqual(g["recipients"]["top1_share"], .75)       # the external counterparty counts toward concentration
        self.assertAlmostEqual(g["recipients"]["classified_share"], .25)  # ...but its industry is unknown, and that is reported
        self.assertEqual(g["internal_turnover"]["amount"], 5000)

    def test_real_export_conventions(self):
        from radar.ingest import datasets
        from radar.knowledge.sectors import normalize_okved, sector_by_okved
        self.assertEqual(normalize_okved("1.11"), "01.11")
        self.assertEqual(sector_by_okved("1.11"), "agri")
        self.assertEqual(normalize_okved("46.71.2"), "46.71.2")
        db = fresh_db()
        raw = ("SYNTHETIC_U;ORG_TYPE;MAINOKVED_CODE;MAINOKVED_NAME;CL_TYPE;CL_PRODUCT_LOA_MARK;FTS_FLAG;FTS_COUNTRY_NAME;REVENUE_COMPANY;GROUP_ID;REGION;CITY;ECO_MARK_LABEL\n"
               "U_1;КОММ_ОРГ;46.71.2;Торговля оптовая моторным топливом;CLIENT;1.0;1.0;КИТАЙ, ГОНКОНГ;60403060000.0;group_1_sb;Москва;г. Москва;Оптимизация\n"
               "U_2;КОММ_ОРГ;41.20;Строительство зданий;PROSPECT;0.0;0.0;;1500000.0;group_2_sb;Москва;г. Москва;\n"
               "U_3;КОММ_ОРГ;41.20;Строительство зданий;CLIENT;0.0;0.0;;2000000.0;group_2_sb;Москва;г. Москва;\n").encode()
        self.assertEqual(datasets.import_companies(db, raw)["imported"], 3)
        p1, p2, p3 = (build_profile(db, c) for c in ("U_1", "U_2", "U_3"))
        self.assertIn("fuel", p1["sells"])                       # 46.71 -> sells fuel, by code
        self.assertIn("КИТАЙ", p1["fts_country"])
        self.assertFalse(any(f["id"] == "group" for f in p1["features"]), "a one-company GROUP_ID is not a group")
        self.assertTrue(any(f["id"] == "group" for f in p3["features"]))
        self.assertTrue(any("не является действующим клиентом" in u["text"] for u in p2["unknown"]))
        self.assertEqual(p2["sens"]["rate"]["value"], p2["sens"]["rate"]["parts"][0]["delta"], "a prospect's missing loans must not lower rate sensitivity")


class ContestFolder(unittest.TestCase):
    def test_gz_files_are_detected_and_loaded(self):
        import gzip, os, tempfile
        from pathlib import Path
        from radar.config import settings
        from radar.seed import loader
        d = Path(tempfile.mkdtemp())
        (d / "contest").mkdir()
        files = {"u.csv.gz": "SYNTHETIC_U;MAINOKVED_CODE;MAINOKVED_NAME;REVENUE_COMPANY;CL_TYPE\nU_1;46.90;Торговля;20000000000;CLIENT\nU_2;41.20;Строительство;1000000;PROSPECT\n",
                 "p.csv.gz": "BENEFICIARY;PAYER;PAY_AMT;PAY_CNT\nU_2;U_1;1000.0;3\nU_9;U_1;3000.0;1\n",
                 "f.csv.gz": "SYNTHETIC_F;CITY_NAME;RC_NAME;SYNTHETIC_U\nF_1;Москва;МОСКОВСКИЙ;U_1\nF_1;Москва;МОСКОВСКИЙ;U_2\n"}
        for n, t in files.items():
            with gzip.open(d / "contest" / n, "wb") as f:
                f.write(t.encode())
        old = settings.data_dir
        settings.data_dir = d
        try:
            self.assertEqual(set(loader.contest_files()), {"companies", "payments", "persons"})
            db = fresh_db()
            loader.bootstrap(db, dataset="contest")
        finally:
            settings.data_dir = old
        from radar.graph import company_graph
        self.assertEqual(db.one("SELECT COUNT(*) n FROM companies")["n"], 2)
        g = company_graph(db, "U_1")
        self.assertEqual(g["recipients"]["n"], 2)
        self.assertEqual([a["id"] for a in g["affiliated"]], ["U_2"], "a shared person links the two organisations")
        self.assertGreaterEqual(db.one("SELECT COUNT(*) n FROM users")["n"], 1)

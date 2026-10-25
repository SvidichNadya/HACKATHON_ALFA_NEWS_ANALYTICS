"""Idempotent bootstrap: dataset, news, bank analytics, accounts."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from ..config import settings
from ..db import dumps
from ..ingest import datasets, files, store
from . import corpus, generate

ACCOUNTS = [
    ("metal.ceo", "Андрей Волков", "ceo", ["U-DEMO-0001"]), ("metal.cfo", "Мария Левина", "cfo", ["U-DEMO-0001"]),
    ("metal.treasurer", "Игорь Сорокин", "treasurer", ["U-DEMO-0001"]), ("trade.cfo", "Елена Громова", "cfo", ["U-DEMO-0002"]),
    ("trade.ceo", "Павел Дмитриев", "ceo", ["U-DEMO-0002"]), ("agro.ceo", "Олег Назаров", "ceo", ["U-DEMO-0003"]),
    ("build.cfo", "Анна Крылова", "cfo", ["U-DEMO-0004"]), ("build.accountant", "Светлана Орлова", "chief_accountant", ["U-DEMO-0004"]),
    ("digital.ceo", "Дарья Ким", "ceo", ["U-DEMO-0005"]), ("mining.owner", "Виктор Лазарев", "owner", ["U-DEMO-0006", "U-DEMO-0001"]),
]


ROLE_CYCLE = [("ceo", "Генеральный директор"), ("cfo", "Финансовый директор")]
PEOPLE = ["Андрей Волков", "Мария Левина", "Игорь Сорокин", "Елена Громова", "Павел Дмитриев", "Ольга Назарова", "Сергей Крылов", "Анна Орлова", "Дмитрий Лазарев", "Наталья Ким"]


def accounts_for(db):
    synthetic = db.one("SELECT COUNT(*) n FROM companies WHERE id LIKE 'U-DEMO-%'")["n"] > 0
    if synthetic:
        return ACCOUNTS
    out = []
    for i, cid in enumerate(real_accounts(db), 1):
        for j, (role, _) in enumerate(ROLE_CYCLE):
            out.append((f"co{i}.{role}", PEOPLE[(i * 2 + j) % len(PEOPLE)], role, [cid]))
    return out


def ensure_accounts(db):
    if db.one("SELECT COUNT(*) n FROM users")["n"]:
        return
    pw = generate_password_hash(settings.demo_password)
    for login, name, role, comps in accounts_for(db):
        uid = db.x("INSERT INTO users(login,name,role,pw_hash) VALUES (?,?,?,?)", (login, name, role, pw))
        for c in comps:
            db.x("INSERT OR IGNORE INTO user_company VALUES (?,?)", (uid, c))
    uid = db.x("INSERT INTO users(login,name,role,pw_hash,is_admin) VALUES (?,?,?,?,1)", ("jury", "Эксперт жюри", "ceo", pw))
    for r in db.q("SELECT id FROM companies"):
        db.x("INSERT OR IGNORE INTO user_company VALUES (?,?)", (uid, r["id"]))


def contest_files():
    """Real export dropped into data/contest/ (CSV or CSV.GZ). Type of each file is detected from its headers."""
    folder = settings.data_dir / "contest"
    found = {}
    if folder.exists():
        for f in sorted(folder.iterdir()):
            if f.name.endswith((".csv", ".csv.gz")):
                with open(f, "rb") as fh:
                    head = fh.read(4096)
                if head[:2] == b"\x1f\x8b":
                    import gzip
                    head = gzip.open(f, "rb").read(4096)
                kind = datasets.detect_kind(head + b"\n")
                if kind:
                    found[kind] = f
    return found if {"companies", "payments"} <= set(found) else {}


def seed_dataset(db, dataset=None):
    dataset = dataset or settings.dataset
    if db.one("SELECT COUNT(*) n FROM companies")["n"]:
        return None
    files = contest_files() if dataset in ("auto", "contest") else {}
    if dataset == "contest" and not files:
        raise RuntimeError("RADAR_DATASET=contest, но в data/contest/ нет файлов компаний и платежей")
    if files:
        out = {"source": "contest"}
        out["companies"] = datasets.import_companies(db, files["companies"].read_bytes(), files["companies"].name)
        if "persons" in files:
            out["persons"] = datasets.import_persons(db, files["persons"].read_bytes(), files["persons"].name)
        out["payments"] = datasets.import_payments(db, files["payments"].read_bytes(), files["payments"].name)
        return out
    c, p, pr, _ = generate.build_files()
    datasets.import_companies(db, c, "synthetic", synthetic=True)
    datasets.import_persons(db, p, "synthetic")
    datasets.import_payments(db, pr, "synthetic")
    return {"source": "synthetic"}


def real_accounts(db, n=8):
    """Showcase accounts for a real export: the largest companies with a visible payment network, diverse by industry and product set."""
    rows = db.q("SELECT c.id, c.revenue, c.okved_code, c.p_loa, c.p_dep, c.p_lea, c.fts_flag, c.p_fac, c.p_gar, c.client_type, "
                "(SELECT COUNT(*) FROM payments p WHERE p.payer=c.id OR p.beneficiary=c.id) links FROM companies c WHERE c.revenue>=15e9 ORDER BY c.revenue DESC LIMIT 200")
    from ..knowledge.sectors import sector_by_okved
    chosen, seen_sec, seen_sig = [], set(), set()
    for r in rows:
        if r["links"] < 20 or r["client_type"] != "CLIENT":
            continue
        sec = sector_by_okved(r["okved_code"])
        sig = (r["p_loa"], r["p_dep"], r["fts_flag"], r["p_gar"])
        if sec in seen_sec and sig in seen_sig:
            continue
        seen_sec.add(sec); seen_sig.add(sig); chosen.append(r["id"])
        if len(chosen) >= n:
            break
    return chosen


def seed_corpus(db, now=None):
    now = now or datetime.now(timezone.utc)
    if db.one("SELECT COUNT(*) n FROM docs")["n"]:
        return 0
    n = 0
    for title, days, text in corpus.BANK:
        pub = (now - timedelta(days=days)).isoformat()
        title_, blocks = title, [("раздел «" + (b.split("\n", 1)[0].lstrip("# ") if b.startswith("#") else "документ") + "»", b.split("\n", 1)[1] if b.startswith("#") else b)
                                 for b in text.strip().split("\n\n") if b.strip()]
        # headings are separated from paragraphs by a blank line in the source; rebuild blocks by section
        blocks, section = [], "документ"
        for part in text.strip().split("\n"):
            if part.startswith("#"):
                section = part.lstrip("# ").strip()
            elif part.strip():
                blocks.append((f"раздел «{section}»", part.strip()))
        store.add_document(db, "bank_analysis", title_, " ".join(b[1] for b in blocks), "Альфа-Банк, ЦМИ (учебный образец)", published_at=pub, is_synthetic=True,
                           meta={"note": "illustrative"}, blocks=blocks)
        n += 1
    for key, src, days, title, body, gold in corpus.NEWS:
        pub = (now - timedelta(days=days, hours=hash(key) % 7)).isoformat()
        store.add_document(db, "news", title, body, src, url=f"https://demo.invalid/news/{key}", published_at=pub, is_synthetic=True, meta={"demo_key": key, "gold": gold})
        n += 1
    return n


def seed_bank_folder(db):
    """Original PDFs/DOCX/MD dropped into data/bank_analytics are imported as real bank materials."""
    folder = settings.data_dir / "bank_analytics"
    done = 0
    if not folder.exists():
        return 0
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in (".pdf", ".docx", ".md", ".txt"):
            continue
        title, blocks = files.read_blocks(f.name, f.read_bytes())
        body = "\n\n".join(t for _, t in blocks)
        if len(body) < 60:
            continue
        try:
            store.add_document(db, "bank_analysis", f.stem.replace("_", " "), body, "Альфа-Банк, Центр макроэкономических исследований", published_at=files.guess_date(body[:3000]),
                               meta={"file": f.name}, blocks=blocks)
            done += 1
        except ValueError:
            continue
    return done


def bootstrap(db, dataset=None):
    db.migrate()
    info = seed_dataset(db, dataset)
    if info:
        print("dataset:", info)
    seed_corpus(db)
    seed_bank_folder(db)
    ensure_accounts(db)

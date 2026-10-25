"""Command line: init the database, seed demo data, run evaluation, export sample CSVs."""
import argparse
import json
import sys
from pathlib import Path

from .config import settings
from .db import DB


def main(argv=None):
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create schema, load synthetic dataset, demo news, bank materials and accounts (idempotent)")
    sub.add_parser("accounts", help="list demo accounts and the companies they see")
    sub.add_parser("eval", help="print offline ranking quality")
    ex = sub.add_parser("export-samples", help="write the synthetic CSVs in the contest schema")
    ex.add_argument("--out", default=str(settings.data_dir / "samples"))
    imp = sub.add_parser("import-csv", help="import companies / persons / payments CSV (type is detected from headers)")
    imp.add_argument("path")
    docs = sub.add_parser("import-docs", help="import PDF/DOCX/MD/TXT bank analytics from a folder")
    docs.add_argument("folder", nargs="?", default=str(settings.data_dir / "bank_analytics"))
    a = ap.parse_args(argv)
    db = DB(settings.db_path)
    db.migrate()
    if a.cmd == "init":
        from .seed import loader
        loader.bootstrap(db)
        print(json.dumps(db.one("SELECT (SELECT COUNT(*) FROM companies) companies, (SELECT COUNT(*) FROM payments) payments, (SELECT COUNT(*) FROM docs) docs, (SELECT COUNT(*) FROM events) events, (SELECT COUNT(*) FROM users) users"), ensure_ascii=False))
    elif a.cmd == "accounts":
        for r in db.q("SELECT u.login, u.role, c.id, c.display_name, c.revenue FROM users u JOIN user_company uc ON uc.user_id=u.id JOIN companies c ON c.id=uc.company_id ORDER BY u.id"):
            print(f"{r['login']:<18}{r['role']:<10}{r['id']:<12}{(r['revenue'] or 0) / 1e9:>7.1f} млрд  {r['display_name']}")
        print("jury              (все компании)")
    elif a.cmd == "eval":
        from . import evaluation
        print(json.dumps(evaluation.run(db), ensure_ascii=False, indent=2))
    elif a.cmd == "export-samples":
        from .seed import generate
        c, p, pr, _ = generate.build_files()
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "df_Uid_data_hack.csv").write_bytes(c)
        (out / "df_Fid_link_hack.csv").write_bytes(p)
        (out / "df_Payments_hack.csv").write_bytes(pr)
        print("written to", out)
    elif a.cmd == "import-csv":
        from .ingest import datasets
        raw = Path(a.path).read_bytes()
        kind = datasets.detect_kind(raw)
        fn = {"companies": datasets.import_companies, "persons": datasets.import_persons, "payments": datasets.import_payments}.get(kind)
        if not fn:
            sys.exit("Не удалось определить тип CSV по заголовкам")
        print(kind, fn(db, raw, Path(a.path).name))
    elif a.cmd == "import-docs":
        from .seed import loader
        settings.data_dir = Path(a.folder).parent
        print("imported:", loader.seed_bank_folder(db))


if __name__ == "__main__":
    main()

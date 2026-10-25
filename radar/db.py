"""SQLite storage. WAL mode, one connection per thread, explicit migrations."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = [
    # v1
    """
    CREATE TABLE companies (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        org_type TEXT, okfs TEXT, age_band TEXT, stage TEXT,
        okved_code TEXT, okved_name TEXT,
        workers_fns TEXT, workers_spark TEXT,
        client_type TEXT, key_owner_flag INTEGER DEFAULT 0,
        p_rko INTEGER DEFAULT 0, p_gar INTEGER DEFAULT 0, p_loa INTEGER DEFAULT 0,
        p_lea INTEGER DEFAULT 0, p_dep INTEGER DEFAULT 0, p_zpp INTEGER DEFAULT 0,
        p_fac INTEGER DEFAULT 0,
        fts_flag INTEGER DEFAULT 0, fts_country TEXT,
        revenue REAL, group_id TEXT, city TEXT, region TEXT,
        is_synthetic INTEGER DEFAULT 1,
        source_file TEXT, imported_at TEXT
    );
    CREATE INDEX ix_companies_group ON companies(group_id);
    CREATE INDEX ix_companies_okved ON companies(okved_code);

    CREATE TABLE persons (
        id TEXT NOT NULL, company_id TEXT NOT NULL, city TEXT, region TEXT,
        PRIMARY KEY (id, company_id)
    );
    CREATE INDEX ix_persons_company ON persons(company_id);

    CREATE TABLE payments (
        payer TEXT NOT NULL, beneficiary TEXT NOT NULL,
        amount REAL, cnt INTEGER, source_file TEXT,
        PRIMARY KEY (payer, beneficiary)
    );
    CREATE INDEX ix_pay_ben ON payments(beneficiary);

    CREATE TABLE docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,              -- news | bank_analysis
        title TEXT NOT NULL,
        source_name TEXT NOT NULL,
        url TEXT, author TEXT,
        published_at TEXT, event_at TEXT, fetched_at TEXT NOT NULL,
        body TEXT NOT NULL,
        content_hash TEXT NOT NULL UNIQUE,
        simhash TEXT,
        is_synthetic INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ok',
        meta TEXT DEFAULT '{}'
    );
    CREATE INDEX ix_docs_kind_pub ON docs(kind, published_at);

    CREATE TABLE chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
        ord INTEGER NOT NULL, locator TEXT, text TEXT NOT NULL, factors TEXT DEFAULT '[]'
    );
    CREATE INDEX ix_chunks_doc ON chunks(doc_id);

    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, summary TEXT,
        categories TEXT DEFAULT '[]', signals TEXT DEFAULT '[]',
        entities TEXT DEFAULT '{}', facts TEXT DEFAULT '[]',
        sectors TEXT DEFAULT '[]', regions TEXT DEFAULT '[]', countries TEXT DEFAULT '[]',
        commodities TEXT DEFAULT '[]',
        first_seen TEXT, last_seen TEXT, event_at TEXT,
        doc_ids TEXT DEFAULT '[]', source_count INTEGER DEFAULT 1,
        authority REAL DEFAULT 0.5, contradictions TEXT DEFAULT '[]',
        is_synthetic INTEGER DEFAULT 0, version INTEGER DEFAULT 1, updated_at TEXT
    );
    CREATE INDEX ix_events_last ON events(last_seen);

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL,
        pw_hash TEXT NOT NULL, is_admin INTEGER DEFAULT 0
    );
    CREATE TABLE user_company (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, company_id)
    );

    CREATE TABLE insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        user_id INTEGER, role TEXT,
        kind TEXT NOT NULL,              -- event | cascade | adhoc
        event_ids TEXT DEFAULT '[]',
        title TEXT, priority TEXT, confidence TEXT,
        importance REAL, confidence_score REAL,
        payload TEXT NOT NULL,
        status TEXT DEFAULT 'active', version INTEGER DEFAULT 1,
        run_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX ix_insights_company ON insights(company_id, status, importance);

    CREATE TABLE agent_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id TEXT NOT NULL, user_id INTEGER, insight_id INTEGER,
        kind TEXT, status TEXT, plan TEXT DEFAULT '[]', trace TEXT DEFAULT '[]',
        mode TEXT, model TEXT,
        tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, llm_calls INTEGER DEFAULT 0,
        steps INTEGER DEFAULT 0, replans INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0,
        error TEXT, created_at TEXT NOT NULL
    );
    CREATE INDEX ix_runs_company ON agent_runs(company_id, created_at);

    CREATE TABLE audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, user_id INTEGER, run_id INTEGER,
        actor TEXT, action TEXT, target TEXT, allowed INTEGER DEFAULT 1, detail TEXT
    );
    CREATE INDEX ix_audit_ts ON audit(ts);

    CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        insight_id INTEGER NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
        user_id INTEGER, kind TEXT NOT NULL, comment TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        insight_id INTEGER NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
        user_id INTEGER, role TEXT NOT NULL, content TEXT NOT NULL,
        citations TEXT DEFAULT '[]', created_at TEXT NOT NULL
    );
    CREATE TABLE seen_state (
        user_id INTEGER NOT NULL, company_id TEXT NOT NULL, last_seen TEXT NOT NULL,
        PRIMARY KEY (user_id, company_id)
    );
    CREATE TABLE token_ledger (
        day TEXT PRIMARY KEY, tokens INTEGER DEFAULT 0
    );
    """,
    # v2: shared-person lookups for affiliation signals
    "CREATE INDEX IF NOT EXISTS ix_persons_id ON persons(id);",
]

_local = threading.local()


class DB:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def conn(self):
        key = "c_" + self.path
        c = getattr(_local, key, None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            setattr(_local, key, c)
        return c

    def migrate(self):
        c = self.conn()
        ver = c.execute("PRAGMA user_version").fetchone()[0]
        for i in range(ver, len(SCHEMA)):
            c.executescript("BEGIN;" + SCHEMA[i] + f"PRAGMA user_version={i + 1};COMMIT;")

    def q(self, sql, args=()):
        return [dict(r) for r in self.conn().execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.conn().execute(sql, args).fetchone()
        return dict(r) if r else None

    def x(self, sql, args=()):
        cur = self.conn().execute(sql, args)
        return cur.lastrowid

    def many(self, sql, rows):
        self.conn().executemany(sql, rows)

    @contextmanager
    def tx(self):
        c = self.conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def dumps(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def loads(s, default=None):
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default

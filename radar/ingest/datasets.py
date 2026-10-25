"""CSV importers for the contest schema (companies, linked persons, aggregated payments)."""
import csv
import gzip
import io
from datetime import datetime, timezone

from ..knowledge.sectors import normalize_okved, sector_by_okved

TRUE = {"1", "1.0", "true", "да", "yes", "y", "есть", "+"}


def _decode(raw, lenient=False):
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if lenient:
        return raw.decode("utf-8-sig", errors="ignore")
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Неизвестная кодировка файла")


def _reader(raw, lenient=False):
    text = _decode(raw, lenient)
    head = text.split("\n", 1)[0]
    delim = ";" if head.count(";") > head.count(",") else ("\t" if head.count("\t") > head.count(",") else ",")
    return csv.DictReader(io.StringIO(text), delimiter=delim)


def detect_kind(raw):
    r = _reader(raw, lenient=True)
    cols = set(r.fieldnames or [])
    if {"PAYER", "BENEFICIARY"} <= cols:
        return "payments"
    if "SYNTHETIC_U" in cols and ("MAINOKVED_CODE" in cols or "ORG_TYPE" in cols):
        return "companies"
    if "SYNTHETIC_F" in cols:
        return "persons"
    return None


def _v(row, *keys):
    for k in keys:
        x = row.get(k)
        if x is not None and str(x).strip() not in ("", "nan", "NaN", "None", "null"):
            return str(x).strip()
    return ""


def _flag(row, key):
    return int(_v(row, key).lower() in TRUE)


def _num(s):
    try:
        return float(s.replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def short_name(org_type, okved_name, cid):
    """The dataset is anonymised, so a company is identified by activity and id: 'Торговля оптовая зерном… · U_34911'."""
    base = (okved_name or "Компания").strip()
    if len(base) > 56:
        base = base[:56].rsplit(" ", 1)[0].rstrip(" ,") + "…"
    return f"{base} · {cid}"


def import_companies(db, raw, source="upload", synthetic=False, limit=500_000):
    n = dup = 0
    seen = set()
    now = datetime.now(timezone.utc).isoformat()
    batch = []
    for row in _reader(raw):
        cid = _v(row, "SYNTHETIC_U")
        if not cid:
            continue
        dup += cid in seen
        seen.add(cid)
        name = _v(row, "MAINOKVED_NAME")
        batch.append((
            cid, _v(row, "DISPLAY_NAME") or short_name(_v(row, "ORG_TYPE"), name, cid), _v(row, "ORG_TYPE"), _v(row, "OKFS_NAME"),
            _v(row, "COMPANY_AGE_YEARS_GRADATION"), _v(row, "ECO_MARK_LABEL"), normalize_okved(_v(row, "MAINOKVED_CODE")), name,
            _v(row, "AMOUNT_WORKERS_FNS_GRADATION"), _v(row, "AMOUNT_WORKERS_SPARK_GRADATION"), _v(row, "CL_TYPE"), _flag(row, "NEGATIVEMARK"),
            _flag(row, "CL_PRODUCT_RKO_MARK"), _flag(row, "CL_PRODUCT_GAR_MARK"), _flag(row, "CL_PRODUCT_LOA_MARK"), _flag(row, "CL_PRODUCT_LEA_MARK"),
            _flag(row, "CL_PRODUCT_DEP_MARK"), _flag(row, "CL_PRODUCT_ZPP_MARK"), _flag(row, "FACTORING_MARK"),
            _flag(row, "FTS_FLAG"), _v(row, "FTS_COUNTRY_NAME"), _num(_v(row, "REVENUE_COMPANY")), _v(row, "GROUP_ID"),
            _v(row, "CITY"), _v(row, "REGION"), int(synthetic), source, now))
        n += 1
        if n >= limit:
            break
    with db.tx():
        db.many("INSERT OR REPLACE INTO companies(id,display_name,org_type,okfs,age_band,stage,okved_code,okved_name,workers_fns,workers_spark,client_type,key_owner_flag,"
                "p_rko,p_gar,p_loa,p_lea,p_dep,p_zpp,p_fac,fts_flag,fts_country,revenue,group_id,city,region,is_synthetic,source_file,imported_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
    return {"imported": len(seen), "rows": n, "duplicate_ids": dup}


def import_persons(db, raw, source="upload", limit=2_000_000):
    rows = []
    known = {r["id"] for r in db.q("SELECT id FROM companies")}
    skipped = 0
    for row in _reader(raw):
        f, u = _v(row, "SYNTHETIC_F"), _v(row, "SYNTHETIC_U")
        if not f or u not in known:
            skipped += 1
            continue
        rows.append((f, u, _v(row, "CITY_NAME"), _v(row, "RC_NAME")))
        if len(rows) >= limit:
            break
    with db.tx():
        db.many("INSERT OR REPLACE INTO persons(id,company_id,city,region) VALUES (?,?,?,?)", rows)
    return {"imported": len(rows), "skipped": skipped}


def import_payments(db, raw, source="upload", limit=5_000_000):
    """Keeps a payment if at least one side is a known company. Counterparties outside the set stay as bare ids:
    they still count toward concentration, but their industry is unknown (the graph reports that coverage)."""
    known = {r["id"] for r in db.q("SELECT id FROM companies")}
    agg = {}
    skipped = 0
    for row in _reader(raw):
        p, b = _v(row, "PAYER"), _v(row, "BENEFICIARY")
        if not p or not b or (p not in known and b not in known):
            skipped += 1
            continue
        amt, cnt = _num(_v(row, "PAY_AMT")), _num(_v(row, "PAY_CNT"))
        cur = agg.get((p, b))
        if cur is None:
            agg[(p, b)] = [amt or 0.0, int(cnt or 0)]
        else:
            cur[0] += amt or 0.0
            cur[1] += int(cnt or 0)
        if len(agg) >= limit:
            break
    with db.tx():
        db.many("INSERT OR REPLACE INTO payments(payer,beneficiary,amount,cnt,source_file) VALUES (?,?,?,?,?)",
                [(p, b, a, c, source) for (p, b), (a, c) in agg.items()])
    return {"imported": len(agg), "skipped_both_unknown": skipped, "self_flows": sum(1 for (p, b) in agg if p == b)}


def sector_distribution(db):
    out = {}
    for r in db.q("SELECT okved_code, COUNT(*) n FROM companies GROUP BY okved_code"):
        k = sector_by_okved(r["okved_code"]) or "unknown"
        out[k] = out.get(k, 0) + r["n"]
    return out

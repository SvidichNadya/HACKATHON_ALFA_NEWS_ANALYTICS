"""Observed payment network. Payments carry no dates and no contract data, so the graph describes
concentration and sector mix only - never dynamics, criticality or contractual dependency.

Real exports contain counterparties that are not in the company table. They stay in the graph as bare ids so that
concentration is honest, but their industry is unknown; every side reports how much of the flow is classified."""
from collections import defaultdict

from .knowledge.sectors import SECTORS, sector_by_okved

EXTERNAL = "Контрагент вне набора данных"


def _hhi(shares):
    return round(sum(s * s for s in shares), 4)


def _side(rows, company_group, group_size):
    weights = [(r["amount"] or 0) or (r["cnt"] or 0) for r in rows]
    basis = "amount" if any((r["amount"] or 0) for r in rows) else ("count" if any(weights) else None)
    wsum = sum(weights) or 1
    items = []
    for r, w in zip(rows, weights):
        known = r["display_name"] is not None
        in_group = bool(known and group_size > 1 and company_group and r["group_id"] == company_group)
        items.append({
            "id": r["cid"], "name": r["display_name"] or f"{EXTERNAL} ({r['cid']})", "known": known, "okved": r["okved_code"], "okved_name": r["okved_name"],
            "sector": sector_by_okved(r["okved_code"]) if known and r["okved_code"] else None, "region": r["region"], "group_id": r["group_id"],
            "amount": r["amount"], "count": r["cnt"], "share": round(w / wsum, 4), "in_group": in_group,
        })
    items.sort(key=lambda x: -x["share"])
    sec = defaultdict(float)
    for it in items:
        if it["sector"]:
            sec[it["sector"]] += it["share"]
    coverage = round(sum(it["share"] for it in items if it["sector"]), 4)
    return {
        "n": len(items), "total_amount": sum(r["amount"] or 0 for r in rows) or None, "basis": basis,
        "top": items[:8], "top1_share": items[0]["share"] if items else None,
        "top3_share": round(sum(i["share"] for i in items[:3]), 4) if items else None,
        "hhi": _hhi([i["share"] for i in items]) if items else None,
        "sectors": {k: round(v, 4) for k, v in sorted(sec.items(), key=lambda kv: -kv[1])},
        "classified_share": coverage,
        "intra_group_share": round(sum(i["share"] for i in items if i["in_group"]), 4) if items else 0.0,
        "items": items,
    }


def company_graph(db, cid):
    me = db.one("SELECT group_id, revenue FROM companies WHERE id=?", (cid,)) or {}
    group = me.get("group_id") or ""
    gsize = db.one("SELECT COUNT(*) n FROM companies WHERE group_id=?", (group,))["n"] if group else 0
    cols = "p.{k} AS cid, c.display_name, c.okved_code, c.okved_name, c.region, c.group_id, p.amount, p.cnt"
    pays_to = db.q(f"SELECT {cols.format(k='beneficiary')} FROM payments p LEFT JOIN companies c ON c.id=p.beneficiary WHERE p.payer=? AND p.beneficiary<>p.payer", (cid,))
    pays_from = db.q(f"SELECT {cols.format(k='payer')} FROM payments p LEFT JOIN companies c ON c.id=p.payer WHERE p.beneficiary=? AND p.beneficiary<>p.payer", (cid,))
    own = db.one("SELECT amount, cnt FROM payments WHERE payer=? AND beneficiary=?", (cid, cid))
    recipients = _side(pays_to, group, gsize)      # company pays them: cost side, likely suppliers
    payers = _side(pays_from, group, gsize)        # they pay company: revenue side, likely customers
    members = []
    if gsize > 1:
        members = db.q("SELECT id, display_name, okved_name, revenue FROM companies WHERE group_id=? AND id<>? ORDER BY revenue DESC LIMIT 12", (group, cid))
    affiliated = db.q("SELECT c.id, c.display_name, c.okved_name, c.revenue, COUNT(DISTINCT a.id) shared FROM persons a JOIN persons b ON b.id=a.id AND b.company_id<>a.company_id "
                      "JOIN companies c ON c.id=b.company_id WHERE a.company_id=? GROUP BY c.id ORDER BY shared DESC, c.revenue DESC LIMIT 12", (cid,))
    return {
        "company_id": cid, "group_id": group if gsize > 1 else None, "group_size": gsize, "group_members": members,
        "affiliated": affiliated, "recipients": recipients, "payers": payers,
        "internal_turnover": {"amount": own["amount"], "count": own["cnt"], "share_of_revenue": (own["amount"] / me["revenue"]) if own and me.get("revenue") else None} if own else None,
        "available": bool(pays_to or pays_from),
        "caveat": "Платёжные данные агрегированы без дат и договоров: они показывают концентрацию и отраслевую структуру, "
                  "но не подтверждают критичность поставщика, срок оплаты или динамику. Часть контрагентов находится вне набора данных, их отрасль неизвестна.",
    }


def network_view(db, cid, limit=10):
    """Small ego network for visualisation: company, top counterparties both ways, group members."""
    g = company_graph(db, cid)
    nodes = {cid: {"id": cid, "role": "self"}}
    edges = []
    for side, role, rev in ((g["recipients"], "recipient", False), (g["payers"], "payer", True)):
        for it in side["items"][:limit]:
            nodes.setdefault(it["id"], {"id": it["id"], "role": role, "name": it["name"], "sector": it["sector"], "okved_name": it["okved_name"], "known": it["known"], "in_group": it["in_group"]})
            edges.append({"from": it["id"] if rev else cid, "to": cid if rev else it["id"], "share": it["share"], "amount": it["amount"]})
    for m in g["group_members"][:5]:
        nodes.setdefault(m["id"], {"id": m["id"], "role": "group", "name": m["display_name"], "okved_name": m["okved_name"], "in_group": True, "known": True})
    me = db.one("SELECT display_name, okved_name FROM companies WHERE id=?", (cid,))
    nodes[cid].update({"name": me["display_name"], "okved_name": me["okved_name"]})
    return {"nodes": list(nodes.values()), "edges": edges, "basis": g["recipients"]["basis"] or g["payers"]["basis"],
            "coverage": {"recipients": g["recipients"]["classified_share"], "payers": g["payers"]["classified_share"]},
            "affiliated": [{"id": a["id"], "name": a["display_name"], "shared": a["shared"]} for a in g["affiliated"][:6]], "group_size": g["group_size"]}


def sector_label(key):
    return SECTORS.get(key, {}).get("label", key or "—")

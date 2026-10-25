"""Company profile: observed attributes, derived exposure per factor, provenance for each number."""
from .config import settings
from .graph import company_graph
from .knowledge.sectors import FACTORS, SECTORS, sector_by_okved, sells_for, SELLS_BY_CODE

PRODUCT_LABELS = {
    "p_rko": "расчётно-кассовое обслуживание", "p_loa": "кредитные продукты", "p_lea": "лизинг", "p_gar": "банковские гарантии",
    "p_dep": "депозиты", "p_zpp": "зарплатный проект", "p_fac": "факторинг",
}
PRODUCT_COLUMNS = {
    "p_rko": "CL_PRODUCT_RKO_MARK", "p_loa": "CL_PRODUCT_LOA_MARK", "p_lea": "CL_PRODUCT_LEA_MARK", "p_gar": "CL_PRODUCT_GAR_MARK",
    "p_dep": "CL_PRODUCT_DEP_MARK", "p_zpp": "CL_PRODUCT_ZPP_MARK", "p_fac": "FACTORING_MARK",
}
SRC = "df_Uid_data_hack.csv"
CLIENT_LABEL = {"CLIENT": "Действующий клиент банка", "PROSPECT": "Потенциальный клиент", "CLOSE_CLIENT": "Бывший клиент банка"}
LARGE_WORKERS = {"Более 251", "более 251", "101-250", "5000 и более", "от 1000 до 5000"}
STATE_OWNED = ("ФЕДЕРАЛЬНАЯ", "СУБЪЕКТОВ", "ФЕДЕРАЛЬНОЙ", "МУНИЦИПАЛЬН")
FOREIGN_OWNED = ("ИНОСТРАН",)


def revenue_band(v):
    if v is None:
        return None
    b = v / 1e9
    if b < 1:
        return "менее 1 млрд ₽"
    if b < 15:
        return f"{b:.1f} млрд ₽"
    return f"{b:,.0f} млрд ₽".replace(",", "\u00a0")


def _feat(fid, label, value, kind, source):
    return {"id": fid, "label": label, "value": value, "kind": kind, "source": source}


def build_profile(db, cid, with_graph=True):
    row = db.one("SELECT * FROM companies WHERE id=?", (cid,))
    if not row:
        return None
    sector = sector_by_okved(row["okved_code"])
    sec = SECTORS.get(sector) if sector else None
    feats = []
    unknown = []
    if row["okved_code"]:
        feats.append(_feat("okved", "Основной вид деятельности", f"{row['okved_code']} · {row['okved_name'] or ''}".strip(" ·"), "observed", f"{SRC}: MAINOKVED_CODE/NAME"))
    else:
        unknown.append({"id": "okved", "text": "Не указан основной вид деятельности: отраслевая чувствительность не рассчитана."})
    if row["revenue"]:
        feats.append(_feat("revenue", "Годовая выручка", revenue_band(row["revenue"]), "observed", f"{SRC}: REVENUE_COMPANY"))
    else:
        unknown.append({"id": "revenue", "text": "Нет данных о выручке: масштаб влияния в рублях оценить нельзя."})
    if row["region"] or row["city"]:
        place = [x for x in (row["region"], row["city"]) if x]
        if len(place) == 2 and place[0].lower() in place[1].lower():
            place = [place[1]]
        feats.append(_feat("region", "Регион присутствия", ", ".join(place), "observed", f"{SRC}: REGION/CITY"))
    gsize = db.one("SELECT COUNT(*) n FROM companies WHERE group_id=?", (row["group_id"],))["n"] if row["group_id"] else 0
    if gsize > 1:
        feats.append(_feat("group", "Группа компаний", f"{gsize} организаций в наборе данных", "observed", f"{SRC}: GROUP_ID"))
    if row["client_type"]:
        feats.append(_feat("client", "Статус в банке", CLIENT_LABEL.get(row["client_type"], row["client_type"]), "observed", f"{SRC}: CL_TYPE"))
    prospect = row["client_type"] in ("PROSPECT", "CLOSE_CLIENT")
    for col, label in PRODUCT_LABELS.items():
        if row[col]:
            feats.append(_feat(col, label.capitalize(), "есть", "observed", f"{SRC}: {PRODUCT_COLUMNS[col]}"))
    if row["fts_flag"]:
        feats.append(_feat("fts", "Внешнеторговая деятельность", row["fts_country"] or "страна не указана", "observed", f"{SRC}: FTS_FLAG/FTS_COUNTRY_NAME"))
    elif row["fts_country"]:
        feats.append(_feat("fts", "Страна в данных ФТС", row["fts_country"], "observed", f"{SRC}: FTS_COUNTRY_NAME"))
    workers = row["workers_fns"] or row["workers_spark"]
    if workers:
        feats.append(_feat("workers", "Численность работников", workers, "observed", f"{SRC}: AMOUNT_WORKERS_*_GRADATION"))
    if row["stage"]:
        feats.append(_feat("stage", "Стадия развития бизнеса", row["stage"], "observed", f"{SRC}: ECO_MARK_LABEL"))

    sens = {f: {"value": 0.0, "parts": []} for f in FACTORS}

    def add(f, delta, label, kind, feature=None):
        sens[f]["parts"].append({"label": label, "delta": round(delta, 3), "kind": kind, "feature": feature})
        sens[f]["value"] = max(0.0, min(1.0, sens[f]["value"] + delta))

    if sec:
        for f, v in sec["base"].items():
            add(f, v, f"Типичная чувствительность отрасли «{sec['label']}»", "derived", "okved")
    debt = 0.0
    if row["p_loa"]:
        debt += 0.5
    if row["p_lea"]:
        debt += 0.25
    if row["p_fac"]:
        debt += 0.2
    if row["p_gar"]:
        debt += 0.1
    debt = min(1.0, debt)
    if debt:
        for col, d, note in (("p_loa", .3, "кредитный продукт"), ("p_lea", .15, "лизинг"), ("p_fac", .1, "факторинг"), ("p_gar", .05, "гарантии")):
            if row[col]:
                add("rate", d, f"Подтверждён продукт: {note}", "observed", col)
                add("liquidity", d * .6, f"Подтверждён продукт: {note}", "observed", col)
        unknown.append({"id": "debt_terms", "text": "Условия финансирования (сумма, ставка, график пересмотра, ковенанты) в данных отсутствуют: процентную нагрузку в рублях рассчитать нельзя."})
    elif sec and prospect:
        unknown.append({"id": "debt", "text": "Компания не является действующим клиентом: продукты банка не подключены, поэтому долг, депозиты и расчётные потоки вне банка в данных не видны."})
    elif sec:
        add("rate", -sec["base"]["rate"] * 0.4, "В банке нет кредитных продуктов; внебанковский долг неизвестен", "derived", "p_loa")
        unknown.append({"id": "debt", "text": "Нет подтверждённых кредитных продуктов в банке; долг вне банка и облигации в данных не видны."})
    if row["fts_flag"]:
        add("fx", .3, "Подтверждена внешнеторговая деятельность (ФТС)", "observed", "fts")
        add("foreign_trade", .3, "Подтверждена внешнеторговая деятельность (ФТС)", "observed", "fts")
        add("logistics", .1, "Внешнеторговые поставки", "observed", "fts")
    elif sec:
        add("fx", -sec["base"]["fx"] * .3, "Внешнеторговая деятельность в данных не подтверждена", "derived", "fts")
        add("foreign_trade", -sec["base"]["foreign_trade"] * .4, "Внешнеторговая деятельность в данных не подтверждена", "derived", "fts")
    own = (row["okfs"] or "").upper()
    if any(k in own for k in STATE_OWNED):
        add("regulation", .1, "Государственная форма собственности: чувствительность к регулированию и бюджетным решениям", "observed", "okfs")
        feats.append(_feat("okfs", "Форма собственности", row["okfs"].capitalize(), "observed", f"{SRC}: OKFS_NAME"))
    elif any(k in own for k in FOREIGN_OWNED):
        add("foreign_trade", .1, "Иностранное участие в собственности", "observed", "okfs")
        add("fx", .05, "Иностранное участие в собственности", "observed", "okfs")
        feats.append(_feat("okfs", "Форма собственности", row["okfs"].capitalize(), "observed", f"{SRC}: OKFS_NAME"))
    if (row["workers_fns"] or "") in LARGE_WORKERS:
        add("labor", .08, f"Численность работников: {row['workers_fns']}", "observed", "workers")
    if row["p_zpp"]:
        add("labor", .1, "Подключён зарплатный проект: значимый штат", "observed", "p_zpp")
    if row["p_gar"]:
        add("regulation", .05, "Банковские гарантии часто связаны с госзакупками и подрядами", "derived", "p_gar")
    unknown.append({"id": "fx_direction", "text": "Направление внешнеторговых операций (экспорт/импорт) и валюта контрактов не указаны."} if row["fts_flag"] else
                   {"id": "fts", "text": "Нет сведений о внешнеторговых операциях."})

    graph = company_graph(db, cid) if with_graph else None
    if graph and graph["available"]:
        feats.append(_feat("graph", "Наблюдаемые платёжные связи", f"получателей: {graph['recipients']['n']}, плательщиков: {graph['payers']['n']}", "observed", "payments"))
        cov = min(graph["recipients"]["classified_share"] if graph["recipients"]["n"] else 1, graph["payers"]["classified_share"] if graph["payers"]["n"] else 1)
        if cov < .8:
            unknown.append({"id": "graph_cov", "text": f"Отрасль известна лишь для части платёжных потоков (получатели {graph['recipients']['classified_share']:.0%}, плательщики {graph['payers']['classified_share']:.0%}): остальные контрагенты вне набора данных."})
        if graph["affiliated"]:
            feats.append(_feat("affiliated", "Связи через общих физических лиц", f"{len(graph['affiliated'])} возможно аффилированных организаций", "observed", "df_Fid_Uid_link_hack.csv"))
        r1, p1 = graph["recipients"]["top1_share"], graph["payers"]["top1_share"]
        if r1 and r1 >= .4:
            add("logistics", .1, f"Концентрация платежей: крупнейший получатель {r1:.0%}", "observed", "graph")
            add("input_costs", .05, f"Концентрация платежей: крупнейший получатель {r1:.0%}", "observed", "graph")
    else:
        unknown.append({"id": "graph", "text": "Платёжные связи компании не найдены в загруженных данных."})

    # Commodity roles: sector prior plus what the payment graph reveals about suppliers
    buys, sells = {}, {}
    if sec:
        for c in sec["buys"]:
            buys[c] = {"weight": .5, "kind": "derived", "why": f"типичные закупки отрасли «{sec['label']}»"}
        for c in sells_for(row["okved_code"], sector):
            by_code = (row["okved_code"] or "")[:4] in SELLS_BY_CODE or (row["okved_code"] or "") in SELLS_BY_CODE
            sells[c] = {"weight": .9 if by_code else .6, "kind": "mapped" if by_code else "derived",
                        "why": f"вид деятельности {row['okved_code']} подразумевает продажу этого товара" if by_code else f"типичная продукция отрасли «{sec['label']}»"}
    if graph and graph["recipients"]["n"]:
        agg = {}
        for it in graph["recipients"]["items"]:
            for c in sells_for(it["okved"], it["sector"]):
                a = agg.setdefault(c, {"share": 0.0, "sector": it["sector"]})
                a["share"] += it["share"]
        for c, a in agg.items():
            if a["share"] >= .2:
                prev = buys.get(c, {"weight": 0})
                buys[c] = {"weight": min(1, max(prev["weight"], .4 + a["share"])), "kind": "observed",
                           "why": f"{a['share']:.0%} платежей уходит контрагентам, которые по ОКВЭД производят этот товар"}

    return {
        "id": cid, "display_name": row["display_name"], "is_synthetic": bool(row["is_synthetic"]), "client_type": row["client_type"], "group_size": gsize,
        "sector": sector, "sector_label": sec["label"] if sec else None,
        "okved_code": row["okved_code"], "okved_name": row["okved_name"],
        "revenue": row["revenue"], "revenue_band": revenue_band(row["revenue"]),
        "region": row["region"], "city": row["city"], "group_id": row["group_id"],
        "fts_flag": bool(row["fts_flag"]), "fts_country": row["fts_country"],
        "org_type": row["org_type"], "ownership": row["okfs"], "age_band": row["age_band"], "stage": row["stage"],
        "workers": workers,
        "products": [PRODUCT_LABELS[c] for c in PRODUCT_LABELS if row[c]],
        "product_flags": {c: bool(row[c]) for c in PRODUCT_LABELS},
        "debt_exposure": round(debt, 2), "has_deposit": bool(row["p_dep"]),
        "export_lean": sec["export"] if sec else None,
        "features": feats, "sens": sens, "buys": buys, "sells": sells, "graph": graph, "unknown": unknown,
        "completeness": round(min(1.0, len([f for f in feats if f["kind"] == "observed"]) / 9), 2),
    }


def sens_value(p, factor):
    return p["sens"][factor]["value"]


def sens_kind_mix(p, factor):
    """Share of the positive contributions to a sensitivity that is observed rather than assumed from sector priors."""
    parts = [x for x in p["sens"][factor]["parts"] if x["delta"] > 0]
    tot = sum(x["delta"] for x in parts) or 1
    obs = sum(x["delta"] for x in parts if x["kind"] == "observed")
    return round(obs / tot, 3)


def feature_ids(p):
    return {f["id"] for f in p["features"]}


def public_profile(p):
    """Profile for the UI: drop heavy graph rows, keep what a user needs to see."""
    q = {k: v for k, v in p.items() if k not in {"graph", "sens"}}
    g = p.get("graph")
    if g:
        q["graph"] = {
            "available": g["available"], "group_id": g["group_id"], "group_members": g["group_members"][:8], "caveat": g["caveat"],
            "recipients": {k: v for k, v in g["recipients"].items() if k != "items"},
            "payers": {k: v for k, v in g["payers"].items() if k != "items"},
        }
    q["sens"] = {f: {"value": round(v["value"], 2), "parts": [x for x in v["parts"] if abs(x["delta"]) >= .04]} for f, v in p["sens"].items()}
    return q

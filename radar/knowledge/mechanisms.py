"""Business-impact mechanisms: (event signal) x (company exposure) -> scenario with conditions, unknowns, checks.

Every builder returns None unless the company profile or the event gives an actual reason; there is no generic
fallback template. Impact is 0..1 and drives ranking, the same object drives the interpretation text, so the
score and the explanation cannot drift apart.
"""
from .sectors import COMMODITIES, FACTOR_LABELS, SECTORS
from ..config import settings

W_OBS, W_GRAPH, W_MAPPED, W_DERIVED, W_ASSUMED = 1.0, 0.9, 0.8, 0.55, 0.3


def _ex(feature, text, kind):
    return {"feature": feature, "text": text, "kind": kind,
            "weight": {"observed": W_OBS, "graph": W_GRAPH, "mapped": W_MAPPED, "derived": W_DERIVED, "assumed": W_ASSUMED}[kind]}


def _fid(p, f):
    return next((x for x in p["features"] if x["id"] == f), None)


def _prod(p, col, label):
    return _ex(col, f"Подтверждено в данных банка: {label}.", "observed") if p["product_flags"].get(col) else None


def _sector_ex(p):
    return _ex("okved", f"Отрасль «{p['sector_label']}» (ОКВЭД {p['okved_code']}): типичная чувствительность к этому фактору.", "derived")


def _pct(v):
    return f"{v:g}".replace(".", ",") + "%"


def _mk(mid, factor, sig, kind, impact, nodes, headline, why, how, outcome, exposure, conditions, unknowns, checks, horizon, calc=None, product_hint=None):
    exposure = [e for e in exposure if e]
    w = [e["weight"] for e in exposure] or [W_ASSUMED]
    return {
        "id": mid, "factor": factor, "signal": {k: sig.get(k) for k in ("factor", "direction", "strength", "commodity", "level", "tone", "values", "quote")},
        "kind": kind, "impact": round(max(0.0, min(1.0, impact)), 3),
        "nodes": [{"node": n, "sign": s} for n, s in nodes],
        "headline": headline, "why": why, "how": how, "outcome": outcome, "exposure": exposure,
        "evidence_share": round(sum(w) / len(w), 3), "conditions": conditions, "unknowns": unknowns,
        "checks": checks, "horizon": horizon, "calc": calc, "product_hint": product_hint,
    }


def _rate_state(sig):
    v = sig.get("level_value") or (sig["values"][0] if sig.get("values") else None)
    return v, sig.get("tone")


# ---------------------------------------------------------------- rate
def m_rate_debt(p, sig, ev):
    if sig["factor"] != "rate" or p["debt_exposure"] < .3:
        return None
    v, tone = _rate_state(sig)
    elevated = sig.get("level") == "elevated" or (v is not None and v >= settings.rate_elevated_pct)
    d = sig["direction"]
    held_high = d == "flat" and (elevated or tone == "hawkish")
    if d == "flat" and not held_high:
        return None
    ex = [_prod(p, "p_loa", "кредитные продукты"), _prod(p, "p_lea", "лизинг"), _prod(p, "p_fac", "факторинг")]
    lvl = f" на уровне {_pct(v)}" if v else ""
    if d == "down":
        return _mk("rate_debt_down", "rate", sig, "opportunity", sig["strength"] * (.35 + .6 * p["debt_exposure"]), [("refi_window", -1), ("debt_cost", -1)],
                   "Открывается окно для пересмотра условий долга",
                   "У компании подтверждены кредитные продукты, поэтому изменение ключевой ставки напрямую влияет на стоимость обслуживания долга.",
                   f"Ключевая ставка снижается{lvl}. Кредиты с плавающей ставкой дешевеют автоматически, а для договоров с фиксированной ставкой появляется основание для переговоров о рефинансировании.",
                   "Сокращение процентных расходов и возможность вернуть часть инвестиционных проектов в план.",
                   ex, ["Часть долга привязана к ключевой ставке либо допускает досрочное погашение без значимых санкций", "Снижение подтверждается следующими решениями регулятора"],
                   ["Структура долга: доли фиксированной и плавающей ставки, даты пересмотра"],
                   ["Сопоставить действующие ставки с рыночными и оценить выгоду рефинансирования с учётом комиссий", "Определить проекты, отложенные из-за стоимости заёмных средств"],
                   "1–2 квартала", "debt_service", "refinancing")
    how = (f"Ключевая ставка остаётся{lvl}, а тон регулятора {'жёсткий' if tone == 'hawkish' else 'не смягчается'}: период дорогих денег продлевается. "
           "Плавающие ставки по действующим кредитам остаются высокими, а рефинансирование по более низкой ставке откладывается."
           if d == "flat" else
           f"Ключевая ставка повышается{lvl}. Стоимость кредитов с плавающей ставкой растёт, новые заимствования и рефинансирование дорожают.")
    return _mk("rate_debt_high", "rate", sig, "risk", sig["strength"] * (.35 + .65 * p["debt_exposure"]) * (1.0 if d == "up" else .92), [("debt_cost", +1)],
               "Стоимость обслуживания долга не снизится" if d == "flat" else "Растёт стоимость обслуживания долга",
               "В данных банка подтверждено: " + ", ".join(x for x in p["products"] if x in ("кредитные продукты", "лизинг", "факторинг")) + ". Поэтому процентная ставка напрямую влияет на расходы компании по долгу.",
               how, "Давление процентных платежей на денежный поток и ограничение программ, которые финансируются заёмными средствами.",
               ex, ["Часть долга с плавающей ставкой или с пересмотром в ближайшие 12 месяцев", "Нет процентного хеджирования или фиксации ставки"],
               ["Сумма, ставка, график и ковенанты по кредитам и лизингу", "Доля инвестиций, финансируемых заёмными средствами"],
               ["Свести портфель обязательств: фиксированная/плавающая ставка, даты пересмотра, ковенанты", "Пересчитать обслуживание долга на 2–3 квартала вперёд при текущей ставке (калькулятор ниже)", "Определить, какие инвестиции зависят от заёмных средств и можно ли их поэтапно сдвинуть"],
               "1–3 квартала", "debt_service", "refinancing" if d != "down" else None)


def m_rate_deposit(p, sig, ev):
    if sig["factor"] != "rate" or not p["has_deposit"]:
        return None
    d = sig["direction"]
    v, tone = _rate_state(sig)
    elevated = sig.get("level") == "elevated" or (v is not None and v >= settings.rate_elevated_pct)
    if d == "down":
        return _mk("rate_deposit_down", "rate", sig, "risk", sig["strength"] * .35, [("deposit_income", -1)],
                   "Доходность размещений свободных средств снижается",
                   "У компании есть депозитные продукты в банке, их доходность связана с ключевой ставкой.",
                   "Снижение ставки постепенно уменьшает доходность новых размещений, а продление действующих происходит по менее выгодным условиям.",
                   "Меньший процентный доход от свободной ликвидности.", [_prod(p, "p_dep", "депозиты")],
                   ["Значимый объём свободных средств на депозитах"], ["Объём и сроки размещений"],
                   ["Рассмотреть фиксацию доходности на более длинные сроки до очередного снижения ставки"], "1–2 квартала", None, "deposit")
    if d == "flat" and not (elevated or tone == "hawkish"):
        return None
    return _mk("rate_deposit_high", "rate", sig, "opportunity", sig["strength"] * .55, [("deposit_income", +1)],
               "Высокая ставка поддерживает доходность размещений",
               "У компании есть депозитные продукты в банке, поэтому высокая ключевая ставка работает в её пользу.",
               f"При ключевой ставке{' ' + _pct(v) if v else ''}, которая дольше остаётся высокой, свободные средства размещаются с повышенной доходностью. Чем дольше пауза в снижении, тем дольше сохраняется этот эффект.",
               "Дополнительный процентный доход и более высокая отдача от управления ликвидностью.", [_prod(p, "p_dep", "депозиты")],
               ["Свободные средства действительно размещаются на срок, а не лежат на счетах без процентов", "Нет ограничений на досрочное снятие"],
               ["Средний остаток свободной ликвидности и график платежей по обязательствам"],
               ["Проверить, какая доля остатков работает под процент, и сравнить условия размещения на разные сроки"], "1–3 квартала", None, "deposit")


def m_rate_working_capital(p, sig, ev):
    if sig["factor"] != "rate":
        return None
    d = sig["direction"]
    v, tone = _rate_state(sig)
    elevated = sig.get("level") == "elevated" or (v is not None and v >= settings.rate_elevated_pct)
    if d == "down" or (d == "flat" and not (elevated or tone == "hawkish")):
        return None
    has_fac = p["product_flags"].get("p_fac")
    wc_sectors = {"trade", "construction", "transport", "food", "machinery", "build_materials"}
    if not has_fac and p["sector"] not in wc_sectors:
        return None
    ex = [_prod(p, "p_fac", "факторинг"), _prod(p, "p_gar", "банковские гарантии")]
    if not has_fac:
        ex.append(_sector_ex(p))
    return _mk("rate_wc", "rate", sig, "risk", sig["strength"] * (.7 if has_fac else .5), [("wc_need", +1), ("debt_cost", +1)],
               "Дорожает финансирование оборотного капитала",
               ("Подтверждён факторинг: его стоимость привязана к ставкам, а значит растёт вместе с ценой денег." if has_fac else
                f"Для отрасли «{p['sector_label']}» характерна высокая потребность в оборотном капитале, которую обычно покрывают заёмными средствами и отсрочками."),
               "Высокая ставка удорожает торговое финансирование: растёт дисконт при факторинге, дорожают кредитные линии и отсрочки от поставщиков, которые закладывают стоимость денег в цену.",
               "Увеличение стоимости каждого дня отсрочки платежа и сокращение маржи на сделках с длинным циклом оплаты.",
               ex, ["Значимая доля оборота финансируется факторингом или кредитными линиями", "Сроки оплаты покупателями не сокращаются"],
               ["Объём уступаемой дебиторской задолженности и дисконт", "Средние сроки оплаты по покупателям и поставщикам"],
               ["Сравнить эффективную стоимость факторинга и кредитных линий с маржой по сделкам", "Пересмотреть сроки оплаты с крупнейшими покупателями и поставщиками"],
               "1–2 квартала", None, "factoring" if has_fac else None)


def m_rate_demand(p, sig, ev):
    if sig["factor"] != "rate" or p["sector"] not in {"construction", "real_estate", "machinery", "build_materials", "trade"}:
        return None
    d = sig["direction"]
    v, tone = _rate_state(sig)
    elevated = sig.get("level") == "elevated" or (v is not None and v >= settings.rate_elevated_pct)
    if d == "down":
        sgn, kind, head = -1, "opportunity", "Дешевеющие кредиты могут вернуть спрос ваших покупателей"
    elif d == "up" or elevated or tone == "hawkish":
        sgn, kind, head = 1, "risk", "Дорогие кредиты охлаждают спрос ваших покупателей"
    else:
        return None
    channel = {"construction": "ипотека и проектное финансирование", "real_estate": "ипотека и ставки аренды", "machinery": "инвестиционные кредиты и лизинг для покупателей техники",
               "build_materials": "кредиты застройщиков и строительные проекты", "trade": "потребительские кредиты и оборотное финансирование клиентов"}[p["sector"]]
    return _mk("rate_demand_" + kind, "rate", sig, kind, sig["strength"] * p["sens"]["demand"]["value"] * (.5 if p["sector"] == "trade" else .75), [("demand_pressure", sgn)],
               head, f"Спрос в отрасли «{p['sector_label']}» чувствителен к стоимости кредитов у клиентов.",
               f"Через канал «{channel}» ставка влияет на решения ваших клиентов о покупке и инвестициях: когда деньги дорогие, часть сделок откладывается.",
               "Смещение сроков контрактов и более длинный цикл продаж." if sgn > 0 else "Рост числа сделок, зависящих от кредитования.",
               [_sector_ex(p)], ["Заметная доля продаж финансируется клиентами за счёт кредитов"], ["Доля сделок с кредитным финансированием на стороне покупателя"],
               ["Проверить воронку продаж: сколько сделок зависят от кредитования и как изменился срок их закрытия"], "2–4 квартала", None)


# ---------------------------------------------------------------- inflation / costs / commodities
def m_inflation(p, sig, ev):
    if sig["factor"] != "inflation":
        return None
    s = p["sens"]["inflation"]["value"] * .5 + p["sens"]["input_costs"]["value"] * .5
    if s < .35:
        return None
    d = sig["direction"]
    if d == "flat":
        return None
    up = d == "up"
    return _mk("inflation_" + d, "inflation", sig, "risk" if up else "opportunity", sig["strength"] * s * (1 if up else .7),
               [("input_cost", +1 if up else -1)],
               "Инфляционное давление на затраты усиливается" if up else "Инфляционное давление на затраты ослабевает",
               f"Для отрасли «{p['sector_label']}» значима доля закупок и оплаты труда, которые индексируются вслед за ценами.",
               ("Ускорение инфляции подталкивает вверх цены поставщиков и ожидания по зарплатам, а регулятор дольше удерживает высокую ставку." if up else
                "Замедление инфляции снижает давление на закупочные цены и повышает вероятность смягчения денежно-кредитной политики."),
               "Сжатие маржи, если рост издержек не удаётся переложить в цены." if up else "Больше пространства для планирования закупок и пересмотра цен контрактов.",
               [_sector_ex(p)], ["Рост цен поставщиков не компенсируется индексацией отпускных цен"], ["Структура затрат: сырьё, энергия, оплата труда"],
               ["Проверить условия индексации в долгосрочных контрактах с поставщиками и покупателями", "Оценить долю затрат, привязанных к ценовым индексам"], "1–2 квартала", "input_cost")


def m_input_costs(p, sig, ev):
    if sig["factor"] != "input_costs" or sig["direction"] == "flat":
        return None
    s = p["sens"]["input_costs"]["value"]
    if s < .45:
        return None
    up = sig["direction"] == "up"
    return _mk("input_costs_" + sig["direction"], "input_costs", sig, "risk" if up else "opportunity", sig["strength"] * s * (1 if up else .7),
               [("input_cost", +1 if up else -1)],
               "Растут закупочные затраты" if up else "Закупочные затраты снижаются",
               f"Структура затрат отрасли «{p['sector_label']}» включает сырьё, энергию и материалы, цены на которые меняются.",
               "Рост стоимости сырья и энергоносителей передаётся в себестоимость с задержкой, определяемой условиями контрактов." if up else
               "Снижение цен на ресурсы расширяет маржу, пока цены продаж не пересмотрены.",
               "Сжатие операционной маржи и рост потребности в оборотном капитале." if up else "Возможность сохранить маржу или конкурировать ценой.",
               [_sector_ex(p)], ["Нет индексации цен продаж или хеджирования закупок"], ["Доля затрат на затронутые ресурсы в себестоимости"],
               ["Оценить долю затронутых ресурсов в себестоимости и срок до пересмотра цен контрактов"], "1–2 квартала", "input_cost")


def m_commodity(p, sig, ev):
    if sig["factor"] != "commodity":
        return None
    c = sig["commodity"]
    label = COMMODITIES[c][0]
    up = sig["direction"] == "up"
    out = []
    sells, buys = p["sells"].get(c), p["buys"].get(c)
    if buys:
        kind_ex = "graph" if buys["kind"] == "observed" else "derived"
        out.append(_mk(f"commodity_buyer_{c}", "commodity", sig, "risk" if up else "opportunity", sig["strength"] * buys["weight"] * (1 if up else .7),
                       [("input_cost", +1 if up else -1)],
                       f"{'Дорожает' if up else 'Дешевеет'}: {label}",
                       f"{buys['why'].capitalize()}.",
                       f"{'Рост' if up else 'Снижение'} цены на {label} передаётся в закупочные цены компании напрямую или через поставщиков.",
                       "Давление на маржу при росте цен и необходимость пересмотра закупочных контрактов." if up else "Возможность закупать дешевле и укрепить маржу.",
                       [_ex("graph" if kind_ex == "graph" else "okved", buys["why"].capitalize() + ".", kind_ex)],
                       ["Закупки привязаны к рыночной цене и не зафиксированы", "Цена продажи не индексируется"],
                       [f"Доля {label} в структуре закупок"],
                       [f"Оценить долю {label} в закупках и условия цены в контрактах с поставщиками"], "1–3 месяца", "input_cost"))
    if sells:
        out.append(_mk(f"commodity_seller_{c}", "commodity", sig, "opportunity" if up else "risk", sig["strength"] * min(1.0, sells["weight"] * (1.2 if sells["kind"] == "mapped" else 1.0)) * (1 if up else .9),
                       [("margin", -1 if up else +1)],
                       f"{'Растёт' if up else 'Падает'} цена продукции: {label}",
                       f"{sells['why'].capitalize()}.",
                       f"Цена на {label} {'растёт' if up else 'снижается'}, поэтому меняется выручка производителей этого товара и маржа по контрактам, привязанным к рыночным ценам.",
                       "Рост выручки и маржи по рыночным контрактам." if up else "Снижение выручки и давление на инвестиционные планы.",
                       [_ex("okved", sells["why"].capitalize() + ".", sells["kind"])], ["Контракты привязаны к рыночным ценам, а не фиксированы"],
                       ["Доля продаж по формулам, привязанным к биржевым ценам", "Валюта контрактов"],
                       ["Определить долю выручки с привязкой к цене товара и пересчитать план при изменении цены"], "1–3 месяца", None))
    return out or None


# ---------------------------------------------------------------- fx / foreign trade / logistics
def m_fx(p, sig, ev):
    if sig["factor"] != "fx" or sig["direction"] == "flat":
        return None
    s = p["sens"]["fx"]["value"]
    if s < .35:
        return None
    weaker = sig["direction"] == "up"
    lean = p["export_lean"] if p["export_lean"] is not None else .3
    exporter = lean >= .5
    fts = _fid(p, "fts")
    ex = [_ex("fts", f"Подтверждена внешнеторговая деятельность ({fts['value']}).", "observed") if fts else None, _sector_ex(p)]
    unknown = ["Направление операций (экспорт/импорт), валюта контрактов и доля валютной выручки и расходов"]
    if exporter == weaker:
        kind, head = "opportunity", ("Слабый рубль повышает рублёвую выручку экспортёров" if weaker else "Укрепление рубля помогает импортным закупкам")
    else:
        kind, head = "risk", ("Слабый рубль удорожает импортные закупки" if weaker else "Крепкий рубль снижает рублёвую выручку экспортёров")
    base = (f"Курс {'ослабляет' if weaker else 'укрепляет'} рубль. Для компаний с {'валютной выручкой' if exporter else 'импортными закупками'} это "
            f"{'расширяет' if kind == 'opportunity' else 'сжимает'} маржу, если валюта контрактов и рублёвые расходы не сбалансированы.")
    return _mk("fx_" + kind, "fx", sig, kind, sig["strength"] * s * (.85 if fts else .55), [("fx_pressure", +1)],
               head, "Компания присутствует во внешней торговле, и валютный курс влияет на баланс валюты выручки и расходов." if fts else
               f"Для отрасли «{p['sector_label']}» характерна заметная валютная чувствительность.",
               base + " Направление операций в данных не указано; вывод опирается на типичную ориентацию отрасли.",
               "Изменение рублёвой маржи и стоимости контрактов в иностранной валюте.", ex,
               ["Выручка и расходы компании номинированы в разных валютах", "Нет естественного или финансового хеджирования"], unknown,
               ["Составить валютный баланс: потоки выручки и платежей по валютам и срокам", "Проверить условия валютных оговорок в контрактах"], "1–3 месяца", "fx", "fx")


def m_foreign_trade(p, sig, ev):
    if sig["factor"] != "foreign_trade" or sig["direction"] == "flat":
        return None
    tight = sig["direction"] == "up"
    event_c = set(ev.get("countries") or [])
    my_c = {x.strip() for x in (p["fts_country"] or "").replace(";", ",").split(",") if x.strip()}
    match = {c for c in event_c for m in my_c if c.lower()[:5] == m.lower()[:5] or m.lower() in c.lower() or c.lower() in m.lower()}
    s = p["sens"]["foreign_trade"]["value"]
    if not p["fts_flag"] and not match and s < .55:
        return None
    direct = bool(match)
    ex = [_ex("fts", f"Страна из данных ФТС ({p['fts_country']}) совпадает с упомянутой в событии: {', '.join(sorted(match))}.", "observed") if direct else
          (_ex("fts", "Подтверждена внешнеторговая деятельность.", "observed") if p["fts_flag"] else _sector_ex(p))]
    impact = sig["strength"] * (.9 if direct else (.5 if p["fts_flag"] else .3))
    return _mk("ftrade_" + ("tight" if tight else "ease"), "foreign_trade", sig, "risk" if tight else "opportunity", impact,
               [("supply_continuity", +1 if tight else -1), ("fx_pressure", +1)],
               ("Ужесточаются условия внешней торговли" + (f": {', '.join(sorted(match))}" if direct else "")) if tight else "Условия внешней торговли смягчаются",
               ("Страна из данных ФТС компании прямо упомянута в событии." if direct else
                "В данных подтверждена внешнеторговая деятельность компании." if p["fts_flag"] else f"Отрасль «{p['sector_label']}» вовлечена во внешнюю торговлю."),
               ("Новые ограничения, пошлины или санкции меняют стоимость и сроки поставок, могут потребовать смены маршрутов, контрагентов и платёжных каналов." if tight else
                "Смягчение условий снижает издержки на таможне и расширяет набор маршрутов и контрагентов."),
               "Рост стоимости и сроков поставок, риск простоев и пересмотра контрактов." if tight else "Снижение издержек поставок и расширение рынков.",
               ex, ["Затронуты товарные позиции, страны или платёжные каналы, которые используются компанией"],
               ["Товарная структура и география поставок по контрактам", "Альтернативные маршруты и поставщики"],
               ["Сопоставить затронутые товарные позиции и страны с действующими контрактами", "Оценить запас по сроку поставок и альтернативные маршруты"], "1–6 месяцев", None, "fx" if tight else None)


def m_logistics(p, sig, ev):
    if sig["factor"] != "logistics" or sig["direction"] == "flat":
        return None
    s = p["sens"]["logistics"]["value"]
    if s < .4:
        return None
    up = sig["direction"] == "up"
    g = p.get("graph") or {}
    top = (g.get("recipients") or {}).get("top1_share")
    ex = [_sector_ex(p)]
    if top and top >= .4:
        ex.append(_ex("graph", f"В наблюдаемых платежах крупнейший получатель занимает {top:.0%}: цепочка зависит от немногих контрагентов.", "graph"))
    return _mk("logistics_" + sig["direction"], "logistics", sig, "risk" if up else "opportunity", sig["strength"] * s * (1.1 if top and top >= .4 else 1),
               [("supply_continuity", +1 if up else -1)],
               "Растёт нагрузка на логистику и поставки" if up else "Логистика упрощается и дешевеет",
               f"Отрасль «{p['sector_label']}» чувствительна к стоимости и срокам перевозок.",
               ("Задержки и рост тарифов на перевозки увеличивают срок доставки, заставляют держать больше запасов и повышают стоимость каждой поставки." if up else
                "Снижение ставок и сроков доставки уменьшает запасы и стоимость поставок."),
               "Рост запасов, затрат на доставку и потребности в оборотном капитале." if up else "Снижение себестоимости доставки и высвобождение оборотного капитала.",
               ex, ["Затронутые маршруты и виды транспорта используются компанией"], ["Маршруты поставок и доля логистики в себестоимости"],
               ["Выявить маршруты, затронутые событием, и оценить запас прочности по срокам поставок"], "1–3 месяца", None)


# ---------------------------------------------------------------- demand / labour / regulation / competition / tech / liquidity
def m_demand(p, sig, ev):
    if sig["factor"] != "demand" or sig["direction"] == "flat":
        return None
    s = p["sens"]["demand"]["value"]
    ev_sec = set(ev.get("sectors") or [])
    cust = ((p.get("graph") or {}).get("payers") or {}).get("sectors", {})
    cust_hit = max((cust.get(k, 0) for k in ev_sec), default=0)
    own_hit = p["sector"] in ev_sec
    if ev_sec and not own_hit and cust_hit < .15:
        return None
    if not ev_sec and s < .7:
        return None
    up = sig["direction"] == "up"
    ex = [_sector_ex(p)]
    if own_hit:
        ex.append(_ex("okved", f"Событие относится к отрасли «{p['sector_label']}», в которой работает компания.", "observed"))
    if cust_hit >= .15:
        ex.append(_ex("graph", f"{cust_hit:.0%} наблюдаемых входящих платежей приходит из затронутой отрасли.", "graph"))
    boost = 1.0 + (.25 if own_hit else 0) + (.2 if cust_hit >= .15 else 0)
    return _mk("demand_" + sig["direction"], "demand", sig, "opportunity" if up else "risk", sig["strength"] * min(1, s * boost),
               [("demand_pressure", -1 if up else +1)],
               ("Спрос в вашей отрасли растёт" if up else "Спрос в вашей отрасли слабеет") if own_hit else
               ("Растёт спрос у ваших покупателей" if up else "Слабеет спрос у ваших покупателей") if cust_hit >= .15 else
               ("Спрос в затронутом сегменте растёт" if up else "Спрос в затронутом сегменте слабеет"),
               "Событие затрагивает " + ("вашу отрасль" if own_hit else "отрасль, из которой приходит значимая доля платежей компании" if cust_hit >= .15 else f"отрасль, где спрос определяет результат («{p['sector_label']}»)") + ".",
               ("Рост спроса увеличивает загрузку мощностей и объём заказов, но требует запасов и оборотного капитала." if up else
                "Снижение спроса удлиняет оборачиваемость запасов и дебиторской задолженности и давит на цены."),
               "Рост продаж при необходимости нарастить запасы." if up else "Падение продаж и удлинение цикла оплаты.", ex,
               ["Затронутый сегмент составляет заметную долю продаж компании"], ["Структура продаж по сегментам и клиентам"],
               ["Оценить долю затронутого сегмента в выручке и концентрацию крупнейших покупателей"], "1–3 квартала", None)


def m_labor(p, sig, ev):
    if sig["factor"] != "labor" or sig["direction"] == "flat":
        return None
    s = p["sens"]["labor"]["value"]
    if s < .5:
        return None
    up = sig["direction"] == "up"
    return _mk("labor_" + sig["direction"], "labor", sig, "risk" if up else "opportunity", sig["strength"] * s * (1 if up else .6),
               [("labor_cost", +1 if up else -1)],
               "Рынок труда усиливает давление на зарплаты" if up else "Давление на рынок труда ослабевает",
               "Отрасль требует значимого штата" + (", и у компании подключён зарплатный проект" if p["product_flags"].get("p_zpp") else "") + ".",
               "Напряжённый рынок труда повышает цену привлечения и удержания сотрудников, а индексация зарплат закрепляется в постоянных расходах." if up else
               "Смягчение рынка труда облегчает найм и снижает темп роста оплаты труда.",
               "Рост фонда оплаты труда и текучести ключевых специальностей." if up else "Снижение давления на постоянные затраты.",
               [_prod(p, "p_zpp", "зарплатный проект"), _sector_ex(p)], ["Дефицит кадров затрагивает ключевые специальности компании"],
               ["Доля ФОТ в расходах и структура штата по специальностям"],
               ["Проверить, какие должности уже требуют премий к рынку и какова текучесть"], "2–4 квартала", None)


def m_regulation(p, sig, ev):
    if sig["factor"] != "regulation" or sig["direction"] == "flat":
        return None
    own_hit = p["sector"] in set(ev.get("sectors") or [])
    s = p["sens"]["regulation"]["value"]
    generic_tax = any(w in sig["quote"].lower() for w in ("налог", "ндс", "отчётн", "отчетн", "страхов"))
    if not own_hit and s < .6 and not generic_tax:
        return None
    up = sig["direction"] == "up"
    ex = [_ex("okved", f"Регулирование затрагивает отрасль «{p['sector_label']}».", "observed") if own_hit else _sector_ex(p)]
    return _mk("regulation_" + sig["direction"], "regulation", sig, "risk" if up else "opportunity", sig["strength"] * min(1, (s if not own_hit else max(s, .7)) * (1.15 if own_hit else .8)),
               [("compliance_cost", +1 if up else -1)],
               "Регулирование усложняется" if up else "Регуляторная нагрузка снижается",
               "Правило затрагивает " + ("вашу отрасль" if own_hit else "хозяйственную деятельность независимо от отрасли (налоги и отчётность)") + ".",
               "Новые требования и санкции за их нарушение повышают постоянные издержки и требуют перестройки процессов и учёта." if up else
               "Снятие или упрощение требований снижает издержки соблюдения и риск штрафов.",
               "Рост затрат на соблюдение требований и риск санкций при задержке." if up else "Экономия на соблюдении требований.",
               ex, ["Правило применяется к видам деятельности компании и вступает в силу в горизонте планирования"],
               ["Дата вступления в силу, переходные положения и применимость к юридическим лицам группы"],
               ["Поручить юристам и бухгалтерии оценить применимость и сроки", "Определить затронутые процессы и системы учёта"], "до даты вступления в силу", None)


def m_competition(p, sig, ev):
    if sig["factor"] != "competition" or p["sector"] not in set(ev.get("sectors") or []):
        return None
    up = sig["direction"] != "down"
    return _mk("competition_" + sig["direction"], "competition", sig, "risk" if up else "opportunity", sig["strength"] * max(p["sens"]["competition"]["value"], .5) * .8,
               [("demand_pressure", +1 if up else -1)],
               "Конкурентная среда в вашей отрасли меняется",
               f"Событие относится к отрасли «{p['sector_label']}», в которой работает компания.",
               "Укрупнение, выход нового игрока или смена стратегии крупного участника перераспределяют спрос и условия закупок." if up else
               "Уход игрока освобождает долю рынка и ослабляет ценовое давление.",
               "Давление на цены и долю рынка." if up else "Возможность нарастить долю в освободившемся сегменте.",
               [_ex("okved", f"Событие относится к отрасли «{p['sector_label']}».", "observed")], ["Игрок конкурирует с компанией в одних и тех же сегментах и регионах"],
               ["Пересечение географии и клиентов с затронутыми игроками"],
               ["Оценить пересечение клиентской базы и регионов с затронутым игроком"], "2–4 квартала", None)


def m_tech(p, sig, ev):
    if sig["factor"] != "tech" or sig["direction"] == "down":
        return None
    rko = p["product_flags"].get("p_rko")
    s = max(p["sens"]["tech"]["value"], .45 if rko else 0)
    if s < .4:
        return None
    return _mk("tech_risk", "tech", sig, "risk", sig["strength"] * s * .8, [],
               "Растут киберриски и риски мошенничества с платежами",
               "У компании подтверждено расчётно-кассовое обслуживание: через него проходят платежи и доступы руководителей." if rko else
               f"Для отрасли «{p['sector_label']}» цифровая инфраструктура критична для работы.",
               "Социальная инженерия, подделка голоса и документов и атаки на цифровые сервисы нацелены на подмену платёжных указаний и получение доступов.",
               "Прямые потери от мошеннических платежей и простои сервисов.",
               [_prod(p, "p_rko", "расчётно-кассовое обслуживание") if rko else _sector_ex(p)],
               ["Подтверждение платежей осуществляется без дополнительных проверок"], ["Политика подтверждения платежей и разграничение доступов"],
               ["Проверить порядок подтверждения платежей по новым реквизитам и лимиты на операции", "Провести напоминание сотрудникам о сценариях подмены руководителя"], "немедленно", None)


def m_liquidity(p, sig, ev):
    if sig["factor"] != "liquidity" or sig["direction"] == "flat":
        return None
    s = p["sens"]["liquidity"]["value"]
    if s < .45:
        return None
    tight = sig["direction"] == "up"
    return _mk("liquidity_" + ("tight" if tight else "ease"), "liquidity", sig, "risk" if tight else "opportunity", sig["strength"] * s * .85,
               [("debt_cost", +1 if tight else -1), ("wc_need", +1 if tight else -1)],
               "Ужесточаются условия рыночного финансирования" if tight else "Условия рыночного финансирования смягчаются",
               "Компания использует заёмные инструменты банка или чувствительна к стоимости ликвидности." if p["debt_exposure"] else
               f"Отрасль «{p['sector_label']}» зависит от доступности финансирования.",
               "Рост доходностей и спредов на долговом рынке повышает цену новых заимствований и рефинансирования." if tight else
               "Снижение доходностей и спредов делает размещения облигаций и рефинансирование дешевле.",
               "Дорожание новых заимствований и ограничение сроков." if tight else "Окно для заимствований на лучших условиях.",
               [_prod(p, "p_loa", "кредитные продукты"), _prod(p, "p_gar", "банковские гарантии"), _sector_ex(p)],
               ["Планируются новые заимствования или рефинансирование в ближайшие 12 месяцев"], ["График погашений и планы заимствований"],
               ["Сверить календарь погашений с текущими условиями рынка"], "1–2 квартала", None)


def m_counterparty(p, sig, ev):
    """Event touches the sector of the company's largest payment counterparties."""
    g = p.get("graph")
    if not g or not g["available"] or sig["factor"] in {"rate", "fx", "inflation", "liquidity"}:
        return None
    ev_sec = set(ev.get("sectors") or [])
    if not ev_sec:
        return None
    rec = g["recipients"]["sectors"]
    pay = g["payers"]["sectors"]
    best = max(((k, rec.get(k, 0), "recipients") for k in ev_sec), key=lambda x: x[1], default=None)
    best2 = max(((k, pay.get(k, 0), "payers") for k in ev_sec), key=lambda x: x[1], default=None)
    cand = max([c for c in (best, best2) if c], key=lambda x: x[1], default=None)
    if not cand or cand[1] < .15 or cand[0] == p["sector"]:
        return None
    k, share, side = cand
    side_txt = "получателям платежей компании (вероятным поставщикам)" if side == "recipients" else "плательщикам компании (вероятным покупателям)"
    node = "supply_continuity" if side == "recipients" else "demand_pressure"
    return _mk("counterparty_" + side, sig["factor"], sig, "watch", sig["strength"] * min(1, share * 1.4) * .55, [(node, +1)],
               "Событие затрагивает отрасль ваших ключевых контрагентов",
               f"{share:.0%} наблюдаемых платежей приходится на отрасль «{SECTORS[k]['label']}» — это относится к {side_txt}.",
               f"Сигнал в отрасли «{SECTORS[k]['label']}» может косвенно изменить цены, сроки и надёжность по цепочке {'поставок' if side == 'recipients' else 'сбыта'}, даже если компания в нём не упомянута.",
               "Косвенное влияние через контрагентов; степень зависимости по платёжным данным не определяется.",
               [_ex("graph", f"{share:.0%} платежей — в отрасль «{SECTORS[k]['label']}» (по ОКВЭД контрагентов).", "graph")],
               ["Контрагенты из этой отрасли действительно критичны и трудно заменяемы"], ["Договорные условия и заменяемость контрагентов", "Динамика платежей во времени (нет в данных)"],
               ["Выяснить у закупок/продаж, какие контрагенты в этой отрасли критичны, и запросить у них оценку влияния"], "1–3 квартала", None)


BUILDERS = [m_rate_debt, m_rate_deposit, m_rate_working_capital, m_rate_demand, m_inflation, m_input_costs, m_commodity, m_fx,
            m_foreign_trade, m_logistics, m_demand, m_labor, m_regulation, m_competition, m_tech, m_liquidity, m_counterparty]


def mechanisms_for(profile, event):
    out = []
    for sig in event["signals"]:
        for b in BUILDERS:
            r = b(profile, sig, event)
            if r is None:
                continue
            out.extend(r if isinstance(r, list) else [r])
    out.sort(key=lambda m: -m["impact"])
    seen, uniq = set(), []
    for m in out:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        uniq.append(m)
    return uniq

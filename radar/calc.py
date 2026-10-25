"""Sensitivity arithmetic. Pure functions; every input is supplied by the user and echoed back as an assumption."""


def _f(v, name, lo=None, hi=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Поле «{name}» должно быть числом")
    if lo is not None and x < lo or hi is not None and x > hi:
        raise ValueError(f"Поле «{name}» вне допустимого диапазона")
    return x


def debt_service(debt, floating_share, rate_delta_pp, months=12, revenue=None):
    debt, fs = _f(debt, "Объём долга", 0), _f(floating_share, "Доля плавающей ставки, %", 0, 100) / 100
    d, m = _f(rate_delta_pp, "Изменение ставки, п.п."), _f(months, "Горизонт, мес.", 1, 60)
    extra = debt * fs * d / 100 * m / 12
    table = [{"delta_pp": x, "extra": debt * fs * x / 100 * m / 12} for x in (-2, -1, 0, 1, 2, 3)]
    res = {"kind": "debt_service", "result": extra, "unit": "₽",
           "formula": "Δ процентных расходов = долг × доля плавающей ставки × Δ ставки × горизонт / 12",
           "steps": [f"{debt:,.0f} × {fs:.0%} × {d:+g} п.п. × {m:g}/12 = {extra:,.0f} ₽"], "table": table,
           "assumptions": ["Ставка по плавающей части меняется на указанную величину сразу и на весь горизонт", "Долг не гасится в течение горизонта", "Фиксированная часть долга не меняется"]}
    if revenue:
        res["share_of_revenue_pct"] = extra / float(revenue) * 100
    return res


def input_cost(purchases, price_change_pct, passthrough_pct, revenue=None):
    p, c = _f(purchases, "Годовые закупки затронутого ресурса", 0), _f(price_change_pct, "Изменение цены, %")
    t = _f(passthrough_pct, "Доля, переложенная в цены продаж, %", 0, 100) / 100
    gross = p * c / 100
    net = gross * (1 - t)
    res = {"kind": "input_cost", "result": -net, "unit": "₽ маржи в год",
           "formula": "Эффект на маржу = − закупки × Δ цены × (1 − доля переложенная в цены)",
           "steps": [f"Рост затрат: {p:,.0f} × {c:+g}% = {gross:,.0f} ₽", f"Остаётся на марже: {gross:,.0f} × (1 − {t:.0%}) = {net:,.0f} ₽"],
           "table": [{"passthrough": x, "effect": -gross * (1 - x / 100)} for x in (0, 25, 50, 75, 100)],
           "assumptions": ["Объём закупок не меняется", "Изменение цены действует весь год", "Цены продаж пересматриваются на указанную долю роста затрат"]}
    if revenue:
        res["share_of_revenue_pp"] = -net / float(revenue) * 100
    return res


def fx(foreign_revenue, foreign_costs, fx_change_pct):
    r, c, ch = _f(foreign_revenue, "Валютная выручка (в рублях по текущему курсу)", 0), _f(foreign_costs, "Валютные расходы (в рублях по текущему курсу)", 0), _f(fx_change_pct, "Изменение курса, % (+ рубль слабее)")
    net = (r - c) * ch / 100
    return {"kind": "fx", "result": net, "unit": "₽ в год",
            "formula": "Эффект = (валютная выручка − валютные расходы) × Δ курса",
            "steps": [f"({r:,.0f} − {c:,.0f}) × {ch:+g}% = {net:,.0f} ₽"],
            "table": [{"fx_change": x, "effect": (r - c) * x / 100} for x in (-15, -10, -5, 0, 5, 10, 15)],
            "assumptions": ["Рублёвые расходы и цены контрактов не меняются", "Курс меняется сразу и на весь горизонт", "Хеджирование отсутствует"]}


def working_capital(revenue, extra_days, cost_of_funds_pct):
    rev, d, k = _f(revenue, "Годовая выручка", 0), _f(extra_days, "Дополнительные дни оборота", -90, 180), _f(cost_of_funds_pct, "Стоимость финансирования, %", 0, 100)
    need = rev / 365 * d
    interest = need * k / 100
    return {"kind": "working_capital", "result": need, "unit": "₽ дополнительного оборотного капитала", "extra_interest": interest,
            "formula": "Доп. оборотный капитал = выручка / 365 × дополнительные дни; процентные расходы = капитал × стоимость финансирования",
            "steps": [f"{rev:,.0f} / 365 × {d:g} = {need:,.0f} ₽", f"{need:,.0f} × {k:g}% = {interest:,.0f} ₽ в год"],
            "table": [{"days": x, "need": rev / 365 * x} for x in (5, 10, 15, 30)],
            "assumptions": ["Выручка равномерна в течение года", "Дополнительный капитал полностью финансируется заёмными средствами"]}


CALCS = {
    "debt_service": {"fn": debt_service, "title": "Процентная нагрузка при изменении ставки",
                     "fields": [("debt", "Объём долга, ₽", None), ("floating_share", "Доля плавающей ставки, %", 100), ("rate_delta_pp", "Изменение ставки, п.п.", 1), ("months", "Горизонт, мес.", 12)]},
    "input_cost": {"fn": input_cost, "title": "Влияние роста затрат на маржу",
                   "fields": [("purchases", "Годовые закупки ресурса, ₽", None), ("price_change_pct", "Изменение цены, %", 10), ("passthrough_pct", "Доля, переложенная в цены, %", 50)]},
    "fx": {"fn": fx, "title": "Валютный эффект",
           "fields": [("foreign_revenue", "Валютная выручка, ₽-экв.", None), ("foreign_costs", "Валютные расходы, ₽-экв.", None), ("fx_change_pct", "Изменение курса, % (+ рубль слабее)", 10)]},
    "working_capital": {"fn": working_capital, "title": "Потребность в оборотном капитале",
                        "fields": [("extra_days", "Дополнительные дни оборота", 10), ("cost_of_funds_pct", "Стоимость финансирования, %", None)]},
}


def run(kind, inputs, revenue=None):
    spec = CALCS.get(kind)
    if not spec:
        raise ValueError("Неизвестный тип расчёта")
    args = dict(inputs or {})
    if kind in ("debt_service", "input_cost") and revenue:
        args["revenue"] = revenue
    if kind == "working_capital":
        args["revenue"] = args.get("revenue") or revenue
        if not args["revenue"]:
            raise ValueError("Для расчёта нужна годовая выручка")
    return spec["fn"](**args)


def spec_for(kind, revenue=None):
    s = CALCS[kind]
    fields = [{"key": k, "label": l, "default": d} for k, l, d in s["fields"]]
    return {"kind": kind, "title": s["title"], "fields": fields, "revenue": revenue}

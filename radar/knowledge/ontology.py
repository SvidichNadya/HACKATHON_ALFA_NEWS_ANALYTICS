"""Transmission ontology: how external factors travel through a company's economics.

Tier 1 nodes are first-order effects of a factor, tier 2 are shared bottlenecks where independent signals
converge, tier 3 is the outcome a manager cares about. Edge weights are structural priors, not estimates
for a particular company; the cascade detector reports them as such.
"""

NODES = {
    "debt_cost": {"label": "Стоимость обслуживания долга", "tier": 1},
    "input_cost": {"label": "Закупочные затраты", "tier": 1},
    "fx_pressure": {"label": "Валютная чувствительность", "tier": 1},
    "supply_continuity": {"label": "Устойчивость поставок", "tier": 1},
    "demand_pressure": {"label": "Давление на спрос", "tier": 1},
    "compliance_cost": {"label": "Регуляторная нагрузка", "tier": 1},
    "labor_cost": {"label": "Затраты на персонал", "tier": 1},
    "deposit_income": {"label": "Доходность размещений", "tier": 1},
    "refi_window": {"label": "Окно рефинансирования", "tier": 1},
    "wc_need": {"label": "Потребность в оборотном капитале", "tier": 2},
    "margin": {"label": "Операционная маржа", "tier": 2},
    "liquidity": {"label": "Запас ликвидности", "tier": 3},
}

# (from, to, weight, explanation)
EDGES = [
    ("debt_cost", "liquidity", .70, "Рост процентных платежей уменьшает свободный денежный поток."),
    ("input_cost", "margin", .80, "Дорожающие закупки сжимают маржу, если их не удаётся переложить в цены."),
    ("input_cost", "wc_need", .60, "Дорожающие запасы и предоплаты увеличивают потребность в оборотном капитале."),
    ("fx_pressure", "margin", .60, "Расхождение валюты расходов и выручки меняет маржу."),
    ("fx_pressure", "wc_need", .50, "Курсовые колебания меняют стоимость закупок и сроков расчётов."),
    ("supply_continuity", "wc_need", .60, "Сбои поставок требуют повышенных запасов и предоплат."),
    ("supply_continuity", "margin", .40, "Срочные закупки и простои повышают себестоимость."),
    ("demand_pressure", "wc_need", .50, "Слабый спрос удлиняет оборачиваемость запасов и дебиторской задолженности."),
    ("demand_pressure", "margin", .60, "Недозагрузка мощностей и скидки снижают маржу."),
    ("compliance_cost", "margin", .40, "Новые требования добавляют постоянные издержки."),
    ("labor_cost", "margin", .60, "Рост оплаты труда увеличивает постоянные расходы."),
    ("wc_need", "liquidity", .80, "Рост потребности в оборотном капитале расходует ликвидность и усиливает зависимость от кредитных линий."),
    ("margin", "liquidity", .70, "Падение маржи сокращает операционный денежный поток."),
    ("deposit_income", "liquidity", .40, "Процентный доход от размещений пополняет запас ликвидности."),
    ("refi_window", "debt_cost", .60, "Дешевеющее рефинансирование снижает стоимость долга."),
]
EDGE_INDEX = {(a, b): (w, t) for a, b, w, t in EDGES}

ROLE_WEIGHTS = {
    "owner": {"competition": 1.2, "regulation": 1.1, "foreign_trade": 1.1, "commodity": 1.1},
    "ceo": {},
    "cfo": {"rate": 1.2, "liquidity": 1.2, "fx": 1.1, "regulation": 1.1, "inflation": 1.05},
    "treasurer": {"rate": 1.3, "liquidity": 1.3, "fx": 1.25},
    "chief_accountant": {"regulation": 1.45, "labor": 1.1},
    "dept_head": {"logistics": 1.2, "demand": 1.2, "labor": 1.15, "input_costs": 1.1, "commodity": 1.1},
}

ROLE_LABELS = {
    "owner": "Собственник", "ceo": "Генеральный директор", "cfo": "Финансовый директор",
    "treasurer": "Руководитель казначейства", "chief_accountant": "Главный бухгалтер", "dept_head": "Руководитель направления",
}

"""Sector knowledge keyed by OKVED division.

Baseline sensitivities are expert priors about how strongly a *typical* firm in the sector is exposed to a
macro factor (0..1). They are never shown as facts about a particular company: the profile builder records
them with kind="derived" and the interpretation layer treats them as hypotheses until company data confirms.
"""

FACTORS = (
    "rate", "inflation", "input_costs", "fx", "foreign_trade", "logistics",
    "demand", "labor", "regulation", "commodity", "competition", "tech", "liquidity",
)

FACTOR_LABELS = {
    "rate": "Стоимость заёмного капитала",
    "inflation": "Инфляция",
    "input_costs": "Затраты и сырьё",
    "fx": "Валютный курс",
    "foreign_trade": "Внешняя торговля",
    "logistics": "Логистика и поставки",
    "demand": "Спрос",
    "labor": "Рынок труда",
    "regulation": "Регулирование и налоги",
    "commodity": "Товарные рынки",
    "competition": "Конкуренция",
    "tech": "Технологии и киберриски",
    "liquidity": "Условия финансирования",
}

COMMODITIES = {
    "oil": ("нефть", ["нефт", "brent", "urals"]),
    "gas": ("газ", ["газ", "спг"]),
    "fuel": ("топливо", ["бензин", "дизельн", "топлив", "дт "]),
    "electricity": ("электроэнергия", ["электроэнерг", "энерготариф"]),
    "coal": ("уголь", ["уголь", "угол", "коксующ"]),
    "steel": ("сталь и прокат", ["сталь", "прокат", "арматур", "чугун", "металлопрокат"]),
    "aluminium": ("алюминий", ["алюмин"]),
    "copper": ("медь", ["медь", "медн"]),
    "nickel": ("никель", ["никел"]),
    "gold": ("золото", ["золот"]),
    "grain": ("зерно", ["пшениц", "зерн", "ячмен", "кукуруз", "подсолнечн"]),
    "sugar": ("сахар", ["сахар"]),
    "fertilizer": ("удобрения", ["удобрен", "аммиачн", "карбамид", "калий"]),
    "cement": ("цемент", ["цемент", "бетон", "стройматериал"]),
    "timber": ("лесоматериалы", ["лесоматериал", "древесин", "пиломатериал"]),
    "chemicals": ("полимеры и химия", ["полимер", "полиэтилен", "пластик", "химическ"]),
    "components": ("электронные компоненты", ["микросхем", "чип", "комплектующ", "полупроводник"]),
}

# key: (label, [(lo, hi) divisions], baseline sensitivities, keywords (surface words, stemmed at import),
#       commodities sold, commodities bought, export orientation 0..1)
_RAW = {
    "agri": ("Сельское и лесное хозяйство, рыболовство", [(1, 3)],
             dict(rate=.55, inflation=.5, input_costs=.75, fx=.45, foreign_trade=.55, logistics=.55, demand=.35, labor=.35, regulation=.5, competition=.3, tech=.2, liquidity=.4),
             ["сельск", "агро", "урожа", "посев", "ферм", "животновод", "растениевод", "рыболов"], ["grain", "sugar"], ["fuel", "fertilizer"], .5),
    "mining_energy": ("Добыча нефти, газа, угля", [(5, 6)],
             dict(rate=.45, inflation=.35, input_costs=.4, fx=.85, foreign_trade=.85, logistics=.6, demand=.3, labor=.4, regulation=.75, competition=.2, tech=.3, liquidity=.4),
             ["нефтедобыч", "добыч", "нефтегаз", "месторожден", "угольн"], ["oil", "gas", "coal"], ["electricity", "fuel"], .85),
    "mining_metals": ("Добыча металлических руд и прочих полезных ископаемых", [(7, 9)],
             dict(rate=.5, inflation=.4, input_costs=.5, fx=.8, foreign_trade=.8, logistics=.65, demand=.4, labor=.45, regulation=.7, competition=.25, tech=.3, liquidity=.4),
             ["руд", "горнодобыв", "карьер", "рудник", "драгоценн"], [], ["electricity", "fuel"], .8),
    "food": ("Производство пищевых продуктов и напитков", [(10, 12)],
             dict(rate=.55, inflation=.6, input_costs=.7, fx=.4, foreign_trade=.4, logistics=.6, demand=.65, labor=.45, regulation=.6, competition=.65, tech=.3, liquidity=.45),
             ["пищев", "продовольств", "мясо", "молоч", "напитк", "кондитер", "мукомол", "масложир"], [], ["grain", "sugar", "electricity", "chemicals"], .35),
    "light": ("Текстиль, одежда, кожа", [(13, 15)],
             dict(rate=.5, inflation=.5, input_costs=.65, fx=.55, foreign_trade=.55, logistics=.55, demand=.7, labor=.55, regulation=.45, competition=.7, tech=.25, liquidity=.4),
             ["текстил", "одежд", "швейн", "кож", "обув"], [], ["chemicals", "electricity"], .15),
    "wood_paper": ("Деревообработка, бумага, полиграфия", [(16, 18)],
             dict(rate=.55, inflation=.5, input_costs=.65, fx=.55, foreign_trade=.6, logistics=.65, demand=.55, labor=.45, regulation=.5, competition=.5, tech=.3, liquidity=.4),
             ["деревообраб", "бумаг", "картон", "полиграф", "лесопиль", "древесин"], ["timber"], ["electricity", "timber"], .5),
    "refining": ("Производство кокса и нефтепродуктов", [(19, 19)],
             dict(rate=.55, inflation=.4, input_costs=.5, fx=.8, foreign_trade=.8, logistics=.7, demand=.4, labor=.35, regulation=.85, competition=.25, tech=.35, liquidity=.4),
             ["нефтепереработ", "нпз", "нефтепродукт", "коксохим"], ["fuel"], ["oil", "electricity"], .65),
    "chem_pharma": ("Химия, фармацевтика, пластмассы", [(20, 22)],
             dict(rate=.6, inflation=.5, input_costs=.7, fx=.65, foreign_trade=.65, logistics=.6, demand=.55, labor=.45, regulation=.7, competition=.5, tech=.4, liquidity=.45),
             ["хими", "фармацевт", "лекарств", "пластмасс", "резин", "удобрен"], ["fertilizer", "chemicals"], ["gas", "oil", "electricity"], .5),
    "build_materials": ("Производство неметаллических минеральных продуктов", [(23, 23)],
             dict(rate=.65, inflation=.5, input_costs=.75, fx=.35, foreign_trade=.3, logistics=.7, demand=.75, labor=.45, regulation=.55, competition=.55, tech=.3, liquidity=.45),
             ["цемент", "стекл", "кирпич", "бетон", "керамик", "стройматериал"], ["cement"], ["gas", "electricity", "fuel"], .15),
    "metallurgy": ("Металлургия и металлообработка", [(24, 25)],
             dict(rate=.6, inflation=.45, input_costs=.7, fx=.75, foreign_trade=.8, logistics=.7, demand=.65, labor=.45, regulation=.6, competition=.5, tech=.35, liquidity=.45),
             ["металлург", "прокат", "металлопрокат", "чугун", "алюмин", "металлоконструкц", "трубн", "сплав"], ["steel", "aluminium"], ["coal", "electricity", "gas"], .65),
    "machinery": ("Машиностроение, электроника, автомобили", [(26, 30)],
             dict(rate=.7, inflation=.5, input_costs=.65, fx=.6, foreign_trade=.65, logistics=.6, demand=.8, labor=.55, regulation=.5, competition=.6, tech=.55, liquidity=.5),
             ["машиностроен", "станк", "оборудован", "электроник", "автомобил", "двигател", "приборостро", "локомотив"], [], ["steel", "components", "electricity", "aluminium"], .3),
    "other_mfg": ("Прочее производство, ремонт и монтаж оборудования", [(31, 33)],
             dict(rate=.5, inflation=.5, input_costs=.6, fx=.45, foreign_trade=.4, logistics=.5, demand=.65, labor=.5, regulation=.45, competition=.6, tech=.35, liquidity=.4),
             ["мебел", "ремонт оборудован", "монтаж оборудован"], [], ["timber", "steel", "chemicals"], .1),
    "energy_util": ("Энергетика, водоснабжение, обращение с отходами", [(35, 39)],
             dict(rate=.65, inflation=.45, input_costs=.5, fx=.3, foreign_trade=.2, logistics=.3, demand=.4, labor=.45, regulation=.9, competition=.2, tech=.45, liquidity=.5),
             ["электроэнерг", "генерац", "теплоснабж", "водоснабж", "энергосбыт", "коммунальн", "отход"], ["electricity"], ["gas", "coal"], .05),
    "construction": ("Строительство", [(41, 43)],
             dict(rate=.85, inflation=.65, input_costs=.85, fx=.3, foreign_trade=.3, logistics=.65, demand=.8, labor=.65, regulation=.65, competition=.6, tech=.3, liquidity=.65),
             ["строительн", "застройщик", "жилищн", "подряд", "девелопер", "недвижим", "ипотек"], [], ["cement", "steel", "fuel", "timber"], .05),
    "trade": ("Торговля оптовая и розничная", [(45, 47)],
             dict(rate=.65, inflation=.6, input_costs=.5, fx=.55, foreign_trade=.55, logistics=.75, demand=.85, labor=.55, regulation=.5, competition=.75, tech=.45, liquidity=.55),
             ["торговл", "ритейл", "оптов", "розничн", "дистрибу", "магазин", "маркетплейс", "потребительск"], [], ["fuel"], .1),
    "transport": ("Транспортировка и хранение", [(49, 53)],
             dict(rate=.6, inflation=.5, input_costs=.75, fx=.45, foreign_trade=.65, logistics=.9, demand=.65, labor=.65, regulation=.6, competition=.55, tech=.4, liquidity=.5),
             ["транспорт", "перевозк", "грузоперевоз", "логистик", "склад", "авиа", "морск", "железнодорож", "порт"], [], ["fuel"], .3),
    "hospitality": ("Гостиницы, общепит, туризм", [(55, 56)],
             dict(rate=.5, inflation=.6, input_costs=.6, fx=.4, foreign_trade=.3, logistics=.35, demand=.85, labor=.75, regulation=.5, competition=.65, tech=.35, liquidity=.4),
             ["гостиниц", "отел", "общепит", "ресторан", "туризм", "турист"], [], ["grain", "sugar"], .05),
    "it_telecom": ("Информационные технологии и связь", [(58, 63)],
             dict(rate=.35, inflation=.4, input_costs=.35, fx=.5, foreign_trade=.4, logistics=.2, demand=.65, labor=.9, regulation=.6, competition=.65, tech=.9, liquidity=.35),
             ["программн", "разработк", "телеком", "связь", "оператор связи", "цифров", "облачн", "информационн"], [], ["components"], .15),
    "finance": ("Финансы и страхование", [(64, 66)],
             dict(rate=.8, inflation=.4, input_costs=.2, fx=.5, foreign_trade=.3, logistics=.1, demand=.6, labor=.55, regulation=.9, competition=.65, tech=.7, liquidity=.9),
             ["банковск", "страхов", "лизинг", "брокер", "финансов"], [], [], .05),
    "real_estate": ("Операции с недвижимым имуществом", [(68, 68)],
             dict(rate=.9, inflation=.5, input_costs=.4, fx=.2, foreign_trade=.1, logistics=.1, demand=.8, labor=.3, regulation=.65, competition=.5, tech=.3, liquidity=.7),
             ["недвижим", "аренд", "девелопер", "коммерческ недвижим"], [], [], .0),
    "prof_services": ("Профессиональные, научные и технические услуги", [(69, 75)],
             dict(rate=.35, inflation=.4, input_costs=.3, fx=.35, foreign_trade=.3, logistics=.15, demand=.65, labor=.8, regulation=.5, competition=.6, tech=.6, liquidity=.35),
             ["консалтинг", "юридическ", "аудит", "инжиниринг", "проектирован", "научн", "исследован", "реклам"], [], [], .1),
    "admin_support": ("Административная деятельность и сопутствующие услуги", [(77, 82)],
             dict(rate=.4, inflation=.45, input_costs=.4, fx=.25, foreign_trade=.2, logistics=.3, demand=.55, labor=.8, regulation=.5, competition=.6, tech=.4, liquidity=.35),
             ["аутсорсинг", "персонал", "охран", "клининг", "аренда оборудован"], [], [], .0),
    "public_social": ("Госуправление, образование, здравоохранение", [(84, 88)],
             dict(rate=.3, inflation=.5, input_costs=.5, fx=.3, foreign_trade=.2, logistics=.3, demand=.4, labor=.7, regulation=.85, competition=.3, tech=.4, liquidity=.3),
             ["образован", "здравоохран", "медицинск", "больниц", "школ"], [], [], .0),
    "other": ("Прочие виды деятельности", [(90, 99)],
             dict(rate=.4, inflation=.45, input_costs=.4, fx=.3, foreign_trade=.2, logistics=.3, demand=.55, labor=.5, regulation=.45, competition=.5, tech=.35, liquidity=.35),
             [], [], [], .0),
}

SECTORS = {}
for _k, (_label, _ranges, _base, _kw, _sells, _buys, _exp) in _RAW.items():
    SECTORS[_k] = {
        "key": _k, "label": _label, "ranges": _ranges, "base": _base,
        "kw": _kw, "sells": _sells, "buys": _buys, "export": _exp,
    }

def normalize_okved(code):
    """'1.11' -> '01.11', '46.71.2' stays, junk -> ''. Spreadsheet exports routinely drop the leading zero."""
    c = str(code or "").strip().replace(",", ".")
    if not c or c.lower() in ("nan", "none"):
        return ""
    head, _, tail = c.partition(".")
    if not head.isdigit():
        return ""
    return head.zfill(2) + ("." + tail if tail else "")


def sector_by_okved(code):
    """Return sector key for an OKVED code such as '24.10' or '24'. Unknown codes map to 'other'."""
    try:
        div = int(normalize_okved(code).split(".")[0])
    except (ValueError, IndexError):
        return None
    for k, s in SECTORS.items():
        for lo, hi in s["ranges"]:
            if lo <= div <= hi:
                return k
    return "other"


# Commodities sold, refined by OKVED prefix (longest prefix wins); falls back to the sector prior.
SELLS_BY_CODE = {"07.10": [], "07.2": ["nickel", "copper"], "07.29": ["gold", "copper", "nickel"], "06.10": ["oil", "gas"], "06.2": ["gas"], "05": ["coal"],
                 "19.20": ["fuel"], "24.42": ["aluminium"], "24.4": ["copper", "aluminium", "nickel"], "20.15": ["fertilizer"], "01.1": ["grain"], "01.11": ["grain"], "23.5": ["cement"], "35.1": ["electricity"],
                 "46.71": ["fuel", "oil"], "46.71.1": ["coal"], "46.72": ["steel", "aluminium", "copper", "nickel"], "46.21": ["grain"], "46.73": ["cement", "timber"], "46.75": ["chemicals", "fertilizer"],
                 "46.76": ["chemicals"], "46.46": [], "47.3": ["fuel"], "19.2": ["fuel"]}


def sells_for(okved_code, sector):
    code = normalize_okved(okved_code)
    for n in range(len(code), 0, -1):
        if code[:n] in SELLS_BY_CODE:
            return SELLS_BY_CODE[code[:n]]
    return SECTORS.get(sector, {}).get("sells", [])

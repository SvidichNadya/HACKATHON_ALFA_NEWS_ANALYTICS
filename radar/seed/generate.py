"""Synthetic dataset in the contest schema (df_Uid_data_hack.csv, df_Fid_Uid_link_hack.csv, payments)."""
import csv
import io
import math
import random

from ..knowledge.sectors import SECTORS, sector_by_okved

OKVED = {
    "agri": [("01.11", "Выращивание зерновых, зернобобовых культур и семян масличных культур"), ("01.41", "Разведение молочного крупного рогатого скота")],
    "mining_energy": [("06.10", "Добыча сырой нефти и нефтяного (попутного) газа"), ("05.10", "Добыча и обогащение угля")],
    "mining_metals": [("07.10", "Добыча и обогащение железных руд"), ("07.29", "Добыча руд прочих цветных металлов")],
    "food": [("10.51", "Производство молока и молочной продукции"), ("10.11", "Переработка и консервирование мяса")],
    "light": [("14.13", "Производство верхней одежды"), ("13.20", "Производство тканей")],
    "wood_paper": [("17.12", "Производство бумаги и картона"), ("16.10", "Распиловка и строгание древесины")],
    "refining": [("19.20", "Производство нефтепродуктов")],
    "chem_pharma": [("20.15", "Производство удобрений и азотных соединений"), ("21.20", "Производство лекарственных препаратов")],
    "build_materials": [("23.51", "Производство цемента"), ("23.61", "Производство изделий из бетона")],
    "metallurgy": [("24.10", "Производство чугуна, стали и ферросплавов"), ("25.11", "Производство строительных металлических конструкций")],
    "machinery": [("28.30", "Производство машин и оборудования для сельского и лесного хозяйства"), ("29.10", "Производство автотранспортных средств")],
    "energy_util": [("35.11", "Производство электроэнергии"), ("35.30", "Производство, передача и распределение пара и горячей воды")],
    "construction": [("41.20", "Строительство жилых и нежилых зданий"), ("42.11", "Строительство автомобильных дорог")],
    "trade": [("46.90", "Торговля оптовая неспециализированная"), ("47.11", "Торговля розничная преимущественно пищевыми продуктами"), ("46.71", "Торговля оптовая твёрдым, жидким и газообразным топливом")],
    "transport": [("49.41", "Перевозки грузов автомобильным транспортом"), ("49.20", "Перевозка грузов железнодорожным транспортом"), ("52.29", "Деятельность транспортная вспомогательная прочая")],
    "hospitality": [("55.10", "Деятельность гостиниц и прочих мест для временного проживания")],
    "it_telecom": [("62.01", "Разработка компьютерного программного обеспечения"), ("61.20", "Деятельность в области связи на базе беспроводных технологий")],
    "finance": [("64.92", "Предоставление займов и прочих видов кредита")],
    "real_estate": [("68.20", "Аренда и управление собственным или арендованным недвижимым имуществом")],
    "prof_services": [("70.22", "Консультирование по вопросам коммерческой деятельности и управления"), ("71.12", "Деятельность в области инженерных изысканий")],
}
WEIGHT = {"agri": 6, "mining_energy": 5, "mining_metals": 4, "food": 8, "light": 2, "wood_paper": 3, "refining": 2, "chem_pharma": 5, "build_materials": 3,
          "metallurgy": 8, "machinery": 8, "energy_util": 4, "construction": 9, "trade": 14, "transport": 8, "hospitality": 1, "it_telecom": 5,
          "finance": 1, "real_estate": 3, "prof_services": 3}
SUPPLIERS = {
    "agri": {"chem_pharma": 3, "refining": 3, "machinery": 3, "transport": 2, "energy_util": 1, "trade": 2},
    "mining_energy": {"machinery": 3, "energy_util": 2, "transport": 3, "prof_services": 1, "metallurgy": 2},
    "mining_metals": {"machinery": 3, "energy_util": 3, "transport": 3, "refining": 2},
    "food": {"agri": 5, "transport": 2, "energy_util": 1, "wood_paper": 1, "chem_pharma": 1},
    "light": {"chem_pharma": 2, "transport": 2, "trade": 2},
    "wood_paper": {"energy_util": 2, "transport": 3, "machinery": 1},
    "refining": {"mining_energy": 6, "transport": 2, "energy_util": 1},
    "chem_pharma": {"mining_energy": 4, "energy_util": 2, "transport": 2, "machinery": 1},
    "build_materials": {"energy_util": 3, "mining_metals": 2, "transport": 3, "refining": 1},
    "metallurgy": {"mining_metals": 5, "energy_util": 3, "transport": 3, "mining_energy": 2},
    "machinery": {"metallurgy": 5, "it_telecom": 1, "transport": 2, "energy_util": 1},
    "energy_util": {"mining_energy": 5, "machinery": 1, "prof_services": 1},
    "construction": {"build_materials": 4, "metallurgy": 4, "transport": 2, "machinery": 1, "refining": 1},
    "trade": {"food": 3, "machinery": 2, "transport": 3, "chem_pharma": 1, "light": 2, "metallurgy": 1},
    "transport": {"refining": 4, "machinery": 2, "energy_util": 1},
    "hospitality": {"food": 3, "energy_util": 1},
    "it_telecom": {"prof_services": 2, "real_estate": 2, "it_telecom": 2},
    "finance": {"it_telecom": 2, "real_estate": 1},
    "real_estate": {"construction": 3, "energy_util": 1},
    "prof_services": {"it_telecom": 2, "real_estate": 1},
}
CITIES = [("Москва", "Москва"), ("Санкт-Петербург", "Санкт-Петербург"), ("Екатеринбург", "Свердловская область"), ("Челябинск", "Челябинская область"),
          ("Краснодар", "Краснодарский край"), ("Новосибирск", "Новосибирская область"), ("Казань", "Республика Татарстан"), ("Нижний Новгород", "Нижегородская область"),
          ("Самара", "Самарская область"), ("Ростов-на-Дону", "Ростовская область"), ("Красноярск", "Красноярский край"), ("Пермь", "Пермский край"),
          ("Воронеж", "Воронежская область"), ("Тюмень", "Тюменская область"), ("Уфа", "Республика Башкортостан"), ("Кемерово", "Кемеровская область")]
COUNTRIES = ["Китай", "Турция", "Казахстан", "Беларусь", "ОАЭ", "Индия", "Узбекистан", "Армения", "Германия", "Вьетнам"]
HEADERS = ["SYNTHETIC_U", "DISPLAY_NAME", "ORG_TYPE", "OKFS_NAME", "COMPANY_AGE_YEARS_GRADATION", "ECO_MARK_LABEL", "MAINOKVED_CODE", "MAINOKVED_NAME", "NEGATIVEMARK",
           "AMOUNT_WORKERS_FNS_GRADATION", "AMOUNT_WORKERS_SPARK_GRADATION", "CL_TYPE", "CL_PRODUCT_RKO_MARK", "CL_PRODUCT_GAR_MARK", "CL_PRODUCT_LOA_MARK",
           "CL_PRODUCT_LEA_MARK", "CL_PRODUCT_DEP_MARK", "CL_PRODUCT_ZPP_MARK", "FTS_FLAG", "FTS_COUNTRY_NAME", "FACTORING_MARK", "REVENUE_COMPANY", "GROUP_ID", "CITY", "REGION"]

DEMO = {
    "metal": dict(id="U-DEMO-0001", name="Уральский металлургический холдинг", sector="metallurgy", okved=("24.10", OKVED["metallurgy"][0][1]), rev=82e9, loa=1, lea=1, gar=1, dep=0, fac=0, zpp=1,
                  fts=("Китай, Турция"), city=("Екатеринбург", "Свердловская область"), group="G-URAL-METAL", workers="5000 и более"),
    "trade": dict(id="U-DEMO-0002", name="Торговый дом «Меридиан»", sector="trade", okved=("46.90", OKVED["trade"][0][1]), rev=41e9, loa=1, lea=0, gar=1, dep=0, fac=1, zpp=0,
                  fts=("Китай, Турция"), city=("Москва", "Москва"), group="", workers="от 1000 до 5000"),
    "agro": dict(id="U-DEMO-0003", name="Агрохолдинг «Южные поля»", sector="agri", okved=("01.11", OKVED["agri"][0][1]), rev=27e9, loa=1, lea=1, gar=0, dep=0, fac=0, zpp=1,
                 fts=("Казахстан, Турция"), city=("Краснодар", "Краснодарский край"), group="", workers="от 1000 до 5000"),
    "build": dict(id="U-DEMO-0004", name="Строительная группа «Вектор»", sector="construction", okved=("41.20", OKVED["construction"][0][1]), rev=33e9, loa=1, lea=0, gar=1, dep=0, fac=0, zpp=1,
                  fts="", city=("Санкт-Петербург", "Санкт-Петербург"), group="G-VECTOR", workers="от 1000 до 5000"),
    "digital": dict(id="U-DEMO-0005", name="Цифровая платформа «Атлас»", sector="it_telecom", okved=("62.01", OKVED["it_telecom"][0][1]), rev=18e9, loa=0, lea=0, gar=0, dep=1, fac=0, zpp=1,
                    fts="", city=("Москва", "Москва"), group="", workers="от 1000 до 5000"),
    "mining": dict(id="U-DEMO-0006", name="Сибирская горнодобывающая компания", sector="mining_metals", okved=("07.29", OKVED["mining_metals"][1][1]), rev=64e9, loa=0, lea=0, gar=1, dep=1, fac=0, zpp=1,
                   fts=("Китай, ОАЭ"), city=("Красноярск", "Красноярский край"), group="", workers="от 5000"),
}
DEMO_EDGES = {  # (payer_key, beneficiary sector or key, share of payer's spend)
    "metal": [("mining_metals", .38), ("energy_util", .2), ("transport", .15), ("mining_energy", .1)],
    "trade": [("food", .2), ("machinery", .18), ("transport", .22), ("light", .1)],
    "agro": [("chem_pharma", .24), ("refining", .2), ("machinery", .2), ("transport", .12)],
    "build": [("build_materials", .24), ("metallurgy", .27), ("transport", .12), ("machinery", .08)],
    "digital": [("prof_services", .25), ("real_estate", .3), ("it_telecom", .2)],
    "mining": [("energy_util", .28), ("machinery", .24), ("transport", .2), ("refining", .15)],
}
DEMO_CUSTOMERS = {  # sector -> share of this company's incoming payments (payers)
    "metal": [("machinery", .3), ("construction", .3), ("trade", .2)], "trade": [("trade", .46), ("hospitality", .1)],
    "agro": [("food", .4), ("trade", .2), ("transport", .1)], "build": [("real_estate", .35), ("finance", .1), ("trade", .1)],
    "digital": [("finance", .3), ("trade", .2), ("machinery", .15)], "mining": [("metallurgy", .45), ("trade", .2)],
}


def _grade(workers):
    return {"до 100": "до 100", "от 100 до 1000": "от 100 до 1000", "от 1000 до 5000": "от 1000 до 5000", "5000 и более": "5000 и более", "от 5000": "5000 и более"}.get(workers, workers)


def generate(n=420, seed=26):
    rnd = random.Random(seed)
    sectors = list(WEIGHT)
    comps, by_sector = [], {k: [] for k in SECTORS}
    for key, d in DEMO.items():
        row = {"SYNTHETIC_U": d["id"], "DISPLAY_NAME": d["name"], "ORG_TYPE": "АО" if key in ("metal", "mining", "agro") else "ООО", "OKFS_NAME": "Частная собственность",
               "COMPANY_AGE_YEARS_GRADATION": "более 10 лет", "ECO_MARK_LABEL": "Зрелый бизнес", "MAINOKVED_CODE": d["okved"][0], "MAINOKVED_NAME": d["okved"][1], "NEGATIVEMARK": 0,
               "AMOUNT_WORKERS_FNS_GRADATION": _grade(d["workers"]), "AMOUNT_WORKERS_SPARK_GRADATION": _grade(d["workers"]), "CL_TYPE": "Действующий клиент",
               "CL_PRODUCT_RKO_MARK": 1, "CL_PRODUCT_GAR_MARK": d["gar"], "CL_PRODUCT_LOA_MARK": d["loa"], "CL_PRODUCT_LEA_MARK": d["lea"], "CL_PRODUCT_DEP_MARK": d["dep"],
               "CL_PRODUCT_ZPP_MARK": d["zpp"], "FTS_FLAG": 1 if d["fts"] else 0, "FTS_COUNTRY_NAME": d["fts"], "FACTORING_MARK": d["fac"], "REVENUE_COMPANY": d["rev"],
               "GROUP_ID": d["group"], "CITY": d["city"][0], "REGION": d["city"][1], "_sector": d["sector"], "_demo": key}
        comps.append(row)
        by_sector[d["sector"]].append(row)
    groups = {}
    for i in range(n):
        sk = rnd.choices(sectors, [WEIGHT[s] for s in sectors])[0]
        code, name = rnd.choice(OKVED[sk])
        rev = math.exp(rnd.gauss(math.log(24e9), .75))
        city = rnd.choice(CITIES)
        ftsc = ""
        if rnd.random() < SECTORS[sk]["export"] * .7 + .1:
            ftsc = ", ".join(rnd.sample(COUNTRIES, rnd.choice([1, 1, 2])))
        gid = ""
        if rnd.random() < .22:
            gid = f"G-{rnd.randint(1, 70):03d}"
        loa = int(rnd.random() < .55 + .2 * (rev > 2e10))
        row = {"SYNTHETIC_U": f"U-{rnd.getrandbits(40):010x}", "DISPLAY_NAME": "", "ORG_TYPE": rnd.choice(["ООО", "ООО", "АО", "ПАО"]),
               "OKFS_NAME": rnd.choice(["Частная собственность", "Частная собственность", "Смешанная российская собственность", "Иностранная собственность"]),
               "COMPANY_AGE_YEARS_GRADATION": rnd.choice(["от 3 до 5 лет", "от 5 до 10 лет", "более 10 лет", "более 10 лет"]), "ECO_MARK_LABEL": rnd.choice(["Зрелый бизнес", "Растущий бизнес", "Стабильный бизнес"]),
               "MAINOKVED_CODE": code, "MAINOKVED_NAME": name, "NEGATIVEMARK": int(rnd.random() < .08),
               "AMOUNT_WORKERS_FNS_GRADATION": rnd.choice(["от 100 до 1000", "от 1000 до 5000", "от 1000 до 5000", "5000 и более"]), "AMOUNT_WORKERS_SPARK_GRADATION": "",
               "CL_TYPE": rnd.choice(["Действующий клиент"] * 4 + ["Потенциальный клиент"]), "CL_PRODUCT_RKO_MARK": int(rnd.random() < .9), "CL_PRODUCT_GAR_MARK": int(rnd.random() < .25 + .2 * (sk == "construction")),
               "CL_PRODUCT_LOA_MARK": loa, "CL_PRODUCT_LEA_MARK": int(rnd.random() < .2), "CL_PRODUCT_DEP_MARK": int(rnd.random() < .3), "CL_PRODUCT_ZPP_MARK": int(rnd.random() < .6),
               "FTS_FLAG": int(bool(ftsc)), "FTS_COUNTRY_NAME": ftsc, "FACTORING_MARK": int(rnd.random() < (.3 if sk == "trade" else .06)), "REVENUE_COMPANY": round(rev, -6),
               "GROUP_ID": gid, "CITY": city[0], "REGION": city[1], "_sector": sk}
        comps.append(row)
        by_sector[sk].append(row)
    pay = {}

    def pick(sk, avoid):
        pool = by_sector.get(sk) or []
        pool = [c for c in pool if c["SYNTHETIC_U"] != avoid]
        if not pool:
            return None
        w = [c["REVENUE_COMPANY"] ** .6 for c in pool]
        return rnd.choices(pool, w)[0]

    for c in comps:
        sk = c["_sector"]
        spend = c["REVENUE_COMPANY"] * .55
        if c.get("_demo"):
            for tsk, share in DEMO_EDGES[c["_demo"]]:
                b = pick(tsk, c["SYNTHETIC_U"])
                if b:
                    amt = spend * share
                    pay[(c["SYNTHETIC_U"], b["SYNTHETIC_U"])] = (amt, max(3, int(amt / 4e7)))
            for tsk, share in DEMO_CUSTOMERS[c["_demo"]]:
                p = pick(tsk, c["SYNTHETIC_U"])
                if p:
                    amt = c["REVENUE_COMPANY"] * .5 * share
                    pay[(p["SYNTHETIC_U"], c["SYNTHETIC_U"])] = (amt, max(3, int(amt / 5e7)))
            if c["_demo"] == "metal":
                for m in by_sector["mining_metals"][:0]:
                    pass
        aff = SUPPLIERS.get(sk, {"trade": 1, "transport": 1})
        for _ in range(rnd.randint(5, 11)):
            tsk = rnd.choices(list(aff), list(aff.values()))[0]
            b = pick(tsk, c["SYNTHETIC_U"])
            if not b:
                continue
            amt = spend * rnd.random() ** 2.2 * .35 + 1e7
            old = pay.get((c["SYNTHETIC_U"], b["SYNTHETIC_U"]), (0, 0))
            pay[(c["SYNTHETIC_U"], b["SYNTHETIC_U"])] = (old[0] + amt, old[1] + max(1, int(amt / 3e7)))
    # group members of the metallurgical holding and the construction group
    for gid, secs, owner in (("G-URAL-METAL", ["mining_metals", "transport", "energy_util"], DEMO["metal"]["id"]), ("G-VECTOR", ["build_materials", "machinery"], DEMO["build"]["id"])):
        for sk in secs:
            m = by_sector[sk][-1]
            if gid == "G-URAL-METAL" and sk == "mining_metals":
                m["MAINOKVED_CODE"], m["MAINOKVED_NAME"] = OKVED["mining_metals"][0]
            m["GROUP_ID"] = gid
            amt = 3e9 if gid == "G-URAL-METAL" and sk == "mining_metals" else 8e8
            pay[(owner, m["SYNTHETIC_U"])] = (pay.get((owner, m["SYNTHETIC_U"]), (0, 0))[0] + amt, 120)
    persons = []
    for c in comps:
        for _ in range(rnd.randint(1, 4)):
            city = rnd.choice(CITIES)
            persons.append({"SYNTHETIC_F": f"F-{rnd.getrandbits(36):09x}", "CITY_NAME": city[0], "RC_NAME": city[1], "SYNTHETIC_U": c["SYNTHETIC_U"]})
    return comps, persons, pay


def to_csv(rows, headers):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8")


def build_files():
    comps, persons, pay = generate()
    c = to_csv(comps, HEADERS)
    p = to_csv(persons, ["SYNTHETIC_F", "CITY_NAME", "RC_NAME", "SYNTHETIC_U"])
    pr = [{"BENEFICIARY": b, "PAYER": a, "PAY_AMT": round(v[0], 2), "PAY_CNT": v[1]} for (a, b), v in pay.items()]
    return c, p, to_csv(pr, ["BENEFICIARY", "PAYER", "PAY_AMT", "PAY_CNT"]), {d["id"]: k for k, d in DEMO.items()}

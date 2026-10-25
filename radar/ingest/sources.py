"""Source authority. A prior, shown to the user as such: it moves confidence, never the facts."""
import re

OFFICIAL = re.compile(r"банк\s+росси|\bцб\b|cbr\.ru|минфин|росстат|правительств|kremlin|консультант|гарант\.ру|ФНС|ФАС|минэкономразвития|минпромторг", re.I)
WIRE = re.compile(r"интерфакс|тасс|рбк|коммерсант|ведомости|reuters|bloomberg|прайм|финмаркет|forbes|эксперт|известия|rg\.ru|cnbc", re.I)


def authority(kind, source_name, is_synthetic=False):
    if kind == "bank_analysis":
        return 0.95
    if OFFICIAL.search(source_name or ""):
        return 0.9
    if WIRE.search(source_name or ""):
        return 0.72
    return 0.55 if is_synthetic else 0.5

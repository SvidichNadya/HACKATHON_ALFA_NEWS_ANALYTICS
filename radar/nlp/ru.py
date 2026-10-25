"""Russian tokenisation and Snowball-style stemming (no external NLP dependencies)."""
import re
from functools import lru_cache

_WORD = re.compile(r"[a-zа-яё0-9]+(?:[-’'][a-zа-яё0-9]+)*", re.I)
_RVRE = re.compile(r"^(.*?[аеиоуыэюя])(.*)$")
_PERF = re.compile(r"((ив|ивши|ившись|ыв|ывши|ывшись)|((?<=[ая])(в|вши|вшись)))$")
_REFL = re.compile(r"(с[яь])$")
_ADJ = re.compile(r"(ее|ие|ые|ое|ими|ыми|ей|ий|ый|ой|ем|им|ым|ом|его|ого|ему|ому|их|ых|ую|юю|ая|яя|ою|ею)$")
_PART = re.compile(r"((ивш|ывш|ующ)|((?<=[ая])(ем|нн|вш|ющ|щ)))$")
_VERB = re.compile(
    r"((ила|ыла|ена|ейте|уйте|ите|или|ыли|ей|уй|ил|ыл|им|ым|ен|ило|ыло|ено|ят|ует|уют|ит|ыт|ены|ить|ыть|ишь|ую|ю)"
    r"|((?<=[ая])(ла|на|ете|йте|ли|й|л|ем|н|ло|но|ет|ют|ны|ть|ешь|нно)))$"
)
_NOUN = re.compile(
    r"(а|ев|ов|ие|ье|е|иями|ями|ами|еи|ии|и|ией|ей|ой|ий|й|иям|ям|ием|ем|ам|ом|о|у|ах|иях|ях|ы|ь|ию|ью|ю|ия|ья|я)$"
)
_DER = re.compile(r".*[^аеиоуыэюя]+[аеиоуыэюя].*ость?$")
_DERIV = re.compile(r"ость?$")
_SUPER = re.compile(r"(ейше|ейш)$")

STOP = frozenset(
    "и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня "
    "еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам сказал "
    "ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего "
    "раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы "
    "нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот через эти нас "
    "про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им "
    "более всегда конечно всю между также которые который которая которое которых году года год г гг млрд млн тыс руб "
    "составил составила составили сообщил сообщила сообщили заявил заявила отметил отметили свои свой".split()
)


@lru_cache(maxsize=65536)
def stem(word):
    w = word.lower().replace("ё", "е")
    if not re.search(r"[а-я]", w) or len(w) <= 3:
        return w
    m = _RVRE.match(w)
    if not m:
        return w
    head, rv = m.group(1), m.group(2)
    p = _PERF.search(rv)
    if p:
        rv = rv[: p.start()]
    else:
        rv = _REFL.sub("", rv)
        if _ADJ.search(rv):
            rv = _PART.sub("", _ADJ.sub("", rv))
        elif _VERB.search(rv):
            rv = _VERB.sub("", rv)
        else:
            rv = _NOUN.sub("", rv)
    rv = re.sub(r"и$", "", rv)
    if _DER.match(rv):
        rv = _DERIV.sub("", rv)
    if rv.endswith("нн"):
        rv = rv[:-1]
    else:
        rv = re.sub(r"ь$", "", _SUPER.sub("", rv))
    return head + rv


def tokens(text, drop_stop=True):
    out = []
    for m in _WORD.finditer(text or ""):
        t = m.group(0).lower().replace("ё", "е")
        if drop_stop and (t in STOP or len(t) < 2):
            continue
        out.append(t)
    return out


def stems(text, drop_stop=True):
    return [stem(t) for t in tokens(text, drop_stop)]


def sentences(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    parts = re.split(r"(?<=[.!?…])\s+(?=[А-ЯЁA-Z0-9«\"(])", text)
    return [p.strip() for p in parts if p.strip()]

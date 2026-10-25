"""Outbound HTTP with SSRF protection, and RSS/Atom + article extraction."""
import ipaddress
import re
import socket
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from lxml import etree, html as lhtml

from ..config import settings

MAX_BYTES = 4_000_000
UA = "AlfaBusinessRadar/1.0 (+news-intelligence)"


class FetchError(Exception):
    pass


def _check_url(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https":
        raise FetchError("Разрешены только HTTPS-адреса")
    if not u.hostname:
        raise FetchError("Некорректный адрес")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise FetchError("Адрес не разрешается: " + u.hostname) from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FetchError("Адрес указывает на внутреннюю сеть и заблокирован")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def fetch(url, accept="*/*", max_redirects=3):
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(max_redirects + 1):
        _check_url(url)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
        try:
            with opener.open(req, timeout=settings.http_timeout) as r:
                data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise FetchError("Ответ превышает допустимый размер")
                return data, r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            raise FetchError(f"HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise FetchError("Источник недоступен: " + type(e).__name__) from e
    raise FetchError("Слишком много перенаправлений")


def _text(el):
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def html_to_text(fragment):
    if not fragment:
        return ""
    try:
        doc = lhtml.fromstring("<div>" + fragment + "</div>")
        for bad in doc.xpath("//script|//style"):
            bad.drop_tree()
        return re.sub(r"\s+", " ", doc.text_content()).strip()
    except (etree.ParserError, ValueError):
        return re.sub(r"<[^>]+>", " ", fragment)


def _date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def parse_feed(data):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, recover=True)
    root = etree.fromstring(data, parser)
    if root is None:
        raise FetchError("Не удалось разобрать ленту")
    items = []
    ns = {"a": "http://www.w3.org/2005/Atom", "c": "http://purl.org/rss/1.0/modules/content/"}
    for it in root.xpath("//item"):
        items.append({
            "title": _text(it.find("title")), "url": _text(it.find("link")),
            "body": html_to_text(_text(it.find("c:encoded", ns)) or "".join(etree.tostring(x, encoding="unicode", method="text") for x in it.findall("description"))),
            "published_at": _date(_text(it.find("pubDate")) or _text(it.find("{http://purl.org/dc/elements/1.1/}date"))),
            "author": _text(it.find("author")),
        })
    for e in root.xpath("//a:entry", namespaces=ns):
        link = e.find("a:link", ns)
        items.append({
            "title": _text(e.find("a:title", ns)), "url": link.get("href") if link is not None else "",
            "body": html_to_text(_text(e.find("a:content", ns)) or _text(e.find("a:summary", ns))),
            "published_at": _date(_text(e.find("a:published", ns)) or _text(e.find("a:updated", ns))), "author": _text(e.find("a:author/a:name", ns)),
        })
    return [i for i in items if i["title"]]


def extract_article(raw_html):
    doc = lhtml.fromstring(raw_html)
    for bad in doc.xpath("//script|//style|//nav|//header|//footer|//aside|//form|//noscript"):
        bad.drop_tree()
    title = _text(doc.find(".//h1")) or _text(doc.find(".//title"))
    art = doc.xpath("//article")
    root = art[0] if art else doc
    paras = [re.sub(r"\s+", " ", p.text_content()).strip() for p in root.xpath(".//p")]
    paras = [p for p in paras if len(p) > 60]
    return title, "\n\n".join(paras)

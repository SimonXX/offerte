"""Fonte RSS 2.0 / Atom: qualunque feed, compresi quelli prodotti da RSSHub o da altri aggregatori."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlsplit

from ..config import ConfigError
from ..dedupe import text_key
from ..http import FetchError
from ..parser import Message, fragment
from . import registra
from .base import FetchContext, FetchResult, Source, parse_date, url_con_schema

RSS10 = "http://purl.org/rss/1.0/"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "rss10": RSS10,
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _rss_items(root: ET.Element) -> list[dict]:
    """RSS 2.0 e RSS 1.0: in RDF gli elementi stanno nel namespace http://purl.org/rss/1.0/."""
    out = []
    for item in [*root.iter("item"), *root.iter(f"{{{RSS10}}}item")]:
        enclosure = item.find("enclosure")
        media = item.find("media:content", NS) if item.find("media:content", NS) is not None else item.find("media:thumbnail", NS)
        image = None
        if enclosure is not None and (enclosure.get("type") or "image").startswith("image"):
            image = enclosure.get("url")
        elif media is not None:
            image = media.get("url")
        def campo(nome: str) -> str:
            return _text(item.find(nome)) or _text(item.find(f"rss10:{nome}", NS))

        out.append({
            "title": campo("title"), "link": campo("link"),
            "id": _text(item.find("guid")) or item.get(f"{{http://www.w3.org/1999/02/22-rdf-syntax-ns#}}about", ""),
            "html": _text(item.find("content:encoded", NS)) or campo("description"),
            "date": _text(item.find("pubDate")) or _text(item.find("dc:date", NS)), "image": image,
        })
    return out


def _atom_entries(root: ET.Element) -> list[dict]:
    out = []
    for e in root.findall("atom:entry", NS):
        link = ""
        for ln in e.findall("atom:link", NS):
            if ln.get("rel") in (None, "alternate"):
                link = ln.get("href") or ""
                break
        content = e.find("atom:content", NS)
        out.append({
            "title": _text(e.find("atom:title", NS)), "link": link, "id": _text(e.find("atom:id", NS)),
            "html": _text(content) if content is not None else _text(e.find("atom:summary", NS)),
            "date": _text(e.find("atom:published", NS)) or _text(e.find("atom:updated", NS)), "image": None,
        })
    return out


def parse_feed(data: bytes, source: str, now: datetime, limit: int = 50) -> list[Message]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FetchError(f"feed non valido: {e}") from None
    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in {"rss", "feed", "rdf"}:
        raise FetchError(f"non è un feed: radice <{tag}>")
    raw = _atom_entries(root) if tag == "feed" else _rss_items(root)
    messages: list[Message] = []
    for r in raw[:limit]:
        text, links, struck, image = fragment(r["html"])
        if r["title"] and r["title"] not in text:
            text = f"{r['title']}\n\n{text}".strip()
        if not text:
            continue
        all_links = ([r["link"]] if r["link"] else []) + links
        messages.append(Message(
            channel=source, id=r["id"] or r["link"] or text_key(text), date=parse_date(r["date"]) or now,
            text=text, struck=struck, links=list(dict.fromkeys(all_links)), image=r["image"] or image,
            permalink=r["link"] or "",
        ))
    return messages


def _appartiene(url: str, host: str) -> bool:
    """Vero se l'URL punta a quell'host o a un suo sottodominio."""
    try:
        h = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return h == host or h.endswith("." + host)


@registra
class RssSource(Source):
    tipo = "rss"
    chiavi = frozenset({"url", "url_env", "massimo", "scarta_host"})

    def configura(self) -> None:
        url = self.opzione("url")
        self.url_env = self.opzione("url_env")
        if bool(url) == bool(self.url_env):
            raise ConfigError(f"fonte '{self.nome}' (rss): serve 'url' oppure 'url_env', non entrambi")
        self.url = url_con_schema(self, str(url)) if url else None
        self.scarta_host = str(self.opzione("scarta_host") or "").strip().lower().lstrip(".") or None

    def indirizzo(self) -> str:
        """L'URL del feed. Con `url_env` si rilegge a ogni giro, così il token non sta in config."""
        if self.url:
            return self.url
        valore = os.environ.get(str(self.url_env), "")
        if not valore.strip():
            raise FetchError(f"fonte '{self.nome}' (rss): la variabile {self.url_env} non è impostata")
        return valore.strip()

    def fetch(self, ctx: FetchContext) -> FetchResult:
        url = self.indirizzo()
        resp = ctx.client.get(url, nome=self.nome if self.url_env else None)
        items = parse_feed(resp.content, self.nome, ctx.now, int(self.opzione("massimo") or 50))
        if self.scarta_host:
            # L'identificativo di un feed privato sta nei suoi link: non deve finire nei feed pubblicati.
            for m in items:
                m.links = [u for u in m.links if not _appartiene(u, self.scarta_host)]
                if m.permalink and _appartiene(m.permalink, self.scarta_host):
                    m.permalink = ""
                if m.image and _appartiene(m.image, self.scarta_host):
                    m.image = None
        return FetchResult(items)

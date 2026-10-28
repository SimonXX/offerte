"""Fonte RSS 2.0 / Atom: qualunque feed, compresi quelli prodotti da RSSHub o da altri aggregatori."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from ..dedupe import text_key
from ..http import FetchError
from ..parser import Message, fragment
from . import registra
from .base import FetchContext, FetchResult, Source, parse_date

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _rss_items(root: ET.Element) -> list[dict]:
    out = []
    for item in root.iter("item"):
        enclosure = item.find("enclosure")
        media = item.find("media:content", NS) if item.find("media:content", NS) is not None else item.find("media:thumbnail", NS)
        image = None
        if enclosure is not None and (enclosure.get("type") or "image").startswith("image"):
            image = enclosure.get("url")
        elif media is not None:
            image = media.get("url")
        out.append({
            "title": _text(item.find("title")), "link": _text(item.find("link")),
            "id": _text(item.find("guid")), "html": _text(item.find("content:encoded", NS)) or _text(item.find("description")),
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
    raw = _atom_entries(root) if root.tag.endswith("feed") else _rss_items(root)
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


@registra
class RssSource(Source):
    tipo = "rss"
    chiavi = frozenset({"url", "massimo"})

    def configura(self) -> None:
        self.url = str(self.opzione("url", obbligatoria=True))

    def fetch(self, ctx: FetchContext) -> FetchResult:
        resp = ctx.client.get(self.url)
        return FetchResult(parse_feed(resp.content, self.nome, ctx.now, int(self.opzione("massimo") or 50)))

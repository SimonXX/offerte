"""Feed RSS 2.0 e JSON Feed per cartella e per regola, scritti in var/feeds/."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from feedgen.feed import FeedGenerator

from .config import Config
from .store import Offer, Store

MIME = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "feed"


def fmt_price(price: float) -> str:
    """1299.5 -> '1.299,50€'."""
    return f"{price:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".") + "€"


def item_title(o: Offer) -> str:
    title = o.title or o.text.splitlines()[0][:80]
    if o.price is not None:
        title += f", {fmt_price(o.price)}"
    if o.discount:
        title += f" (-{o.discount}%)"
    return title


def item_html(o: Offer) -> str:
    e = html.escape
    parts = []
    if o.image:
        parts.append(f'<p><img src="{e(o.image)}" alt=""></p>')
    parts.append("<p>" + e(o.text).replace("\n", "<br>") + "</p>")
    dettagli = []
    if o.price is not None:
        dettagli.append(f"Prezzo: {fmt_price(o.price)}")
    if o.old_price is not None:
        dettagli.append(f"prima {fmt_price(o.old_price)}")
    if o.discount:
        dettagli.append(f"sconto {o.discount}%")
    if o.coupon:
        dettagli.append(f"coupon {e(o.coupon)}")
    if dettagli:
        parts.append("<p>" + " · ".join(dettagli) + "</p>")
    parts.append(f"<p>Canali: {e(', '.join(o.channels))}</p>")
    voci = []
    if o.link:
        voci.append(f'<a href="{e(o.link)}">Vai all\'offerta</a>')
    if o.permalink and o.permalink != o.link:
        voci.append(f'<a href="{e(o.permalink)}">Messaggio originale</a>')
    if voci:
        parts.append("<p>" + " · ".join(voci) + "</p>")
    return "\n".join(parts)


def rss_bytes(title: str, self_url: str, home_url: str, offers: list[Offer], now: datetime) -> bytes:
    fg = FeedGenerator()
    fg.title(title)
    fg.link(href=self_url, rel="self")
    fg.link(href=home_url, rel="alternate")
    fg.description(title)
    fg.language("it")
    fg.lastBuildDate(now)
    fg.generator("offerte")
    for o in offers:
        fe = fg.add_entry(order="append")
        fe.guid(f"urn:offerte:{o.id}", permalink=False)
        fe.title(item_title(o))
        fe.link(href=o.link or o.permalink)
        fe.description(item_html(o))
        fe.pubDate(datetime.fromisoformat(o.posted_at))
        fe.category([{"term": c} for c in o.channels])
        if o.image:
            fe.enclosure(url=o.image, length="0", type=MIME.get(Path(o.image).suffix.lower(), "image/jpeg"))
    return fg.rss_str(pretty=True)


def json_bytes(title: str, self_url: str, home_url: str, offers: list[Offer]) -> bytes:
    items = []
    for o in offers:
        item = {
            "id": f"urn:offerte:{o.id}",
            "url": o.link or o.permalink,
            "title": item_title(o),
            "content_html": item_html(o),
            "content_text": o.text,
            "date_published": o.posted_at,
            "tags": o.channels,
            "_offerte": {
                "prezzo": o.price, "prezzo_barrato": o.old_price, "sconto": o.discount, "coupon": o.coupon,
                "canali": o.channels, "messaggio": o.permalink,
            },
        }
        if o.image:
            item["image"] = o.image
        items.append(item)
    feed = {"version": "https://jsonfeed.org/version/1.1", "title": title, "home_page_url": home_url,
            "feed_url": self_url, "language": "it", "items": items}
    return json.dumps(feed, ensure_ascii=False, indent=1).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _index_html(entries: list[tuple[str, str, int]], base_url: str, now: datetime) -> str:
    e = html.escape
    sezioni = {"cartella": "Cartelle", "regola": "Regole"}
    out = ["<!doctype html><html lang='it'><head><meta charset='utf-8'><title>Feed offerte</title>",
           "<style>body{font-family:sans-serif;max-width:40em;margin:2em auto;padding:0 1em}li{margin:.3em 0}</style>",
           "</head><body><h1>Feed offerte</h1>"]
    for group, label in sezioni.items():
        out.append(f"<h2>{label}</h2><ul>")
        for g, name, n in entries:
            if g != group:
                continue
            s = slug(name)
            out.append(f"<li>{e(name)} · <a href='{base_url}/{group}/{s}.xml'>RSS</a>"
                       f" · <a href='{base_url}/{group}/{s}.json'>JSON</a> · {n} offerte</li>")
        out.append("</ul>")
    out.append(f"<p><small>aggiornato {now.astimezone().strftime('%Y-%m-%d %H:%M')}</small></p></body></html>")
    return "".join(out)


def write_feeds(store: Store, config: Config, now: datetime) -> list[tuple[str, str, int]]:
    """Scrive tutti i feed e la pagina indice; rimuove i feed di cartelle o regole non più in config."""
    p = config.parametri
    base = p.var_dir / "feeds"
    since = (now - timedelta(days=p.feed_giorni)).isoformat(timespec="seconds")
    home_url = p.feed_base_url + "/"
    written: list[tuple[str, str, int]] = []
    keep: set[Path] = set()

    def emit(group: str, name: str, title: str, offers: list[Offer]) -> None:
        folder = base / group
        folder.mkdir(parents=True, exist_ok=True)
        s = slug(name)
        for ext, make in (("xml", lambda u: rss_bytes(title, u, home_url, offers, now)),
                          ("json", lambda u: json_bytes(title, u, home_url, offers))):
            path = folder / f"{s}.{ext}"
            _atomic_write(path, make(f"{p.feed_base_url}/{group}/{s}.{ext}"))
            keep.add(path)
        written.append((group, name, len(offers)))

    for cartella, canali in sorted(config.cartelle().items()):
        emit("cartella", cartella, f"Offerte {cartella}", store.offers_for_channels(canali, since, p.feed_max_elementi))
    for rule in config.regole:
        emit("regola", rule.nome, f"Alert {rule.nome}", store.offers_for_rule(rule.nome, since, p.feed_max_elementi))
    for stale in base.glob("*/*"):
        if stale.suffix in (".xml", ".json") and stale not in keep:
            stale.unlink()
    _atomic_write(base / "index.html", _index_html(written, p.feed_base_url, now).encode("utf-8"))
    return written

"""Feed RSS 2.0 e JSON Feed per cartella e per regola, scritti in var/feeds/."""

from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from feedgen.feed import FeedGenerator

from .config import Config
from .store import Offer, Store

log = logging.getLogger(__name__)

MIME = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
STATIC = Path(__file__).parent / "static"
DASHBOARD_VERSIONE = 1
DASHBOARD_ASSET = ("dashboard.html", "dashboard.css", "filtri.js", "dashboard.js")
ASIN_CHIAVE_RE = re.compile(r"^url:amazon\.[a-z.]+/dp/([A-Z0-9]{10})$")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "feed"


def fmt_price(price: float) -> str:
    """1299.5 -> '1.299,50€'."""
    return f"{price:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".") + "€"


def safe_url(u: str | None) -> str | None:
    """Solo http e https: un `javascript:` o un `data:` nella pagina sarebbe un vettore di XSS."""
    if not u:
        return None
    try:
        schema = urlsplit(u).scheme.lower()
    except ValueError:
        return None
    return u if schema in ("http", "https") else None


def item_name(o: Offer) -> str:
    """Nome del prodotto senza prezzo: il titolo estratto, altrimenti la prima riga del testo."""
    return o.title or (o.text.splitlines() or [""])[0][:80] or "(senza titolo)"


def item_title(o: Offer) -> str:
    title = item_name(o)
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


def _epoch(iso: str) -> int | None:
    """Secondi epoch UTC da una data ISO del database; una data senza fuso si legge come UTC."""
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp())


def dashboard_cartelle(config: Config) -> dict[str, list[str]]:
    """Cartella (minuscola) -> fonti, anche quelle inattive: le regole `canali: [cartella]` le includono."""
    per_cartella: dict[str, set[str]] = {}
    for f in config.fonti:
        per_cartella.setdefault(f.cartella.lower(), set()).add(f.nome)
    return {cartella: sorted(nomi) for cartella, nomi in sorted(per_cartella.items())}


def dashboard_regole(config: Config) -> list[dict]:
    """Le regole come sono scritte in config, anche le spente: la pagina le mostra come preset dormienti."""
    out = []
    for r in config.regole:
        voce: dict = {"nome": r.nome, "slug": slug(r.nome), "parole": list(r.parole_src),
                      "escludi": list(r.escludi_src), "canali": list(r.canali_src),
                      "tutte": r.tutte, "solo_coupon": r.solo_coupon, "attiva": r.attiva}
        if r.prezzo_min is not None:
            voce["prezzo_min"] = r.prezzo_min
        if r.prezzo_max is not None:
            voce["prezzo_max"] = r.prezzo_max
        if r.sconto_min is not None:
            voce["sconto_min"] = r.sconto_min
        out.append(voce)
    return out


def dashboard_fonti(config: Config, store: Store) -> list[dict]:
    """Stato di ogni fonte, nell'ordine di config: serve al riquadro «Fonti» della pagina."""
    out = []
    for f in config.fonti:
        st = store.channel_state(f.nome)
        voce: dict = {"nome": f.nome, "cartella": f.cartella.lower(), "ogni": int(f.ogni or 0),
                      "attiva": bool(f.attivo)}
        quando = _epoch(st.last_fetch) if st.last_fetch else None
        if quando is not None:
            voce["ultimo_fetch"] = quando
        if st.last_status:
            voce["stato"] = st.last_status
        out.append(voce)
    return out


def dashboard_offerta(o: Offer) -> dict:
    """Un'offerta nel formato compatto del contratto: i campi assenti si omettono, mai `null`."""
    voce: dict = {"id": o.id, "t": _epoch(o.posted_at) or 0, "n": item_name(o), "x": o.text, "k": list(o.channels)}
    if o.price is not None:
        voce["p"] = o.price
    if o.old_price is not None:
        voce["b"] = o.old_price
    if o.discount is not None:
        voce["s"] = o.discount
    if o.coupon:
        voce["c"] = o.coupon
    offerta_url = safe_url(o.link) or safe_url(o.permalink)
    if offerta_url:
        voce["u"] = offerta_url
    messaggio = safe_url(o.permalink)
    if messaggio and messaggio != offerta_url:
        voce["m"] = messaggio
    immagine = safe_url(o.image)
    if immagine:
        voce["i"] = immagine
    asin = ASIN_CHIAVE_RE.match(o.key or "")
    if asin:
        voce["a"] = asin.group(1)  # serve al grafico dello storico prezzi, caricato a richiesta
    return voce


def dashboard_bytes(offers: list[Offer], cartelle: dict[str, list[str]], regole: list[dict], fonti: list[dict],
                    now: datetime, giorni: int, max_offerte: int = 10000, grafico: str = "",
                    condividi: str = "", predefinite: tuple[str, ...] = (), nuova_regola: str = "") -> bytes:
    """Il documento `dashboard.json`. Pura: niente disco, niente store, così si prova a mano."""
    ordinate = sorted(offers, key=lambda o: (_epoch(o.posted_at) or 0, o.id), reverse=True)
    doc = {
        "v": DASHBOARD_VERSIONE,
        "generato": int(now.timestamp()),
        "finestra_giorni": giorni,
        "troncato": len(ordinate) > max_offerte,
        "cartelle": cartelle,
        "regole": regole,
        "fonti": fonti,
        "offerte": [dashboard_offerta(o) for o in ordinate[:max_offerte]],
    }
    if grafico:
        doc["grafico"] = grafico
    if condividi:
        doc["condividi"] = condividi
    if nuova_regola:
        doc["nuova_regola"] = nuova_regola  # base del pulsante che apre l'editor di GitHub gia' compilato
    note = [c for c in predefinite if c in cartelle]
    if note:
        doc["predefinite"] = note  # cartelle spuntate all'apertura, se il link non dice altro
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _copia_se_diverso(sorgente: Path, destinazione: Path) -> None:
    dati = sorgente.read_bytes()
    if destinazione.exists() and destinazione.read_bytes() == dati:
        return
    _atomic_write(destinazione, dati)


def write_dashboard(store: Store, config: Config, now: datetime) -> int:
    """Scrive `dashboard.json` e i quattro file statici. Torna il numero di offerte scritte."""
    p = config.parametri
    base = p.var_dir / "feeds"
    base.mkdir(parents=True, exist_ok=True)
    if not p.dashboard:
        for nome in (*DASHBOARD_ASSET, "dashboard.json"):
            (base / nome).unlink(missing_ok=True)
        return 0
    giorni = p.dashboard_giorni or p.feed_giorni  # la pagina può guardare più indietro dei feed
    since = (now - timedelta(days=giorni)).isoformat(timespec="seconds")
    offers = store.offers_since(since)
    dati = dashboard_bytes(
        offers, dashboard_cartelle(config), dashboard_regole(config) if p.dashboard_regole else [],
        dashboard_fonti(config, store), now, giorni, p.dashboard_max_offerte, p.grafico_prezzi,
        p.condividi_url, p.dashboard_cartelle, p.regole_url)
    for nome in DASHBOARD_ASSET:
        _copia_se_diverso(STATIC / nome, base / nome)
    _atomic_write(base / "dashboard.json", dati)  # per ultimo: la pagina non deve mai leggere dati più vecchi di sé
    return min(len(offers), p.dashboard_max_offerte)


def _opml(entries: list[tuple[str, str, int]], base_url: str, now: datetime) -> str:
    """Tutti i feed in un file solo, da importare in Miniflux, Inoreader o FreshRSS."""
    e = html.escape
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<opml version="2.0">',
           f"<head><title>Feed offerte</title><dateCreated>{now.astimezone(timezone.utc):%a, %d %b %Y %H:%M:%S} GMT"
           "</dateCreated></head>", "<body>"]
    for group, label in (("cartella", "Cartelle"), ("regola", "Regole")):
        out.append(f'<outline text="{label}" title="{label}">')
        for g, name, _ in entries:
            if g != group:
                continue
            s = slug(name)
            out.append(f'<outline type="rss" text="{e(name)}" title="{e(name)}"'
                       f' xmlUrl="{e(base_url)}/{group}/{s}.xml" htmlUrl="{e(base_url)}/"/>')
        out.append("</outline>")
    out.append("</body></opml>")
    return "\n".join(out)


def _index_html(entries: list[tuple[str, str, int]], base_url: str, now: datetime,
                con_dashboard: bool = False) -> str:
    e = html.escape
    sezioni = {"cartella": "Cartelle", "regola": "Regole"}
    out = ["<!doctype html><html lang='it'><head><meta charset='utf-8'><title>Feed offerte</title>",
           "<style>body{font-family:sans-serif;max-width:40em;margin:2em auto;padding:0 1em}li{margin:.3em 0}</style>",
           "</head><body><h1>Feed offerte</h1>"]
    if con_dashboard:
        out.append("<p><a href='dashboard.html'>Dashboard</a></p>")
    for group, label in sezioni.items():
        out.append(f"<h2>{label}</h2><ul>")
        for g, name, n in entries:
            if g != group:
                continue
            s = slug(name)
            out.append(f"<li>{e(name)} · <a href='{base_url}/{group}/{s}.xml'>RSS</a>"
                       f" · <a href='{base_url}/{group}/{s}.json'>JSON</a> · {n} offerte</li>")
        out.append("</ul>")
    out.append("<p><a href='feeds.opml'>Tutti i feed in un file OPML</a></p>")
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
    for rule in config.regole_attive():
        emit("regola", rule.nome, f"Alert {rule.nome}", store.offers_for_rule(rule.nome, since, p.feed_max_elementi))
    for gruppo in ("cartella", "regola"):  # solo le cartelle dei feed: dashboard.json sta nella radice
        for stale in (base / gruppo).glob("*"):
            if stale.suffix in (".xml", ".json") and stale not in keep:
                stale.unlink()
    _atomic_write(base / "feeds.opml", _opml(written, p.feed_base_url, now).encode("utf-8"))
    _atomic_write(base / "index.html",
                  _index_html(written, p.feed_base_url, now, con_dashboard=p.dashboard).encode("utf-8"))
    try:
        write_dashboard(store, config, now)
    except Exception:  # la dashboard non deve fermare feed, notifiche e salvataggio dello stato
        log.exception("dashboard: scrittura fallita")
    return written

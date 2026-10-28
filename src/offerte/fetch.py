"""Un giro di raccolta: canali, estrazione, dedupe, regole, notifiche, feed."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from . import links as L
from .config import Config
from .dedupe import offer_key
from .extract import extract
from .feeds import write_feeds
from .http import Client, FetchError
from .notify import Notifier
from .parser import Message, parse_page
from .rules import apply_rules
from .store import Store

log = logging.getLogger(__name__)
BASE_URL = "https://t.me/s"


class NoPreview(Exception):
    pass


@dataclass
class RunSummary:
    ok: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    new_posts: int = 0
    new_offers: list[int] = field(default_factory=list)
    matches: dict[str, int] = field(default_factory=dict)
    notified: int = 0
    feeds: list[tuple[str, str, int]] = field(default_factory=list)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def fetch_channel_messages(client: Client, channel: str, *, last_id: int, max_pages: int) -> tuple[list[Message], int]:
    """Legge t.me/s/<canale> dalla pagina più recente indietro (?before=) finché trova id già noti o esaurisce le pagine.

    Torna i messaggi nuovi e l'id più alto visto nella pagina più recente.
    """
    out: list[Message] = []
    before: int | None = None
    max_seen = last_id
    for _ in range(max_pages):
        url = f"{BASE_URL}/{channel}" + (f"?before={before}" if before else "")
        resp = client.get(url)
        if not urlsplit(str(resp.url)).path.startswith("/s/"):
            raise NoPreview  # t.me/s/<canale> rimanda a t.me/<canale>: niente anteprima pubblica
        page = parse_page(resp.text, channel)
        if not page.has_preview:
            raise NoPreview
        if not page.ids:
            break
        max_seen = max(max_seen, *page.ids)
        out.extend(m for m in page.messages if m.id > last_id)
        min_id = min(page.ids)
        if min_id <= last_id or (before is not None and min_id >= before):
            break
        before = min_id
    return out, max_seen


def resolve_link(store: Store, client: Client, url: str, now: str) -> str:
    if not L.is_short_link(url):
        return url
    cached = store.get_redirect(url)
    if cached:
        return cached
    resolved = client.resolve(url)
    if resolved != url:
        store.set_redirect(url, resolved, now)
    return resolved


def process_message(store: Store, client: Client, m: Message, *, now: str, dedupe_since: str) -> tuple[int, bool]:
    """Inserisce o aggrega il messaggio. Torna (id offerta, True se l'offerta è nuova)."""
    raw_link = L.pick_offer_link(m.links)
    link = L.clean_url(resolve_link(store, client, raw_link, now)) if raw_link else None
    key = offer_key(link, m.text)
    posted_at = iso(m.date)
    existing = store.find_offer(key, dedupe_since)
    if existing:
        store.touch_offer(existing.id, m.channel, now)
        offer_id, created = existing.id, False
    else:
        ex = extract(m.text, m.struck)
        image = m.image or next((L.normalize_input(u) for u in m.links if L.is_image_url(u)), None)
        offer_id = store.insert_offer(
            key=key, title=ex.title, text=m.text, link=link, permalink=m.permalink, image=image,
            price=ex.price, old_price=ex.old_price, discount=ex.discount, coupon=ex.coupon,
            posted_at=posted_at, channel=m.channel, now=now)
        created = True
    store.add_post(m.channel, m.id, offer_id, posted_at, m.permalink)
    return offer_id, created


def run_fetch(config: Config, store: Store, client: Client, notifier: Notifier | None = None, *,
              only: str | None = None, pages: int | None = None, now: datetime | None = None) -> RunSummary:
    now_dt = now or datetime.now(timezone.utc)
    now_s = iso(now_dt)
    p = config.parametri
    s = RunSummary()
    dedupe_since = iso(now_dt - timedelta(days=p.giorni_dedupe))

    for ch in config.canali_attivi():
        if only and ch.nome != only:
            continue
        last_id, _ = store.channel_state(ch.nome)
        try:
            msgs, max_seen = fetch_channel_messages(client, ch.nome, last_id=last_id, max_pages=pages or p.pagine_storico)
        except NoPreview:
            log.warning("canale %s: nessuna anteprima pubblica su t.me/s, saltato", ch.nome)
            store.update_channel(ch.nome, status="no_preview", now=now_s, error="nessuna anteprima pubblica")
            s.skipped.append(ch.nome)
            continue
        except FetchError as e:
            log.error("canale %s: %s", ch.nome, e)
            store.update_channel(ch.nome, status="error", now=now_s, error=str(e)[:500])
            s.failed[ch.nome] = str(e)
            continue
        except Exception as e:  # un canale che fallisce non blocca gli altri
            log.exception("canale %s: errore inatteso", ch.nome)
            store.update_channel(ch.nome, status="error", now=now_s, error=f"{type(e).__name__}: {e}"[:500])
            s.failed[ch.nome] = f"{type(e).__name__}: {e}"
            continue

        nuove = 0
        for m in sorted(msgs, key=lambda x: x.id):
            if store.post_exists(ch.nome, m.id):
                continue
            try:
                offer_id, created = process_message(store, client, m, now=now_s, dedupe_since=dedupe_since)
            except Exception:  # un messaggio malformato non ferma il canale
                log.exception("canale %s, messaggio %s: scartato", ch.nome, m.id)
                continue
            s.new_posts += 1
            if created:
                s.new_offers.append(offer_id)
                nuove += 1
        store.update_channel(ch.nome, status="ok", now=now_s, last_id=max_seen, bootstrapped=True)
        s.ok.append(ch.nome)
        log.info("canale %s: %d messaggi nuovi, %d offerte nuove", ch.nome, len(msgs), nuove)

    window = iso(now_dt - timedelta(days=p.feed_giorni))
    new_matches = apply_rules(store, config.regole, since=window, now=now_s)
    for rules in new_matches.values():
        for r in rules:
            s.matches[r.nome] = s.matches.get(r.nome, 0) + 1

    if notifier is not None:
        fresh = set(s.new_offers)
        min_posted = iso(now_dt - timedelta(hours=p.notifica_max_ore))
        for offer_id, rules in new_matches.items():
            da_notificare = [r.nome for r in rules if r.notify]
            if offer_id not in fresh or not da_notificare or store.is_notified(offer_id):
                continue
            offer = store.get_offer(offer_id)
            if offer.posted_at < min_posted:
                continue
            if notifier.send(offer, da_notificare):
                store.mark_notified(offer_id, now_s)
                s.notified += 1

    s.feeds = write_feeds(store, config, now_dt)
    log.info("fine giro: canali ok %d, saltati %d, falliti %d; post nuovi %d, offerte nuove %d, regole scattate %s, notifiche %d",
             len(s.ok), len(s.skipped), len(s.failed), s.new_posts, len(s.new_offers), s.matches or "nessuna", s.notified)
    return s

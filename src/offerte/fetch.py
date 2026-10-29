"""Un giro di raccolta: canali, estrazione, dedupe, regole, notifiche, feed."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from . import links as L
from .config import Config
from .dedupe import offer_key
from .extract import extract
from .feeds import write_feeds
from .http import Client, FetchError
from .notify import Notifier
from .parser import Message
from .rules import apply_rules
from .sources.base import FetchContext, Source
from .sources.telegram import NoPreview
from .store import SourceState, Store

log = logging.getLogger(__name__)

# Un ripost dello stesso link a un prezzo almeno cosi' piu' basso e' un'offerta nuova, non un duplicato:
# e' proprio il ribasso l'evento che interessa, e le regole lo vedono solo se nasce una riga nuova.
RIBASSO_MINIMO = 0.05
MAX_NOTIFICHE_PER_GIRO = 30


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


def is_due(source: Source, state: SourceState, now: datetime) -> bool:
    """Una fonte con `ogni: N` (minuti) si rilegge solo quando sono passati N minuti dall'ultimo fetch."""
    if not source.ogni or not state.last_fetch:
        return True
    return datetime.fromisoformat(state.last_fetch) + timedelta(minutes=source.ogni) <= now


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


def is_ribasso(vecchio: float | None, nuovo: float | None) -> bool:
    """Vero se il prezzo nuovo è inferiore al precedente di almeno RIBASSO_MINIMO."""
    if vecchio is None or nuovo is None:
        return False
    return nuovo <= vecchio * (1 - RIBASSO_MINIMO)


def process_message(store: Store, client: Client, m: Message, *, now: str, dedupe_since: str) -> tuple[int, bool]:
    """Inserisce o aggrega il messaggio. Torna (id offerta, True se l'offerta è nuova)."""
    raw_link = L.pick_offer_link(m.links)
    try:
        link = L.clean_url(resolve_link(store, client, raw_link, now)) if raw_link else None
    except ValueError:  # URL malformato: il messaggio resta, senza link, con la chiave calcolata dal testo
        log.warning("fonte %s, elemento %s: link inutilizzabile, resta il solo testo", m.channel, m.id)
        link = None
    key = offer_key(link, m.text)
    posted_at = iso(m.date)
    ex = extract(m.text, m.struck)
    price = m.price if m.price is not None else ex.price
    old_price = m.old_price if m.old_price is not None else ex.old_price
    discount = ex.discount
    if (m.price is not None or m.old_price is not None) and price and old_price and old_price > price:
        discount = round((1 - price / old_price) * 100) or None
    existing = store.find_offer(key, dedupe_since)
    if existing is not None and not is_ribasso(existing.price, price):
        store.touch_offer(existing.id, m.channel, now)
        offer_id, created = existing.id, False
    else:
        image = m.image or next((L.normalize_input(u) for u in m.links if L.is_image_url(u)), None)
        offer_id = store.insert_offer(
            key=key, title=ex.title, text=m.text, link=link, permalink=m.permalink or link or "", image=image,
            price=price, old_price=old_price, discount=discount, coupon=ex.coupon,
            posted_at=posted_at, channel=m.channel, now=now)
        created = True
    store.add_post(m.channel, m.id, offer_id, posted_at, m.permalink or link or "")
    return offer_id, created


def run_fetch(config: Config, store: Store, client: Client, notifier: Notifier | None = None, *,
              only: str | None = None, pages: int | None = None, now: datetime | None = None) -> RunSummary:
    now_dt = now or datetime.now(timezone.utc)
    now_s = iso(now_dt)
    p = config.parametri
    s = RunSummary()
    dedupe_since = iso(now_dt - timedelta(days=p.giorni_dedupe))

    for fonte in config.fonti_attive():
        if only and fonte.nome != only:
            continue
        state = store.channel_state(fonte.nome)
        if not is_due(fonte, state, now_dt):
            log.debug("fonte %s: non ancora scaduto l'intervallo di %d minuti", fonte.nome, fonte.ogni)
            continue
        ctx = FetchContext(client=client, store=store, now=now_dt, state=state,
                           pages=pages or p.pagine_storico, config_dir=config.path.parent)
        try:
            result = fonte.fetch(ctx)
        except NoPreview:
            log.warning("fonte %s: nessuna anteprima pubblica su t.me/s, saltata", fonte.nome)
            store.update_channel(fonte.nome, status="no_preview", now=now_s, error="nessuna anteprima pubblica")
            s.skipped.append(fonte.nome)
            continue
        except FetchError as e:
            log.error("fonte %s: %s", fonte.nome, e)
            store.update_channel(fonte.nome, status="error", now=now_s, error=str(e)[:500])
            s.failed[fonte.nome] = str(e)
            continue
        except Exception as e:  # una fonte che fallisce non blocca le altre
            log.exception("fonte %s: errore inatteso", fonte.nome)
            store.update_channel(fonte.nome, status="error", now=now_s, error=f"{type(e).__name__}: {e}"[:500])
            s.failed[fonte.nome] = f"{type(e).__name__}: {e}"
            continue

        nuove = 0
        for m in sorted(result.items, key=lambda x: (x.date, str(x.id))):
            if store.post_exists(fonte.nome, m.id):
                continue
            try:
                offer_id, created = process_message(store, client, m, now=now_s, dedupe_since=dedupe_since)
            except Exception:  # un messaggio malformato non ferma la fonte
                log.exception("fonte %s, elemento %s: scartato", fonte.nome, m.id)
                continue
            s.new_posts += 1
            if created:
                s.new_offers.append(offer_id)
                nuove += 1
                if m.date == now_dt and not state.bootstrapped:
                    # Data di ripiego al primo giro di una fonte: non sappiamo quando è stata pubblicata,
                    # quindi la segniamo come già notificata invece di mandarne una raffica.
                    store.mark_notified(offer_id, now_s)
        stato_fonte = "vuota" if result.vuota else "ok"
        store.update_channel(fonte.nome, status=stato_fonte, now=now_s, last_id=result.last_id, bootstrapped=True)
        s.ok.append(fonte.nome)
        log.info("fonte %s: %d elementi nuovi, %d offerte nuove", fonte.nome, len(result.items), nuove)

    window = iso(now_dt - timedelta(days=p.feed_giorni))
    new_matches = apply_rules(store, config.regole, since=window, now=now_s)
    for rules in new_matches.values():
        for r in rules:
            s.matches[r.nome] = s.matches.get(r.nome, 0) + 1

    if notifier is not None:
        nomi_notify = [r.nome for r in config.regole if r.notify]
        min_posted = iso(now_dt - timedelta(hours=p.notifica_max_ore))
        in_coda = store.pending_notifications(nomi_notify, min_posted)
        for offer, regole_scattate in in_coda[:MAX_NOTIFICHE_PER_GIRO]:
            if notifier.send(offer, regole_scattate):
                store.mark_notified(offer.id, now_s)
                s.notified += 1
        restanti = len(in_coda) - MAX_NOTIFICHE_PER_GIRO
        if restanti > 0:
            log.info("notifiche: %d restano in coda per il prossimo giro (tetto di %d per giro)",
                     restanti, MAX_NOTIFICHE_PER_GIRO)

    if p.giorni_ritenzione > 0:
        tolte = store.purge(iso(now_dt - timedelta(days=p.giorni_ritenzione)))
        if tolte:
            log.info("ritenzione: tolte %d offerte più vecchie di %d giorni", tolte, p.giorni_ritenzione)
    s.feeds = write_feeds(store, config, now_dt)
    log.info("fine giro: fonti ok %d, saltate %d, fallite %d; post nuovi %d, offerte nuove %d, regole scattate %s, notifiche %d",
             len(s.ok), len(s.skipped), len(s.failed), s.new_posts, len(s.new_offers), s.matches or "nessuna", s.notified)
    return s

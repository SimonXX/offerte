"""Fonte Telegram: anteprima pubblica https://t.me/s/<canale>, paginata con ?before=<id>."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from ..http import Client
from ..parser import Message, parse_page
from . import registra
from .base import FetchContext, FetchResult, Source

log = logging.getLogger(__name__)

BASE_URL = "https://t.me/s"
# Nei giri incrementali il ciclo si ferma al primo id noto, quindi un tetto alto non costa nulla nel caso
# normale e serve solo a recuperare dopo una pausa lunga (macchina spenta, cron fermo).
PAGINE_INCREMENTALI = 30


class NoPreview(Exception):
    pass


def fetch_channel_messages(client: Client, channel: str, *, last_id: int, max_pages: int) -> tuple[list[Message], int]:
    """Legge dalla pagina più recente indietro finché trova id già noti o esaurisce le pagine.

    Torna i messaggi nuovi e l'id più alto visto.
    """
    out: list[Message] = []
    before: int | None = None
    max_seen = last_id
    min_letto: int | None = None
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
        min_letto = min_id if min_letto is None else min(min_letto, min_id)
        if min_id <= last_id or (before is not None and min_id >= before):
            break
        before = min_id
    else:  # pagine esaurite senza incontrare un id noto: in mezzo possono esserci messaggi mai letti
        if last_id and min_letto is not None and min_letto > last_id + 1:
            log.warning("canale %s: pagine esaurite al id %d con ultimo noto %d, fino a %d messaggi saltati",
                        channel, min_letto, last_id, min_letto - last_id - 1)
    return out, max_seen


@registra
class TelegramSource(Source):
    tipo = "telegram"
    chiavi = frozenset({"canale", "pagine"})

    def configura(self) -> None:
        self.canale = str(self.opzione("canale") or self.nome).strip().lstrip("@").lower()

    def fetch(self, ctx: FetchContext) -> FetchResult:
        scelte = self.opzione("pagine")
        pagine = int(scelte) if scelte else (
            ctx.pages if not ctx.state.last_id else max(ctx.pages, PAGINE_INCREMENTALI))
        msgs, max_seen = fetch_channel_messages(
            ctx.client, self.canale, last_id=ctx.state.last_id, max_pages=pagine)
        for m in msgs:
            m.channel = self.nome
        return FetchResult(msgs, last_id=max_seen)

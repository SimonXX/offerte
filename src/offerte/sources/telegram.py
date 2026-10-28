"""Fonte Telegram: anteprima pubblica https://t.me/s/<canale>, paginata con ?before=<id>."""

from __future__ import annotations

from urllib.parse import urlsplit

from ..http import Client
from ..parser import Message, parse_page
from . import registra
from .base import FetchContext, FetchResult, Source

BASE_URL = "https://t.me/s"


class NoPreview(Exception):
    pass


def fetch_channel_messages(client: Client, channel: str, *, last_id: int, max_pages: int) -> tuple[list[Message], int]:
    """Legge dalla pagina più recente indietro finché trova id già noti o esaurisce le pagine.

    Torna i messaggi nuovi e l'id più alto visto.
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


@registra
class TelegramSource(Source):
    tipo = "telegram"
    chiavi = frozenset({"canale", "pagine"})

    def configura(self) -> None:
        self.canale = str(self.opzione("canale") or self.nome).strip().lstrip("@").lower()

    def fetch(self, ctx: FetchContext) -> FetchResult:
        msgs, max_seen = fetch_channel_messages(
            ctx.client, self.canale, last_id=ctx.state.last_id, max_pages=int(self.opzione("pagine") or ctx.pages))
        for m in msgs:
            m.channel = self.nome
        return FetchResult(msgs, last_id=max_seen)

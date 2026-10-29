"""Notifiche via bot Telegram per le regole con notify: true. Token e chat id da .env."""

from __future__ import annotations

import html
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from .feeds import fmt_price
from .store import Offer

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/sendMessage"
ATTESA_MASSIMA = 60.0  # tetto dell'attesa chiesta da Telegram con un 429


def load_env(path: Path) -> None:
    """Carica KEY=VALUE da .env nell'ambiente, senza sovrascrivere variabili già presenti."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().removeprefix("export ").strip(), value.strip().strip("'\""))


def format_message(offer: Offer, rules: list[str]) -> str:
    e = html.escape
    righe = [f"🔔 <b>{e(', '.join(rules))}</b>", f"<b>{e(offer.title or 'Offerta')}</b>"]
    if offer.price is not None:
        prezzo = fmt_price(offer.price)
        if offer.old_price:
            prezzo += f" <s>{fmt_price(offer.old_price)}</s>"
        if offer.discount:
            prezzo += f" (-{offer.discount}%)"
        righe.append("💶 " + prezzo)
    if offer.coupon:
        righe.append(f"🎟 Coupon: <code>{e(offer.coupon)}</code>")
    righe.append("📣 " + e(", ".join(offer.channels)))
    righe.append(f'<a href="{e(offer.link or offer.permalink)}">Vai all\'offerta</a>')
    return "\n".join(righe)


class Notifier:
    def __init__(self, token: str, chat_id: str, *, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep, timeout: float = 15.0) -> None:
        self._url = API.format(token=token)
        self._chat_id = chat_id
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._sleep = sleep
        self._sent = 0

    @classmethod
    def from_env(cls, **kwargs) -> Notifier | None:
        token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return None
        return cls(token, chat_id, **kwargs)

    def send(self, offer: Offer, rules: list[str]) -> bool:
        for tentativo in range(2):
            if self._sent:
                self._sleep(1.0)  # limite Telegram: circa un messaggio al secondo per chat
            try:
                resp = self._client.post(self._url, data={
                    "chat_id": self._chat_id, "text": format_message(offer, rules), "parse_mode": "HTML"})
            except httpx.HTTPError as e:
                log.error("notifica fallita: %s", type(e).__name__)  # mai l'URL: contiene il token
                return False
            self._sent += 1
            if resp.status_code == 200:
                return True
            corpo = {}
            try:
                letto = resp.json()
            except ValueError:
                letto = None
            if isinstance(letto, dict):
                corpo = letto
            desc = corpo.get("description", "")
            attesa = (corpo.get("parameters") or {}).get("retry_after")
            if resp.status_code == 429 and tentativo == 0 and attesa is not None:
                log.warning("notifica rinviata di %s s dal limite di Telegram, riprovo una volta", attesa)
                self._sleep(min(float(attesa), ATTESA_MASSIMA))
                continue
            log.error("notifica rifiutata (HTTP %s) %s", resp.status_code, desc)
            return False
        return False

    def close(self) -> None:
        self._client.close()

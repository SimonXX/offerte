"""Contratto di una fonte e utilità comuni (date, record generici)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, ClassVar

from ..config import ConfigError
from ..dedupe import text_key
from ..extract import find_prices
from ..http import Client
from ..parser import Message
from ..store import SourceState, Store


@dataclass
class FetchResult:
    items: list[Message]
    last_id: int | None = None  # solo per fonti con id numerici crescenti (Telegram)


@dataclass
class FetchContext:
    client: Client
    store: Store
    now: datetime
    state: SourceState
    pages: int
    config_dir: Path
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("offerte.fonti"))


class Source:
    """Una fonte produce messaggi grezzi; il resto della pipeline (estrazione, dedupe, regole, feed) è comune."""

    tipo: ClassVar[str] = ""
    chiavi: ClassVar[frozenset[str]] = frozenset()  # opzioni ammesse oltre a nome, tipo, cartella, attivo, ogni

    def __init__(self, nome: str, cartella: str, opzioni: dict[str, Any], ogni: int = 0, attivo: bool = True) -> None:
        self.nome, self.cartella, self.ogni, self.attivo = nome, cartella, ogni, attivo
        extra = set(opzioni) - self.chiavi
        if extra:
            raise ConfigError(f"fonte '{nome}' ({self.tipo}): opzioni sconosciute {sorted(extra)}; ammesse {sorted(self.chiavi)}")
        self.opzioni = opzioni
        self.configura()

    def configura(self) -> None:
        """Validazione specifica del tipo; solleva ConfigError."""

    def fetch(self, ctx: FetchContext) -> FetchResult:
        raise NotImplementedError

    def opzione(self, chiave: str, default: Any = None, *, obbligatoria: bool = False) -> Any:
        valore = self.opzioni.get(chiave, default)
        if obbligatoria and (valore is None or valore == ""):
            raise ConfigError(f"fonte '{self.nome}' ({self.tipo}): manca '{chiave}'")
        return valore

    def __repr__(self) -> str:
        return f"<fonte {self.nome} tipo={self.tipo} cartella={self.cartella}>"


def parse_date(value: Any) -> datetime | None:
    """RFC 2822, ISO 8601 (anche con Z) o timestamp Unix; sempre con fuso, UTC se assente."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / (1000 if value > 1e11 else 1), tz=timezone.utc)
    s = str(value).strip()
    dt = None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_number(value: Any) -> float | None:
    """19.99, '19,99 €', '€ 1.299' -> float; None se non c'è un numero."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value)
    prezzi = find_prices(s)
    if prezzi:
        return prezzi[0][0]
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return None


ALIAS = {
    "id": ("id", "uid", "guid", "asin"),
    "titolo": ("titolo", "title", "name"),
    "testo": ("testo", "text", "description", "descrizione", "content"),
    "link": ("link", "url"),
    "links": ("links", "urls"),
    "immagine": ("immagine", "image", "img", "thumbnail"),
    "prezzo": ("prezzo", "price"),
    "prezzo_barrato": ("prezzo_barrato", "old_price", "list_price", "listPrice", "originalPrice"),
    "data": ("data", "date", "published", "timestamp"),
    "permalink": ("permalink",),
}


def _pick(d: dict[str, Any], campo: str) -> Any:
    for k in ALIAS[campo]:
        if d.get(k) not in (None, "", []):
            return d[k]
    return None


def record_to_message(d: dict[str, Any], source: str, now: datetime) -> Message | None:
    """Da un record generico (comando esterno, dataset Apify, JSON qualsiasi) a Message. None se non c'è testo."""
    titolo = str(_pick(d, "titolo") or "").strip()
    testo = str(_pick(d, "testo") or "").strip()
    if titolo and titolo not in testo:
        testo = f"{titolo}\n\n{testo}".strip()
    if not testo:
        return None
    link = _pick(d, "link")
    links = ([str(link)] if link else []) + [str(u) for u in (_pick(d, "links") or []) if u]
    uid = _pick(d, "id") or link or text_key(testo)
    immagine = _pick(d, "immagine")
    return Message(
        channel=source, id=str(uid), date=parse_date(_pick(d, "data")) or now, text=testo, struck=[],
        links=list(dict.fromkeys(links)), image=str(immagine) if immagine else None,
        permalink=str(_pick(d, "permalink") or link or ""),
        price=to_number(_pick(d, "prezzo")), old_price=to_number(_pick(d, "prezzo_barrato")),
    )

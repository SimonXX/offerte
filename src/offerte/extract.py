"""Estrazione di prezzo, prezzo barrato, sconto, coupon e nome prodotto dal testo di un messaggio."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Importi europei ("1.299,00", "19,99", "19.99", "1299") e americani ("1,299.00").
AMOUNT = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
PRICE_RE = re.compile(
    r"(?<![\d.,])(?:€\s?(?P<pre>" + AMOUNT + r")(?!\d)|(?P<post>" + AMOUNT + r")\s?(?:€|(?:euro|eur)(?![a-z])))",
    re.IGNORECASE,
)
PCT_RE = re.compile(r"(?<![\d.,])(?P<neg>[-−–]\s?)?(?P<pct>[1-9]\d?)\s?%")
OLD_HINT_RE = re.compile(
    r"(?:invece(?:\s+di|\s+che)?|anzich[eéè']?|listino|prezzo\s+pieno|prezzo\s+consigliato|era|prima|rrp|da)"
    r"\s*:?\s*(?:a\s+)?$",
    re.IGNORECASE,
)
COUPON_RE = re.compile(
    r"(?i:\b(?:coupon|codice(?:\s+sconto|\s+promo(?:zionale)?)?|code|promo\s?code|voucher)\b)[\s:：=\-]*[\"'«“]?"
    r"(?P<code>(?=[A-Z0-9_\-]*[A-Z])[A-Z0-9][A-Z0-9_\-]{2,}[A-Z0-9])(?![a-z0-9])"
)
COUPON_STOP = {
    "AMAZON", "SCONTO", "COUPON", "CODICE", "APPLICA", "APPLICABILE", "DISPONIBILE", "CHECKOUT", "CARRELLO",
    "EXTRA", "PRIME", "FLASH", "PREZZO", "OFFERTA", "NELLA", "DELLA", "ATTIVA", "ATTIVABILE", "SPUNTA", "PAGINA",
}
TRAILING_PRICE_RE = re.compile(
    r"[\s,;:|\-–—]*(?:\b(?:a|al prezzo di|per|solo|a soli|soli|da|ora|adesso)\s+)?"
    r"(?:€\s?" + AMOUNT + r"|" + AMOUNT + r"\s?(?:€|euro|eur))\s*(?:\([^)]*\))?\s*$",
    re.IGNORECASE,
)
LEAD_JUNK_RE = re.compile(r"^[\W_]+")
TRAIL_JUNK_RE = re.compile(r"[^\w)\]»\"'%]+$")


@dataclass
class Extracted:
    title: str | None
    price: float | None
    old_price: float | None
    discount: int | None
    coupon: str | None


def parse_amount(raw: str) -> float:
    raw = raw.strip()
    m = re.search(r"[.,](\d{1,2})$", raw)
    if m:
        cents, whole = m.group(1).ljust(2, "0"), raw[: m.start()]
    else:
        cents, whole = "00", raw
    return float(f"{re.sub(r'[.,]', '', whole)}.{cents}")


def find_prices(text: str) -> list[tuple[float, int]]:
    """Tutti i prezzi nel testo come (importo, posizione)."""
    return [(parse_amount(m.group("pre") or m.group("post")), m.start()) for m in PRICE_RE.finditer(text)]


def extract_prices(text: str, struck: list[str] = ()) -> tuple[float | None, float | None]:
    """(prezzo attuale, prezzo barrato). Barrato = dentro <s>, o preceduto da "invece di", "listino", "da"..."""
    struck_amounts = {amount for s in struck for amount, _ in find_prices(s)}
    current: list[float] = []
    old: list[float] = []
    for amount, start in find_prices(text):
        window = text[max(0, start - 30):start]
        if amount in struck_amounts or OLD_HINT_RE.search(window):
            old.append(amount)
        else:
            current.append(amount)
    price = current[0] if current else None
    old_price = max(old) if old else None
    if old_price is None and len(set(current)) == 2:
        price, old_price = min(current), max(current)
    if price is None or (old_price is not None and old_price <= price):
        old_price = None
    return price, old_price


def find_discount(text: str) -> int | None:
    first = None
    for m in PCT_RE.finditer(text):
        pct = int(m.group("pct"))
        before = text[max(0, m.start() - 20):m.start()].lower()
        if m.group("neg") or "scont" in before or "risparm" in before:
            return pct
        if first is None:
            first = pct
    return first


def find_coupon(text: str) -> str | None:
    for m in COUPON_RE.finditer(text):
        if m.group("code") not in COUPON_STOP:
            return m.group("code")
    return None


def _clean_line(line: str) -> str:
    s = TRAILING_PRICE_RE.sub("", line.strip())
    s = TRAIL_JUNK_RE.sub("", LEAD_JUNK_RE.sub("", s))
    s = re.sub(r"\s{2,}", " ", s)
    return s if re.search(r"\w", s) else ""


def _is_banner(s: str) -> bool:
    """Insegna breve tutta in maiuscolo ("ERRORE DI PREZZO", "BOMBA"), non un nome di prodotto."""
    return len(s.split()) <= 3 and not re.search(r"[a-zà-ú\d]", s)


def product_name(text: str, max_len: int = 120) -> str | None:
    lines = [s for s in (_clean_line(line) for line in text.splitlines()) if s]
    if not lines:
        return None
    chosen = lines[1] if len(lines) > 1 and _is_banner(lines[0]) else lines[0]
    if len(chosen) > max_len:
        chosen = TRAIL_JUNK_RE.sub("", chosen[:max_len].rsplit(" ", 1)[0]) + "…"
    return chosen


def extract(text: str, struck: list[str] = ()) -> Extracted:
    price, old_price = extract_prices(text, struck)
    discount = find_discount(text)
    if discount is None and price and old_price:
        discount = round((1 - price / old_price) * 100) or None
    return Extracted(product_name(text), price, old_price, discount, find_coupon(text))

"""Estrazione di prezzo, prezzo barrato, sconto, coupon e nome prodotto dal testo di un messaggio."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Importi europei ("1.299,00", "19,99", "19.99", "1299") e americani ("1,299.00").
AMOUNT = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
# Gli stessi formati con i decimali obbligatori. Per questi il simbolo staccato non e' mai il prefisso
# dell'importo successivo, quindi non serve la guardia che salva "Series 9 € 299" dal leggere 9 euro.
AMOUNT_DEC = r"(?:\d{1,3}(?:\.\d{3})+,\d{1,2}|\d{1,3}(?:,\d{3})+\.\d{1,2}|\d+[.,]\d{1,2})"
PRICE_RE = re.compile(
    r"(?<![\d.,])(?:"
    r"€\s?(?P<pre>" + AMOUNT + r")(?!\d)"
    r"|(?P<postd>" + AMOUNT_DEC + r")\s?(?:€|(?:euro|eur)(?![a-z]))"
    r"|(?P<post>" + AMOUNT + r")(?:€|\s€(?!\s?\d)|\s?(?:euro|eur)(?![a-z]))"
    r")",
    re.IGNORECASE,
)
PCT_RE = re.compile(r"(?<![\d.,])(?P<neg>[-\N{MINUS SIGN}\N{EN DASH}]\s?)?(?P<pct>100|[1-9]\d?)\s?%")
# Una percentuale vale come sconto solo se ha il segno meno o uno di questi nelle vicinanze.
PCT_CONTEXT_RE = re.compile(r"scont|risparm|\boff\b|\bsotto\b", re.IGNORECASE)
OLD_HINT_RE = re.compile(
    r"\b(?:invece(?:\s+di|\s+che)?|anzich[eéè']?|listino|prezzo\s+pieno|prezzo\s+consigliato"
    r"|era|prima|rrp|(?<!partire\s)da)"
    r"\s*:?\s*(?:a\s+)?$",
    re.IGNORECASE,
)
# Importi che non sono il prezzo del prodotto: coupon, spedizione, cashback, rate, risparmio.
NOISE_BEFORE = re.compile(
    r"\b(?:coupon|codice|buono|voucher|cashback|rimborso|extra|risparmi\w*|rate|rata"
    r"|sconto(?:\s+di)?|di\s+sconto"
    r"|spedizion[ei](?!\s+(?:gratuita|gratis|inclusa|prime)))"
    r"\s*(?:di|da|:|\+)?\s*$",
    re.IGNORECASE,
)
NOISE_AFTER = re.compile(
    r"^\s*(?:/\s*\w+|al\s+(?:kg|pezzo|litro)|di\s+(?:sconto|spedizione|coupon|cashback)|cad\b)",
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
    r"[\s,;:|\-\N{EN DASH}\N{EM DASH}]*(?:\b(?:a|al prezzo di|per|solo|a soli|soli|da|ora|adesso)\s+)?"
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


def _price_spans(text: str) -> list[tuple[float, int, int]]:
    """Tutti i prezzi come (importo, inizio, fine): la fine serve a leggere il contesto che segue."""
    return [(parse_amount(m.group("pre") or m.group("postd") or m.group("post")), m.start(), m.end())
            for m in PRICE_RE.finditer(text)]


def find_prices(text: str) -> list[tuple[float, int]]:
    """Tutti i prezzi nel testo come (importo, posizione)."""
    return [(amount, start) for amount, start, _ in _price_spans(text)]


def extract_prices(text: str, struck: list[str] = ()) -> tuple[float | None, float | None]:
    """(prezzo attuale, prezzo barrato). Barrato = dentro <s>, o preceduto da "invece di", "listino", "da"..."""
    struck_amounts = {amount for s in struck for amount, _ in find_prices(s)}
    current: list[tuple[float, int]] = []  # importo e numero di riga
    old: list[float] = []
    for amount, start, end in _price_spans(text):
        window = text[max(0, start - 30):start]
        if NOISE_BEFORE.search(window) or NOISE_AFTER.match(text[end:end + 25]):
            continue  # coupon, spedizione, cashback, rate: non è il prezzo del prodotto
        if amount in struck_amounts or OLD_HINT_RE.search(window):
            old.append(amount)
        else:
            current.append((amount, text.count("\n", 0, start)))
    price = current[0][0] if current else None
    old_price = max(old) if old else None
    importi = {amount for amount, _ in current}
    # Due soli importi senza indizi: il minore è il prezzo, ma solo se stanno sulla stessa riga.
    if old_price is None and len(importi) == 2 and len({riga for _, riga in current}) == 1:
        price, old_price = min(importi), max(importi)
    if price is None or (old_price is not None and old_price <= price):
        old_price = None
    return price, old_price


def find_discount(text: str) -> int | None:
    """Percentuale di sconto dichiarata nel testo: serve il segno meno o un contesto che parli di sconto."""
    for m in PCT_RE.finditer(text):
        before = text[max(0, m.start() - 20):m.start()]
        if m.group("neg") or PCT_CONTEXT_RE.search(before):
            return int(m.group("pct"))
    return None


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
    pct = find_discount(text)
    calcolato = None
    if price is not None and old_price:
        calcolato = round((1 - price / old_price) * 100) or None
    # La percentuale scritta nel testo vince solo se non smentisce quella calcolata dai due prezzi
    # ("IVA 22% inclusa" accanto a 49,99€ invece di 79,99€ non è lo sconto).
    if pct is None or (calcolato is not None and abs(calcolato - pct) > 3):
        discount = calcolato
    else:
        discount = pct
    return Extracted(product_name(text), price, old_price, discount, find_coupon(text))

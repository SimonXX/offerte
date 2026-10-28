"""Chiave di dedupe di un'offerta: URL normalizzato se c'è, altrimenti hash del testo normalizzato."""

from __future__ import annotations

import hashlib
import re

from .links import dedupe_key

URL_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    t = URL_RE.sub(" ", text.lower())
    t = re.sub(r"[@#]\w+", " ", t)  # menzioni e hashtag sono firma del canale, non dell'offerta
    t = re.sub(r"[^\w\s]", " ", t)  # emoji, punteggiatura, simboli di valuta
    return re.sub(r"\s+", " ", t).strip()


def text_key(text: str) -> str:
    return "text:" + hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()


def offer_key(link: str | None, text: str) -> str:
    return dedupe_key(link) if link else text_key(text)

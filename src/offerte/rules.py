"""Regole di alert: parole chiave (parola intera o regex), prezzo massimo, canali."""

from __future__ import annotations

from .config import Rule
from .store import Offer, Store


def matches(rule: Rule, offer: Offer) -> bool:
    if rule.canali and not rule.canali.intersection(offer.channels):
        return False
    if rule.prezzo_max is not None and (offer.price is None or offer.price > rule.prezzo_max):
        return False
    return any(p.search(offer.text) for p in rule.parole)


def apply_rules(store: Store, rules: tuple[Rule, ...], *, since: str, now: str) -> dict[int, list[Rule]]:
    """Valuta ogni regola sulle offerte della finestra non ancora associate; torna i nuovi match per offerta."""
    new: dict[int, list[Rule]] = {}
    for rule in rules:
        for offer in store.unmatched_offers(rule.nome, since):
            if matches(rule, offer):
                store.add_match(rule.nome, offer.id, now)
                new.setdefault(offer.id, []).append(rule)
    return new

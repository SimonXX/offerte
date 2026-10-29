"""Oracolo in Python del motore JavaScript: la stessa selezione, calcolata con rules.matches.

Lo usano sia i test del motore (tests/test_dashboard_js.py) sia quelli della pagina vera
(tests/test_dashboard_browser.py), così l'atteso è scritto una volta sola.
"""

from __future__ import annotations

import re

from offerte.config import Rule, compile_keyword
from offerte.rules import matches
from offerte.store import Offer

PERIODO_RE = re.compile(r"^([1-9][0-9]{0,2})(h|g)$")


def periodo_secondi(per: str | None) -> int | None:
    """Stessa regola di filtri.js: <numero>h oppure <numero>g."""
    m = PERIODO_RE.match(per or "")
    return int(m.group(1)) * (3600 if m.group(2) == "h" else 86400) if m else None


def offerta(voce: dict) -> Offer:
    """Da una voce di dashboard.json all'Offer che rules.matches sa valutare."""
    return Offer(id=voce["id"], key=str(voce["id"]), title=voce["n"], text=voce["x"], link=voce.get("u"),
                 permalink=voce.get("u") or "", image=voce.get("i"), price=voce.get("p"),
                 old_price=voce.get("b"), discount=voce.get("s"), coupon=voce.get("c"),
                 posted_at="", first_seen="", last_seen="", channels=list(voce["k"]), n_posts=1)


def canali_dello_stato(stato: dict, cartelle: dict) -> frozenset[str]:
    nomi: set[str] = set()
    for cartella in stato.get("cart", []):
        nomi |= set(cartelle.get(cartella, []))
    nomi |= set(stato.get("can", []))
    return frozenset(nomi)


def regola_dello_stato(stato: dict, cartelle: dict) -> Rule:
    return Rule(nome="caso",
                parole=tuple(compile_keyword(p) for p in stato.get("q", [])),
                escludi=tuple(compile_keyword(p) for p in stato.get("no", [])),
                tutte=bool(stato.get("tutte", False)),
                prezzo_min=stato.get("pmin"), prezzo_max=stato.get("pmax"),
                sconto_min=stato.get("smin"), solo_coupon=bool(stato.get("cp", False)),
                canali=canali_dello_stato(stato, cartelle))


def ordina(voci: list[dict], ordine: str) -> list[dict]:
    """Stessa chiave di specifica §3.5: i valori mancanti in fondo, a parità data e id decrescenti."""
    if ordine in ("prezzo-asc", "prezzo-desc", "sconto-asc", "sconto-desc"):
        campo = "p" if ordine.startswith("prezzo") else "s"
        crescente = ordine.endswith("asc")

        def chiave(v):
            manca = v.get(campo) is None
            valore = 0.0 if manca else float(v[campo])
            return (1 if manca else 0, valore if crescente else -valore, -v["t"], -v["id"])

        return sorted(voci, key=chiave)
    crescente = ordine == "data-asc"
    return sorted(voci, key=lambda v: (v["t"] if crescente else -v["t"], -v["id"]))


def seleziona(voci: list[dict], stato: dict, cartelle: dict, adesso: int | None = None) -> list[int]:
    """Gli id che la pagina deve mostrare, nell'ordine in cui deve mostrarli."""
    regola = regola_dello_stato(stato, cartelle)
    dentro = [v for v in voci if matches(regola, offerta(v))]
    secondi = periodo_secondi(stato.get("per"))
    if secondi is not None and adesso is not None:
        dentro = [v for v in dentro if v["t"] >= adesso - secondi]
    return [v["id"] for v in ordina(dentro, stato.get("ord") or "data-desc")]

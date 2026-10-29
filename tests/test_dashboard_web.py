"""Controlli statici sui file di src/offerte/static/: cosa il codice non deve contenere."""

import re
from pathlib import Path

import pytest

import offerte

STATIC = Path(offerte.__file__).parent / "static"
VIETATI_MOTORE = ("document", "window", "URLSearchParams", "performance", "navigator", "localStorage",
                  "fetch", "require", "module")


def sorgente(nome: str) -> str:
    return (STATIC / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize("vietato", VIETATI_MOTORE)
def test_motore_senza_identificatori_di_ambiente(vietato):
    """filtri.js deve girare identico nel browser, in gjs, in node, in deno e in bun."""
    assert not re.search(r"\b" + re.escape(vietato) + r"\b", sorgente("filtri.js")), vietato


def test_motore_senza_lookbehind_letterale():
    """Il lookbehind manca prima di Safari 16.4: va costruito con new RegExp, quindi dentro una stringa."""
    for numero, riga in enumerate(sorgente("filtri.js").splitlines(), start=1):
        for posizione in [m.start() for m in re.finditer(r"\(\?<[=!]", riga)]:
            prima = riga[:posizione]
            assert any(apice in prima for apice in ("'", '"', "`")), f"filtri.js:{numero}: lookbehind letterale"


def test_motore_espone_solo_filtri():
    testo = sorgente("filtri.js")
    assert "globalThis" in testo and "radice.Filtri = {" in testo
    assert "eval(" not in testo and "new Function" not in testo

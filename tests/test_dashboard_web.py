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


FILE_STATICI = ("dashboard.html", "dashboard.css", "filtri.js", "dashboard.js")
ID_OBBLIGATORI = ("q no tutte pmin pmax smin cart can per cp ord conta nascoste suggerimento elenco altre"
                  " regola azzera copia-link ricarica stato-dati avvisi preset chip-attivi filtri errore-q"
                  " errore-no toast dialogo nome-regola nome-avviso notify yaml esclusi-regola copia-yaml"
                  " chiudi-dialogo").split()
COPPIE_CONTRASTO = (("testo", "sfondo"), ("testo-2", "sfondo"), ("accento-testo", "accento"),
                    ("sconto-testo", "sconto"), ("avviso-testo", "avviso"))


# --- A27: cosa non deve esserci nei file serviti -----------------------------

@pytest.mark.parametrize("nome", FILE_STATICI)
def test_niente_url_assoluti_ne_percorsi_di_radice(nome):
    """La pagina deve funzionare sia su 127.0.0.1:8099 sia sotto il sottopercorso di GitHub Pages."""
    testo = sorgente(nome)
    assert "http://" not in testo and "https://" not in testo
    assert not re.search(r'(?:href|src)="/', testo)


@pytest.mark.parametrize("nome", FILE_STATICI)
def test_niente_trattini_lunghi(nome):
    testo = sorgente(nome)
    assert "\N{EN DASH}" not in testo and "\N{EM DASH}" not in testo


@pytest.mark.parametrize("nome", ("dashboard.js", "filtri.js"))
def test_niente_html_dinamico(nome):
    testo = sorgente(nome)
    for vietato in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "new Function"):
        assert vietato not in testo, vietato
    assert not re.search(r"\beval\s*\(", testo)


def test_html_senza_inline():
    testo = sorgente("dashboard.html")
    assert not re.search(r"<script(?![^>]*\ssrc=)", testo)      # nessuno script inline
    assert "<style" not in testo
    assert not re.search(r"\sstyle=", testo)
    assert not re.search(r"\son[a-z]+=", testo)


def test_csp_prima_di_tutto():
    testo = sorgente("dashboard.html")
    csp = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', testo)
    assert csp, "manca il meta CSP"
    regole = csp.group(1)
    assert "unsafe-inline" not in regole and "unsafe-eval" not in regole
    for direttiva in ("default-src 'none'", "script-src 'self'", "style-src 'self'",
                      "connect-src 'self'", "base-uri 'none'", "form-action 'none'"):
        assert direttiva in regole, direttiva
    # il meta protegge solo cio' che viene dopo di se'
    assert testo.index("Content-Security-Policy") < testo.index("<script")
    assert testo.index("Content-Security-Policy") < testo.index("<link")


def test_meta_di_testa():
    testo = sorgente("dashboard.html")
    assert '<html lang="it">' in testo
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in testo
    assert 'name="color-scheme" content="light dark"' in testo
    assert 'name="robots" content="noindex"' in testo
    assert 'name="referrer" content="no-referrer"' in testo
    assert "<title>Offerte</title>" in testo


# --- A28: gli id letti dal JS esistono nell'HTML -----------------------------

def test_id_letti_dal_js_esistono():
    html = sorgente("dashboard.html")
    presenti = set(re.findall(r'id="([^"]+)"', html))
    letti = set(re.findall(r'document\.getElementById\("([^"]+)"\)', sorgente("dashboard.js")))
    assert letti, "dashboard.js deve leggere gli id con getElementById e una stringa letterale"
    assert letti - presenti == set()


@pytest.mark.parametrize("identificatore", ID_OBBLIGATORI)
def test_id_obbligatori(identificatore):
    assert f'id="{identificatore}"' in sorgente("dashboard.html")


# --- A29: token di colore e contrasti ---------------------------------------

def blocchi_colore() -> dict[str, dict[str, str]]:
    css = sorgente("dashboard.css")

    def token(dopo: str) -> dict[str, str]:
        corpo = css.split(dopo, 1)[1].split("}", 1)[0]
        return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-f]{6});", corpo))

    return {"chiaro": token(":root {"),
            "scuro-media": token('prefers-color-scheme: dark'),
            "scuro-attributo": token(':root[data-theme="dark"] {')}


def test_token_negli_stessi_nomi():
    blocchi = blocchi_colore()
    assert len(blocchi["chiaro"]) >= 12
    assert set(blocchi["chiaro"]) == set(blocchi["scuro-media"]) == set(blocchi["scuro-attributo"])
    assert blocchi["scuro-media"] == blocchi["scuro-attributo"]


def luminanza(colore: str) -> float:
    def canale(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (int(colore[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * canale(r) + 0.7152 * canale(g) + 0.0722 * canale(b)


def contrasto(a: str, b: str) -> float:
    la, lb = luminanza(a), luminanza(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("tema", ("chiaro", "scuro-media", "scuro-attributo"))
def test_contrasti(tema):
    colori = blocchi_colore()[tema]
    for davanti, dietro in COPPIE_CONTRASTO:
        rapporto = contrasto(colori["--" + davanti], colori["--" + dietro])
        assert rapporto >= 4.5, f"{tema}: {davanti} su {dietro} e' {rapporto:.2f}"


def test_scala_dei_periodi_nel_js():
    """Il menu Periodo si costruisce dalla finestra dei dati, non e' una lista fissa nell'HTML."""
    js = sorgente("dashboard.js")
    assert "SCALA_PERIODI" in js and "finestra_giorni" in js
    gradini = re.findall(r'\{valore: "([0-9]+[hg])"', js)
    assert gradini == ["1h", "3h", "6h", "12h", "24h", "48h", "3g", "7g", "14g", "30g", "60g", "90g"]


def test_interruttore_parola_intera():
    """La ricerca di default e' per sottostringa; la parola intera e' un interruttore, non una sintassi."""
    js = sorgente("filtri.js")
    assert "function compilaVoce(voce, parolaIntera)" in js
    assert "pi: false" in js          # il default dello stato
    assert "stato.pi = true;" in js   # una regola di config vale come parola intera
    html = sorgente("dashboard.html")
    assert '<input type="checkbox" id="parola-intera">' in html


def test_grafico_caricato_solo_a_richiesta():
    """L'immagine di terzi si crea all'apertura della scheda, non al rendering delle 60 schede."""
    js = sorgente("dashboard.js")
    assert 'd.classList.contains("storico")' in js and 'if (d.querySelector("img")) { return; }' in js
    assert "dati.grafico" in js and "https://" not in js   # l'indirizzo arriva dai dati, non dal sorgente
    assert 'img.referrerPolicy = "no-referrer"' in js

"""La pagina vera in Chrome headless, servita da offerte.serve su una porta effimera."""

import json
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from demo_dati import crea_db, scrivi_config
from offerte import serve as modulo_serve
from offerte.config import load_config
from offerte.feeds import dashboard_cartelle, write_feeds
from offerte.rules import apply_rules
from riferimento import seleziona

BROWSER = ("google-chrome", "chromium", "chromium-browser")
WEB = Path(__file__).parent / "web"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def trova_browser() -> str | None:
    import os
    scelto = os.environ.get("OFFERTE_TEST_BROWSER")
    if scelto and shutil.which(scelto):
        return shutil.which(scelto)
    for nome in BROWSER:
        percorso = shutil.which(nome)
        if percorso:
            return percorso
    return None


CHROME = trova_browser()
if CHROME is None:
    pytest.skip("nessun Chrome o Chromium: i test della pagina si saltano", allow_module_level=True)


def dom(url: str, timeout: float = 60.0) -> str:
    """Il DOM finale della pagina: --dump-dom esegue gli script prima di stampare."""
    with tempfile.TemporaryDirectory(prefix="offerte-chrome-") as profilo:
        esito = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profilo}",
             "--virtual-time-budget=8000", "--dump-dom", url],
            capture_output=True, text=True, timeout=timeout)
    return esito.stdout


def attributi(html: str) -> dict[str, str]:
    inizio = re.search(r"<html([^>]*)>", html)
    return dict(re.findall(r'(data-[a-z-]+)="([^"]*)"', inizio.group(1) if inizio else ""))


class Servitore:
    def __init__(self, cartella: Path) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          partial(modulo_serve.FeedHandler, directory=str(cartella)))
        self.cartella = cartella
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def chiudi(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def prepara(cartella: Path, quante: int = 300) -> tuple[dict, dict]:
    config = load_config(scrivi_config(cartella))
    db = config.parametri.var_dir / "offerte.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    with crea_db(db, n=quante, now=NOW) as store:
        apply_rules(store, config.regole, since=(NOW - timedelta(days=14)).isoformat(timespec="seconds"),
                    now=NOW.isoformat(timespec="seconds"))
        write_feeds(store, config, datetime.now(timezone.utc))
    documento = json.loads((config.parametri.var_dir / "feeds" / "dashboard.json").read_text(encoding="utf-8"))
    return documento, dashboard_cartelle(config)


@pytest.fixture(scope="module")
def servito():
    with tempfile.TemporaryDirectory(prefix="offerte-web-") as cartella:
        documento, cartelle = prepara(Path(cartella))
        feeds = Path(cartella) / "var" / "feeds"
        shutil.copy(WEB / "layout.html", feeds / "layout.html")
        servitore = Servitore(feeds)
        try:
            yield servitore, documento, cartelle
        finally:
            servitore.chiudi()


URL_DI_PROVA = [
    ("", {}),
    ("?q=ssd", {"q": ["ssd"]}),
    ("?q=apple%20watch&no=cinturino", {"q": ["apple watch"], "no": ["cinturino"]}),
    ("?q=ssd&q=cuffie", {"q": ["ssd", "cuffie"]}),
    ("?q=ssd&q=cuffie&tutte=1", {"q": ["ssd", "cuffie"], "tutte": True}),
    ("?q=%2F%5Cbwatch%5Cs*(se%7Cultra)%5Cb%2F", {"q": [r"/\bwatch\s*(se|ultra)\b/"]}),
    ("?pmax=100", {"pmax": 100.0}),
    ("?pmin=0", {"pmin": 0.0}),
    ("?pmin=20&pmax=60", {"pmin": 20.0, "pmax": 60.0}),
    ("?pmin=250&pmax=20", {"pmin": 20.0, "pmax": 250.0}),
    ("?smin=40", {"smin": 40}),
    ("?cp=1", {"cp": True}),
    ("?smin=30&cp=1", {"smin": 30, "cp": True}),
    ("?cart=informatica", {"cart": ["informatica"]}),
    ("?cart=informatica,casa", {"cart": ["informatica", "casa"]}),
    ("?can=mttvideo", {"can": ["mttvideo"]}),
    ("?cart=cina&can=mttvideo", {"cart": ["cina"], "can": ["mttvideo"]}),
    ("?can=sparito", {}),
    ("?ord=data-asc", {"ord": "data-asc"}),
    ("?ord=prezzo-asc", {"ord": "prezzo-asc"}),
    ("?ord=prezzo-desc", {"ord": "prezzo-desc"}),
    ("?ord=sconto-desc", {"ord": "sconto-desc"}),
    ("?ord=sconto-asc", {"ord": "sconto-asc"}),
    ("?q=ssd&pmax=100&smin=20&cart=informatica&ord=prezzo-asc",
     {"q": ["ssd"], "pmax": 100.0, "smin": 20, "cart": ["informatica"], "ord": "prezzo-asc"}),
]


def test_url_riferimento(servito):
    servitore, documento, cartelle = servito
    offerte = documento["offerte"]
    assert len(URL_DI_PROVA) >= 20
    for coda, atteso in URL_DI_PROVA:
        html = dom(f"{servitore.base}/dashboard.html{coda}")
        a = attributi(html)
        assert a.get("data-stato") == "pronto", coda
        ids = seleziona(offerte, atteso, cartelle)
        assert a.get("data-n") == str(len(ids)), coda
        assert a.get("data-primi") == ",".join(str(i) for i in ids[:20]), coda


def test_regex_non_valida_ignora_il_filtro_testo(servito):
    servitore, documento, _ = servito
    a = attributi(dom(f"{servitore.base}/dashboard.html?q=%2F(%2F"))
    assert a.get("data-errori-regex") == "1"
    assert a.get("data-n") == str(len(documento["offerte"]))


def test_layout_senza_scroll(servito):
    servitore, _, _ = servito
    html = dom(f"{servitore.base}/layout.html")
    testo = re.search(r'<pre id="esito">(.*?)</pre>', html, re.S).group(1)
    misure = json.loads(testo)
    assert sorted(int(k) for k in misure) == [320, 360, 390, 768, 1280]
    for larghezza, valori in misure.items():
        assert valori["scrollWidth"] <= valori["clientWidth"], f"{larghezza} px: scroll orizzontale"


def test_xss_json_ostile(tmp_path):
    documento, _ = prepara(tmp_path, quante=5)
    feeds = tmp_path / "var" / "feeds"
    ostile = {
        "v": 1, "generato": documento["generato"], "finestra_giorni": 14, "troncato": False,
        "cartelle": {"casa": ["mttcasa"]}, "regole": [], "fonti": [],
        "offerte": [{"id": 1, "t": documento["generato"] - 60,
                     "n": "Titolo ostile <img src=x onerror=alert(1)>",
                     "x": "Testo con <script>alert(2)</script> e <img onerror=alert(3)>",
                     "k": ["mttcasa"], "u": "javascript:alert(1)", "m": "data:text/html,<b>x</b>",
                     "i": "data:image/svg+xml,<svg onload=alert(4)>"}],
    }
    (feeds / "dashboard.json").write_text(json.dumps(ostile, ensure_ascii=False), encoding="utf-8")
    servitore = Servitore(feeds)
    try:
        html = dom(f"{servitore.base}/dashboard.html")
    finally:
        servitore.chiudi()
    corpo = html[html.index("<body"):]
    assert "onerror=" not in corpo.replace("onerror=alert", "ONERROR_TESTUALE")
    assert "<script>alert(2)" not in corpo
    for attributo in re.findall(r'(?:href|src)="([^"]*)"', corpo):
        assert attributo.startswith(("http:", "https:", "index.html", "regola/", "dashboard", "filtri")), attributo
    assert "Titolo ostile &lt;img src=x onerror=alert(1)&gt;" in corpo
    assert attributi(html).get("data-n") == "1"


def test_file_protocol(tmp_path):
    prepara(tmp_path, quante=5)
    pagina = tmp_path / "var" / "feeds" / "dashboard.html"
    assert attributi(dom(pagina.as_uri())).get("data-stato") == "errore-file"


@pytest.fixture(scope="module")
def servito_predefinite():
    """La stessa pagina, con config che parte dalla sola cartella informatica."""
    with tempfile.TemporaryDirectory(prefix="offerte-pred-") as cartella:
        base = Path(cartella)
        config = load_config(scrivi_config(base, dashboard_cartelle=["informatica"]))
        db = config.parametri.var_dir / "offerte.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        with crea_db(db, n=300, now=NOW) as store:
            apply_rules(store, config.regole, since=(NOW - timedelta(days=14)).isoformat(timespec="seconds"),
                        now=NOW.isoformat(timespec="seconds"))
            write_feeds(store, config, datetime.now(timezone.utc))
        feeds = config.parametri.var_dir / "feeds"
        documento = json.loads((feeds / "dashboard.json").read_text(encoding="utf-8"))
        servitore = Servitore(feeds)
        try:
            yield servitore, documento, dashboard_cartelle(config)
        finally:
            servitore.chiudi()


def test_cartelle_predefinite_senza_link(servito_predefinite):
    """Senza nulla nell'URL la pagina parte dalle cartelle di config; un link esplicito le scavalca."""
    servitore, documento, cartelle = servito_predefinite
    assert documento["predefinite"] == ["informatica"]
    offerte = documento["offerte"]

    a = attributi(dom(f"{servitore.base}/dashboard.html"))
    assert a.get("data-stato") == "pronto"
    ids = seleziona(offerte, {"cart": ["informatica"]}, cartelle)
    assert a.get("data-n") == str(len(ids))
    assert a.get("data-primi") == ",".join(str(i) for i in ids[:20])

    a = attributi(dom(f"{servitore.base}/dashboard.html?cart=casa"))
    ids = seleziona(offerte, {"cart": ["casa"]}, cartelle)
    assert a.get("data-n") == str(len(ids))

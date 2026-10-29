"""Giro completo su trasporto finto: canale ok con storico, canale senza anteprima, canale che fallisce."""

import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import httpx
import pytest
import yaml

from offerte.config import load_config
from offerte.fetch import run_fetch
from offerte.http import Client
from offerte.notify import Notifier
from offerte.store import Store

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
PAGINA_VUOTA = "<html><body><div class='tgme_channel_info'></div><section class='tgme_channel_history'></section></body></html>"


@pytest.fixture
def ambiente(tmp_path, fixture_html):
    cfg = {
        "parametri": {"intervallo_cortesia": 0, "pagine_storico": 3, "var_dir": str(tmp_path / "var")},
        "canali": [
            {"nome": "canale_test", "cartella": "informatica"},
            {"nome": "privato", "cartella": "casa"},
            {"nome": "rotto", "cartella": "casa"},
        ],
        "regole": [
            {"nome": "ssd", "parole": ["ssd"], "prezzo_max": 100, "notify": True},
            {"nome": "cuffie", "parole": ["/wh-ch\\d+/"], "canali": ["informatica"]},
        ],
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    config = load_config(tmp_path / "config.yaml")
    pagine = {
        "https://t.me/s/canale_test": fixture_html("canale_pagina1.html"),
        "https://t.me/s/canale_test?before=101": fixture_html("canale_pagina2.html"),
        "https://t.me/s/canale_test?before=99": PAGINA_VUOTA,
        "https://t.me/privato": fixture_html("senza_anteprima.html"),
    }
    redirect = {
        "https://amzn.to/3abcDEF": "https://www.amazon.it/Samsung-980-PRO/dp/B08GLX7TNT/ref=cm_sw?tag=canale-21&linkCode=sl1",
        "https://amzlink.to/az0H8zvgoKGOf": "https://www.amazon.it/dp/B07BN21Y1J?tag=errnew25-21&psc=1",
    }
    inviate = []

    def handler(request):
        url = str(request.url)
        if request.method == "POST" and "api.telegram.org" in url:
            inviate.append(dict(parse_qsl(request.read().decode())))
            return httpx.Response(200, json={"ok": True})
        if url in pagine:
            return httpx.Response(200, text=pagine[url])
        if url.startswith("https://t.me/s/privato"):
            return httpx.Response(302, headers={"location": "https://t.me/privato"})
        if url.startswith("https://t.me/s/rotto"):
            return httpx.Response(503)
        if url in redirect:
            return httpx.Response(301, headers={"location": redirect[url]})
        if "amazon.it" in url:
            return httpx.Response(200, text="")
        return httpx.Response(404)

    return config, httpx.MockTransport(handler), inviate


def test_giro_completo(ambiente):
    config, transport, inviate = ambiente
    var = config.parametri.var_dir
    with Store(var / "offerte.sqlite") as store:
        client = Client("ua", courtesy=0, transport=transport, sleep=lambda s: None)
        notifier = Notifier("token", "42", transport=transport, sleep=lambda s: None)
        s = run_fetch(config, store, client, notifier, now=NOW)

        assert s.ok == ["canale_test"] and s.skipped == ["privato"] and list(s.failed) == ["rotto"]
        assert s.new_posts == 6 and len(s.new_offers) == 6
        stato = store.channel_state("canale_test")
        assert (stato.last_id, stato.bootstrapped) == (106, True)

        per_msg = {o.permalink.rsplit("/", 1)[1]: o for o in store.offers_for_channels(["canale_test"], "2026-01-01", 100)}
        assert per_msg["102"].link == "https://www.amazon.it/dp/B08GLX7TNT?tag=canale-21"  # shortener risolto e ripulito
        assert per_msg["99"].link == "https://www.amazon.it/dp/B07BN21Y1J?tag=errnew25-21"
        assert per_msg["99"].key == "url:amazon.it/dp/B07BN21Y1J"
        assert (per_msg["106"].title, per_msg["106"].price, per_msg["106"].old_price, per_msg["106"].discount) == \
            ("Mikado Cioccolato Fondente, 24x39g", 13.08, 34.90, 63)
        assert per_msg["105"].key.startswith("text:") and per_msg["105"].link is None
        assert per_msg["100"].price == 199.0

        assert s.matches == {"ssd": 1, "cuffie": 1}
        assert s.notified == 1 and len(inviate) == 1
        assert "SSD Samsung 980 PRO 1TB" in inviate[0]["text"] and inviate[0]["chat_id"] == "42"

        feeds = var / "feeds"
        rss = (feeds / "cartella" / "informatica.xml").read_text(encoding="utf-8")
        assert "SSD Samsung 980 PRO 1TB NVMe PCIe 4.0, 79,99€ (-38%)" in rss
        assert "<enclosure" in rss and "<category>canale_test</category>" in rss
        jf = json.loads((feeds / "regola" / "ssd.json").read_text(encoding="utf-8"))
        assert [i["title"] for i in jf["items"]] == ["SSD Samsung 980 PRO 1TB NVMe PCIe 4.0, 79,99€ (-38%)"]
        assert jf["items"][0]["_offerte"]["canali"] == ["canale_test"]
        assert (feeds / "cartella" / "casa.xml").exists() and (feeds / "index.html").exists()
        assert (var / "offerte.sqlite").exists()

        dash = json.loads((feeds / "dashboard.json").read_text(encoding="utf-8"))
        assert len(dash["offerte"]) == 6 and dash["v"] == 1
        assert sorted(dash["cartelle"]) == ["casa", "informatica"]
        assert [f["nome"] for f in dash["fonti"]] == ["canale_test", "privato", "rotto"]
        for nome in ("dashboard.html", "dashboard.css", "filtri.js", "dashboard.js"):
            assert (feeds / nome).exists(), nome

        # secondo giro: niente di nuovo, nessuna notifica ripetuta, il canale rotto resta isolato
        s2 = run_fetch(config, store, client, notifier, now=NOW)
        assert s2.new_posts == 0 and s2.notified == 0 and len(inviate) == 1
        assert s2.ok == ["canale_test"]


def telegram_finto(risposte):
    """Trasporto che risponde solo all'API di Telegram, consumando `risposte` una alla volta."""
    inviate = []

    def handler(request):
        inviate.append(dict(parse_qsl(request.read().decode())))
        return risposte.pop(0)

    return httpx.MockTransport(handler), inviate


def config_finta(tmp_path, **extra):
    cfg = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var")},
        "fonti": [{"nome": "finta", "tipo": "fonte_finta:FonteFinta", "cartella": "casa", "n": 1}],
        "regole": [{"nome": "finto", "parole": ["prodotto"], "notify": True}],
        **extra,
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return load_config(tmp_path / "config.yaml")


def test_notifica_fallita_si_ritenta_al_giro_dopo(tmp_path):
    config = config_finta(tmp_path)
    rifiuto = {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 2}}
    transport, inviate = telegram_finto([httpx.Response(429, json=rifiuto), httpx.Response(429, json=rifiuto),
                                         httpx.Response(200, json={"ok": True})])
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=httpx.MockTransport(lambda r: httpx.Response(404)), sleep=lambda s: None)
        notifier = Notifier("token", "42", transport=transport, sleep=lambda s: None)
        primo = run_fetch(config, store, client, notifier, now=NOW)
        assert primo.notified == 0 and len(inviate) == 2  # 429 e una sola riprova nello stesso giro
        secondo = run_fetch(config, store, client, notifier, now=NOW + timedelta(minutes=10))
        assert secondo.notified == 1 and len(inviate) == 3
        terzo = run_fetch(config, store, client, notifier, now=NOW + timedelta(minutes=20))
        assert terzo.notified == 0 and len(inviate) == 3  # notificata una volta sola


def test_notifica_riprova_una_volta_su_429(tmp_path):
    config = config_finta(tmp_path)
    rifiuto = {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 1}}
    transport, inviate = telegram_finto([httpx.Response(429, json=rifiuto), httpx.Response(200, json={"ok": True})])
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=httpx.MockTransport(lambda r: httpx.Response(404)), sleep=lambda s: None)
        notifier = Notifier("token", "42", transport=transport, sleep=lambda s: None)
        s = run_fetch(config, store, client, notifier, now=NOW)
    assert s.notified == 1 and len(inviate) == 2


def test_regola_senza_notify_non_mette_in_coda(tmp_path):
    config = config_finta(tmp_path, regole=[{"nome": "finto", "parole": ["prodotto"], "notify": False}])
    transport, inviate = telegram_finto([])
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=httpx.MockTransport(lambda r: httpx.Response(404)), sleep=lambda s: None)
        s = run_fetch(config, store, client, Notifier("token", "42", transport=transport, sleep=lambda s: None), now=NOW)
    assert s.notified == 0 and inviate == []


SCRIPT_SENZA_DATA = (
    "import json\n"
    "for i in range(3):\n"
    "    print(json.dumps({'id': f'x{i}', 'titolo': f'Prodotto {i}', 'testo': 'descrizione', 'prezzo': '19,99 €'}))\n"
)


def test_data_di_ripiego_al_primo_giro_non_notifica(tmp_path):
    (tmp_path / "scraper.py").write_text(SCRIPT_SENZA_DATA, encoding="utf-8")
    cfg = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var")},
        "fonti": [{"nome": "senzadata", "tipo": "comando", "cartella": "casa",
                   "comando": [sys.executable, str(tmp_path / "scraper.py")]}],
        "regole": [{"nome": "tutto", "parole": ["prodotto"], "notify": True}],
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    config = load_config(tmp_path / "config.yaml")
    transport, inviate = telegram_finto([])
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=httpx.MockTransport(lambda r: httpx.Response(404)), sleep=lambda s: None)
        notifier = Notifier("token", "42", transport=transport, sleep=lambda s: None)
        primo = run_fetch(config, store, client, notifier, now=NOW)
        secondo = run_fetch(config, store, client, notifier, now=NOW + timedelta(minutes=10))
    assert len(primo.new_offers) == 3 and primo.notified == 0
    assert secondo.notified == 0 and inviate == []


def test_fonte_html_vuota_resta_fra_le_ok(tmp_path):
    cfg = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var")},
        "fonti": [{"nome": "pagina", "tipo": "html", "cartella": "casa",
                   "url": "https://shop.example.com/offerte", "elemento": "div.deal"}],
        "regole": [{"nome": "r", "parole": ["ssd"]}],
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    config = load_config(tmp_path / "config.yaml")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="<html><body><p>layout cambiato</p></body></html>"))
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=transport, sleep=lambda s: None)
        s = run_fetch(config, store, client, None, now=NOW)
        assert s.ok == ["pagina"] and not s.failed
        assert store.channel_state("pagina").last_status == "vuota"


def test_isolamento_errore_dashboard(ambiente, monkeypatch, caplog):
    """Se la dashboard fallisce, il giro arriva in fondo: feed scritti, stato salvabile, niente rinotifiche."""
    config, transport, _ = ambiente

    def esplode(store, config, now):
        raise RuntimeError("disco pieno")

    monkeypatch.setattr("offerte.feeds.write_dashboard", esplode)
    var = config.parametri.var_dir
    with Store(var / "offerte.sqlite") as store, caplog.at_level("ERROR"):
        client = Client("ua", courtesy=0, transport=transport, sleep=lambda s: None)
        s = run_fetch(config, store, client, None, now=NOW)
    assert s.ok == ["canale_test"] and len(s.new_offers) == 6
    assert (var / "feeds" / "cartella" / "informatica.xml").exists()
    assert (var / "feeds" / "index.html").exists()
    assert not (var / "feeds" / "dashboard.json").exists()
    assert "dashboard: scrittura fallita" in caplog.text

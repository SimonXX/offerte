import json
import sys
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import yaml

from offerte.config import ConfigError, load_config
from offerte.fetch import is_due, run_fetch
from offerte.http import Client, FetchError
from offerte.sources import crea_fonte, tipo_fonte
from offerte.sources.apify import ApifySource, mappa
from offerte.sources.base import FetchContext, parse_date, to_number
from offerte.sources.comando import CommandSource
from offerte.sources.html import HtmlSource
from offerte.sources.rss import parse_feed
from offerte.store import SourceState, Store

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Offerte Test</title><link>https://example.com/</link>
<item><title>Apple Watch SE 2024 40mm</title><link>https://example.com/offerte/apple-watch-se?utm_source=rss</link>
<guid isPermaLink="false">aw-se-1</guid><pubDate>Mon, 27 Oct 2026 08:15:00 +0000</pubDate>
<description><![CDATA[<p>Prezzo <b>199,00\xe2\x82\xac</b> <s>279,00\xe2\x82\xac</s></p><p><a href="https://www.amazon.it/dp/B0DGHQ2QG4?tag=x-21">Vai</a></p><img src="https://example.com/img/aw.jpg">]]></description>
<enclosure url="https://example.com/img/aw-big.jpg" type="image/jpeg" length="0"/>
</item>
<item><title>Solo titolo</title><link>https://example.com/2</link><pubDate>boh</pubDate><description></description></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
<entry><title>Cuffie Sony</title><link rel="alternate" href="https://example.com/cuffie"/><id>urn:1</id>
<updated>2026-10-27T09:30:00Z</updated><summary type="html">&lt;p&gt;29,99 euro&lt;/p&gt;</summary></entry></feed>"""

PAGINA = """<html><body>
<div class="deal"><h3>SSD Crucial P3 1TB</h3><span class="price">59,99 €</span><span class="old">89,99 €</span>
 <a href="/p/crucial-p3?ref=home">dettagli</a><img src="/img/p3.jpg"></div>
<div class="deal"><h3>Mouse Logitech</h3><span class="price">€ 19.99</span><a href="https://shop.example.com/p/mx">x</a></div>
<div class="deal"><h3></h3></div>
</body></html>"""


def ctx(tmp_path, transport=None):
    return FetchContext(client=Client("ua", courtesy=0, transport=transport or httpx.MockTransport(lambda r: httpx.Response(404)), sleep=lambda s: None),
                        store=Store(":memory:"), now=NOW, state=SourceState(), pages=1, config_dir=tmp_path)


def test_rss():
    msgs = parse_feed(RSS, "feed", NOW)
    assert [m.id for m in msgs] == ["aw-se-1", "https://example.com/2"]
    m = msgs[0]
    assert m.date.isoformat() == "2026-10-27T08:15:00+00:00"
    assert m.text.startswith("Apple Watch SE 2024 40mm\n\nPrezzo 199,00€ 279,00€")
    assert m.struck == ["279,00€"]
    assert m.links == ["https://example.com/offerte/apple-watch-se?utm_source=rss", "https://www.amazon.it/dp/B0DGHQ2QG4?tag=x-21"]
    assert m.image == "https://example.com/img/aw-big.jpg"  # l'enclosure vince sull'img nel testo
    assert msgs[1].date == NOW and msgs[1].text == "Solo titolo"


def test_atom():
    (m,) = parse_feed(ATOM, "feed", NOW)
    assert (m.id, m.permalink, m.text) == ("urn:1", "https://example.com/cuffie", "Cuffie Sony\n\n29,99 euro")
    assert m.date.isoformat() == "2026-10-27T09:30:00+00:00"


def test_feed_rotto():
    with pytest.raises(FetchError):
        parse_feed(b"<rss><channel><item>", "feed", NOW)


def test_html():
    fonte = HtmlSource("pagina", "informatica", {
        "url": "https://shop.example.com/offerte", "elemento": "div.deal",
        "campi": {"titolo": "h3", "link": "a@href", "prezzo": ".price", "prezzo_barrato": ".old", "immagine": "img@src"}})
    items = fonte.parse(PAGINA, NOW)
    assert len(items) == 2  # il terzo elemento non ha testo
    a, b = items
    assert a.text.startswith("SSD Crucial P3 1TB")
    assert (a.price, a.old_price) == (59.99, 89.99)
    assert a.links[0] == "https://shop.example.com/p/crucial-p3?ref=home" and a.id == a.links[0]
    assert a.image == "https://shop.example.com/img/p3.jpg"
    assert (b.price, b.old_price, b.image) == (19.99, None, None)


def test_html_campi_sconosciuti():
    with pytest.raises(ConfigError, match="campi sconosciuti"):
        HtmlSource("x", "y", {"url": "https://e.com", "elemento": "div", "campi": {"prezo": ".p"}})


def test_comando(tmp_path):
    script = tmp_path / "scraper.py"
    script.write_text(
        "import json, os, sys\n"
        "print(json.dumps({'id': 'a1', 'titolo': 'Robot ' + os.environ['OFFERTE_FONTE'], 'testo': 'descrizione', 'link': 'https://e.com/a1', 'prezzo': '199,00 €', 'data': '2026-10-27T10:00:00Z'}))\n"
        "print(json.dumps({'title': 'Senza id', 'url': 'https://e.com/b', 'price': 12.5, 'image': 'https://e.com/b.jpg'}))\n"
        "print(json.dumps({'title': ''}))\n", encoding="utf-8")
    fonte = CommandSource("mio", "varie", {"comando": [sys.executable, str(script)]})
    items = fonte.fetch(ctx(tmp_path)).items
    assert len(items) == 2
    assert (items[0].id, items[0].price, items[0].text.splitlines()[0]) == ("a1", 199.0, "Robot mio")
    assert items[0].date.isoformat() == "2026-10-27T10:00:00+00:00"
    assert (items[1].id, items[1].price, items[1].image) == ("https://e.com/b", 12.5, "https://e.com/b.jpg")


def test_comando_fallito(tmp_path):
    fonte = CommandSource("mio", "varie", {"comando": f"{sys.executable} -c 'import sys; sys.exit(3)'"})
    with pytest.raises(FetchError, match="uscito con 3"):
        fonte.fetch(ctx(tmp_path))


def test_apify(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "tok-segreto")
    richieste = []

    def handler(request):
        richieste.append(request)
        return httpx.Response(200, json=[
            {"asin": "B0X", "title": "Robot aspirapolvere", "description": "con mappatura", "url": "https://www.amazon.it/dp/B0X?tag=a-21",
             "price": {"value": 199.0}, "listPrice": "279,00 €", "image": "https://m.media-amazon.com/x.jpg"},
            {"title": "", "description": ""},
        ])

    c = ctx(tmp_path, httpx.MockTransport(handler))
    sync = ApifySource("deals", "casa", {"actor": "ayeeyee/amazon-deals-scraper", "modo": "sync", "input": {"country": "it"}, "timeout": 60}, ogni=180)
    items = sync.fetch(c).items
    assert len(items) == 1 and items[0].id == "B0X" and items[0].price == 199.0 and items[0].old_price == 279.0
    r = richieste[-1]
    assert r.method == "POST" and r.url.path == "/v2/acts/ayeeyee~amazon-deals-scraper/run-sync-get-dataset-items"
    assert r.headers["authorization"] == "Bearer tok-segreto" and r.url.params["timeout"] == "60"
    assert json.loads(r.read()) == {"country": "it"}

    ultimo = ApifySource("deals2", "casa", {"actor": "ayeeyee/amazon-deals-scraper"}, ogni=60)
    ultimo.fetch(c)
    r = richieste[-1]
    assert r.method == "GET" and r.url.path.endswith("/runs/last/dataset/items") and r.url.params["status"] == "SUCCEEDED"


def test_apify_vincoli(tmp_path, monkeypatch):
    with pytest.raises(ConfigError, match="ogni"):
        ApifySource("x", "y", {"actor": "a/b"})
    with pytest.raises(ConfigError, match="modo"):
        ApifySource("x", "y", {"actor": "a/b", "modo": "boh"}, ogni=10)
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with pytest.raises(FetchError, match="APIFY_TOKEN"):
        ApifySource("x", "y", {"actor": "a/b"}, ogni=10).fetch(ctx(tmp_path))


def test_mappa_e_conversioni():
    assert mappa({"a": {"b": 1}, "t": "x"}, {"prezzo": "zz|a.b", "titolo": "t"}) == {"prezzo": 1, "titolo": "x"}
    assert to_number("€ 1.299,00") == 1299.0 and to_number(12) == 12.0 and to_number("n/d") is None
    assert parse_date(1793095200).isoformat() == "2026-10-27T10:00:00+00:00"
    assert parse_date("2026-10-27 10:00:00").tzinfo is not None


def test_registro_e_classe_esterna(tmp_path):
    assert tipo_fonte("rss").tipo == "rss"
    with pytest.raises(ConfigError, match="sconosciuto"):
        tipo_fonte("boh")
    with pytest.raises(ConfigError, match="opzioni sconosciute"):
        crea_fonte({"nome": "x", "tipo": "rss", "url": "https://e.com", "urll": 1})
    fonte = crea_fonte({"nome": "f", "tipo": "fonte_finta:FonteFinta", "cartella": "test", "n": 2})
    assert fonte.tipo == "finta" and fonte.cartella == "test"


def test_is_due():
    recente = SourceState(last_fetch=(NOW - timedelta(minutes=10)).isoformat(timespec="seconds"))
    assert is_due(crea_fonte({"nome": "a", "tipo": "fonte_finta:FonteFinta", "ogni": 5}), recente, NOW)
    assert not is_due(crea_fonte({"nome": "a", "tipo": "fonte_finta:FonteFinta", "ogni": 60}), recente, NOW)
    assert is_due(crea_fonte({"nome": "a", "tipo": "fonte_finta:FonteFinta", "ogni": 60}), SourceState(), NOW)


def test_giro_con_fonti_miste(tmp_path):
    from fonte_finta import FonteFinta

    cfg = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var")},
        "canali": [{"nome": "canale_test", "cartella": "informatica", "attivo": False}],
        "fonti": [
            {"nome": "feed", "tipo": "rss", "cartella": "informatica", "url": "https://example.com/feed.xml"},
            {"nome": "finta", "tipo": "fonte_finta:FonteFinta", "cartella": "casa", "n": 2, "ogni": 60},
        ],
        "regole": [{"nome": "aw", "parole": ["apple watch"], "prezzo_max": 250, "canali": ["informatica"]}],
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    config = load_config(tmp_path / "config.yaml")
    assert [f.tipo for f in config.fonti] == ["telegram", "rss", "finta"] and config.cartelle() == {"informatica": ["feed"], "casa": ["finta"]}

    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=RSS) if "feed.xml" in str(r.url) else httpx.Response(404))
    FonteFinta.chiamate = 0
    with Store(tmp_path / "var" / "db.sqlite") as store:
        client = Client("ua", courtesy=0, transport=transport, sleep=lambda s: None)
        s = run_fetch(config, store, client, None, now=NOW)
        assert s.ok == ["feed", "finta"] and len(s.new_offers) == 4 and s.matches == {"aw": 1}
        aw = store.offers_for_rule("aw", "2026-01-01", 10)[0]
        assert (aw.price, aw.old_price, aw.discount) == (199.0, 279.0, 29)
        assert aw.link == "https://example.com/offerte/apple-watch-se" and aw.channels == ["feed"]
        assert store.post_exists("finta", "f1")
        s2 = run_fetch(config, store, client, None, now=NOW + timedelta(minutes=5))
        assert s2.ok == ["feed"] and FonteFinta.chiamate == 1  # ogni: 60 → la fonte finta salta il secondo giro
        assert s2.new_posts == 0

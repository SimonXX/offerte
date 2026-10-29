"""Contratto di dashboard.json, scrittura dei file, pulizia, parametri e prestazioni."""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from demo_dati import crea_db
from offerte.cli import main
from offerte.config import ConfigError, load_config
from offerte.feeds import (DASHBOARD_ASSET, dashboard_bytes, dashboard_cartelle, dashboard_fonti,
                           dashboard_offerta, dashboard_regole, item_name, safe_url, write_dashboard, write_feeds)
from offerte.store import Offer, Store

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
CHIAVI_TESTA = ["v", "generato", "finestra_giorni", "troncato", "cartelle", "regole", "fonti", "offerte"]
CHIAVI_OFFERTA = {"id", "t", "n", "x", "k", "p", "b", "s", "c", "u", "m", "i"}


def offerta(**kw) -> Offer:
    base = dict(id=1, key="k", title="Cuffie Sony", text="Cuffie Sony\n29,99€", link="https://shop.example.com/p",
                permalink="https://t.me/alfa/1", image=None, price=29.99, old_price=None, discount=None,
                coupon=None, posted_at="2026-10-27T08:15:00+00:00", first_seen="", last_seen="",
                channels=["alfa"], n_posts=1)
    return Offer(**{**base, **kw})


def config_demo(tmp_path, parametri=None, canali=None, regole=None):
    dati = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var"), **(parametri or {})},
        "canali": canali or [{"nome": "alfa", "cartella": "Informatica"}, {"nome": "beta", "cartella": "informatica"},
                             {"nome": "gamma", "cartella": "casa", "attivo": False}],
        "regole": regole if regole is not None else [
            {"nome": "ssd sotto 60", "parole": ["ssd", r"/\b[12]\s?tb\b/"], "escludi": ["usato"],
             "prezzo_max": 60, "sconto_min": 30, "canali": ["Informatica"]}],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(dati, allow_unicode=True), encoding="utf-8")
    return load_config(path)


def doc_da(offerte, config=None, store=None, **kw):
    cartelle = dashboard_cartelle(config) if config else {}
    regole = dashboard_regole(config) if (config and config.parametri.dashboard_regole) else []
    fonti = dashboard_fonti(config, store) if (config and store) else []
    dati = dashboard_bytes(offerte, cartelle, regole, fonti, kw.pop("now", NOW), kw.pop("giorni", 14), **kw)
    return json.loads(dati), dati


# --- A2, A3: contratto -------------------------------------------------------

def test_head_e_tipi(tmp_path):
    config = config_demo(tmp_path)
    with Store(":memory:") as store:
        doc, _ = doc_da([offerta()], config, store)
    assert list(doc) == CHIAVI_TESTA
    assert doc["v"] == 1 and doc["generato"] == int(NOW.timestamp())
    assert doc["finestra_giorni"] == 14 and doc["troncato"] is False
    assert isinstance(doc["cartelle"], dict) and isinstance(doc["regole"], list) and isinstance(doc["fonti"], list)


def test_contratto_offerta():
    voce = dashboard_offerta(offerta(id=7, price=0.0, old_price=99.0, discount=100, coupon="X1",
                                     image="https://cdn.example.com/a.jpg"))
    assert set(voce) <= CHIAVI_OFFERTA
    assert voce["id"] == 7 and voce["t"] == 1793088900 and voce["n"] == "Cuffie Sony"
    assert voce["p"] == 0.0 and voce["b"] == 99.0 and voce["s"] == 100 and voce["c"] == "X1"
    assert voce["u"] == "https://shop.example.com/p" and voce["m"] == "https://t.me/alfa/1"
    assert voce["i"] == "https://cdn.example.com/a.jpg"
    assert isinstance(voce["k"], list) and voce["x"] == "Cuffie Sony\n29,99€"
    # i campi assenti si omettono, non diventano null
    scarna = dashboard_offerta(offerta(price=None, old_price=None, discount=None, coupon="", image=None))
    assert set(scarna) == {"id", "t", "n", "x", "k", "u", "m"}


def test_nessun_null(tmp_path):
    config = config_demo(tmp_path)
    with Store(":memory:") as store:
        doc, dati = doc_da([offerta(), offerta(id=2, price=None, image=None, link=None)], config, store)

    def nessun_none(valore):
        if isinstance(valore, dict):
            return all(v is not None and nessun_none(v) for v in valore.values())
        if isinstance(valore, list):
            return all(v is not None and nessun_none(v) for v in valore)
        return True

    assert nessun_none(doc)
    assert b":null" not in dati and b",null" not in dati and b"[null" not in dati


# --- A4, A5: ordine, finestra, troncamento -----------------------------------

def test_ordine_e_finestra(tmp_path):
    base = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
    offerte = [offerta(id=i, posted_at=(base - timedelta(hours=i)).isoformat(timespec="seconds")) for i in (3, 1, 2)]
    offerte.append(offerta(id=9, posted_at=base.isoformat(timespec="seconds")))  # stessa data dell'id 0
    doc, _ = doc_da(list(reversed(offerte)))
    assert [o["id"] for o in doc["offerte"]] == [9, 1, 2, 3]


def test_finestra_esclude_le_vecchie(tmp_path):
    config = config_demo(tmp_path, {"feed_giorni": 7})
    with Store(tmp_path / "var" / "db.sqlite") as store:
        dentro = store.insert_offer(key="a", title="Dentro", text="t", link=None, permalink="p", image=None,
                                    price=None, old_price=None, discount=None, coupon=None,
                                    posted_at=(NOW - timedelta(days=2)).isoformat(timespec="seconds"),
                                    channel="alfa", now="2026-10-25T12:00:00+00:00")
        store.insert_offer(key="b", title="Fuori", text="t", link=None, permalink="p", image=None, price=None,
                           old_price=None, discount=None, coupon=None,
                           posted_at=(NOW - timedelta(days=30)).isoformat(timespec="seconds"),
                           channel="alfa", now="2026-09-27T12:00:00+00:00")
        write_dashboard(store, config, NOW)
    doc = json.loads((config.parametri.var_dir / "feeds" / "dashboard.json").read_text(encoding="utf-8"))
    assert [o["id"] for o in doc["offerte"]] == [dentro]


def test_troncamento():
    base = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
    offerte = [offerta(id=i, posted_at=(base - timedelta(hours=i)).isoformat(timespec="seconds")) for i in range(5)]
    doc, _ = doc_da(offerte, max_offerte=2)
    assert doc["troncato"] is True and [o["id"] for o in doc["offerte"]] == [0, 1]


# --- A6, A7: cartelle, regole, fonti -----------------------------------------

def test_cartelle_tutte_minuscole(tmp_path):
    config = config_demo(tmp_path)
    assert dashboard_cartelle(config) == {"casa": ["gamma"], "informatica": ["alfa", "beta"]}


def test_regole_sorgenti(tmp_path):
    config = config_demo(tmp_path)
    (regola,) = dashboard_regole(config)
    assert regola["nome"] == "ssd sotto 60" and regola["slug"] == "ssd-sotto-60"
    assert regola["parole"] == ["ssd", r"/\b[12]\s?tb\b/"] and regola["escludi"] == ["usato"]
    assert regola["canali"] == ["informatica"] and regola["prezzo_max"] == 60.0 and regola["sconto_min"] == 30
    assert regola["tutte"] is False and regola["solo_coupon"] is False
    assert "prezzo_min" not in regola

    spenta = config_demo(tmp_path, {"dashboard_regole": False})
    with Store(":memory:") as store:
        doc, _ = doc_da([offerta()], spenta, store)
    assert doc["regole"] == []


def test_fonti_con_stato(tmp_path):
    config = config_demo(tmp_path)
    with Store(":memory:") as store:
        store.update_channel("alfa", status="vuota", now="2026-10-27T11:50:00+00:00")
        fonti = dashboard_fonti(config, store)
    assert [f["nome"] for f in fonti] == ["alfa", "beta", "gamma"]
    assert fonti[0] == {"nome": "alfa", "cartella": "informatica", "ogni": 0, "attiva": True,
                        "ultimo_fetch": 1793101800, "stato": "vuota"}
    assert fonti[2]["attiva"] is False and "stato" not in fonti[2]  # mai letta


# --- A8, A9: URL e nomi -------------------------------------------------------

@pytest.mark.parametrize("u", ["javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "ftp://e.com/f", "", None])
def test_safe_url_scarta(u):
    assert safe_url(u) is None


def test_url_non_sicuri():
    voce = dashboard_offerta(offerta(link="javascript:alert(1)", image="data:text/html,x",
                                     permalink="https://t.me/alfa/1"))
    assert voce["u"] == "https://t.me/alfa/1"  # ripiego sul permalink
    assert "m" not in voce and "i" not in voce
    senza = dashboard_offerta(offerta(link="javascript:alert(1)", permalink="tg://x", image=None))
    assert "u" not in senza and "m" not in senza


def test_item_name_senza_testo():
    assert item_name(offerta(title=None, text="")) == "(senza titolo)"
    assert item_name(offerta(title=None, text="Prima riga\nseconda")) == "Prima riga"
    assert dashboard_offerta(offerta(title=None, text=""))["n"] == "(senza titolo)"


# --- A10, A11, A14: scrittura su disco ----------------------------------------

def test_write_feeds_scrive_dashboard(tmp_path):
    config = config_demo(tmp_path)
    feeds = config.parametri.var_dir / "feeds"
    with Store(tmp_path / "var" / "db.sqlite") as store:
        write_feeds(store, config, NOW)
        for nome in (*DASHBOARD_ASSET, "dashboard.json"):
            assert (feeds / nome).exists(), nome
        assert "href='dashboard.html'" in (feeds / "index.html").read_text(encoding="utf-8")

        vecchio = feeds / "cartella" / "vecchia.json"
        vecchio.write_text("{}", encoding="utf-8")
        write_feeds(store, config, NOW + timedelta(minutes=10))
        assert not vecchio.exists()
        for nome in (*DASHBOARD_ASSET, "dashboard.json"):
            assert (feeds / nome).exists(), nome


def test_asset_non_riscritti(tmp_path):
    config = config_demo(tmp_path)
    feeds = config.parametri.var_dir / "feeds"
    with Store(tmp_path / "var" / "db.sqlite") as store:
        write_dashboard(store, config, NOW)
        prima = {nome: (feeds / nome).stat().st_mtime_ns for nome in DASHBOARD_ASSET}
        time.sleep(0.01)
        write_dashboard(store, config, NOW + timedelta(minutes=10))
        assert {nome: (feeds / nome).stat().st_mtime_ns for nome in DASHBOARD_ASSET} == prima


def test_dashboard_disattivata(tmp_path):
    config = config_demo(tmp_path)
    feeds = config.parametri.var_dir / "feeds"
    with Store(tmp_path / "var" / "db.sqlite") as store:
        write_feeds(store, config, NOW)
        assert (feeds / "dashboard.json").exists()
        spenta = config_demo(tmp_path, {"dashboard": False})
        write_feeds(store, spenta, NOW + timedelta(minutes=10))
    for nome in (*DASHBOARD_ASSET, "dashboard.json"):
        assert not (feeds / nome).exists(), nome
    assert "dashboard.html" not in (feeds / "index.html").read_text(encoding="utf-8")


def test_opml(tmp_path):
    import xml.etree.ElementTree as ET
    config = config_demo(tmp_path, {"feed_base_url": "https://utente.github.io/offerte"},
                         canali=[{"nome": "alfa", "cartella": "informatica"}, {"nome": "gamma", "cartella": "casa"}],
                         regole=[{"nome": "ssd sotto 60", "parole": ["ssd"]}])
    with Store(tmp_path / "var" / "db.sqlite") as store:
        scritti = write_feeds(store, config, NOW)
    radice = ET.fromstring((config.parametri.var_dir / "feeds" / "feeds.opml").read_bytes())
    url = {o.get("xmlUrl") for o in radice.iter("outline") if o.get("xmlUrl")}
    assert len(url) == len(scritti) == 3
    assert "https://utente.github.io/offerte/cartella/casa.xml" in url
    assert "https://utente.github.io/offerte/cartella/informatica.xml" in url
    assert "https://utente.github.io/offerte/regola/ssd-sotto-60.xml" in url
    assert "feeds.opml" in (config.parametri.var_dir / "feeds" / "index.html").read_text(encoding="utf-8")


# --- A13, A15, A16 ------------------------------------------------------------

def test_params_da_yaml(tmp_path):
    config = config_demo(tmp_path, {"dashboard": False, "dashboard_regole": False, "dashboard_max_offerte": 5})
    p = config.parametri
    assert (p.dashboard, p.dashboard_regole, p.dashboard_max_offerte) == (False, False, 5)
    (tmp_path / "brutta.yaml").write_text("parametri: {dashbord: true}\ncanali: [{nome: a}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="chiavi sconosciute"):
        load_config(tmp_path / "brutta.yaml")


def test_feed_cli(tmp_path, capsys):
    config = config_demo(tmp_path)
    crea_db(config.parametri.var_dir / "offerte.sqlite", n=20, now=NOW).close()
    assert main(["-c", str(config.path), "feed"]) == 0
    assert "scritti 3 feed" in capsys.readouterr().out
    doc = json.loads((config.parametri.var_dir / "feeds" / "dashboard.json").read_text(encoding="utf-8"))
    assert len(doc["offerte"]) > 0


def test_prestazioni_6000(tmp_path):
    with crea_db(":memory:", n=6000, now=NOW) as store:
        offerte = store.offers_since((NOW - timedelta(days=14)).isoformat(timespec="seconds"))
        assert len(offerte) > 5000
        inizio = time.perf_counter()
        dati = dashboard_bytes(offerte, {"informatica": ["alfa"]}, [], [], NOW, 14)
        durata = time.perf_counter() - inizio
    assert durata < 1.5, f"dashboard_bytes ha impiegato {durata:.2f} s"
    assert len(dati) < 8_000_000, f"dashboard.json di {len(dati)} byte"


# --- finestra della dashboard staccata da quella dei feed ------------------

def test_dashboard_giorni_allarga_la_finestra(tmp_path):
    """La pagina può guardare più indietro dei feed: i feed restano a feed_giorni, il JSON no."""
    config = config_demo(tmp_path, {"feed_giorni": 7, "dashboard_giorni": 60})
    with Store(tmp_path / "var" / "db.sqlite") as store:
        for giorni, chiave in ((2, "recente"), (20, "media"), (90, "antica")):
            store.insert_offer(key=chiave, title=chiave, text="t", link=None, permalink="p", image=None,
                               price=None, old_price=None, discount=None, coupon=None,
                               posted_at=(NOW - timedelta(days=giorni)).isoformat(timespec="seconds"),
                               channel="alfa", now="2026-01-01T00:00:00+00:00")
        write_feeds(store, config, NOW)
    doc = json.loads((config.parametri.var_dir / "feeds" / "dashboard.json").read_text(encoding="utf-8"))
    assert doc["finestra_giorni"] == 60
    assert sorted(o["n"] for o in doc["offerte"]) == ["media", "recente"]


def test_dashboard_giorni_assente_segue_i_feed(tmp_path):
    config = config_demo(tmp_path, {"feed_giorni": 21})
    assert config.parametri.dashboard_giorni is None
    with Store(":memory:") as store:
        write_dashboard(store, config, NOW)
    doc = json.loads((config.parametri.var_dir / "feeds" / "dashboard.json").read_text(encoding="utf-8"))
    assert doc["finestra_giorni"] == 21


def test_dashboard_giorni_non_valido(tmp_path):
    (tmp_path / "brutta.yaml").write_text(
        "parametri: {dashboard_giorni: 0}\ncanali: [{nome: a}]\nregole: [{nome: r, parole: [ssd]}]\n",
        encoding="utf-8")
    with pytest.raises(ConfigError, match="dashboard_giorni deve essere almeno 1"):
        load_config(tmp_path / "brutta.yaml")

from datetime import datetime

from offerte.dedupe import offer_key, text_key
from offerte.fetch import process_message
from offerte.parser import Message
from offerte.store import Store

NOW = "2026-10-27T12:00:00+00:00"
SINCE = "2026-10-20T12:00:00+00:00"


class NoResolve:
    def resolve(self, url):
        raise AssertionError("nessun redirect da risolvere qui")


def msg(channel, msg_id, text, links=(), date="2026-10-27T10:00:00+00:00"):
    return Message(channel, msg_id, datetime.fromisoformat(date), text, [], list(links), None, f"https://t.me/{channel}/{msg_id}")


def test_chiave_url_oppure_testo():
    assert offer_key("https://www.amazon.it/dp/B08GLX7TNT?tag=a-21", "x") == "url:amazon.it/dp/B08GLX7TNT"
    assert offer_key(None, "🔥 Offerta SSD 1TB a 59,99€ #ad") == offer_key(None, "Offerta SSD 1TB a 59,99€ @canale")
    assert text_key("SSD 1TB 59,99€") != text_key("SSD 2TB 99,99€")


def test_stesso_link_da_due_canali(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        a, nuova_a = process_message(store, NoResolve(), msg("alfa", 1, "SSD 1TB\n59,99€", ["https://www.amazon.it/dp/B08GLX7TNT?tag=alfa-21"]), now=NOW, dedupe_since=SINCE)
        b, nuova_b = process_message(store, NoResolve(), msg("beta", 7, "Super SSD\n59,99€ invece di 99€", ["https://amazon.it/Samsung/dp/B08GLX7TNT/ref=x?tag=beta-21"]), now=NOW, dedupe_since=SINCE)
        assert (nuova_a, nuova_b) == (True, False) and a == b
        o = store.get_offer(a)
        assert o.channels == ["alfa", "beta"] and o.n_posts == 2
        assert o.link == "https://www.amazon.it/dp/B08GLX7TNT?tag=alfa-21"  # il primo canale tiene il suo tag
        c, nuova_c = process_message(store, NoResolve(), msg("alfa", 2, "SSD 2TB\n99,99€", ["https://www.amazon.it/dp/B0B7CMZ3QH"]), now=NOW, dedupe_since=SINCE)
        assert nuova_c and c != a


def test_stesso_testo_senza_link(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        a, _ = process_message(store, NoResolve(), msg("alfa", 1, "🔥 Sconto 20% su tutto con il codice PROMO20 #ad"), now=NOW, dedupe_since=SINCE)
        b, nuova = process_message(store, NoResolve(), msg("beta", 1, "Sconto 20% su tutto con il codice PROMO20\n@beta"), now=NOW, dedupe_since=SINCE)
        assert a == b and not nuova
        assert store.get_offer(a).channels == ["alfa", "beta"]


def test_ripubblicata_dopo_la_finestra(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        link = ["https://www.amazon.it/dp/B08GLX7TNT"]
        a, _ = process_message(store, NoResolve(), msg("alfa", 1, "SSD", link), now=NOW, dedupe_since=SINCE)
        b, nuova = process_message(store, NoResolve(), msg("alfa", 2, "SSD", link), now="2026-11-10T12:00:00+00:00", dedupe_since="2026-11-03T12:00:00+00:00")
        assert nuova and b != a

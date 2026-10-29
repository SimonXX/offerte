from offerte.store import Store


def test_purge(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        args = dict(title=None, text="t", link=None, permalink="p", image=None, price=None, old_price=None,
                    discount=None, coupon=None, channel="a")
        vecchia = store.insert_offer(key="k1", posted_at="2026-01-01T00:00:00+00:00", now="2026-01-01T00:00:00+00:00", **args)
        nuova = store.insert_offer(key="k2", posted_at="2026-10-27T00:00:00+00:00", now="2026-10-27T00:00:00+00:00", **args)
        store.add_post("a", 1, vecchia, "2026-01-01T00:00:00+00:00", "p")
        store.add_match("r", vecchia, "2026-01-01T00:00:00+00:00")
        store.mark_notified(vecchia, "2026-01-01T00:00:00+00:00")
        store.set_redirect("https://s.ho/rt", "https://lungo", "2026-01-01T00:00:00+00:00")
        assert store.purge("2026-06-01T00:00:00+00:00", vacuum=True) == 1
        assert store.counts() == {"offers": 1, "posts": 0, "channels": 0}
        assert store.get_offer(nuova).key == "k2" and not store.is_notified(vecchia)
        assert store.get_redirect("https://s.ho/rt") is None


def offerta(store, key, posted_at, channel="a", price=None):
    return store.insert_offer(key=key, title=None, text="t", link=None, permalink="p", image=None, price=price,
                              old_price=None, discount=None, coupon=None, posted_at=posted_at, channel=channel,
                              now=posted_at)


def test_pending_notifications(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        recente = offerta(store, "k1", "2026-10-27T10:00:00+00:00")
        vecchia = offerta(store, "k2", "2026-10-01T10:00:00+00:00")
        gia_inviata = offerta(store, "k3", "2026-10-27T11:00:00+00:00")
        senza_notify = offerta(store, "k4", "2026-10-27T11:30:00+00:00")
        for offer_id in (recente, vecchia, gia_inviata):
            store.add_match("ssd", offer_id, "2026-10-27T12:00:00+00:00")
        store.add_match("cuffie", recente, "2026-10-27T12:00:00+00:00")
        store.add_match("muta", senza_notify, "2026-10-27T12:00:00+00:00")
        store.mark_notified(gia_inviata, "2026-10-27T12:00:00+00:00")

        in_coda = store.pending_notifications(["ssd", "cuffie"], "2026-10-26T12:00:00+00:00")
        assert [(o.id, regole) for o, regole in in_coda] == [(recente, ["cuffie", "ssd"])]
        assert store.pending_notifications([], "2026-10-26T12:00:00+00:00") == []


def test_touch_offer_e_offers_for_channels(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        uno = offerta(store, "k1", "2026-10-27T10:00:00+00:00", channel="alfa", price=19.99)
        store.add_post("alfa", 1, uno, "2026-10-27T10:00:00+00:00", "p")
        store.touch_offer(uno, "beta", "2026-10-27T11:00:00+00:00")
        store.touch_offer(uno, "beta", "2026-10-27T11:30:00+00:00")  # stesso canale: non si duplica
        store.add_post("beta", 7, uno, "2026-10-27T11:00:00+00:00", "p")
        due = offerta(store, "k2", "2026-10-26T10:00:00+00:00", channel="gamma")
        store.add_post("gamma", 2, due, "2026-10-26T10:00:00+00:00", "p")

        o = store.get_offer(uno)
        assert o.channels == ["alfa", "beta"] and o.n_posts == 3 and o.last_seen == "2026-10-27T11:30:00+00:00"
        assert [x.id for x in store.offers_for_channels(["beta"], "2026-01-01", 10)] == [uno]
        assert [x.id for x in store.offers_for_channels(["alfa", "gamma"], "2026-01-01", 10)] == [uno, due]
        assert store.offers_for_channels([], "2026-01-01", 10) == []
        assert [x.id for x in store.offers_for_channels(["alfa", "gamma"], "2026-10-27", 10)] == [uno]

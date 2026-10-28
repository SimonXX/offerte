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

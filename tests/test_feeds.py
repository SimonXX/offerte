from offerte.feeds import fmt_price, item_name, item_title
from offerte.store import Offer


def offer(**kw):
    base = dict(id=1, key="k", title="Cuffie Sony", text="Cuffie Sony\n29,99€", link=None, permalink="p", image=None,
                price=None, old_price=None, discount=None, coupon=None, posted_at="2026-10-27T08:15:00+00:00",
                first_seen="", last_seen="", channels=["alfa"], n_posts=1)
    return Offer(**{**base, **kw})


def test_formato_prezzo():
    assert fmt_price(29.99) == "29,99€"
    assert fmt_price(1299.5) == "1.299,50€"


def test_titolo_elemento():
    assert item_title(offer()) == "Cuffie Sony"
    assert item_title(offer(price=29.99)) == "Cuffie Sony, 29,99€"
    assert item_title(offer(price=29.99, discount=40)) == "Cuffie Sony, 29,99€ (-40%)"
    assert item_title(offer(title=None, text="Prima riga lunga\nseconda")) == "Prima riga lunga"


def test_nome_elemento():
    """item_name è il nome senza prezzo: lo usano la dashboard e item_title."""
    assert item_name(offer()) == "Cuffie Sony"
    assert item_name(offer(title=None, text="Prima riga lunga\nseconda")) == "Prima riga lunga"
    assert item_name(offer(title=None, text="")) == "(senza titolo)"
    assert item_name(offer(title="", text="")) == "(senza titolo)"
    assert item_name(offer(title=None, text="x" * 200)) == "x" * 80
    assert item_title(offer(title=None, text="", price=29.99)) == "(senza titolo), 29,99€"

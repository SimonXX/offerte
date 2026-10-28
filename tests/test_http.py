import httpx
import pytest

from offerte.http import Client, FetchError


def transport_con(risposte):
    chiamate = []

    def handler(request):
        chiamate.append(request.url.path)
        return risposte.pop(0)

    return httpx.MockTransport(handler), chiamate


def test_backoff_su_429_e_5xx_poi_ok():
    transport, chiamate = transport_con([
        httpx.Response(429, headers={"Retry-After": "5"}), httpx.Response(503), httpx.Response(200, text="ok")])
    attese = []
    c = Client("ua", courtesy=0, transport=transport, sleep=attese.append)
    assert c.get("https://t.me/s/x").text == "ok"
    assert len(chiamate) == 3
    assert attese == [5.0, 10.0]


def test_404_non_riprova():
    transport, chiamate = transport_con([httpx.Response(404)])
    with pytest.raises(FetchError):
        Client("ua", courtesy=0, transport=transport, sleep=lambda s: None).get("https://t.me/s/x")
    assert len(chiamate) == 1


def test_5xx_esaurisce_i_tentativi():
    transport, chiamate = transport_con([httpx.Response(500)] * 3)
    attese = []
    with pytest.raises(FetchError):
        Client("ua", courtesy=0, max_retries=2, transport=transport, sleep=attese.append).get("https://t.me/s/x")
    assert len(chiamate) == 3 and attese == [2.0, 4.0]


def test_intervallo_di_cortesia():
    transport, _ = transport_con([httpx.Response(200), httpx.Response(200)])
    attese = []
    c = Client("ua", courtesy=3, transport=transport, sleep=attese.append, clock=lambda: 0.0)
    c.get("https://t.me/s/a")
    c.get("https://t.me/s/b")
    assert attese == [3.0]

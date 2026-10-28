import pytest

from offerte.parser import parse_page


@pytest.fixture
def pagina1(fixture_html):
    return parse_page(fixture_html("canale_pagina1.html"), "canale_test")


@pytest.fixture
def per_id(pagina1):
    return {m.id: m for m in pagina1.messages}


def test_pagina_completa(pagina1):
    assert pagina1.has_preview
    assert pagina1.title == "Canale Test Offerte"
    assert pagina1.ids == [101, 102, 103, 104, 105, 106]
    # il messaggio di servizio (101) e la foto senza testo (104) non sono offerte
    assert [m.id for m in pagina1.messages] == [102, 103, 105, 106]


def test_foto_e_link_nel_testo(per_id):
    m = per_id[102]
    assert m.date.isoformat() == "2026-10-27T08:15:00+00:00"
    assert m.text.splitlines()[0] == "⚡ SSD Samsung 980 PRO 1TB NVMe PCIe 4.0"
    assert "79,99€ invece di 129,99€" in m.text
    assert "#Amazon" in m.text  # gli hashtag restano nel testo ma non fra i link
    assert m.links == ["https://amzn.to/3abcDEF", "http://t.me/canale_test_gruppo"]
    assert m.image == "https://cdn4.telesco.pe/file/foto102.jpg"
    assert m.permalink == "https://t.me/canale_test/102"
    assert m.struck == []


def test_pulsante_barrato_e_anteprima(per_id):
    m = per_id[103]
    # pulsante e anteprima puntano allo stesso URL: compare una volta, con le entità decodificate
    assert m.links == ["https://www.amazon.it/dp/B0BS1RNG7Y/?tag=canale-21&linkCode=ll1&ref_=as_li_ss_tl"]
    assert m.struck == ["49,99€"]
    assert m.image == "https://cdn4.telesco.pe/file/anteprima103.jpg"
    assert "Coupon: SONY10" in m.text


def test_solo_testo(per_id):
    m = per_id[105]
    assert m.links == ["https://t.me/canale_test", "https://t.me/canale_test_gruppo"]
    assert m.image is None


def test_link_immagine_e_pulsante(per_id):
    m = per_id[106]
    assert m.links[0] == "https://www.amazon.it/dp/B01M714FZX/?tag=amzproductid-21"
    assert "https://m.media-amazon.com/images/I/51pGibfNNuL._SL500_.jpg" in m.links
    assert m.image == "https://cdn4.telesco.pe/file/anteprima106.jpg"
    assert m.text.splitlines()[0] == "🚨ERRORE DI PREZZO🚨"


def test_pagina_storico(fixture_html):
    page = parse_page(fixture_html("canale_pagina2.html"), "canale_test")
    assert page.ids == [99, 100]
    assert [m.id for m in page.messages] == [99, 100]
    # le entità doppie dei post reali arrivano decodificate una volta sola: le finisce links.normalize_input
    assert "&amp;quantity=1" in page.messages[0].links[1]


def test_senza_anteprima(fixture_html):
    page = parse_page(fixture_html("senza_anteprima.html"), "privato")
    assert not page.has_preview
    assert page.messages == [] and page.ids == []

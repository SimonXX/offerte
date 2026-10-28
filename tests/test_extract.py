import pytest

from offerte.extract import extract, extract_prices, find_coupon, find_discount, find_prices, product_name


@pytest.mark.parametrize("testo, atteso", [
    ("19,99€", 19.99),
    ("€ 19.99", 19.99),
    ("19,99 euro", 19.99),
    ("1.299,00 €", 1299.0),
    ("€1.299", 1299.0),
    ("19€", 19.0),
    ("19.99 EUR", 19.99),
    ("€1,299.00", 1299.0),
    ("a soli 5,5€", 5.5),
    ("10.000€", 10000.0),
])
def test_formati_prezzo(testo, atteso):
    assert [p for p, _ in find_prices(testo)] == [atteso]


def test_numeri_senza_valuta_ignorati():
    assert find_prices("Samsung 980 PRO 1TB, 7000 MB/s, 5 anni di garanzia, 2024") == []


@pytest.mark.parametrize("testo, struck, atteso", [
    ("💰 82,69€ invece di 169,99€", [], (82.69, 169.99)),
    ("💶 A 13,08€\n❌ Invece di 34,90€", [], (13.08, 34.90)),
    ("€ 29.99 49,99€ (-40%)", ["49,99€"], (29.99, 49.99)),
    ("Prezzo 19,99€ 29,99€", [], (19.99, 29.99)),
    ("da 80,00€ a 20,00€", [], (20.0, 80.0)),
    ("Solo 13,08€", [], (13.08, None)),
    ("39€ invece di 29€", [], (39.0, None)),
    ("Nessun prezzo qui", [], (None, None)),
])
def test_prezzo_attuale_e_barrato(testo, struck, atteso):
    assert extract_prices(testo, struck) == atteso


def test_sconto():
    assert find_discount("📉 Sconto: 63%") == 63
    assert find_discount("29,99€ (-40%)") == 40
    assert find_discount("100% cotone") is None
    assert extract("Cuffie\n79,99€ invece di 129,99€").discount == 38  # calcolato


def test_coupon():
    assert find_coupon("🎟 Coupon: SONY10") == "SONY10"
    assert find_coupon("codice sconto XYZ123 al checkout") == "XYZ123"
    assert find_coupon("applica il coupon del 20% in pagina") is None
    assert find_coupon("COUPON AMAZON da spuntare") is None


def test_nome_prodotto():
    assert product_name("⚡ SSD Samsung 980 PRO 1TB a 79,99€\n\n👉 link") == "SSD Samsung 980 PRO 1TB"
    assert product_name("🚨ERRORE DI PREZZO🚨\n\n💥 Mikado Cioccolato Fondente, 24x39g\n\n💶 A 13,08€") == "Mikado Cioccolato Fondente, 24x39g"
    assert product_name("🔥🔥🔥\n\nRobot aspirapolvere Xiaomi\n199 euro") == "Robot aspirapolvere Xiaomi"
    assert product_name("") is None


def test_estrazione_completa():
    ex = extract("🔥 Cuffie Sony WH-CH520 Bluetooth\n\n💶 € 29.99 49,99€ (-40%)\n🎟 Coupon: SONY10", struck=["49,99€"])
    assert (ex.title, ex.price, ex.old_price, ex.discount, ex.coupon) == ("Cuffie Sony WH-CH520 Bluetooth", 29.99, 49.99, 40, "SONY10")

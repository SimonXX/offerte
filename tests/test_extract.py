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


@pytest.mark.parametrize("testo, atteso", [
    ("SSD Samsung 980 1TB 79,99€\nCoupon 10€ in pagina", (79.99, None)),
    ("Cuffie Sony WH-1000XM5 289€\nSpedizione 4,99€", (289.0, None)),
    ("Echo Dot 29,99€\nCashback 5€ con PayPal", (29.99, None)),
    ("59,90€ + spedizione 4,99€", (59.90, None)),
    ("Sconto di 30€ sul totale, prezzo finale 199€", (199.0, None)),
    ("59,90€ spedizione gratuita", (59.90, None)),
])
def test_importi_di_rumore_non_sono_il_prezzo(testo, atteso):
    assert extract_prices(testo) == atteso


@pytest.mark.parametrize("testo, atteso", [
    ("Fotocamera 199€", 199.0),      # "era" dentro "Fotocamera" non è un indizio di prezzo pieno
    ("Lampada 9,99€", 9.99),         # né "da" dentro "Lampada"
    ("Scheda 80€", 80.0),
    ("Cuffie a partire da 19,99€", 19.99),   # "a partire da" è il prezzo minimo attuale
])
def test_indizi_di_barrato_con_confine_di_parola(testo, atteso):
    assert extract_prices(testo) == (atteso, None)


def test_simbolo_come_prefisso_non_ruba_il_numero_precedente():
    assert extract_prices("Apple Watch Series 9 € 299") == (299.0, None)
    assert extract_prices("Modello 2024 € 59,99") == (59.99, None)
    assert extract_prices("59,99 € 99,99 €") == (59.99, 99.99)  # con i decimali la guardia non scatta


def test_due_importi_solo_sulla_stessa_riga():
    assert extract_prices("Monitor 199€\nAbbonamento 9€ al mese") == (199.0, None)
    assert extract_prices("Monitor 199€ 299€") == (199.0, 299.0)


@pytest.mark.parametrize("segno", ["-", "\N{MINUS SIGN}", "\N{EN DASH}"])
def test_sconto_con_segno(segno):
    assert find_discount(f"Cashback 10% su Prime, {segno}40% oggi") == 40


def test_sconto_calcolato_batte_una_percentuale_estranea():
    ex = extract("Cuffie JBL 49,99€ invece di 79,99€ (IVA 22% inclusa)")
    assert (ex.price, ex.old_price, ex.discount) == (49.99, 79.99, 38)
    assert extract("SSD 1TB 59,99€ + cashback 5%").discount is None
    assert find_discount("Errore di prezzo: sconto 100%") == 100

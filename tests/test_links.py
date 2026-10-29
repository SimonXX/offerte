from offerte.links import clean_url, dedupe_key, is_short_link, pick_offer_link


def test_amazon_pulito_ma_con_tag():
    u = "https://www.amazon.it/Samsung-980-PRO/dp/B08GLX7TNT/ref=sr_1_1?tag=canale-21&linkCode=ll1&keywords=ssd&ref_=as_li_ss_tl&th=1#x"
    assert clean_url(u) == "https://www.amazon.it/dp/B08GLX7TNT?tag=canale-21"


def test_chiave_amazon_ignora_affiliate_e_tld_path():
    a = dedupe_key("https://www.amazon.it/dp/B08GLX7TNT?tag=a-21")
    b = dedupe_key("https://amazon.it/Samsung/dp/B08GLX7TNT/ref=x?tag=b-21&utm_source=tg")
    assert a == b == "url:amazon.it/dp/B08GLX7TNT"


def test_checkout_amazon_con_entita():
    u = "https://www.amazon.it/checkout/entry/buynow?buyNow=1&amp;quantity=1&amp;asin=B07BN21Y1J&amp;tag=errnew25-21"
    assert clean_url(u) == "https://www.amazon.it/checkout/entry/buynow?buyNow=1&quantity=1&asin=B07BN21Y1J&tag=errnew25-21"
    assert dedupe_key(u) == "url:amazon.it/dp/B07BN21Y1J"


def test_ebay():
    u = "https://www.ebay.it/itm/123456789?mkcid=1&campid=5338&hash=item1234:g:abc&utm_source=tg"
    assert clean_url(u) == "https://www.ebay.it/itm/123456789?mkcid=1&campid=5338"
    assert dedupe_key(u) == "url:ebay.it/itm/123456789"


def test_generico_conserva_query_funzionale():
    assert clean_url("https://shop.example.com/p?id=42&utm_campaign=x&fbclid=y") == "https://shop.example.com/p?id=42"
    assert dedupe_key("https://WWW.Example.com/a/b/?id=42&aff_id=9") == "url:example.com/a/b?id=42"


def test_scelta_link():
    assert pick_offer_link(["https://t.me/canale", "https://m.media-amazon.com/images/I/x.jpg", "https://amzn.to/abc"]) == "https://amzn.to/abc"
    assert pick_offer_link(["?q=%23tag", "https://t.me/x", "http://telegram.me/y"]) is None
    # pulsanti "seguici" prima dell'offerta vera, come su alcuni canali
    assert pick_offer_link(["https://linktr.ee/u_app", "https://chat.whatsapp.com/abc", "https://amzlink.to/az0x"]) == "https://amzlink.to/az0x"
    assert pick_offer_link(["https://assets.offerte.club/up.jpg?t=1", "https://ofclub.click/1n3n08j"]) == "https://ofclub.click/1n3n08j"


def test_short_link():
    assert is_short_link("https://amzn.to/3abcDEF")
    assert is_short_link("https://amzlink.to/az0H8zvgoKGOf")
    assert is_short_link("https://sconti.example/x7Yz9")
    assert not is_short_link("https://www.amazon.it/dp/B08GLX7TNT")
    assert not is_short_link("https://www.mediaworld.it/it/product/_x-123.html")


def test_entita_senza_punto_e_virgola_non_si_decodificano():
    u = "https://shop.example.com/p?id=1&currency=EUR&section=a&region=it&notify=1"
    assert clean_url(u) == u
    # le entità vere, anche doppie come nei post reali, si decodificano lo stesso
    assert clean_url("https://shop.example.com/p?a=1&amp;amp;b=2") == "https://shop.example.com/p?a=1&b=2"


def test_schemi_non_web_scartati():
    assert pick_offer_link(["tel:+390212345", "mailto:info@shop.it", "https://shop.example.com/p"]) == "https://shop.example.com/p"
    assert pick_offer_link(["tel:+390212345"]) is None
    assert pick_offer_link(["https://example.com:abc/x"]) is None  # porta non numerica

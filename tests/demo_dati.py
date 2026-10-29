"""Dati demo per sviluppare e collaudare la dashboard senza fare fetch.

Importabile dai test (`from demo_dati import crea_db, scrivi_config`) ed eseguibile a mano:

    uv run python tests/demo_dati.py /tmp/offerte-demo
    uv run offerte -c /tmp/offerte-demo/config.yaml serve
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from offerte.store import Store

CARTELLE = {
    "informatica": ["mttvideo", "mttgadgets", "prophecytechofferte", "prodigeekofferte", "prezzitech",
                    "offertesmartworld", "offertepuntotech", "vereoffertetech", "mvofferte", "offerten1tech"],
    "casa": ["erroridiprezzo", "erroridiprezzo_offertedalweb", "mttcasa"],
    "cina": ["mttcina"],
    "raffica": ["rafficaffari", "tecnofferte", "codiciscontotech"],
}
CANALI = [nome for nomi in CARTELLE.values() for nome in nomi]

PRODOTTI = [
    "SSD Samsung 980 PRO 1TB NVMe PCIe 4.0", "SSD Crucial P3 Plus 2TB", "Apple Watch SE 2024 40mm",
    "Apple Watch Series 9 45mm", "Cuffie Sony WH-1000XM5", "Robot aspirapolvere Xiaomi S20",
    "Friggitrice ad aria Ninja 7,6 litri", "Monitor LG UltraGear 27 pollici 180 Hz",
    "Mouse Logitech MX Master 3S", "Tastiera meccanica Keychron K2", "Caffè Lavazza Qualità Rossa 20 cialde",
    "Città del Capo, guida di viaggio illustrata", "Manuale di programmazione in C++ moderno",
    "Powerbank Anker 20000 mAh 65 W", "Smartphone Xiaomi Redmi Note 14 Pro", "Scheda microSD SanDisk 512 GB",
    "Set di pentole antiaderenti 10 pezzi", "Aspirapolvere senza filo Dyson V12",
    "Televisore Hisense 55 pollici QLED", "Zaino antifurto da 15,6 pollici",
]
CONTORNO = [
    "Prezzo più basso degli ultimi trenta giorni secondo lo storico del canale.",
    "Spedizione gratuita con Prime, consegna prevista in due giorni lavorativi.",
    "Disponibilità limitata: il venditore è Amazon, non un marketplace terzo.",
    "Segnalato da un utente del gruppo, verificato prima della pubblicazione.",
    "Garanzia Italia di due anni, fattura disponibile su richiesta nell'ordine.",
    "Il coupon va spuntato nella pagina del prodotto prima di aggiungerlo al carrello.",
    "Attenzione: il prezzo può tornare a salire nel giro di poche ore.",
]
OSTILI = [
    ("Offerta sospetta <img src=x onerror=alert(1)>", "javascript:alert(1)", "data:text/html,<script>alert(1)</script>"),
    ("Titolo con \"virgolette\" e <b>tag</b> & entità", "https://shop.example.com/p/ok", "data:image/png;base64,AAAA"),
    ("Prodotto con link storto", "ftp://example.com/file", "https://cdn.example.com/img.jpg"),
]


def _testo(rnd: random.Random, prodotto: str, prezzo: float | None, barrato: float | None,
           sconto: int | None, coupon: str | None) -> str:
    righe = [prodotto]
    if prezzo is not None:
        riga = f"{prezzo:.2f}".replace(".", ",") + "€"
        if barrato is not None:
            riga += f" invece di " + f"{barrato:.2f}".replace(".", ",") + "€"
        if sconto is not None:
            riga += f" (-{sconto}%)"
        righe.append(riga)
    if coupon:
        righe.append(f"Coupon: {coupon}")
    righe.extend(rnd.sample(CONTORNO, k=rnd.randint(2, 3)))
    return "\n".join(righe)


def crea_db(path: Path | str, n: int = 6000, now: datetime | None = None, seed: int = 7) -> Store:
    """Riempie uno Store con `n` offerte sintetiche deterministiche, distribuite negli ultimi 14 giorni."""
    rnd = random.Random(seed)
    adesso = now or datetime.now(timezone.utc)
    store = Store(path)
    for i in range(n):
        canale = CANALI[i % len(CANALI)]
        quando = adesso - timedelta(minutes=rnd.randint(1, 14 * 24 * 60))
        prodotto = rnd.choice(PRODOTTI)
        prezzo = round(rnd.uniform(4.99, 1299.0), 2) if rnd.random() < 0.80 else None
        sconto = rnd.randint(5, 85) if (prezzo is not None and rnd.random() < 0.50) else None
        barrato = round(prezzo / (1 - sconto / 100), 2) if (prezzo is not None and sconto) else None
        coupon = f"DEMO{rnd.randint(10, 99)}" if rnd.random() < 0.08 else None
        testo = _testo(rnd, prodotto, prezzo, barrato, sconto, coupon)
        link = f"https://www.amazon.it/dp/B{i:09d}?tag={canale[:8]}-21"
        offer_id = store.insert_offer(
            key=f"url:amazon.it/dp/B{i:09d}", title=prodotto, text=testo, link=link,
            permalink=f"https://t.me/{canale}/{1000 + i}",
            image=f"https://cdn4.telesco.pe/file/{seed:02d}{i:06d}_{rnd.randint(10**9, 10**10):d}.jpg",
            price=prezzo, old_price=barrato, discount=sconto, coupon=coupon,
            posted_at=quando.isoformat(timespec="seconds"), channel=canale,
            now=quando.isoformat(timespec="seconds"))
        store.add_post(canale, 1000 + i, offer_id, quando.isoformat(timespec="seconds"),
                       f"https://t.me/{canale}/{1000 + i}")
        if i % max(1, n // 15) == 0 and i:  # una quindicina di offerte viste su due canali
            altro = CANALI[(i + 5) % len(CANALI)]
            store.touch_offer(offer_id, altro, quando.isoformat(timespec="seconds"))
            store.add_post(altro, 50000 + i, offer_id, quando.isoformat(timespec="seconds"),
                           f"https://t.me/{altro}/{50000 + i}")
    for j, (testo, link, immagine) in enumerate(OSTILI):
        quando = adesso - timedelta(hours=j + 1)
        store.insert_offer(key=f"ostile:{j}", title=None, text=testo, link=link,
                           permalink=f"https://t.me/mttcasa/{90000 + j}", image=immagine,
                           price=19.99, old_price=None, discount=None, coupon=None,
                           posted_at=quando.isoformat(timespec="seconds"), channel="mttcasa",
                           now=quando.isoformat(timespec="seconds"))
    return store


def scrivi_config(cartella: Path | str, **parametri) -> Path:
    """config.yaml con i 17 canali e le tre regole del repository, con var_dir dentro `cartella`."""
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    dati = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(cartella / "var"), "feed_giorni": 14,
                      "feed_max_elementi": 200, **parametri},
        "canali": [{"nome": nome, "cartella": cartella_nome}
                   for cartella_nome, nomi in CARTELLE.items() for nome in nomi],
        "regole": [
            {"nome": "ssd-sotto-60", "parole": ["ssd", "nvme", r"/\b[12]\s?tb\b/"], "prezzo_max": 60,
             "canali": ["informatica"], "notify": False},
            {"nome": "apple-watch-sotto-250", "parole": ["apple watch", r"/\bwatch\s*(se|series|ultra)\b/"],
             "escludi": ["cinturino", "cover"], "prezzo_max": 250, "notify": False},
            {"nome": "errori-di-prezzo", "parole": ["errore di prezzo", r"/sconto:?\s*[7-9]\d\s?%/"],
             "canali": ["erroridiprezzo", "erroridiprezzo_offertedalweb"], "notify": False},
        ],
    }
    path = cartella / "config.yaml"
    path.write_text(yaml.safe_dump(dati, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    from offerte.config import load_config
    from offerte.feeds import write_feeds
    from offerte.fetch import iso
    from offerte.rules import apply_rules

    cartella = Path(argv[1] if len(argv) > 1 else "/tmp/offerte-demo")
    quante = int(argv[2]) if len(argv) > 2 else 600
    config = load_config(scrivi_config(cartella))
    adesso = datetime.now(timezone.utc)
    db = config.parametri.var_dir / "offerte.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)
    with crea_db(db, n=quante, now=adesso) as store:
        apply_rules(store, config.regole, since=iso(adesso - timedelta(days=14)), now=iso(adesso))
        scritti = write_feeds(store, config, adesso)
    print(f"{quante} offerte in {db}, {len(scritti)} feed in {config.parametri.var_dir / 'feeds'}")
    print(f"uv run offerte -c {config.path} serve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

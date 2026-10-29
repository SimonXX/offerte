"""Test di fumo della riga di comando: ogni sottocomando gira su un database temporaneo, senza rete."""

import re
from pathlib import Path

import pytest
import yaml

from datetime import datetime, timezone

from offerte.cli import main
from offerte.fetch import RunSummary
from offerte.store import Store

RADICE = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg(tmp_path):
    dati = {
        "parametri": {"intervallo_cortesia": 0, "var_dir": str(tmp_path / "var")},
        "fonti": [{"nome": "finta", "tipo": "fonte_finta:FonteFinta", "cartella": "casa", "n": 2}],
        "regole": [{"nome": "finto", "parole": ["prodotto"], "prezzo_max": 100}],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(dati, allow_unicode=True), encoding="utf-8")
    return str(path)


def test_config_mancante_esce_con_2(capsys, tmp_path):
    assert main(["-c", str(tmp_path / "assente.yaml"), "fonti"]) == 2
    assert "errore di configurazione" in capsys.readouterr().err


def test_fonti(cfg, capsys):
    assert main(["-c", cfg, "fonti"]) == 0
    out = capsys.readouterr().out
    assert "finta" in out and "casa" in out


def test_search_e_filtra_su_database_vuoto(cfg, capsys):
    assert main(["-c", cfg, "search", "ssd"]) == 0
    assert "nessuna offerta trovata" in capsys.readouterr().out
    assert main(["-c", cfg, "filtra", "ssd", "--prezzo-max", "60"]) == 0
    assert "nessuna offerta corrisponde" in capsys.readouterr().out


def test_filtra_regex_non_valida(cfg, capsys):
    assert main(["-c", cfg, "filtra", "/(/"]) == 2
    assert "regola non valida" in capsys.readouterr().err


def test_stats(cfg, capsys):
    assert main(["-c", cfg, "stats", "--giorni", "3"]) == 0
    out = capsys.readouterr().out
    assert "Offerte al giorno per canale" in out and "Regole scattate" in out


def test_pulisci(cfg, capsys):
    assert main(["-c", cfg, "pulisci", "--giorni", "30"]) == 0
    assert "tolte 0 offerte" in capsys.readouterr().out
    assert main(["-c", cfg, "pulisci", "--giorni", "0"]) == 0
    assert "ritenzione disattivata" in capsys.readouterr().out


def test_serve(cfg, monkeypatch):
    chiamate = []
    monkeypatch.setattr("offerte.cli.serve", lambda d, h, p: chiamate.append((str(d), h, p)))
    assert main(["-c", cfg, "serve", "--port", "9999"]) == 0
    assert chiamate and chiamate[0][1:] == ("127.0.0.1", 9999)


def test_fetch(cfg, monkeypatch):
    chiamate = []

    def finto_run_fetch(config, store, client, notifier, **kw):
        chiamate.append(kw)
        return RunSummary(ok=["finta"])

    monkeypatch.setattr("offerte.cli.run_fetch", finto_run_fetch)
    monkeypatch.setattr("offerte.cli.Client", lambda *a, **k: _ClientFinto())
    assert main(["-c", cfg, "fetch", "--senza-notifiche", "--storico", "2"]) == 0
    assert chiamate == [{"only": None, "pages": 2}]


def test_fetch_fonte_sconosciuta(cfg):
    assert main(["-c", cfg, "fetch", "--senza-notifiche", "--fonte", "boh"]) == 2


def test_prova(cfg, capsys, monkeypatch):
    monkeypatch.setattr("offerte.cli.Client", lambda *a, **k: _ClientFinto())
    assert main(["-c", cfg, "prova", "finta"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("2 elementi")
    # prezzo e link come li calcola process_message, non i campi grezzi del messaggio
    assert "10,00€" in out and "https://finta.example/p/0" in out


def test_prova_fonte_sconosciuta(cfg, capsys):
    assert main(["-c", cfg, "prova", "boh"]) == 2
    assert "non in config" in capsys.readouterr().err


def popola(tmp_path, **offerte):
    adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with Store(tmp_path / "var" / "offerte.sqlite") as store:
        for titolo, (prezzo, sconto, coupon) in offerte.items():
            store.insert_offer(key=titolo, title=titolo, text=f"{titolo} in offerta", link=None, permalink="p",
                               image=None, price=prezzo, old_price=None, discount=sconto, coupon=coupon,
                               posted_at=adesso, channel="finta", now=adesso)


def test_filtra_con_soli_criteri_numerici(cfg, tmp_path, capsys):
    popola(tmp_path, scontata=(50.0, 40, "ABC10"), senza_coupon=(50.0, 40, None), poco_scontata=(50.0, 10, "ABC10"))
    assert main(["-c", cfg, "filtra", "--sconto-min", "30", "--solo-coupon"]) == 0
    out = capsys.readouterr().out
    assert "scontata" in out and "senza_coupon" not in out and "poco_scontata" not in out


def test_filtra_senza_criteri(cfg, capsys):
    assert main(["-c", cfg, "filtra"]) == 2
    assert "serve almeno una parola chiave o un altro criterio" in capsys.readouterr().err


def test_filtra_sconto_min_fuori_scala(cfg, capsys):
    assert main(["-c", cfg, "filtra", "--sconto-min", "0"]) == 2
    assert "intero da 1 a 99" in capsys.readouterr().err


def test_estratto_di_config_nel_readme():
    """L'estratto del README deve essere copiato riga per riga da config.yaml, non riscritto a mano."""
    readme = (RADICE / "README.md").read_text(encoding="utf-8")
    config = (RADICE / "config.yaml").read_text(encoding="utf-8")
    blocco = readme.split("## Configurazione", 1)[1].split("```yaml", 1)[1].split("```", 1)[0]
    righe = [re.sub(r"\s+#.*$", "", riga).rstrip() for riga in blocco.splitlines()]
    controllate = 0
    for riga in righe:
        if not riga or riga.lstrip().startswith("#"):
            continue
        assert riga in config, f"riga dell'estratto assente da config.yaml: {riga!r}"
        controllate += 1
    assert controllate > 20


class _ClientFinto:
    """Sostituisce Client nei test della CLI: nessuna richiesta, nemmeno la creazione del client httpx."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def close(self):
        pass

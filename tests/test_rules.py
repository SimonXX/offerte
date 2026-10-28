import pytest

from offerte.config import ConfigError, Rule, compile_keyword, load_config
from offerte.rules import matches
from offerte.store import Offer


def offer(text, price=None, channels=("alfa",)):
    return Offer(id=1, key="k", title=None, text=text, link=None, permalink="p", image=None, price=price,
                 old_price=None, discount=None, coupon=None, posted_at="", first_seen="", last_seen="",
                 channels=list(channels), n_posts=1)


def rule(*parole, **kw):
    return Rule(nome="r", parole=tuple(compile_keyword(p) for p in parole), **kw)


def test_parola_intera_senza_maiuscole():
    assert matches(rule("ssd"), offer("Super SSD NVMe"))
    assert matches(rule("c++"), offer("Corso di C++ base"))
    assert not matches(rule("tb"), offer("football"))


def test_regex_fra_barre():
    r = rule(r"/\b[12]\s?tb\b/")
    assert matches(r, offer("SSD 2TB"))
    assert matches(r, offer("hdd 1 TB"))
    assert not matches(r, offer("512GB"))


def test_basta_una_parola():
    assert matches(rule("nvme", "ssd"), offer("ssd sata"))


def test_prezzo_massimo():
    r = rule("ssd", prezzo_max=50)
    assert matches(r, offer("ssd", 49.99))
    assert not matches(r, offer("ssd", 59.99))
    assert not matches(r, offer("ssd", None))  # senza prezzo il tetto non è verificabile


def test_canali():
    r = rule("ssd", canali=frozenset({"alfa"}))
    assert matches(r, offer("ssd", channels=("beta", "alfa")))
    assert not matches(r, offer("ssd", channels=("beta",)))


def test_config_espande_cartelle(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali:\n  - {nome: a, cartella: Informatica}\n  - {nome: b, cartella: informatica}\n  - {nome: c, cartella: casa}\n"
        "regole:\n  - {nome: r, parole: [ssd], canali: [informatica]}\n", encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg.regole[0].canali == {"a", "b"}
    assert cfg.parametri.var_dir == tmp_path / "var"


def test_config_regex_non_valida(tmp_path):
    (tmp_path / "config.yaml").write_text("canali: [{nome: a}]\nregole: [{nome: r, parole: ['/(/']}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="regex non valida"):
        load_config(tmp_path / "config.yaml")

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


def test_tutte_le_parole():
    r = rule("apple", "watch", tutte=True)
    assert matches(r, offer("Apple Watch SE 2024"))
    assert not matches(r, offer("Apple AirPods Pro"))


def test_escludi():
    r = Rule(nome="r", parole=(compile_keyword("apple watch"),), escludi=(compile_keyword("cinturino"), compile_keyword("cover")))
    assert matches(r, offer("Apple Watch SE 40mm", 199.0))
    assert not matches(r, offer("Cinturino per Apple Watch 44mm", 9.99))


def test_prezzo_minimo():
    r = rule("apple watch", prezzo_min=100)
    assert matches(r, offer("apple watch", 199.0))
    assert not matches(r, offer("apple watch", 9.99))  # accessorio travestito
    assert not matches(r, offer("apple watch", None))


def test_config_regola_completa(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali: [{nome: a}]\nregole:\n  - {nome: aw, parole: ['apple watch'], escludi: [cinturino], prezzo_max: 250, prezzo_min: 80, tutte: true}\n",
        encoding="utf-8")
    r = load_config(tmp_path / "config.yaml").regole[0]
    assert (r.prezzo_max, r.prezzo_min, r.tutte, len(r.escludi)) == (250.0, 80.0, True, 1)


def offerta_completa(**kw):
    base = dict(id=1, key="k", title=None, text="ssd nvme", link=None, permalink="p", image=None, price=None,
                old_price=None, discount=None, coupon=None, posted_at="", first_seen="", last_seen="",
                channels=["alfa"], n_posts=1)
    return Offer(**{**base, **kw})


def test_sconto_min():
    r = rule("ssd", sconto_min=30)
    assert matches(r, offerta_completa(discount=30))
    assert matches(r, offerta_completa(discount=70))
    assert not matches(r, offerta_completa(discount=29))
    assert not matches(r, offerta_completa(discount=None))  # senza sconto il criterio non è verificabile


def test_solo_coupon():
    r = rule("ssd", solo_coupon=True)
    assert matches(r, offerta_completa(coupon="SSD10"))
    assert not matches(r, offerta_completa(coupon=None))
    assert not matches(r, offerta_completa(coupon=""))


def test_parole_opzionali():
    r = Rule(nome="r", parole=(), prezzo_max=50)
    assert matches(r, offerta_completa(text="qualunque cosa", price=20.0))
    assert not matches(r, offerta_completa(text="qualunque cosa", price=80.0))
    # escludi continua a valere anche senza parole
    r2 = Rule(nome="r", parole=(), prezzo_max=50, escludi=(compile_keyword("cinturino"),))
    assert not matches(r2, offerta_completa(text="cinturino per watch", price=20.0))


def test_config_conserva_le_stringhe_sorgenti(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali:\n  - {nome: a, cartella: Informatica}\n  - {nome: b, cartella: informatica}\n"
        "regole:\n  - nome: r\n    parole: ['apple watch', '/\\bwatch\\b/']\n    escludi: [Cinturino]\n"
        "    canali: ['@Informatica']\n", encoding="utf-8")
    r = load_config(tmp_path / "config.yaml").regole[0]
    assert r.parole_src == ("apple watch", "/\\bwatch\\b/")
    assert r.escludi_src == ("Cinturino",)
    assert r.canali_src == ("informatica",)   # normalizzata ma non espansa
    assert r.canali == {"a", "b"}             # espansa solo qui


@pytest.mark.parametrize("valore", [0, 100, "x", 30.5, True])
def test_config_rifiuta_sconto_non_valido(tmp_path, valore):
    (tmp_path / "config.yaml").write_text(
        f"canali: [{{nome: a}}]\nregole: [{{nome: r, parole: [ssd], sconto_min: {valore!r}}}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="sconto_min deve essere un intero da 1 a 99"):
        load_config(tmp_path / "config.yaml")


def test_config_regola_senza_criteri(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali: [{nome: a}]\nregole: [{nome: r, escludi: [cover]}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="serve almeno una parola chiave o un altro criterio"):
        load_config(tmp_path / "config.yaml")


def test_config_regola_con_solo_criteri_numerici(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali: [{nome: a}]\nregole: [{nome: r, sconto_min: 50, solo_coupon: true}]\n", encoding="utf-8")
    r = load_config(tmp_path / "config.yaml").regole[0]
    assert (r.parole, r.sconto_min, r.solo_coupon) == ((), 50, True)


def test_config_notify_senza_parole(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "canali: [{nome: a}]\nregole: [{nome: r, prezzo_max: 10, notify: true}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="notify richiede almeno una parola chiave"):
        load_config(tmp_path / "config.yaml")


@pytest.mark.parametrize("valore, errore", [(0, True), (1, False)])
def test_config_dashboard_max_offerte(tmp_path, valore, errore):
    (tmp_path / "config.yaml").write_text(
        f"parametri: {{dashboard_max_offerte: {valore}}}\ncanali: [{{nome: a}}]\n"
        "regole: [{nome: r, parole: [ssd]}]\n", encoding="utf-8")
    if errore:
        with pytest.raises(ConfigError, match="dashboard_max_offerte"):
            load_config(tmp_path / "config.yaml")
    else:
        assert load_config(tmp_path / "config.yaml").parametri.dashboard_max_offerte == 1

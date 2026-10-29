"""Il motore filtri.js su ogni runtime disponibile, con Python come oracolo.

Per i casi non `solo_js` nessun esito è scritto a mano: gli id attesi li calcola `rules.matches`.
"""

import json
import re
import tempfile
from pathlib import Path

import pytest
import yaml

from js_runner import esegui, motori_disponibili
from offerte.config import load_config
from offerte.feeds import dashboard_cartelle
from offerte.rules import matches
from riferimento import offerta, ordina, regola_dello_stato

FIXTURE = Path(__file__).parent / "fixtures" / "dashboard_casi.json"
MOTORI = motori_disponibili()

if not MOTORI:
    pytest.skip("nessun motore JavaScript fra gjs, node, deno e bun", allow_module_level=True)


def _config(tmp_path, fonti, regole_yaml=""):
    canali = []
    for f in fonti:
        voce = {"nome": f["nome"], "cartella": f["cartella"]}
        if "attivo" in f:
            voce["attivo"] = f["attivo"]
        canali.append(voce)
    testo = yaml.safe_dump({"parametri": {"var_dir": str(tmp_path / "var")}, "canali": canali},
                           allow_unicode=True)
    if regole_yaml:
        testo += "regole:\n" + regole_yaml
    path = tmp_path / "config.yaml"
    path.write_text(testo, encoding="utf-8")
    return load_config(path)


@pytest.fixture(scope="module")
def casi():
    dati = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="offerte-fixture-") as cartella:
        config = _config(Path(cartella), dati["fonti"])
    dati["cartelle"] = dashboard_cartelle(config)
    return dati


@pytest.fixture(scope="module")
def risultati(casi):
    return {motore: esegui(motore, casi) for motore in MOTORI}


def offerte_di(casi) -> list:
    return [offerta(v) for v in casi["offerte"]]


def ordinati(offerte, per_id) -> list[int]:
    """Ordine di default della pagina: data decrescente, poi id decrescente."""
    return [v["id"] for v in ordina([per_id[o.id] for o in offerte], "data-desc")]


def casi_di_parita(casi):
    return [c for c in casi["casi"] if not c.get("solo_js")]


@pytest.mark.parametrize("motore", MOTORI)
def test_parita_con_python(motore, casi, risultati):
    per_id = {v["id"]: v for v in casi["offerte"]}
    offerte = offerte_di(casi)
    ottenuti = {c["nome"]: c for c in risultati[motore]["casi"]}
    for caso in casi_di_parita(casi):
        regola = regola_dello_stato(caso["stato"], casi["cartelle"])
        attesi = ordinati([o for o in offerte if matches(regola, o)], per_id)
        assert ottenuti[caso["nome"]]["ids"] == attesi, caso["nome"]
        assert ottenuti[caso["nome"]]["errori"] == [], caso["nome"]


@pytest.mark.parametrize("motore", MOTORI)
def test_yaml_andata_e_ritorno(motore, casi, risultati, tmp_path):
    per_id = {v["id"]: v for v in casi["offerte"]}
    offerte = offerte_di(casi)
    ottenuti = {c["nome"]: c for c in risultati[motore]["casi"]}
    for caso in casi_di_parita(casi):
        voce = ottenuti[caso["nome"]]
        stato = caso["stato"]
        if voce["yaml"] is None:
            assert not any(stato.get(k) for k in ("q", "pmin", "pmax", "smin", "cp", "cart", "can")), caso["nome"]
            assert voce["ids"] == ordinati(offerte, per_id), caso["nome"]
            continue
        cartella = tmp_path / f"{motore}-{caso['nome']}"
        cartella.mkdir()
        config = _config(cartella, casi["fonti"], voce["yaml"])
        (regola,) = config.regole
        attesi = ordinati([o for o in offerte if matches(regola, o)], per_id)
        assert voce["ids"] == attesi, f"{caso['nome']}\n{voce['yaml']}"
        assert voce["esclusi"] == [], caso["nome"]


@pytest.mark.parametrize("motore", MOTORI)
def test_preset_da_regola(motore, casi, risultati, tmp_path):
    per_id = {v["id"]: v for v in casi["offerte"]}
    offerte = offerte_di(casi)
    blocco = ""
    for r in casi["regole"]:
        blocco += f"  - nome: {r['nome']}\n"
        if r["parole"]:
            blocco += "    parole: " + json.dumps(r["parole"], ensure_ascii=False) + "\n"
        if r["escludi"]:
            blocco += "    escludi: " + json.dumps(r["escludi"], ensure_ascii=False) + "\n"
        if r["canali"]:
            blocco += "    canali: " + json.dumps(r["canali"], ensure_ascii=False) + "\n"
        for chiave in ("prezzo_min", "prezzo_max", "sconto_min"):
            if r.get(chiave) is not None:
                blocco += f"    {chiave}: {r[chiave]}\n"
        if r["solo_coupon"]:
            blocco += "    solo_coupon: true\n"
    cartella = tmp_path / motore
    cartella.mkdir()
    config = _config(cartella, casi["fonti"], blocco)
    per_nome = {r.nome: r for r in config.regole}
    for voce in risultati[motore]["preset"]:
        regola = per_nome[voce["nome"]]
        attesi = ordinati([o for o in offerte if matches(regola, o)], per_id)
        assert voce["ids"] == attesi, voce["nome"]
        assert voce["uguale"] is True, voce["nome"]


@pytest.mark.parametrize("motore", MOTORI)
def test_casi_solo_js(motore, casi, risultati):
    ottenuti = {c["nome"]: c for c in risultati[motore]["casi"]}
    for caso in casi["casi"]:
        if not caso.get("solo_js") or "attesi" not in caso:
            continue
        assert ottenuti[caso["nome"]]["ids"] == caso["attesi"], caso["nome"]

    assert ottenuti["contatore-senza-prezzo"]["senzaPrezzo"] == 1
    assert ottenuti["contatore-senza-sconto"]["senzaSconto"] == 3

    budget = ottenuti["budget-superato"]
    assert budget["troppoLento"] is True and 0 < len(budget["ids"]) < 800

    togli = ottenuti["togli-prezzo"]
    assert togli["gruppi"] == ["q", "pi", "prezzo", "smin"]
    assert togli["dopoTogli"]["pmin"] is None and togli["dopoTogli"]["pmax"] is None
    assert togli["gruppiDopoTogli"] == ["q", "pi", "smin"]
    assert togli["idsDopoTogli"] == [1, 24, 36]

    rotta = ottenuti["regex-non-valida"]
    assert len(rotta["errori"]) == 1 and rotta["errori"][0]["campo"] == "q" and rotta["errori"][0]["riga"] == 1

    sparito = ottenuti["canale-sparito"]
    assert sparito["esclusi"] == ["sparita"]
    assert ottenuti["nessun-criterio"]["gruppi"] == [] and ottenuti["nessun-criterio"]["yaml"] is None


@pytest.mark.parametrize("motore", MOTORI)
def test_url_andata_e_ritorno(motore, casi, risultati):
    for voce in risultati[motore]["url"]:
        assert voce["uguale"] is True, voce["search"]
    attesi = {c["search"]: c["atteso"] for c in casi["url_invalidi"]}
    vuoto = {"q": [], "no": [], "tutte": False, "pi": False, "pmin": None, "pmax": None, "smin": None,
             "cart": [], "can": [], "per": None, "cp": False, "ord": "data-desc"}
    for voce in risultati[motore]["url_invalidi"]:
        assert voce["stato"] == {**vuoto, **attesi[voce["search"]]}, voce["search"]


FLAG_INLINE = re.compile(r"^\(\?[aimsuxL]+\)")


@pytest.mark.parametrize("motore", MOTORI)
def test_regex_come_python(motore, casi, risultati):
    for voce in risultati[motore]["regex"]:
        flag = FLAG_INLINE.match(voce["src"])
        if flag and flag.group(0) != "(?i)":
            assert voce["ok"] is False, f"flag inline {flag.group(0)} andava rifiutata"
            continue
        try:
            atteso = re.search(voce["src"], voce["testo"], re.IGNORECASE) is not None
        except re.error:
            assert voce["ok"] is False, voce["src"]
            continue
        assert voce["ok"] is True, f"{voce['src']}: {voce}"
        assert voce["esito"] is atteso, f"{voce['src']} su {voce['testo']!r}"

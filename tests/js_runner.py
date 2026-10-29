"""Esegue filtri.js con il primo motore JavaScript disponibile fra gjs, node, deno e bun.

Nessuna dipendenza nuova: lo script temporaneo è `filtri.js` più i casi come costante e un harness fisso,
così gira identico su tutti i motori, senza leggere file né argomenti.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

MOTORI = ("gjs", "node", "deno", "bun")
STATIC = Path(__file__).resolve().parents[1] / "src" / "offerte" / "static"

HARNESS = r"""
var F = globalThis.Filtri;
var stampa = typeof print === "function" ? print : console.log;

function statoPieno(parziale) {
  var s = F.statoDefault();
  Object.keys(parziale || {}).forEach(function (k) { s[k] = parziale[k]; });
  return s;
}

function ids(righe) {
  return righe.map(function (o) { return o.id; });
}

var fuori = {casi: [], url: [], url_invalidi: [], regex: [], preset: []};

(CASI.casi || []).forEach(function (caso) {
  var stato = statoPieno(caso.stato);
  var opz = {cartelle: CASI.cartelle, adesso: CASI.adesso};
  if (caso.ora_finta) {
    var orologio = 0;
    opz.ora = function () { orologio += caso.passo_ms || 1000; return orologio; };
    opz.budgetMs = caso.budget_ms || 1500;
  }
  var offerte = CASI.offerte;
  if (caso.ripeti) {
    offerte = [];
    for (var n = 0; n < caso.ripeti; n++) { offerte = offerte.concat(CASI.offerte); }
  }
  var r = F.applica(offerte, stato, opz);
  var regola = F.yamlRegola(stato, {nome: caso.nome_regola, notify: !!caso.notify}, CASI.cartelle);
  var voce = {
    nome: caso.nome,
    ids: ids(r.righe),
    senzaPrezzo: r.senzaPrezzo,
    senzaSconto: r.senzaSconto,
    troppoLento: r.troppoLento,
    errori: r.compilato.errori,
    avvisi: r.compilato.avvisi.length,
    yaml: regola ? regola.yaml : null,
    esclusi: regola ? regola.esclusi : [],
    gruppi: F.gruppiAttivi(stato),
    nomeSuggerito: F.nomeSuggerito(stato)
  };
  if (caso.togli) {
    var dopo = F.togliGruppo(stato, caso.togli);
    voce.dopoTogli = dopo;
    voce.gruppiDopoTogli = F.gruppiAttivi(dopo);
    voce.idsDopoTogli = ids(F.applica(CASI.offerte, dopo, {cartelle: CASI.cartelle, adesso: CASI.adesso}).righe);
  }
  fuori.casi.push(voce);
});

(CASI.url || []).forEach(function (parziale) {
  var stato = statoPieno(parziale);
  var search = F.scriviUrl(stato);
  var riletto = F.leggiUrl(search, CASI.cartelle);
  fuori.url.push({search: search, riletto: riletto,
                  uguale: JSON.stringify(riletto) === JSON.stringify(stato)});
});

(CASI.url_invalidi || []).forEach(function (caso) {
  fuori.url_invalidi.push({search: caso.search, stato: F.leggiUrl(caso.search, CASI.cartelle)});
});

(CASI.regex || []).forEach(function (v) {
  var c = F.compilaVoce("/" + v.src + "/");
  fuori.regex.push({src: v.src, testo: v.testo, ok: !!c.ok,
                    esito: c.ok ? c.re.test(v.testo) : null, avvisi: c.ok ? c.avvisi.length : 0});
});

(CASI.regole || []).forEach(function (regola) {
  var stato = F.statoDaRegola(regola, CASI.cartelle);
  var r = F.applica(CASI.offerte, stato, {cartelle: CASI.cartelle, adesso: CASI.adesso});
  fuori.preset.push({nome: regola.nome, ids: ids(r.righe), stato: stato,
                     uguale: F.regolaUguale(stato, regola, CASI.cartelle)});
});

stampa(JSON.stringify(fuori));
"""


def motori_disponibili() -> list[str]:
    return [m for m in MOTORI if shutil.which(m)]


def _comando(motore: str, script: Path) -> list[str]:
    if motore == "deno":
        return ["deno", "run", "--quiet", str(script)]
    if motore == "bun":
        return ["bun", "run", str(script)]
    return [motore, str(script)]


def esegui(motore: str, casi: dict, timeout: float = 60.0) -> dict:
    """Lancia filtri.js su `casi` e torna l'oggetto stampato dall'harness."""
    sorgente = (STATIC / "filtri.js").read_text(encoding="utf-8")
    testo = f"{sorgente}\nvar CASI = {json.dumps(casi, ensure_ascii=False)};\n{HARNESS}"
    with tempfile.TemporaryDirectory(prefix="offerte-js-") as cartella:
        script = Path(cartella) / "prova.js"
        script.write_text(testo, encoding="utf-8")
        esito = subprocess.run(_comando(motore, script), capture_output=True, text=True, timeout=timeout,
                               cwd=cartella)
    if esito.returncode != 0:
        raise RuntimeError(f"{motore} è uscito con {esito.returncode}:\n{esito.stderr[-2000:]}")
    righe = [r for r in esito.stdout.splitlines() if r.strip()]
    if not righe:
        raise RuntimeError(f"{motore} non ha stampato nulla; stderr:\n{esito.stderr[-2000:]}")
    return json.loads(righe[-1])

"""Caricamento e validazione di config.yaml."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .sources.base import Source

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) offerte/0.1"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    nome: str
    parole: tuple[re.Pattern[str], ...]
    prezzo_max: float | None = None
    canali: frozenset[str] = frozenset()  # vuoto = tutti i canali
    notify: bool = False
    tutte: bool = False  # True: servono tutte le parole, non una sola
    escludi: tuple[re.Pattern[str], ...] = ()  # una sola di queste nel testo e la regola non scatta
    prezzo_min: float | None = None


@dataclass(frozen=True)
class Params:
    intervallo_cortesia: float = 3.0
    user_agent: str = DEFAULT_USER_AGENT
    pagine_storico: int = 3
    var_dir: Path = Path("var")
    feed_base_url: str = "http://127.0.0.1:8099"
    feed_giorni: int = 14
    feed_max_elementi: int = 100
    giorni_dedupe: int = 7
    notifica_max_ore: int = 24
    http_host: str = "127.0.0.1"
    http_port: int = 8099


@dataclass(frozen=True)
class Config:
    path: Path
    fonti: tuple["Source", ...]
    regole: tuple[Rule, ...]
    parametri: Params

    def fonti_attive(self) -> list["Source"]:
        return [f for f in self.fonti if f.attivo]

    def cartelle(self) -> dict[str, list[str]]:
        """Cartella -> nomi delle fonti attive che vi appartengono."""
        out: dict[str, list[str]] = {}
        for f in self.fonti_attive():
            out.setdefault(f.cartella, []).append(f.nome)
        return out


def compile_keyword(parola: str) -> re.Pattern[str]:
    """`/.../` è una regex; tutto il resto è una parola intera. Sempre senza distinzione di maiuscole."""
    if len(parola) > 2 and parola.startswith("/") and parola.endswith("/"):
        return re.compile(parola[1:-1], re.IGNORECASE)
    return re.compile(r"(?<!\w)" + re.escape(parola) + r"(?!\w)", re.IGNORECASE)


def _check_keys(section: str, data: dict, allowed: set[str]) -> None:
    extra = set(data) - allowed
    if extra:
        raise ConfigError(f"{section}: chiavi sconosciute {sorted(extra)}")


def _as_list(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def load_config(path: Path | str) -> Config:
    path = Path(path).resolve()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise ConfigError(f"config non trovata: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML non valido in {path}: {e}") from None
    if not isinstance(data, dict):
        raise ConfigError("la config deve essere una mappa YAML")
    raw = data.get("parametri") or {}
    _check_keys("parametri", raw, set(Params.__dataclass_fields__))
    var_dir = Path(raw.get("var_dir") or "var")
    if not var_dir.is_absolute():
        var_dir = path.parent / var_dir
    params = Params(
        intervallo_cortesia=float(raw.get("intervallo_cortesia", 3)),
        user_agent=str(raw.get("user_agent") or DEFAULT_USER_AGENT),
        pagine_storico=max(1, int(raw.get("pagine_storico", 3))),
        var_dir=var_dir,
        feed_base_url=str(os.environ.get("OFFERTE_FEED_BASE_URL") or raw.get("feed_base_url", "http://127.0.0.1:8099")).rstrip("/"),
        feed_giorni=int(raw.get("feed_giorni", 14)),
        feed_max_elementi=int(raw.get("feed_max_elementi", 100)),
        giorni_dedupe=int(raw.get("giorni_dedupe", 7)),
        notifica_max_ore=int(raw.get("notifica_max_ore", 24)),
        http_host=str(raw.get("http_host", "127.0.0.1")),
        http_port=int(raw.get("http_port", 8099)),
    )

    _check_keys("config", data, {"canali", "fonti", "regole", "parametri"})
    from .sources import crea_fonte  # import ritardato: sources importa ConfigError da qui

    fonti = []
    for i, rc in enumerate(data.get("canali") or []):  # scorciatoia: canali = fonti di tipo telegram
        if not isinstance(rc, dict) or not rc.get("nome"):
            raise ConfigError(f"canali[{i}]: serve almeno 'nome'")
        _check_keys(f"canali[{i}]", rc, {"nome", "cartella", "attivo"})
        fonti.append(crea_fonte({**rc, "nome": str(rc["nome"]).strip().lstrip("@").lower(), "tipo": "telegram"}))
    for i, rf in enumerate(data.get("fonti") or []):
        if not isinstance(rf, dict):
            raise ConfigError(f"fonti[{i}]: deve essere una mappa")
        fonti.append(crea_fonte(rf))
    if not fonti:
        raise ConfigError("nessuna fonte configurata (canali: o fonti:)")
    nomi = {f.nome for f in fonti}
    if len(nomi) != len(fonti):
        raise ConfigError("fonti con lo stesso nome")
    per_cartella: dict[str, set[str]] = {}
    for f in fonti:
        per_cartella.setdefault(f.cartella.lower(), set()).add(f.nome)

    regole: list[Rule] = []
    for i, rr in enumerate(data.get("regole") or []):
        if not isinstance(rr, dict) or not rr.get("nome"):
            raise ConfigError(f"regole[{i}]: serve almeno 'nome'")
        _check_keys(f"regole[{i}]", rr, {"nome", "parole", "prezzo_max", "prezzo_min", "canali", "notify", "tutte", "escludi"})
        nome = str(rr["nome"]).strip()
        parole = [str(p) for p in _as_list(rr.get("parole"))]
        if not parole:
            raise ConfigError(f"regola '{nome}': nessuna parola chiave")
        try:
            compiled = tuple(compile_keyword(p) for p in parole)
            escludi = tuple(compile_keyword(str(p)) for p in _as_list(rr.get("escludi")))
        except re.error as e:
            raise ConfigError(f"regola '{nome}': regex non valida ({e})") from None
        prezzo_max = rr.get("prezzo_max")
        prezzo_min = rr.get("prezzo_min")
        selezione: set[str] = set()
        for voce in _as_list(rr.get("canali")):
            voce = str(voce).strip().lstrip("@").lower()
            if voce in nomi:
                selezione.add(voce)
            elif voce in per_cartella:
                selezione |= per_cartella[voce]
            else:
                raise ConfigError(f"regola '{nome}': fonte o cartella sconosciuta '{voce}'")
        regole.append(Rule(
            nome=nome,
            parole=compiled,
            prezzo_max=None if prezzo_max is None else float(prezzo_max),
            canali=frozenset(selezione),
            notify=bool(rr.get("notify", False)),
            tutte=bool(rr.get("tutte", False)),
            escludi=escludi,
            prezzo_min=None if prezzo_min is None else float(prezzo_min),
        ))
    if len({r.nome for r in regole}) != len(regole):
        raise ConfigError("regole con lo stesso nome")

    return Config(path=path, fonti=tuple(fonti), regole=tuple(regole), parametri=params)

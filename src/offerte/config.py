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


CRITERI_REGOLA = ("serve almeno una parola chiave o un altro criterio"
                  " (prezzo_min, prezzo_max, sconto_min, solo_coupon, canali)")


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
    sconto_min: int | None = None  # percentuale minima; un'offerta senza sconto non passa
    solo_coupon: bool = False
    attiva: bool = True  # spenta resta in config ma non scatta, non notifica e non ha un feed
    # Le stringhe come sono scritte in config: le regex compilate non si possono rileggere, e la dashboard
    # deve poter mostrare la regola e riprodurla nei propri filtri.
    parole_src: tuple[str, ...] = ()
    escludi_src: tuple[str, ...] = ()
    canali_src: tuple[str, ...] = ()  # nomi di canale o di cartella, non espansi


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
    giorni_ritenzione: int = 90
    http_host: str = "127.0.0.1"
    http_port: int = 8099
    dashboard: bool = True
    dashboard_regole: bool = True
    dashboard_max_offerte: int = 10000
    dashboard_giorni: int | None = None  # finestra della dashboard; assente = quella dei feed
    # Cartelle gia' spuntate all'apertura della dashboard: serve a non partire da tutto.
    # Vuoto = nessun filtro iniziale. Un link con ?cart=... o ?can=... ha sempre la precedenza.
    dashboard_cartelle: tuple[str, ...] = ()
    regole_dir: str = "regole"      # cartella con una regola per file, accanto a config.yaml
    # Base del pulsante "Crea su GitHub": apre l'editor web con il file della regola gia' scritto.
    # Forma attesa: https://github.com/<utente>/<repo>/new/<branch>. Vuoto = niente pulsante.
    regole_url: str = ""
    # Grafico dello storico prezzi, caricato dal browser solo quando apri la scheda. Vuoto = niente grafico.
    grafico_prezzi: str = "https://graph.keepa.com/pricehistory.png?domain=it&range=365&asin="
    # Base del link "mandamelo in chat". Con t.me/share/url apre il selettore delle chat; con
    # t.me/<nome_bot> apre direttamente quella chat con il messaggio pronto. Vuoto = niente pulsante.
    condividi_url: str = "https://t.me/share/url"


@dataclass(frozen=True)
class Config:
    path: Path
    fonti: tuple["Source", ...]
    regole: tuple[Rule, ...]
    parametri: Params

    def fonti_attive(self) -> list["Source"]:
        return [f for f in self.fonti if f.attivo]

    def regole_attive(self) -> tuple[Rule, ...]:
        return tuple(r for r in self.regole if r.attiva)

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


def _regole_da_cartella(cartella: Path) -> list[tuple[str, dict]]:
    """Una regola per file in `regole/`: si aggiunge committando un file, senza toccare config.yaml.

    Il file contiene i soli campi della regola, senza indentazione. `nome` si può omettere: vale
    il nome del file. Dentro, una regola sola oppure un elenco di regole.
    """
    if not cartella.is_dir():
        return []
    voci: list[tuple[str, dict]] = []
    for file in sorted(cartella.glob("*.y*ml")):
        try:
            contenuto = yaml.safe_load(file.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ConfigError(f"{file.name}: YAML non valido ({e})") from None
        if contenuto is None:
            continue
        gruppo = contenuto if isinstance(contenuto, list) else [contenuto]
        for n, voce in enumerate(gruppo):
            if not isinstance(voce, dict):
                raise ConfigError(f"{file.name}: serve un elenco di campi, non {type(voce).__name__}")
            if not voce.get("nome"):
                voce = {"nome": file.stem, **voce}
            voci.append((file.name if len(gruppo) == 1 else f"{file.name}[{n}]", voce))
    return voci


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
        giorni_ritenzione=int(raw.get("giorni_ritenzione", 90)),
        http_host=str(raw.get("http_host", "127.0.0.1")),
        http_port=int(raw.get("http_port", 8099)),
        dashboard=bool(raw.get("dashboard", True)),
        dashboard_regole=bool(raw.get("dashboard_regole", True)),
        dashboard_max_offerte=int(raw.get("dashboard_max_offerte", 10000)),
        dashboard_giorni=None if raw.get("dashboard_giorni") is None else int(raw["dashboard_giorni"]),
        dashboard_cartelle=tuple(str(c).strip().lower() for c in (raw.get("dashboard_cartelle") or []) if str(c).strip()),
        regole_dir=str(raw.get("regole_dir", "regole")).strip() or "regole",
        regole_url=str(raw.get("regole_url", "")).strip().rstrip("/"),
        grafico_prezzi=str(raw.get("grafico_prezzi", Params.grafico_prezzi)).strip(),
        condividi_url=str(raw.get("condividi_url", Params.condividi_url)).strip(),
    )
    if params.dashboard_max_offerte < 1:
        raise ConfigError("parametri: dashboard_max_offerte deve essere almeno 1")
    if params.dashboard_giorni is not None and params.dashboard_giorni < 1:
        raise ConfigError("parametri: dashboard_giorni deve essere almeno 1")

    _check_keys("config", data, {"canali", "fonti", "regole", "parametri"})
    from .sources import crea_fonte  # import ritardato: sources importa ConfigError da qui

    fonti = []
    for i, rc in enumerate(data.get("canali") or []):  # scorciatoia: canali = fonti di tipo telegram
        if not isinstance(rc, dict) or not rc.get("nome"):
            raise ConfigError(f"canali[{i}]: serve almeno 'nome'")
        _check_keys(f"canali[{i}]", rc, {"nome", "cartella", "attivo", "ogni", "canale", "pagine"})
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
    voci = [(f"regole[{i}]", rr) for i, rr in enumerate(data.get("regole") or [])]
    voci += _regole_da_cartella(path.parent / params.regole_dir)
    visti: set[str] = set()
    for dove, rr in voci:
        if not isinstance(rr, dict) or not rr.get("nome"):
            raise ConfigError(f"{dove}: serve almeno 'nome'")
        _check_keys(dove, rr, {"nome", "parole", "prezzo_max", "prezzo_min", "canali", "notify", "tutte",
                               "escludi", "sconto_min", "solo_coupon", "attiva"})
        nome = str(rr["nome"]).strip()
        if nome in visti:
            raise ConfigError(f"{dove}: esiste gia' una regola di nome '{nome}'")
        visti.add(nome)
        parole = [str(p) for p in _as_list(rr.get("parole"))]
        sconto_min = rr.get("sconto_min")
        if sconto_min is not None and (isinstance(sconto_min, bool) or not isinstance(sconto_min, int)
                                       or not 1 <= sconto_min <= 99):
            raise ConfigError(f"regola '{nome}': sconto_min deve essere un intero da 1 a 99")
        solo_coupon = bool(rr.get("solo_coupon", False))
        altri_criteri = any(rr.get(k) is not None for k in ("prezzo_min", "prezzo_max", "canali")) or solo_coupon \
            or sconto_min is not None
        if not parole and not altri_criteri:
            raise ConfigError(f"regola '{nome}': {CRITERI_REGOLA}")
        if not parole and bool(rr.get("notify", False)):
            # Una regola senza parole corrisponde a tutto ciò che passa i criteri numerici: con notify
            # sarebbe una raffica di notifiche a ogni giro.
            raise ConfigError(f"regola '{nome}': notify richiede almeno una parola chiave")
        try:
            compiled = tuple(compile_keyword(p) for p in parole)
            escludi = tuple(compile_keyword(str(p)) for p in _as_list(rr.get("escludi")))
        except re.error as e:
            raise ConfigError(f"regola '{nome}': regex non valida ({e})") from None
        prezzo_max = rr.get("prezzo_max")
        prezzo_min = rr.get("prezzo_min")
        selezione: set[str] = set()
        canali_src = tuple(str(voce).strip().lstrip("@").lower() for voce in _as_list(rr.get("canali")))
        for voce in canali_src:
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
            sconto_min=sconto_min,
            solo_coupon=solo_coupon,
            attiva=bool(rr.get("attiva", True)),
            parole_src=tuple(parole),
            escludi_src=tuple(str(p) for p in _as_list(rr.get("escludi"))),
            canali_src=canali_src,
        ))
    if len({r.nome for r in regole}) != len(regole):
        raise ConfigError("regole con lo stesso nome")

    cfg = Config(path=path, fonti=tuple(fonti), regole=tuple(regole), parametri=params)
    ignote = [c for c in params.dashboard_cartelle if c not in cfg.cartelle()]
    if ignote:
        raise ConfigError(f"parametri: dashboard_cartelle, cartelle inesistenti: {', '.join(ignote)}")
    return cfg

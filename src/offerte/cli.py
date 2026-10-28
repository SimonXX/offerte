"""Interfaccia a riga di comando: offerte fetch | serve | search | stats."""

from __future__ import annotations

import argparse
import fcntl
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .config import Config, ConfigError, Rule, compile_keyword, load_config
from .feeds import fmt_price
from .fetch import run_fetch
from .http import Client
from .log import setup_logging
from .notify import Notifier, load_env
from .rules import matches
from .serve import serve
from .store import Store

log = logging.getLogger("offerte.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="offerte", description="Offerte dai canali Telegram pubblici, in feed RSS e JSON.")
    parser.add_argument("-c", "--config", type=Path, help="percorso di config.yaml (default: $OFFERTE_CONFIG o ./config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log di debug")
    parser.add_argument("--version", action="version", version=f"offerte {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="scarica i canali, aggiorna il database, applica le regole, rigenera i feed")
    p.add_argument("--canale", help="solo questo canale")
    p.add_argument("--storico", type=int, metavar="N", help="pagine da leggere per canale (sovrascrive pagine_storico)")
    p.add_argument("--senza-notifiche", action="store_true", help="non inviare notifiche Telegram in questo giro")

    p = sub.add_parser("serve", help="serve var/feeds via HTTP")
    p.add_argument("--host", help="default: parametri.http_host (127.0.0.1)")
    p.add_argument("--port", type=int, help="default: parametri.http_port (8099)")

    p = sub.add_parser("search", help="cerca una parola nel testo e nel titolo delle offerte")
    p.add_argument("parola")
    p.add_argument("--limite", type=int, default=20)

    p = sub.add_parser("stats", help="offerte al giorno per canale e regole scattate")
    p.add_argument("--giorni", type=int, default=7)

    p = sub.add_parser("filtra", help="prova una regola al volo sulle offerte salvate, senza toccare la config")
    p.add_argument("parole", nargs="+", help="parole chiave (parola intera o /regex/), come in config")
    p.add_argument("--prezzo-max", type=float)
    p.add_argument("--prezzo-min", type=float)
    p.add_argument("--escludi", nargs="*", default=[], help="parole che annullano la corrispondenza")
    p.add_argument("--tutte", action="store_true", help="servono tutte le parole, non una sola")
    p.add_argument("--canali", nargs="*", default=[], help="nomi di canale o di cartella")
    p.add_argument("--giorni", type=int, default=14)
    p.add_argument("--limite", type=int, default=50)
    return parser


def cmd_fetch(args: argparse.Namespace, config: Config) -> int:
    p = config.parametri
    if args.canale and args.canale not in {c.nome for c in config.canali_attivi()}:
        log.error("canale '%s' non in config o non attivo", args.canale)
        return 2
    with open(p.var_dir / "fetch.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.warning("un altro fetch è in corso, esco")
            return 0
        notifier = None if args.senza_notifiche else Notifier.from_env()
        if notifier is None and not args.senza_notifiche and any(r.notify for r in config.regole):
            log.warning("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID assenti: notifiche disattivate")
        try:
            with Store(p.var_dir / "offerte.sqlite") as store, Client(p.user_agent, p.intervallo_cortesia) as client:
                summary = run_fetch(config, store, client, notifier, only=args.canale, pages=args.storico)
        finally:
            if notifier:
                notifier.close()
    return 1 if summary.failed and not summary.ok else 0


def cmd_serve(args: argparse.Namespace, config: Config) -> int:
    p = config.parametri
    serve(p.var_dir / "feeds", args.host or p.http_host, args.port or p.http_port)
    return 0


def _local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")


def cmd_search(args: argparse.Namespace, config: Config) -> int:
    with Store(config.parametri.var_dir / "offerte.sqlite") as store:
        rows = store.search(args.parola, args.limite)
    if not rows:
        print("nessuna offerta trovata")
        return 0
    _print_offers(rows)
    return 0


def cmd_stats(args: argparse.Namespace, config: Config) -> int:
    giorni = max(1, args.giorni)
    oggi = datetime.now().astimezone().date()
    days = [oggi - timedelta(days=i) for i in range(giorni - 1, -1, -1)]
    since = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat(timespec="seconds")
    with Store(config.parametri.var_dir / "offerte.sqlite") as store:
        per_day, fired, totali = store.posts_per_day(since), store.rules_fired(since), store.counts()

    tabella: dict[str, dict[str, int]] = {c.nome: {} for c in config.canali_attivi()}
    for channel, day, n in per_day:
        tabella.setdefault(channel, {})[day] = n
    print(f"Offerte al giorno per canale (ultimi {giorni} giorni)")
    print(f"{'canale':<32}" + "".join(f"{d.strftime('%d/%m'):>7}" for d in days) + f"{'tot':>7}")
    for channel in sorted(tabella):
        conteggi = [tabella[channel].get(d.isoformat(), 0) for d in days]
        print(f"{channel:<32}" + "".join(f"{n:>7}" for n in conteggi) + f"{sum(conteggi):>7}")

    print(f"\nRegole scattate (ultimi {giorni} giorni)")
    if not fired:
        print("  nessuna")
    for rule, n, last in fired:
        print(f"{rule:<32}{n:>7}  ultimo {_local(last)}")
    print(f"\nTotale: {totali['offers']} offerte, {totali['posts']} post, {totali['channels']} canali")
    return 0


def _print_offers(rows) -> None:
    for o in rows:
        prezzo = fmt_price(o.price) if o.price is not None else "-"
        titolo = o.title or o.text.splitlines()[0][:60]
        print(f"{_local(o.posted_at)}  {prezzo:>10}  {titolo}  [{', '.join(o.channels)}]  {o.link or o.permalink}")


def cmd_filtra(args: argparse.Namespace, config: Config) -> int:
    cartelle = {k.lower(): v for k, v in config.cartelle().items()}
    canali: set[str] = set()
    for voce in args.canali:
        voce = voce.lower().lstrip("@")
        canali |= set(cartelle.get(voce, [voce]))
    try:
        rule = Rule(nome="filtra", parole=tuple(compile_keyword(p) for p in args.parole),
                    prezzo_max=args.prezzo_max, prezzo_min=args.prezzo_min, canali=frozenset(canali),
                    tutte=args.tutte, escludi=tuple(compile_keyword(p) for p in args.escludi))
    except Exception as e:  # noqa: BLE001 (re.error e simili: messaggio all'utente, non traceback)
        print(f"regola non valida: {e}", file=sys.stderr)
        return 2
    since = (datetime.now(timezone.utc) - timedelta(days=args.giorni)).isoformat(timespec="seconds")
    with Store(config.parametri.var_dir / "offerte.sqlite") as store:
        rows = [o for o in store.offers_since(since) if matches(rule, o)][: args.limite]
    if not rows:
        print("nessuna offerta corrisponde")
        return 0
    _print_offers(rows)
    return 0


COMMANDS = {"fetch": cmd_fetch, "serve": cmd_serve, "search": cmd_search, "stats": cmd_stats, "filtra": cmd_filtra}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config or Path(os.environ.get("OFFERTE_CONFIG") or "config.yaml")
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"errore di configurazione: {e}", file=sys.stderr)
        return 2
    setup_logging(config.parametri.var_dir, args.verbose)
    load_env(config.path.parent / ".env")
    try:
        return COMMANDS[args.cmd](args, config)
    except KeyboardInterrupt:
        return 130

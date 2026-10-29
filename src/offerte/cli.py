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
from .config import CRITERI_REGOLA, Config, ConfigError, Rule, compile_keyword, load_config
from .extract import extract
from .feeds import fmt_price
from .fetch import run_fetch
from .http import Client
from .log import setup_logging
from .notify import Notifier, load_env
from .links import pick_offer_link
from .rules import matches
from .serve import serve
from .sources.base import FetchContext
from .store import SourceState, Store

log = logging.getLogger("offerte.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="offerte", description="Offerte dai canali Telegram pubblici, in feed RSS e JSON.")
    parser.add_argument("-c", "--config", type=Path, help="percorso di config.yaml (default: $OFFERTE_CONFIG o ./config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log di debug")
    parser.add_argument("--version", action="version", version=f"offerte {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="scarica i canali, aggiorna il database, applica le regole, rigenera i feed")
    p.add_argument("--fonte", "--canale", dest="fonte", help="solo questa fonte")
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

    sub.add_parser("fonti", help="elenca le fonti configurate con stato e ultimo fetch")

    p = sub.add_parser("pulisci", help="elimina le offerte più vecchie di N giorni e compatta il database")
    p.add_argument("--giorni", type=int, help="default: parametri.giorni_ritenzione")

    p = sub.add_parser("prova", help="esegue una fonte senza salvare nulla e mostra cosa produce")
    p.add_argument("fonte")
    p.add_argument("--limite", type=int, default=20)

    p = sub.add_parser("filtra", help="prova una regola al volo sulle offerte salvate, senza toccare la config")
    p.add_argument("parole", nargs="*", help="parole chiave (parola intera o /regex/), come in config")
    p.add_argument("--prezzo-max", type=float)
    p.add_argument("--prezzo-min", type=float)
    p.add_argument("--sconto-min", type=int, metavar="N", help="sconto minimo in percentuale (1-99)")
    p.add_argument("--solo-coupon", action="store_true", help="solo le offerte con un coupon")
    p.add_argument("--escludi", nargs="*", default=[], help="parole che annullano la corrispondenza")
    p.add_argument("--tutte", action="store_true", help="servono tutte le parole, non una sola")
    p.add_argument("--canali", nargs="*", default=[], help="nomi di canale o di cartella")
    p.add_argument("--giorni", type=int, default=14)
    p.add_argument("--limite", type=int, default=50)
    return parser


def cmd_fetch(args: argparse.Namespace, config: Config) -> int:
    p = config.parametri
    if args.fonte and args.fonte not in {f.nome for f in config.fonti_attive()}:
        log.error("fonte '%s' non in config o non attiva", args.fonte)
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
                summary = run_fetch(config, store, client, notifier, only=args.fonte, pages=args.storico)
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

    tabella: dict[str, dict[str, int]] = {f.nome: {} for f in config.fonti_attive()}
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


def cmd_pulisci(args: argparse.Namespace, config: Config) -> int:
    giorni = args.giorni if args.giorni is not None else config.parametri.giorni_ritenzione
    if giorni <= 0:
        print("ritenzione disattivata (giorni <= 0)")
        return 0
    before = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat(timespec="seconds")
    with Store(config.parametri.var_dir / "offerte.sqlite") as store:
        tolte = store.purge(before, vacuum=True)
        totali = store.counts()
    print(f"tolte {tolte} offerte più vecchie di {giorni} giorni; restano {totali['offers']} offerte e {totali['posts']} post")
    return 0


def cmd_fonti(args: argparse.Namespace, config: Config) -> int:
    with Store(config.parametri.var_dir / "offerte.sqlite") as store:
        print(f"{'fonte':<32}{'tipo':<10}{'cartella':<14}{'ogni':>5}  {'ultimo fetch':<17}{'stato':<12}errore")
        for f in config.fonti:
            st = store.channel_state(f.nome)
            quando = _local(st.last_fetch) if st.last_fetch else "-"
            stato = st.last_status or ("inattiva" if not f.attivo else "-")
            print(f"{f.nome:<32}{f.tipo:<10}{f.cartella:<14}{f.ogni or '':>5}  {quando:<17}{stato:<12}{(st.last_error or '')[:60]}")
    return 0


def cmd_prova(args: argparse.Namespace, config: Config) -> int:
    fonte = next((f for f in config.fonti if f.nome == args.fonte), None)
    if fonte is None:
        print(f"fonte '{args.fonte}' non in config", file=sys.stderr)
        return 2
    p = config.parametri
    with Store(":memory:") as store, Client(p.user_agent, p.intervallo_cortesia) as client:
        ctx = FetchContext(client=client, store=store, now=datetime.now(timezone.utc), state=SourceState(),
                           pages=1, config_dir=config.path.parent)
        try:
            result = fonte.fetch(ctx)
        except Exception as e:  # noqa: BLE001 (è un comando diagnostico: l'errore è il risultato)
            print(f"errore: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
    vuota = ", nessun elemento trovato dal selettore" if result.vuota else ""
    print(f"{len(result.items)} elementi" + (f", id massimo {result.last_id}" if result.last_id else "") + vuota)
    for m in result.items[: args.limite]:
        # Stessa estrazione di process_message: altrimenti il comando mostrerebbe il prezzo grezzo della
        # fonte (vuoto per Telegram) e il primo link qualsiasi, che spesso è la foto dell'anteprima.
        ex = extract(m.text, m.struck)
        prezzo = fmt_price(m.price if m.price is not None else ex.price) if (m.price is not None or ex.price is not None) else "-"
        titolo = ex.title or m.text.splitlines()[0][:70]
        print(f"- {m.date:%Y-%m-%d %H:%M}  id={m.id}  prezzo={prezzo:>10}  {titolo[:70]}  {pick_offer_link(m.links) or ''}")
    return 0


def cmd_filtra(args: argparse.Namespace, config: Config) -> int:
    cartelle = {k.lower(): v for k, v in config.cartelle().items()}
    canali: set[str] = set()
    for voce in args.canali:
        voce = voce.lower().lstrip("@")
        canali |= set(cartelle.get(voce, [voce]))
    if not args.parole and not (args.prezzo_min is not None or args.prezzo_max is not None
                                or args.sconto_min is not None or args.solo_coupon or canali):
        print(f"filtra: {CRITERI_REGOLA}", file=sys.stderr)
        return 2
    if args.sconto_min is not None and not 1 <= args.sconto_min <= 99:
        print("filtra: --sconto-min vuole un intero da 1 a 99", file=sys.stderr)
        return 2
    try:
        rule = Rule(nome="filtra", parole=tuple(compile_keyword(p) for p in args.parole),
                    prezzo_max=args.prezzo_max, prezzo_min=args.prezzo_min, canali=frozenset(canali),
                    tutte=args.tutte, escludi=tuple(compile_keyword(p) for p in args.escludi),
                    sconto_min=args.sconto_min, solo_coupon=args.solo_coupon)
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


COMMANDS = {"fetch": cmd_fetch, "serve": cmd_serve, "search": cmd_search, "stats": cmd_stats, "filtra": cmd_filtra,
            "fonti": cmd_fonti, "prova": cmd_prova, "pulisci": cmd_pulisci}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config or os.environ.get("OFFERTE_CONFIG") or "config.yaml")
    # Prima della config: cosi' le variabili scritte in .env (OFFERTE_FEED_BASE_URL fra le altre) hanno effetto.
    load_env(config_path.parent / ".env")
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"errore di configurazione: {e}", file=sys.stderr)
        return 2
    setup_logging(config.parametri.var_dir, args.verbose)
    try:
        return COMMANDS[args.cmd](args, config)
    except KeyboardInterrupt:
        return 130

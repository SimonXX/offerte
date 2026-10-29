# Registro degli sprint

Un blocco per sprint, scritto alla chiusura. Fatti, comandi eseguiti con l'esito, misure, deviazioni.

## S0, correzioni prioritarie

Data: 29 ottobre 2026. Commit di partenza: `16e8709` (poi `bb1ccd0`, che traccia `docs/`).

### Stato iniziale dell'ambiente

`ls -l var` nel repository, prima di toccare qualunque cosa:

```
-rw-r--r--. 1 utente  utente     0 2026-10-28 22:44:42 *.db
-rw-r--r--. 1 utente  utente     0 2026-10-28 22:01:04 fetch.lock
-rw-r--r--. 1 utente  utente   623 2026-10-28 23:00:41 offerte.log
-rw-r--r--. 1 utente  utente 61440 2026-10-28 22:01:08 offerte.sqlite
```

`sqlite3 var/offerte.sqlite "select count(*) from offers"` dava 0. A fine sprint i quattro file hanno gli
stessi mtime e il conteggio è ancora 0: tutte le prove sono passate da `/tmp/offerte-prova/config.yaml`.

### Cosa è stato fatto

| voce | intervento |
|:--|:--|
| S0.1 | `_assoluto(base, href)` in `sources/html.py`: scarta `#`, `javascript:`, `mailto:`, `tel:` e gli URL uguali alla pagina. Senza campo `link` il link è il primo anchor che passa il filtro; senza link l'id è `text_key(testo)` |
| S0.2 | `extract.py`: `NOISE_BEFORE` e `NOISE_AFTER` escludono coupon, spedizione, cashback, rate e risparmio dagli importi; il caso a due importi scatta solo sulla stessa riga; `\b` in `OLD_HINT_RE` con `(?<!partire\s)da`; terza alternativa `postd` in `PRICE_RE` per la guardia su `9 € 299`; `PCT_RE` ammette 100 e lo sconto del testo cede a quello calcolato se diverge di più di 3 punti; `PCT_CONTEXT_RE` al posto della prima percentuale qualsiasi. I trattini di `PCT_RE` e `TRAILING_PRICE_RE` sono ora `\N{MINUS SIGN}`, `\N{EN DASH}`, `\N{EM DASH}` |
| S0.3 | `Store.pending_notifications(rule_names, since)`: join `matches`, `LEFT JOIN notifications`, raggruppamento in Python, nessuna colonna extra in `_offer`. `run_fetch` invia da quella lista, tetto di 30 per giro con log del resto. `Notifier.send` legge `parameters.retry_after` su 429 e ritenta una volta |
| S0.4 | `PAGINE_INCREMENTALI = 30` in `sources/telegram.py` per i giri con `last_id > 0`; `for/else` con `log.warning` quando le pagine finiscono senza incontrare un id noto |
| S0.5 | Un'offerta con data di ripiego creata al primo giro di una fonte riceve subito `mark_notified` senza invio. `parse_date` accetta `dd/mm/yyyy`, `dd/mm/yyyy hh:mm`, `dd-mm-yyyy` e i timestamp in stringa, e non solleva in nessun ramo |
| S0.6 | `to_number` rifiuta `nan`, `inf`, i booleani e gli underscore; `1.299` vale 1299 solo con tre cifre dopo il punto |
| S0.7 | `rss.py` verifica la radice (`rss`, `feed`, `rdf`) e legge davvero RSS 1.0; `FetchResult.vuota`; `HtmlSource.fetch` la imposta con un warning quando il selettore non trova nodi; `run_fetch` scrive `status="vuota"` tenendo la fonte fra le ok |
| S0.8 | `NON_RITENTABILI` (UnsupportedProtocol, TooManyRedirects, DecodingError) senza riprova; `Retry-After` anche come data HTTP; budget di attesa di 60 s per chiamata; `rss` e `html` rifiutano un `url` senza schema |
| S0.9 | `normalize_input` non antepone `https://` agli schemi non web; `is_web_url` richiede http o https e una porta leggibile; `process_message` cattura `ValueError` e tiene il messaggio senza link |
| S0.10 | `ENTITY_RE` decodifica solo le entità chiuse dal punto e virgola, in due passate |
| S0.11 | `is_ribasso`: un ripost della stessa chiave con prezzo inferiore di almeno il 5% crea una riga nuova |
| S0.12 | `cmd_prova` usa `extract(m.text, m.struck)` e `pick_offer_link(m.links)` |
| S0.13 | `deploy/stato.sh restore` distingue branch assente (rc 0) da remoto irraggiungibile (rc 1) con `ls-remote --exit-code` |
| S0.14 | `load_env` prima di `load_config` in `cli.main` |
| S0.15 | `canali:` accetta `ogni`, `canale` e `pagine`; README: introduzione sulle fonti, `-c` e `-v` prima del sottocomando, `--env-file` facoltativo nel comando container, estratto di config copiato da `config.yaml`; descrizione in `pyproject.toml` |
| S0.16 | `tests/test_cli.py` (fumo su ogni sottocomando più il controllo dell'estratto del README), `tests/test_stato.py`, `tests/test_store.py` esteso |

### Test

73 prima, **149 dopo** (+76). Nessuna asserzione dei 73 esistenti è stata modificata.

Conteggio per file a fine sprint: `test_sources.py` 42, `test_extract.py` 39, `test_cli.py` 12 (nuovo),
`test_rules.py` 11, `test_links.py` 9, `test_dedupe.py` 7, `test_http.py` 7, `test_parser.py` 7,
`test_fetch.py` 6, `test_stato.py` 4 (nuovo), `test_store.py` 3, `test_feeds.py` 2.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 149 passed in 0,25 s |
| controllo trattini (`grep -rnIP` su src, tests, README, config.yaml, docs, deploy, systemd, .github, Containerfile, pyproject.toml) | nessuna riga |
| `uv run offerte --help` | elenca gli otto sottocomandi |
| `uv run offerte -c /tmp/offerte-prova/config.yaml fetch --storico 1 --senza-notifiche` | **17 fonti su 17 ok**, 0 saltate, 0 fallite, 330 post, 287 offerte nuove, 16 senza prezzo, 223 con sconto, 1 regola scattata (`errori-di-prezzo`, 20) |
| `uv run offerte -c /tmp/offerte-prova/config.yaml fonti` | 17 righe, tutte `ok` |
| `uv run offerte -c /tmp/offerte-prova/config.yaml prova mttvideo` | prezzi e link reali al posto di `-` e dell'URL della foto |
| `ls -l var` e `sqlite3 var/offerte.sqlite "select count(*) from offers"` | mtime invariati, 0 offerte |

### Deviazioni

- `docs/` risultava già tracciata: il commit `bb1ccd0` l'aveva aggiunta prima dell'inizio di questo lavoro,
  quindi `git add docs/<file>` di S0 riguarda solo `docs/registro-sprint.md`.
- Problema 16, guardia su `9 € 299`: la guardia vale solo per gli importi senza decimali, come previsto dallo
  stato dell'arte. Costo noto e accettato: un testo con due interi nel formato `199 € 249 €` perde il primo
  importo. Con i decimali (`59,99 € 99,99 €`) entrambi si leggono.
- Problema 10, `to_number`: oltre a quanto chiesto si rifiutano anche gli underscore (`1_000`), perché
  `float()` li accetta e nessuna fonte scrive i prezzi così. `1e3` resta accettato.
- S0.3, raggruppamento: `pending_notifications` ordina per `posted_at, id, rule`, così i nomi delle regole di
  un'offerta arrivano in ordine stabile e il test può confrontarli.

### Lasciato aperto

Problemi dello stato dell'arte non toccati in questo sprint: 4, 5, 6 e 25 (si chiudono con S2), più
18, 19, 20, 22, 23, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 42-55, 58, 59, 61-65, 67.

## S1, motore delle regole

Data: 29 ottobre 2026.

### Cosa è stato fatto

`Rule` guadagna `sconto_min`, `solo_coupon`, `parole_src`, `escludi_src`, `canali_src`, tutti con default:
le chiamate `Rule(...)` dei test e di `cmd_filtra` restano valide. `Params` guadagna `dashboard`,
`dashboard_regole`, `dashboard_max_offerte`, passati uno a uno nella costruzione perché lo YAML abbia effetto;
`dashboard_max_offerte < 1` è `ConfigError`.

`load_config`: chiavi `sconto_min` e `solo_coupon` ammesse in una regola; `sconto_min` deve essere un intero da
1 a 99; le parole diventano facoltative se c'è un altro criterio fra `prezzo_min`, `prezzo_max`, `sconto_min`,
`solo_coupon`, `canali` (`escludi` da solo non è un criterio); `notify: true` senza parole è un errore.
`canali_src` conserva le voci normalizzate ma non espanse, `canali` resta l'insieme espanso.

`rules.matches` valuta nell'ordine canali, prezzo massimo e minimo, `sconto_min`, `solo_coupon`, `escludi`, e
infine le parole, che non si applicano se la regola non ne ha.

`cmd_filtra`: `parole` diventa `nargs="*"`, nuove opzioni `--sconto-min` e `--solo-coupon`, uscita 2 con lo
stesso testo della config se mancano parole e ogni altro criterio. Il testo sta in `CRITERI_REGOLA`
(`config.py`), importato dalla CLI, così esiste in un posto solo.

`config.yaml`: i tre parametri della dashboard nel blocco `parametri`, con il commento.

### Test

149 prima, **166 dopo** (+17): `test_rules.py` da 11 a 25, `test_cli.py` da 12 a 15.
Coperti `sconto_min`, `solo_coupon`, parole opzionali con `escludi` ancora attivo, conservazione delle stringhe
sorgenti, rifiuto di `sconto_min` fuori scala (0, 100, `"x"`, 30.5, `True`), regola senza criteri, regola con
soli criteri numerici, `notify` senza parole, `dashboard_max_offerte` a 0 e a 1, `offerte filtra --sconto-min 30
--solo-coupon` senza parole su offerte salvate.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 166 passed in 0,27 s |
| controllo trattini | nessuna riga |
| `uv run offerte --help` | ok |
| `uv run offerte -c /tmp/offerte-prova/config.yaml filtra` (senza criteri) | uscita 2 con il messaggio dei criteri |

A18, A19 e A20 soddisfatti.

### Deviazioni

- Il paragrafo delle regole nel README e la riga di `offerte filtra` nella tabella dei comandi sono stati
  aggiornati qui invece che in S5, dove la specifica li colloca: descrivono `sconto_min`, `solo_coupon` e le
  parole facoltative, cioè proprio il codice di questo commit. S5 mantiene il resto del suo elenco.
- I conteggi per file dei test di S0 nel blocco precedente sono stati corretti ai valori reali (misurati con
  `pytest --collect-only`).

### Lasciato aperto

Niente di S1.

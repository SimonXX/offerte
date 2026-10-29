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

Nuovi file: `tests/test_cli.py` (13), `tests/test_stato.py` (4). Aggiunte a `test_extract.py` (+25),
`test_links.py` (+2), `test_sources.py` (+24), `test_http.py` (+3), `test_dedupe.py` (+3),
`test_fetch.py` (+5), `test_store.py` (+2).

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

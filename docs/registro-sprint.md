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

## S2, dati e backend

Data: 29 ottobre 2026.

### Cosa è stato fatto

`feeds.py`: `safe_url` (solo http e https), `item_name` (nome senza prezzo, ripiego `(senza titolo)`) da cui ora
parte `item_title`, `_epoch`, `dashboard_cartelle`, `dashboard_regole`, `dashboard_fonti`, `dashboard_offerta`,
`dashboard_bytes` (pura) e `write_dashboard`. La pulizia dei feed vecchi è ristretta a `cartella/*` e `regola/*`,
così `dashboard.json` nella radice sopravvive. `write_feeds` scrive anche `feeds.opml`, mette il link alla
dashboard e all'OPML in `index.html` e chiama `write_dashboard` in `try/except`: se la dashboard fallisce, feed,
notifiche e salvataggio dello stato arrivano comunque in fondo.

`cli.py`: sottocomando `feed`, che rigenera feed e dashboard dal database senza leggere i canali.

`src/offerte/static/`: i quattro file arrivano come segnaposto di una riga; il contenuto vero è di S3 e S4.

`tests/demo_dati.py`: `crea_db(path, n, now, seed)` con offerte sintetiche deterministiche sui 17 canali nelle 4
cartelle reali (80% con prezzo, circa metà di quelle con sconto, 8% con coupon, una quindicina viste su due
canali, testi con accenti e `c++`, 3 offerte ostili con `javascript:`, `data:` e `<img onerror>`), `scrivi_config`
e un `main` che riempie il database, applica le regole e scrive i feed.

### Contratto dati

Chiavi di testa: `v generato finestra_giorni troncato cartelle regole fonti offerte`. Il campo `fonti` è
l'integrazione chiesta dal prompt: una voce per fonte di `config.fonti`, anche inattive, nell'ordine di config,
con `nome`, `cartella` minuscola, `ogni`, `attiva` e, se presenti, `ultimo_fetch` e `stato`.

### Misure

| dataset | offerte | in chiaro | gzip -9 | `dashboard_bytes` |
|:--|--:|--:|--:|--:|
| giro reale su 17 canali (finestra 14 giorni) | 256 | 261.328 byte | 121.494 byte | - |
| demo deterministica | 6.003 | 3.067.912 byte | 323.704 byte | 49 ms |

1.021 byte per offerta in chiaro sul dataset reale, in linea con i 1.022 misurati nella specifica. La soglia di
A16 (sotto 1,5 s e sotto 8 MB su 6000 offerte) è rispettata con ampio margine.

### Test

166 prima, **192 dopo** (+26). Nuovo `tests/test_dashboard.py` (24), più `test_feeds.py` da 2 a 3 e
`test_fetch.py` da 6 a 7.

Coperti A2 (chiavi di testa e dell'offerta), A3 (nessun `null`, ricorsivo e sul testo), A4 (ordine per `(t, id)`
decrescente indipendente dall'ordine di lettura, finestra), A5 (troncamento), A6 (cartelle minuscole unite, con
le fonti inattive), A7 (stringhe sorgenti e slug, `dashboard_regole: false`), A8 (`safe_url` e ripiego sul
permalink), A9 (`item_name` senza testo), A10 (cinque file scritti e conservati, `cartella/vecchia.json`
rimossa, link nell'indice), A11 (`dashboard: false` rimuove i cinque file), A12 (isolamento con monkeypatch che
solleva), A13 (parametri da YAML e chiave sconosciuta rifiutata), A14 (asset non riscritti, mtime invariato),
A15 (`offerte feed`), A16 (prestazioni), A17 (`test_giro_completo` con 6 offerte e i quattro asset), più lo stato
delle fonti e l'OPML.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 192 passed in 0,50 s |
| controllo trattini | nessuna riga |
| `uv run offerte --help` | ok, nove sottocomandi |
| `uv run python tests/demo_dati.py /tmp/offerte-demo 600` | 600 offerte, 7 feed |
| `uv run offerte -c /tmp/offerte-prova/config.yaml feed` | scritti 7 feed, `dashboard.json` con 256 offerte |
| `offerte serve` più `curl` su `index.html`, `dashboard.json`, `feeds.opml`, `dashboard.html` | 200 su tutti e quattro |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

### Deviazioni

- `dashboard_bytes` prende `fonti` come quarto parametro, subito dopo `regole`, così l'ordine degli argomenti
  segue quello delle chiavi di testa. La specifica (§2.3 e §2.2) e il criterio A2 sono stati corretti.
- `write_feeds` scrive anche `feeds.opml` e `index.html` lo linka: integrazione chiesta dal prompt, aggiunta
  alla specifica in §2.1.
- §0 della specifica diceva che `docs/` non era tracciata: corretto.
- Problema 54 (collisione di slug fra cartelle che differiscono solo per le maiuscole) resta aperto e si è visto
  scrivendo il test dell'OPML: con `Informatica` e `informatica` in config, `write_feeds` scrive due volte
  `cartella/informatica.xml`. Il test dell'OPML usa quindi una config senza collisione. `dashboard_cartelle`
  non ne soffre, perché unisce le chiavi in minuscolo.

### Lasciato aperto

Problemi 4, 5, 6 e 25 chiusi da questo sprint. I quattro file statici sono segnaposto fino a S3 e S4.

## S3, motore JavaScript

Data: 29 ottobre 2026.

### Cosa è stato fatto

`src/offerte/static/filtri.js`: motore puro in una IIFE che espone solo `globalThis.Filtri`. Nessun DOM,
nessuna rete, nessuna libreria. Funzioni: `statoDefault`, `slug`, `traduciRegex`, `compilaVoce`, `compila`,
`periodoSecondi`, `insiemeCanali`, `applica`, `ordina`, `gruppiAttivi`, `togliGruppo`, `copiaStato`,
`leggiUrl`, `scriviUrl`, `statoDaRegola`, `regolaUguale`, `nomeSuggerito`, `yamlRegola`.

La traduzione delle regex Python scorre la stringa carattere per carattere tenendo conto delle classi:
`\b` e `\B` diventano confini Unicode con lookbehind, `\w` `\W` `\d` `\D` passano a `\p{L}\p{N}_` e `\p{Nd}`,
`(?P<n>` diventa `(?<n>`, `(?P=n)` diventa `\k<n>`, `\A` e `\Z` diventano `^` e `$`, `(?i)` iniziale si toglie e
gli escape di punteggiatura che JS con il flag `u` rifiuta perdono il backslash. Le espressioni con lookbehind
stanno in stringhe, mai in literal, e si compilano con `new RegExp` in `try/catch`: dove il motore non le regge
si ripiega sulla regex grezza con flag `i` e un avviso.

`tests/js_runner.py` costruisce un solo script temporaneo (sorgente di `filtri.js`, i casi come costante, un
harness fisso) e lo lancia con gjs, node, deno o bun: nessun file letto dal JS, nessun argomento, stesso
comportamento su tutti i motori.

`tests/fixtures/dashboard_casi.json`: 7 fonti (cartelle in maiuscole miste, una cartella che si chiama come un
canale, un canale inattivo, canali `on` e `no`), 40 offerte, 51 casi, 6 stati per l'andata e ritorno dell'URL,
8 URL non validi, 22 vettori di regex, 4 regole per i preset.

### Deviazioni

- `traduciRegex` restituisce anche `errore` quando incontra una flag inline diversa da `(?i)` iniziale: la
  specifica (§3.2) dichiara `{src, avvisi[], tradotta}` ma chiede anche che quella flag sia un errore con un
  messaggio preciso, e un avviso non basta. `compilaRegex` lo trasforma in `{ok: false, errore}`.
- `applica` accetta anche il caso in cui `compila` ha errori: il filtro testo si spegne e gli altri restano,
  come previsto; i casi con regex non valida sono quindi `solo_js`, perché Python non ha un equivalente.
- Il caso `budget-superato` della fixture ripete le offerte venti volte (800 righe): con 40 il controllo del
  budget, che scatta ogni 200 offerte, non si sarebbe mai attivato.
- A26 è verificato in `tests/test_dashboard_web.py`, creato qui con i soli controlli su `filtri.js`; in S4 lo
  stesso file copre anche HTML e CSS.

### Test

192 prima, **227 dopo** (+35). `tests/test_dashboard_js.py` (6 test per 4 motori = 24) e
`tests/test_dashboard_web.py` (11: 9 identificatori vietati, lookbehind, superficie esposta).

Python è l'oracolo: per i 36 casi non `solo_js` nessun esito è scritto a mano. `test_parita_con_python`
costruisce la `Rule` equivalente allo stato e confronta la sequenza di id, ordine compreso;
`test_yaml_andata_e_ritorno` scrive lo YAML prodotto dal JS sotto `regole:` in una config temporanea, la carica
con `load_config` e confronta di nuovo; `test_preset_da_regola` fa lo stesso partendo da `statoDaRegola`.
`test_regex_come_python` confronta 22 vettori con `re.search(src, testo, re.I)`.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 227 passed in 0,87 s |
| motori trovati | gjs, node, deno, bun: tutti e quattro danno gli stessi id su tutti i casi |
| controllo trattini | nessuna riga |
| `uv run offerte --help` | ok |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

A21, A22, A23, A24, A25 e A26 soddisfatti.

### Lasciato aperto

`dashboard.html`, `dashboard.css` e `dashboard.js` sono ancora segnaposto: S4.

## S4, pagina

Data: 29 ottobre 2026.

### Cosa è stato fatto

`src/offerte/static/dashboard.html`: struttura completa, meta CSP come primo elemento dopo `<meta charset>` e
prima di ogni `<script>` e `<link>`, nessuno script né stile inline, nessun attributo `style` o `on*`, tutti i
37 id obbligatori più `stato-testo`, `stato-fonti`, `elenco-fonti`, `motivo-regola`, `scorciatoie-prezzo`,
`cart-gruppo`, `canali`, `riga-tutte`, `filtri-titolo`, `stato-fonti-titolo`, `aiuto-q`, `titolo-dialogo`.

`dashboard.css`: dodici token di colore, ridefiniti identici sotto `@media (prefers-color-scheme: dark)` con
`:root:not([data-theme="light"])` e sotto `:root[data-theme="dark"]`. Una colonna sotto i 900 px con gutter di
16 px, due colonne sopra con la sinistra sticky da 320 px e la destra a 56 rem. Campi a 16 px (niente zoom di
iOS al focus), aree toccabili da 44 px, nessuna animazione, nessun font esterno.

`dashboard.js`: caricamento con `fetch("dashboard.json", {cache: "no-cache"})` e i sette stati di §3.11,
controlli letti e scritti dallo stato, URL con `history.replaceState`, debounce di 200 ms su testo e numeri,
schede costruite con `createElement` e `textContent`, 60 per volta con `DocumentFragment`, un solo listener per
contenitore (la delegazione dell'evento `error` delle immagini usa la fase di cattura, perché `error` non
risale), preset con conteggio calcolato nel browser, chip dei gruppi attivi, suggerimento quando l'elenco è
vuoto, toast con «Annulla» per l'azzeramento, dialogo `<dialog>` con YAML e copia, riquadro delle fonti con
punto colorato decorativo (`aria-hidden`) e testo esplicito.

`tests/riferimento.py`: oracolo condiviso fra i test del motore e quelli della pagina (`regola_dello_stato`,
`ordina`, `seleziona`), così l'atteso è scritto una volta sola.

`tests/web/layout.html`: cinque iframe a 320, 360, 390, 768 e 1280 px che scrivono `scrollWidth` e
`clientWidth` in `<pre id="esito">`; con `?w=360&h=900&tema=dark` mostra un solo riquadro e forza il tema, per
gli screenshot.

### Test

227 prima, **286 dopo** (+59). `tests/test_dashboard_web.py` da 11 a 65 (A27, A28, A29),
`tests/test_dashboard_browser.py` nuovo (5 test, 24 URL di riferimento).

I 24 URL di `test_url_riferimento` coprono parola semplice, due parole, `tutte`, regex, escludi, prezzo massimo,
prezzo minimo 0, minimo e massimo, `pmin > pmax` scambiati, `smin`, `cp`, sconto più coupon, cartella, cartelle
multiple, canale, cartella più canale, canale sconosciuto, i sei ordinamenti e una combinazione di cinque
filtri. Il riferimento lo calcola Python con `rules.matches` più periodo e ordinamento.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 286 passed in 36,5 s (35 s sono i dodici avvii di Chrome) |
| controllo trattini | nessuna riga |
| Chrome headless su `dashboard.html` con dati demo | `data-stato="pronto"`, 303 offerte, 60 schede, preset con conteggio |
| screenshot a 360 px con tema scuro | leggibile, `scrollWidth` 345 uguale a `clientWidth` |
| screenshot a 1400 px | due colonne, pannello sticky, schede corrette |
| `file://dashboard.html` | `data-stato="errore-file"` |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

A27, A28, A29, A30, A31, A32 e A33 soddisfatti.

### Difetti trovati e corretti durante lo sprint

Con l'immagine che non carica, la scheda restava a due colonne e il testo finiva nei 72 px: ora il listener di
`error` aggiunge anche la classe `senza-foto` all'articolo. Visto in uno screenshot a 1400 px, non dai test.

### Deviazioni

- Il dialogo «Crea regola» non si apre nei test automatici: `--dump-dom` non fa clic. Lo stato del pulsante e
  il motivo visibile sono verificati nel DOM, e `yamlRegola` è coperto dai test del motore su quattro runtime.
  La prova a mano del dialogo resta in A36.
- `#stato-fonti` sta dentro `#stato-dati`, che è quindi un `<div role="status">` con dentro un `<p>` per il
  testo: un `<details>` non può stare dentro un `<p>`.

### Lasciato aperto

README, versione 0.3.0, `uv lock`, controllo della wheel e prova su telefono: S5.

## S5, chiusura

Data: 29 ottobre 2026.

### Cosa è stato fatto

README: sezione «Dashboard» fra «Feed» e «Miniflux» con apertura in locale e su Pages, accesso da telefono con
`serve --host <IP LAN>`, tabella dei dieci parametri dell'URL, differenze fra regex Python e JavaScript,
`offerte feed`, `dashboard: false` e `dashboard_regole: false`, il paragrafo su cosa espone `dashboard.json`
su Pages e le dimensioni misurate. Riga `offerte feed` nella tabella dei comandi; `dashboard.html` e
`feeds.opml` nell'elenco dei feed; `static/` e `tests/demo_dati.py` nella struttura; in «Test» la frase sui
motori JavaScript e su Chrome headless.

Versione 0.3.0 in `pyproject.toml` e `src/offerte/__init__.py`, poi `uv lock`. La docstring del pacchetto parla
di fonti, non solo di Telegram, come già la descrizione in `pyproject.toml`.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 286 passed in 36,5 s |
| controllo trattini | nessuna riga |
| `uv run offerte --version` | `offerte 0.3.0` |
| `uv lock --check` | Resolved 21 packages, nessuna modifica |
| `git diff --stat pyproject.toml uv.lock` | 2 file, 2 righe: solo la versione |
| `uv build --out-dir /tmp/offerte-wheel` | wheel e sdist costruiti |
| `unzip -l offerte-0.3.0-py3-none-any.whl` | contiene `offerte/static/` con i quattro file |
| screenshot a 320 px con `?q=ssd&pmax=1000` | `scrollWidth` 305 uguale a `clientWidth`, tutto leggibile |
| screenshot a 360 px con tema scuro | leggibile, nessuno scroll orizzontale |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

A34 e A35 soddisfatti.

### A36, prova su telefono

**Non eseguita: non ho un telefono a disposizione in questa sessione.** Al suo posto sono stati eseguiti i test
a 320, 360, 390, 768 e 1280 px (`test_layout_senza_scroll`, iframe in Chrome headless: `scrollWidth` mai
maggiore di `clientWidth`) e due screenshot a 320 e 360 px, uno per tema. Restano da provare a mano sul
telefono: lo zoom di iOS al focus (i campi sono a 16 px, che è la condizione per non averlo), la punteggiatura
intelligente che trasformerebbe apici e trattini nelle regex (`autocorrect="off"` e `autocapitalize="none"` su
tutti i campi di testo), «Copia link» e «Copia YAML» su http da IP di LAN (contesto non sicuro: il codice
ripiega su `execCommand`), la chiusura del dialogo con Esc.

### Deviazioni

Nessuna.

### Lasciato aperto

S6: le due opzioni della fonte `rss`, `config.locale.yaml` e la sezione «Fonti pronte» del README.

## S6, fonti pronte

Data: 29 ottobre 2026.

### Cosa è stato fatto

Fonte `rss`, due opzioni nuove, entrambe in `chiavi`:

- `url_env: NOME` legge l'URL da `os.environ[NOME]` a ogni fetch, non in `configura`. Se la variabile manca si
  solleva `FetchError`, che ferma quella fonte e non il giro. `url` e `url_env` si escludono a vicenda e uno dei
  due è obbligatorio (`ConfigError`).
- `scarta_host: host` toglie da `links` i link verso quell'host e i suoi sottodomini, lascia vuoto il permalink
  che punta lì e, in più rispetto alla specifica, azzera anche l'immagine che punta lì: sarebbe finita
  nell'`enclosure` del feed con dentro l'identificativo.

`Client.get(url, nome=None)`: i log di riprova e i `FetchError` mostrano il `nome` se passato, altrimenti
l'URL senza query (`scheme://host/path`, con le credenziali tolte). `RssSource.fetch` passa `nome=self.nome`
quando l'URL viene da `url_env`.

`config.locale.yaml` in `.gitignore`; i tre blocchi `fonti:` commentati in `config.yaml`; sezione «Fonti pronte»
nel README con, per ciascuno strumento, cosa fa, quando non usarlo, il comando `podman run`, la configurazione
minima per ottenere un feed e il blocco `fonti:` pronto, più la riga `Environment=OFFERTE_CONFIG=...` per
`systemd/offerte-fetch.service`.

### Un difetto trovato scrivendo il test

Il test chiesto dal prompt («né `caplog.text` né `channels.last_error` contengono SEGRETO») falliva: le nostre
righe erano pulite, ma `httpx` logga ogni richiesta con l'URL completo a livello INFO. Il silenziamento esisteva
già, in `log.py`, quindi valeva solo per chi passa dalla riga di comando. È stato spostato in `http.py`, dove
nasce la perdita e dove vale per chiunque costruisca un `Client`; `log.py` conserva una riga di commento che
rimanda lì.

### Test

286 prima, **293 dopo** (+7), tutti in `tests/test_sources.py`: `url_env` che legge la variabile e che solleva
quando manca, esclusività di `url` e `url_env` nei due versi, `scarta_host` su link, permalink e immagine,
l'identificativo del feed assente da ogni file di `var/feeds/` dopo un giro completo, il token fuori dai log e
da `channels.last_error`, e `etichetta()` sui tre casi (con nome, senza nome, con credenziali nell'URL).

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 293 passed in 36,6 s |
| controllo trattini | nessuna riga |
| `uv run offerte --help` | ok |
| `uv run offerte -c /tmp/offerte-prova/config.yaml fetch --storico 1 --senza-notifiche` | 17 fonti su 17 ok, 20 post nuovi, 19 offerte nuove |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

### Misure finali su dati reali

`dashboard.json` con 275 offerte nella finestra di 14 giorni: 278.577 byte in chiaro, 129.434 byte con
`gzip -9`, cioè 1.013 byte per offerta. I numeri nel README sono questi.

### Prova dal vivo di changedetection.io

**Prova reale non eseguita.** Richiede un container con volume e un cambio di prezzo vero su una pagina seguita,
che in questa sessione non era osservabile. La sezione del README è segnata «non provata» e dichiara che la
configurazione viene dalla lettura della documentazione e del codice dello strumento.

### Deviazioni

- `scarta_host` filtra anche l'immagine, non solo link e permalink: senza, l'URL del pixel di tracciamento di
  kill-the-newsletter sarebbe finito nell'`enclosure` del feed pubblico, e il test sull'identificativo assente
  da `var/feeds/` sarebbe fallito.
- Il silenziamento dei logger `httpx` e `httpcore` si è spostato da `log.py` a `http.py`, per la ragione scritta
  sopra.

### Lasciato aperto

Niente di S6.

## S7, copertura mancante di S0

Data: 29 ottobre 2026.

### Perché esiste questo commit

Il prompt chiede sette commit, uno per sprint, e dice anche che «un numero è chiuso solo se esiste un test che
lo copre». Rileggendo S0 prima della consegna, otto problemi avevano la correzione ma non il test: 7 e 12
(tetto delle pagine nei giri incrementali), 13 e 32 (link malformato dentro `process_message`), 39 (chiavi
`ogni`, `canale`, `pagine` nelle voci di `canali:`), 40, 41, 56 e 66 (coerenza del README). Metterli nel commit
di S6 avrebbe mescolato due sprint, rifare la storia dei sei commit precedenti era peggio: questo commit
contiene solo quei test, nient'altro. **Deviazione: i commit nuovi sono otto, non sette.**

### Test aggiunti

293 prima, **301 dopo** (+8), nessuna riga di codice di produzione toccata.

| test | problema |
|:--|:--|
| `test_telegram_primo_giro_si_ferma_a_pagine_storico` | 12 |
| `test_telegram_giro_incrementale_recupera_il_pregresso` (undici pagine fino a `last_id`, non tre) | 7, 12 |
| `test_telegram_avvisa_se_le_pagine_finiscono_prima` | 7 |
| `test_voci_di_canali_accettano_ogni_canale_pagine` | 39 |
| `test_link_malformato_non_fa_sparire_il_messaggio` (tel:, mailto:, porta non numerica) | 13, 32 |
| `test_load_env_prima_di_load_config` (`OFFERTE_FEED_BASE_URL` in `.env` finisce nei link dell'indice) | 60 |
| `test_readme_elenca_tutti_i_sottocomandi` (confronto con `COMMANDS`) | 56 |
| `test_readme_sulle_opzioni_globali_e_sul_container` | 40, 41, 66 |

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 301 passed in 36,5 s |
| controllo trattini | nessuna riga |
| `ls -l var` e conteggio offerte del repository | mtime invariati, 0 offerte |

## S8, finestra temporale comandabile dalla pagina

Data: 29 ottobre 2026.

### Decisione presa

La dashboard resta in **sola lettura**. Un endpoint che scrive `config.yaml` sarebbe, nei fatti, un endpoint
che esegue comandi arbitrari, perché la config ammette fonti di tipo `comando`; con `serve --host 0.0.0.0` quella
porta è aperta anche alla rete locale e non c'è autenticazione. Renderla sicura vuol dire sessioni, CSRF e un
segreto da gestire: troppo, per cambiare un interruttore che si tocca una volta ogni tanto stando al PC. Dove
serve, la pagina genera il testo da incollare, come fa già «Crea regola». Se la comodità mancherà davvero, la
versione difendibile è un endpoint locale ristretto a interruttori booleani su canali e regole che esistono già,
mai stringhe libere, e si farà con il suo sprint.

### Cosa è stato fatto

Il menu Periodo si fermava a 7 giorni mentre la pagina ne conteneva 14 e il database 90. Due interventi.

`dashboard_giorni` in `Params`, assente di default: la finestra della pagina si stacca da quella dei feed.
`feed_giorni` continua a governare RSS, JSON Feed e la valutazione delle regole a ogni giro; `dashboard_giorni`
governa solo `dashboard.json` e il campo `finestra_giorni`. Serviva perché alzare `feed_giorni` a 60 avrebbe
fatto rivalutare le regole su due mesi di offerte ogni dieci minuti, per un effetto che riguarda solo la pagina.
Minore di 1 è `ConfigError`.

I periodi diventano generici: `periodoSecondi` riconosce `<numero>h` e `<numero>g` da 1 a 999 invece di
consultare una tabella fissa, e `leggiUrl` accetta di conseguenza. Il menu si costruisce a ogni caricamento dalla
scala 1h, 3h, 6h, 12h, 24h, 48h, 3g, 7g, 14g, 30g, 60g, 90g tenendo i gradini più stretti di `finestra_giorni`;
la prima voce dichiara la finestra («Tutto il periodo (60 giorni)»). Un `per` che arriva dall'URL fuori scala si
aggiunge in coda invece di sparire in silenzio.

### Test

301 prima, **305 dopo** (+4): `dashboard_giorni` che allarga la finestra lasciando i feed dov'erano,
`dashboard_giorni` assente che segue `feed_giorni`, `dashboard_giorni: 0` rifiutato, e la scala dei periodi nel
JS. Più la fixture del motore: `per=99h` non è più un valore da scartare (ora è un periodo valido di 99 ore), al
suo posto c'è `per=boh`, e sono stati aggiunti un andata e ritorno con `per=30g` e un caso `solo_js` con `90g`.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 305 passed in 36,9 s |
| controllo trattini | nessuna riga |
| demo con `dashboard_giorni: 60`, menu letto in Chrome | voci fino a `30g`, prima voce «Tutto il periodo (60 giorni)» |
| `?per=48h`, `?per=7g` sulla stessa demo | 58 e 184 offerte su 403: il filtro stringe davvero |
| `?per=90g` con finestra 60 | periodo conservato e mostrato come voce in coda |

### Deviazioni

La specifica fissava gli otto valori di `per` in §3.2, §3.5 e §3.7: corretta in tutti e tre i punti con la regola
generica, e in §2.2 per `finestra_giorni`.

### Nota di lavoro

`pkill -f "offerte.*serve"` uccide anche la shell che lo esegue, perché il pattern combacia con la propria riga
di comando. Si usa `pkill -x offerte`.

## S9, ricerca per sottostringa e canali nuovi

Data: 29 ottobre 2026.

### Il difetto

Cercando `citofono` nella dashboard: nessun risultato, mentre nel database c'era «Blink Outdoor 4 con Blink
**Videocitofono** 2K+». Una voce scritta semplice era cercata come parola intera, perché il motore rispecchiava
`compile_keyword` di `config.py`. Corretto per le regole, sbagliato per una casella di ricerca: chi scrive
«citofono» si aspetta «videocitofono». L'unico modo di ottenerlo era scrivere `/citofono/` a mano, cioè
conoscere una sintassi.

### Cosa è stato fatto

Lo stato guadagna `pi` (parola intera), default **falso**: le voci semplici si cercano come sottostringa.
L'interruttore «Solo parola intera» sta sotto il campo Parole, fuori dal pannello dei filtri, e compare appena
scrivi qualcosa. Nell'URL è `pi=1`.

La parità con `rules.matches` è preservata, ed è il punto delicato: con `pi` falso, «Crea regola» esporta le
voci semplici come regex (`parole: ['/citofono/']`) invece che come parole, così la regola in config seleziona
esattamente quello che la pagina mostrava. `statoDaRegola` fa il contrario e imposta `pi` a vero, perché le
parole scritte in `config.yaml` valgono come parola intera.

L'oracolo Python (`tests/riferimento.py`) rispecchia la regola: `compila_voce(voce, parola_intera)` usa
`compile_keyword` per le regex e per la parola intera, `re.escape` per la sottostringa.

### Canali

Da 17 a 23. Risolti provando gli username e verificando il titolo restituito da `t.me/s/`:

| canale | titolo verificato | volume | cartella |
|:--|:--|--:|:--|
| `offertecasatecno` | Offerte casa | ~34/g | casa |
| `offertetecnomela` | Offerte e Sconti Mela | ~12/g | informatica |
| `tecnocina` | Offerte e Sconti Cina | ~150/g | cina |
| `mio_sconto` | Mio Sconto | ~51/g | casa |
| `bombeelettronica` | Offerte elettronica e informatica | ~27/g | informatica |
| `malati_di_risparmio` | MALATI DI RISPARMIO | ~5/g | casa |

`malati_di_risparmio` è stato aggiunto su richiesta esplicita, con una riserva scritta nel commento di
`config.yaml`: l'anteprima pubblica restituisce tre messaggi con la stessa riga generica, e il messaggio fissato
del canale annuncia il trasferimento su un canale privato (`t.me/+...`), che senza account e senza bot questo
strumento non può leggere.

Non risolti: «Banca delle Offerte» (provate cinque varianti, nessuna anteprima pubblica).

### Test

305 prima, **305 dopo** più 6 casi di fixture e 2 test nuovi. Tutti i casi esistenti della fixture dichiarano
ora `pi: true`, così continuano a provare la parola intera invece di dipendere dal default; i sei casi nuovi
provano la sottostringa (`tb` dentro `football`, `watch` dentro `watchè`, accenti, `c++`, punteggiatura, regex
mista) con Python come oracolo.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 305 passed in 36,6 s |
| controllo trattini | nessuna riga |
| `tb` parola intera contro sottostringa, sui 4 motori | 3 id contro 7, uguali in Python |
| YAML di una ricerca per sottostringa | `parole: ['/c\+\+/', '/prezzo: shock/']`, caricata da `load_config` |

### Deviazioni

La specifica §3.2 e §3.4 descrivevano `compilaVoce(voce)` con la sola semantica di parola intera, speculare a
`compile_keyword`. Ora la semantica dipende da `pi` e la specifica va aggiornata in quei due punti: **non ancora
fatto**, è il primo lavoro del prossimo giro.

## S10, storico prezzi a richiesta

Data: 29 ottobre 2026.

### Due meccanismi verificati prima di scrivere codice

`https://t.me/s/<canale>?q=<termine>` esiste e funziona: la ricerca interna di un canale restituisce quindici
messaggi per pagina, pagina con `&before=<id>` e pesca messaggi che la raccolta incrementale non ha mai
scaricato. Provato su `rafficaffari` con «dyson»: risultati fino a luglio 2025 in una sola richiesta.

`https://graph.keepa.com/pricehistory.png?asin=<ASIN>&domain=it&range=365` restituisce un PNG 500x200 con il
grafico reale del prezzo Amazon degli ultimi dodici mesi, senza chiave API e senza costo. Verificato su
`B0F1Z5982Y`: grafico leggibile con titolo, curva Amazon e curva New.

### Cosa è stato fatto

`search_channel_messages(client, channel, query, max_pages)` in `sources/telegram.py`, e il sottocomando
`offerte storico <termine> [--canali ...] [--pagine N]`: interroga la ricerca di ogni canale Telegram attivo,
estrae prezzo, titolo e link con la pipeline di sempre, e stampa la serie ordinata per data con minimo, massimo
e ultimo prezzo. Su «dyson v15» ha trovato 16 messaggi in 4 canali dal **11/11/2021** al 27/10/2026.

Nella dashboard, ogni scheda di un prodotto Amazon ha un `<details>` «Storico prezzi» che carica il grafico
**solo all'apertura**: con 60 schede in pagina non parte nessuna richiesta a terzi finché non clicchi. L'ASIN
arriva nel nuovo campo `a` della voce, estratto dalla chiave di dedupe; l'indirizzo del grafico arriva nel nuovo
campo di testa `grafico`, che viene dal parametro `grafico_prezzi`. Vuoto, la funzione sparisce.

L'indirizzo sta nei dati e non nel sorgente JavaScript, così il controllo A27 (nessun `https://` nei file
statici) resta valido ed è il parametro, non il codice, a decidere quale servizio interrogare.

### Test

307 prima, **311 dopo** (+4): ASIN presente solo per le chiavi Amazon (quattro chiavi non Amazon verificate),
campo `grafico` presente e assente, `grafico_prezzi: ""` letto dalla config, e il controllo che l'immagine si
crei all'apertura e non al rendering.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 311 passed in 36,6 s |
| controllo trattini | nessuna riga |
| `offerte storico "dyson v15" --canali raffica informatica --pagine 1` | 16 messaggi, 4 canali, dal 2021 |
| Chrome su `?q=asus` | 23 schede con «Storico prezzi», **0** immagini caricate prima del clic |

### Nota di riservatezza

Aprire il grafico comunica al servizio quale prodotto si sta guardando. La pagina manda `no-referrer`, quindi
non comunica da dove, e la richiesta parte solo al clic. Si spegne con `grafico_prezzi: ""`.

## S11, regole come campagne accendibili

Data: 29 ottobre 2026.

### Cosa è stato fatto

`Rule` guadagna `attiva: bool = True` e `Config.regole_attive()`. Una regola spenta resta scritta in
`config.yaml` ma non viene valutata da `apply_rules`, non entra fra i nomi passati a `pending_notifications`,
e il suo feed non viene più scritto: la pulizia di `write_feeds` lo rimuove da sola al giro dopo.

`dashboard_regole` continua a esporre **tutte** le regole, con il campo `attiva`, perché la pagina le mostri
come preset dormienti: una campagna spenta compare con il bordo tratteggiato e l'etichetta «spenta», senza
link RSS, e il suo conteggio dice cosa pescherebbe se la riaccendessi. Il filtro si può applicare lo stesso.

`config.yaml` ha ora sei regole, tre accese e tre spente d'esempio, fra cui due campagne RAM
(`ram-ddr5-32gb-sotto-90`, `ram-ddr4-16gb-sotto-35`) e una senza parole (`sconti-oltre-70-con-coupon`).

Riaccendere una regola la fa ripartire dalle offerte ancora dentro `feed_giorni`, non da tutto lo storico:
`apply_rules` lavora sulla finestra, non sul database intero. Documentato nel README.

### Test

311 prima, **314 dopo** (+3): regola spenta che resta in config ma fuori da `regole_attive()`, giro completo in
cui la spenta non registra match e non scrive il feed mentre l'accesa sì, e presenza della spenta fra le voci
di `dashboard_regole` con `attiva: false`.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 314 passed in 36,4 s |
| controllo trattini | nessuna riga |
| `load_config` su `config.yaml` | 6 regole, 3 attive |
| Chrome sulla dashboard | sei preset, tre «accesa» e tre «spenta» con il conteggio |

### Errore commesso durante il lavoro

La prima scrittura degli esempi ha usato `s.index("regole:")`, che ha trovato `dashboard_regole:` nel blocco
dei parametri e ha troncato il file da lì in poi, cancellando `canali:`. Ripristinato con `git checkout` e
rifatto con un ancoraggio `^regole:$`. Il controllo che l'ha intercettato è stato `load_config`, non i test.

## S12, raccolta ferma contro fonti rotte

Data: 29 ottobre 2026.

### Il difetto

Appena online, la dashboard diceva «Fonti (23 con problemi)» ed elencava tutte e 23 le fonti come «ferma da
55 min», mentre lo stato di ognuna era `ok`. Il fatto era uno solo, ripetuto ventitré volte: da 55 minuti non
girava nessuna raccolta. Un guasto globale presentato come ventitré guasti locali manda a cercare nel posto
sbagliato.

### Cosa è stato fatto

`saluteFonte` restituisce ora un `tipo` (`ok`, `inattiva`, `mai`, `ferma`, `errore`, `vuota`) invece di un
booleano `problema`, e `mostraFonti` decide la presentazione guardando l'insieme: se nessuna fonte è in errore
e sono ferme **tutte** quelle attive, il titolo diventa «Raccolta ferma da N, nessuna fonte in errore» e le
singole righe tornano verdi con l'ora dell'ultima lettura, perché la fonte sta bene. Restano «Fonti (N con
problemi)» quando qualcuna è davvero rotta, «Fonti (N ferme)» quando sono solo alcune, e «Fonti (N, tutte ok)»
quando va tutto.

### Causa reale del fermo

Una sola esecuzione, quella del push. Il cron non era partito perché al momento del push il branch predefinito
del repository era `data`: `deploy/stato.sh save` lo aveva spinto per primo su un repository vuoto e GitHub lo
aveva eletto predefinito. Le esecuzioni pianificate si registrano dal branch predefinito, che non conteneva il
workflow. Corretto con `gh api --method PATCH repos/SimonXX/offerte -f default_branch=main`.

**Da ricordare per il prossimo deploy da zero**: spingere `main` prima di seminare il branch `data`, oppure
correggere subito il branch predefinito. Vale la pena scriverlo nel README.

### Test

314 prima, **315 dopo**: controllo statico che la distinzione fra raccolta ferma e fonti rotte esista nel
sorgente.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 315 passed in 35,5 s |
| Chrome sulla dashboard con dati di un'ora fa | «Raccolta ferma da 1 h, nessuna fonte in errore», zero punti di avviso |
| `gh run list` | una sola esecuzione da push, cron non ancora agganciato |

## S13, mandarsi un'offerta in chat

Data: 29 ottobre 2026.

### Il vincolo

La pagina è statica e, su Pages, pubblica. Mandare un messaggio con l'API del bot richiederebbe il token dentro
la pagina, cioè pubblicarlo: escluso. Si usa invece il selettore di condivisione di Telegram
(`t.me/share/url?url=...&text=...`), che è un semplice link: apre l'app, l'utente sceglie la chat, nessuna
credenziale in giro.

### Cosa è stato fatto

Parametro `condividi_url` (vuoto = funzione spenta), esposto nel campo di testa `condividi` di
`dashboard.json`. Ogni scheda con un link utilizzabile mostra «Mandamelo in chat» con nome, prezzo, sconto e
coupon nel testo e il link dell'offerta nel parametro `url`. Come per il grafico, l'indirizzo sta nei dati e non
nel sorgente JavaScript, così il controllo A27 resta valido.

### Test

315 prima, **317 dopo** (+2): campo `condividi` presente e assente nella testa, e controllo che in
`dashboard.js` non compaiano `api.telegram.org`, `sendMessage` né riferimenti al token.

### Comandi di verifica eseguiti

| comando | esito |
|:--|:--|
| `uv run pytest -q` | 317 passed in 35,7 s |
| Chrome su `?q=ssd&pmax=100` | 9 schede, 9 pulsanti |
| codifica dell'href | `%26` per la `&` interna all'URL Amazon: Telegram riceve il link intero |

## Nota: giro profondo concluso

25.912 post letti, 17.053 offerte nuove, **16.810 in archivio** dal 31 luglio al 29 ottobre, database di 27 MB.
Le regole hanno registrato 13 corrispondenze per `ssd-sotto-60`, 36 per `apple-watch-sotto-250` e 347 per
`errori-di-prezzo`. La ricerca di `oura`, che prima non dava nulla, trova ora le quattro pubblicazioni dell'Oura
Ring 4 del primo e del cinque ottobre.

**Lo storico profondo resta in locale e non viene travasato sul cloud.** Il motivo è che non servirebbe: online
`dashboard_giorni` non è impostato, quindi la finestra della pagina è quella dei feed, 14 giorni, e tre mesi di
storico resterebbero invisibili. In compenso sovrascrivere il branch `data` cancellerebbe le righe di
`notifications` scritte da Actions, con il rischio di rinotificare le offerte delle ultime 24 ore. Se un domani
servisse davvero, il travaso va fatto riportando prima quelle righe nel database locale abbinandole per `key`,
perché gli id delle offerte nei due database sono indipendenti.

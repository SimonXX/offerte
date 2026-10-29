# Specifica: dashboard offerte filtrabile (pagina statica)

## 0. Contesto e vincoli

Repository: `~/Projects/repos/offerte`, branch `main`, commit `16e8709`, Python 3.12, uv. `uv run pytest -q` dava 73 test verdi; dopo S0 e S1 ne dà 192. `var/offerte.sqlite` è vuoto (0 offerte), quindi per provare la pagina servono dati demo (si creano in S2). La cartella `docs/` è tracciata dal commit `bb1ccd0`. Si usa sempre `git add <percorso>`, mai `git add -A` né `git add .`, per non trascinare `var/` o file di prova.

Stato letto nel codice:

- `write_feeds` (`src/offerte/feeds.py:137-165`) scrive a ogni giro un RSS e un JSON Feed per cartella e per regola, tagliati a `feed_max_elementi` (200 in `config.yaml:10`, default 100 in `config.py:43`), più `index.html` (`feeds.py:164`).
- I feed non bastano come sorgente dati. La sola cartella `raffica` fa circa 280 post al giorno (`config.yaml:35-37`), quindi 200 elementi coprono meno di un giorno. In più `content_html` duplica il testo.
- `Store.offers_since(since)` (`store.py:193-195`) restituisce già tutte le offerte della finestra `feed_giorni`, ordinate per `posted_at` decrescente.
- `serve.py:13-26` serve qualunque file sotto `var/feeds` con `Cache-Control: no-cache`. Il workflow `.github/workflows/offerte.yml:55-57` pubblica `var/feeds` intero su GitHub Pages. Entrambi restano invariati.
- Sul branch `data` si salva solo `offerte.sqlite` (`deploy/stato.sh`): `var/feeds` si rigenera a ogni giro.
- Le regole valgono sul testo intero del messaggio: `rules.matches` (`rules.py:9-19`) usa `offer.text`.

Vincoli non negoziabili:

- Costo zero.
- Nessun server dinamico: tutto funziona servito da file statici, in locale e su Pages, con soli URL relativi.
- Nessuna nuova dipendenza Python e nessun passo di build.
- JavaScript vanilla, nessuna libreria, nessuna CDN: nessun `<script src>` né `<link href>` assoluto. Decisione presa dopo la revisione del 29.10.2026: MiniSearch non ha un posto in un filtro che deve dare gli stessi id di `rules.matches`, Alpine richiede `unsafe-eval`, Simple.css impone una griglia globale in conflitto con il layout e con i token di colore di questa specifica. `docs/spunti-open-source.md` resta come riferimento per evoluzioni future.
- Interfaccia in italiano.
- Nessun trattino lungo (U+2014) né mezzo (U+2013) in nessun file scritto o modificato: codice, commenti, README, test.
- Leggibile su telefono (target iOS 15.4 e Chrome 100).

Convenzioni:

- Commit in inglese, imperativo, una riga, nello stile dei precedenti (`git log`: «Add retention of old offers and the pulisci command; bump to 0.2.0»).
- Nessun trailer `Co-Authored-By`, nessuna riga «Generated with», nessuna menzione di assistenti.
- Un commit per sprint, a test verdi.
- Commenti nel codice in italiano, come nel resto del repo.

Fuori perimetro, da non costruire: storico prezzi e sparkline, raggruppamento per prodotto, scorciatoie da tastiera, filtri salvati in localStorage, badge «nuove», pagine HTML per cartella o regola, shard per giorno, gzip in `serve.py`, modifiche a `serve.py`, `store.py`, `fetch.py` e al workflow.

## 1. File da creare o modificare

Percorsi relativi a `~/Projects/repos/offerte`.

| percorso | azione | contenuto |
|:--|:--|:--|
| `src/offerte/static/dashboard.html` | crea | Struttura della pagina, CSP in meta, nessuno script o stile inline. |
| `src/offerte/static/dashboard.css` | crea | Token di colore chiaro e scuro, layout telefono e desktop. |
| `src/offerte/static/filtri.js` | crea | Motore puro senza DOM, esposto come `globalThis.Filtri`. |
| `src/offerte/static/dashboard.js` | crea | Interfaccia: caricamento, controlli, rendering, URL, dialogo regola. |
| `src/offerte/feeds.py` | modifica | `item_name`, funzioni dashboard, pulizia ristretta, link nell'indice, chiamata protetta. |
| `src/offerte/config.py` | modifica | `Rule` e `Params` estesi, validazioni. |
| `src/offerte/rules.py` | modifica | `matches` con `sconto_min`, `solo_coupon`, parole opzionali. |
| `src/offerte/cli.py` | modifica | Sottocomando `feed`, nuove opzioni di `filtra`. |
| `tests/demo_dati.py` | crea | Generatore di dati demo, eseguibile a mano. |
| `tests/js_runner.py` | crea | Esegue `filtri.js` con gjs, node, deno o bun. |
| `tests/fixtures/dashboard_casi.json` | crea | Offerte e casi di prova condivisi. |
| `tests/web/layout.html` | crea | Pagina di prova per larghezze strette e screenshot. |
| `tests/test_dashboard.py` | crea | Contratto dati, pulizia, isolamento, CLI, prestazioni. |
| `tests/test_dashboard_web.py` | crea | Controlli statici su HTML, CSS e JS. |
| `tests/test_dashboard_js.py` | crea | Motore su ogni runner disponibile, parità con Python. |
| `tests/test_dashboard_browser.py` | crea | Chrome headless sulla pagina vera. |
| `tests/test_rules.py` | modifica | Test dei criteri nuovi e della CLI `filtra`. |
| `tests/test_feeds.py` | modifica | Test di `item_name`. |
| `tests/test_fetch.py` | modifica | Asserzioni dopo la riga 102, nuovo test di isolamento. |
| `README.md` | modifica | Sezione «Dashboard», tabella comandi, regole, struttura, test. |
| `config.yaml` | modifica | Tre parametri commentati nel blocco `parametri` (righe 3-13). |
| `pyproject.toml`, `src/offerte/__init__.py`, `uv.lock` | modifica | Versione 0.3.0 (`pyproject.toml:3`, `__init__.py:3`), poi `uv lock`. |

Invariati e verificati: `serve.py`, `fetch.py` (riga 162 chiama `write_feeds`, la protezione sta dentro `write_feeds`), `store.py`, `.github/workflows/offerte.yml`.

I quattro file statici stanno nella radice di `var/feeds/` accanto a `dashboard.json`, non in sottocartelle. La pulizia di `feeds.py:161-163` cancella ogni `.xml` e `.json` a profondità due non presente in `keep`, quindi un `dashboard.json` in sottocartella verrebbe eliminato al giro dopo.

## 2. Contratto dati

### 2.1 File generati in `var/feeds/` (radice)

| file | origine |
|:--|:--|
| `dashboard.json` | dati, scritto per ultimo a ogni giro |
| `feeds.opml` | elenco di tutti i feed scritti, un `outline` per cartella e uno per regola con `xmlUrl` assoluto; `index.html` lo linka |
| `dashboard.html`, `dashboard.css`, `filtri.js`, `dashboard.js` | copia byte per byte da `src/offerte/static/`, riscritta solo se i byte differiscono |

Tutti passano da `_atomic_write` (`feeds.py:112-115`). Ordine di scrittura: prima i quattro asset, poi `dashboard.json`.

### 2.2 Documento `dashboard.json`

Codifica UTF-8, `json.dumps(doc, ensure_ascii=False, separators=(",", ":"))`, nessun valore `null` in tutto il file (i campi assenti si omettono).

```json
{"v":1,"generato":1761685200,"finestra_giorni":14,"troncato":false,
 "cartelle":{"casa":["erroridiprezzo","mttcasa"],"informatica":["mttvideo","prezzitech"]},
 "regole":[{"nome":"ssd-sotto-60","slug":"ssd-sotto-60","parole":["ssd","nvme","/\\b[12]\\s?tb\\b/"],"escludi":[],"tutte":false,"prezzo_max":60,"solo_coupon":false,"canali":["informatica"]}],
 "fonti":[{"nome":"mttvideo","cartella":"informatica","ogni":0,"attiva":true,"ultimo_fetch":1761684000,"stato":"ok"}],
 "offerte":[{"id":4821,"t":1761684600,"n":"SSD Samsung 980 PRO 1TB","x":"testo intero\n79,99€ invece di 129€","k":["mttvideo","prezzitech"],"p":79.99,"b":129.0,"s":38,"c":"SSD10","u":"https://www.amazon.it/dp/B08GLX7TNT?tag=canale-21","m":"https://t.me/mttvideo/1234","i":"https://cdn4.telesco.pe/file/abc.jpg"}]}
```

Campi di testa:

| campo | tipo | valore |
|:--|:--|:--|
| `v` | int | versione del contratto, oggi `1` (costante `DASHBOARD_VERSIONE`) |
| `generato` | int | secondi epoch UTC, `int(now.timestamp())` |
| `finestra_giorni` | int | `p.feed_giorni` |
| `troncato` | bool | vero se le offerte della finestra superano `dashboard_max_offerte` e l'elenco è stato tagliato alle più recenti |
| `cartelle` | oggetto cartella (minuscola) -> lista ordinata di nomi di fonte | tutte le fonti di `config.fonti`, anche inattive, chiavi unite in minuscolo come `config.py:136-138`, chiavi ordinate |
| `regole` | lista di oggetti | vuota se `dashboard_regole` è falso, altrimenti una voce per regola in ordine di config |
| `fonti` | lista di oggetti | una voce per fonte di `config.fonti`, anche inattive, nell'ordine di config |
| `offerte` | lista di oggetti | vedi sotto |

Voce di `fonti`, da `dashboard_fonti(config, store)`:

| campo | tipo | presenza |
|:--|:--|:--|
| `nome` | str | sempre |
| `cartella` | str | sempre, minuscola come le chiavi di `cartelle` |
| `ogni` | int | sempre, minuti; `0` se assente |
| `attiva` | bool | sempre |
| `ultimo_fetch` | int | epoch da `SourceState.last_fetch`, omesso se la fonte non è mai stata letta |
| `stato` | str | da `SourceState.last_status` (`ok`, `vuota`, `error`, `no_preview`), omesso se assente |

Le `cartelle` devono includere le fonti inattive perché `load_config` risolve `canali: [cartella]` su tutte le fonti (`config.py:136-138`, `156-164`), mentre `Config.cartelle()` (`config.py:61-66`) esclude le inattive. Non usare `Config.cartelle()`.

Voce di `regole`:

| campo | tipo | presenza |
|:--|:--|:--|
| `nome` | str | sempre |
| `slug` | str | sempre, `feeds.slug(nome)` (`feeds.py:20`) |
| `parole`, `escludi` | lista di str | sempre, anche vuote; sono le stringhe scritte in config (`Rule.parole_src`, `Rule.escludi_src`) |
| `canali` | lista di str | sempre, `Rule.canali_src` |
| `tutte`, `solo_coupon` | bool | sempre |
| `prezzo_min`, `prezzo_max` | float | omessi se `None` |
| `sconto_min` | int | omesso se `None` |

Voce di `offerte`, tutti i campi da `Offer` (`store.py:66-83`):

| campo | tipo | origine | presenza |
|:--|:--|:--|:--|
| `id` | int | `o.id` | sempre |
| `t` | int | epoch UTC di `o.posted_at`: `datetime.fromisoformat`, se naive si assume UTC | sempre |
| `n` | str | `item_name(o)` | sempre, mai vuota |
| `x` | str | `o.text` intero, mai troncato | sempre |
| `k` | lista di str | `o.channels`, stesso ordine | sempre |
| `p` | float | `o.price` | omesso se `None`; `0.0` si emette |
| `b` | float | `o.old_price` | omesso se `None` |
| `s` | int | `o.discount`, valore del DB senza correzioni | omesso se `None` |
| `c` | str | `o.coupon` | omesso se `None` o vuoto |
| `u` | str | primo fra `o.link` e `o.permalink` che passa `safe_url` | omesso se nessuno passa |
| `m` | str | `o.permalink` se passa `safe_url` ed è diverso da `u` (come `feeds.py:59`) | altrimenti omesso |
| `i` | str | `o.image` se passa `safe_url` | altrimenti omesso |

`x` deve essere completo perché le regole valutano il testo intero (`rules.py:16-18`) e la parità con le regole dipende da questo. I prezzi non si arrotondano: il JS deve confrontare gli stessi float che vede `rules.matches`. `safe_url(u)` accetta solo `http:` e `https:` e restituisce `None` per `javascript:`, `data:`, `file:`, schema assente o stringa vuota. Nel JS un campo assente si legge sempre come `o.p == null`, mai come falsy, perché `0` è un prezzo valido per `pmin`.

Ordine e limiti: offerte ordinate per `(t, id)` decrescente con ordinamento esplicito in Python (`store.py:194` ordina solo per `posted_at`). Finestra: `since = (now - timedelta(days=p.feed_giorni)).isoformat(timespec="seconds")`, identica a `feeds.py:141`. `now` deve essere timezone-aware UTC: lo è in `run_fetch` (`fetch.py:162`), e il comando `feed` usa `datetime.now(timezone.utc)`. Massimo `p.dashboard_max_offerte` offerte (default 10000); sopra si tengono le più recenti e `troncato` diventa `true`.

### 2.3 Codice Python in `feeds.py`

| intervento | dove |
|:--|:--|
| `import logging` e `log = logging.getLogger(__name__)` | in testa, dopo gli import esistenti (righe 5-15) |
| costanti `STATIC = Path(__file__).parent / "static"`, `DASHBOARD_VERSIONE = 1`, `DASHBOARD_ASSET = ("dashboard.html", "dashboard.css", "filtri.js", "dashboard.js")` | dopo `MIME` (riga 17) |
| `item_name(o) -> str`: `o.title or (o.text.splitlines() or [""])[0][:80]`, ripiego `"(senza titolo)"`; `item_title` (righe 29-35) parte da `item_name(o)` e per il resto non cambia | righe 29-35 |
| `safe_url(u: str \| None) -> str \| None` | dopo `fmt_price` (riga 26) |
| `dashboard_cartelle(config) -> dict[str, list[str]]` | dopo riga 134 |
| `dashboard_regole(config) -> list[dict]` | dopo riga 134 |
| `dashboard_fonti(config, store) -> list[dict]` | dopo riga 134 |
| `dashboard_offerta(o: Offer) -> dict` | dopo riga 134 |
| `dashboard_bytes(offers, cartelle, regole, fonti, now, giorni, max_offerte=10000) -> bytes`, pura e testabile senza disco | dopo riga 134 |
| `write_dashboard(store, config, now) -> int`, restituisce il numero di offerte scritte | dopo riga 134 |
| `_index_html(entries, base_url, now, con_dashboard=False)` aggiunge dopo l'`<h1>` (riga 123) `<p><a href='dashboard.html'>Dashboard</a></p>` se `con_dashboard` | righe 118-134 |
| `write_feeds` passa `con_dashboard=p.dashboard`, poi chiama `write_dashboard` in `try/except` | riga 164 |
| pulizia ristretta a `cartella/*` e `regola/*` (le sole cartelle dei feed), con gli stessi controlli di suffisso | righe 161-163 |

`write_dashboard`:

- Crea `base = p.var_dir / "feeds"` se manca.
- Se `p.dashboard` è falso, elimina i cinque file della dashboard se presenti e restituisce 0.
- Altrimenti legge `store.offers_since(since)`, costruisce i byte, scrive gli asset solo se diversi e poi `dashboard.json`.

Chiamata dentro `write_feeds`, dopo la scrittura di `index.html`:

```python
try:
    write_dashboard(store, config, now)
except Exception:  # la dashboard non deve fermare feed, notifiche e salvataggio dello stato
    log.exception("dashboard: scrittura fallita")
```

Il valore restituito da `write_feeds` e `RunSummary.feeds` (`fetch.py:24-33`) non cambiano. Il punto è unico (`write_feeds`), quindi protegge sia `run_fetch` sia il comando `feed`. Il motivo: nel workflow, se `offerte fetch` fallisce, il passo «Salva lo stato sul branch data» non gira (`offerte.yml:47-50`, nessun `if: always()`) e al giro dopo le stesse offerte vengono rinotificate.

I file in `STATIC` arrivano anche in installazione normale: `[tool.hatch.build.targets.wheel] packages = ["src/offerte"]` include i file non Python del pacchetto, e il `Containerfile` fa `COPY src ./src`. Il controllo sulla wheel è un criterio di accettazione.

### 2.4 Estensione di `Rule`, `Params`, `rules.matches`, CLI

Senza questa estensione «Crea regola» non produce la regola equivalente per sconto e coupon.

`config.py`:

- `Rule` (righe 23-32) guadagna, tutti con default: `sconto_min: int | None = None`, `solo_coupon: bool = False`, `parole_src: tuple[str, ...] = ()`, `escludi_src: tuple[str, ...] = ()`, `canali_src: tuple[str, ...] = ()`. I `Rule(...)` dei test e di `cmd_filtra` restano validi.
- `Params` (righe 35-48) guadagna `dashboard: bool = True`, `dashboard_regole: bool = True`, `dashboard_max_offerte: int = 10000`.
- La chiamata `Params(...)` alle righe 103-116 è costruita campo per campo: i tre campi nuovi vanno passati uno a uno (`bool(raw.get("dashboard", True))`, `bool(raw.get("dashboard_regole", True))`, `int(raw.get("dashboard_max_offerte", 10000))`), altrimenti il valore dello YAML passa `_check_keys` (riga 99) e viene ignorato in silenzio. `dashboard_max_offerte < 1` è `ConfigError`.
- Chiavi ammesse di una regola (riga 144): aggiungere `sconto_min` e `solo_coupon`.
- Righe 146-148, errore se mancano tutti i criteri: `regola 'x': serve almeno una parola chiave o un altro criterio (prezzo_min, prezzo_max, sconto_min, solo_coupon, canali)`. I criteri sono parole, `prezzo_min`, `prezzo_max`, `sconto_min`, `solo_coupon`, `canali`; `escludi` da solo non è un criterio.
- Errore `regola 'x': notify richiede almeno una parola chiave` se `notify: true` e nessuna parola. Evita una raffica di notifiche per una regola che corrisponde a tutto.
- `sconto_min`, se presente, deve essere un intero da 1 a 99: `regola 'x': sconto_min deve essere un intero da 1 a 99`.
- Costruzione `Rule` (righe 165-174): valorizzare `sconto_min`, `solo_coupon`, `parole_src=tuple(parole)`, `escludi_src=tuple(str(p) for p in _as_list(rr.get("escludi")))`, `canali_src` con le voci normalizzate come a riga 158 (`str(voce).strip().lstrip("@").lower()`).

`rules.py:9-19`, corpo di `matches` nell'ordine:

1. canali (invariato).
2. prezzo massimo e minimo (invariati).
3. `sconto_min`: `if rule.sconto_min is not None and (offer.discount is None or offer.discount < rule.sconto_min): return False`.
4. `solo_coupon`: `if rule.solo_coupon and not offer.coupon: return False`.
5. `escludi` (invariato).
6. `if not rule.parole: return True`.
7. parole (invariato).

`cli.py`:

- Riga 15: importare anche `write_feeds`.
- Sottocomando `feed` accanto agli altri `sub.add_parser` (righe 35-68): `help="rigenera feed e dashboard dal database, senza leggere i canali"`.
- `cmd_feed(args, config)` accanto a `cmd_serve` (righe 95-98): apre `Store(config.parametri.var_dir / "offerte.sqlite")`, chiama `write_feeds(store, config, datetime.now(timezone.utc))`, stampa `scritti N feed in <cartella>`, restituisce 0. Aggiungere `"feed": cmd_feed` a `COMMANDS` (righe 216-217).
- `filtra` (righe 60-68 e 193-213): `parole` diventa `nargs="*"`; nuove opzioni `--sconto-min` (int) e `--solo-coupon` (flag); se mancano parole e ogni altro criterio, errore su stderr con codice 2 (stesso testo della config). `Rule` si costruisce con `sconto_min`, `solo_coupon`.

### 2.5 Dimensioni

Misurato il 29.10.2026 su 295 offerte reali: 1.022 byte per offerta in chiaro e 466 in gzip; l'URL dell'immagine (`i`, firmato, incomprimibile) pesa 380 byte per offerta, il 37% del file e circa l'80% del gzip. Proiezione a 14 giorni su 5.300-6.500 offerte: 5,4-6,6 MB in chiaro, 2,5-3,0 MB gzip (Pages comprime i `.json`). Soglie da rispettare in test: `dashboard_bytes` su 6000 offerte demo con URL realistici sotto 1,5 s e sotto 8 MB.

## 3. Interfaccia

### 3.1 Caricamento e struttura

`dashboard.html` carica, nell'`<head>`, `<script defer src="filtri.js">` e poi `<script defer src="dashboard.js">`, più `<link rel="stylesheet" href="dashboard.css">`. Tutti i percorsi sono relativi, senza barra iniziale: la pagina deve funzionare sia su `127.0.0.1:8099/dashboard.html` sia su `https://<utente>.github.io/<repo>/dashboard.html`. Nessuno script o stile inline, nessun attributo `style` né `on*`.

Meta nell'`<head>`:

- `<html lang="it">`.
- `charset`, `viewport` (`width=device-width, initial-scale=1`).
- `color-scheme` con `light dark`.
- `robots` con `noindex`.
- `referrer` con `no-referrer`.
- CSP: `default-src 'none'; script-src 'self'; style-src 'self'; img-src https: http:; connect-src 'self'; base-uri 'none'; form-action 'none'`. Mai `unsafe-inline` né `unsafe-eval`. Il meta CSP è il primo elemento dopo `<meta charset>` e precede ogni `<script>`, `<link>` e `<style>`: il meta protegge solo ciò che viene dopo di sé (provato in Chrome 156).

Verificato con Chrome 156 headless: `script-src 'self'` esegue gli script sia da `http://` sia da `file://`.

Titolo della pagina: `<title>Offerte</title>`. Nessun favicon (evita `data:` nella CSP).

La pagina chiede `dashboard.json` con `fetch("dashboard.json", {cache: "no-cache"})`. Il contenuto statico iniziale di `#stato-dati` è `Carico le offerte... Se non succede nulla, apri la pagina da 127.0.0.1:8099/dashboard.html (offerte serve): da file:// i dati non si caricano.`; il JS lo sostituisce subito. Se `location.protocol === "file:"` il JS non tenta il fetch e mostra lo stato `errore-file`.

### 3.2 Motore `filtri.js`

Solo ECMAScript standard. Vietati nel file: `document`, `window`, `URLSearchParams`, `performance`, `navigator`, `localStorage`, `fetch`, `require`, `module`. Nessun lookbehind come literal regex: le espressioni con lookbehind o `\p{}` si costruiscono solo con `new RegExp(stringa, flag)` dentro `try/catch`, così un browser vecchio non rompe il parsing dello script. Si espone solo `globalThis.Filtri`, avvolto in una IIFE.

Stato (`stato`): oggetto con campi `q` (lista di str), `no` (lista di str), `tutte` (bool), `pmin`, `pmax` (numero finito >= 0 o `null`), `smin` (intero 1-99 o `null`), `cart` (lista di str minuscole), `can` (lista di str), `per` (uno fra `1h 3h 6h 12h 24h 48h 3g 7g` o `null` per tutto il periodo), `cp` (bool), `ord` (uno dei sei ordinamenti, default `data-desc`).

| funzione | firma | comportamento |
|:--|:--|:--|
| `statoDefault()` | `() -> stato` | copia fresca dello stato vuoto |
| `leggiUrl(search, cartelle)` | `(str, obj\|null) -> stato` | parser scritto a mano (niente `URLSearchParams`): ignora chiavi ignote; accetta `+` come spazio; `decodeURIComponent` in `try/catch`; scarta numeri non finiti o negativi, `smin` fuori da 1-99, `per` e `ord` sconosciuti; con `cartelle` scarta cartelle e canali assenti dai dati; se `pmin > pmax` li scambia |
| `scriviUrl(stato)` | `(stato) -> str` | forma canonica, senza `?` iniziale, solo parametri diversi dal default, ordine `q no tutte pmin pmax smin cart can per cp ord`; `q` e `no` ripetuti, una voce per parametro; `cart` e `can` con nomi separati da virgola letterale; valori con `encodeURIComponent`; numeri con `String(n)` |
| `traduciRegex(srcPython)` | `(str) -> {src, avvisi[], tradotta}` | vedi 3.4; non lancia mai |
| `compilaVoce(voce)` | `(str) -> {ok, tipo, re, avvisi[]} \| {ok:false, errore}` | parola intera o regex, vedi 3.4 |
| `compila(stato)` | `(stato) -> {ok, errori[], avvisi[], q[], no[]}` | compila ogni riga di `q` e `no`; `errori` e `avvisi` sono `{campo, riga, messaggio}` con riga da 1; `ok` è falso se c'è almeno un errore |
| `periodoSecondi(per)` | `(str\|null) -> int\|null` | 1h 3600, 3h 10800, 6h 21600, 12h 43200, 24h 86400, 48h 172800, 3g 259200, 7g 604800 |
| `insiemeCanali(stato, cartelle)` | `-> Set\|null` | unione dei canali delle cartelle in `cart` e dei nomi in `can`; `null` se entrambe vuote |
| `applica(offerte, stato, opz)` | `opz = {cartelle, adesso, ora, budgetMs}` -> `{righe, senzaPrezzo, senzaSconto, troppoLento, compilato}` | `adesso` in secondi epoch, `ora()` in ms (default `Date.now`), `budgetMs` default 1500; `righe` già ordinate secondo `stato.ord` |
| `ordina(righe, ord)` | `-> nuovo array` | vedi 3.5 |
| `togliGruppo(stato, gruppo)` | `-> stato` | gruppi `q no tutte prezzo smin cart can per cp`; `prezzo` azzera `pmin` e `pmax` |
| `gruppiAttivi(stato)` | `-> lista di id gruppo` | nell'ordine sopra; `tutte` conta solo con almeno 2 parole |
| `yamlRegola(stato, {nome, notify}, cartelle)` | `-> {yaml, esclusi[]} \| null` | vedi 3.10; `null` se nessun criterio esportabile |
| `nomeSuggerito(stato)` | `-> str` | vedi 3.10 |
| `slug(s)` | `-> str` | identico a `feeds.slug`: `s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+\|-+$/g, "") \|\| "feed"` |
| `statoDaRegola(regola, cartelle)` | `-> stato` | `q = parole`, `no = escludi`, `tutte`, `pmin`, `pmax`, `smin`, `cp = solo_coupon`; per ogni voce di `canali`: se è un nome di canale va in `can`, altrimenti se è una cartella va in `cart` (il canale vince, come `config.py:159-162`), altrimenti si ignora; `per = null`, `ord` di default |
| `regolaUguale(stato, regola, cartelle)` | `-> bool` | vero se `q`, `no`, `tutte`, `pmin`, `pmax`, `smin`, `cp` coincidono, i due `insiemeCanali` sono uguali e `per` è `null` |

### 3.3 Semantica dei filtri

Un'offerta passa se supera tutti i filtri attivi. I controlli economici vanno prima, le regex sul testo per ultime.

| filtro | semantica |
|:--|:--|
| Periodo | se `per` è impostato, `t >= adesso - periodoSecondi(per)`; non si esporta nelle regole |
| Canali | se `insiemeCanali` non è `null`, almeno un elemento di `k` sta nell'insieme; equivale a `Rule.canali` (`rules.py:10-11`) |
| Solo coupon | `c != null` |
| Prezzo | se `pmin` o `pmax` è impostato, serve `p != null` e `p >= pmin`, `p <= pmax` (estremi inclusi, come `rules.py:12-15`); `0` è un valore valido |
| Sconto minimo | se `smin` è impostato, serve `s != null` e `s >= smin` |
| Parole | se `q` ha voci: basta una voce che combacia nel campo `x`, oppure tutte se `tutte` è attivo; senza voci non si applica (come `rules.py:18-19` e `any`/`all`) |
| Escludi | una sola voce di `no` che combacia nel campo `x` esclude l'offerta (come `rules.py:16-17`) |

Il testo cercato è sempre `x`, mai il nome `n`, perché le regole confrontano `offer.text`.

Se `compila(stato).ok` è falso, il filtro testo (`q` e `no` insieme) non si applica, come se fosse vuoto; gli altri filtri restano attivi. Questo comportamento vale anche al caricamento da URL.

Contatori di `applica`, ciascuno calcolato lasciando fuori solo il proprio filtro:

- `senzaPrezzo`: offerte che passano ogni altro filtro ma non hanno `p`, con un filtro di prezzo attivo.
- `senzaSconto`: offerte che passano ogni altro filtro ma non hanno `s`, con `smin` attivo.

Budget: ogni 200 offerte si controlla `ora() - inizio > budgetMs`; se superato si interrompe il ciclo, `troppoLento` diventa `true` e `righe` contiene quanto trovato fino a quel punto.

### 3.4 Parole, regex e traduzione Python verso JavaScript

La campo Parole è una `<textarea>`, una voce per riga: elimina l'ambiguità di `;` dentro una regex. Ogni riga è `trim()`; le righe vuote si scartano.

Compilazione di una voce, speculare a `compile_keyword` (`config.py:69-73`):

- Se la voce è più lunga di 2 caratteri e inizia e finisce per `/`, è una regex Python: si prende `voce.slice(1, -1)` e si passa a `traduciRegex`.
- Ogni altra voce è una parola intera: `new RegExp("(?:^|[^\\p{L}\\p{N}_])" + escape(voce) + "(?![\\p{L}\\p{N}_])", "iu")`. Niente lookbehind (Safari prima di 16.4 non lo supporta); per un test booleano equivale a `(?<!\w)` di Python.
- `escape` protegge solo `^ $ \ . * + ? ( ) [ ] { } | /`. Con il flag `u` un escape superfluo come `\-` è un errore di sintassi.
- Mai il flag `g` (renderebbe `test()` con stato).

`traduciRegex(src)` scorre la stringa carattere per carattere tenendo traccia di classi di caratteri `[...]` e backslash. Fuori da classi traduce `\b` e `\B` in confini Unicode con lookbehind e lookahead su `[\p{L}\p{N}_]`, `\w` in `[\p{L}\p{N}_]`, `\W` nella negazione, `\d` in `\p{Nd}`, `\D` in `\P{Nd}`, `(?P<n>` in `(?<n>`, `(?P=n)` in `\k<n>`, `\A` in `^`, `\Z` in `$`, e toglie il backslash agli escape di punteggiatura che JS con flag `u` rifiuta (qualunque carattere ASCII non alfanumerico fuori da `^$\.*+?()[]{}|/`, con `-` ammesso solo dentro una classe). Toglie un `(?i)` iniziale (il flag `i` c'è sempre); ogni altra flag inline è un errore con messaggio «flag inline non supportata, usa solo (?i) iniziale». Dentro le classi traduce `\w` in `\p{L}\p{N}_` e `\d` in `\p{Nd}`; `\W`, `\D`, `\S` dentro una classe non sono rappresentabili e generano un avviso con ripiego sulla regex non tradotta.

Compilazione di una regex, in ordine:

1. La versione tradotta con flag `iu`.
2. Se lancia (per esempio lookbehind non supportato), la regex grezza con flag `i` e avviso «compilata senza regole Unicode: \b e \w valgono solo per lettere ASCII, il risultato può differire dalla regola».
3. Se anche questa lancia, `{ok:false, errore}` con il messaggio del motore.

Messaggio sotto il campo: `Riga N: espressione non valida (<messaggio del motore>)`, in `role="alert"`; avviso: `Riga N: <testo avviso>`.

Divergenze note da scrivere nel testo di aiuto del campo Parole e in README: le regex sono in sintassi JavaScript tradotta; gruppi possessivi, gruppi atomici, `\W` in classi non funzionano.

### 3.5 Ordinamenti

Menu `#ord`, sei voci, valori `data-desc` (default), `data-asc`, `prezzo-asc`, `prezzo-desc`, `sconto-desc`, `sconto-asc`. Le offerte senza prezzo (per i prezzi) o senza sconto (per gli sconti) vanno sempre in fondo, in entrambe le direzioni. A parità si ordina per `t` decrescente, poi per `id` decrescente. L'ordinamento lavora su una copia dell'array filtrato.

### 3.6 Stato nell'URL

Query string su `dashboard.html`, scritta con `history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""))` a ogni modifica (mai `pushState`, mai l'hash) e letta all'apertura. Si scrivono solo i parametri diversi dal default. I valori entrano nei campi solo con `.value`, mai in `innerHTML`.

| parametro | significato | default omesso |
|:--|:--|:--|
| `q` | una voce di Parole; ripetuto | nessuno |
| `no` | una voce di Escludi; ripetuto | nessuno |
| `tutte` | `1` se servono tutte le parole | assente |
| `pmin`, `pmax` | prezzo minimo e massimo, punto decimale | assenti |
| `smin` | sconto minimo in percentuale, intero 1-99 | assente |
| `cart` | cartelle in minuscolo, separate da virgola | assente |
| `can` | canali separati da virgola; si uniscono alle cartelle | assente |
| `per` | `1h 3h 6h 12h 24h 48h 3g 7g` | tutto il periodo |
| `cp` | `1` se solo con coupon | assente |
| `ord` | `data-desc data-asc prezzo-asc prezzo-desc sconto-desc sconto-asc` | `data-desc` |

Esempio: `dashboard.html?q=apple%20watch&q=%2F%5Cbwatch%5Cs*(se%7Cultra)%5Cb%2F&no=cinturino&no=cover&pmax=250&per=7g&ord=prezzo-asc`. Invariante: `leggiUrl(scriviUrl(s), cartelle)` restituisce `s` per ogni stato valido. Il nome della regola, la casella `notify` e lo stato del dialogo non entrano nell'URL. «Copia link» copia `location.href`. Il campo prezzo accetta la virgola decimale e la converte in punto.

### 3.7 Layout e controlli

Layout telefono (sotto 900 px), una colonna, gutter di 16 px, nessuno scroll orizzontale da 320 px in su (`min-width: 0` sui figli di grid e flex, `overflow-wrap: anywhere` su nomi e coupon):

1. Barra alta: titolo «Offerte», riga `#stato-dati` («aggiornato alle 10:42, 14 min fa, 5.213 offerte in 14 giorni»), pulsante «Ricarica» (`#ricarica`) che rifà il fetch e riapplica i filtri, link «Feed» a `index.html`.
2. Campo `#q` a tutta larghezza.
3. `<details id="filtri">` con summary «Filtri (n)», dove n è il numero di gruppi attivi fra Escludi, Tutte le parole, Prezzo, Sconto minimo, Cartella, Canali, Periodo, Solo coupon.
4. Riga dei preset.
5. Riga dei chip dei filtri attivi.
6. Riga con `#conta` e `#ord`.
7. Righe `#nascoste` e `#suggerimento`.
8. Elenco `#elenco`.
9. Pulsante `#altre`.

Layout desktop (900 px e oltre): due colonne. Colonna sinistra larga 320 px, sticky, che contiene `#q` e il pannello filtri sempre aperto (`details.open` impostato da `matchMedia`, summary nascosto); colonna destra con larghezza massima 56 rem.

Pannello filtri, in ordine:

1. Escludi (`#no`).
2. Casella «Devono comparire tutte le parole» (`#tutte`), visibile solo con almeno 2 parole.
3. Fieldset «Prezzo»: `#pmin` e `#pmax` affiancati (`type="text"`, `inputmode="decimal"`), più quattro pulsanti `fino a 25 €`, `50 €`, `100 €`, `250 €` con `data-pmax`: impostano `pmax`, `aria-pressed` quando coincide, un secondo clic lo toglie.
4. «Sconto minimo (%)» (`#smin`, `type="number"`, `min=1 max=99 step=1`, `inputmode="numeric"`).
5. Fieldset «Cartella» (`#cart`): una casella per cartella con conteggio, es. `informatica (212)`.
6. `<details>` «Canali» con contenitore `#can`: caselle raggruppate in un fieldset per cartella, più un gruppo «altri» per i canali presenti nei dati ma non più in config.
7. Select «Periodo» (`#per`).
8. Casella «Solo con coupon» (`#cp`).
9. Pulsanti «Azzera filtri» (`#azzera`), «Copia link» (`#copia-link`), «Crea regola» (`#regola`).

I conteggi per cartella e canale si calcolano una volta sola sul dataset intero. Le opzioni di `#per`: «Tutto il periodo», «Ultima ora», «Ultime 3 ore», «Ultime 6 ore», «Ultime 12 ore», «Ultime 24 ore», «Ultime 48 ore», «Ultimi 3 giorni», «Ultimi 7 giorni». Le opzioni di `#ord`: «Più recenti», «Meno recenti», «Prezzo crescente», «Prezzo decrescente», «Sconto maggiore», «Sconto minore».

Ogni campo di testo ha `autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false"`: la punteggiatura intelligente di iOS trasformerebbe apici e trattini nelle regex. Font dei campi almeno 16 px (niente zoom di iOS al focus). Applicazione dei filtri: debounce di 200 ms su `#q`, `#no`, `#pmin`, `#pmax`, `#smin`; nessun debounce su menu, caselle e pulsanti.

Id obbligatori nell'HTML (verificati da un test): `q`, `no`, `tutte`, `pmin`, `pmax`, `smin`, `cart`, `can`, `per`, `cp`, `ord`, `conta`, `nascoste`, `suggerimento`, `elenco`, `altre`, `regola`, `azzera`, `copia-link`, `ricarica`, `stato-dati`, `avvisi`, `preset`, `chip-attivi`, `filtri`, `errore-q`, `errore-no`, `toast`, `dialogo`, `nome-regola`, `nome-avviso`, `notify`, `yaml`, `esclusi-regola`, `copia-yaml`, `chiudi-dialogo`.

Nel JS gli id si leggono solo con `document.getElementById("...")`, così il test statico può confrontarli con l'HTML.

### 3.8 Scheda offerta

`article.offerta` costruito con `createElement` e `textContent`, mai `innerHTML`. Contenuto:

- Miniatura 72x72 se c'è `i`, con `loading="lazy" decoding="async" referrerpolicy="no-referrer" alt=""`; se il caricamento fallisce si nasconde (listener `error`, non attributo).
- Titolo `n` come link a `u` (se `u` manca, solo testo).
- Riga prezzo: `p` in formato italiano (`Intl.NumberFormat("it-IT", {style: "currency", currency: "EUR"})`), `b` barrato preceduto dal testo «prima», badge `-38%`, badge `coupon SSD10`.
- Riga meta: tempo relativo e canali. Tempo relativo: «adesso» sotto 60 s, «N min fa», «N h fa», «ieri HH:MM», altrimenti «27 ott 08:15», nel fuso del browser, con la data completa nell'attributo `title`.
- Azioni: «Vai all'offerta» (`u`), «Messaggio» (`m`, se c'è), `<details><summary>Testo</summary><pre>` con `x`.

I link hanno `target="_blank"` e `rel="noopener noreferrer nofollow sponsored"`. `href` e `src` passano da una funzione `urlSicuro` in `dashboard.js` che accetta solo `http:` e `https:` (usa `new URL(u, location.href).protocol`, senza stringhe `http://` nel sorgente). Sulle schede: altezza minima stabile (`min-height`) contro i salti di layout; niente `content-visibility`.

### 3.9 Preset, chip, riepilogo, suggerimento, annulla

Preset (`#preset`), visibile solo se `regole` non è vuoto: un pulsante `aria-pressed` per regola con il suo nome e il conteggio calcolato nel browser con lo stesso motore (dopo il primo rendering, con `setTimeout`), più un link «RSS» a `regola/<slug>.xml` (relativo). Un clic imposta nello stato i filtri di `statoDaRegola` mantenendo `ord` e azzerando `per`; non esiste un parametro `preset` nell'URL. Il pulsante risulta premuto finché `regolaUguale` è vero.

Chip dei filtri attivi (`#chip-attivi`): un pulsante per gruppo attivo, con la × e nome accessibile «Rimuovi filtro: <etichetta>»; clic chiama `togliGruppo`. Etichette: «Parole (2)», «Escludi (3)», «Tutte le parole», «da 20 €», «fino a 250 €», «da 20 a 250 €», «sconto da 30%», «cartella: casa, cina», «canale: mttvideo», «ultime 24 h», «ultimi 3 giorni», «solo coupon».

Riepilogo:

- `#conta`, con `aria-live="polite"`: «132 offerte su 5.213», «1 offerta», «Nessuna offerta».
- `#nascoste`: «12 offerte senza prezzo non mostrate» (singolare «1 offerta senza prezzo non mostrata») e «7 offerte senza sconto non mostrate», solo se i contatori sono maggiori di zero.

Elenco vuoto: «Nessuna offerta corrisponde ai filtri.» con pulsante «Azzera filtri». Se ci sono filtri attivi, `#suggerimento` indica il gruppo la cui rimozione dà più risultati: «Togliendo «sconto da 30%» trovi 31 offerte.» con pulsante «Togli» (si calcola solo quando l'elenco è vuoto).

Azzera: riporta lo stato al default e l'URL a `dashboard.html` senza query. Compare un toast `#toast` (`role="status"`) «Filtri azzerati.» con pulsante «Annulla» per 6 secondi, che ripristina lo stato precedente.

Paginazione: 60 schede per volta, pulsante `#altre` «Mostra altre 60» finché ne restano; ogni cambio di filtro riparte dalle prime 60.

### 3.10 Dialogo «Crea regola» e YAML

`<dialog id="dialogo">` nativo (Esc chiude, il fuoco lo gestisce il browser). «Crea regola» (`#regola`) è disabilitato, con motivo visibile («serve almeno un criterio: parole, prezzo, sconto, coupon o canale»), se `yamlRegola` restituisce `null` o se `compila` ha errori. Contenuto del dialogo:

- Campo `#nome-regola`, precompilato da `nomeSuggerito(stato)`: slug ASCII (NFD senza accenti, minuscolo, `[^a-z0-9]+` in `-`) della prima voce che non sia regex, più `-sotto-<pmax>` se c'è `pmax` (il punto decimale diventa `-`); `regola` se non c'è nessuna voce non regex. Se lo slug coincide con quello di una regola in `regole[]` compare in `#nome-avviso` «nome già in uso, proposto «<nome>-2»» e si propone il suffisso `-2`, `-3`, e così via.
- Casella `#notify`, spenta di default, disabilitata se non ci sono parole («notify richiede almeno una parola»), mai nell'URL.
- `<textarea id="yaml" readonly>` in monospace con lo YAML.
- `#esclusi-regola`: «Non incluso nella regola: periodo.» (solo se `per` è attivo) e «Canali non più in config.yaml: <nomi>.» se serve.
- Istruzione «Incolla sotto regole: in config.yaml.»
- Pulsanti «Copia YAML» (`#copia-yaml`) e «Chiudi» (`#chiudi-dialogo`).

Copia: `navigator.clipboard.writeText` se disponibile; in contesto non sicuro (http su IP di LAN dal telefono) ripiego con `textarea.select()` più `document.execCommand("copy")`, lasciando il testo selezionato. Esito comunicato nel toast: «Copiato.» oppure «Copia non riuscita: il testo è selezionato, copialo a mano.»

`yamlRegola` produce un blocco indentato di 2 spazi, pronto da incollare sotto `regole:` (stile `config.yaml:68-81`), con chiavi nell'ordine `nome`, `parole`, `escludi`, `prezzo_min`, `prezzo_max`, `sconto_min`, `solo_coupon`, `canali`, `tutte`, `notify`. Compaiono solo le chiavi valorizzate, tranne `notify` che c'è sempre.

```yaml
  - nome: apple-watch-sotto-250
    parole: ["apple watch", '/\bwatch\s*(se|series|ultra)\b/']
    escludi: ["cinturino", "cover"]
    prezzo_max: 250
    sconto_min: 30
    solo_coupon: true
    canali: ["informatica"]
    notify: false
```

Regole di quotatura:

- Le voci normali si scrivono fra doppi apici con `JSON.stringify` (valido in YAML e protegge parole come `no`, `on`, `123`).
- Le regex (stessa regola di `config.py:70`: più di 2 caratteri, inizio e fine `/`) si scrivono fra apici singoli con l'apice raddoppiato.
- `nome` si scrive in chiaro se corrisponde a `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` e non è una parola riservata YAML (`y n yes no on off true false null`), altrimenti con `JSON.stringify`.
- Le voci di `canali` si scrivono sempre fra doppi apici.
- `tutte: true` compare solo con almeno 2 parole e casella attiva.
- `prezzo_*` e `sconto_min` si scrivono con `String(n)`.

Canali nello YAML: per ogni cartella scelta si scrive il suo nome in minuscolo, salvo che coincida con il nome di un canale (`config.py:159-162` darebbe la precedenza al canale): in quel caso si elencano i canali della cartella. Si aggiungono poi i canali scelti in `can` non già coperti da una cartella. I canali che non esistono in `cartelle` (non più in config) non entrano e vanno in `esclusi`, perché `load_config` rifiuterebbe una fonte sconosciuta (`config.py:163-164`).

### 3.11 Stati e testi

| stato (`data-stato`) | condizione | testo e comportamento |
|:--|:--|:--|
| `caricamento` | fetch in corso | «Carico le offerte...» in `role="status"` |
| `errore-file` | `location.protocol === "file:"` | «Da file:// i dati non si caricano. Esegui offerte serve e apri 127.0.0.1:8099/dashboard.html.» |
| `errore-rete` | fetch fallito o HTTP non 200 | «Non riesco a caricare dashboard.json (HTTP 404). Esegui offerte fetch oppure offerte feed, poi ricarica.» con il codice reale o «rete non raggiungibile» |
| `errore-json` | JSON non valido | «dashboard.json non è leggibile. Rigeneralo con offerte feed.» |
| `errore-versione` | `v` diverso da quello atteso (1) | «La pagina e i dati non sono allineati. Ricarica la pagina.» con pulsante «Ricarica pagina» |
| `vuoto` | `offerte` è vuota | «Nessuna offerta nei dati. Esegui offerte fetch.» |
| `pronto` | dati caricati | interfaccia attiva |

Bande in `#avvisi` (si sommano allo stato `pronto`):

- Dati vecchi: se `generato` è più vecchio di 90 minuti, fascia gialla «I dati risalgono a più di 90 minuti fa: la raccolta potrebbe essersi fermata.»
- Troncato: se `troncato`, fascia «Mostrate le N offerte più recenti.»

Il pulsante `#ricarica` rifà il fetch con `cache: "no-cache"`, riapplica lo stato corrente e riparte dalle prime 60 schede. Il pulsante di errore ripete il fetch. Nessun aggiornamento automatico.

### 3.12 Tema, accessibilità, compatibilità

- Token di colore su `:root`, tutti esadecimali a sei cifre (servono al test sui contrasti): `--sfondo`, `--superficie`, `--testo`, `--testo-2`, `--bordo`, `--accento`, `--accento-testo`, `--sconto`, `--sconto-testo`, `--avviso`, `--avviso-testo`, `--errore`.
- Variante scura ridefinita sotto `@media (prefers-color-scheme: dark)` con selettore `:root:not([data-theme="light"])` e ripetuta identica sotto `:root[data-theme="dark"]` (serve alle pagine di prova per forzare il tema).
- `color-scheme: light dark`; `body` con sfondo e colore espliciti.
- Font di sistema; nessun font esterno.
- Nessun pulsante di cambio tema: segue il sistema operativo.
- Nessuna animazione.

Accessibilità:

- Ogni campo ha `<label for>` visibile; i gruppi usano `fieldset` e `legend`.
- Solo controlli nativi (`button`, `input`, `select`, `details`, `dialog`), tutti con `type="button"` quando non sono di invio.
- Aree toccabili di almeno 44 px.
- `:focus-visible` ben visibile.
- Contrasto minimo 4,5 a 1 (testo su sfondo, testo secondario su sfondo, `--accento-testo` su `--accento`, `--sconto-testo` su `--sconto`, `--avviso-testo` su `--avviso`) in chiaro e in scuro.
- Nessuna informazione solo a colore: i badge portano testo («-38%», «coupon X»).
- `textarea` con errori: `aria-invalid="true"` e `aria-describedby` verso `#errore-q` o `#errore-no`.
- `role="alert"` sugli errori; `role="status"` su `#stato-dati` e `#toast`.

Compatibilità: Chrome 100 e iOS 15.4. Si possono usare `<dialog>`, flag `u` con `\p{L}`, `Set`, `replaceChildren`. Non si usano `Array.prototype.at`, `structuredClone`, lookbehind come literal regex, `:has()`, `inert`.

### 3.13 Sicurezza della pagina

Testo, link e immagini arrivano da canali Telegram e, con le fonti `comando` e `apify`, da script e servizi esterni: non sono fidati.

- Nessun `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`: tutto con `createElement` e `textContent`.
- `href` e `src` solo `http:` e `https:`, controllati sia in Python (`safe_url`) sia in JS (`urlSicuro`).
- CSP come in 3.1. La CSP non impedisce l'esfiltrazione tramite `img-src https:`: la difesa reale è la costruzione del DOM e il filtro degli schemi.

### 3.14 Hook di prova sull'elemento `<html>`

Aggiornati a ogni rendering, senza effetti sul comportamento:

| attributo | valore |
|:--|:--|
| `data-stato` | uno degli stati della tabella 3.11 |
| `data-n` | numero di risultati |
| `data-primi` | i primi 20 id mostrati, separati da virgola, nell'ordine di visualizzazione |
| `data-errori-regex` | numero di righe non valide in `q` e `no` |
| `data-vecchi` | `1` se la fascia dati vecchi è mostrata |
| `data-troncato` | `1` se la fascia troncato è mostrata |

## 4. Prestazioni e caricamento

- Un solo GET di `dashboard.json` (fetch con `cache: "no-cache"`: richiesta condizionale). Il server locale non comprime, ma `Last-Modified` più `no-cache` (`serve.py:24-26`) fanno rispondere 304 se il file non è cambiato; su Pages la compressione gzip è della CDN. Stima: `JSON.parse` di 4 MB nell'ordine di 30 ms su desktop e poche centinaia di ms su un telefono medio (stime, da misurare).
- Nessun indice. Su 6000 offerte la scansione lineare costa meno che costruirlo. All'avvio, in un solo passaggio, si calcolano i conteggi per cartella e per canale. A ogni modifica si compila il filtro una volta (regex e `Set`), si applicano per primi i controlli economici e per ultime le regex sul testo; con 1-8 regex su testi di circa 330 caratteri sono pochi millisecondi (stima da confermare con una misura).
- Mai tutte le schede nel DOM: 60 per volta, inserite con `DocumentFragment`; immagini con `loading="lazy"`; nessun listener per scheda (delegazione sul contenitore).
- Debounce di 200 ms su testo e numeri.
- Budget di filtraggio 1,5 s con messaggio «Espressione troppo lenta, semplificala.» (una regex patologica non si interrompe a metà di una singola `exec`: il budget limita solo il danno cumulativo).
- Python: `write_dashboard` a ogni giro (10 minuti in locale, 15 su Actions); una query su `offers_since`, un `json.dumps`, stimati sotto i 200 ms. Il tetto di `dashboard_max_offerte` (10000) impedisce file enormi se qualcuno porta `feed_giorni` a 90.
- Dopo il primo `offerte fetch` reale si rimisura `dashboard.json`: se supera 6 MB in chiaro o 1,2 MB compresso, si segnala nel README come limite noto e si valuta la precompressione in `serve.py` in un lavoro separato.

## 5. Criteri di accettazione

| n. | criterio | verifica |
|:--|:--|:--|
| A1 | I 73 test esistenti passano senza modificare le loro asserzioni; tutti i test nuovi passano | `uv run pytest -q` |
| A2 | `dashboard.json` ha esattamente le chiavi `v generato finestra_giorni troncato cartelle regole fonti offerte`; ogni offerta ha solo chiavi ammesse e i tipi del contratto | `test_contratto_offerta`, `test_head_e_tipi` |
| A3 | Il file non contiene mai il valore `null` (ricerca ricorsiva e sul testo) | `test_nessun_null` |
| A4 | Offerte ordinate per `(t, id)` decrescente indipendentemente dall'ordine di lettura dal DB; escluse quelle fuori da `feed_giorni` | `test_ordine_e_finestra` |
| A5 | Con `dashboard_max_offerte = 2` restano le 2 più recenti e `troncato` è `true` | `test_troncamento` |
| A6 | `cartelle` unisce `Informatica` e `informatica` in una chiave minuscola con i canali uniti e ordinati, e include le fonti con `attivo: false` | `test_cartelle_tutte_minuscole` |
| A7 | `regole` contiene le stringhe sorgente e lo slug; con `dashboard_regole: false` è vuota | `test_regole_sorgenti` |
| A8 | `u`, `m`, `i` con schema diverso da http e https vengono omessi; `u` ripiega sul permalink | `test_url_non_sicuri` |
| A9 | `item_name` non solleva con titolo e testo vuoti e restituisce `(senza titolo)`; i titoli dei feed esistenti restano identici | `test_item_name_senza_testo` e i test esistenti di `test_feeds.py` |
| A10 | Dopo `write_feeds` esistono in `var/feeds` i cinque file della dashboard; dopo un secondo giro esistono ancora, mentre un `cartella/vecchia.json` inventato viene rimosso; `index.html` contiene `href='dashboard.html'` | `test_write_feeds_scrive_dashboard` |
| A11 | Con `dashboard: false` i cinque file vengono rimossi e l'indice non ha il link | `test_dashboard_disattivata` |
| A12 | Se `write_dashboard` solleva, `run_fetch` termina, feed e `index.html` sono scritti e l'eccezione è nel log | `test_isolamento_errore` in `tests/test_fetch.py` |
| A13 | `dashboard`, `dashboard_regole`, `dashboard_max_offerte` letti da YAML hanno effetto; una chiave sconosciuta in `parametri` è rifiutata | `test_params_da_yaml` |
| A14 | Gli asset non vengono riscritti se i byte sono uguali (mtime invariato al secondo giro) | `test_asset_non_riscritti` |
| A15 | `offerte -c <cfg> feed` su un DB demo scrive i file e torna 0 | `test_feed_cli` |
| A16 | `dashboard_bytes` su 6000 offerte demo: sotto 1,5 s e sotto 8 MB | `test_prestazioni_6000` |
| A17 | `test_giro_completo` verifica `dashboard.json` con 6 offerte e la presenza dei quattro asset | `tests/test_fetch.py` |
| A18 | `Rule` accetta `sconto_min` (intero 1-99) e `solo_coupon`; `matches` esclude offerte senza sconto o senza coupon quando il criterio è attivo; una regola senza parole ma con un altro criterio è valida; senza alcun criterio, o con `notify: true` e senza parole, `load_config` solleva `ConfigError` | `tests/test_rules.py` |
| A19 | `load_config` conserva `parole_src`, `escludi_src`, `canali_src` come scritti | `tests/test_rules.py` |
| A20 | `offerte filtra --sconto-min 30 --solo-coupon` (senza parole) funziona sulle offerte salvate | `test_filtra_cli` |
| A21 | Il motore dà gli stessi id di `rules.matches` su tutti i casi non `solo_js`, su ogni runner disponibile fra gjs, node, deno, bun | `test_dashboard_js.py::test_parita_con_python` |
| A22 | Lo YAML prodotto passa `load_config` e la regola risultante seleziona le stesse offerte del filtro | `test_dashboard_js.py::test_yaml_andata_e_ritorno` |
| A23 | `statoDaRegola` di ogni regola di un config di prova seleziona le stesse offerte di `rules.matches` per quella regola | `test_dashboard_js.py::test_preset_da_regola` |
| A24 | `/\bcaff[eè]\b/` su «un caffè » è vero in Python e in JS; `/\bwatch\b/` su «watchè» è falso in entrambi | vettori `regex` della fixture |
| A25 | `leggiUrl(scriviUrl(s))` restituisce `s`; valori non validi si scartano senza errore | `test_url_andata_e_ritorno` |
| A26 | `filtri.js` non usa identificatori vietati e non contiene literal regex con lookbehind | `tests/test_dashboard_web.py` |
| A27 | HTML, CSS e JS non hanno U+2014 né U+2013, né stringhe `http://` o `https://`, né percorsi con barra iniziale, né `innerHTML`, `eval`, `new Function`, né script o stili inline, né attributi `style` o `on*`; la CSP c'è, non contiene `unsafe-inline` né `unsafe-eval`, e nel file `dashboard.html` l'offset del meta CSP è minore di quello di ogni `<script` e `<link`; `lang="it"`, `viewport`, `color-scheme`, `robots noindex` presenti | `tests/test_dashboard_web.py` |
| A28 | Ogni id letto da `dashboard.js` esiste in `dashboard.html`, e ogni id obbligatorio di 3.7 c'è | `tests/test_dashboard_web.py` |
| A29 | I token di colore hanno gli stessi nomi in chiaro e nelle due varianti scure, e tutte le coppie elencate in 3.12 hanno contrasto di almeno 4,5 in chiaro e in scuro | `tests/test_dashboard_web.py` |
| A30 | In Chrome headless via HTTP la pagina mostra gli stessi `data-n` e `data-primi` del riferimento Python per almeno 20 URL | `test_dashboard_browser.py::test_url_riferimento` |
| A31 | A 320, 360, 390, 768 e 1280 px (iframe) `scrollWidth <= clientWidth` con i dati caricati | `test_layout_senza_scroll` |
| A32 | Con dati ostili (testo con `<img onerror=...>`, `u` `javascript:alert(1)`, `i` `data:`, scritti a mano nel JSON) il DOM non ha attributi `onerror`, nessun `href` o `src` con schema diverso da http e https, e il testo compare come testo | `test_xss_json_ostile` |
| A33 | Da `file://` la pagina imposta `data-stato="errore-file"` | `test_file_protocol` |
| A34 | La versione è 0.3.0 in `pyproject.toml` e `__init__.py`; `uv lock --check` passa; `git diff` di `pyproject.toml` e `uv.lock` mostra solo la versione | comandi |
| A35 | La wheel contiene `offerte/static/` con i quattro file | `uv build --out-dir <tmp>` e `unzip -l` (se manca la rete per la build, annotarlo nel README) |
| A36 | Verifica manuale su telefono (S5): nessuno scroll orizzontale a 360 px, nessuno zoom al focus, apici e trattini non convertiti, «Copia link» e «Copia YAML» funzionano su http da IP di LAN, il dialogo si chiude con «Chiudi» ed Esc, tema scuro leggibile | checklist in 6.5 |

## 6. Piano di test

### 6.1 Dati demo

`tests/demo_dati.py`, importabile dai test (`from demo_dati import crea_db, scrivi_config`: `tests/` non ha `__init__.py`, pytest aggiunge la cartella a `sys.path`) ed eseguibile a mano con `uv run python tests/demo_dati.py <cartella>`.

- `crea_db(path, n=6000, now=None, seed=7)`: riempie uno `Store` con offerte sintetiche deterministiche (`random.Random(seed)`), relative a `now`.
- Contenuto: 17 canali nelle 4 cartelle del `config.yaml` reale; testi italiani di 150-500 caratteri; 80% con prezzo, 40% con sconto, 8% con coupon, circa 15 offerte su 2 canali (`touch_offer`); alcuni testi con accenti e `c++`; 3 offerte ostili (testo con `<img src=x onerror=alert(1)>`, link `javascript:alert(1)`, immagine `data:text/html,...`).
- Usa `Store.insert_offer` (`store.py:157`), `Store.add_post` (`store.py:144`), `Store.touch_offer` (`store.py:168`).
- `scrivi_config(cartella) -> Path`: scrive un `config.yaml` con quei 17 canali, tre regole (copiate da `config.yaml:68-81`) e `var_dir` nella cartella.
- Eseguito a mano: crea config e DB, applica le regole (`apply_rules`) e chiama `write_feeds`, così la pagina si apre senza fare fetch.

### 6.2 Backend (pytest, nessuna rete, nessun browser)

`tests/test_dashboard.py` contiene i test della colonna «verifica» di A2-A16: contratto con `Store(":memory:")` e 4 offerte (una con due canali via `touch_offer`), cartelle con fonti inattive e maiuscole miste, finestra e troncamento (parametro `max_offerte` di `dashboard_bytes`, o `dashboard_max_offerte` in una config temporanea), pulizia, isolamento (monkeypatch di `offerte.feeds.write_dashboard` che solleva), parametri da YAML, CLI, prestazioni. Il test di isolamento sta in `tests/test_fetch.py` e riusa la fixture `ambiente` (`test_fetch.py:22`); l'asserzione di A17 va dopo la riga 102.

`tests/test_rules.py`: `test_sconto_min`, `test_solo_coupon`, `test_parole_opzionali`, `test_config_conserva_sorgenti`, `test_config_rifiuta_sconto_non_valido` (0, 100, `"x"`), `test_config_regola_senza_criteri`, `test_config_notify_senza_parole`, `test_filtra_cli` (con `main(["-c", cfg, "filtra", "--sconto-min", "30", "--solo-coupon"])` e `capsys`).

### 6.3 Motore JavaScript senza node come dipendenza

`tests/js_runner.py` cerca `gjs`, `node`, `deno`, `bun` con `shutil.which`. Costruisce un solo script temporaneo: sorgente di `filtri.js`, poi `const CASI = <json>;`, poi un harness (stringa costante nel runner) che calcola i risultati di ogni caso e li stampa con `JSON.stringify` tramite `print` se esiste, altrimenti `console.log`. Nessun file letto dal JS, nessun `argv`: identico su tutti i motori. Lo script si lancia con `subprocess` (timeout 60 s) e si legge l'ultima riga di stdout. Lo script intero rivela anche errori di sintassi.

`tests/test_dashboard_js.py` esegue ogni test una volta per ogni motore trovato (`parametrize`); se non ne trova nessuno fa `pytest.skip` con il motivo.

`tests/fixtures/dashboard_casi.json`:

- `adesso` fisso in secondi.
- `fonti`: lista di `{nome, cartella, attivo?}` con cartelle in maiuscole miste, una cartella con lo stesso nome di un canale, un canale inattivo, canali chiamati `on` e `no`. Il test scrive un config temporaneo da qui, lo carica con `load_config` e calcola `cartelle = dashboard_cartelle(config)` da passare al JS.
- `offerte`: circa 40 offerte nel formato del contratto (accenti, `c++`, `football`, «un caffè », «watchè», cifre `Nd` non ASCII, prezzi 0 e assenti, sconti e coupon vari, due canali).
- `casi`: ciascuno con `nome`, `stato` (campi parziali sopra `statoDefault`), `solo_js` (bool) e, per i `solo_js`, `attesi` (id scritti a mano).
- `url`: stati validi per l'andata e ritorno, e `url_invalidi` con `search` e stato atteso.
- `regex`: coppie `{src, testo}`; Python calcola l'atteso con `re.search(src, testo, re.I)` e, dove `re.compile` solleva, ci si aspetta `ok: false` dal JS.

Python è l'oracolo: i casi non `solo_js` non portano esiti attesi. Per ognuno il JS restituisce `{ids, yaml}`; il test scrive un `config.yaml` con le fonti della fixture e lo YAML ricevuto sotto `regole:`, lo carica con `load_config` (compila anche le regex in Python), costruisce gli `Offer` dalla fixture, calcola gli id con `rules.matches` e confronta l'insieme con quello del JS. Dove `yaml` è `null` (nessun criterio) il test verifica che lo stato non abbia criteri e che il JS restituisca tutte le offerte.

Casi non `solo_js` da coprire:

- parole intere con accenti («città», «caffè»);
- `c++`;
- `tb` contro `football`;
- maiuscole;
- regex con `\b`, `\s`, alternanza, `[12]`, `\d` Unicode;
- `(?P<marca>ssd|nvme)` e `(?i)ssd` iniziale;
- `\A` e `\Z`;
- regex accentata `\bcaff[eè]\b` e `\bwatch\b` contro «watchè»;
- escludi;
- tutte contro una sola parola;
- prezzo massimo con e senza prezzo;
- prezzo minimo uguale a 0;
- minimo e massimo insieme;
- sconto minimo;
- solo coupon;
- sconto più coupon;
- canale singolo;
- cartella;
- cartelle multiple;
- cartella più canale (unione);
- cartella con maiuscole in config;
- cartella con nome uguale a un canale;
- canali `on` e `no` (quotatura YAML);
- apici singoli dentro una regex;
- parole con virgola, due punti e `#`;
- parole `no` e `123`;
- criteri solo numerici senza parole;
- stato senza nessun criterio.

Casi `solo_js`: periodo (con `adesso` fisso), i sei ordinamenti con valori mancanti in fondo, contatori `senzaPrezzo` e `senzaSconto`, `troppoLento` (con un `ora()` finto che avanza di oltre 1500 ms), `togliGruppo` e `gruppiAttivi`, andata e ritorno URL e valori non validi, regex non valida (`compila().ok` falso, nessuna eccezione), canale non più in config (finisce in `esclusi`).

Il test `test_preset_da_regola` carica un config di prova con le tre regole di `config.yaml`, passa a JS `statoDaRegola` di ciascuna e confronta gli id con `rules.matches` su tutte le offerte della fixture.

### 6.4 Pagina vera con Chrome headless

`tests/test_dashboard_browser.py`. Il browser si cerca fra `google-chrome`, `chromium`, `chromium-browser` e la variabile `OFFERTE_TEST_BROWSER`; se non c'è, `pytest.skip`. Si lancia sempre con `--headless=new --disable-gpu --no-sandbox --user-data-dir=<cartella temporanea> --virtual-time-budget=8000 --dump-dom <url>` (timeout 60 s): la cartella del profilo è obbligatoriamente temporanea, per non toccare i profili del browser dell'utente. Verificato: `--dump-dom` esegue gli script e stampa il DOM finale.

Fixture di modulo: `demo_dati.crea_db` con 300 offerte, `write_feeds` in una cartella temporanea, `ThreadingHTTPServer(("127.0.0.1", 0), partial(serve.FeedHandler, directory=...))` in un thread, porta letta da `server.server_address`. Il DOM si legge con `selectolax` (già dipendenza) sugli attributi `data-*` di `<html>`.

- `test_url_riferimento`: almeno 20 URL, fra cui parola semplice, regex, escludi, `tutte`, prezzo minimo e massimo, prezzo minimo 0, `smin`, `cp`, cartelle multiple, canale, cartella più canale, `per`, ciascuno dei sei `ord`, regex non valida (atteso: filtro testo ignorato e `data-errori-regex=1`), canale sconosciuto (ignorato), `pmin > pmax` (scambiati), combinazione di più filtri. Il riferimento si calcola in Python: `Rule` costruita con `compile_keyword` e canali risolti dalla mappa cartelle, `rules.matches` per tutto tranne periodo e ordinamento, filtro periodo su `t` e ordinamento con la stessa chiave di 3.5. I casi con `per` usano offerte lontane almeno 30 minuti dai confini del periodo.
- `test_layout_senza_scroll`: il test copia `tests/web/layout.html` nella cartella servita e la apre con Chrome. La pagina contiene 5 iframe di larghezza 320, 360, 390, 768 e 1280 px su `dashboard.html`; dopo il caricamento (poll su `data-stato="pronto"` dell'iframe) scrive in `<pre id="esito">` il JSON `{larghezza: {scrollWidth, clientWidth}}`. Il test chiede `scrollWidth <= clientWidth` per ogni larghezza. Serve l'iframe perché Chrome headless con `--window-size=390` dà `innerWidth` 500, mentre l'iframe riceve davvero il viewport stretto. Con `layout.html?w=360&h=900&tema=dark` mostra un solo iframe e imposta `data-theme` dall'esterno, per fare screenshot (`--screenshot=<png> --window-size=600,950`, che si guardano con lo strumento di lettura delle immagini).
- `test_xss_json_ostile`: scrive a mano nella cartella servita un `dashboard.json` con campi `x`, `n`, `u`, `m`, `i` ostili (bypassa `safe_url` di Python) e verifica A32.
- `test_file_protocol`: apre `file://<cartella>/dashboard.html` e verifica `data-stato="errore-file"`.

### 6.5 Controlli statici e verifica manuale

`tests/test_dashboard_web.py` realizza A26-A29: lettura dei file con `importlib.resources`/`Path(offerte.__file__).parent / "static"`, espressioni regolari e `selectolax`. Per i contrasti legge i token esadecimali dal CSS (blocco `:root`, blocco `@media` scuro e blocco `[data-theme="dark"]`) e calcola il rapporto WCAG. Per il lookbehind: ogni occorrenza di `(?<=` o `(?<!` in `filtri.js` deve stare su una riga con un apice, un doppio apice o un backtick prima dell'occorrenza (cioè dentro una stringa).

Verifica manuale su telefono (S5): `uv run python tests/demo_dati.py /tmp/offerte-demo`, poi `uv run offerte -c /tmp/offerte-demo/config.yaml serve --host <IP LAN>` e apertura da un telefono. Controlli come in A36. Dopo il primo `offerte fetch --senza-notifiche` reale: misurare `ls -l var/feeds/dashboard.json` e `gzip -c var/feeds/dashboard.json | wc -c` e riportare i numeri nel README. Dopo il primo deploy su Pages: `curl -sI -H 'Accept-Encoding: gzip' https://<utente>.github.io/<repo>/dashboard.json` deve dare `content-encoding: gzip`, e la pagina deve aprirsi sotto `/<repo>/`.

## 7. Ordine di lavoro consigliato

Un commit per sprint a test verdi (`uv run pytest -q`), messaggi in inglese, senza trailer di co-autore.

1. S1, motore delle regole (circa 1,5 h). `config.py` (`Rule`, `Params`, chiavi ammesse, validazioni, `*_src`), `rules.py`, `cmd_filtra` con le nuove opzioni, test in `tests/test_rules.py`, `config.yaml` con i tre parametri commentati. Si chiude con A18-A20.
2. S2, dati e backend (circa 2 h). `item_name`, `safe_url`, funzioni dashboard e `write_dashboard` in `feeds.py`, pulizia ristretta, link nell'indice, chiamata protetta, comando `feed`, `tests/demo_dati.py`, `tests/test_dashboard.py`, estensioni di `test_feeds.py` e `test_fetch.py`. I quattro file statici esistono come segnaposto minimi (anche vuoti) per far passare la copia. Si chiude con A2-A17.
3. S3, motore JavaScript (circa 3 h). `filtri.js` completo, `tests/js_runner.py`, `tests/fixtures/dashboard_casi.json`, `tests/test_dashboard_js.py`. Si chiude con A21-A26 (A26 con il controllo del solo `filtri.js`).
4. S4, pagina (circa 4 h). `dashboard.html`, `dashboard.css`, `dashboard.js`: caricamento e stati, controlli, rendering, URL, preset, chip, annulla, dialogo regola; `tests/test_dashboard_web.py`, `tests/web/layout.html`, `tests/test_dashboard_browser.py`. Si chiude con A27-A33.
5. S5, chiusura (circa 1,5 h). README (sezione «Dashboard» dopo «Feed» alle righe 127-141, prima di «Miniflux» a riga 143; riga `offerte feed` nella tabella Comandi, righe 110-125; paragrafo regole alle righe 74-80 con `sconto_min`, `solo_coupon` e parole opzionali; `static/`, `tests/demo_dati.py` nella Struttura dalla riga 295; una frase in «Test», riga 284, sul test con Chrome), versione 0.3.0 e `uv lock`, controllo wheel, verifica manuale su telefono. La sezione del README dichiara: apertura da `offerte serve` su `/dashboard.html` e su Pages, accesso da telefono con `serve --host <IP LAN>`, parametri URL, differenze fra regex Python e JavaScript, comando `offerte feed`, `dashboard: false` e `dashboard_regole: false`, e il fatto che `dashboard.json` espone su Pages l'intero corpus della finestra (testo completo e link affiliati, più dei feed limitati a `feed_max_elementi`) più le parole e le soglie delle regole se `dashboard_regole` è vero. Si chiude con A34-A36 e `git status` pulito.

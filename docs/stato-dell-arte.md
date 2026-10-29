# Stato dell'arte di offerte

Data: 28 ottobre 2026, sera. Repository `~/Projects/repos/offerte`, branch `main`, versione 0.2.0, sei commit, 73 test verdi (`uv run pytest -q`, 0,13 s). Questo documento è il punto di partenza per lo sprint della dashboard: dice cosa c'è, cosa è stato verificato davvero e cosa è risultato difettoso dopo una lettura indipendente del codice con verifica a tre voti per ogni problema.

## 1. Cosa c'è

Un servizio Python 3.12 (uv) che legge fonti pubbliche, estrae offerte, le deduplica, applica regole di alert e pubblica feed statici.

| modulo | ruolo |
|:--|:--|
| `sources/` | contratto `Source`/`FetchContext`/`FetchResult`, registro dei tipi (incorporati, entry point `offerte.fonti`, `modulo:Classe`); tipi `telegram`, `rss`, `html`, `comando`, `apify` |
| `parser.py` | HTML di `t.me/s` in `Message`; `fragment()` per descrizioni HTML |
| `http.py` | client httpx con cortesia globale, backoff 2, 4, 8, 16 s su 429 e 5xx, risoluzione redirect |
| `fetch.py` | un giro: fonti, `process_message` (link, dedupe, estrazione), regole, notifiche, ritenzione, feed |
| `extract.py` | prezzo, barrato, sconto, coupon, nome prodotto da testo |
| `links.py`, `dedupe.py` | scelta del link, pulizia tracciamento, chiave di dedupe (URL/ASIN o hash del testo) |
| `rules.py`, `config.py` | regole (`parole`, `escludi`, `tutte`, `prezzo_min`, `prezzo_max`, `canali`, `notify`), caricamento e validazione di `config.yaml` |
| `store.py` | SQLite (channels, offers, posts, matches, notifications, redirects), ritenzione |
| `feeds.py`, `serve.py`, `notify.py`, `log.py` | RSS 2.0 e JSON Feed per cartella e regola, `index.html`, server stdlib, bot Telegram, log con rotazione |
| `cli.py` | `fetch`, `serve`, `search`, `stats`, `filtra`, `fonti`, `prova`, `pulisci` |
| `deploy/`, `.github/workflows/offerte.yml`, `systemd/`, `Containerfile` | stato su branch orfano `data`, cron GitHub Actions ogni 15 minuti con Pages, timer utente, container |

Configurazione attuale: 17 canali Telegram verificati il 28.10.2026 in quattro cartelle (`informatica` 10, `casa` 3, `cina` 1, `raffica` 3) e tre regole (`ssd-sotto-60`, `apple-watch-sotto-250`, `errori-di-prezzo`). Giro reale sul codice committato: 17 fonti su 17 lette in 1 minuto e 29 secondi, 333 post, 295 offerte dopo il dedupe, 212 link Amazon risolti e ripuliti, 15 offerte senza prezzo.

Documenti di lavoro in `docs/`, non ancora tracciati da git al momento della scrittura (entrano nel commit di S0): `specifica-dashboard.md` (specifica completa della dashboard, vincitrice di un pannello a tre progetti e tre giudici, rivista dopo una revisione avversaria a quattro lenti), `spunti-ricerche-precedenti.md` (estratto dalle ricerche in `~/Downloads/ricerche`), `spunti-open-source.md` (librerie e progetti verificati), `prompt-opus.md` (il prompt di lavoro per gli sprint rimanenti). Ricerche di origine: `~/Downloads/ricerche/Scraping_Provider_Research_20261028` e `Canali_Telegram_Offerte_20261028`.

## 2. Verificato oggi

- I 73 test passano; la distribuzione è sbilanciata: 23 su `extract`, 13 su `sources`, 11 su `rules`, 7 su `parser`, 7 su `links`, 4 su `dedupe`, 4 su `http`, 2 su `feeds`, 1 su `fetch`, 1 su `store`; nessun test su `cli.py` (233 righe), `deploy/stato.sh`, `systemd/installa.sh`.
- `offerte prova mttvideo` e `offerte prova rafficaffari` leggono 20 e 19 elementi reali, ma la stampa è fuorviante: mostra `m.price` (sempre vuoto per Telegram, perché il prezzo si estrae dopo) e `m.links[0]` (per MoreThanTech è la foto su i.ibb.co, non il link dell'offerta). `extract()` e `pick_offer_link()` sul medesimo materiale danno prezzo e link giusti su 39 elementi su 39: il difetto è solo nel comando.
- Il branch locale si chiamava `master`, mentre il workflow GitHub scatta su `main` e i cron girano solo sul branch predefinito: rinominato in `main` il 28.10.2026, nessun remoto ancora configurato.
- Le notifiche sono disattivate in locale (nessun `.env`), come previsto.
- Dalle letture sono emersi e sono stati confutati sei presunti problemi, fra cui: il token Apify nel log (il campo `token` è il nome di una variabile, non il valore), il server senza CORS (non serve: la dashboard è servita dalla stessa origine), lo stato SQLite oltre i limiti di GitHub (resta sotto i 100 MB con la ritenzione a 90 giorni).

## 3. Problemi confermati

Sessantasette segnalazioni sono sopravvissute alla verifica avversaria (tre scettici indipendenti ciascuna, scartata se almeno due la confutavano). La severità indicata è quella rivista dai verificatori. I numeri di riga valgono al commit `16e8709`. Le correzioni suggerite sono proposte dei lettori: `docs/prompt-opus.md` decide quali entrano nello sprint S0 e come; dove i due testi divergono vale il prompt.

**1. HTML: link non univoco ('#' o pagina stessa) fa collassare tutti gli elementi su un solo id** (fonti, alta).

[verificato eseguendo] Se il primo `a[href]` dell'elemento (o il campo `link: a@href`) e' `#`, urljoin lo trasforma nell'URL della pagina; quel valore diventa `link`, `id` e `permalink` di tutti gli elementi. In run_fetch il secondo elemento trova post_exists(fonte, id) e viene saltato, e ai giri successivi sono saltati tutti: dei 50 elementi ne resta al massimo uno, in silenzio. Eseguito con due `div.deal` con `<a href="#">wishlist</a>`: stesso id `https://shop.example.com/offerte` per entrambi. Inoltre la scelta del primo anchor in assoluto (riga 60) prende pulsanti non di prodotto.

Evidenza: html.py:58-62 "link = get(\"link\") ... a = node.css_first(\"a[href]\") ... link = urljoin(self.url, link) if link else None"; html.py:68 links = ... urljoin(self.url, a.attributes["href"]); html.py:70 "id=get(\"id\") or link or text_key(testo)"; fetch.py:123 "if store.post_exists(fonte.nome, m.id):"

Correzione suggerita:

In html.py aggiungere:

    def _assoluto(base: str, href: str | None) -> str | None:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return None
        url = urljoin(base, href)
        return None if url.split("#")[0].rstrip("/") == base.split("#")[0].rstrip("/") else url

e usarlo ovunque oggi c'e' urljoin: `link = _assoluto(self.url, link)`; se `link` e' None cercare il primo anchor valido con `next((u for a in node.css("a[href]") if (u := _assoluto(self.url, a.attributes.get("href")))), None)`; `links = [u for a in node.css("a[href]") if (u := _assoluto(self.url, a.attributes.get("href")))]` con `link` in testa.

**2. Due importi distinti = prezzo minore e barrato maggiore: coupon, spedizione e cashback diventano il prezzo** (pipeline, media).

[Eseguito] extract() su 'SSD Samsung 980 1TB 79,99€\nCoupon 10€ in pagina' restituisce price 10.0, old_price 79.99, discount 87. 'Cuffie Sony WH-1000XM5 289€\nSpedizione 4,99€' da 4.99 / 289 / 98%. 'Echo Dot 29,99€\nCashback 5€ con PayPal' da 5.0 / 29.99 / 83%. Con run_fetch, la regola ssd-sotto-60 (prezzo_max 60, notify) scatta e invia la notifica per un SSD da 79,99 euro. La regola dei due importi non verifica che stiano sulla stessa riga ne' che il secondo non sia un coupon, una spedizione o un prezzo al kg. Effetti: feed con prezzo e sconto falsi, falsi positivi sui filtri prezzo (rules.py:12), notifiche sbagliate.

Evidenza: src/offerte/extract.py:74-75 `if old_price is None and len(set(current)) == 2: price, old_price = min(current), max(current)`; consumo in rules.py:12 e fetch.py:149-155

Correzione suggerita:

Escludere dagli importi gli elementi marcati come rumore e applicare min/max solo se i due importi stanno sulla stessa riga. Sostituzione in extract_prices (prototipo provato in scratchpad su 12 testi, non applicato): `NOISE_BEFORE = re.compile(r"\b(?:coupon|codice|spedizione|cashback|rimborso|buono|voucher|extra|risparmi\w*|sconto(?:\s+di)?)\s*:?\s*(?:di\s+|da\s+)?$", re.I)`; `NOISE_AFTER = re.compile(r"^\s*(?:/\s*\w+|al\s+(?:kg|pezzo|litro)|di\s+(?:sconto|spedizione|coupon|cashback)|cad\b)", re.I)`; nel ciclo `if NOISE_BEFORE.search(window) or NOISE_AFTER.match(text[m.end():m.end()+25]): continue`; tracciare la riga di ogni importo e far scattare il caso a due importi solo se `len({riga for _, riga in current}) == 1`. Con il prototipo i tre esempi danno (79.99, None), (289.0, None), (29.99, None) e i casi del test esistente restano invariati.

**3. Notifiche al piu' una volta, senza recupero: errore di invio o giro interrotto le perdono per sempre** (pipeline, media).

[Eseguito] 1) Telegram risponde 429 al primo giro: notified 0, is_notified False; al secondo giro, con Telegram di nuovo ok, notified resta 0 e le chiamate totali restano 1. Motivo: l'offerta non e' piu' in `fresh` (solo offerte create in questo giro) e i match sono gia' registrati, quindi `unmatched_offers` non la riporta. `Notifier.send` non legge `parameters.retry_after` ne' ritenta. 2) [Eseguito] Giro interrotto (KeyboardInterrupt alla seconda fonte, equivalente a SIGTERM o al TimeoutStartSec=15min): la prima fonte ha gia' scritto l'offerta e il suo last_id (update_channel fa commit per fonte), ma regole e notifiche stanno alla fine; al giro successivo il match scatta ma notified 0 e nessuna chiamata a Telegram. 3) [Dedotto dal codice] process_message committa insert_offer e add_post separatamente (store.py:165 e 147): un crash fra i due fa trattare il ripasso come duplicato (created False), quindi mai notificato, e gonfia n_posts. Il README dice 'notificata una volta sola' (README.md:259) ma il comportamento reale e' 'al piu' una volta'.

Evidenza: src/offerte/fetch.py:145 `fresh = set(s.new_offers)` e :149 `if offer_id not in fresh or ...`; :154-155 `if notifier.send(...): store.mark_notified(...)`; src/offerte/notify.py:78-84 `if resp.status_code != 200: ... return False`; src/offerte/store.py:134 e :137 commit di last_id per fonte

Correzione suggerita:

Rendere la consegna idempotente guidata dal DB invece che dal giro. In store.py aggiungere `def pending_notifications(self, since): return self.db.execute("SELECT o.*, group_concat(m.rule, char(31)) AS rules FROM offers o JOIN matches m ON m.offer_id = o.id LEFT JOIN notifications n ON n.offer_id = o.id WHERE n.offer_id IS NULL AND o.posted_at >= ? GROUP BY o.id ORDER BY o.posted_at", (since,)).fetchall()`; in run_fetch sostituire il ciclo su `new_matches` con questo elenco filtrato sulle regole `notify` presenti in config, e togliere la condizione `offer_id not in fresh`. Cosi' un invio fallito si ritenta al giro dopo finche' posted_at supera notifica_max_ore, e un giro interrotto non perde nulla. In Notifier.send, su 429 leggere `resp.json().get('parameters', {}).get('retry_after')`, dormire e ritentare una volta.

**4. Nessun JSON aggregato né manifest: dove inserirlo e cosa deve contenere** (dati e feed, media).

[LETTO] Le uniche uscite JSON sono i JSON Feed per cartella e per regola (feeds.py:157-160). L'elenco dei feed disponibili, delle cartelle e delle regole esiste solo come HTML (feeds.py:118-134), quindi una dashboard statica non può scoprirli senza parsare HTML o hardcodarli. Un'offerta in più cartelle compare duplicata in più feed e va deduplicata per id. [DEDOTTO] Il punto di innesto è fetch.py:162, perché lì store, config e now_dt sono già in mano e write_feeds ha appena restituito s.feeds (n offerte per feed); write_feeds è chiamata solo da lì (grep).

Evidenza: feeds.py:118-134, 157-165; fetch.py:162; offerte.yml:57

Correzione suggerita:

1) Nuovo modulo src/offerte/dashboard.py con build_dashboard(store, config, now, feeds_scritti) -> dict e write_dashboard(...) che usa feeds._atomic_write e feeds.slug. 2) Chiamarlo in fetch.py subito dopo la riga 162. 3) Scrivere var/feeds/dashboard.json alla radice (non soggetto alla pulizia 161-163) e var/feeds/dashboard.html statica con URL relativi (funziona in locale e sotto il sottopercorso di Pages; feed_base_url è assoluto, feeds.py:130). Eventuale divisione in dashboard.json (metadati, pochi KB) e offerte.json (array) se la dimensione pesa. 4) Schema proposto: {versione:1, generato:ISO UTC, finestra:{giorni, da, a}, parametri:{feed_giorni, giorni_ritenzione, giorni_dedupe, notifica_max_ore}, totali:{store.counts() + offerte e post in finestra}, cartelle:[{nome, slug, fonti[], n_offerte, feed_xml, feed_json}], fonti:[{nome, tipo, cartella, ogni, attivo, last_fetch, last_status, last_error (ripulito), last_id, n_post_finestra, n_offerte_finestra}], regole:[{nome, slug, parole[], escludi[], tutte, prezzo_min, prezzo_max, canali[], notify, n_match_finestra, ultimo_match, feed_xml, feed_json}], post_per_giorno:[{giorno, fonte, n}], offerte:[{id, titolo, testo, link, permalink, immagine, prezzo, prezzo_barrato, sconto, coupon, posted_at, first_seen, last_seen, canali[], cartelle[], regole[], n_post, notificata}]}. Record base da dataclasses.asdict(offer) su store.offers_since(since). 5) Aggiungere il link alla dashboard in _index_html senza sostituire index.html (test_fetch.py:102 ne verifica l'esistenza).

**5. I feed esistenti coprono una frazione della finestra** (dati e feed, media).

[LETTO] offers_for_channels e offers_for_rule ordinano per posted_at DESC e applicano LIMIT feed_max_elementi (200 in config.yaml:10). [DEDOTTO dai volumi indicativi nei commenti di config.yaml:18-37] informatica pubblica circa 129 post al giorno, raffica circa 280, totale circa 430 al giorno: 200 elementi coprono circa 1,5 giorni di informatica e meno di un giorno di raffica, contro 14 giorni di finestra. Il contatore mostrato in index.html è len(offers) già troncato, quindi non è il numero di offerte della finestra.

Evidenza: store.py:182-184, 187-190; feeds.py:155, 158, 160; config.yaml:10, 18-37

Correzione suggerita:

Per la dashboard non leggere i feed: usare store.offers_since(since) (store.py:193-195, senza limite) con since = iso(now - feed_giorni) come in feeds.py:141. Stima [DEDOTTA, non misurata]: un record compatto di esempio pesa 732 byte contro 1511 di un item JSON Feed (misurato su un'offerta sintetica), quindi 4000-6000 offerte in 14 giorni sono circa 3-4,5 MB grezzi e meno di 1 MB compressi da Pages; il server locale non comprime. Se serve ridurre, accorciare il testo a 300 caratteri o dividere il file.

**6. Campi mancanti nei JSON esistenti per una dashboard** (dati e feed, media).

[LETTO] L'item JSON Feed non porta: title grezzo (solo il titolo composto con prezzo e sconto), key, first_seen, last_seen, n_posts, link distinto dal permalink (url = link oppure permalink, quindi con link assente url e messaggio coincidono), cartelle, regole scattate, flag notificata. Non c'è nemmeno un timestamp di generazione nel JSON, quindi la dashboard non sa quanto sono freschi i dati.

Evidenza: feeds.py:91-103, 107-108 contro store.py:66-83

Correzione suggerita:

Nel record della dashboard esporre titolo già risolto (o.title o prima riga di testo[:80], come feeds.py:30), testo, link, permalink, immagine, prezzo, prezzo_barrato, sconto, coupon, posted_at, first_seen, last_seen, canali, n_post, più cartelle (da canale a config.fonti[].cartella, con 'senza cartella' per canali non più in config), regole (da matches) e notificata (da notifications). Il campo generato in ISO UTC va al top level.

**7. Telegram: messaggi persi senza avviso quando il vuoto supera `pagine`** (fonti, media).

[letto + verificato eseguendo] Nei giri incrementali il ciclo si ferma anche dopo `max_pages` pagine (default 3, circa 60 messaggi), non solo quando incontra un id noto. Se fra due giri il canale ha pubblicato piu' messaggi di quelli letti, i messaggi fra last_id e la pagina piu' vecchia letta non vengono mai richiesti, e last_id salta a max_seen. Simulazione: last_id=100, canale a 200, 20 per pagina: 60 nuovi letti (141..200), persi 101..140, nessun log. Con i canali `raffica` del config (circa 100 messaggi al giorno) basta una macchina spenta per una notte lunga o un weekend (il timer systemd ha Persistent=true, quindi parte una sola volta al riavvio). Il README dice 'finche' si incontra un id gia' noto'.

Evidenza: telegram.py:27 "for _ in range(max_pages):"; telegram.py:40 "if min_id <= last_id or (before is not None and min_id >= before):"; telegram.py:56 "max_pages=int(self.opzione(\"pagine\") or ctx.pages)"; fetch.py:134 update_channel(... last_id=result.last_id ...); README.md:265-266

Correzione suggerita:

In telegram.py aggiungere `import logging` e `log = logging.getLogger(__name__)`; in fetch_channel_messages dare piu' margine ai giri incrementali e avvisare se il ciclo finisce per esaurimento:

    max_pages = max(max_pages, 10) if last_id else max_pages
    for _ in range(max_pages):
        ...
    else:  # nessun break: pagine finite prima di incontrare un id noto
        if last_id and before is not None and before > last_id + 1:
            log.warning("canale %s: mancano i messaggi fra %d e %d (alza 'pagine')", channel, last_id + 1, before - 1)

**8. Notifiche a raffica per elementi senza data valida: il filtro notifica_max_ore non vale** (fonti, media).

[verificato eseguendo] Quando una fonte non da' una data interpretabile, il messaggio prende `date=now`, quindi posted_at e' 'adesso' e la guardia `offer.posted_at < min_posted` non scatta. Prova: fonte `comando` con 5 record con `data: '27/10/2026'` (formato italiano non riconosciuto da parse_date), regola `notify: true`, giro eseguito il 01/11: 5 notifiche inviate al primo giro invece di 0. Succede per html senza campo `data`, per comando/apify senza data e per ogni dataset Apify `ultimo` al primo avvio (fino a 200 elementi). Il commento di config.yaml:12 promette 'evita raffiche al primo avvio'.

Evidenza: base.py:135 "date=parse_date(_pick(d, \"data\")) or now"; html.py:70 "date=parse_date(get(\"data\")) or now"; rss.py:76 "date=parse_date(r[\"date\"]) or now"; fetch.py:146 "min_posted = iso(now_dt - timedelta(hours=p.notifica_max_ore))"; fetch.py:152 "if offer.posted_at < min_posted:"; config.yaml:12

Correzione suggerita:

In fetch.py nel ciclo dei messaggi, non considerare 'fresca' un'offerta di una fonte al primo giro la cui data e' il ripiego `now`:

    sconosciuta = m.date == now_dt
    ...
    if created:
        nuove += 1
        if not (sconosciuta and not state.bootstrapped):
            s.new_offers.append(offer_id)

Piu' parse_date esteso (vedi il rilievo sulle conversioni).

**9. Fonti morte che risultano 'ok': zero elementi non e' mai un segnale** (fonti, media).

[verificato eseguendo] Un feed che diventa una pagina HTML, un RSS 1.0 (rdf:RDF con item in namespace), un selettore HTML che non trova piu' nulla, un comando che stampa vuoto restituiscono lista vuota e run_fetch scrive status 'ok': `offerte fonti` mostra 'ok' mentre la fonte e' morta. Eseguito: parse_feed(b'<html><body>ciao</body></html>') -> []; RSS 1.0 -> []; Atom senza namespace -> []. Per l'HTML un cambio di layout del sito e' il caso piu' probabile e non lascia traccia.

Evidenza: rss.py:66 "raw = _atom_entries(root) if root.tag.endswith(\"feed\") else _rss_items(root)"; rss.py:28 "for item in root.iter(\"item\"):"; html.py:50 "for node in tree.css(self.elemento)[: ...]"; comando.py:17-19 "if not testo: return []"; fetch.py:134 status="ok"

Correzione suggerita:

rss.py dopo il parse:

    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in {"rss", "feed", "rdf"}:
        raise FetchError(f"non e' un feed: radice <{tag}>")

e in _rss_items iterare anche `root.iter("{http://purl.org/rss/1.0/}item")`. In html.py fetch: `nodi = tree.css(self.elemento)`; se vuoto `ctx.log.warning("fonte %s: il selettore '%s' non trova elementi", self.nome, self.elemento)` (ctx.log esiste e oggi non e' usato).

**10. parse_date e to_number: eccezioni che abbattono la fonte, numeri come stringa non riconosciuti, nan/inf accettati** (fonti, media).

[verificato eseguendo] parse_date: un timestamp numerico enorme o NaN solleva OSError/OverflowError/ValueError (1e20, 10**30, nan) e, poiche' la conversione e' dentro la list comprehension, abbatte l'intera fonte per un solo record. Un timestamp in stringa ('1793095200', '1793095200000') da' None mentre lo stesso valore intero e' accettato; 'dd/mm/yyyy' da' None (poi data=now, vedi rilievo sulle notifiche); un orario senza fuso e' trattato come UTC. to_number: 'nan' e 'inf' diventano float, '1.299' (senza simbolo e senza virgola) diventa 1.299 invece di 1299, '1_000' e '1e3' passano. True e' accettato come 1.0.

Evidenza: base.py:71-72 "if isinstance(value, (int, float)): return datetime.fromtimestamp(float(value) / (1000 if value > 1e11 else 1), tz=timezone.utc)"; base.py:73-82 (solo parsedate_to_datetime e fromisoformat); base.py:96 "return float(s.replace(\".\", \"\").replace(\",\", \".\")) if \",\" in s else float(s)"

Correzione suggerita:

base.py parse_date, sostituire il ramo numerico:

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        try:
            n = float(value)
            return datetime.fromtimestamp(n / (1000 if n > 1e11 else 1), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

e prima del fallback ISO provare `datetime.strptime(s, f)` per f in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y"). to_number: `import math`, e per float/int e stringhe `x = ...; return x if math.isfinite(x) else None`; prima del fallback, `if re.fullmatch(r"\d{1,3}(\.\d{3})+", s.strip()): return float(s.replace(".", ""))`.

**11. Backoff senza budget complessivo e con tentativi inutili su errori non transitori** (fonti, media).

[verificato eseguendo] (1) Retry-After in forma data HTTP e' ignorato (resta 2 s, 4 s) e un Retry-After numerico e' tagliato a 120 s: con 'Retry-After: 3600' il client dorme 4 x 120 = 480 s per un solo URL e poi fallisce. Non c'e' un tetto al tempo totale di un giro: con qualche canale t.me in 429 persistente si supera TimeoutStartSec=15min (unit systemd e README) e il giro viene ucciso a meta'. (2) Il ramo `except httpx.HTTPError` ritenta anche errori che non passeranno mai: UnsupportedProtocol (URL senza schema, ftp://) e TooManyRedirects; eseguito con trasporto reale: 4 attese 2+4+8+16 = 30 s prima di FetchError. L'URL senza schema in `rss`/`html` non e' controllato in configura.

Evidenza: http.py:67 "except httpx.HTTPError as e:"; http.py:75-77 "retry_after = resp.headers.get(\"Retry-After\", \"\") if retry_after.isdigit(): delay = max(delay, float(retry_after))"; http.py:80 "self._sleep(min(delay, 120.0))"; systemd/offerte-fetch.service:10 "TimeoutStartSec=15min"; README.md:182

Correzione suggerita:

http.py: errori non ritentabili prima del ramo generico e budget di attesa per chiamata:

    NON_RITENTABILI = (httpx.UnsupportedProtocol, httpx.TooManyRedirects, httpx.DecodingError)
    ...
    except NON_RITENTABILI as e:
        raise FetchError(f"{url}: {type(e).__name__}") from None
    except httpx.HTTPError as e:
        ...

e in get(): `speso = 0.0` all'inizio; prima di dormire `if speso + min(delay, 120.0) > 90: break`; dopo `speso += min(delay, 120.0)`. Per la data HTTP: `email.utils.parsedate_to_datetime(retry_after)` e differenza con datetime.now(timezone.utc).

**12. Il tetto `pagine_storico` vale a ogni giro: dopo una pausa lunga i messaggi piu' vecchi si perdono e last_id salta** (pipeline, media).

[Eseguito] fetch_channel_messages con last_id=100, 200 messaggi nuovi (101..300), max_pages=3: legge 60 messaggi (241..300), perde 101..240 e torna max_seen=300, che diventa il nuovo last_id; i messaggi persi non vengono piu' riletti. Il tetto viene da `pages or p.pagine_storico` ad ogni giro, non solo al primo avvio. Con i volumi dichiarati in config (rafficaffari ~80/g, tecnofferte e codiciscontotech ~100/g) 60 messaggi sono circa 14 ore di buco: un fine settimana a macchina spenta o un cron GitHub fermo basta. Nessun log segnala il buco.

Evidenza: src/offerte/sources/telegram.py:27 `for _ in range(max_pages):` e :56 `max_pages=int(self.opzione("pagine") or ctx.pages)`; src/offerte/fetch.py:102 `pages=pages or p.pagine_storico`; config.yaml:35-37

Correzione suggerita:

In TelegramSource.fetch: `max_pages = int(self.opzione("pagine") or (ctx.pages if ctx.state.last_id == 0 else max(ctx.pages, 30)))`. In fetch_channel_messages, dopo il ciclo: `if last_id and out and min(m.id for m in out) > last_id + 1: log.warning('canale %s: possibile buco, letti solo gli id %d..%d', channel, min_out, max_seen)` (usare l'id minimo letto, non solo dei messaggi con testo).

**13. Un link malformato scarta il messaggio e il messaggio non viene piu' riletto (tel:, mailto:, porta non valida)** (pipeline, media).

[Eseguito] `pick_offer_link(['tel:+390212345'])` torna 'https://tel:+390212345' e `clean_url` su quel valore solleva ValueError (porta non numerica); lo stesso per 'https://example.com:abc/x'. 'mailto:info@shop.it' diventa 'https://mailto:info@shop.it', accettato come link offerta con host shop.it. In run_fetch un giro con due messaggi (id 10 con link tel:, id 11 normale) produce new_posts 1, post 10 non registrato e last_id 11: il messaggio 10 e' perso per sempre perche' fetch.py:134 avanza last_id comunque. La causa e' `normalize_input` che antepone https:// a qualunque stringa senza '://'.

Evidenza: src/offerte/links.py:51-52 `if "://" not in url: url = "https://" + url`; :117 `parts.port in (None, 80, 443)`; src/offerte/fetch.py:127-129 `except Exception: log.exception(...); continue` e :134

Correzione suggerita:

In links.py: `if "://" not in url and not re.match(r"(?i)^(?:mailto|tel|sms|javascript|data|geo|tg|whatsapp):", url): url = "https://" + url`; in pick_offer_link aggiungere un controllo `_valid(url)` che richiede scheme http/https e `urlsplit(url).port` senza ValueError (try/except). In process_message avvolgere la riga del link: `try: link = L.clean_url(resolve_link(store, client, raw_link, now)) if raw_link else None\nexcept ValueError: link = None` cosi' il messaggio ricade sulla chiave testuale invece di sparire.

**14. html.unescape su href gia' decodificati corrompe i parametri che iniziano come un'entita' senza punto e virgola** (pipeline, media).

[Eseguito end to end] Un `<a href="...?id=1&amp;currency=EUR&amp;section=a&amp;region=it">` esce dal parser come '...id=1&currency=EUR&section=a&region=it', `pick_offer_link` lo trasforma in '...id=1¤cy=EUR§ion=a®ion=it' e `clean_url` lo salva come '...id=1%C2%A4cy%3DEUR%C2%A7ion%3Da%C2%AEion%3Dit'. Python html.unescape decodifica le entita' legacy anche senza ';' (curren, sect, reg, not, times, copy, para, deg, uml...). Il link mostrato all'utente perde `currency`, `section`, `region`, `notify`, `times` e simili. La doppia decodifica serve davvero (test_parser.py:63-64 documenta '&amp;quantity=1' nei post reali), quindi il fix deve restringerla.

Evidenza: src/offerte/links.py:50 `url = html.unescape(url.strip())`; tests/test_parser.py:63-64 `# le entita doppie dei post reali arrivano decodificate una volta sola: le finisce links.normalize_input`

Correzione suggerita:

Decodificare solo entita' con punto e virgola, in due passate: `_ENT = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d+|#[xX][0-9A-Fa-f]+);")` e in normalize_input `url = url.strip()\nfor _ in range(2):\n    url = _ENT.sub(lambda m: html.unescape(m.group(0)), url)`. Provato in scratchpad: '&currency=EUR&section=a&region=it' resta intatto, '&amp;amp;b=2' diventa '&b=2', '&amp;b=2&notify=1' diventa '&b=2&notify=1'. Aggiungere un test con `&currency=`.

**15. OLD_HINT_RE senza confine di parola: 'Fotocamera 199€' e 'Lampada 9,99€' perdono il prezzo; 'a partire da' lo trasforma in barrato** (pipeline, media).

[Eseguito] extract() su 'Fotocamera 199€', 'Lampada 9,99€', 'Scheda 80€' e 'Cuffie a partire da 19,99€' restituisce price None. Gli hint 'era', 'prima', 'rrp', 'da' sono cercati in coda alla finestra di 30 caratteri senza `\b` iniziale, quindi 'era' di 'Fotocamera' e 'da' di 'Lampada' o 'Scheda' sono letti come 'invece di'. L'importo finisce in `old`, `current` resta vuoto e il guard di extract.py:76 azzera anche old_price. Con price None le regole con prezzo_max/prezzo_min non scattano mai (rules.py:12). Anche 'da' in 'a partire da 19,99€' indica il prezzo minimo attuale, non un prezzo pieno.

Evidenza: src/offerte/extract.py:15-19 `r"(?:invece(?:\s+di|\s+che)?|anzich[eéè']?|listino|prezzo\s+pieno|prezzo\s+consigliato|era|prima|rrp|da)"` senza `\b`; :67-68 `window = text[max(0, start - 30):start]` / `OLD_HINT_RE.search(window)`

Correzione suggerita:

Sostituire l'inizio del pattern con `r"\b(?:invece(?:\s+di|\s+che)?|anzich[eéè']?|listino|prezzo\s+pieno|prezzo\s+consigliato|era|prima|rrp|(?<!partire\s)da)"` lasciando invariata la coda `\s*:?\s*(?:a\s+)?$`. Provato in scratchpad: 'Fotocamera 199€' -> 199.0, 'Lampada 9,99€' -> 9.99, 'a partire da 19,99€' -> 19.99, e 'da 80,00€ a 20,00€' resta (20.0, 80.0).

**16. PRICE_RE legge 'N €' come prezzo quando e' seguito da '€ M': 'Series 9 € 299' da 9 euro** (pipeline, media).

[Eseguito] 'Apple Watch Series 9 € 299' da price 9.0; 'Modello 2024 € 59,99' da 2024.0. L'alternativa `post` (importo seguito da `\s?€`) viene provata per prima sul numero che precede il simbolo e consuma il '€' destinato al prefisso `€ 299`. Il formato '€ importo' con un numero di modello subito prima e' tipico dei canali che usano il simbolo come prefisso. Effetto: prezzo e filtri sbagliati, e con prezzo 9 la regola apple-watch-sotto-250 scatta su qualunque Apple Watch.

Evidenza: src/offerte/extract.py:10-12 `(?:€\s?(?P<pre>...)(?!\d)|(?P<post>...)\s?(?:€|(?:euro|eur)(?![a-z])))`

Correzione suggerita:

Aggiungere una guardia sull'alternativa `post`: se fra l'importo e il '€' c'e' uno spazio e dopo il '€' segue `\s?\d`, il '€' appartiene all'importo successivo. Variante minima `(?P<post>AMOUNT)(?:€|\s€(?!\s?\d)|\s?(?:euro|eur)(?![a-z]))`. Costo: '59,99 € 99,99 €' (formato con spazio prima del simbolo) perderebbe il primo importo, quindi scrivere prima due test (formato '9 € 299' e formato '59,99 € 99,99 €') e scegliere la variante che li passa entrambi, ad esempio limitando la guardia agli importi senza decimali.

**17. Un ripost dello stesso link con prezzo piu' basso viene inghiottito: ne' aggiornamento ne' notifica** (pipeline, media).

[Eseguito] Stesso ASIN pubblicato a 79,99 e due ore dopo come 'PREZZO CROLLATO 39,99€' (con un tag affiliato diverso): una sola offerta, price 79.99, n_posts 2, nessun match con ssd-sotto-60 (prezzo_max 60), nessuna notifica. Il ramo duplicato non rilegge il testo del nuovo messaggio (fetch.py:65-67) e `touch_offer` aggiorna solo canali, last_seen e n_posts. Per un aggregatore di offerte il ribasso e' proprio l'evento che interessa.

Evidenza: src/offerte/fetch.py:65-67 `existing = store.find_offer(key, dedupe_since)` / `store.touch_offer(existing.id, m.channel, now)` senza extract; src/offerte/store.py:173 `UPDATE offers SET channels = ?, last_seen = ?, n_posts = n_posts + 1`

Correzione suggerita:

Nel ramo `existing`, estrarre anche dal nuovo messaggio; se `new.price` e' valorizzato e inferiore a `existing.price` di almeno il 5%, aggiornare price/old_price/discount (nuovo metodo `store.update_price`) e trattare l'offerta come fresca per le notifiche (rimuovere la riga da `notifications` o notificare con etichetta 'ribasso'). In alternativa includere il prezzo arrotondato nella chiave per gli URL non Amazon.

**18. Chiave URL troppo aggressiva sugli host generici: pagine diverse collassano in una offerta** (pipeline, media).

[Eseguito] Le liste TRACKING_EXACT e AFFILIATE_EXACT valgono per ogni host, e il frammento viene sempre tolto. Risultato: dedupe_key('https://shop.example/search?keywords=ssd') == dedupe_key('...?keywords=hdd') == 'url:shop.example/search'; '?tag=ssd' e '?tag=hdd' danno 'url:blog.example/offers'; 'https://shop.example/#/product/123' e '#/product/456' danno entrambi 'url:shop.example'. `keywords`, `sr`, `si`, `ref`, `th`, `feature`, `dib`, `tag` sono parametri funzionali su molti siti non Amazon. Un secondo messaggio con un prodotto diverso verso la stessa pagina di ricerca o lo stesso SPA viene aggregato al primo e sparisce dal feed.

Evidenza: src/offerte/links.py:27-32 TRACKING_EXACT (`"keywords"`, `"sr"`, `"si"`, `"ref"`, `"th"`...), :34-37 AFFILIATE_EXACT (`"tag"`), :125 `query = [(k, v) for k, v in query if not _is_tracking(k, host)]`, :126 `urlunsplit(..., "")` che azzera il frammento, :138 `kept = sorted(... if not _is_affiliate(k))`

Correzione suggerita:

Tenere globali solo i parametri inequivocabili (utm_*, fbclid, gclid, msclkid, igshid, mc_*, _ga, _gl) e spostare `keywords`, `crid`, `sprefix`, `qid`, `sr`, `th`, `psc`, `dib`, `ref`, `tag` dentro il ramo Amazon (links.py:120-124) o in un dict per host. Conservare il frammento quando inizia con `/` o `!`: `frag = parts.fragment if parts.fragment.startswith(("/", "!")) else ""` e passarlo a urlunsplit e alla chiave.

**19. Scelta del link: il primo link esterno non e' sempre l'offerta, e dopo la risoluzione non c'e' piu' alcun filtro** (pipeline, media).

[Eseguito] `pick_offer_link(['https://bit.ly/seguici-tg', 'https://www.amazon.it/dp/B08GLX7TNT'])` torna il bit.ly; wa.me, discord.gg, t.co, fb.me e telegra.ph sono accettati; `is_telegram('https://cdn4.telesco.pe/file/x.mp4')` e' False perche' il controllo sui sottodomini copre solo .t.me e .telegram.org (il fixture del repo usa cdn4.telesco.pe, test_parser.py:31). [Eseguito con trasporto finto] bit.ly/join risolve in https://t.me/offertecanale; due messaggi con testo e link offerta diversi ma lo stesso primo link 'unisciti' producono una sola offerta (stesso id, n_posts 2, link t.me): il secondo prodotto non compare. I filtri is_telegram/is_social/is_image_url girano solo prima della risoluzione. Il commento di test_links.py:35 riconosce che i pulsanti 'seguici' precedono l'offerta su alcuni canali.

Evidenza: src/offerte/links.py:12-15 SOCIAL_HOSTS (manca wa.me, discord.gg, t.co, fb.me), :56-58 `h in TELEGRAM_HOSTS or h.endswith((".t.me", ".telegram.org"))`, :74 filtro solo sull'URL grezzo; src/offerte/fetch.py:61-62 `raw_link = L.pick_offer_link(m.links)` / `L.clean_url(resolve_link(...))`

Correzione suggerita:

Riapplicare il filtro all'URL risolto e passare al link successivo: in process_message iterare su un generatore `L.candidate_links(m.links)`, risolvere, e scartare se `L.is_telegram(r) or L.is_social(r) or L.is_image_url(r)`. Aggiungere a SOCIAL_HOSTS 'wa.me', 'discord.gg', 'discord.com', 'fb.me', 't.co', 'ig.me', 'telegra.ph' e portare il controllo Telegram a `h == d or h.endswith('.' + d)` su tutto TELEGRAM_HOSTS. Preferire, fra i candidati, quello con host retail o ASIN.

**20. Risoluzione dei redirect fragile: nessun retry, nessuna cortesia, il link breve resta salvato e cambia la chiave** (pipeline, media).

[Eseguito] Con HEAD e GET entrambi a 429, resolve_link torna 'https://bit.ly/abc123', non scrive in cache e non ritenta; la chiave diventa 'url:bit.ly/abc123'. Lo stesso prodotto postato da un altro canale con il link risolto non si aggrega, e `offers.link` non viene mai riscritto. `Client.resolve` non chiama `_wait()` (la cortesia vale solo per get()) e non ha backoff; config.yaml:22-23 dichiara canali con link bit.ly (prezzitech) e x.gd (offertesmartworld) a 12-15 messaggi al giorno, e al primo giro si risolvono decine di link in sequenza. [Eseguito] `is_short_link('https://a.aliexpress.com/_EHxyz123')` e' False perche' RETAIL_HOST_RE esclude qualunque sottodominio aliexpress prima del controllo sul path; [Dedotto] che i canali cina usino quel formato di condivisione non e' provato dal repo.

Evidenza: src/offerte/http.py:91-101 (nessun _wait, nessun retry, `except httpx.HTTPError: return url`); src/offerte/fetch.py:54 `if resolved != url: store.set_redirect(...)`; src/offerte/links.py:84-85 `if RETAIL_HOST_RE.search(h): return False`

Correzione suggerita:

In Client.resolve: chiamare `self._wait()`, ritentare 2 volte con backoff su 429/5xx riusando la logica di get(). In process_message, se `existing.link` e' un host di SHORT_HOSTS e il nuovo messaggio ha un link risolto, aggiornare `offers.link` e la chiave (`store.update_link`). In is_short_link spostare il controllo retail dopo quello sul path solo per host non acquisto: `if h.startswith('a.aliexpress.') and SHORT_PATH_RE.match(parts.path): return True`.

**21. Lo sconto e' la prima percentuale qualunque del testo e prevale sul calcolo dai prezzi** (pipeline, media).

[Eseguito] 'Cuffie JBL 49,99€ invece di 79,99€ (IVA 22% inclusa)' da discount 22 (calcolato sarebbe 37). 'SSD 1TB 59,99€ + cashback 5%' da discount 5 senza alcun barrato. '-100%' (errore di prezzo) non viene letto perche' PCT_RE ammette 1-99. Un prezzo 0,00€ con barrato 19,99 da discount None perche' `price and old_price` e' falso con price 0.0. find_discount ritorna subito solo se vede 'scont' o 'risparm' nei 20 caratteri precedenti, altrimenti prende la prima percentuale.

Evidenza: src/offerte/extract.py:14 `(?P<pct>[1-9]\d?)\s?%`; :81-90 find_discount (`first = pct` fallback); :124-126 `discount = find_discount(text)` / `if discount is None and price and old_price`

Correzione suggerita:

In extract(): calcolare `calc` se price is not None e old_price; usare la percentuale del testo solo se manca `calc` oppure `abs(calc - pct) <= 3`; altrimenti `calc`. Cambiare `price and old_price` in `price is not None and old_price` e ammettere 100 in PCT_RE con `(?P<pct>100|[1-9]\d?)`. Nel ramo fallback di find_discount richiedere un segno meno o un contesto 'scont|risparm|off|sotto' invece di prendere la prima percentuale.

**22. Coupon: falsi positivi a capo riga e codici non maiuscoli o con emoji persi** (pipeline, media).

[Eseguito] 'Applica il coupon\nSOLO OGGI su Amazon' da coupon 'SOLO'; 'COUPON GRATIS per tutti' da 'GRATIS'; 'QR code SCAN here' da 'SCAN'. Mancati: 'Coupon 🎟 ABC123' e 'Codice: Natale20' (il gruppo code e' case-sensitive maiuscolo, min 4 caratteri, e fra parola chiave e codice sono ammessi solo spazi, due punti, uguale e trattino). Il separatore `\s` attraversa gli a capo, quindi una parola maiuscola all'inizio della riga dopo 'coupon' diventa il codice. Il valore finisce in notifica come '🎟 Coupon: SOLO' (notify.py:45-46).

Evidenza: src/offerte/extract.py:20-23 COUPON_RE (`\s+` e `[\s:：=\-]*` accettano a capo), :24-27 COUPON_STOP di 20 voci, :93-97 find_coupon

Correzione suggerita:

Usare `[ \t]` al posto di `\s` nel separatore e nei `\s+` interni (provato: 'Applica il coupon\nSOLO OGGI' -> None, 'Coupon: SONY10' e 'codice sconto XYZ123' restano); richiedere almeno una cifra oppure lunghezza >= 6 per i codici di sole lettere; estendere COUPON_STOP con 'GRATIS', 'SOLO', 'SCAN', 'LINK', 'OGGI', 'ESCLUSIVO', 'ATTIVO'; consentire un emoji opzionale fra parola chiave e codice.

**23. Statistiche per cartella, canale e regola: query mancanti e semantica disomogenea** (dati e feed, media).

[LETTO] Non esiste un metodo che legga tutte le righe di channels: c'è solo channel_state(name), usato in ciclo da cmd_fonti. Non esistono query bulk per matches e notifications per offerta (solo add_match, is_notified singoli). rules_fired filtra su matched_at (momento della valutazione) mentre i feed filtrano su posted_at: una regola appena creata conta come scattata 'ora' anche per offerte di 13 giorni fa (README:79-80 descrive proprio questo ripopolamento). rules_fired restituisce solo le regole con almeno un match, quindi regole a zero e regole rimosse dalla config (le righe di matches restano finché non si fa purge dell'offerta, store.py:233-235) vanno riconciliate con config.regole. posts_per_day conta post (messaggi), non offerte, e usa date(posted_at,'localtime'): il giorno dipende dal fuso del processo (UTC su GitHub Actions, locale sul PC).

Evidenza: store.py:122-126, 205-214, 251-261; cli.py:117-121, 164-165; store.py:187-190 contro 257-261

Correzione suggerita:

Aggiungere a Store: channel_states() -> dict[str, SourceState] (SELECT * FROM channels), matches_since(since) -> dict[int, list[str]] (join su offers.posted_at >= since), notified_since(since) -> set[int]. Contare i match per regola con posted_at (non matched_at) e filtrare sui nomi presenti in config.regole. Per le serie giornaliere esportare posted_at in UTC e aggregare nel browser, oppure passare il fuso esplicitamente; per i post per canale e giorno riusare posts_per_day (non ricostruibile dall'array offerte perché una stessa offerta può avere post in giorni diversi).

**24. Una notifica Telegram fallita non viene mai ritentata** (dati e feed, media).

[VERIFICATO eseguendo un giro con Telegram che risponde 429 la prima volta] Il match viene registrato prima dell'invio (rules.py:28); la notifica considera solo le offerte nuove del giro (fetch.py:149, fresh) e solo i match nuovi (apply_rules torna solo offerte senza match precedente, store.py:197-201). Se send torna False (HTTP 429, 5xx, errore di rete) l'offerta resta senza riga in notifications ma non rientra più in nessun giro: nel test 1 sola chiamata a Telegram in 3 giri, is_notified False. Notify non legge retry_after di Telegram (notify.py:78-84). Stessa perdita per le offerte raccolte con --senza-notifiche o senza token.

Evidenza: fetch.py:139-156; rules.py:22-30; store.py:197-201; notify.py:68-85

Correzione suggerita:

In fetch.py:144-156 iterare sulle offerte della finestra con match di una regola notify, senza riga in notifications e con posted_at >= now - notifica_max_ore (nuovo Store.pending_notifications(rule_names, min_posted)), invece che su fresh/new_matches; in send gestire 429 con una attesa di retry_after (parameters.retry_after nel JSON di risposta). Nella dashboard il flag notificata permette comunque di vedere le offerte con regola notify e notificata false.

**25. Nessun comando rigenera feed e dashboard dal DB senza fare fetch** (dati e feed, media).

[LETTO] write_feeds ha un solo chiamante, run_fetch (fetch.py:162), e COMMANDS non ha un comando di esportazione. Per sviluppare e collaudare la dashboard serve rigenerare l'uscita senza passare dalla rete; il DB locale è vuoto (verificato), quindi serve anche un set di dati di prova.

Evidenza: cli.py:216-217; fetch.py:162; var/offerte.sqlite con 0 righe

Correzione suggerita:

Aggiungere in cli.py un comando `esporta` che apre Store(var_dir/'offerte.sqlite'), chiama write_feeds e write_dashboard con now=datetime.now(timezone.utc) e registrarlo in COMMANDS (cli.py:216). Per i dati di prova: un test che riempie uno Store in tmp_path con 3 canali, 2 cartelle, 2 regole e una decina di offerte (stesso stile di test_store.py:6-13) e salva il dashboard.json di esempio in tests/fixtures/ per sviluppare l'HTML contro di esso, compreso lo stato vuoto.

**26. restore scambia ogni errore per 'primo avvio' e save sovrascrive lo stato** (cli e deploy, media).

stato.sh restore silenzia stderr e tratta qualsiasi fallimento di `git fetch` (rete, 5xx, permessi) come branch assente, esce 0 e il workflow prosegue con un database vuoto. Il passo save fa poi push forzato su `data`: si perdono tutta la storia, il dedupe e la tabella notifications, e con notifica_max_ore=24 le offerte delle ultime 24 ore che corrispondono a regole notify vengono notificate di nuovo. Provato: con remoto irraggiungibile stampa 'nessun branch data: primo avvio' con rc=0.

Evidenza: deploy/stato.sh:20-25 (`fetch ... 2>/dev/null`, else = primo avvio) e :33 (`push -q --force`); .github/workflows/offerte.yml:37-50

Correzione suggerita:

In stato.sh sostituire il blocco `restore)` (righe 19-25) con (provato in copia: rc 0 con branch, 0 con branch assente, 1 con remoto irraggiungibile):
  restore)
    url="$(remote)"
    if git ls-remote --exit-code --heads "$url" "$BRANCH" >/dev/null 2>&1; then
      git -C "$ROOT" fetch -q --depth 1 "$url" "$BRANCH"
      git -C "$ROOT" show FETCH_HEAD:offerte.sqlite > "$VAR/offerte.sqlite"
      echo "stato ripristinato dal branch $BRANCH ($(stat -c%s "$VAR/offerte.sqlite") byte)"
    else
      rc=$?
      if [ "$rc" -eq 2 ]; then echo "nessun branch $BRANCH: primo avvio"
      else echo "remoto non raggiungibile (ls-remote rc=$rc): mi fermo per non sovrascrivere lo stato" >&2; exit 1; fi
    fi ;;

**27. Nessun test per cli.py, stato.sh, installa.sh, né per i valori di config errati** (cli e deploy, media).

Nessun file in tests/ importa offerte.cli, quindi parser, codici di uscita, ordine delle opzioni e lock di fetch sono verificati solo a mano. Gli script di deploy non hanno test; il giro restore/save si prova in pochi secondi con un bare repo (come fatto qui). Il workflow non esegue pytest prima di pubblicare.

Evidenza: grep di `offerte.cli`, `build_parser`, `stato.sh` in tests/*.py senza risultati; tests/ elenca solo test_dedupe, extract, feeds, fetch, http, links, parser, rules, sources, store

Correzione suggerita:

Aggiungere tests/test_cli.py con config temporanea e `main(["-c", str(cfg), "fonti"])`, `main(["-c", str(cfg), "filtra", "ssd"])` su database vuoto e un caso `["fetch", "-v"]` che si aspetta SystemExit(2); aggiungere tests/test_stato.py che esegue stato.sh restore/save con `OFFERTE_DATA_REMOTE` su un bare repo in tmp_path, inclusi il caso di remoto irraggiungibile (exit 1) e di branch assente (exit 0).

**28. Apify: niente backoff, risposta non JSON non gestita, prezzo 0 passa ogni prezzo_max** (fonti, media).

[letto + verificato eseguendo per il prezzo] (1) Apify usa ctx.client.http direttamente: nessuna cortesia, nessun retry su 429/5xx, FetchError immediato. (2) resp.json() solleva JSONDecodeError se il corpo non e' JSON (proxy, pagina di errore con 200): finisce nel ramo generico con traceback. (3) Un record con `price: 0` (comune quando l'actor non trova il prezzo) diventa price=0.0 e la regola `prezzo_max` lo accetta: rules.py:12 rifiuta solo None o prezzo superiore al massimo, quindi 0.0 notifica ogni regola con prezzo_max.

Evidenza: apify.py:73 e 77 "ctx.client.http.post/get(...)"; apify.py:83 "dati = resp.json()"; base.py:85-90 to_number(0) -> 0.0; base.py:138 "price=to_number(_pick(d, \"prezzo\"))"; rules.py:12 "if rule.prezzo_max is not None and (offer.price is None or offer.price > rule.prezzo_max):"

Correzione suggerita:

apify.py riga 83:

    try:
        dati = resp.json()
    except ValueError:
        raise FetchError("Apify: risposta non JSON") from None

base.py record_to_message: `price=(p if (p := to_number(_pick(d, "prezzo"))) else None)` e lo stesso per `old_price`, cosi' 0 e' trattato come prezzo assente.

**29. Parser Telegram: foto-risposta prende il testo citato; datetime non valido abbatte la pagina** (fonti, media).

[dedotto per la struttura reale, verificato su markup sintetico] Per un messaggio senza testo proprio ma con una risposta, il fallback `.tgme_widget_message_text` trova il blocco citato della risposta e lo tratta come testo del messaggio: con markup sintetico (blocco reply con classe js-message_reply_text, la struttura che ricordo di t.me/s, non confermata da alcuna fixture: nessuna fixture contiene 'reply') nasce un'offerta dal testo di un altro post, con il suo prezzo. Il primo selettore con js-message_text esclude gia' la risposta quando il messaggio ha testo. Inoltre datetime.fromisoformat non e' protetto: un valore non valido solleva ValueError, abbatte parse_page e quindi la fonte intera (verificato con datetime 'domani').

Evidenza: parser.py:70 "text_node = node.css_first(\".tgme_widget_message_text.js-message_text\") or node.css_first(\".tgme_widget_message_text\")"; parser.py:101 "date=datetime.fromisoformat(time_node.attributes[\"datetime\"])"

Correzione suggerita:

parser.py riga 70:

    text_node = node.css_first(".tgme_widget_message_text:not(.js-message_reply_text)")

(provato in selectolax: ignora il blocco di risposta e trova il testo proprio). Riga 101: calcolare la data in un `try: date = datetime.fromisoformat(...) except ValueError: return None` prima di costruire Message.

**30. Testi che normalizzano a stringa vuota hanno tutti la stessa chiave** (pipeline, media).

[Eseguito] offer_key(None, 'https://t.me/foo'), offer_key(None, '📲 @canale') e offer_key(None, '🔥🔥🔥') tornano tutte 'text:da39a3ee5e6b4b0d3255bfef95601890afd80709' (SHA-1 della stringa vuota). Un messaggio il cui unico contenuto e' un link Telegram, una menzione o emoji, senza link utile, viene aggregato a qualunque altro dello stesso tipo nei 7 giorni.

Evidenza: src/offerte/dedupe.py:13-17 normalize_text e :20-21 `"text:" + hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()`

Correzione suggerita:

In text_key: `n = normalize_text(text)\nreturn "text:" + hashlib.sha1((n or text).encode("utf-8")).hexdigest()`; meglio ancora, per `n` vuoto usare `"msg:" + permalink`, passando il permalink a offer_key.

**31. Regex quadratica in TRAILING_PRICE_RE e product_name pulisce tutte le righe anche se ne usa due** (pipeline, media).

[Eseguito] Una riga di soli trattini: 4096 caratteri 0,35 s, 8000 caratteri 1,3 s, andamento quadratico (a 60000 supera il timeout di prova da 120 s). Telegram limita il messaggio a 4096 caratteri ma rss, html, comando e apify no, e record_to_message non comprime gli spazi (base.py:124-139). product_name applica `_clean_line` a ogni riga (extract.py:113) pur scegliendo solo lines[0] o lines[1] (extract.py:116).

Evidenza: src/offerte/extract.py:28-32 `[\s,;:|\--, ]*(?:\b(?:a|al prezzo di|...)\s+)?(...)\s*$`, :113 `lines = [s for s in (_clean_line(line) for line in text.splitlines()) if s]`

Correzione suggerita:

In product_name usare un generatore e fermarsi alla seconda riga non vuota (`itertools.islice`), e limitare ogni riga con `line[:300]` prima di `_clean_line`.

### Segnalazioni a bassa severità

| n. | area | severità | problema |
|:--|:--|:--|:--|
| 32 | fonti | bassa | Messaggio scartato per sempre se l'URL e' malformato (resolve e clean_url sollevano, last_id avanza) |
| 33 | fonti | bassa | SSRF cieco: resolve() segue link di post altrui verso host privati |
| 34 | fonti | bassa | comando: lo script eredita tutto l'ambiente, token compresi |
| 35 | pipeline | bassa | Titolo del prodotto: la prima riga puo' essere insegna, URL, riga prezzo o hashtag |
| 36 | pipeline | bassa | Ritenzione per posted_at e cancellazione dei post: item vecchi di fonti non Telegram si ricreano e si ripurgano a ogni giro |
| 37 | dati e feed | bassa | La dataclass Rule perde il testo originale di parole, escludi e canali |
| 38 | cli e deploy | bassa | Trigger push del workflow su `main`: chiuso, il branch locale è `main` dal 28.10.2026; resta senza remoto |
| 39 | cli e deploy | bassa | Voci `canali:` rifiutano `ogni`, `canale` e `pagine`, ma il README dice il contrario |
| 40 | cli e deploy | bassa | Il comando container del README richiede un .env che il README presenta come facoltativo |
| 41 | cli e deploy | bassa | Opzioni globali -c e -v accettate solo prima del sottocomando |
| 42 | fonti | bassa | Validazione di configura() incompleta: ValueError, AttributeError, TypeError, IndexError invece di ConfigError |
| 43 | fonti | bassa | comando: cwd relativo, decodifica, stdin ereditato |
| 44 | fonti | bassa | record_to_message: `links` stringa spezzata in caratteri, id 0 scartato |
| 45 | fonti | bassa | RSS/Atom: link e immagini relativi, content xhtml, enclosure senza type |
| 46 | fonti | bassa | NoPreview senza messaggio e dipendenza da telegram.py in fetch.py |
| 47 | pipeline | bassa | Prezzo fornito dalla fonte e testo incoerenti: viene salvato un barrato minore del prezzo |
| 48 | pipeline | bassa | La finestra di dedupe parte da first_seen e non dall'ultimo ripost |
| 49 | pipeline | bassa | Canonicalizzazione degli host incompleta: sottodomini Amazon e AliExpress e parametri AliExpress non unificati |
| 50 | pipeline | bassa | Stato delle regole non ripulito e rilettura completa a ogni giro |
| 51 | pipeline | bassa | Ordinamento dei messaggi fuori dal try: date naive e aware mescolate abortiscono l'intero giro |
| 52 | pipeline | bassa | Il flag `bootstrapped` viene scritto ma mai letto |
| 53 | dati e feed | bassa | write_feeds va in FileNotFoundError se non emette alcun feed |
| 54 | dati e feed | bassa | Collisione di slug fra cartelle o regole con nomi diversi |
| 55 | dati e feed | bassa | search non trova testo maiuscolo accentato |
| 56 | cli e deploy | bassa | README e docstring non elencano tutti i comandi e le opzioni |
| 57 | cli e deploy | bassa | Estratto di config.yaml nel README diverso dal file reale |
| 58 | cli e deploy | bassa | Container: arresto lento, nessuna politica di riavvio, fuso UTC, utente root, nessun .containerignore |
| 59 | cli e deploy | bassa | README consiglia `podman generate systemd`, deprecato |
| 60 | cli e deploy | bassa | load_env gira dopo load_config: OFFERTE_FEED_BASE_URL in .env è ignorata |
| 61 | cli e deploy | bassa | Valori numerici errati in config danno traceback invece di ConfigError |
| 62 | cli e deploy | bassa | Il file .env.example copiato tale e quale attiva notifiche con credenziali finte |
| 63 | cli e deploy | bassa | Workflow: permessi ampi a livello di workflow, azioni su tag, uv run reinstalla il gruppo dev |
| 64 | cli e deploy | bassa | Accoppiamento non documentato fra var_dir, stato.sh e workflow |
| 65 | cli e deploy | bassa | Affermazione sulla riabilitazione automatica del cron non verificata |
| 66 | cli e deploy | bassa | README intro e descrizione del pacchetto fermi alla sola fonte Telegram, `prova` e `cwd` con caveat taciuti |
| 67 | cli e deploy | bassa | `fetch --fonte` distingue le maiuscole mentre i nomi dei canali sono normalizzati |

## 4. Cosa manca rispetto all'obiettivo

L'obiettivo dichiarato è una dashboard per filtrare le offerte (testo o regex, prezzo, sconto, cartella, canale, periodo, coupon) con stato nell'URL, a costo zero, funzionante sia da `offerte serve` sia su GitHub Pages. Oggi esistono solo i feed e la pagina indice. La specifica in `docs/specifica-dashboard.md` fissa file, contratto dati (`dashboard.json` con tutte le offerte della finestra, cartelle, regole), motore JavaScript `filtri.js` con parità verificata contro `rules.matches`, pagina, test (pytest, runner JS, Chrome headless) e criteri di accettazione A1-A36. Il pannello di progettazione ha scartato per eccesso di complessità lo storico prezzi, il raggruppamento per prodotto, gli shard per giorno e il rendering doppio Python/JS.

## 5. Sprint rimanenti

| sprint | contenuto | chiusura |
|:--|:--|:--|
| S0 correzioni | i problemi 1, 2, 3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 24, 26, 27 e le incoerenze del README (39, 40, 41, 56, 57, 60, 66), più la stampa di `offerte prova`; 4, 5, 6 e 25 si chiudono con la dashboard (S2) | test dedicati, `pytest` verde, commit |
| S1 motore delle regole | `sconto_min`, `solo_coupon`, parole opzionali, stringhe sorgente in `Rule`, `filtra` esteso | A18-A20 |
| S2 dati e backend | `dashboard.json`, `item_name`, `safe_url`, `write_dashboard` protetto, comando `feed`, dati demo | A2-A17 |
| S3 motore JavaScript | `filtri.js`, runner su gjs/node/deno/bun, fixture condivisa, parità con Python | A21-A26 |
| S4 pagina | `dashboard.html`, `dashboard.css`, `dashboard.js`, controlli statici, test con Chrome headless | A27-A33 |
| S5 chiusura | README, versione 0.3.0, wheel, verifica su telefono | A34-A36 |
| S6 fonti pronte | strumenti open source documentati come fonti `rss` locali (vedi `docs/spunti-open-source.md` §3), opzioni `url_env` e `scarta_host` | test delle due opzioni; la prova dal vivo di changedetection.io non è richiesta in questo giro |

Le istruzioni operative per eseguirli stanno in `docs/prompt-opus.md`.

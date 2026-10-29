# Spunti open source per offerte

Stato al 28.10.2026.

## 1. Candidati tenuti

| Nome | Cosa è | Licenza | Come si usa qui | Priorità |
|:--|:--|:--|:--|:--|
| [MiniSearch 7.2.0](https://github.com/lucaong/minisearch) | Full-text in memoria con prefisso, fuzzy e AND, 6 KB gzip | MIT | Casella testo tollerante a refusi e accenti. Indice costruito una volta su `dashboard.json`. Regex e soglie restano JS nativo | usa subito |
| [uFuzzy 1.0.19](https://github.com/leeoniya/uFuzzy) | Fuzzy su array di stringhe senza indice, 4 KB gzip | MIT | Al posto di MiniSearch solo se serve l'evidenziazione dei termini. Mai entrambe | alternativa |
| [Alpine.js 3.17.5](https://github.com/alpinejs/alpine) e `@alpinejs/intersect` | Reattività dichiarativa nell'HTML, 20 KB gzip più 1 KB | MIT | Lega gli 8 controlli ai filtri e carica le card a lotti con `x-intersect` | usa subito |
| [Tabulator 6.7.1](https://github.com/tabulator-tables/tabulator) | Tabella con rendering virtuale e ordinamento, 104 KB gzip | MIT | Vista tabella densa opzionale, caricata alla prima apertura e alimentata con `replaceData` | utile dopo |
| [Clusterize.js 1.0.0](https://github.com/NeXTs/Clusterize.js) | Rendering virtuale per righe di altezza fissa, 2,5 KB gzip | MIT (solo la 1.0.0, le 0.x sono GPLv3) | Riserva se i lotti da 60 card non bastano su un telefono vero | utile dopo |
| [CSS content-visibility: auto](https://developer.mozilla.org/en-US/docs/Web/CSS/content-visibility) | Proprietà nativa che salta il layout delle card fuori schermo | nessuna | Serve solo con oltre 1500 card renderizzate insieme. A 500 il guadagno è nullo | utile dopo |
| [Simple.css 2.3.7](https://github.com/kevquirk/simple.css) | CSS classless, 2,8 KB gzip, tema scuro automatico | MIT | Stile base di form, `article`, `mark`. Colonna larga e griglia con 5 righe proprie | usa subito |
| [Pico CSS 2.1.1](https://github.com/picocss/pico) | CSS con classi, 11,6 KB gzip, archiviato il 04.10.2026 | MIT | Alternativa a Simple.css se servono dropdown e `fieldset role=group`. File pinned e immutabile su jsDelivr | alternativa |
| [Oat 1.0.0](https://github.com/knadh/oat) | CSS con card, badge, griglia, 7,3 KB gzip | MIT | Il più completo e vivo, ma usa `light-dark()` e nesting nativo, fuori dal target iOS 15.4 e Chrome 100 | alternativa se si alza il target |
| [MVP.css 1.18](https://github.com/andybrewer/mvp) | CSS classless con card `section` e `aside`, 2,7 KB gzip | MIT | Piano B per avere la griglia di card senza CSS di layout. Il tema scuro richiede `color-mode="user"` | utile dopo |
| [Water.css 2.1.1](https://github.com/kognise/water.css) | CSS classless, 3,6 KB gzip, fermo dal 2021 | MIT | Ripiego per pagine di servizio o lista a righe | utile dopo |
| [Bootstrap Icons 1.13.2](https://github.com/twbs/icons) | SVG a 16 px con `fill=currentColor`, compreso il logo Telegram | MIT | Unico set per l'interfaccia: 13 icone copiate come `<symbol>` nell'HTML, 6,4 KB, nessuna CDN | usa subito |
| [Lucide 1.63.0](https://github.com/lucide-icons/lucide) | SVG a tratto, 24 px | ISC, più MIT per alcune icone | Alternativa a Bootstrap Icons, da non mescolare. Manca il logo Telegram | alternativa |
| [HenryLok0/steam-deals-tracker](https://github.com/HenryLok0/steam-deals-tracker) | Dashboard statica di offerte Steam, JS vanilla a moduli ES | MIT | Da leggere: `docs/app.js` righe 244-310, 1086-1101, 1303-1352 (stato nell'URL, debounce, lotti) | usa subito |
| [sushi057/salekhoj](https://github.com/sushi057/salekhoj) | Aggregatore statico di sconti, `app.js` da 491 righe | MIT | Scheletro di `renderDeals()` (`site/app.js` righe 312-409) e idea di `scrapers/gate.py` | usa subito |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | Monitor di pagine con rilevamento di prezzo e disponibilità, RSS in uscita | Apache-2.0 | Satellite locale per pagine prodotto con JSON-LD, fonte `rss` sul feed per tag | utile dopo |
| [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) | PHP, 550 bridge, uscita Atom | Unlicense | Istanza locale per siti italiani senza feed che la fonte `html` non copre | utile dopo |
| [kill-the-newsletter](https://github.com/leafac/kill-the-newsletter) | Casella email anonima che diventa feed Atom | MIT | Coupon riservati agli iscritti, solo servizio ospitato, dopo due modifiche al codice | utile dopo |
| [Discount-Bandit](https://github.com/Cybrarist/Discount-Bandit) | Tracker di prezzi Laravel con feed RSS delle notifiche | nessuna nel v4 | Solo locale, per watchlist Amazon.it, dopo aver esteso `PRICE_RE` | utile dopo |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Generatore di feed Node, circa 2000 namespace | AGPL-3.0 | Solo per un sito con route già mantenuta. Nessuna route per Amazon.it, eBay o offerte italiane | utile dopo |
| [FreshRSS](https://github.com/FreshRSS/FreshRSS) | Lettore RSS e JSON Feed self-hosted | AGPL-3.0 | Collaudo locale dei feed prodotti e modello per la sintassi di ricerca | utile dopo |
| [gabrielhsp-sys/telegram-offer-monitor](https://github.com/gabrielhsp-sys/telegram-offer-monitor) | `parser.py` e `dedup.py` a regex per offerte Telegram | MIT | Tre idee da riscrivere, non codice da importare (sezione 4) | prima della dashboard |
| [ClearURLs/Rules](https://github.com/ClearURLs/Rules) | Database JSON di regole per ripulire gli URL, 206 provider | LGPL-3.0 | Riserva per link awin, tradedoubler, effiliation (sezione 4) | utile dopo |
| [scrapinghub/price-parser](https://github.com/scrapinghub/price-parser) | Parsing di importi e valute | BSD-3-Clause | Solo il corpus di test, con avviso di licenza | utile dopo |
| [Datasette Lite](https://github.com/simonw/datasette-lite) | Datasette nel browser su Pyodide | Apache-2.0 | Link «esplora in SQL» verso una copia self-hosted con pin | utile dopo |
| [sql.js 1.15.2](https://github.com/sql-js/sql.js) | SQLite in WebAssembly, 354 KB | MIT | Livello dati alternativo a `dashboard.json`, solo se servono JOIN o statistiche | utile dopo |
| [@sqlite.org/sqlite-wasm 3.54.1-build1](https://github.com/sqlite/sqlite-wasm) | Build wasm di SQLite con FTS5 | Apache-2.0 | Solo se la ricerca FTS5 diventa un requisito | utile dopo |

## 2. Dashboard

Decisione del 29.10.2026, dopo la revisione avversaria dei documenti: nella dashboard di `docs/specifica-dashboard.md` non si usano librerie da CDN. MiniSearch darebbe risultati diversi da `rules.matches` (prefisso e fuzzy contro parola intera e regex), Alpine richiede `unsafe-eval` nella CSP e Simple.css impone una griglia globale in conflitto con layout e token di colore della specifica. Questa sezione resta come riferimento verificato (hash, versioni, misure) per un'evoluzione futura, per esempio una casella di ricerca tollerante separata dal filtro delle regole. Il paragrafo «Vincoli della specifica» in fondo cita la specifica nella versione del 28.10.

### Librerie da CDN

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/simpledotcss@2.3.7/simple.min.css"
      integrity="sha384-w3/JhK7GP1jIgYT9phdYXYeUKzhTc4AxDpfqFZO1tkmCHBZrEmZ2c68gaD1yKhZq" crossorigin="anonymous">

<script defer src="https://cdnjs.cloudflare.com/ajax/libs/minisearch/7.2.0/umd/index.min.js"
        integrity="sha512-bxNn8csqHSaI1AgYVvi4ejDdG9GfPbmth/TBcxd6J02ShNFQRqRJVPqqCvRHYV1nnvwCTeteqWuoOAeNewQ9CQ==" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/intersect@3.17.5/dist/cdn.min.js"
        integrity="sha384-2xKHWSjeeiB/MQGC0Cs4HQ3mYVvbQP7a/mdjP1d6A1AKxER75HPZwrofpbWfx0b6" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.17.5/dist/cdn.min.js"
        integrity="sha384-FYLKjwG3aohNhNZoVG8sY/5ntunm+MqylL90Q+rT3OM7AwV9/BKFjk/RjoIpIgsI" crossorigin="anonymous"></script>
```

Totale circa 30 KB gzip: Alpine 19,9, intersect 1,0, MiniSearch 5,9, Simple.css 2,8. L'ordine conta. Il plugin intersect va prima del core (https://alpinejs.dev/plugins/intersect). MiniSearch va prima di Alpine, perché Alpine parte appena il suo script è eseguito (deduzione sul comportamento di `defer`).

MiniSearch si prende da cdnjs e non da jsDelivr. Su jsDelivr `index.min.js` è minificato al volo e il file stesso dice di non usare SRI. Tabulator, se servirà, si prende da jsDelivr, perché su cdnjs è fermo alla 6.4.0 (la 6.7.1 dà 404).

Le icone si copiano come `<symbol>` in un `<svg style="display:none">` da `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.2/icons/<nome>.svg`. Si usano con `<svg class="i"><use href="#i-telegram"/></svg>` e `.i{width:1em;height:1em;fill:currentColor}`. Le 13 icone sono: search, funnel, tag, calendar, rss, percent, ticket-perforated, box-arrow-up-right, sort-down, telegram, brightness-high, moon, copy. Nel repo va il testo della licenza MIT. L'icona Telegram è un marchio: per un link personale è un uso descrittivo (inferenza), altrimenti basta `send`.

### CSS di raccordo per Simple.css

```css
body{grid-template-columns:1fr min(72rem,94%) 1fr}
fieldset{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.5rem 1rem}
fieldset label>input,fieldset label>select{display:block;width:100%;box-sizing:border-box}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(18rem,1fr));gap:1rem}
main>form{grid-column:1/-1}
```

Sconto in `<mark>`, coupon in `<code>`, tabelle dentro `<figure>` per lo scroll orizzontale su telefono. Il tema scuro è letto nel sorgente (`prefers-color-scheme`), non verificato a schermo.

Con Pico al posto di Simple.css la lista di card non va in `.grid`, che mette tutti gli elementi su una riga di colonne strette. Va sostituito con:

```css
.offerte{display:grid;gap:var(--pico-grid-row-gap) var(--pico-grid-column-gap);grid-template-columns:repeat(auto-fill,minmax(16rem,1fr))}
.offerte>article{margin:0}
```

### Dati e collante

I dati sono il `dashboard.json` di `docs/specifica-dashboard.md` §2.2 (chiavi `id t n x k p b s c u m i`), che copre già l'intera finestra con tetto a 10000 offerte. Non serve un secondo esportatore. Lo schema sotto è assemblato da frammenti provati (MiniSearch, `$watch` con `history.replaceState`, `x-intersect`). L'insieme non è stato eseguito.

```html
<main x-data="offerte()">
  <form>
    <input type="search" x-model.debounce.250ms="f.q">
    <input type="number" x-model.number="f.min"> <input type="number" x-model.number="f.max">
    <input type="number" x-model.number="f.sc"> <input type="checkbox" x-model="f.cp">
  </form>
  <template x-for="o in shown" :key="o.id">
    <article class="card"><h3 x-text="o.n"></h3></article>
  </template>
  <div x-show="n < filtered.length" x-intersect.margin.400px="n += 60"></div>
</main>
```

```js
const KEYS = ['q', 're', 'min', 'max', 'sc', 'cat', 'can', 'per', 'cp'];
const BOOL = ['re', 'cp'];
const pieno = v => v !== '' && v != null && v !== false;
const norm = t => t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

function offerte() {
  return {
    all: [], n: 60, ms: null,
    f: { q: '', re: false, min: '', max: '', sc: '', cat: '', can: '', per: '', cp: false },
    async init() {
      this.all = (await (await fetch('dashboard.json', { cache: 'no-cache' })).json()).offerte;
      this.ms = new MiniSearch({ fields: ['n', 'x', 'k'], processTerm: norm });
      this.ms.addAll(this.all);                       // una volta sola, mai replace, remove o discard
      const p = new URLSearchParams(location.search);
      for (const k of KEYS) if (p.has(k)) this.f[k] = BOOL.includes(k) ? p.get(k) === '1' : p.get(k);
      this.$watch('f', () => {                        // dopo la lettura dell'URL
        this.n = 60;
        const u = new URLSearchParams();
        for (const k of KEYS) if (pieno(this.f[k])) u.set(k, this.f[k] === true ? '1' : this.f[k]);
        const s = u.toString();
        history.replaceState(null, '', s ? '?' + s : location.pathname);
      });
    },
    get filtered() {
      const f = this.f;
      const ids = pieno(f.q) && !f.re
        ? new Set(this.ms.search(f.q, { prefix: true, fuzzy: 0.2, combineWith: 'AND' }).map(r => r.id)) : null;
      let rx = null;
      if (pieno(f.q) && f.re) { try { rx = new RegExp(f.q, 'i'); } catch (e) { /* espressione incompleta */ } }
      return this.all.filter(o =>
        (!ids || ids.has(o.id)) && (!rx || rx.test(o.x)) &&
        (!pieno(f.min) || o.p >= +f.min) && (!pieno(f.max) || o.p <= +f.max) &&
        (!pieno(f.sc) || o.s >= +f.sc) && (!f.cp || o.c));   // cartella, canale, periodo: stesso schema su o.k e o.t
    },
    get shown() { return this.filtered.slice(0, this.n); },
  };
}
```

Le trappole di Alpine verificate sono tre. `x-model` su input numerico senza `.number` salva stringhe, quindi nel filtro si usa `+f.min`. `x-for` vuole un solo elemento radice e `:key`. `x-intersect` scatta solo al cambio di stato, quindi il primo lotto deve riempire viewport più margine (con card da circa 84 px e lotti da 60 succede).

### Repository di riferimento

Lo scheletro è `site/app.js` di salekhoj (MIT, Copyright (c) 2026 Suvash Joshi), righe 312-409 di `renderDeals()`. Stato iniziale da `URLSearchParams`, `apply()` che filtra e ordina in memoria, `history.replaceState`, solo le prime 48 card con reset a ogni cambio filtro, skeleton ad altezza fissa contro il layout shift. Su 10.592 prodotti reali filtro più sort costa circa 1,1 ms e un filtro RegExp circa 0,5 ms (misura in Node 22), quindi non serve virtualizzazione.

Come secondo riferimento c'è steam-deals-tracker (MIT, Copyright (c) 2026 Henry Lok). In `docs/app.js` servono `buildFilterParams` e `syncUrlParams` (righe 244-271), la lettura all'avvio (276-310), il debounce da 250 ms (1303-1313) e il caricamento a lotti (1349-1352). Il comportamento si prova dal vivo su https://steam-deals.henrylok.me/.

Con Alpine il rendering e il binding dei controlli non si copiano: dai due repo restano la logica di filtro, l'URL e la paginazione. Sono repo giovani e di un solo autore, quindi si leggono e si riscrivono, non si forkano. Se si copia una porzione sostanziale, in testa al file va `Adapted from sushi057/salekhoj (MIT, Copyright (c) 2026 Suvash Joshi)`.

### Cosa evitare

- Non usare MiniSearch e uFuzzy insieme. Con uFuzzy `filter()` rispetta l'ordine delle parole (serve `search()` con `outOfOrder` a 0 o 3), oltre 1000 match non c'è ordinamento e un termine con «-» davanti è un'esclusione («-30%» esclude).
- Non usare URL non fissati: unpkg senza versione (la doc di Oat e di MVP.css), `cdn.simplecss.org` e `water.css@2`.
- Non usare Clusterize 0.x (GPLv3).
- Non mettere mai `innerHTML` né `x-html` sul testo che arriva da Telegram: si usano `x-text` e `textContent`.
- Sugli `href` `esc()` non basta: `javascript:` passerebbe. Serve il controllo `^https?://` prima di costruire la card.
- Non copiare `sanitize.js` di steam-deals, che toglie `alt`, `width` e `class` da `a` e `img`.
- Non copiare il fallback su `localStorage` di steam-deals. Un link condiviso non riprodurrebbe lo stato: si parte dai default e si applica l'URL.
- Non copiare il `games.json` da 50 MB committato nel repo né il service worker di steam-deals.
- Non copiare da salekhoj GoatCounter (`app.js` righe 151-163 e 481-482), il `@import` di Google Fonts (`style.css` riga 4) né le pagine brand e home. I valori in `value="${b}"` e `data-c="${b}"` (righe 329 e 341) non sono escapati.
- Non usare `content-visibility` con lotti da 60 card, dove non dà nulla. Con 3000-6000 card in una volta costa 58-79 ms contro 167-200. Va con `contain-intrinsic-size` stimato per breakpoint, e su Safari 18.x la ricerca nella pagina non trova il testo saltato.
- Non scrivere `@alpinejs/history`. Non esiste su npm. Nel repo c'è solo un sorgente segnaposto per Livewire.

### Vincoli della specifica

`docs/specifica-dashboard.md` §0 fissa «JavaScript vanilla, nessuna libreria, nessuna CDN» e come target iOS 15.4 e Chrome 100. Questo stack richiede di sostituire il primo vincolo. Il secondo esclude Oat, perché `light-dark()` è disponibile da maggio 2024 e su iOS 15.4 la pagina resterebbe senza tema. Alpine 3.17.5 e Simple.css 2.3.7 non risultano provati su iOS 15.4, quindi la prova su telefono va fatta prima di fissare lo stack.

## 3. Fonti

La fonte `rss` legge RSS 2.0 e Atom, non JSON Feed. Le opzioni ammesse sono `url` e `massimo` più i campi comuni (`src/offerte/sources/rss.py` riga 86, `base.py` riga 41). Il prezzo si estrae dal testo e `PRICE_RE` (`extract.py` riga 11) vuole «€» o «euro/eur» dopo l'importo.

Il workflow su Actions non raggiunge `127.0.0.1`. Le fonti locali vanno quindi in un `config.locale.yaml` non tracciato, selezionato con `-c` o `OFFERTE_CONFIG` (`cli.py` riga 30, 222). Nel servizio systemd si aggiunge `Environment=OFFERTE_CONFIG=...` a `systemd/offerte-fetch.service`. Il file non tracciato serve anche perché i token dei feed non devono stare in un config su repo pubblico. Le voci raccolte in locale finiscono nel database e nei feed locali, non in quelli di Pages (deduzione: lo stato di Actions vive nel branch `data`).

```
podman run -d --name changedetection -p 127.0.0.1:5000:5000 -v changedetection-data:/datastore ghcr.io/dgtlmoon/changedetection.io
podman run -d --name rss-bridge -p 127.0.0.1:3000:80 docker.io/rssbridge/rss-bridge:latest
```

```yaml
# config.locale.yaml: copia di config.yaml con queste fonti
fonti:
  - nome: cdio-negozi
    tipo: rss
    cartella: informatica
    url: "http://127.0.0.1:5000/rss/tag/<uuid-del-tag-offerte>?token=<rss_access_token>"
    ogni: 30
  - nome: rssbridge-sito
    tipo: rss
    cartella: casa
    url: "http://127.0.0.1:3000/?action=display&bridge=<NomeBridge>&<parametri>&format=Atom"
    ogni: 60
```

### changedetection.io

È l'unico tracker di modifiche che serve, e solo per pagine prodotto con JSON-LD, OpenGraph o microdata. Si crea un watch «Re-stock & Price detection for single product pages» per prodotto, tutti con il tag `offerte`. Per «avvisa sotto X» si imposta solo il minimo, perché un prezzo dentro l'intervallo min-max viene soppresso.

- **Template del feed.** Il testo predefinito è «In Stock: True - Price: 12.99», senza valuta, e `PRICE_RE` non lo legge (provato con `extract()`). In Settings, RSS, `rss_template_override` serve questo, la cui sintassi esatta va verificata sull'istanza: `{{watch_label}}\n{{restock.price}} €{% if restock.previous_price %} invece di {{restock.previous_price}} €{% endif %}\n{{watch_open_url}}`.
- **Feed per tag.** Si usa il feed per tag. Quello per singolo watch risponde 400 finché ci sono meno di 2 snapshot, quello per tag salta i watch in silenzio. Ha una voce per watch (l'ultimo cambio), che sparisce quando si apre il watch nella UI e ricompare al cambio successivo. Il guid `uuid/timestamp` fa reggere la dedupe.
- **Titolo e link.** Il titolo dell'item è `<URL> - Change @ <data>` e il link è la pagina diff locale (deduzione dal codice). Nome e link del prodotto devono quindi stare nel corpo del template.
- **Amazon.it.** Non funziona. Il plugin Amazon è deprecato dal 2024-08 e la pagina non espone JSON-LD.

### RSS-Bridge

Serve solo per un sito italiano senza feed, con dati in JSON incorporato o che richiede XPath. La fonte `html` copre già selettori CSS, prezzo, barrato e immagine. Va usato il formato Atom o Mrss, non Json (JSON Feed 1, che la fonte `rss` non legge). `ogni: 60` rispetta la cache dei bridge. Il timeout di default è 3 secondi e va alzato per i siti lenti.

Non va usato per Amazon.it (prezzo vuoto sui domini nazionali, issue [#2863](https://github.com/RSS-Bridge/rss-bridge/issues/2863) e [#4586](https://github.com/RSS-Bridge/rss-bridge/issues/4586)), per eBay (403, [#4974](https://github.com/RSS-Bridge/rss-bridge/issues/4974)), per Idealo.it né per Pepper (chiuso il 14.08.2025). Dentro Actions il runner ubuntu-24.04 ha PHP 8.3, ma `php -S` non è provato. Colpirebbe i siti da IP datacenter ogni 15 minuti con la cache vuota, quindi non si fa. Prima di adottarlo serve una prova di 10 minuti con un solo bridge su un sito reale.

### kill-the-newsletter

Serve solo per i coupon riservati agli iscritti, con il servizio ospitato (https://kill-the-newsletter.com/, Atom con `content type="html"`, già letto da `rss.py`). Prima servono due modifiche piccole:

- Un'opzione `url_env` in `sources/rss.py`, con la variabile nel blocco `env` di `offerte.yml` accanto ad `APIFY_TOKEN`.
- Permalink vuoto e scarto dei link `kill-the-newsletter.com` per questa fonte.

L'ID del feed coincide con la parte locale dell'indirizzo email e compare nei link di ogni voce, quindi finirebbe nei feed pubblici. Il tetto è 512 KiB per feed, le voci oltre un mese sono cancellate e la gratuità non è dichiarata. Nessun feed reale è passato dal parser, quindi non so se le newsletter dei negozi italiani lo bloccano.

### Discount-Bandit, RSSHub, FreshRSS

- **Discount-Bandit.** Il v4 non ha licenza (la GPL-3.0 è solo nei tag v3, albero cancellato), quindi non si copia codice. Il feed locale è `http://127.0.0.1:8080/feed/?feed_id=<token di 250 caratteri dal profilo>`. Le voci dicono «For Just EUR 12.99 - Discount For ...» e `PRICE_RE` non riconosce «EUR» prima dell'importo, quindi va esteso. Amazon.it usa richieste HTTP con User-Agent a rotazione, eBay c'è solo come .com e .de. Per pagine singole è meglio changedetection.io.
- **RSSHub.** Non aggiunge dati: `parser.py` riga 80 legge già gli href dei pulsanti inline. Ha senso solo per un sito con route mantenuta su docs.rsshub.app, con tag datato (per esempio `diygod/rsshub:2026-10-28`) su `127.0.0.1:1200`.
- **FreshRSS.** Serve per collaudare i feed prodotti. Legge anche JSON Feed 1.1 (dalla 1.24.0). Dalla 1.30.0 blocca `127.0.0.1` per SSRF, quindi ci si iscrive all'URL pubblico di Pages oppure si imposta `INTERNAL_HOST_ALLOWLIST`. La sintassi `intitle:`, `#tag`, `date:P1W`, `-negazione` e regex fra slash è un buon modello per il campo di ricerca.

## 4. Euristiche

| Repository | File e funzioni | Licenza | Cosa se ne ricava |
|:--|:--|:--|:--|
| telegram-offer-monitor | `src/parser.py`: `NOISE_CONTEXT_RX` (26), `PRICE_MARKER_RX` (34), `INSTALLMENT_BLOCK_RX` (23), `_extract_price` (130) | MIT, nota di copyright se si copia | Scartare gli importi preceduti da «risparmi», «sconto di», «rate», «spedizione». Il porting letterale perde prezzi (scarta l'intera riga), quindi si scrive a livello di importo (sotto, nessun codice copiato) |
| telegram-offer-monitor | `src/dedup.py`: `price_band` (27), `offer_key` (42), `Deduplicator.evaluate` (59) | MIT | Non copiare le bande: larghe il 2%, due prezzi distanti l'1% finiscono in bande diverse nel 50% dei casi. Tenere solo l'idea che un ribasso sullo stesso ASIN è una riga nuova |
| telegram-offer-monitor | `src/dedup.py`: `detect_store`, `STORE_BY_DOMAIN` (51, 106) | MIT | Solo l'idea del filtro «negozio». Si ricava dall'host del link con la mappa di `links.py` riga 22 (`RETAIL_HOST_RE`), una decina di righe JS |
| salekhoj | `scrapers/gate.py` (3.787 byte, stdlib), `.github/workflows/refresh.yml` | MIT | Gate anti-collasso del deploy. Va ricalibrato: confronto sulle offerte nella finestra di retention e sui canali con almeno un messaggio parsato rispetto all'ultimo giro buono, non su un conteggio a 15 minuti. Dopo la dashboard |
| ClearURLs/Rules | `data.minify.json` (37 KB) | LGPL-3.0, testo accanto al file | Riserva, non sostituzione (sotto) |
| price-parser | `price_parser/parser.py`: `extract_price_text` (284), `get_decimal_separator` (378), `parse_number` (401); `tests/test_price_parsing.py` | BSD-3-Clause, testo completo e «Copyright (c) Scrapinghub» se si copia | Solo il corpus di test. Il caso «249€99 invece di 399€» fallisce anche in price-parser, perché il ramo dell'euro come decimale scatta con un solo «€» |

Filtro del rumore da inserire in `extract_prices`, applicato alla finestra di 30 caratteri prima di ogni importo (la stessa di `OLD_HINT_RE`), scartando l'importo se combacia:

```python
NOISE_BEFORE = re.compile(
    r"\b(?:risparmi\w*|sconto\s+di|di\s+sconto|cashback(?:\s+di)?|buono\s+(?:da|di)|rate?|rata"
    r"|spedizion[ei](?!\s+(?:gratuita|gratis|inclusa|prime)))\s*(?:di|da|:|\+)?\s*$", re.I)
```

Test da aggiungere: «59,90€ + spedizione 4,99€» dà 59,90, «Sconto di 30€ ... Prezzo finale 199€» dà 199, «59,90€ spedizione gratuita» dà 59,90, più il messaggio reale mttcina 3190, che oggi esce con prezzo 2,00 e sconto 100%. Sui 235 messaggi reali letti cambia solo quest'ultimo esito e non ci sono regressioni. Va fatto prima della dashboard, perché un prezzo 2,00 sporca i filtri min e max. Nessun repository trovato spezza i post riepilogo con più prodotti (17 messaggi su 235 con 3 o più importi distinti), che vanno risolti in casa.

Sul ribasso di una chiave già vista si sceglie l'opzione A, nuova riga. L'opzione B (aggiornare la riga esistente) è scartata, perché `fetch.py` riga 149 notifica solo le offerte nuove e un ribasso sotto soglia su un ASIN già visto non farebbe scattare la regola. La chiave non contiene banda di prezzo né coupon. Il prezzo si confronta con tolleranza con quello dell'ultima riga della stessa chiave e non si crea una riga se il prezzo estratto è None.

ClearURLs non sostituisce `TRACKING_EXACT`, `TRACKING_PREFIX` e `AFFILIATE_EXACT`. Dei 20 nomi di `AFFILIATE_EXACT` ne copre solo `tag`. Su 588 link esterni reali gli unici provider toccati sono amazon e aliexpress, già gestiti, con 0 redirezioni scattate. Va tenuto per `dedupe_key` e la risoluzione dei link awin, tradedoubler, effiliation, admitad, quando compaiono (oggi 0). Si scarica `https://rules2.clearurls.xyz/data.minify.json`, che omette le chiavi vuote (l'applicatore usa `.get` con default), e si verifica lo sha256 con `https://rules2.clearurls.xyz/rules.minify.hash`. Le `redirections` tolgono il link affiliato del canale, quindi mai sul link mostrato.

Per «249€99» basta estendere `PRICE_RE` e `parse_amount` con un'alternativa scritta in casa, che non richiede nessun avviso di licenza: `(?P<post>\d{1,5})€(?P<cents>\d{2})(?!\d)`. Il formato compare 0 volte nei 234 messaggi Telegram letti da chi ha fatto la ricerca.

## 5. Alternative che sostituirebbero la dashboard

Nessuna la sostituisce.

| Alternativa | Giudizio | Motivo |
|:--|:--|:--|
| Datasette Lite | No come dashboard, sì come link secondario | Nessuna regex: SQLite non ha `REGEXP` e i plugin JS non girano in Lite (issue [#8](https://github.com/simonw/datasette-lite/issues/8)). UI a tabella generica a 16 colonne, senza card. A ogni visita scarica Pyodide (wasm da 10,1 MB) e le ruote Python da PyPI con dipendenze transitive non fissate. Il sito live oggi non parte: `platformdirs` 4.14.0 del 28.10.2026 dà `ImportError: cannot import name 'geteuid' from 'os'` |
| sql.js 1.15.2 | No come dashboard. Livello dati solo se servono JOIN o statistiche | Il vantaggio principale (finestra del periodo oltre i feed) è già coperto da `dashboard.json`. Non ha FTS5 (ha FTS3 e FTS4), serve una tabella `cartelle(canale, cartella)` e il DB va pubblicato con `VACUUM INTO` |
| @sqlite.org/sqlite-wasm | No | Apre solo DB non WAL, mentre `store.py` riga 107 imposta WAL. FTS5 non copre la regex. Pesa circa 140 KB in più di sql.js |
| Tabulator 6.7.1 | No come vista principale | 104 KB gzip, layout a tabella poco adatto a card con immagine e a badge, regex built-in senza `try/catch`. Va bene come vista densa opzionale |
| FreshRSS | No | PHP più database, nessun operatore numerico per prezzo e sconto, non pubblicabile su Pages |

Datasette Lite resta utile come link «esplora in SQL» da una copia self-hosted. Servono i tre file `index.html`, `webworker.js` e `app.css` (Apache-2.0), con le righe 33 e 34 di Plausible tolte. Servono poi i pin `datasette==0.65.5` e `platformdirs<4.14` in `webworker.js`, fissando anche le altre dipendenze (provato solo il pin di `platformdirs`). Il DB si pubblica nell'artifact Pages con `sqlite3 var/offerte.sqlite "VACUUM INTO 'var/feeds/offerte.db'"`. Il link porta i filtri nel frammento, provato su DB sintetico: `#/offerte/offers?price__gte=10&price__lte=100&discount__gte=30&coupon__notblank=1&_sort_desc=discount`. Il `http.server` locale non emette CORS, quindi funziona solo la copia self-hosted sulla stessa origine.

Se un giorno servono JOIN su `posts` e `matches` o statistiche per canale, il livello dati diventa sql.js da `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.15.2/sql-wasm.js` (`integrity="sha384-xT9kd8BCaJ6QIR2xaUGPFFe0H6o0Vzj8ANZG2XVd0UtJ/Xu3r3aTaB0h7tzXD0pE"`, il `.wasm` non è coperto da SRI). La regex si registra con `db.create_function('regexp', (re, s) => new RegExp(re, 'i').test(s ?? '') ? 1 : 0)`, compilando la RegExp una volta e con `try/catch`. Provata una query con regex, prezzo, sconto, coupon, periodo e canale (`json_each`): 7 righe uguali al riferimento Python, in 140-170 ms a freddo.

## 6. Scartati

| Nome | Motivo |
|:--|:--|
| Fuse.js 7.5.0 | 27-76 ms a query su 6000 documenti, 594 risultati contro 33-66 delle altre su 3 parole, dalla 7.5.0 su CDN solo ESM |
| FlexSearch 0.8.212 | 51 KB, circa 11 MB di heap, 120 ms di indicizzazione, vantaggio inutile a 6000 elementi |
| Lunr 2.3.9 | Ultima release 2020, nessun vantaggio su MiniSearch |
| List.js 2.3.1 | Ferma al 2021, solo sottostringa, lavora sul DOM |
| Grid.js 6.2.0 | Marzo 2024, niente rendering virtuale né filtri a intervallo |
| petite-vue 0.4.1 | Ferma al 2022, Alpine la sostituisce |
| htmx | Presuppone un server che risponde con HTML |
| Preact 11.1.0 | Su jsDelivr solo ESM, e Alpine basta |
| Bulma | 678 KB raw, 65 KB gzip, non classless |
| New.css | Ultima release maggio 2020, nessun componente utile |
| blades | Successore di Pico ancora in beta, release ogni uno o due giorni |
| Tabler webfont | woff2 da 509 KB |
| lucide.min.js | 463 KB raw, 110 KB gzip, contiene tutte le icone |
| Font e sprite di Bootstrap Icons | Font 87 KB di CSS più 134 KB di woff2, sprite da 1,1 MB e `<use>` cross-origin non funziona |
| DuckDB-Wasm | `duckdb-eh.wasm` da 35,9 MB |
| sql.js-httpvfs | Pacchetto npm fermo a settembre 2022, le range request servono per DB di decine di MB |
| [osmosfeed](https://github.com/osmoscraft/osmosfeed) | Ultima release giugno 2022, solo elenco di articoli senza filtri |
| [Glance](https://github.com/glanceapp/glance) | AGPL-3.0, processo server Go, nessun export statico |
| [FeedMe](https://github.com/Seanium/FeedMe) | React, Vite e pnpm: ha un build step |
| [llun/feeds](https://github.com/llun/feeds) | Next.js e nessuna licenza dichiarata |
| [gereader-homepage](https://github.com/gereader/gereader-homepage) | Filtri solo in `localStorage`, 108 articoli, testo del feed in `innerHTML` |
| [jackydangelo/staticfeed](https://github.com/jackydangelo/staticfeed) | Nessun JS lato client, solo l'idea di `actions/cache` più ETag, poco utile con `t.me/s` (deduzione) |
| githubocto/flat, flat-ui, flat-viewer, flatgithub.com | I tre repo sono archiviati, il sito non è raggiungibile (certificato non corrispondente) |
| maximevaillancourt/json-feed-viewer | Server Express con Redis, fermo al 2022 |
| [Fraidycat](https://fraidyc.at/) | Estensione del browser, ultime versioni 2020 e 2021 |
| [tinyfeed](https://github.com/TheBigRoomXXL/tinyfeed) | L'input è un file di URL e non un feed locale, template predefinito con solo titolo, data e dominio, filtri solo proposti (issue #34) |
| [Huginn](https://github.com/huginn/huginn) | Server Ruby con MySQL interno, advisory critiche tra agosto e settembre 2026 (GHSA-p347-7m45-694r), JSON proprietario e non JSON Feed |
| [simonw/git-history](https://github.com/simonw/git-history) | Legge solo la storia git di JSON o CSV: 96 commit al giorno, circa 35.000 l'anno. Issue aperte #56 (float sempre cambiati) e #53 (item rimossi non tracciati) |
| urlwatch | BSD-3-Clause e attivo, ma nessun reporter RSS o Atom né webhook generico |
| Feedbridge di dewey | Ultimo push maggio 2021, README «work in progress» |
| [PriceBuddy](https://github.com/jez500/pricebuddy) | GPL-3.0, richiede app, MySQL e servizio scraper, nessuna uscita RSS |
| Plugin Amazon di changedetection.io | Deprecato dal 2024-08 |
| Bridge Pepper e TelegramBridge di RSS-Bridge | Pepper.it chiuso il 14.08.2025, TelegramBridge duplica la fonte `telegram` |
| python-amazon-paapi, albertopasqualetto/amazon-deals-telegram-bot | Ripetono ciò che `links.py` fa già |
| kauavnogueira/Telegram-Deals-Radar, thgoo/deals-platform, VanshRupeja/telegram-deal-forwarder, alexandrepereira23/dealbot, HasData/ecommerce-price-scraper | Nessun file di licenza |
| VPariz/bot-promocoes-telegram | MIT, ma l'estrazione è affidata a LLM esterni (Groq, DeepSeek) |
| Piero24/TelegramBot-AmazonOffers | Dichiara Apache-2.0, ma le intestazioni dei file vietano la redistribuzione |
| Unalix | Porting Python di ClearURLs, archiviato dal 2022 |
| [mpchadwick/tracking-query-params-registry](https://github.com/mpchadwick/tracking-query-params-registry) | 0 parametri recuperati su 588 link reali. I 16 non coperti sono HubSpot, Klaviyo e simili, e nomi generici (`cid`, `sid`, `kb`) fonderebbero prodotti diversi |
| Datasette Lite come prototipo senza codice sul JSON Feed | `?json=` importa `_offerte` e `tags` come testo JSON, quindi niente filtri numerici su prezzo e sconto, né regex, e il sito live oggi non parte (sezione 5) |

DataTables non è stato valutato.

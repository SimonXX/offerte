# offerte

Aggrega offerte da fonti pubbliche e produce feed RSS 2.0 e JSON Feed per cartella e per regola di alert. La fonte
principale sono i canali Telegram pubblici, letti dalle pagine di anteprima `https://t.me/s/<canale>` (nessun account,
nessun bot, nessuna API); accanto ci sono feed RSS e Atom, pagine HTML con selettori CSS, script esterni e actor Apify.
Stato in SQLite, configurazione in YAML, servizio utente systemd ogni dieci minuti, server HTTP locale su
`127.0.0.1:8099`.

Per ogni messaggio estrae id, data, testo, link (redirect degli accorciatori risolti, parametri di tracciamento tolti,
tag affiliate conservati), immagine, canale; dal testo ricava prezzo, prezzo barrato, sconto, coupon e nome del prodotto.
La stessa offerta pubblicata da più canali, o più volte dallo stesso, è una sola voce con l'elenco dei canali; un
ripost con prezzo inferiore di almeno il 5% a quello già salvato è una voce nuova, così il ribasso scatta come
offerta nuova.

## Requisiti

Python 3.12 e [uv](https://docs.astral.sh/uv/). Su Fedora: `sudo dnf install uv`.

## Installazione

```sh
cd ~/Projects/repos/offerte
uv sync                      # crea .venv con httpx, selectolax, pyyaml, feedgen
$EDITOR config.yaml          # canali, cartelle, regole
cp .env.example .env         # solo se vuoi le notifiche Telegram
uv run offerte fetch         # primo giro: legge lo storico, scrive var/offerte.sqlite e var/feeds/
uv run offerte serve         # http://127.0.0.1:8099/ elenca i feed
```

`uv run offerte …` e `.venv/bin/offerte …` sono equivalenti. La config si cerca in `--config`, poi in `$OFFERTE_CONFIG`,
poi in `./config.yaml`; i percorsi relativi nella config partono dalla cartella della config stessa.

## Configurazione

Estratto di `config.yaml`, copiato dal file del repository, che ha 23 canali verificati divisi in
`informatica`, `casa`, `cina` e `raffica`:

```yaml
parametri:
  intervallo_cortesia: 3          # secondi fra una richiesta a t.me e la successiva
  user_agent: "Mozilla/5.0 (X11; Linux x86_64) offerte/0.1"
  pagine_storico: 3               # pagine di t.me/s (circa 20 messaggi l'una) lette al primo avvio di un canale
  var_dir: var                    # database, feed e log
  feed_base_url: http://127.0.0.1:8099   # base dei link "self" nei feed: se li esponi altrove, cambiala
  feed_giorni: 14                 # finestra temporale dei feed
  feed_max_elementi: 200
  giorni_dedupe: 7                # la stessa offerta ripubblicata oltre questo intervallo è un'offerta nuova
  notifica_max_ore: 24            # non notifica offerte più vecchie di così (evita raffiche al primo avvio)
  giorni_ritenzione: 90           # le offerte più vecchie si eliminano a fine giro (0 = mai)
  dashboard: true                 # scrive dashboard.json e la pagina dei filtri in var/feeds/
  dashboard_regole: true          # espone parole e soglie delle regole nella dashboard (preset e "Crea regola")
  dashboard_max_offerte: 10000    # tetto delle offerte in dashboard.json; oltre, si tengono le più recenti
  # dashboard_giorni: 60          # finestra della dashboard se deve guardare più indietro dei feed
  # grafico_prezzi: ""            # vuoto = niente grafico dello storico prezzi nelle schede

canali:
  - {nome: mttvideo,            cartella: informatica}               # MoreThanHardware - Offerte PC, 45,9K iscritti, ~4/g
  - {nome: erroridiprezzo,              cartella: casa}              # Errori di Prezzo, ~5/g
  - {nome: rafficaffari,        cartella: raffica, pagine: 25}       # RafficAffari, Offerte Bomba ed Errori di Prezzo, ~80/g

regole:
  - nome: ssd-sotto-60
    parole: ["ssd", "nvme", '/\b[12]\s?tb\b/']   # parola intera, oppure regex fra barre
    prezzo_max: 60
    canali: [informatica]            # nomi di canale o di cartella; assente = tutti
    notify: true
  - nome: apple-watch-sotto-250
    parole: ["apple watch", '/\bwatch\s*(se|series|ultra)\b/']
    escludi: [cinturino, cinturini, cover, pellicola, vetro, caricatore, cavo, supporto, custodia]
    prezzo_max: 250
    notify: true
  - nome: errori-di-prezzo
    parole: ["errore di prezzo", '/sconto:?\s*[7-9]\d\s?%/']
    canali: [erroridiprezzo, erroridiprezzo_offertedalweb, rafficaffari]
    notify: false
```

Una regola scatta se almeno una parola compare nel testo (con `tutte: true` devono comparire tutte). Una parola
semplice è cercata come parola intera, senza distinzione di maiuscole; una voce fra barre (`'/…/'`) è una regex
Python, sempre case-insensitive. `escludi` elenca parole che annullano la corrispondenza: è il modo per tenere fuori
cinturini e cover quando si cerca un Apple Watch. `prezzo_max` e `prezzo_min` si applicano al prezzo attuale
estratto: un'offerta senza prezzo non passa un filtro di prezzo. `sconto_min` è la percentuale minima di sconto e
`solo_coupon: true` tiene solo le offerte con un codice: un'offerta senza sconto, o senza coupon, non li passa.
`canali` accetta nomi di canale o di cartella; assente, la regola vale per tutti.

Le parole sono facoltative se c'è almeno un altro criterio (`prezzo_min`, `prezzo_max`, `sconto_min`,
`solo_coupon`, `canali`): «tutto quello che sta sotto 20 euro» è una regola valida. `escludi` da solo non basta, e
una regola senza parole non può avere `notify: true`, altrimenti notificherebbe a raffica. Le regole si valutano a ogni giro sulle offerte della finestra `feed_giorni`, quindi
una regola nuova popola subito il proprio feed con il pregresso; le notifiche partono solo per le offerte nuove del giro.

## Fonti

Ogni voce di `canali:` è una fonte Telegram; `fonti:` aggiunge gli altri tipi. Tutte condividono `nome`, `cartella`,
`attivo` e `ogni` (minuti fra una lettura e la successiva; assente o 0 = a ogni giro). Il resto della pipeline,
estrazione prezzi, dedupe, regole, feed e notifiche, è lo stesso per tutte.

| tipo | opzioni | cosa fa |
|:--|:--|:--|
| `telegram` | `canale` (default: il nome), `pagine` | anteprima pubblica `t.me/s/<canale>`, incrementale per id |
| `rss` | `url`, `url_env`, `massimo`, `scarta_host` | RSS 2.0, RSS 1.0 o Atom; testo, link, immagine e prezzi barrati dalla descrizione |
| `html` | `url`, `elemento`, `campi`, `massimo` | una pagina, un selettore CSS per ogni offerta, selettori per i campi (`css`, `css@attr`, `@attr`) |
| `comando` | `comando`, `cwd`, `timeout` | esegue uno script qualsiasi che stampa record JSON (una riga per record o un array) |
| `apify` | `actor`, `modo`, `input`, `campi`, `token`, `timeout`, `massimo`, `memoria` | actor dello store Apify via REST; `modo: sync` lo lancia, `modo: ultimo` legge l'ultima esecuzione riuscita |
| `modulo:Classe` | quelle della classe | una sottoclasse di `offerte.sources.base.Source` importabile, o un entry point `offerte.fonti` |

Campi dei record per `comando` e `apify` (accettati in italiano o in inglese): `id`, `titolo`, `testo`, `link`, `links`,
`immagine`, `prezzo`, `prezzo_barrato`, `data`, `permalink`. Basta `testo` o `titolo`; il resto, se manca, si ricava dal
testo come per Telegram. Per `apify` la mappatura `campi` traduce i nomi dell'actor, con percorsi puntati e alternative
(`prezzo: "price.value|price"`); il token sta in `.env` come `APIFY_TOKEN` e `ogni` è obbligatorio per non spendere
credito a ogni giro. Uno script per `comando`, in qualunque linguaggio, riceve la variabile `OFFERTE_FONTE` e stampa:

```
{"id": "a1", "titolo": "Robot aspirapolvere", "link": "https://…", "prezzo": "199,00 €", "data": "2026-10-27T10:00:00Z"}
```

`offerte prova <fonte>` esegue una fonte senza salvare e mostra cosa produce; `offerte fonti` elenca stato e ultimo
fetch di tutte. Esempi di configurazione per ogni tipo sono commentati in `config.yaml`.

### Fonti pronte

Tre strumenti open source che producono un feed RSS o Atom e che la fonte `rss` legge senza scrivere codice.
Girano in locale su `127.0.0.1`, che GitHub Actions non raggiunge: le loro voci vanno in `config.locale.yaml`,
non tracciato (`.gitignore`), scelto con `-c` oppure con `OFFERTE_CONFIG`.

```sh
uv run offerte -c config.locale.yaml fetch
```

Per il servizio systemd basta una riga in `systemd/offerte-fetch.service`:

```ini
[Service]
Environment=OFFERTE_CONFIG=@PROJECT_DIR@/config.locale.yaml
```

`config.locale.yaml` contiene solo le fonti locali e regole **senza** `notify`: le notifiche restano in una sola
installazione, quella su Actions, altrimenti ogni offerta arriva due volte. Gli stessi blocchi stanno commentati
in `config.yaml`.

La fonte `rss` ha due opzioni pensate per questi strumenti. `url_env: NOME` legge l'URL del feed da una variabile
d'ambiente a ogni giro, invece che dalla config: serve quando l'URL contiene un token, e i log e gli errori
mostrano il nome della fonte al posto dell'URL. `scarta_host: esempio.it` toglia dai link dell'offerta quelli
verso quell'host e i suoi sottodomini, e lascia vuoto il permalink che punta lì: serve quando l'indirizzo dello
strumento è esso stesso il segreto. `url` e `url_env` si escludono a vicenda e uno dei due è obbligatorio.

#### changedetection.io, prezzi di pagine prodotto

**Non provata dal vivo**: la verifica richiede un cambio di prezzo reale su una pagina seguita, che in questa
sessione non è stato possibile osservare. La configurazione qui sotto viene dalla lettura della documentazione e
del codice dello strumento, non da un giro completo.

Serve per le pagine prodotto di negozi che espongono JSON-LD, OpenGraph o microdata, una per watch. Non serve per
Amazon.it: il plugin Amazon è deprecato dal 2024-08 e la pagina non espone JSON-LD. Non serve per i siti che hanno
già un feed, né per quelli che la fonte `html` copre con un selettore CSS.

```sh
podman run -d --name changedetection -p 127.0.0.1:5000:5000 -v changedetection-data:/datastore \
  ghcr.io/dgtlmoon/changedetection.io
```

Nello strumento: per ogni prodotto un watch di tipo «Re-stock & Price detection for single product pages», tutti
con il tag `offerte`; per «avvisami sotto X» si imposta solo il minimo, perché un prezzo dentro l'intervallo
minimo-massimo viene soppresso. In Settings, RSS, `rss_template_override` deve mettere il prezzo seguito da `€`,
altrimenti l'estrattore non lo riconosce (il testo predefinito, «In Stock: True - Price: 12.99», non ha valuta):

```
{{watch_label}}
{{restock.price}} €{% if restock.previous_price %} invece di {{restock.previous_price}} €{% endif %}
{{watch_open_url}}
```

Si usa il feed per tag, non quello per singolo watch: quello per watch risponde 400 finché ci sono meno di due
istantanee. L'URL sta in una variabile perché contiene il token:

```sh
export CDIO_FEED="http://127.0.0.1:5000/rss/tag/<uuid-del-tag-offerte>?token=<rss_access_token>"
```

```yaml
fonti:
  - nome: cdio-negozi
    tipo: rss
    cartella: informatica
    url_env: CDIO_FEED
    ogni: 30
```

#### RSS-Bridge, siti senza feed

Serve solo per un sito italiano senza feed che la fonte `html` non copre, per esempio perché i dati sono in un
JSON incorporato o servono espressioni XPath. Non va usato per Amazon.it (prezzo vuoto sui domini nazionali), per
eBay (403), per Idealo.it né per Pepper, chiuso nel 2025. Va chiesto il formato Atom o Mrss, non Json, che è
JSON Feed e la fonte `rss` non lo legge. `ogni: 60` rispetta la cache dei bridge; il timeout predefinito è di tre
secondi e va alzato per i siti lenti.

```sh
podman run -d --name rss-bridge -p 127.0.0.1:3000:80 docker.io/rssbridge/rss-bridge:latest
```

```yaml
fonti:
  - nome: rssbridge-sito
    tipo: rss
    cartella: casa
    url: http://127.0.0.1:3000/?action=display&bridge=<NomeBridge>&format=Atom
    ogni: 60
```

#### kill-the-newsletter, coupon riservati agli iscritti

Serve per le newsletter dei negozi, quando il coupon arriva solo per posta. Il servizio ospitato
(`kill-the-newsletter.com`) trasforma un indirizzo email in un feed Atom. Non serve per nient'altro: il tetto è di
512 KiB per feed e le voci oltre il mese si cancellano.

L'identificativo del feed coincide con la parte locale dell'indirizzo email e compare nei link di ogni voce,
quindi finirebbe nei feed pubblicati su Pages: per questo `url_env` lo tiene fuori dalla config e `scarta_host` lo
toglie dai link delle offerte.

```sh
export KTN_FEED="https://kill-the-newsletter.com/feeds/<identificativo>/entries.xml"
```

```yaml
fonti:
  - nome: newsletter-coupon
    tipo: rss
    cartella: casa
    url_env: KTN_FEED
    scarta_host: kill-the-newsletter.com
    ogni: 60
```

## Comandi

| comando | cosa fa |
|:--|:--|
| `offerte fetch [--fonte X] [--storico N] [--senza-notifiche]` | legge le fonti, aggiorna il database, applica le regole, invia le notifiche, rigenera i feed |
| `offerte feed` | rigenera feed, OPML e dashboard dal database, senza leggere le fonti |
| `offerte fonti` | fonti configurate con tipo, cartella, intervallo, ultimo fetch e stato |
| `offerte pulisci [--giorni N]` | elimina le offerte più vecchie di N giorni e compatta il database (a fine `fetch` avviene da sé, senza compattare) |
| `offerte prova <fonte> [--limite N]` | esegue una fonte senza salvare e mostra gli elementi prodotti |
| `offerte serve [--host H] [--port P]` | serve `var/feeds/` via HTTP (default `127.0.0.1:8099`) |
| `offerte search <parola> [--limite N]` | cerca nel testo e nel titolo delle offerte salvate |
| `offerte storico <termine> [--canali …] [--pagine N]` | cerca un prodotto nell'archivio dei canali, anche di mesi o anni fa, e mostra l'andamento dei prezzi |
| `offerte stats [--giorni N]` | offerte al giorno per canale e regole scattate |
| `offerte filtra [parole…] [--prezzo-max X] [--prezzo-min X] [--sconto-min N] [--solo-coupon] [--escludi …] [--tutte] [--canali …]` | prova una regola al volo sulle offerte salvate, per tararla prima di metterla in config |

Esempio: `offerte filtra "apple watch" --prezzo-max 250 --escludi cinturino cover`.
Opzioni globali: `--config` (`-c`), `-v` (debug), `--version`. Vanno scritte prima del sottocomando
(`offerte -c altra.yaml fetch`, non `offerte fetch -c altra.yaml`). Due `fetch` non girano insieme
(lock su `var/fetch.lock`).
Il log va su stderr e su `var/offerte.log` (rotazione a 2 MB, cinque copie).

## Feed

In `var/feeds/`, serviti dal server:

```
http://127.0.0.1:8099/                          indice
http://127.0.0.1:8099/dashboard.html            dashboard dei filtri
http://127.0.0.1:8099/feeds.opml                tutti i feed in un file, da importare nel lettore
http://127.0.0.1:8099/cartella/informatica.xml  RSS 2.0 della cartella
http://127.0.0.1:8099/cartella/informatica.json JSON Feed della cartella
http://127.0.0.1:8099/regola/ssd-sotto-60.xml   RSS 2.0 della regola
http://127.0.0.1:8099/regola/ssd-sotto-60.json  JSON Feed della regola
```

Ogni elemento ha titolo `prodotto, prezzo (-sconto%)`, descrizione con immagine, testo originale, prezzo barrato,
coupon, canali di provenienza e link al messaggio, link diretto all'offerta, data del primo post. Il JSON Feed porta
gli stessi campi anche strutturati in `_offerte`.

### Dashboard

`http://127.0.0.1:8099/dashboard.html` (oppure `https://<utente>.github.io/<repo>/dashboard.html` su Pages) è una
pagina statica che filtra tutte le offerte della finestra `feed_giorni`: parole e regex, escludi, prezzo, sconto
minimo, cartella, canale, periodo, solo con coupon, sei ordinamenti. HTML, CSS e JavaScript scritti a mano, nessuna
libreria, nessuna CDN, nessun passo di build: i quattro file stanno in `src/offerte/static/` e vengono copiati in
`var/feeds/` a ogni giro insieme a `dashboard.json`.

Da telefono, sulla stessa rete: `uv run offerte serve --host 192.168.x.y` e poi `http://192.168.x.y:8099/dashboard.html`
dal telefono (solo su rete fidata). Da `file://` i dati non si caricano: il browser blocca il fetch, e la pagina lo
dice.

Lo stato dei filtri sta nella query string, quindi un filtro si salva nei preferiti e si manda a qualcuno con «Copia
link»:

| parametro | valore |
|:--|:--|
| `q` | una voce di Parole, ripetibile |
| `no` | una voce di Escludi, ripetibile |
| `tutte` | `1` se servono tutte le parole |
| `pmin`, `pmax` | prezzo minimo e massimo, con il punto decimale |
| `smin` | sconto minimo in percentuale, da 1 a 99 |
| `cart` | cartelle separate da virgola |
| `can` | canali separati da virgola, in unione con le cartelle |
| `per` | `<numero>h` o `<numero>g`, per esempio `12h` o `30g` |
| `cp` | `1` per le sole offerte con coupon |
| `ord` | `data-desc data-asc prezzo-asc prezzo-desc sconto-desc sconto-asc` |

Esempio: `dashboard.html?q=apple%20watch&no=cinturino&pmax=250&per=7g&ord=prezzo-asc`.

Le parole si scrivono una per riga e valgono le stesse regole della config: parola intera senza distinzione di
maiuscole, oppure una regex fra barre. Le regex sono scritte in sintassi Python e tradotte in JavaScript: `\b`, `\w`,
`\d`, `\A`, `\Z`, `(?P<nome>…)` e `(?i)` iniziale funzionano; gruppi possessivi, gruppi atomici e le classi negate
dentro parentesi quadre (`[\W]`) no, e la pagina lo segnala sotto il campo. Su un browser senza lookbehind (Safari
prima di 16.4) la regex si compila senza regole Unicode e `\b` vale solo per le lettere ASCII, con un avviso.

«Crea regola» prende i filtri correnti e produce il blocco YAML da incollare sotto `regole:` in `config.yaml`: le
soglie di prezzo e sconto, il coupon, i canali e le parole, con la quotatura giusta. Il periodo non si esporta,
perché una regola non ha un periodo. I pulsanti in cima sono le regole già in config: un clic ne riapplica i filtri.

Il menu **Periodo** non è una lista fissa: si costruisce dalla finestra dei dati. La prima voce dice quanto è
larga («Tutto il periodo (14 giorni)») e i gradini arrivano fino a lì, quindi alzando la finestra compaiono da soli
«Ultimi 14 giorni», «Ultimi 30 giorni» e così via. Un periodo scritto a mano nell'indirizzo (`?per=45g`) vale
comunque, anche se non è fra i gradini.

La finestra della dashboard è staccata da quella dei feed. `feed_giorni` governa RSS e JSON Feed e la valutazione
delle regole a ogni giro; `dashboard_giorni`, se lo imposti, governa solo la pagina. Serve perché il database
conserva `giorni_ritenzione` giorni (90 di default) mentre i feed ne mostrano 14: con `dashboard_giorni: 60` la
pagina filtra su due mesi senza allargare i feed né far rivalutare le regole su due mesi di offerte a ogni giro.
Il prezzo è la dimensione del file, che cresce in proporzione: circa 1 KB per offerta.

`offerte feed` rigenera feed, OPML e `dashboard.json` dal database senza toccare la rete: serve per provare la pagina
dopo aver cambiato una regola. Con `dashboard: false` nei parametri la pagina e i suoi file non si scrivono (e si
cancellano se c'erano); con `dashboard_regole: false` i preset e «Crea regola» restano senza regole, e parole e
soglie non finiscono nel JSON.

**Cosa espone `dashboard.json`.** Contiene tutte le offerte della finestra, con il testo intero del messaggio e il
link affiliato: più di quanto espongano i feed, tagliati a `feed_max_elementi`. Se `dashboard_regole` è vero contiene
anche nome, parole, esclusioni e soglie di ogni regola. Su GitHub Pages quel file è pubblico come i feed: chi ha
l'URL del repository lo legge. Se una regola contiene qualcosa che non vuoi pubblicare, metti `dashboard_regole:
false`; se non vuoi pubblicare il corpus, `dashboard: false`.

Dimensioni misurate il 29.10.2026 su un giro reale di 17 canali: 275 offerte in 14 giorni fanno 279 KB in chiaro e
129 KB compressi, cioè circa 1.010 byte per offerta (buona parte è l'URL dell'immagine, firmato e incomprimibile).
La proiezione a regime, 5.000-6.500 offerte, è 5-6,5 MB in chiaro e 2,5-3 MB compressi: Pages comprime i `.json`,
il server locale no.

**Storico dei prezzi, a richiesta.** Ogni scheda di un prodotto Amazon ha un blocco «Storico prezzi» che,
quando lo apri, mostra il grafico dei dodici mesi dal servizio indicato in `grafico_prezzi` (di default quello
gratuito di Keepa). Si carica solo all'apertura, non al disegno delle schede, quindi finché non clicchi nessuna
richiesta parte. Sappi però che aprirlo dice a quel servizio quale prodotto stai guardando; la pagina manda
`no-referrer`, quindi non impara da dove. Con `grafico_prezzi: ""` nei parametri il blocco sparisce del tutto.

Per andare più indietro dei dati raccolti c'è `offerte storico`, che interroga la ricerca interna dei canali
invece del database:

```sh
uv run offerte storico "dyson v15" --canali raffica informatica
```

Pesca anche messaggi di anni fa, che la raccolta incrementale non ha mai scaricato (in una prova reale ha
trovato sedici messaggi dal novembre 2021), e stampa data, prezzo, canale e link di ognuno, più minimo, massimo
e ultimo prezzo visto. Costa una richiesta per canale, quindi si usa su un prodotto per volta, non di default.

### Miniflux

Miniflux sulla stessa macchina: Feeds, Add feed, URL `http://127.0.0.1:8099/cartella/informatica.xml`. Se Miniflux
gira in un container, `127.0.0.1` è il container stesso: avvialo con `--network=host`, oppure esponi il server su un
indirizzo raggiungibile (`offerte serve --host 192.168.x.y`, solo su rete fidata) e usa quell'indirizzo.

### Inoreader

Inoreader legge i feed dai propri server, quindi `127.0.0.1` non è raggiungibile. Serve un URL pubblico: un reverse
proxy (Caddy, nginx) con HTTPS davanti a `127.0.0.1:8099`, oppure un tunnel (Cloudflare Tunnel, Tailscale Funnel).
Imposta `feed_base_url` su quell'URL perché i link `self` dei feed siano coerenti, poi in Inoreader: Add subscription,
incolla l'URL del feed. I feed non contengono dati personali, ma un URL pubblico resta indovinabile: meglio con un
percorso non banale o con autenticazione basic sul proxy (Inoreader accetta `https://utente:password@host/…`).

## Servizio systemd (utente)

Le unit stanno in `systemd/`. Lo script le copia in `~/.config/systemd/user/` con il percorso del progetto e ricarica
systemd; non abilita nulla.

```sh
./systemd/installa.sh
systemctl --user enable --now offerte-fetch.timer offerte-serve.service
systemctl --user list-timers offerte-fetch.timer
journalctl --user -u offerte-fetch.service -n 50
loginctl enable-linger "$USER"     # perché giri anche senza sessione aperta
```

`offerte-fetch.service` (oneshot, lanciato dal timer):

```ini
[Unit]
Description=Offerte: raccolta dai canali Telegram
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=@PROJECT_DIR@
ExecStart=@PROJECT_DIR@/.venv/bin/offerte fetch
TimeoutStartSec=15min
Nice=10
```

`offerte-fetch.timer`:

```ini
[Unit]
Description=Offerte: raccolta ogni 10 minuti

[Timer]
OnCalendar=*:0/10
RandomizedDelaySec=60
Persistent=true

[Install]
WantedBy=timers.target
```

`offerte-serve.service`:

```ini
[Unit]
Description=Offerte: server HTTP dei feed su 127.0.0.1:8099
After=network.target

[Service]
WorkingDirectory=@PROJECT_DIR@
ExecStart=@PROJECT_DIR@/.venv/bin/offerte serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

## Deploy a costo zero su GitHub

Il workflow `.github/workflows/offerte.yml` esegue la raccolta ogni 15 minuti su GitHub Actions e pubblica `var/feeds/`
su GitHub Pages: i feed hanno un'URL pubblica, leggibile da Inoreader, senza server. Sui repository pubblici i runner
standard non costano nulla; lo stato SQLite vive su un branch orfano `data` con un solo commit, riscritto a ogni giro.

1. Pubblica il repository su GitHub, pubblico (Pages e minuti illimitati sul piano gratuito valgono solo lì).
2. Settings, Pages, Source: `GitHub Actions`.
3. Settings, Secrets and variables, Actions: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` se vuoi le notifiche,
   `APIFY_TOKEN` se usi fonti Apify. Senza segreti il workflow gira lo stesso.
4. Actions, workflow `offerte`, `Run workflow` per il primo giro; poi il cron fa da solo.
5. I feed sono su `https://<utente>.github.io/<repo>/`, ad esempio
   `https://<utente>.github.io/<repo>/cartella/casa.xml`: in Inoreader, Add subscription, incolla l'URL.

`feed_base_url` viene impostata dal workflow tramite la variabile `OFFERTE_FEED_BASE_URL`, che ha la precedenza sulla
config. Il cron di GitHub parte al minimo ogni 5 minuti e può slittare di qualche minuto nei momenti di carico; dopo
60 giorni senza attività GitHub spegne i cron, e il workflow si riabilita da solo a ogni giro per evitarlo. Per
provare in locale il salvataggio dello stato: `OFFERTE_DATA_REMOTE=/percorso/repo.git ./deploy/stato.sh save`.

## Container

```sh
podman build -t offerte -f Containerfile .
podman volume create offerte-var
podman run --rm -v ./config.yaml:/app/config.yaml:ro,Z -v offerte-var:/app/var offerte offerte fetch
podman run -d --name offerte-serve -p 127.0.0.1:8099:8099 -v ./config.yaml:/app/config.yaml:ro,Z -v offerte-var:/app/var offerte
```

Aggiungi `--env-file .env` al primo comando solo se il file esiste: senza, `podman run` esce con un errore. Serve
per le notifiche Telegram e per `APIFY_TOKEN`; senza, il giro funziona lo stesso.

Per il giro periodico in container basta un timer utente che lancia il primo `podman run`, oppure
`podman generate systemd`. Nel container `var_dir: var` risolve in `/app/var`, cioè il volume.

## Notifiche Telegram

Solo per le regole con `notify: true`. Crea il bot con BotFather, scrivigli un messaggio, poi ricava il tuo chat id
(ad esempio con `@userinfobot`). In `.env`, accanto a `config.yaml`:

```
TELEGRAM_BOT_TOKEN=123456789:…
TELEGRAM_CHAT_ID=123456789
```

Le variabili valgono anche se esportate nell'ambiente. Ogni offerta è notificata una volta sola, anche se scatta per più
regole o viene ripubblicata; non si notificano offerte più vecchie di `notifica_max_ore`. La coda di invio si legge dal
database, non dal giro: un invio fallito (Telegram in 429, rete giù, giro interrotto a metà) si ritenta al giro dopo,
finché l'offerta resta dentro `notifica_max_ore`. Al massimo 30 invii per giro, il resto passa al successivo. Senza
token e chat id il fetch funziona lo stesso e avvisa nel log che le notifiche sono disattivate.

## Dettagli di funzionamento

- Al primo giro di un canale si leggono `pagine_storico` pagine seguendo `?before=<id>`; ai giri successivi si legge
  dalla pagina più recente indietro finché si incontra un id già noto, con un tetto di 30 pagine che serve solo a
  recuperare dopo una pausa lunga. Se le pagine finiscono prima di incontrare un id noto, il log dice quanti messaggi
  possono essere stati saltati.
- Una fonte che fallisce (429, 5xx dopo quattro tentativi con backoff 2, 4, 8, 16 s, errore di rete, script che
  esce con errore) viene registrata e si passa alla successiva. Un canale senza anteprima pubblica (t.me/s rimanda a t.me/<canale>) viene
  segnalato nel log e saltato.
- Link dell'offerta: primo fra i pulsanti inline, poi i link nel testo, poi l'anteprima; si scartano i link Telegram e
  quelli a immagini. Gli accorciatori (amzn.to, bit.ly, amzlink.to e simili, o URL con un solo segmento corto) si
  risolvono con una HEAD e il risultato si mette in cache nel database.
- Chiave di dedupe: URL senza tracciamento né affiliate, senza `www.`; per Amazon basta l'ASIN. Senza link, SHA-1 del
  testo normalizzato (minuscolo, senza URL, menzioni, hashtag, emoji e punteggiatura). Il primo canale che pubblica
  tiene il proprio link affiliato.
- Prezzo: il primo importo non marcato come barrato; barrato è ciò che sta in `<s>` o dopo "invece di", "anziché",
  "listino", "da", "era". Con due soli importi senza indizi: il minore è il prezzo, il maggiore il barrato. Lo sconto
  si legge dal testo, altrimenti si calcola.
- Nome del prodotto: prima riga non vuota, senza emoji ai bordi e senza un eventuale prezzo in coda; se la prima riga
  è un'insegna breve tutta in maiuscolo ("ERRORE DI PREZZO") si passa alla successiva.
- Una fonte che risponde ma non produce nulla (selettore CSS che non trova più niente) resta fra le fonti lette e
  prende lo stato `vuota` in `offerte fonti`: zero elementi di solito vuol dire layout cambiato, non assenza di offerte.
- Un link malformato (`tel:`, `mailto:`, porta non numerica) non fa sparire il messaggio: l'offerta si salva senza link
  e con la chiave calcolata dal testo.
- Un ripost della stessa chiave a un prezzo inferiore di almeno il 5% crea una riga nuova invece di aggregarsi, così le
  regole di prezzo e le notifiche vedono il ribasso. Sotto quella soglia, o senza prezzo, si aggrega come sempre.
- Le notifiche si recuperano: finché un'offerta ha un match di una regola `notify`, non ha una riga in `notifications`
  ed è dentro `notifica_max_ore`, resta in coda e il giro successivo riprova.
- I messaggi senza testo (solo foto, sticker) e quelli di servizio non diventano offerte. Le modifiche successive a un
  messaggio non vengono rilette.

## Test

```sh
uv run pytest
```

Coprono il parser su fixture salvate dell'HTML di `t.me/s`, i formati di prezzo, l'estrazione di barrato, sconto,
coupon e nome, la normalizzazione dei link, il dedupe fra canali e nel tempo, le regole con regex, il backoff del
client, la riga di comando, `deploy/stato.sh` su un bare repo temporaneo e un giro completo su trasporto finto
(canale con storico, canale senza anteprima, canale guasto, notifica senza ripetizione, feed generati).

Il motore dei filtri della dashboard gira su gjs, node, deno e bun, quelli che trova, e deve dare gli stessi id di
`rules.matches`; la pagina vera si apre in Chrome headless (`google-chrome`, `chromium` o `$OFFERTE_TEST_BROWSER`)
e si confronta con lo stesso riferimento. Se il motore o il browser mancano, quei test si saltano.

## Struttura

```
offerte/
├── pyproject.toml          progetto uv, script `offerte`
├── config.yaml             configurazione d'esempio
├── .env.example            token e chat id del bot
├── Containerfile
├── systemd/                unit, timer e installa.sh
├── src/offerte/
│   ├── cli.py              fetch | serve | feed | search | stats | filtra | fonti | prova | pulisci
│   ├── config.py           caricamento e validazione di config.yaml
│   ├── sources/            fonti: base, telegram, rss, html, comando, apify; registro dei tipi
│   ├── http.py             client httpx: cortesia, backoff, risoluzione redirect
│   ├── parser.py           HTML di t.me/s -> messaggi; frammenti HTML
│   ├── extract.py          prezzo, barrato, sconto, coupon, nome prodotto
│   ├── links.py            scelta del link, pulizia, chiave di dedupe
│   ├── dedupe.py           chiave URL o hash del testo
│   ├── store.py            SQLite
│   ├── rules.py            regole di alert
│   ├── feeds.py            RSS 2.0, JSON Feed, indice, OPML, dashboard.json
│   ├── static/             dashboard.html, dashboard.css, filtri.js, dashboard.js (copiati in var/feeds/)
│   ├── notify.py           bot Telegram, .env
│   ├── fetch.py            orchestrazione di un giro
│   ├── serve.py            server HTTP
│   └── log.py              stderr + var/offerte.log con rotazione
├── tests/                  pytest, fixture HTML in tests/fixtures/
│   └── demo_dati.py        database e config di prova: `uv run python tests/demo_dati.py /tmp/offerte-demo`
└── var/                    creata al primo avvio: offerte.sqlite, feeds/, offerte.log
```

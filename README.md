# offerte

Aggrega i post dei canali Telegram pubblici leggendo le pagine di anteprima `https://t.me/s/<canale>` (nessun account,
nessun bot, nessuna API) e produce feed RSS 2.0 e JSON Feed per cartella e per regola di alert. Stato in SQLite,
configurazione in YAML, servizio utente systemd ogni dieci minuti, server HTTP locale su `127.0.0.1:8099`.

Per ogni messaggio estrae id, data, testo, link (redirect degli accorciatori risolti, parametri di tracciamento tolti,
tag affiliate conservati), immagine, canale; dal testo ricava prezzo, prezzo barrato, sconto, coupon e nome del prodotto.
La stessa offerta pubblicata da più canali, o più volte dallo stesso, è una sola voce con l'elenco dei canali.

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

`config.yaml` con tre canali e tre regole:

```yaml
parametri:
  intervallo_cortesia: 3          # secondi fra una richiesta a t.me e la successiva
  user_agent: "Mozilla/5.0 (X11; Linux x86_64) offerte/0.1"
  pagine_storico: 3               # pagine di t.me/s (circa 20 messaggi l'una) lette al primo avvio di un canale
  var_dir: var                    # database, feed e log
  feed_base_url: http://127.0.0.1:8099   # base dei link "self" nei feed
  feed_giorni: 14                 # finestra temporale dei feed
  feed_max_elementi: 100
  giorni_dedupe: 7                # la stessa offerta ripubblicata oltre questo intervallo è un'offerta nuova
  notifica_max_ore: 24            # non notifica offerte più vecchie di così

canali:
  - nome: erroridiprezzo
    cartella: casa
    attivo: true
  - nome: erroridiprezzo_offertedalweb
    cartella: casa
    attivo: true
  - nome: offertetecnologia
    cartella: informatica
    attivo: true

regole:
  - nome: ssd-sotto-60
    parole: ["ssd", "nvme", '/\b[12]\s?tb\b/']
    prezzo_max: 60
    canali: [informatica]
    notify: true
  - nome: apple-watch-sotto-250
    parole: ["apple watch", '/\bwatch\s*(se|series|ultra)\b/']
    escludi: [cinturino, cinturini, cover, pellicola, vetro, caricatore, cavo, supporto, custodia]
    prezzo_max: 250
    notify: true
  - nome: errori-di-prezzo
    parole: ["errore di prezzo", '/sconto:?\s*[7-9]\d\s?%/']
    canali: [erroridiprezzo, erroridiprezzo_offertedalweb]
    notify: false
```

Una regola scatta se almeno una parola compare nel testo (con `tutte: true` devono comparire tutte). Una parola
semplice è cercata come parola intera, senza distinzione di maiuscole; una voce fra barre (`'/…/'`) è una regex
Python, sempre case-insensitive. `escludi` elenca parole che annullano la corrispondenza: è il modo per tenere fuori
cinturini e cover quando si cerca un Apple Watch. `prezzo_max` e `prezzo_min` si applicano al prezzo attuale
estratto: un'offerta senza prezzo non passa un filtro di prezzo. `canali` accetta nomi di canale o di cartella;
assente, la regola vale per tutti. Le regole si valutano a ogni giro sulle offerte della finestra `feed_giorni`, quindi
una regola nuova popola subito il proprio feed con il pregresso; le notifiche partono solo per le offerte nuove del giro.

## Comandi

| comando | cosa fa |
|:--|:--|
| `offerte fetch [--canale X] [--storico N] [--senza-notifiche]` | scarica i canali, aggiorna il database, applica le regole, invia le notifiche, rigenera i feed |
| `offerte serve [--host H] [--port P]` | serve `var/feeds/` via HTTP (default `127.0.0.1:8099`) |
| `offerte search <parola> [--limite N]` | cerca nel testo e nel titolo delle offerte salvate |
| `offerte stats [--giorni N]` | offerte al giorno per canale e regole scattate |
| `offerte filtra <parole…> [--prezzo-max X] [--prezzo-min X] [--escludi …] [--tutte] [--canali …]` | prova una regola al volo sulle offerte salvate, per tararla prima di metterla in config |

Esempio: `offerte filtra "apple watch" --prezzo-max 250 --escludi cinturino cover`.
Opzioni globali: `--config`, `-v` (debug), `--version`. Due `fetch` non girano insieme (lock su `var/fetch.lock`).
Il log va su stderr e su `var/offerte.log` (rotazione a 2 MB, cinque copie).

## Feed

In `var/feeds/`, serviti dal server:

```
http://127.0.0.1:8099/                          indice
http://127.0.0.1:8099/cartella/informatica.xml  RSS 2.0 della cartella
http://127.0.0.1:8099/cartella/informatica.json JSON Feed della cartella
http://127.0.0.1:8099/regola/ssd-sotto-60.xml   RSS 2.0 della regola
http://127.0.0.1:8099/regola/ssd-sotto-60.json  JSON Feed della regola
```

Ogni elemento ha titolo `prodotto, prezzo (-sconto%)`, descrizione con immagine, testo originale, prezzo barrato,
coupon, canali di provenienza e link al messaggio, link diretto all'offerta, data del primo post. Il JSON Feed porta
gli stessi campi anche strutturati in `_offerte`.

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

## Container

```sh
podman build -t offerte -f Containerfile .
podman volume create offerte-var
podman run --rm -v ./config.yaml:/app/config.yaml:ro,Z -v offerte-var:/app/var --env-file .env offerte offerte fetch
podman run -d --name offerte-serve -p 127.0.0.1:8099:8099 -v ./config.yaml:/app/config.yaml:ro,Z -v offerte-var:/app/var offerte
```

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
regole o viene ripubblicata; non si notificano offerte più vecchie di `notifica_max_ore`. Senza token e chat id il fetch
funziona lo stesso e avvisa nel log che le notifiche sono disattivate.

## Dettagli di funzionamento

- Al primo giro di un canale si leggono `pagine_storico` pagine seguendo `?before=<id>`; ai giri successivi si legge
  dalla pagina più recente indietro finché si incontra un id già noto.
- Un canale che fallisce (429, 5xx dopo quattro tentativi con backoff 2, 4, 8, 16 s, oppure errore di rete) viene
  registrato e si passa al successivo. Un canale senza anteprima pubblica (t.me/s rimanda a t.me/<canale>) viene
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
- I messaggi senza testo (solo foto, sticker) e quelli di servizio non diventano offerte. Le modifiche successive a un
  messaggio non vengono rilette.

## Test

```sh
uv run pytest
```

Coprono il parser su fixture salvate dell'HTML di `t.me/s`, i formati di prezzo, l'estrazione di barrato, sconto,
coupon e nome, la normalizzazione dei link, il dedupe fra canali e nel tempo, le regole con regex, il backoff del
client e un giro completo su trasporto finto (canale con storico, canale senza anteprima, canale guasto, notifica
senza ripetizione, feed generati).

## Struttura

```
offerte/
├── pyproject.toml          progetto uv, script `offerte`
├── config.yaml             configurazione d'esempio
├── .env.example            token e chat id del bot
├── Containerfile
├── systemd/                unit, timer e installa.sh
├── src/offerte/
│   ├── cli.py              fetch | serve | search | stats
│   ├── config.py           caricamento e validazione di config.yaml
│   ├── http.py             client httpx: cortesia, backoff, risoluzione redirect
│   ├── parser.py           HTML di t.me/s -> messaggi
│   ├── extract.py          prezzo, barrato, sconto, coupon, nome prodotto
│   ├── links.py            scelta del link, pulizia, chiave di dedupe
│   ├── dedupe.py           chiave URL o hash del testo
│   ├── store.py            SQLite
│   ├── rules.py            regole di alert
│   ├── feeds.py            RSS 2.0, JSON Feed, indice
│   ├── notify.py           bot Telegram, .env
│   ├── fetch.py            orchestrazione di un giro
│   ├── serve.py            server HTTP
│   └── log.py              stderr + var/offerte.log con rotazione
├── tests/                  pytest, fixture HTML in tests/fixtures/
└── var/                    creata al primo avvio: offerte.sqlite, feeds/, offerte.log
```

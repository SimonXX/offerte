// Interfaccia della dashboard: caricamento, controlli, rendering, stato nell'URL, dialogo della regola.
// Il DOM si costruisce solo con createElement e textContent: testi, link e immagini vengono da canali
// pubblici e da script esterni, quindi non sono fidati.
(function () {
  "use strict";

  var F = globalThis.Filtri;
  var PAGINA = 60;
  var VERSIONE_ATTESA = 1;
  var DEBOUNCE_MS = 200;
  var VECCHI_MINUTI = 90;
  var TOAST_MS = 6000;

  var DOM = {
    q: document.getElementById("q"),
    no: document.getElementById("no"),
    tutte: document.getElementById("tutte"),
    rigaTutte: document.getElementById("riga-tutte"),
    parolaIntera: document.getElementById("parola-intera"),
    rigaParolaIntera: document.getElementById("riga-parola-intera"),
    pmin: document.getElementById("pmin"),
    pmax: document.getElementById("pmax"),
    smin: document.getElementById("smin"),
    cart: document.getElementById("cart"),
    cartGruppo: document.getElementById("cart-gruppo"),
    can: document.getElementById("can"),
    canali: document.getElementById("canali"),
    per: document.getElementById("per"),
    cp: document.getElementById("cp"),
    ord: document.getElementById("ord"),
    conta: document.getElementById("conta"),
    nascoste: document.getElementById("nascoste"),
    suggerimento: document.getElementById("suggerimento"),
    elenco: document.getElementById("elenco"),
    altre: document.getElementById("altre"),
    regola: document.getElementById("regola"),
    motivoRegola: document.getElementById("motivo-regola"),
    azzera: document.getElementById("azzera"),
    copiaLink: document.getElementById("copia-link"),
    ricarica: document.getElementById("ricarica"),
    statoDati: document.getElementById("stato-dati"),
    statoTesto: document.getElementById("stato-testo"),
    statoFonti: document.getElementById("stato-fonti"),
    statoFontiTitolo: document.getElementById("stato-fonti-titolo"),
    elencoFonti: document.getElementById("elenco-fonti"),
    avvisi: document.getElementById("avvisi"),
    preset: document.getElementById("preset"),
    chipAttivi: document.getElementById("chip-attivi"),
    filtri: document.getElementById("filtri"),
    filtriTitolo: document.getElementById("filtri-titolo"),
    erroreQ: document.getElementById("errore-q"),
    erroreNo: document.getElementById("errore-no"),
    scorciatoiePrezzo: document.getElementById("scorciatoie-prezzo"),
    toast: document.getElementById("toast"),
    dialogo: document.getElementById("dialogo"),
    nomeRegola: document.getElementById("nome-regola"),
    nomeAvviso: document.getElementById("nome-avviso"),
    notify: document.getElementById("notify"),
    yaml: document.getElementById("yaml"),
    esclusiRegola: document.getElementById("esclusi-regola"),
    copiaYaml: document.getElementById("copia-yaml"),
    chiudiDialogo: document.getElementById("chiudi-dialogo")
  };

  // Scala del menu Periodo: si mostrano solo i gradini più stretti della finestra dei dati, che la
  // pagina legge da dashboard.json. Alzando dashboard_giorni compaiono da soli i gradini più larghi.
  var SCALA_PERIODI = [
    {valore: "1h", testo: "Ultima ora"},
    {valore: "3h", testo: "Ultime 3 ore"},
    {valore: "6h", testo: "Ultime 6 ore"},
    {valore: "12h", testo: "Ultime 12 ore"},
    {valore: "24h", testo: "Ultime 24 ore"},
    {valore: "48h", testo: "Ultime 48 ore"},
    {valore: "3g", testo: "Ultimi 3 giorni"},
    {valore: "7g", testo: "Ultimi 7 giorni"},
    {valore: "14g", testo: "Ultimi 14 giorni"},
    {valore: "30g", testo: "Ultimi 30 giorni"},
    {valore: "60g", testo: "Ultimi 60 giorni"},
    {valore: "90g", testo: "Ultimi 90 giorni"}
  ];

  var euro = new Intl.NumberFormat("it-IT", {style: "currency", currency: "EUR"});
  var gruppiNumeri = new Intl.NumberFormat("it-IT");

  var dati = null;
  var offerte = [];
  var cartelle = {};
  var regole = [];
  var fonti = [];
  var canaliNoti = [];
  var conteggiCartella = {};
  var conteggiCanale = {};
  var stato = F.statoDefault();
  var statoPrimaDellAzzera = null;
  var mostrate = PAGINA;
  var esito = {righe: [], senzaPrezzo: 0, senzaSconto: 0, troppoLento: false, compilato: null};
  var timerFiltri = null;
  var timerToast = null;
  var primoCaricamento = true;

  // --- utilità -------------------------------------------------------------

  function svuota(nodo) {
    nodo.replaceChildren();
  }

  function crea(tag, classe, testo) {
    var n = document.createElement(tag);
    if (classe) { n.className = classe; }
    if (testo !== undefined && testo !== null) { n.textContent = String(testo); }
    return n;
  }

  function urlSicuro(u) {
    if (!u) { return null; }
    try {
      var protocollo = new URL(u, location.href).protocol;
      return (protocollo === "http:" || protocollo === "https:") ? u : null;
    } catch (e) {
      return null;
    }
  }

  function righeDi(testo) {
    return String(testo || "").split("\n").map(function (r) { return r.trim(); })
      .filter(function (r) { return r.length > 0; });
  }

  function numeroCampo(v) {
    var s = String(v === undefined || v === null ? "" : v).trim().replace(",", ".");
    if (!s) { return null; }
    var n = Number(s);
    return isFinite(n) && n >= 0 ? n : null;
  }

  function interoCampo(v) {
    var s = String(v === undefined || v === null ? "" : v).trim();
    if (!s) { return null; }
    var n = Number(s);
    return isFinite(n) && Math.floor(n) === n && n >= 1 && n <= 99 ? n : null;
  }

  function plurale(n, singolare, plurale2) {
    return n === 1 ? singolare : plurale2;
  }

  function quandoRelativo(secondi) {
    var differenza = Math.floor(Date.now() / 1000) - secondi;
    if (differenza < 60) { return "adesso"; }
    if (differenza < 3600) { return Math.floor(differenza / 60) + " min fa"; }
    if (differenza < 86400) { return Math.floor(differenza / 3600) + " h fa"; }
    var quando = new Date(secondi * 1000);
    var oggi = new Date();
    var ieri = new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate() - 1);
    var ore = quando.toLocaleTimeString("it-IT", {hour: "2-digit", minute: "2-digit"});
    if (quando.getFullYear() === ieri.getFullYear() && quando.getMonth() === ieri.getMonth()
        && quando.getDate() === ieri.getDate()) {
      return "ieri " + ore;
    }
    return quando.toLocaleDateString("it-IT", {day: "numeric", month: "short"}) + " " + ore;
  }

  function dataCompleta(secondi) {
    return new Date(secondi * 1000).toLocaleString("it-IT");
  }

  // --- stato della pagina --------------------------------------------------

  function segna(nome, valore) {
    if (valore === null) {
      document.documentElement.removeAttribute(nome);
    } else {
      document.documentElement.setAttribute(nome, String(valore));
    }
  }

  function mostraStato(nome, testo, azione) {
    segna("data-stato", nome);
    svuota(DOM.statoTesto);
    DOM.statoTesto.appendChild(document.createTextNode(testo));
    if (azione) {
      var b = crea("button", null, azione.etichetta);
      b.type = "button";
      b.addEventListener("click", azione.fai);
      DOM.statoTesto.appendChild(document.createTextNode(" "));
      DOM.statoTesto.appendChild(b);
    }
  }

  // --- caricamento ---------------------------------------------------------

  function carica() {
    mostraStato("caricamento", "Carico le offerte...");
    fetch("dashboard.json", {cache: "no-cache"}).then(function (risposta) {
      if (!risposta.ok) {
        mostraStato("errore-rete",
          "Non riesco a caricare dashboard.json (HTTP " + risposta.status +
          "). Esegui offerte fetch oppure offerte feed, poi ricarica.",
          {etichetta: "Riprova", fai: carica});
        return null;
      }
      return risposta.json().catch(function () {
        mostraStato("errore-json", "dashboard.json non è leggibile. Rigeneralo con offerte feed.",
          {etichetta: "Riprova", fai: carica});
        return null;
      });
    }).catch(function () {
      mostraStato("errore-rete",
        "Non riesco a caricare dashboard.json (rete non raggiungibile). Esegui offerte fetch oppure" +
        " offerte feed, poi ricarica.", {etichetta: "Riprova", fai: carica});
      return null;
    }).then(function (documento) {
      if (documento) { accogli(documento); }
    });
  }

  function accogli(documento) {
    if (documento.v !== VERSIONE_ATTESA) {
      mostraStato("errore-versione", "La pagina e i dati non sono allineati. Ricarica la pagina.",
        {etichetta: "Ricarica pagina", fai: function () { location.reload(); }});
      return;
    }
    dati = documento;
    offerte = documento.offerte || [];
    cartelle = documento.cartelle || {};
    regole = documento.regole || [];
    fonti = documento.fonti || [];
    canaliNoti = [];
    Object.keys(cartelle).forEach(function (c) {
      cartelle[c].forEach(function (n) { canaliNoti.push(n); });
    });
    calcolaConteggi();
    if (primoCaricamento) {
      stato = F.leggiUrl(location.search, cartelle);
      costruisciCaselle();
      primoCaricamento = false;
    }
    costruisciPeriodi();
    mostraFonti();
    mostraAvvisi();
    if (!offerte.length) {
      mostraStato("vuoto", "Nessuna offerta nei dati. Esegui offerte fetch.");
      svuota(DOM.elenco);
      segna("data-n", 0);
      segna("data-primi", "");
      return;
    }
    scriviControlli();
    mostrate = PAGINA;
    aggiorna(false);
    mostraStato("pronto", riassuntoDati());
    setTimeout(contaPreset, 0);
  }

  function riassuntoDati() {
    var quando = new Date(dati.generato * 1000);
    return "aggiornato alle " + quando.toLocaleTimeString("it-IT", {hour: "2-digit", minute: "2-digit"}) +
      ", " + quandoRelativo(dati.generato) + ", " + gruppiNumeri.format(offerte.length) + " " +
      plurale(offerte.length, "offerta", "offerte") + " in " + dati.finestra_giorni + " giorni";
  }

  function opzione(valore, testo) {
    var o = document.createElement("option");
    o.value = valore;
    o.textContent = testo;
    return o;
  }

  function costruisciPeriodi() {
    var giorni = dati.finestra_giorni || 14;
    var finestra = giorni * 86400;
    var scelti = SCALA_PERIODI.filter(function (v) { return F.periodoSecondi(v.valore) < finestra; });
    var presenti = scelti.map(function (v) { return v.valore; });
    if (stato.per !== null && presenti.indexOf(stato.per) === -1) {
      scelti.push({valore: stato.per, testo: "Periodo dall'indirizzo: " + stato.per});
    }
    svuota(DOM.per);
    DOM.per.appendChild(opzione("", "Tutto il periodo (" + giorni + " giorni)"));
    scelti.forEach(function (v) { DOM.per.appendChild(opzione(v.valore, v.testo)); });
  }

  function calcolaConteggi() {
    conteggiCartella = {};
    conteggiCanale = {};
    var cartelleDi = {};
    Object.keys(cartelle).forEach(function (c) {
      cartelle[c].forEach(function (n) {
        if (!cartelleDi[n]) { cartelleDi[n] = []; }
        cartelleDi[n].push(c);
      });
    });
    offerte.forEach(function (o) {
      var viste = {};
      (o.k || []).forEach(function (n) {
        conteggiCanale[n] = (conteggiCanale[n] || 0) + 1;
        (cartelleDi[n] || []).forEach(function (c) {
          if (!viste[c]) { viste[c] = true; conteggiCartella[c] = (conteggiCartella[c] || 0) + 1; }
        });
      });
    });
  }

  // --- stato delle fonti ---------------------------------------------------

  function saluteFonte(f) {
    if (!f.attiva) { return {classe: "punto", testo: "inattiva", problema: false}; }
    if (f.stato === "error" || f.stato === "no_preview") {
      return {classe: "punto punto-errore", testo: "errore", problema: true};
    }
    if (f.stato === "vuota") { return {classe: "punto punto-attesa", testo: "vuota", problema: true}; }
    if (f.ultimo_fetch === undefined || f.ultimo_fetch === null) {
      return {classe: "punto", testo: "mai letta", problema: false};
    }
    var fermo = Math.floor(Date.now() / 1000) - f.ultimo_fetch;
    var soglia = Math.max(45 * 60, (f.ogni || 0) * 60 * 3);
    if (fermo > soglia) {
      return {classe: "punto punto-attesa", testo: "ferma da " + quandoRelativo(f.ultimo_fetch).replace(" fa", ""),
              problema: true};
    }
    return {classe: "punto punto-ok", testo: "ok, " + quandoRelativo(f.ultimo_fetch), problema: false};
  }

  function mostraFonti() {
    svuota(DOM.elencoFonti);
    if (!fonti.length) {
      DOM.statoFonti.hidden = true;
      return;
    }
    DOM.statoFonti.hidden = false;
    var problemi = 0;
    fonti.forEach(function (f) {
      var salute = saluteFonte(f);
      if (salute.problema) { problemi += 1; }
      var riga = crea("li");
      var punto = crea("span", salute.classe);
      punto.setAttribute("aria-hidden", "true");
      riga.appendChild(punto);
      riga.appendChild(document.createTextNode(f.nome + ", " + salute.testo));
      DOM.elencoFonti.appendChild(riga);
    });
    DOM.statoFontiTitolo.textContent = "Fonti (" + problemi + " con " +
      plurale(problemi, "problema", "problemi") + ")";
  }

  function mostraAvvisi() {
    svuota(DOM.avvisi);
    var vecchi = (Math.floor(Date.now() / 1000) - dati.generato) > VECCHI_MINUTI * 60;
    if (vecchi) {
      DOM.avvisi.appendChild(crea("p", "banda",
        "I dati risalgono a più di " + VECCHI_MINUTI + " minuti fa: la raccolta potrebbe essersi fermata."));
    }
    if (dati.troncato) {
      DOM.avvisi.appendChild(crea("p", "banda",
        "Mostrate le " + gruppiNumeri.format(offerte.length) + " offerte più recenti."));
    }
    segna("data-vecchi", vecchi ? "1" : "0");
    segna("data-troncato", dati.troncato ? "1" : "0");
  }

  // --- caselle di cartelle e canali ---------------------------------------

  function casella(contenitore, valore, etichetta, gruppo) {
    var p = crea("p", "campo campo-casella");
    var input = document.createElement("input");
    input.type = "checkbox";
    input.id = gruppo + "-" + valore;
    input.value = valore;
    input.setAttribute("data-gruppo", gruppo);
    var label = crea("label", null, etichetta);
    label.htmlFor = input.id;
    p.appendChild(input);
    p.appendChild(label);
    contenitore.appendChild(p);
    return input;
  }

  function costruisciCaselle() {
    svuota(DOM.cart);
    svuota(DOM.can);
    var nomiCartelle = Object.keys(cartelle).sort();
    nomiCartelle.forEach(function (c) {
      casella(DOM.cart, c, c + " (" + gruppiNumeri.format(conteggiCartella[c] || 0) + ")", "cart");
    });
    DOM.cartGruppo.hidden = nomiCartelle.length === 0;
    nomiCartelle.forEach(function (c) {
      var gruppo = document.createElement("fieldset");
      gruppo.appendChild(crea("legend", null, c));
      cartelle[c].forEach(function (n) {
        casella(gruppo, n, n + " (" + gruppiNumeri.format(conteggiCanale[n] || 0) + ")", "can");
      });
      DOM.can.appendChild(gruppo);
    });
    var altri = Object.keys(conteggiCanale).filter(function (n) { return canaliNoti.indexOf(n) === -1; }).sort();
    if (altri.length) {
      var gruppoAltri = document.createElement("fieldset");
      gruppoAltri.appendChild(crea("legend", null, "altri"));
      altri.forEach(function (n) {
        casella(gruppoAltri, n, n + " (" + gruppiNumeri.format(conteggiCanale[n]) + ")", "can");
      });
      DOM.can.appendChild(gruppoAltri);
    }
  }

  function selezionate(contenitore) {
    var fuori = [];
    contenitore.querySelectorAll("input[type=checkbox]").forEach(function (i) {
      if (i.checked) { fuori.push(i.value); }
    });
    return fuori;
  }

  // --- controlli -----------------------------------------------------------

  function scriviControlli() {
    DOM.q.value = stato.q.join("\n");
    DOM.no.value = stato.no.join("\n");
    DOM.tutte.checked = stato.tutte;
    DOM.parolaIntera.checked = stato.pi;
    DOM.pmin.value = stato.pmin === null ? "" : String(stato.pmin);
    DOM.pmax.value = stato.pmax === null ? "" : String(stato.pmax);
    DOM.smin.value = stato.smin === null ? "" : String(stato.smin);
    DOM.per.value = stato.per === null ? "" : stato.per;
    DOM.cp.checked = stato.cp;
    DOM.ord.value = stato.ord;
    DOM.cart.querySelectorAll("input[type=checkbox]").forEach(function (i) {
      i.checked = stato.cart.indexOf(i.value) >= 0;
    });
    DOM.can.querySelectorAll("input[type=checkbox]").forEach(function (i) {
      i.checked = stato.can.indexOf(i.value) >= 0;
    });
  }

  function leggiControlli() {
    var s = F.copiaStato(stato);
    s.q = righeDi(DOM.q.value);
    s.no = righeDi(DOM.no.value);
    s.tutte = DOM.tutte.checked;
    s.pi = DOM.parolaIntera.checked;
    s.pmin = numeroCampo(DOM.pmin.value);
    s.pmax = numeroCampo(DOM.pmax.value);
    s.smin = interoCampo(DOM.smin.value);
    s.cart = selezionate(DOM.cart);
    s.can = selezionate(DOM.can);
    s.per = DOM.per.value || null;
    s.cp = DOM.cp.checked;
    s.ord = DOM.ord.value;
    return s;
  }

  function dalleControlli() {
    stato = leggiControlli();
    mostrate = PAGINA;
    aggiorna(false);
  }

  function imposta(nuovo) {
    stato = nuovo;
    mostrate = PAGINA;
    scriviControlli();
    aggiorna(false);
  }

  function aggiorna(saltaUrl) {
    if (!saltaUrl) {
      var qs = F.scriviUrl(stato);
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
    }
    esito = F.applica(offerte, stato, {cartelle: cartelle});
    mostraErrori();
    mostraRisultati();
    mostraChip();
    aggiornaPreset();
    aggiornaPannello();
  }

  function mostraErrori() {
    var compilato = esito.compilato;
    [["q", DOM.q, DOM.erroreQ], ["no", DOM.no, DOM.erroreNo]].forEach(function (voce) {
      var campo = voce[0], controllo = voce[1], riquadro = voce[2];
      var messaggi = [];
      compilato.errori.forEach(function (e) {
        if (e.campo === campo) { messaggi.push("Riga " + e.riga + ": espressione non valida (" + e.messaggio + ")"); }
      });
      compilato.avvisi.forEach(function (a) {
        if (a.campo === campo) { messaggi.push("Riga " + a.riga + ": " + a.messaggio); }
      });
      riquadro.textContent = messaggi.join(" ");
      var haErrori = compilato.errori.some(function (e) { return e.campo === campo; });
      controllo.setAttribute("aria-invalid", haErrori ? "true" : "false");
    });
    segna("data-errori-regex", compilato.errori.length);
  }

  function aggiornaPannello() {
    var attivi = F.gruppiAttivi(stato).filter(function (g) { return g !== "q"; });
    DOM.filtriTitolo.textContent = "Filtri (" + attivi.length + ")";
    DOM.rigaTutte.hidden = stato.q.length < 2;
    DOM.rigaParolaIntera.hidden = stato.q.length === 0 && stato.no.length === 0;
    DOM.scorciatoiePrezzo.querySelectorAll("button").forEach(function (b) {
      var valore = Number(b.getAttribute("data-pmax"));
      b.setAttribute("aria-pressed", stato.pmax === valore ? "true" : "false");
    });
    var regolaYaml = F.yamlRegola(stato, {nome: F.nomeSuggerito(stato), notify: false}, cartelle);
    var puo = regolaYaml !== null && esito.compilato.ok;
    DOM.regola.disabled = !puo;
    if (regolaYaml === null) {
      DOM.motivoRegola.textContent = "serve almeno un criterio: parole, prezzo, sconto, coupon o canale";
    } else if (!esito.compilato.ok) {
      DOM.motivoRegola.textContent = "correggi le espressioni non valide prima di creare la regola";
    } else {
      DOM.motivoRegola.textContent = "";
    }
  }

  // --- risultati -----------------------------------------------------------

  function schedaOfferta(o) {
    var articolo = crea("article", "offerta");
    var immagine = urlSicuro(o.i);
    if (immagine) {
      var img = document.createElement("img");
      img.className = "miniatura";
      img.src = immagine;
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.referrerPolicy = "no-referrer";
      img.width = 72;
      img.height = 72;
      articolo.appendChild(img);
    } else {
      articolo.className = "offerta senza-foto";
    }
    var corpo = crea("div");

    var nome = crea("p", "nome");
    var destinazione = urlSicuro(o.u);
    if (destinazione) {
      var collegamento = crea("a", null, o.n);
      collegamento.href = destinazione;
      collegamento.target = "_blank";
      collegamento.rel = "noopener noreferrer nofollow sponsored";
      nome.appendChild(collegamento);
    } else {
      nome.appendChild(document.createTextNode(o.n));
    }
    corpo.appendChild(nome);

    var prezzi = crea("p", "prezzi");
    if (o.p !== undefined && o.p !== null) {
      prezzi.appendChild(crea("span", "prezzo", euro.format(o.p)));
    }
    if (o.b !== undefined && o.b !== null) {
      prezzi.appendChild(crea("span", "barrato", "prima " + euro.format(o.b)));
    }
    if (o.s !== undefined && o.s !== null) {
      prezzi.appendChild(crea("span", "badge badge-sconto", "-" + o.s + "%"));
    }
    if (o.c) {
      prezzi.appendChild(crea("span", "badge badge-coupon", "coupon " + o.c));
    }
    if (prezzi.childNodes.length) { corpo.appendChild(prezzi); }

    var meta = crea("p", "meta", quandoRelativo(o.t) + " · " + (o.k || []).join(", "));
    meta.title = dataCompleta(o.t);
    corpo.appendChild(meta);

    var azioni = crea("p", "azioni-offerta");
    if (destinazione) {
      var vai = crea("a", null, "Vai all'offerta");
      vai.href = destinazione;
      vai.target = "_blank";
      vai.rel = "noopener noreferrer nofollow sponsored";
      azioni.appendChild(vai);
    }
    var messaggio = urlSicuro(o.m);
    if (messaggio) {
      var msg = crea("a", null, "Messaggio");
      msg.href = messaggio;
      msg.target = "_blank";
      msg.rel = "noopener noreferrer nofollow sponsored";
      azioni.appendChild(msg);
    }
    if (azioni.childNodes.length) { corpo.appendChild(azioni); }

    var dettagli = document.createElement("details");
    dettagli.appendChild(crea("summary", null, "Testo"));
    dettagli.appendChild(crea("pre", "testo-originale", o.x || ""));
    corpo.appendChild(dettagli);

    articolo.appendChild(corpo);
    return articolo;
  }

  function mostraRisultati() {
    var righe = esito.righe;
    var totale = righe.length;
    svuota(DOM.elenco);
    var pezzo = document.createDocumentFragment();
    righe.slice(0, mostrate).forEach(function (o) { pezzo.appendChild(schedaOfferta(o)); });
    DOM.elenco.appendChild(pezzo);
    DOM.altre.hidden = totale <= mostrate;

    if (totale === 0) {
      DOM.conta.textContent = "Nessuna offerta";
      var vuoto = crea("p", null, "Nessuna offerta corrisponde ai filtri.");
      var pulsante = crea("button", null, "Azzera filtri");
      pulsante.type = "button";
      pulsante.addEventListener("click", azzera);
      vuoto.appendChild(document.createTextNode(" "));
      vuoto.appendChild(pulsante);
      DOM.elenco.appendChild(vuoto);
      mostraSuggerimento();
    } else {
      DOM.conta.textContent = totale === 1
        ? "1 offerta"
        : gruppiNumeri.format(totale) + " offerte su " + gruppiNumeri.format(offerte.length);
      DOM.suggerimento.textContent = "";
    }

    var parti = [];
    if (esito.senzaPrezzo > 0) {
      parti.push(gruppiNumeri.format(esito.senzaPrezzo) + " " +
        plurale(esito.senzaPrezzo, "offerta senza prezzo non mostrata", "offerte senza prezzo non mostrate"));
    }
    if (esito.senzaSconto > 0) {
      parti.push(gruppiNumeri.format(esito.senzaSconto) + " " +
        plurale(esito.senzaSconto, "offerta senza sconto non mostrata", "offerte senza sconto non mostrate"));
    }
    if (esito.troppoLento) { parti.push("Espressione troppo lenta, semplificala."); }
    DOM.nascoste.textContent = parti.join(". ");

    segna("data-n", totale);
    segna("data-primi", righe.slice(0, 20).map(function (o) { return o.id; }).join(","));
  }

  var ETICHETTE = {
    q: "Parole", no: "Escludi", tutte: "Tutte le parole", pi: "Solo parola intera",
    prezzo: "Prezzo", smin: "Sconto minimo",
    cart: "Cartella", can: "Canali", per: "Periodo", cp: "Solo coupon"
  };

  function etichettaGruppo(gruppo) {
    if (gruppo === "q") { return "Parole (" + stato.q.length + ")"; }
    if (gruppo === "no") { return "Escludi (" + stato.no.length + ")"; }
    if (gruppo === "tutte") { return "Tutte le parole"; }
    if (gruppo === "prezzo") {
      if (stato.pmin !== null && stato.pmax !== null) {
        return "da " + euro.format(stato.pmin) + " a " + euro.format(stato.pmax);
      }
      return stato.pmin !== null ? "da " + euro.format(stato.pmin) : "fino a " + euro.format(stato.pmax);
    }
    if (gruppo === "smin") { return "sconto da " + stato.smin + "%"; }
    if (gruppo === "cart") { return "cartella: " + stato.cart.join(", "); }
    if (gruppo === "can") { return "canale: " + stato.can.join(", "); }
    if (gruppo === "per") { return DOM.per.options[DOM.per.selectedIndex].text.toLowerCase(); }
    return ETICHETTE[gruppo] || gruppo;
  }

  function mostraChip() {
    svuota(DOM.chipAttivi);
    F.gruppiAttivi(stato).forEach(function (gruppo) {
      var etichetta = etichettaGruppo(gruppo);
      var b = crea("button", null, etichetta + " ×");
      b.type = "button";
      b.setAttribute("data-gruppo", gruppo);
      b.setAttribute("aria-label", "Rimuovi filtro: " + etichetta);
      DOM.chipAttivi.appendChild(b);
    });
  }

  function mostraSuggerimento() {
    DOM.suggerimento.textContent = "";
    var attivi = F.gruppiAttivi(stato);
    if (!attivi.length) { return; }
    var migliore = null;
    attivi.forEach(function (gruppo) {
      var senza = F.applica(offerte, F.togliGruppo(stato, gruppo), {cartelle: cartelle});
      if (senza.righe.length > 0 && (migliore === null || senza.righe.length > migliore.quante)) {
        migliore = {gruppo: gruppo, quante: senza.righe.length, etichetta: etichettaGruppo(gruppo)};
      }
    });
    if (migliore === null) { return; }
    DOM.suggerimento.appendChild(document.createTextNode(
      "Togliendo «" + migliore.etichetta + "» trovi " + gruppiNumeri.format(migliore.quante) + " " +
      plurale(migliore.quante, "offerta", "offerte") + ". "));
    var b = crea("button", null, "Togli");
    b.type = "button";
    b.addEventListener("click", function () { imposta(F.togliGruppo(stato, migliore.gruppo)); });
    DOM.suggerimento.appendChild(b);
  }

  // --- preset --------------------------------------------------------------

  function aggiornaPreset() {
    DOM.preset.hidden = regole.length === 0;
    if (!regole.length) { return; }
    if (DOM.preset.childNodes.length !== regole.length) {
      svuota(DOM.preset);
      regole.forEach(function (r) {
        var voce = crea("span", "preset-voce");
        var b = crea("button", null, r.nome);
        b.type = "button";
        b.setAttribute("data-regola", r.nome);
        voce.appendChild(b);
        var rss = crea("a", null, "RSS");
        rss.href = "regola/" + r.slug + ".xml";
        voce.appendChild(rss);
        DOM.preset.appendChild(voce);
      });
    }
    DOM.preset.querySelectorAll("button[data-regola]").forEach(function (b) {
      var nome = b.getAttribute("data-regola");
      var r = regole.filter(function (x) { return x.nome === nome; })[0];
      b.setAttribute("aria-pressed", r && F.regolaUguale(stato, r, cartelle) ? "true" : "false");
    });
  }

  function contaPreset() {
    regole.forEach(function (r) {
      var quante = F.applica(offerte, F.statoDaRegola(r, cartelle), {cartelle: cartelle}).righe.length;
      DOM.preset.querySelectorAll("button[data-regola]").forEach(function (b) {
        if (b.getAttribute("data-regola") === r.nome) {
          b.textContent = r.nome + " (" + gruppiNumeri.format(quante) + ")";
        }
      });
    });
  }

  // --- toast, copia, dialogo ----------------------------------------------

  function toast(testo, azione) {
    svuota(DOM.toast);
    DOM.toast.hidden = false;
    DOM.toast.appendChild(document.createTextNode(testo));
    if (azione) {
      var b = crea("button", null, azione.etichetta);
      b.type = "button";
      b.addEventListener("click", function () { chiudiToast(); azione.fai(); });
      DOM.toast.appendChild(b);
    }
    if (timerToast) { clearTimeout(timerToast); }
    timerToast = setTimeout(chiudiToast, TOAST_MS);
  }

  function chiudiToast() {
    if (timerToast) { clearTimeout(timerToast); timerToast = null; }
    DOM.toast.hidden = true;
    svuota(DOM.toast);
  }

  function copia(testo, campo) {
    function ripiego() {
      if (campo) {
        campo.focus();
        campo.select();
        try {
          if (document.execCommand("copy")) { toast("Copiato."); return; }
        } catch (e) {
          // contesto non sicuro senza execCommand
        }
      }
      toast("Copia non riuscita: il testo è selezionato, copialo a mano.");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(testo).then(function () { toast("Copiato."); }, ripiego);
      return;
    }
    ripiego();
  }

  function azzera() {
    statoPrimaDellAzzera = F.copiaStato(stato);
    imposta(F.statoDefault());
    toast("Filtri azzerati.", {etichetta: "Annulla", fai: function () {
      if (statoPrimaDellAzzera) { imposta(statoPrimaDellAzzera); }
    }});
  }

  function nomeLibero(base) {
    var usati = regole.map(function (r) { return r.slug; });
    if (usati.indexOf(F.slug(base)) === -1) { return {nome: base, avviso: "" }; }
    var n = 2;
    while (usati.indexOf(F.slug(base + "-" + n)) >= 0) { n += 1; }
    var proposto = base + "-" + n;
    return {nome: proposto, avviso: "nome già in uso, proposto «" + proposto + "»"};
  }

  function apriDialogo() {
    var scelta = nomeLibero(F.nomeSuggerito(stato));
    DOM.nomeRegola.value = scelta.nome;
    DOM.nomeAvviso.textContent = scelta.avviso;
    DOM.notify.checked = false;
    DOM.notify.disabled = stato.q.length === 0;
    aggiornaYaml();
    DOM.dialogo.showModal();
  }

  function aggiornaYaml() {
    var prodotta = F.yamlRegola(stato, {nome: DOM.nomeRegola.value.trim(), notify: DOM.notify.checked}, cartelle);
    DOM.yaml.value = prodotta ? prodotta.yaml : "";
    var note = [];
    if (stato.per !== null) { note.push("Non incluso nella regola: periodo."); }
    if (prodotta && prodotta.esclusi.length) {
      note.push("Canali non più in config.yaml: " + prodotta.esclusi.join(", ") + ".");
    }
    if (DOM.notify.disabled) { note.push("notify richiede almeno una parola."); }
    DOM.esclusiRegola.textContent = note.join(" ");
  }

  // --- eventi --------------------------------------------------------------

  function conRitardo() {
    if (timerFiltri) { clearTimeout(timerFiltri); }
    timerFiltri = setTimeout(dalleControlli, DEBOUNCE_MS);
  }

  function collega() {
    [DOM.q, DOM.no, DOM.pmin, DOM.pmax, DOM.smin].forEach(function (c) {
      c.addEventListener("input", conRitardo);
    });
    [DOM.tutte, DOM.parolaIntera, DOM.cp, DOM.per, DOM.ord].forEach(function (c) {
      c.addEventListener("change", dalleControlli);
    });
    [DOM.cart, DOM.can].forEach(function (c) {
      c.addEventListener("change", function (ev) {
        if (ev.target && ev.target.type === "checkbox") { dalleControlli(); }
      });
    });
    DOM.scorciatoiePrezzo.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button[data-pmax]") : null;
      if (!b) { return; }
      var valore = Number(b.getAttribute("data-pmax"));
      var s = F.copiaStato(stato);
      s.pmax = s.pmax === valore ? null : valore;
      imposta(s);
    });
    DOM.chipAttivi.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button[data-gruppo]") : null;
      if (b) { imposta(F.togliGruppo(stato, b.getAttribute("data-gruppo"))); }
    });
    DOM.preset.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button[data-regola]") : null;
      if (!b) { return; }
      var r = regole.filter(function (x) { return x.nome === b.getAttribute("data-regola"); })[0];
      if (!r) { return; }
      var s = F.statoDaRegola(r, cartelle);
      s.ord = stato.ord;
      imposta(s);
    });
    DOM.elenco.addEventListener("error", function (ev) {
      if (!ev.target || ev.target.tagName !== "IMG") { return; }
      ev.target.hidden = true;
      // senza la miniatura la scheda deve tornare a una colonna, altrimenti il testo resta nei 72 px
      if (ev.target.parentNode && ev.target.parentNode.classList) {
        ev.target.parentNode.classList.add("senza-foto");
      }
    }, true);
    DOM.altre.addEventListener("click", function () {
      mostrate += PAGINA;
      mostraRisultati();
    });
    DOM.azzera.addEventListener("click", azzera);
    DOM.copiaLink.addEventListener("click", function () { copia(location.href, null); });
    DOM.ricarica.addEventListener("click", carica);
    DOM.regola.addEventListener("click", apriDialogo);
    DOM.nomeRegola.addEventListener("input", aggiornaYaml);
    DOM.notify.addEventListener("change", aggiornaYaml);
    DOM.copiaYaml.addEventListener("click", function () { copia(DOM.yaml.value, DOM.yaml); });
    DOM.chiudiDialogo.addEventListener("click", function () { DOM.dialogo.close(); });
    if (matchMedia("(min-width: 900px)").matches) { DOM.filtri.open = true; }
  }

  function avvia() {
    collega();
    if (location.protocol === "file:") {
      mostraStato("errore-file",
        "Da file:// i dati non si caricano. Esegui offerte serve e apri 127.0.0.1:8099/dashboard.html.");
      return;
    }
    carica();
  }

  avvia();
}());

// Motore dei filtri della dashboard: nessun DOM, nessuna rete, nessuna libreria.
// Deve dare gli stessi id di offerte.rules.matches in Python: ogni cambio qui va riflesso là.
(function (radice) {
  "use strict";

  var VERSIONE_CONTRATTO = 1;
  var ORDINI = ["data-desc", "data-asc", "prezzo-asc", "prezzo-desc", "sconto-desc", "sconto-asc"];
  // Un periodo è <numero>h oppure <numero>g: la scala del menu dipende dalla finestra dei dati,
  // quindi non può stare in una tabella fissa.
  var PERIODO_RE = /^([1-9][0-9]{0,2})(h|g)$/;
  var GRUPPI = ["q", "no", "tutte", "pi", "prezzo", "smin", "cart", "can", "per", "cp"];
  var RISERVATE_YAML = ["y", "n", "yes", "no", "on", "off", "true", "false", "null"];

  // Classe di "carattere di parola" alla Python: \w con le regole Unicode.
  var PAROLA = "[\\p{L}\\p{N}_]";
  var NON_PAROLA = "[^\\p{L}\\p{N}_]";
  // \b e \B tradotti: stringhe, non literal, perché il lookbehind non esiste prima di Safari 16.4.
  var CONFINE = "(?:(?<!" + PAROLA + ")(?=" + PAROLA + ")|(?<=" + PAROLA + ")(?!" + PAROLA + "))";
  var NON_CONFINE = "(?:(?<=" + PAROLA + ")(?=" + PAROLA + ")|(?<!" + PAROLA + ")(?!" + PAROLA + "))";
  var AVVISO_ASCII = "compilata senza regole Unicode: \\b e \\w valgono solo per lettere ASCII," +
    " il risultato può differire dalla regola";
  var ERRORE_FLAG = "flag inline non supportata, usa solo (?i) iniziale";
  var DA_PROTEGGERE = "^$\\.*+?()[]{}|/";

  function haProprieta(oggetto, chiave) {
    return oggetto != null && Object.prototype.hasOwnProperty.call(oggetto, chiave);
  }

  function statoDefault() {
    return {q: [], no: [], tutte: false, pi: false, pmin: null, pmax: null, smin: null,
            cart: [], can: [], per: null, cp: false, ord: "data-desc"};
  }

  function slug(s) {
    var t = String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return t || "feed";
  }

  function slugAscii(s) {
    var t = String(s);
    try {
      t = t.normalize("NFD").replace(/[̀-ͯ]/g, "");
    } catch (e) {
      // normalize assente: si prosegue con il testo originale
    }
    return t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  // --- parole e regex ------------------------------------------------------

  function eRegex(voce) {
    var s = String(voce);
    return s.length > 2 && s.charAt(0) === "/" && s.charAt(s.length - 1) === "/";
  }

  function proteggi(s) {
    // Solo i caratteri che JS accetta come escape anche con il flag u: con u, "\-" è un errore di sintassi.
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      out += DA_PROTEGGERE.indexOf(c) >= 0 ? "\\" + c : c;
    }
    return out;
  }

  function escapeDaTenere(c, inClasse) {
    if (DA_PROTEGGERE.indexOf(c) >= 0) {
      return true;
    }
    return c === "-" && inClasse;  // dentro una classe JS accetta \-, fuori no
  }

  function traduciEscape(c, inClasse, avvisi) {
    if (c === "") {
      return "\\\\";
    }
    if (!inClasse) {
      if (c === "b") { return CONFINE; }
      if (c === "B") { return NON_CONFINE; }
      if (c === "A") { return "^"; }
      if (c === "Z") { return "$"; }
      if (c === "w") { return PAROLA; }
      if (c === "W") { return NON_PAROLA; }
      if (c === "d") { return "\\p{Nd}"; }
      if (c === "D") { return "\\P{Nd}"; }
    } else {
      if (c === "w") { return "\\p{L}\\p{N}_"; }
      if (c === "d") { return "\\p{Nd}"; }
      if (c === "W" || c === "D" || c === "S") {
        avvisi.push("\\" + c + " dentro una classe di caratteri non è traducibile");
        return null;  // segnale: la traduzione non è possibile
      }
    }
    if (/[0-9A-Za-z]/.test(c)) {
      return "\\" + c;  // \n, \t, \xNN, \uNNNN, riferimenti all'indietro
    }
    return escapeDaTenere(c, inClasse) ? "\\" + c : c;
  }

  function traduciRegex(srcPython) {
    var originale = String(srcPython);
    var src = originale;
    var avvisi = [];
    var out = "";
    var inClasse = false;
    var i = 0;
    if (src.slice(0, 4) === "(?i)") {
      src = src.slice(4);  // il flag i c'è sempre
    }
    while (i < src.length) {
      var c = src.charAt(i);
      if (c === "\\") {
        var tradotto = traduciEscape(src.charAt(i + 1), inClasse, avvisi);
        if (tradotto === null) {
          return {src: originale, avvisi: avvisi, tradotta: false};
        }
        out += tradotto;
        i += 2;
        continue;
      }
      if (!inClasse && c === "[") {
        inClasse = true;
        out += c;
        i += 1;
        if (src.charAt(i) === "^") { out += "^"; i += 1; }
        if (src.charAt(i) === "]") { out += "\\]"; i += 1; }  // "]" subito dopo "[" è letterale in Python
        continue;
      }
      if (inClasse && c === "]") {
        inClasse = false;
        out += c;
        i += 1;
        continue;
      }
      if (!inClasse && src.slice(i, i + 3) === "(?P") {
        if (src.charAt(i + 3) === "<") { out += "(?<"; i += 4; continue; }
        if (src.charAt(i + 3) === "=") {
          var fine = src.indexOf(")", i + 4);
          if (fine < 0) { out += src.slice(i); i = src.length; continue; }
          out += "\\k<" + src.slice(i + 4, fine) + ">";
          i = fine + 1;
          continue;
        }
      }
      if (!inClasse && src.charAt(i) === "(" && src.charAt(i + 1) === "?") {
        var chiusura = src.indexOf(")", i + 2);
        var corpo = chiusura < 0 ? "" : src.slice(i + 2, chiusura);
        if (corpo.length > 0 && /^[aimsuxL]+$/.test(corpo)) {
          return {src: originale, avvisi: avvisi, tradotta: false, errore: ERRORE_FLAG};
        }
      }
      out += c;
      i += 1;
    }
    return {src: out, avvisi: avvisi, tradotta: true};
  }

  function compilaRegex(sorgente) {
    var t = traduciRegex(sorgente);
    if (t.errore) {
      return {ok: false, errore: t.errore};
    }
    var avvisi = t.avvisi.slice();
    if (t.tradotta) {
      try {
        return {ok: true, tipo: "regex", re: new RegExp(t.src, "iu"), avvisi: avvisi};
      } catch (e) {
        // lookbehind non supportato, o costrutto che JS rifiuta: si ripiega sulla regex grezza
      }
    }
    avvisi.push(AVVISO_ASCII);
    try {
      return {ok: true, tipo: "regex", re: new RegExp(String(sorgente), "i"), avvisi: avvisi};
    } catch (e2) {
      return {ok: false, errore: String((e2 && e2.message) || e2)};
    }
  }

  function compilaVoce(voce, parolaIntera) {
    var s = String(voce);
    if (eRegex(s)) {
      return compilaRegex(s.slice(1, -1));
    }
    // Senza "solo parola intera" la voce si cerca dentro le parole, come in una casella di ricerca:
    // chi scrive "citofono" si aspetta di trovare anche "videocitofono".
    var sorgente = parolaIntera
      ? "(?:^|" + NON_PAROLA + ")" + proteggi(s) + "(?!" + PAROLA + ")"
      : proteggi(s);
    try {
      return {ok: true, tipo: "parola", re: new RegExp(sorgente, "iu"), avvisi: []};
    } catch (e) {
      return {ok: false, errore: String((e && e.message) || e)};
    }
  }

  function compila(stato) {
    var errori = [];
    var avvisi = [];
    var fuori = {q: [], no: []};
    ["q", "no"].forEach(function (campo) {
      (stato[campo] || []).forEach(function (voce, indice) {
        var c = compilaVoce(voce, !!stato.pi);
        if (!c.ok) {
          errori.push({campo: campo, riga: indice + 1, messaggio: c.errore});
          return;
        }
        (c.avvisi || []).forEach(function (a) {
          avvisi.push({campo: campo, riga: indice + 1, messaggio: a});
        });
        fuori[campo].push(c.re);
      });
    });
    return {ok: errori.length === 0, errori: errori, avvisi: avvisi, q: fuori.q, no: fuori.no};
  }

  // --- selezione -----------------------------------------------------------

  function periodoSecondi(per) {
    var m = per ? PERIODO_RE.exec(String(per)) : null;
    return m ? Number(m[1]) * (m[2] === "h" ? 3600 : 86400) : null;
  }

  function nomiCanali(cartelle) {
    var set = new Set();
    if (cartelle) {
      Object.keys(cartelle).forEach(function (c) {
        (cartelle[c] || []).forEach(function (n) { set.add(n); });
      });
    }
    return set;
  }

  function insiemeCanali(stato, cartelle) {
    var cart = stato.cart || [];
    var can = stato.can || [];
    if (!cart.length && !can.length) {
      return null;
    }
    var set = new Set();
    cart.forEach(function (c) {
      ((cartelle && cartelle[c]) || []).forEach(function (n) { set.add(n); });
    });
    can.forEach(function (n) { set.add(n); });
    return set;
  }

  function ordina(righe, ord) {
    var copia = righe.slice();
    var chiave = null;
    if (ord === "prezzo-asc" || ord === "prezzo-desc") { chiave = "p"; }
    if (ord === "sconto-asc" || ord === "sconto-desc") { chiave = "s"; }
    var crescente = ord === "data-asc" || ord === "prezzo-asc" || ord === "sconto-asc";
    copia.sort(function (a, b) {
      if (chiave !== null) {
        var va = a[chiave];
        var vb = b[chiave];
        var ma = va === undefined || va === null;
        var mb = vb === undefined || vb === null;
        if (ma !== mb) { return ma ? 1 : -1; }  // senza valore sempre in fondo, in entrambi i versi
        if (!ma && va !== vb) { return crescente ? va - vb : vb - va; }
      } else if (a.t !== b.t) {
        return crescente ? a.t - b.t : b.t - a.t;
      }
      if (a.t !== b.t) { return b.t - a.t; }
      return b.id - a.id;
    });
    return copia;
  }

  function applica(offerte, stato, opz) {
    opz = opz || {};
    var cartelle = opz.cartelle || null;
    var adesso = typeof opz.adesso === "number" ? opz.adesso : Math.floor(Date.now() / 1000);
    var ora = typeof opz.ora === "function" ? opz.ora : Date.now;
    var budgetMs = typeof opz.budgetMs === "number" ? opz.budgetMs : 1500;

    var compilato = compila(stato);
    var usaTesto = compilato.ok && (compilato.q.length > 0 || compilato.no.length > 0);
    var canali = insiemeCanali(stato, cartelle);
    var secondi = periodoSecondi(stato.per);
    var daQuando = secondi === null ? null : adesso - secondi;
    var filtroPrezzo = stato.pmin !== null || stato.pmax !== null;
    var filtroSconto = stato.smin !== null;

    var righe = [];
    var senzaPrezzo = 0;
    var senzaSconto = 0;
    var troppoLento = false;
    var inizio = ora();
    for (var i = 0; i < offerte.length; i++) {
      if (i > 0 && i % 200 === 0 && ora() - inizio > budgetMs) {
        troppoLento = true;
        break;
      }
      var o = offerte[i];
      if (daQuando !== null && !(o.t >= daQuando)) { continue; }
      if (canali !== null && !(o.k || []).some(function (c) { return canali.has(c); })) { continue; }
      if (stato.cp && !o.c) { continue; }
      var haPrezzo = o.p !== undefined && o.p !== null;
      var haSconto = o.s !== undefined && o.s !== null;
      var prezzoOk = !filtroPrezzo || (haPrezzo
        && (stato.pmin === null || o.p >= stato.pmin) && (stato.pmax === null || o.p <= stato.pmax));
      var scontoOk = !filtroSconto || (haSconto && o.s >= stato.smin);
      if (!prezzoOk && haPrezzo) { continue; }   // prezzo c'è ma è fuori intervallo: scartata e basta
      if (!scontoOk && haSconto) { continue; }
      if (usaTesto && !passaTesto(o, stato, compilato)) { continue; }
      if (!prezzoOk && scontoOk) { senzaPrezzo += 1; }
      if (!scontoOk && prezzoOk) { senzaSconto += 1; }
      if (prezzoOk && scontoOk) { righe.push(o); }
    }
    return {righe: ordina(righe, stato.ord), senzaPrezzo: senzaPrezzo, senzaSconto: senzaSconto,
            troppoLento: troppoLento, compilato: compilato};
  }

  function passaTesto(o, stato, compilato) {
    var testo = String(o.x === undefined || o.x === null ? "" : o.x);
    var i;
    for (i = 0; i < compilato.no.length; i++) {
      if (compilato.no[i].test(testo)) { return false; }
    }
    if (!compilato.q.length) { return true; }
    if (stato.tutte) {
      for (i = 0; i < compilato.q.length; i++) {
        if (!compilato.q[i].test(testo)) { return false; }
      }
      return true;
    }
    for (i = 0; i < compilato.q.length; i++) {
      if (compilato.q[i].test(testo)) { return true; }
    }
    return false;
  }

  // --- gruppi di filtri ----------------------------------------------------

  function gruppiAttivi(stato) {
    var out = [];
    if (stato.q.length) { out.push("q"); }
    if (stato.no.length) { out.push("no"); }
    if (stato.tutte && stato.q.length >= 2) { out.push("tutte"); }
    if (stato.pi && (stato.q.length || stato.no.length)) { out.push("pi"); }
    if (stato.pmin !== null || stato.pmax !== null) { out.push("prezzo"); }
    if (stato.smin !== null) { out.push("smin"); }
    if (stato.cart.length) { out.push("cart"); }
    if (stato.can.length) { out.push("can"); }
    if (stato.per !== null) { out.push("per"); }
    if (stato.cp) { out.push("cp"); }
    return out;
  }

  function copiaStato(stato) {
    return {q: stato.q.slice(), no: stato.no.slice(), tutte: stato.tutte, pi: stato.pi,
            pmin: stato.pmin, pmax: stato.pmax,
            smin: stato.smin, cart: stato.cart.slice(), can: stato.can.slice(), per: stato.per,
            cp: stato.cp, ord: stato.ord};
  }

  function togliGruppo(stato, gruppo) {
    var s = copiaStato(stato);
    if (gruppo === "q") { s.q = []; s.tutte = false; }
    if (gruppo === "no") { s.no = []; }
    if (gruppo === "tutte") { s.tutte = false; }
    if (gruppo === "pi") { s.pi = false; }
    if (gruppo === "prezzo") { s.pmin = null; s.pmax = null; }
    if (gruppo === "smin") { s.smin = null; }
    if (gruppo === "cart") { s.cart = []; }
    if (gruppo === "can") { s.can = []; }
    if (gruppo === "per") { s.per = null; }
    if (gruppo === "cp") { s.cp = false; }
    return s;
  }

  // --- stato nell'URL ------------------------------------------------------

  function decodifica(s) {
    var grezzo = String(s).replace(/\+/g, " ");
    try {
      return decodeURIComponent(grezzo);
    } catch (e) {
      return grezzo;  // percentuale isolata o sequenza non valida: si tiene il testo com'è
    }
  }

  function numeroValido(v) {
    if (v === undefined || v === null || v === "") { return null; }
    var n = typeof v === "number" ? v : Number(String(v).replace(",", "."));
    if (typeof n !== "number" || !isFinite(n) || n < 0) { return null; }
    return n;
  }

  function interoValido(v) {
    if (v === undefined || v === null || v === "") { return null; }
    var n = Number(String(v));
    if (!isFinite(n) || Math.floor(n) !== n || n < 1 || n > 99) { return null; }
    return n;
  }

  function aggiungiUnici(lista, voci) {
    voci.forEach(function (v) {
      if (v && lista.indexOf(v) === -1) { lista.push(v); }
    });
  }

  function leggiUrl(search, cartelle) {
    var stato = statoDefault();
    var testo = String(search === undefined || search === null ? "" : search).replace(/^\?/, "");
    if (!testo) { return stato; }
    var noti = cartelle ? nomiCanali(cartelle) : null;
    testo.split("&").forEach(function (pezzo) {
      if (!pezzo) { return; }
      var taglio = pezzo.indexOf("=");
      var chiave = decodifica(taglio === -1 ? pezzo : pezzo.slice(0, taglio));
      var valore = taglio === -1 ? "" : decodifica(pezzo.slice(taglio + 1));
      if (chiave === "q" || chiave === "no") {
        if (valore.trim()) { stato[chiave].push(valore.trim()); }
      } else if (chiave === "tutte") {
        stato.tutte = valore === "1";
      } else if (chiave === "cp") {
        stato.cp = valore === "1";
      } else if (chiave === "pi") {
        stato.pi = valore === "1";
      } else if (chiave === "pmin" || chiave === "pmax") {
        stato[chiave] = numeroValido(valore);
      } else if (chiave === "smin") {
        stato.smin = interoValido(valore);
      } else if (chiave === "cart") {
        aggiungiUnici(stato.cart, valore.split(",").map(function (v) { return v.trim().toLowerCase(); })
          .filter(function (v) { return !cartelle || haProprieta(cartelle, v); }));
      } else if (chiave === "can") {
        aggiungiUnici(stato.can, valore.split(",").map(function (v) { return v.trim().toLowerCase(); })
          .filter(function (v) { return !noti || noti.has(v); }));
      } else if (chiave === "per") {
        stato.per = periodoSecondi(valore) === null ? null : valore;
      } else if (chiave === "ord") {
        stato.ord = ORDINI.indexOf(valore) >= 0 ? valore : "data-desc";
      }
    });
    if (stato.pmin !== null && stato.pmax !== null && stato.pmin > stato.pmax) {
      var scambio = stato.pmin;
      stato.pmin = stato.pmax;
      stato.pmax = scambio;
    }
    return stato;
  }

  function scriviUrl(stato) {
    var parti = [];
    stato.q.forEach(function (v) { parti.push("q=" + encodeURIComponent(v)); });
    stato.no.forEach(function (v) { parti.push("no=" + encodeURIComponent(v)); });
    if (stato.tutte) { parti.push("tutte=1"); }
    if (stato.pi) { parti.push("pi=1"); }
    if (stato.pmin !== null) { parti.push("pmin=" + String(stato.pmin)); }
    if (stato.pmax !== null) { parti.push("pmax=" + String(stato.pmax)); }
    if (stato.smin !== null) { parti.push("smin=" + String(stato.smin)); }
    if (stato.cart.length) {
      parti.push("cart=" + stato.cart.map(function (v) { return encodeURIComponent(v); }).join(","));
    }
    if (stato.can.length) {
      parti.push("can=" + stato.can.map(function (v) { return encodeURIComponent(v); }).join(","));
    }
    if (stato.per !== null) { parti.push("per=" + encodeURIComponent(stato.per)); }
    if (stato.cp) { parti.push("cp=1"); }
    if (stato.ord !== "data-desc") { parti.push("ord=" + encodeURIComponent(stato.ord)); }
    return parti.join("&");
  }

  // --- regole --------------------------------------------------------------

  function statoDaRegola(regola, cartelle) {
    var stato = statoDefault();
    stato.q = (regola.parole || []).slice();
    stato.no = (regola.escludi || []).slice();
    stato.tutte = !!regola.tutte;
    stato.pi = true;  // le parole di una regola in config valgono come parola intera
    stato.pmin = numeroValido(regola.prezzo_min);
    stato.pmax = numeroValido(regola.prezzo_max);
    stato.smin = interoValido(regola.sconto_min);
    stato.cp = !!regola.solo_coupon;
    var noti = nomiCanali(cartelle);
    (regola.canali || []).forEach(function (voce) {
      var v = String(voce).toLowerCase();
      if (noti.has(v)) {
        aggiungiUnici(stato.can, [v]);   // il canale vince sulla cartella, come fa load_config
      } else if (cartelle && haProprieta(cartelle, v)) {
        aggiungiUnici(stato.cart, [v]);
      }
    });
    return stato;
  }

  function listeUguali(a, b) {
    if (a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) { return false; }
    }
    return true;
  }

  function insiemiUguali(a, b) {
    if (a === null || b === null) { return a === b; }
    if (a.size !== b.size) { return false; }
    var uguali = true;
    a.forEach(function (v) { if (!b.has(v)) { uguali = false; } });
    return uguali;
  }

  function regolaUguale(stato, regola, cartelle) {
    if (stato.per !== null) { return false; }
    var altro = statoDaRegola(regola, cartelle);
    if (!listeUguali(stato.q, altro.q) || !listeUguali(stato.no, altro.no)) { return false; }
    if (stato.tutte !== altro.tutte || stato.cp !== altro.cp || !stato.pi !== !altro.pi) { return false; }
    if (stato.pmin !== altro.pmin || stato.pmax !== altro.pmax || stato.smin !== altro.smin) { return false; }
    return insiemiUguali(insiemeCanali(stato, cartelle), insiemeCanali(altro, cartelle));
  }

  function nomeSuggerito(stato) {
    var base = "regola";
    for (var i = 0; i < stato.q.length; i++) {
      if (!eRegex(stato.q[i])) {
        base = slugAscii(stato.q[i]) || "regola";
        break;
      }
    }
    if (stato.pmax !== null) {
      base += "-sotto-" + String(stato.pmax).replace(".", "-");
    }
    return base;
  }

  function voceYaml(v, parolaIntera) {
    var s = String(v);
    if (!eRegex(s) && parolaIntera) {
      return JSON.stringify(s);
    }
    // Senza parola intera la voce diventa una regex, così la regola in config seleziona
    // esattamente quello che la pagina stava mostrando.
    var corpo = eRegex(s) ? s : "/" + proteggi(s) + "/";
    return "'" + corpo.replace(/'/g, "''") + "'";
  }

  function nomeYaml(n) {
    var s = String(n);
    if (/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(s) && RISERVATE_YAML.indexOf(s) === -1) {
      return s;
    }
    return JSON.stringify(s);
  }

  function canaliYaml(stato, cartelle) {
    var noti = nomiCanali(cartelle);
    var voci = [];
    var coperti = new Set();
    var esclusi = [];
    stato.cart.forEach(function (c) {
      var nomi = (cartelle && cartelle[c]) || null;
      if (!nomi) {
        esclusi.push(c);
        return;
      }
      if (noti.has(c)) {
        // La cartella si chiama come un canale: load_config darebbe la precedenza al canale, quindi
        // si elencano i canali della cartella uno per uno.
        nomi.forEach(function (n) {
          if (!coperti.has(n)) { voci.push(n); coperti.add(n); }
        });
      } else {
        voci.push(c);
        nomi.forEach(function (n) { coperti.add(n); });
      }
    });
    stato.can.forEach(function (n) {
      if (!noti.has(n)) {
        esclusi.push(n);   // non più in config: load_config rifiuterebbe la regola
        return;
      }
      if (!coperti.has(n)) { voci.push(n); coperti.add(n); }
    });
    return {voci: voci, esclusi: esclusi};
  }

  function yamlRegola(stato, opzioni, cartelle) {
    opzioni = opzioni || {};
    var canali = canaliYaml(stato, cartelle);
    var haCriteri = stato.q.length > 0 || stato.pmin !== null || stato.pmax !== null
      || stato.smin !== null || stato.cp || canali.voci.length > 0;
    if (!haCriteri) {
      return null;
    }
    var righe = ["  - nome: " + nomeYaml(opzioni.nome || nomeSuggerito(stato))];
    var scrivi = function (v) { return voceYaml(v, !!stato.pi); };
    if (stato.q.length) {
      righe.push("    parole: [" + stato.q.map(scrivi).join(", ") + "]");
    }
    if (stato.no.length) {
      righe.push("    escludi: [" + stato.no.map(scrivi).join(", ") + "]");
    }
    if (stato.pmin !== null) { righe.push("    prezzo_min: " + String(stato.pmin)); }
    if (stato.pmax !== null) { righe.push("    prezzo_max: " + String(stato.pmax)); }
    if (stato.smin !== null) { righe.push("    sconto_min: " + String(stato.smin)); }
    if (stato.cp) { righe.push("    solo_coupon: true"); }
    if (canali.voci.length) {
      righe.push("    canali: [" + canali.voci.map(function (v) { return JSON.stringify(v); }).join(", ") + "]");
    }
    if (stato.tutte && stato.q.length >= 2) { righe.push("    tutte: true"); }
    righe.push("    notify: " + (opzioni.notify ? "true" : "false"));
    return {yaml: righe.join("\n") + "\n", esclusi: canali.esclusi};
  }

  radice.Filtri = {
    VERSIONE_CONTRATTO: VERSIONE_CONTRATTO,
    ORDINI: ORDINI,
    GRUPPI: GRUPPI,
    statoDefault: statoDefault,
    slug: slug,
    traduciRegex: traduciRegex,
    compilaVoce: compilaVoce,
    compila: compila,
    periodoSecondi: periodoSecondi,
    insiemeCanali: insiemeCanali,
    applica: applica,
    ordina: ordina,
    gruppiAttivi: gruppiAttivi,
    togliGruppo: togliGruppo,
    copiaStato: copiaStato,
    leggiUrl: leggiUrl,
    scriviUrl: scriviUrl,
    statoDaRegola: statoDaRegola,
    regolaUguale: regolaUguale,
    nomeSuggerito: nomeSuggerito,
    yamlRegola: yamlRegola
  };
}(globalThis));

"""Fonte HTML: una pagina, un selettore CSS per elemento, selettori per i campi. Nessun codice da scrivere."""

from __future__ import annotations

from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser, LexborNode as Node

from ..config import ConfigError
from ..dedupe import text_key
from ..parser import BR_RE, Message, _clean_text
from . import registra
from .base import FetchContext, FetchResult, Source, parse_date, to_number, url_con_schema

CAMPI = {"titolo", "testo", "link", "immagine", "prezzo", "prezzo_barrato", "id", "data"}


def _assoluto(base: str, href: str | None) -> str | None:
    """URL assoluto di un href, oppure None se non porta da nessuna parte (ancora, pagina stessa, javascript:)."""
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    url = urljoin(base, href)
    return None if url.split("#")[0].rstrip("/") == base.split("#")[0].rstrip("/") else url


def _campo(node: Node, spec: str | None) -> str | None:
    """'css', 'css@attr' o '@attr' (attributo dell'elemento stesso)."""
    if not spec:
        return None
    css, _, attr = spec.partition("@")
    target = node if not css.strip() else node.css_first(css.strip())
    if target is None:
        return None
    value = target.attributes.get(attr.strip()) if attr else target.text(deep=True)
    return value.strip() if value else None


@registra
class HtmlSource(Source):
    tipo = "html"
    chiavi = frozenset({"url", "elemento", "campi", "massimo"})

    def configura(self) -> None:
        self.url = url_con_schema(self, str(self.opzione("url", obbligatoria=True)))
        self.elemento = str(self.opzione("elemento", obbligatoria=True))
        self.campi = {str(k): str(v) for k, v in (self.opzione("campi") or {}).items()}
        self.nodi_trovati = 0  # aggiornato da parse(), letto da fetch() per segnalare la fonte vuota
        extra = set(self.campi) - CAMPI
        if extra:
            raise ConfigError(f"fonte '{self.nome}' (html): campi sconosciuti {sorted(extra)}; ammessi {sorted(CAMPI)}")

    def fetch(self, ctx: FetchContext) -> FetchResult:
        resp = ctx.client.get(self.url)
        items = self.parse(resp.text, ctx.now)
        if not self.nodi_trovati:
            ctx.log.warning("fonte %s: il selettore '%s' non trova elementi", self.nome, self.elemento)
            return FetchResult(items, vuota=True)
        return FetchResult(items)

    def parse(self, html: str, now) -> list[Message]:
        tree = HTMLParser(BR_RE.sub("\n", html))
        nodi = tree.css(self.elemento)[: int(self.opzione("massimo") or 50)]
        self.nodi_trovati = len(nodi)
        items: list[Message] = []
        for node in nodi:
            get = lambda campo: _campo(node, self.campi.get(campo))  # noqa: E731
            titolo = get("titolo")
            testo = _clean_text(get("testo") or node.text(deep=True))
            if titolo and titolo not in testo:
                testo = f"{titolo}\n\n{testo}".strip()
            if not testo:
                continue
            altri = [u for a in node.css("a[href]") if (u := _assoluto(self.url, a.attributes.get("href")))]
            link = _assoluto(self.url, get("link"))
            if link is None and self.campi.get("link") is None:
                # Senza campo `link` vale il primo anchor utile, non il primo in assoluto: "#" e i pulsanti
                # che rimandano alla pagina stessa darebbero lo stesso id a tutti gli elementi.
                link = altri[0] if altri else None
            immagine = get("immagine")
            if immagine is None:
                img = node.css_first("img[src]")
                immagine = img.attributes.get("src") if img else None
            immagine = urljoin(self.url, immagine) if immagine else None
            links = ([link] if link else []) + altri
            items.append(Message(
                channel=self.nome, id=get("id") or link or text_key(testo), date=parse_date(get("data")) or now,
                text=testo, struck=[s.text(deep=True).strip() for tag in ("s", "strike", "del") for s in node.css(tag)],
                links=list(dict.fromkeys(links)), image=immagine, permalink=link or self.url,
                price=to_number(get("prezzo")), old_price=to_number(get("prezzo_barrato")),
            ))
        return items

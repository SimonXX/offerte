"""Fonte HTML: una pagina, un selettore CSS per elemento, selettori per i campi. Nessun codice da scrivere."""

from __future__ import annotations

from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser, LexborNode as Node

from ..config import ConfigError
from ..dedupe import text_key
from ..parser import BR_RE, Message, _clean_text
from . import registra
from .base import FetchContext, FetchResult, Source, parse_date, to_number

CAMPI = {"titolo", "testo", "link", "immagine", "prezzo", "prezzo_barrato", "id", "data"}


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
        self.url = str(self.opzione("url", obbligatoria=True))
        self.elemento = str(self.opzione("elemento", obbligatoria=True))
        self.campi = {str(k): str(v) for k, v in (self.opzione("campi") or {}).items()}
        extra = set(self.campi) - CAMPI
        if extra:
            raise ConfigError(f"fonte '{self.nome}' (html): campi sconosciuti {sorted(extra)}; ammessi {sorted(CAMPI)}")

    def fetch(self, ctx: FetchContext) -> FetchResult:
        resp = ctx.client.get(self.url)
        return FetchResult(self.parse(resp.text, ctx.now))

    def parse(self, html: str, now) -> list[Message]:
        tree = HTMLParser(BR_RE.sub("\n", html))
        items: list[Message] = []
        for node in tree.css(self.elemento)[: int(self.opzione("massimo") or 50)]:
            get = lambda campo: _campo(node, self.campi.get(campo))  # noqa: E731
            titolo = get("titolo")
            testo = _clean_text(get("testo") or node.text(deep=True))
            if titolo and titolo not in testo:
                testo = f"{titolo}\n\n{testo}".strip()
            if not testo:
                continue
            link = get("link")
            if link is None:
                a = node.css_first("a[href]")
                link = a.attributes.get("href") if a else None
            link = urljoin(self.url, link) if link else None
            immagine = get("immagine")
            if immagine is None:
                img = node.css_first("img[src]")
                immagine = img.attributes.get("src") if img else None
            immagine = urljoin(self.url, immagine) if immagine else None
            links = ([link] if link else []) + [urljoin(self.url, a.attributes["href"]) for a in node.css("a[href]") if a.attributes.get("href")]
            items.append(Message(
                channel=self.nome, id=get("id") or link or text_key(testo), date=parse_date(get("data")) or now,
                text=testo, struck=[s.text(deep=True).strip() for tag in ("s", "strike", "del") for s in node.css(tag)],
                links=list(dict.fromkeys(links)), image=immagine, permalink=link or self.url,
                price=to_number(get("prezzo")), old_price=to_number(get("prezzo_barrato")),
            ))
        return items

"""Scelta del link dell'offerta, pulizia dai parametri di tracciamento, chiave di dedupe."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TELEGRAM_HOSTS = {"t.me", "telegram.me", "telegram.dog", "telegram.org", "telesco.pe"}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
# Pulsanti e link "seguici" che non sono mai l'offerta.
SOCIAL_HOSTS = {
    "linktr.ee", "linkin.bio", "whatsapp.com", "chat.whatsapp.com", "instagram.com", "facebook.com", "youtube.com",
    "youtu.be", "yt.openinapp.co", "tiktok.com", "x.com", "twitter.com", "play.google.com", "apps.apple.com",
}
SHORT_HOSTS = {
    "amzn.to", "amzn.eu", "a.co", "amzlink.to", "bit.ly", "bitly.com", "tinyurl.com", "cutt.ly", "t.ly", "rb.gy",
    "is.gd", "ow.ly", "tiny.cc", "shorturl.at", "ebay.us", "s.click.aliexpress.com", "fkrt.it", "rebrand.ly",
    "lnk.to", "short.io", "trib.al", "buff.ly", "goo.gl", "shor.by", "mtkv.me", "x.gd", "ofclub.click", "amzn.cl",
}
SHORT_PATH_RE = re.compile(r"^/[A-Za-z0-9_\-]{4,16}/?$")
RETAIL_HOST_RE = re.compile(r"(?:^|\.)(?:amazon|ebay|aliexpress|mediaworld|unieuro|euronics)\.[a-z.]+$")
AMAZON_HOST_RE = re.compile(r"(?:^|\.)amazon\.[a-z.]+$")
ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|product|d)/([A-Z0-9]{10})(?![A-Z0-9])")
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

TRACKING_EXACT = {
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "ttclid", "twclid", "igshid", "mc_cid",
    "mc_eid", "_ga", "_gl", "ref", "ref_", "refrid", "linkcode", "linkid", "ascsubtag", "sr", "qid", "keywords",
    "crid", "sprefix", "dib", "dib_tag", "content-id", "th", "psc", "spm", "scm", "pdp_npi", "algo_pvid",
    "algo_exp_id", "_trkparms", "_trksid", "amdata", "si", "feature", "btn_ref", "btn_type", "_encoding",
}
TRACKING_PREFIX = ("utm_", "pf_rd_", "pd_rd_", "_hs", "oly_", "vero_")
AFFILIATE_EXACT = {
    "tag", "campid", "customid", "mkcid", "mkrid", "mkevt", "toolid", "awc", "tduid", "zanpid", "irgwc",
    "irclickid", "clickid", "subid", "sub_id", "afftrack", "cjevent", "affid", "a_aid", "a_bid",
}
AFFILIATE_PREFIX = ("aff_", "affiliate")


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def normalize_input(url: str) -> str:
    """Decodifica le entità HTML (capita `&amp;amp;` nei post) e aggiunge lo schema se manca."""
    url = html.unescape(url.strip())
    if "://" not in url:
        url = "https://" + url
    return url


def is_telegram(url: str) -> bool:
    h = _host(url)
    return h in TELEGRAM_HOSTS or h.endswith((".t.me", ".telegram.org"))


def is_social(url: str) -> bool:
    h = _host(url)
    return any(h == s or h.endswith("." + s) for s in SOCIAL_HOSTS)


def is_image_url(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(IMAGE_EXT)


def pick_offer_link(links: list[str]) -> str | None:
    """Primo link esterno che non sia Telegram né un'immagine (i canali linkano foto per forzare l'anteprima)."""
    for raw in links:
        url = normalize_input(raw)
        if _host(url) and not is_telegram(url) and not is_social(url) and not is_image_url(url):
            return url
    return None


def is_short_link(url: str) -> bool:
    """Host accorciatore noto, oppure URL con un solo segmento corto e senza query (bit.ly/xyz, amzlink.to/abc)."""
    h = _host(url)
    if h in SHORT_HOSTS:
        return True
    if RETAIL_HOST_RE.search(h):
        return False
    parts = urlsplit(url)
    return bool(SHORT_PATH_RE.match(parts.path)) and not parts.query


def _is_tracking(name: str, host: str) -> bool:
    n = name.lower()
    return n in TRACKING_EXACT or n.startswith(TRACKING_PREFIX) or (n == "hash" and ".ebay." in f".{host}")


def _is_affiliate(name: str) -> bool:
    n = name.lower()
    return n in AFFILIATE_EXACT or n.startswith(AFFILIATE_PREFIX)


def _find_asin(path: str, query: list[tuple[str, str]]) -> str | None:
    m = ASIN_PATH_RE.search(path)
    if m:
        return m.group(1)
    for k, v in query:
        if k.lower() == "asin" and ASIN_RE.match(v):
            return v
    return None


def clean_url(url: str) -> str:
    """URL da mostrare: senza frammento e parametri di tracciamento, con i tag affiliate intatti."""
    url = normalize_input(url)
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        return url
    netloc = host if parts.port in (None, 80, 443) else f"{host}:{parts.port}"
    path = parts.path or "/"
    query = parse_qsl(parts.query, keep_blank_values=True)
    if AMAZON_HOST_RE.search(host):
        asin = _find_asin(path, query)
        if asin and ASIN_PATH_RE.search(path):
            path = f"/dp/{asin}"
        path = re.sub(r"/ref=[^/?#]*", "", path) or "/"
    query = [(k, v) for k, v in query if not _is_tracking(k, host)]
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def dedupe_key(url: str) -> str:
    """Chiave di dedupe: host senza www, percorso, query senza tracciamento né affiliate; Amazon ridotto all'ASIN."""
    parts = urlsplit(clean_url(url))
    host = (parts.hostname or "").removeprefix("www.")
    query = parse_qsl(parts.query, keep_blank_values=True)
    if AMAZON_HOST_RE.search(host):
        asin = _find_asin(parts.path, query)
        if asin:
            return f"url:{host}/dp/{asin}"
    kept = sorted((k.lower(), v) for k, v in query if not _is_affiliate(k))
    return "url:" + host + parts.path.rstrip("/") + (f"?{urlencode(kept)}" if kept else "")

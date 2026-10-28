"""Parser dell'HTML di https://t.me/s/<canale>."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser, LexborNode as Node

BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
STYLE_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")
IMAGE_SELECTORS = (
    ".tgme_widget_message_photo_wrap",
    ".tgme_widget_message_video_thumb",
    ".link_preview_image",
    ".link_preview_right_image",
)


@dataclass
class Message:
    channel: str
    id: int
    date: datetime
    text: str
    struck: list[str]  # testi barrati (<s>), di solito il prezzo pieno
    links: list[str]  # in ordine di preferenza: pulsanti, link nel testo, anteprima
    image: str | None
    permalink: str


@dataclass
class Page:
    messages: list[Message]  # solo i messaggi con testo, esclusi quelli di servizio
    ids: list[int]  # tutti gli id presenti nella pagina, utili per la paginazione
    has_preview: bool
    title: str | None


def parse_page(html: str, channel: str) -> Page:
    tree = HTMLParser(BR_RE.sub("\n", html))
    title_node = tree.css_first(".tgme_channel_info_header_title")
    page = Page(
        messages=[],
        ids=[],
        has_preview=tree.css_first(".tgme_channel_info") is not None,
        title=title_node.text(deep=True).strip() if title_node else None,
    )
    for node in tree.css(".tgme_widget_message[data-post]"):
        post = node.attributes.get("data-post") or ""
        if "/" not in post or not post.rsplit("/", 1)[1].isdigit():
            continue
        msg_id = int(post.rsplit("/", 1)[1])
        page.ids.append(msg_id)
        message = _parse_message(node, channel, msg_id)
        if message is not None:
            page.messages.append(message)
    return page


def _parse_message(node: Node, channel: str, msg_id: int) -> Message | None:
    if "service_message" in (node.attributes.get("class") or ""):
        return None
    time_node = node.css_first("time[datetime]")
    text_node = node.css_first(".tgme_widget_message_text.js-message_text") or node.css_first(".tgme_widget_message_text")
    if time_node is None or text_node is None:
        return None
    text = _clean_text(text_node.text(deep=True))
    if not text:
        return None

    struck = [s.text(deep=True).strip() for tag in ("s", "strike", "del") for s in text_node.css(tag)]

    links: list[str] = []
    for a in node.css(".tgme_widget_message_inline_button[href]"):
        links.append(a.attributes["href"] or "")
    for a in text_node.css("a[href]"):
        links.append(a.attributes["href"] or "")
    preview = node.css_first(".tgme_widget_message_link_preview[href]")
    if preview is not None:
        links.append(preview.attributes["href"] or "")
    links = [u for u in dict.fromkeys(links) if u and not u.startswith(("?", "#", "tg://"))]

    image = None
    for selector in IMAGE_SELECTORS:
        found = node.css_first(selector)
        if found is not None:
            m = STYLE_URL_RE.search(found.attributes.get("style") or "")
            if m:
                image = m.group(1)
                break

    return Message(
        channel=channel,
        id=msg_id,
        date=datetime.fromisoformat(time_node.attributes["datetime"]),
        text=text,
        struck=[s for s in struck if s],
        links=links,
        image=image,
        permalink=f"https://t.me/{channel}/{msg_id}",
    )


def _clean_text(raw: str) -> str:
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in raw.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

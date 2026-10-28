"""Server HTTP minimale (stdlib) che serve var/feeds/ su 127.0.0.1:8099."""

from __future__ import annotations

import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger(__name__)


class FeedHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".xml": "application/rss+xml; charset=utf-8",
        ".json": "application/feed+json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (firma della stdlib)
        log.debug("%s %s", self.address_string(), format % args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def serve(directory: Path, host: str, port: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), partial(FeedHandler, directory=str(directory)))
    log.info("servo %s su http://%s:%d/", directory, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

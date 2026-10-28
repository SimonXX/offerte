"""Client HTTP: intervallo di cortesia, backoff su 429 e 5xx, risoluzione dei redirect."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    pass


class Client:
    def __init__(
        self,
        user_agent: str,
        courtesy: float = 3.0,
        *,
        timeout: float = 20.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "it-IT,it;q=0.9,en;q=0.7"},
            timeout=timeout,
            follow_redirects=True,
            max_redirects=10,
            transport=transport,
        )
        self.courtesy = courtesy
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    @property
    def http(self) -> httpx.Client:
        """Il client httpx sottostante, per le fonti che parlano con altre API (Apify e simili)."""
        return self._client

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get(self, url: str) -> httpx.Response:
        """GET con intervallo di cortesia e backoff esponenziale; FetchError quando i tentativi finiscono."""
        delay = 2.0
        errore = ""
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as e:
                errore = f"{type(e).__name__}: {e}"
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in RETRY_STATUS:
                    raise FetchError(f"HTTP {resp.status_code} per {url}")
                errore = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, float(retry_after))
            if attempt < self.max_retries:
                log.warning("%s: %s, riprovo fra %.0f s", url, errore, delay)
                self._sleep(min(delay, 120.0))
                delay *= 2
        raise FetchError(f"{url}: {errore} dopo {self.max_retries + 1} tentativi")

    def _wait(self) -> None:
        if self._last is not None:
            resto = self.courtesy - (self._clock() - self._last)
            if resto > 0:
                self._sleep(resto)
        self._last = self._clock()

    def resolve(self, url: str) -> str:
        """Segue i redirect (HEAD, poi GET se il server rifiuta HEAD) e torna l'URL finale; se fallisce, l'originale."""
        try:
            resp = self._client.head(url)
            if str(resp.url) == url and resp.status_code >= 400:
                with self._client.stream("GET", url) as resp:
                    return str(resp.url)
            return str(resp.url)
        except httpx.HTTPError as e:
            log.debug("redirect non risolto per %s: %s", url, type(e).__name__)
            return url

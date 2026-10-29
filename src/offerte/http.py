"""Client HTTP: intervallo di cortesia, backoff su 429 e 5xx, risoluzione dei redirect."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
# Errori che non cambieranno al tentativo dopo: ritentarli regala solo 30 secondi di attesa.
NON_RITENTABILI = (httpx.UnsupportedProtocol, httpx.TooManyRedirects, httpx.DecodingError)
ATTESA_MASSIMA = 120.0  # tetto di una singola attesa
BUDGET_ATTESA = 60.0    # tetto del tempo speso ad aspettare in una sola chiamata


def _retry_after(valore: str) -> float | None:
    """Retry-After in secondi o come data HTTP; None se non si capisce."""
    valore = valore.strip()
    if valore.isdigit():
        return float(valore)
    if not valore:
        return None
    try:
        secondi = (parsedate_to_datetime(valore) - datetime.now(timezone.utc)).total_seconds()
    except (TypeError, ValueError, IndexError):
        return None
    return secondi if secondi > 0 else None


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
        speso = 0.0
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                resp = self._client.get(url)
            except NON_RITENTABILI as e:
                raise FetchError(f"{url}: {type(e).__name__}") from None
            except httpx.HTTPError as e:
                errore = f"{type(e).__name__}: {e}"
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in RETRY_STATUS:
                    raise FetchError(f"HTTP {resp.status_code} per {url}")
                errore = f"HTTP {resp.status_code}"
                indicata = _retry_after(resp.headers.get("Retry-After", ""))
                if indicata is not None:
                    delay = max(delay, indicata)
            if attempt < self.max_retries:
                attesa = min(delay, ATTESA_MASSIMA)
                if speso + attesa > BUDGET_ATTESA:
                    # Un canale in 429 persistente terrebbe fermo tutto il giro oltre il TimeoutStartSec dell'unit.
                    raise FetchError(f"{url}: {errore}, attesa richiesta oltre il budget di {BUDGET_ATTESA:.0f} s")
                log.warning("%s: %s, riprovo fra %.0f s", url, errore, attesa)
                self._sleep(attesa)
                speso += attesa
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

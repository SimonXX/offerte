"""Fonte Apify: un actor dello store, eseguito al volo (sync) o letto dall'ultima esecuzione riuscita (ultimo).

Solo REST, token in .env (APIFY_TOKEN), nessun SDK. Richiede `ogni` per non consumare il credito a ogni giro.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from ..config import ConfigError
from ..http import FetchError
from . import registra
from .base import FetchContext, FetchResult, Source, record_to_message

API = "https://api.apify.com/v2"
CAMPI_DEFAULT = {
    "id": "id|asin|url", "titolo": "title|name", "testo": "description|text", "link": "url|link",
    "immagine": "image|thumbnail|imageUrl", "prezzo": "price|currentPrice|price.value",
    "prezzo_barrato": "listPrice|originalPrice|oldPrice", "data": "date|scrapedAt|timestamp",
}


def _path(d: Any, path: str) -> Any:
    for parte in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(parte)
    return d


def mappa(record: dict[str, Any], campi: dict[str, str]) -> dict[str, Any]:
    """Applica la mappatura campo -> 'percorso.a|alternativa' al record dell'actor."""
    out: dict[str, Any] = {}
    for campo, spec in campi.items():
        for alternativa in str(spec).split("|"):
            valore = _path(record, alternativa.strip())
            if valore not in (None, "", []) and not isinstance(valore, (dict, list)):
                out[campo] = valore
                break
    return out


@registra
class ApifySource(Source):
    tipo = "apify"
    chiavi = frozenset({"actor", "input", "modo", "campi", "token", "timeout", "massimo", "memoria"})

    def configura(self) -> None:
        self.actor = str(self.opzione("actor", obbligatoria=True)).replace("/", "~")
        self.modo = str(self.opzione("modo") or "ultimo")
        if self.modo not in ("sync", "ultimo"):
            raise ConfigError(f"fonte '{self.nome}' (apify): modo '{self.modo}' non valido (sync | ultimo)")
        if not self.ogni:
            raise ConfigError(f"fonte '{self.nome}' (apify): serve 'ogni' (minuti) per non consumare il credito a ogni giro")
        self.token_var = str(self.opzione("token") or "APIFY_TOKEN")
        self.campi = {**CAMPI_DEFAULT, **{str(k): str(v) for k, v in (self.opzione("campi") or {}).items()}}
        self.timeout = min(int(self.opzione("timeout") or 120), 300)  # oltre 300 s l'endpoint sync risponde 408

    def fetch(self, ctx: FetchContext) -> FetchResult:
        token = os.environ.get(self.token_var)
        if not token:
            raise FetchError(f"variabile {self.token_var} assente (mettila in .env)")
        headers = {"Authorization": f"Bearer {token}"}
        params: dict[str, Any] = {"clean": "true", "limit": int(self.opzione("massimo") or 200)}
        try:
            if self.modo == "sync":
                params["timeout"] = self.timeout
                if self.opzione("memoria"):
                    params["memory"] = int(self.opzione("memoria"))
                resp = ctx.client.http.post(f"{API}/acts/{self.actor}/run-sync-get-dataset-items", params=params,
                                            json=self.opzione("input") or {}, headers=headers, timeout=self.timeout + 30)
            else:
                params["status"] = "SUCCEEDED"
                resp = ctx.client.http.get(f"{API}/acts/{self.actor}/runs/last/dataset/items", params=params,
                                           headers=headers, timeout=60)
        except httpx.HTTPError as e:
            raise FetchError(f"Apify: {type(e).__name__}") from None
        if resp.status_code >= 400:
            raise FetchError(f"Apify HTTP {resp.status_code}: {resp.text[:200]}")
        dati = resp.json()
        if not isinstance(dati, list):
            raise FetchError("Apify: risposta non è un elenco di elementi")
        items = [m for m in (record_to_message(mappa(r, self.campi), self.nome, ctx.now) for r in dati if isinstance(r, dict)) if m]
        return FetchResult(items)

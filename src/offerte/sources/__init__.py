"""Fonti agganciabili: telegram, rss, html, comando, apify, più classi esterne via entry point o percorso modulo:Classe."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from typing import Any

from ..config import ConfigError
from .base import FetchContext, FetchResult, Source, record_to_message

TIPI: dict[str, type[Source]] = {}
CHIAVI_COMUNI = {"nome", "tipo", "cartella", "attivo", "ogni"}


def registra(cls: type[Source]) -> type[Source]:
    TIPI[cls.tipo] = cls
    return cls


def tipo_fonte(nome: str) -> type[Source]:
    """Tipo incorporato, entry point del gruppo `offerte.fonti`, oppure `pacchetto.modulo:Classe`."""
    if nome in TIPI:
        return TIPI[nome]
    for ep in entry_points(group="offerte.fonti"):
        if ep.name == nome:
            TIPI[nome] = ep.load()
            return TIPI[nome]
    if ":" in nome:
        modulo, _, classe = nome.partition(":")
        try:
            cls = getattr(import_module(modulo), classe)
        except (ImportError, AttributeError) as e:
            raise ConfigError(f"tipo di fonte '{nome}' non importabile: {e}") from None
        TIPI[nome] = cls
        return cls
    raise ConfigError(f"tipo di fonte sconosciuto: '{nome}' (disponibili: {', '.join(sorted(TIPI))})")


def crea_fonte(spec: dict[str, Any]) -> Source:
    nome = str(spec.get("nome") or "").strip()
    if not nome:
        raise ConfigError("fonte senza 'nome'")
    cls = tipo_fonte(str(spec.get("tipo") or "telegram"))
    opzioni = {k: v for k, v in spec.items() if k not in CHIAVI_COMUNI}
    return cls(nome=nome, cartella=str(spec.get("cartella") or "varie").strip(), opzioni=opzioni,
               ogni=int(spec.get("ogni") or 0), attivo=bool(spec.get("attivo", True)))


from . import apify, comando, html, rss, telegram  # noqa: E402,F401  (registrano i tipi incorporati)

__all__ = ["FetchContext", "FetchResult", "Source", "TIPI", "crea_fonte", "record_to_message", "registra", "tipo_fonte"]

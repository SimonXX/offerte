"""Fonte esterna di prova: dimostra l'aggancio di una classe via `tipo: modulo:Classe`."""

from datetime import datetime, timezone

from offerte.parser import Message
from offerte.sources.base import FetchContext, FetchResult, Source


class FonteFinta(Source):
    tipo = "finta"
    chiavi = frozenset({"n"})
    chiamate = 0

    def fetch(self, ctx: FetchContext) -> FetchResult:
        FonteFinta.chiamate += 1
        n = int(self.opzione("n") or 1)
        return FetchResult([
            Message(self.nome, f"f{i}", datetime(2026, 10, 27, 10, i, tzinfo=timezone.utc), f"Prodotto finto {i}\n{10 + i},00€",
                    [], [f"https://finta.example/p/{i}"], None, f"https://finta.example/p/{i}")
            for i in range(n)
        ])

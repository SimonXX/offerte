"""Fonte comando: qualunque script, in qualunque linguaggio, che stampa record JSON (una riga per record o un array)."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

from ..http import FetchError
from . import registra
from .base import FetchContext, FetchResult, Source, record_to_message


def iter_records(stdout: str) -> list[dict[str, Any]]:
    testo = stdout.strip()
    if not testo:
        return []
    if testo.startswith("["):
        dati = json.loads(testo)
        return [d for d in dati if isinstance(d, dict)]
    out = []
    for riga in testo.splitlines():
        riga = riga.strip()
        if riga:
            d = json.loads(riga)
            if isinstance(d, dict):
                out.append(d)
    return out


@registra
class CommandSource(Source):
    tipo = "comando"
    chiavi = frozenset({"comando", "cwd", "timeout"})

    def configura(self) -> None:
        cmd = self.opzione("comando", obbligatoria=True)
        self.argv = shlex.split(cmd) if isinstance(cmd, str) else [str(x) for x in cmd]

    def fetch(self, ctx: FetchContext) -> FetchResult:
        env = {**os.environ, "OFFERTE_FONTE": self.nome, "OFFERTE_ULTIMO_FETCH": ctx.state.last_fetch or ""}
        try:
            proc = subprocess.run(self.argv, cwd=str(self.opzione("cwd") or ctx.config_dir), env=env,
                                  capture_output=True, text=True, timeout=float(self.opzione("timeout") or 120))
        except (OSError, subprocess.TimeoutExpired) as e:
            raise FetchError(f"comando {self.argv[0]}: {e}") from None
        if proc.returncode != 0:
            raise FetchError(f"comando uscito con {proc.returncode}: {proc.stderr.strip()[-300:]}")
        try:
            records = iter_records(proc.stdout)
        except json.JSONDecodeError as e:
            raise FetchError(f"output non JSON: {e}") from None
        items = [m for m in (record_to_message(r, self.nome, ctx.now) for r in records) if m]
        return FetchResult(items)

"""Logging su stderr e su var/offerte.log con rotazione."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(var_dir: Path, verbose: bool = False) -> None:
    var_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("offerte")
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    if root.handlers:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr),
        RotatingFileHandler(var_dir / "offerte.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"),
    ]
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    # Il silenzio di httpx e httpcore lo impone offerte.http all'import: l'URL completo contiene i token.

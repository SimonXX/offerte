"""deploy/stato.sh su un bare repo temporaneo: branch assente, branch presente, remoto irraggiungibile."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[1]
STATO = RADICE / "deploy" / "stato.sh"


def ambiente(tmp_path, remoto):
    """Git isolato dalla configurazione dell'utente: niente firma, niente hook, niente identità globale."""
    return {**os.environ, "OFFERTE_VAR_DIR": str(tmp_path / "var"), "OFFERTE_DATA_REMOTE": str(remoto),
            "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig-assente"),
            "GIT_CONFIG_SYSTEM": str(tmp_path / "gitconfig-assente"),
            "GIT_TERMINAL_PROMPT": "0"}


@pytest.fixture
def progetto(tmp_path):
    """Copia dello script in un repository usa e getta: le prove non devono toccare il repository vero."""
    radice = tmp_path / "progetto"
    (radice / "deploy").mkdir(parents=True)
    shutil.copy(STATO, radice / "deploy" / "stato.sh")
    subprocess.run(["git", "init", "-q", radice], check=True, env=ambiente(tmp_path, ""))
    return radice


def esegui(progetto, tmp_path, azione, remoto):
    return subprocess.run(["bash", str(progetto / "deploy" / "stato.sh"), azione],
                          capture_output=True, text=True, env=ambiente(tmp_path, remoto))


def test_branch_assente_e_primo_avvio(progetto, tmp_path):
    bare = tmp_path / "dati.git"
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True, env=ambiente(tmp_path, ""))
    esito = esegui(progetto, tmp_path, "restore", bare)
    assert esito.returncode == 0 and "primo avvio" in esito.stdout


def test_salva_e_ripristina(progetto, tmp_path):
    bare = tmp_path / "dati.git"
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True, env=ambiente(tmp_path, ""))
    (tmp_path / "var").mkdir(exist_ok=True)
    (tmp_path / "var" / "offerte.sqlite").write_bytes(b"SQLite format 3\x00 finto")

    salvato = esegui(progetto, tmp_path, "save", bare)
    assert salvato.returncode == 0, salvato.stderr
    (tmp_path / "var" / "offerte.sqlite").unlink()

    ripristinato = esegui(progetto, tmp_path, "restore", bare)
    assert ripristinato.returncode == 0, ripristinato.stderr
    assert (tmp_path / "var" / "offerte.sqlite").read_bytes() == b"SQLite format 3\x00 finto"
    assert "stato ripristinato" in ripristinato.stdout


def test_remoto_irraggiungibile_non_sovrascrive(progetto, tmp_path):
    esito = esegui(progetto, tmp_path, "restore", tmp_path / "non-esiste.git")
    assert esito.returncode == 1
    assert "non raggiungibile" in esito.stderr
    assert not (tmp_path / "var" / "offerte.sqlite").exists()


def test_azione_sconosciuta(progetto, tmp_path):
    esito = esegui(progetto, tmp_path, "boh", tmp_path / "dati.git")
    assert esito.returncode == 2 and "uso:" in esito.stderr

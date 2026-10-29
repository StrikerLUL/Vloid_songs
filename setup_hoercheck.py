# setup_hoercheck.py – richtet den Hör-Check ein (faster-whisper „small“, MIT-Lizenz)
#
# Legt in tools/hoercheck eine eigene Python-Umgebung an, damit die Spracherkennung die Bibliotheken der App nicht
# berührt, installiert dort faster-whisper und lädt das japanische Modell einmal herunter (etwa 500 MB). Danach hört
# die App nach jedem Singen ab, ob man den Text versteht; ausschalten lässt sich das im Tab „Gesang“. Löschen: den
# Ordner tools/hoercheck löschen.
#
#   uv run setup_hoercheck.py
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import config  # noqa: E402
import hoercheck  # noqa: E402

PAKETE = ("faster-whisper>=1.0", "requests")
PYTHON = "3.12"


def _ausfuehren(befehl: list, **kwargs) -> bool:
    print("  " + " ".join(befehl), flush=True)
    try:
        return subprocess.run(befehl, **kwargs).returncode == 0
    except OSError as e:
        print(f"Fehler: {e}")
        return False


def setup() -> bool:
    uv = shutil.which("uv")
    if not uv:
        print("uv fehlt. Einmal in PowerShell ausführen: winget install astral-sh.uv")
        return False
    venv = os.path.join(hoercheck.FOLDER, "venv")
    print(f"Richte den Hör-Check in {hoercheck.FOLDER} ein")
    if not os.path.isfile(hoercheck.python()) and not _ausfuehren([uv, "venv", venv, "--python",
                                                                   config.venv_python(PYTHON)]):
        return False
    if not _ausfuehren([uv, "pip", "install", "--python", hoercheck.python(), *PAKETE]):
        print("Die Installation hat nicht geklappt; die Songs entstehen dann ohne Hör-Check wie bisher.")
        return False
    print("Lade das Modell (etwa 500 MB) und höre eine Probe ab ...", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        if not hoercheck.probe(tmp):
            print(f"Die Erkennung läuft noch nicht ({hoercheck.problem()}). Noch einmal starten hilft oft beim "
                  "Download.")
            return False
    print("Fertig. Nach dem nächsten Song steht unter dem Player, ob man jede Zeile versteht.")
    return True


if __name__ == "__main__":
    argparse.ArgumentParser(description="Richtet den Hör-Check ein (faster-whisper small)").parse_args()
    sys.exit(0 if setup() else 1)

# setup_begleitung.py – richtet die KI-Begleitung ein (Versuch): der Anticipatory Music Transformer schreibt
# Begleitstimmen zu Melodie, Bass und Schlagzeug
#
# Legt in tools/begleitung eine eigene Python-Umgebung an, damit PyTorch die Bibliotheken der App nicht berührt,
# installiert dort das Paket anticipation (Stanford, Apache 2.0) und lädt das Modell einmal herunter: mit NVIDIA-
# Grafikkarte das mittlere (etwa 1,5 GB), sonst das kleine (etwa 0,5 GB, ein Song dauert dann trotzdem lange).
# Danach unter Pfade „Begleitung vom KI-Modell schreiben lassen“ einschalten. Löschen: den Ordner tools/begleitung
# löschen.
#
#   uv run setup_begleitung.py          mit Grafikkarte etwa 4 GB, ohne deutlich weniger
#   uv run setup_begleitung.py --cpu    PyTorch nur für den Prozessor (kleiner, langsamer)
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import accompaniment  # noqa: E402

PAKETE = ("torch", "transformers>=4.40,<5", "tqdm",
          "anticipation @ https://github.com/jthickstun/anticipation/archive/refs/heads/main.zip")
PYTHON = "3.12"


def _ausfuehren(befehl: list, **kwargs) -> bool:
    print("  " + " ".join(befehl), flush=True)
    try:
        return subprocess.run(befehl, **kwargs).returncode == 0
    except OSError as e:
        print(f"Fehler: {e}")
        return False


def setup(cpu: bool = False) -> bool:
    uv = shutil.which("uv")
    if not uv:
        print("uv fehlt. Einmal in PowerShell ausführen: winget install astral-sh.uv")
        return False
    venv = os.path.join(accompaniment.FOLDER, "venv")
    print(f"Richte die KI-Begleitung in {accompaniment.FOLDER} ein")
    if not os.path.isfile(accompaniment.python()) and not _ausfuehren([uv, "venv", venv, "--python", PYTHON]):
        return False
    backend = "cpu" if cpu else "auto"
    if not _ausfuehren([uv, "pip", "install", "--python", accompaniment.python(), "--torch-backend", backend,
                        *PAKETE]):
        print("Die Installation hat nicht geklappt; die App komponiert die Begleitung dann selbst wie bisher.")
        return False
    print("Lade das Modell und lasse es acht Sekunden Begleitung schreiben ...", flush=True)
    melodie = [[0.5 * i, 0.5 * i + 0.4, 60 + 2 * (i % 4), accompaniment.MELODY] for i in range(16)]
    with tempfile.TemporaryDirectory() as tmp:
        toene = accompaniment.write(melodie, 8.0, 7, tmp, reuse=False)
    if toene is None:
        print(f"Das Modell läuft noch nicht (Ausgabe in {os.path.join(accompaniment.FOLDER, accompaniment.LOG_FILE)}). "
              "Noch einmal starten hilft oft beim Download.")
        return False
    print(f"Fertig, {len(toene)} Töne zur Probe. Jetzt unter Pfade „Begleitung vom KI-Modell schreiben lassen“ "
          "einschalten.")
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Richtet die KI-Begleitung ein (Anticipatory Music Transformer, Versuch)")
    p.add_argument("--cpu", action="store_true", help="PyTorch nur für den Prozessor, ohne Grafikkarte")
    sys.exit(0 if setup(p.parse_args().cpu) else 1)

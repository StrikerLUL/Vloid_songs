# setup_bewertung.py – richtet die automatische Bewertung mehrerer Fassungen ein (Meta Audiobox Aesthetics)
#
# Legt in tools/bewertung eine eigene Python-Umgebung an, damit PyTorch die Bibliotheken der App nicht berührt,
# installiert dort Audiobox Aesthetics und lädt das Modell einmal herunter. uv wählt PyTorch passend zur
# Grafikkarte (mit NVIDIA rechnet sie, sonst der Prozessor). Danach bewertet die App mehrere Fassungen eines Songs von
# selbst und lädt die beste; ausschalten lässt sich das im Tab „Pfade“. Löschen: den Ordner tools/bewertung löschen.
#
#   uv run setup_bewertung.py          mit Grafikkarte etwa 3 GB, ohne deutlich weniger
#   uv run setup_bewertung.py --cpu    PyTorch nur für den Prozessor (kleiner, langsamer)
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import config  # noqa: E402
import rating  # noqa: E402

PAKETE = ("audiobox_aesthetics==0.0.4", "soundfile")
PYTHON = "3.12"     # ohne Setup.exe; sonst nimmt die Umgebung deren Python (config.venv_python)


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
    venv = os.path.join(rating.FOLDER, "venv")
    print(f"Richte die Bewertung in {rating.FOLDER} ein")
    anlegen = [uv, "venv", venv, "--python", config.venv_python(PYTHON)]
    if not os.path.isfile(rating.python()) and not _ausfuehren(anlegen):
        return False
    backend = "cpu" if cpu else "auto"
    if not _ausfuehren([uv, "pip", "install", "--python", rating.python(), "--torch-backend", backend, *PAKETE]):
        print("Die Installation hat nicht geklappt; die App bewertet dann nicht, sonst ändert sich nichts.")
        return False
    print("Lade das Modell und probiere es einmal aus ...", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe.wav")
        import numpy as np
        import soundfile as sf
        t = np.arange(44100 * 3) / 44100
        sf.write(probe, np.stack([np.sin(2 * np.pi * 440 * t)] * 2, axis=1) * 0.3, 44100)
        ergebnis = rating.rate([probe])[0]
    if ergebnis is None:
        print("Das Modell läuft noch nicht (Meldung steht oben). Noch einmal starten hilft oft beim Download.")
        return False
    print(f"Fertig. Probeton: {ergebnis.describe()}")
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Richtet die automatische Bewertung (Audiobox Aesthetics) ein")
    p.add_argument("--cpu", action="store_true", help="PyTorch nur für den Prozessor, ohne Grafikkarte")
    sys.exit(0 if setup(p.parse_args().cpu) else 1)

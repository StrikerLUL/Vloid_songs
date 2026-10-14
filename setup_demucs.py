# setup_demucs.py – richtet „Mix wie die Vorbilder“ ein: Demucs zerlegt die Vorbild-Songs in Gesang, Schlagzeug, Bass
# und Rest
#
# Legt in tools/demucs eine eigene Python-Umgebung an, damit PyTorch die Bibliotheken der App nicht berührt,
# installiert dort Demucs (Meta, MIT-Lizenz) und lädt das Modell htdemucs einmal herunter (etwa 80 MB). uv wählt
# PyTorch passend zur Grafikkarte (mit NVIDIA geht das Zerlegen schneller, sonst rechnet der Prozessor, etwa eine
# Minute pro Vorbild). Danach gleicht der Mix Gesang, Schlagzeug, Bass und Rest einzeln an die Vorbilder an;
# ausschalten lässt sich das im Tab „Vorbilder“ („Mix pro Instrument“). Löschen: den Ordner tools/demucs löschen.
#
#   uv run setup_demucs.py          mit Grafikkarte etwa 3 GB, ohne deutlich weniger
#   uv run setup_demucs.py --cpu    PyTorch nur für den Prozessor (kleiner, langsamer)
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import separation  # noqa: E402

# torchaudio ab 2.9 liest Audio nur noch mit FFmpeg; der Worker liest selbst, Demucs 4.0.1 braucht es trotzdem
PAKETE = ("demucs==4.0.1", "soundfile", "torch<2.9", "torchaudio<2.9")
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
    venv = os.path.join(separation.FOLDER, "venv")
    print(f"Richte Demucs in {separation.FOLDER} ein")
    if not os.path.isfile(separation.python()) and not _ausfuehren([uv, "venv", venv, "--python", PYTHON]):
        return False
    backend = "cpu" if cpu else "auto"
    if not _ausfuehren([uv, "pip", "install", "--python", separation.python(), "--torch-backend", backend, *PAKETE]):
        print("Die Installation hat nicht geklappt; der Mix bleibt dann wie bisher, sonst ändert sich nichts.")
        return False
    print("Lade das Modell und probiere es einmal aus ...", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe.wav")
        import numpy as np
        import soundfile as sf
        t = np.arange(44100 * 4) / 44100
        sf.write(probe, np.stack([np.sin(2 * np.pi * 220 * t)] * 2, axis=1) * 0.3, 44100)
        fertig = separation.separate([probe], [os.path.join(tmp, "probe")])
    if not fertig:
        print("Demucs läuft noch nicht (Meldung steht oben). Noch einmal starten hilft oft beim Download.")
        return False
    print("Fertig. Ab jetzt zerlegt die App jedes Vorbild einmal und merkt sich, wie es gemischt ist.")
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Richtet „Mix wie die Vorbilder“ ein (Demucs)")
    p.add_argument("--cpu", action="store_true", help="PyTorch nur für den Prozessor, ohne Grafikkarte")
    sys.exit(0 if setup(p.parse_args().cpu) else 1)

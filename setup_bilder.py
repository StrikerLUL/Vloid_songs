# setup_bilder.py – richtet die KI-Hintergründe fürs Musikvideo ein (LCM Dreamshaper v7, MIT-Lizenz)
#
# Legt in tools/bilder eine eigene Python-Umgebung an, damit PyTorch die Bibliotheken der App nicht berührt,
# installiert dort diffusers und lädt das Bildmodell einmal herunter. uv wählt PyTorch passend zur Grafikkarte (mit
# NVIDIA malt sie, 4 GB Grafikspeicher reichen, sonst der Prozessor). Danach malt die App beim Video für jede Sektion
# ein eigenes Bild; ausschalten lässt sich das im Tab „Video“. Löschen: den Ordner tools/bilder löschen.
#
#   uv run setup_bilder.py              etwa 4 GB Modell, dazu PyTorch
#   uv run setup_bilder.py --cpu        PyTorch nur für den Prozessor (kleiner, langsamer)
#   uv run setup_bilder.py --ergaenzen  nur fehlende Pakete in eine schon eingerichtete Umgebung (macht die Setup.exe)
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import bilder  # noqa: E402
import config  # noqa: E402

PAKETE = ("diffusers>=0.30", "transformers", "accelerate", "safetensors", "requests")
PYTHON = "3.12"


def _ausfuehren(befehl: list, **kwargs) -> bool:
    print("  " + " ".join(befehl), flush=True)
    try:
        return subprocess.run(befehl, **kwargs).returncode == 0
    except OSError as e:
        print(f"Fehler: {e}")
        return False


def _uv():
    uv = shutil.which("uv")
    if not uv:
        print("uv fehlt. Einmal in PowerShell ausführen: winget install astral-sh.uv")
    return uv


def ergaenzen() -> bool:
    """Nach einem Update: neue Pakete aus PAKETE in die eingerichtete Umgebung; ohne Umgebung passiert nichts."""
    if not bilder.available():
        return True
    uv = _uv()
    if not uv:
        return False
    print("Ergänze die KI-Bilder", flush=True)
    if not _ausfuehren([uv, "pip", "install", "--python", bilder.python(), "--torch-backend", "auto", "torch",
                        *PAKETE]):
        print("Das Ergänzen hat nicht geklappt; unter Hilfe › Einrichten lässt es sich wiederholen.")
        return False
    return True


def setup(cpu: bool = False) -> bool:
    uv = _uv()
    if not uv:
        return False
    venv = os.path.join(bilder.FOLDER, "venv")
    print(f"Richte die KI-Bilder in {bilder.FOLDER} ein")
    if not os.path.isfile(bilder.python()) and not _ausfuehren([uv, "venv", venv, "--python",
                                                                config.venv_python(PYTHON)]):
        return False
    backend = "cpu" if cpu else "auto"
    if not _ausfuehren([uv, "pip", "install", "--python", bilder.python(), "--torch-backend", backend, "torch",
                        *PAKETE]):
        print("Die Installation hat nicht geklappt; das Video bekommt dann die gezeichneten Szenen wie bisher.")
        return False
    print("Lade das Modell (etwa 4 GB) und male ein Probebild ...", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        bild = bilder.probe(tmp)
        if bild is None:
            print(f"Das Modell läuft noch nicht ({bilder.problem()}). Noch einmal starten hilft oft beim Download.")
            return False
    print("Fertig. Das nächste Video bekommt eigene Bilder pro Sektion.")
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Richtet die KI-Hintergründe fürs Musikvideo ein (LCM Dreamshaper v7)")
    p.add_argument("--cpu", action="store_true", help="PyTorch nur für den Prozessor, ohne Grafikkarte")
    p.add_argument("--ergaenzen", action="store_true", help="nur fehlende Pakete in die eingerichtete Umgebung laden")
    args = p.parse_args()
    sys.exit(0 if (ergaenzen() if args.ergaenzen else setup(args.cpu)) else 1)

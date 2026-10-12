# setup_ace_step.py – richtet den Klang-Veredler ein (ACE-Step 1.5, Versuch)
#
# Lädt ACE-Step 1.5 in einer festen Fassung nach tools/ace-step, legt dort mit uv seine eigene Python-Umgebung an
# (PyTorch für NVIDIA-Grafikkarten, berührt die App nicht), lädt die Modelle und probiert einmal, ob die Grafikkarte
# erkannt wird. Danach macht die App zu jedem Song eine zweite Fassung mit neu eingespielter Band; ausschalten lässt
# sich das in der App unter Pfade. Löschen: den Ordner tools/ace-step löschen.
#
#   uv run setup_ace_step.py      braucht etwa 20 GB Platz (Modelle etwa 10 GB, PyTorch mit CUDA etwa 6 GB)
#
# ACE-Step 1.5 steht unter der MIT-Lizenz: https://github.com/ace-step/ACE-Step-1.5
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import polish  # noqa: E402

COMMIT = "ca1e85fe9430179831e6bc6be790c332190a3866"      # feste Fassung, mit der die App getestet ist
REPO = "https://github.com/ace-step/ACE-Step-1.5.git"
ZIP = f"https://codeload.github.com/ace-step/ACE-Step-1.5/zip/{COMMIT}"
PLATZ_GB = 20


def _ausfuehren(befehl: list, **kwargs) -> bool:
    print("  " + " ".join(befehl), flush=True)
    try:
        return subprocess.run(befehl, **kwargs).returncode == 0
    except OSError as e:
        print(f"Fehler: {e}")
        return False


def _platz_frei() -> float:
    ordner = polish.FOLDER
    while not os.path.exists(ordner):
        ordner = os.path.dirname(ordner)
    return shutil.disk_usage(ordner).free / 1024 ** 3


def _entpacken(archiv: str, ziel: str) -> None:
    """Das ZIP von GitHub nach ziel; der oberste Ordner im Archiv fällt weg."""
    with zipfile.ZipFile(archiv) as z:
        oben = z.namelist()[0].split("/")[0]
        tmp = ziel + ".entpacken"
        shutil.rmtree(tmp, ignore_errors=True)
        for name in z.namelist():
            pfad = os.path.abspath(os.path.join(tmp, name))
            if os.path.commonpath([pfad, os.path.abspath(tmp)]) != os.path.abspath(tmp):
                raise ValueError(f"Unerwarteter Pfad im Archiv: {name}")
        z.extractall(tmp)
    os.replace(os.path.join(tmp, oben), ziel)
    shutil.rmtree(tmp, ignore_errors=True)


def quelle_holen() -> bool:
    ziel = polish.source()
    if os.path.isfile(os.path.join(ziel, "pyproject.toml")):
        print(f"ACE-Step liegt schon in {ziel}")
        return True
    shutil.rmtree(ziel, ignore_errors=True)        # Reste eines abgebrochenen Versuchs
    os.makedirs(polish.FOLDER, exist_ok=True)
    git = shutil.which("git")
    if git:
        # ohne alte Dateistände: es kommen nur die Dateien der festen Fassung
        return _ausfuehren([git, "clone", "--quiet", "--filter=blob:none", "--no-checkout", REPO, ziel]) and \
            _ausfuehren([git, "-C", ziel, "-c", "advice.detachedHead=false", "checkout", "--quiet", COMMIT])
    print("Lade ACE-Step als ZIP (ohne git) ...", flush=True)
    with tempfile.TemporaryDirectory(dir=polish.FOLDER) as tmp:
        archiv = os.path.join(tmp, "ace-step.zip")
        try:
            with urllib.request.urlopen(ZIP, timeout=300) as antwort, open(archiv, "wb") as f:
                shutil.copyfileobj(antwort, f, 1 << 20)
            _entpacken(archiv, ziel)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"Download fehlgeschlagen: {e}")
            return False
    return True


def probe() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        return polish.run({"probe": True}, tmp) or {}


def setup() -> bool:
    uv = shutil.which("uv")
    if not uv:
        print("uv fehlt. Einmal in PowerShell ausführen: winget install astral-sh.uv")
        return False
    frei = _platz_frei()
    if frei < PLATZ_GB and not os.path.isfile(polish.python()):
        print(f"Zu wenig Platz: frei sind {frei:.0f} GB, gebraucht werden etwa {PLATZ_GB} GB.")
        return False
    print(f"Richte den Klang-Veredler in {polish.FOLDER} ein")
    if not quelle_holen():
        return False
    print("Installiere die Umgebung von ACE-Step (PyTorch mit CUDA, das dauert) ...", flush=True)
    if not _ausfuehren([uv, "sync"], cwd=polish.source()):
        print("Die Installation hat nicht geklappt; die App veredelt dann nicht, sonst ändert sich nichts.")
        return False
    print("Lade die Modelle (etwa 10 GB) ...", flush=True)
    if not _ausfuehren([polish.python(), "-m", "acestep.model_downloader", "--model", "main",
                        "--dir", os.path.join(polish.source(), "checkpoints")],
                       cwd=polish.source(), env=polish.environment()):
        print("Der Download hat nicht geklappt. Noch einmal starten macht dort weiter.")
        return False
    print("Probiere ACE-Step einmal aus ...", flush=True)
    gefunden = probe()
    if "cuda" not in gefunden:
        print("ACE-Step startet noch nicht (Meldung steht oben).")
        return False
    with open(os.path.join(polish.FOLDER, polish.READY_FILE), "w", encoding="utf-8") as f:
        json.dump(gefunden, f)
    if not gefunden["cuda"]:
        print("Fertig, aber ohne NVIDIA-Grafikkarte: ACE-Step rechnet dann auf dem Prozessor und braucht sehr lange. "
              "Ausschalten in der App unter Pfade.")
    else:
        print(f"Fertig. Grafikkarte: {gefunden['name']} ({gefunden['memory_gb']:g} GB)")
    return True


if __name__ == "__main__":
    argparse.ArgumentParser(description="Richtet den Klang-Veredler (ACE-Step 1.5) ein").parse_args()
    sys.exit(0 if setup() else 1)

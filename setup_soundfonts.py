# setup_soundfonts.py – lädt bessere Klänge für einzelne Instrumente nach tools/soundfonts
#
# Flügel, E-Pianos, Streicher, Bläser und Holzbläser aus MuseScore, E-Gitarren und FM-Piano von FreePats,
# echte Schlagzeuge von AVL Drumkits. Die App nimmt sie von selbst, sobald sie da sind; ohne sie spielt
# alles weiter aus GeneralUser GS. MS Basic.sf3 spielt nur FluidSynth (setup_fluidsynth.py).
#
#   uv run setup_soundfonts.py            alles (etwa 250 MB Download, 550 MB auf der Platte)
#   uv run setup_soundfonts.py --ohne-verzerrt   ohne die große verzerrte Gitarre (130 MB weniger)
import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
from dataclasses import dataclass

ZIEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "soundfonts")
FREEPATS = "https://github.com/freepats"
AVL = "https://raw.githubusercontent.com/x42/avldrums.lv2/v0.7.4/sf2"


@dataclass(frozen=True)
class Download:
    datei: str          # Name in tools/soundfonts (wie in sound_library.py)
    url: str
    sha256: str         # der heruntergeladenen Datei
    mb: int
    lizenz: str
    archiv: bool = False   # .7z, aus dem nur die .sf2-Datei ausgepackt wird


DOWNLOADS = (
    Download("MS Basic.sf3",
             "https://raw.githubusercontent.com/musescore/MuseScore/v4.6.0/share/sound/MS%20Basic.sf3",
             "5ea2375e8bd7d8e71def1036978c1621e85b66934169b6a2744b27b9b3c2d99c", 51,
             "MIT, MuseScore (https://github.com/musescore/MuseScore)"),
    Download("FM-Piano1 20190916.sf2",
             f"{FREEPATS}/fm-piano1/releases/download/2019-09-16/FM-Piano1-SF2-20190916.7z",
             "543774e268e00eaf13968c53d9a42eada7f13564e559d51534ed552507c971ad", 14,
             "CC0, FreePats (https://freepats.zenvoid.org)", archiv=True),
    Download("EGuitarFSBS-clean bridge small 20260807.sf2",
             f"{FREEPATS}/electric-guitar-FSBS-clean/releases/download/2026-08-07/"
             "EGuitarFSBS-clean-bridge-small-SF2-20260807.7z",
             "bcea7d4c92a1cc6a26e545a218b34e59037d4bab6cf0fce24396428e6934d69c", 7,
             "CC0, FreePats (https://freepats.zenvoid.org)", archiv=True),
    Download("EGuitarFSBS-dist2 bridge 20220911.sf2",
             f"{FREEPATS}/electric-guitar-FSBS-dist2/releases/download/2022-09-11/EGuitarFSBS-dist2-SF2-20220911.7z",
             "0ed99135d955940c1200e09ca9e36e261dfebbe8767ae58da6f298fe29fdd146", 127,
             "CC0, FreePats (https://freepats.zenvoid.org)", archiv=True),
    Download("Red_Zeppelin_4_LV2.sf2", f"{AVL}/Red_Zeppelin_4_LV2.sf2",
             "289fc3e30a4859eb74ae14eb08ddef453e8bf8eab3e501772dcf96fd8328a71a", 26,
             "CC-BY-SA 3.0, AVL Drumkits von Glen MacArthur (http://www.bandshed.net/avldrumkits/)"),
    Download("Black_Pearl_4_LV2.sf2", f"{AVL}/Black_Pearl_4_LV2.sf2",
             "e0542ec19f2816ef4e0d00aeb087e7aa311e888d6f4805f971688bb267c6d405", 19,
             "CC-BY-SA 3.0, AVL Drumkits von Glen MacArthur (http://www.bandshed.net/avldrumkits/)"),
)
VERZERRT = "EGuitarFSBS-dist2 bridge 20220911.sf2"
VERSUCHE = 3


def _laden(url: str, ziel: str) -> str:
    """Lädt url nach ziel und gibt die SHA-256 der Datei zurück."""
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as antwort, open(ziel, "wb") as f:
        while block := antwort.read(1 << 20):
            h.update(block)
            f.write(block)
    return h.hexdigest()


def _auspacken(archiv: str, datei: str, ziel: str) -> None:
    import py7zr
    with tempfile.TemporaryDirectory() as tmp:
        with py7zr.SevenZipFile(archiv) as z:
            namen = [n for n in z.getnames() if os.path.basename(n) == datei]
            if not namen:
                raise RuntimeError(f"{datei} fehlt im Archiv")
            z.extract(path=tmp, targets=namen)
        shutil.move(os.path.join(tmp, namen[0]), ziel)


def hole(d: Download, ordner: str = ZIEL) -> bool:
    ziel = os.path.join(ordner, d.datei)
    if os.path.isfile(ziel):
        print(f"  {d.datei}: schon da")
        return True
    print(f"  {d.datei}: lade {d.mb} MB ...", flush=True)
    os.makedirs(ordner, exist_ok=True)
    tmp = ziel + ".download"
    try:
        # Bricht die Verbindung mittendrin ab, stimmt die Prüfsumme nicht: dann noch einmal laden
        if not any(_laden(d.url, tmp) == d.sha256 for _ in range(VERSUCHE)):
            print(f"Fehler: {d.datei} ist nicht die erwartete Datei. Übersprungen.")
            return False
        if d.archiv:
            _auspacken(tmp, d.datei, ziel)
        else:
            os.replace(tmp, ziel)
    except Exception as e:
        print(f"Fehler bei {d.datei}: {e}")
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return True


def setup(ohne_verzerrt: bool = False, ordner: str = ZIEL) -> bool:
    auswahl = [d for d in DOWNLOADS if not (ohne_verzerrt and d.datei == VERZERRT)]
    print(f"Lade {len(auswahl)} SoundFonts nach {ordner} (zusammen {sum(d.mb for d in auswahl)} MB)")
    ok = all([hole(d, ordner) for d in auswahl])
    with open(os.path.join(ordner, "LIZENZEN.txt"), "w", encoding="utf-8") as f:
        f.write("Herkunft und Lizenz der SoundFonts in diesem Ordner\n\n")
        f.writelines(f"{d.datei}\n  {d.lizenz}\n  {d.url}\n\n" for d in DOWNLOADS)
    print("Fertig." if ok else "Nicht alles hat geklappt, die App nimmt, was da ist.")
    return ok


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Lädt zusätzliche SoundFonts für bessere Instrumente")
    p.add_argument("--ohne-verzerrt", action="store_true", help="ohne die verzerrte E-Gitarre (127 MB)")
    sys.exit(0 if setup(p.parse_args().ohne_verzerrt) else 1)

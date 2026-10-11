# setup_fluidsynth.py – lädt FluidSynth für Windows nach tools/fluidsynth/bin
#
# Mit FluidSynth klingen die Instrumente aus dem SoundFont so, wie der SoundFont gebaut ist (Anschlag öffnet
# den Filter, Ausklang, Vibrato). Ohne läuft die App weiter mit tinysoundfont.
import hashlib
import io
import os
import sys
import urllib.request
import zipfile

VERSION = "2.6.0"
URL = (f"https://github.com/FluidSynth/fluidsynth/releases/download/v{VERSION}/"
       f"fluidsynth-v{VERSION}-win10-x64-cpp11.zip")
SHA256 = "817262deacaa748edb3af6731dffe1766b00146790becfccc949a9f701e76681"
ZIEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "fluidsynth", "bin")


def setup() -> bool:
    print(f"Lade FluidSynth {VERSION} ...")
    with urllib.request.urlopen(URL, timeout=120) as antwort:
        daten = antwort.read()
    if hashlib.sha256(daten).hexdigest() != SHA256:
        print("Fehler: Die heruntergeladene Datei ist nicht die erwartete. Abgebrochen.")
        return False
    os.makedirs(ZIEL, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        for eintrag in z.infolist():
            name = eintrag.filename.replace("\\", "/")
            if "/bin/" in name and name.lower().endswith(".dll"):
                with open(os.path.join(ZIEL, os.path.basename(name)), "wb") as f:
                    f.write(z.read(eintrag))
                print(f"  {os.path.basename(name)}")
    print(f"Fertig: {ZIEL}")
    return True


if __name__ == "__main__":
    sys.exit(0 if setup() else 1)

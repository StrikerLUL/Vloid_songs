# setup_surge.py – lädt Surge XT (VST3) und fünf seiner Klänge nach tools/surge
#
# Surge XT (Surge Synth Team, GPL-3, kostenlos) ist ein großer Synthesizer. Die App lässt damit ihre eigenen Synths
# Supersaw, Pluck, Chip-Lead, Future-Bass-Akkorde und Reese-Bass spielen (surge_sounds.py). Geladen wird nur das
# Plugin (Ausgabe „pluginsonly“, Windows etwa 50 MB, Linux etwa 100 MB) und die fünf Klänge (.fxp) aus dem
# Quellcode derselben Ausgabe. Sie liegen in SurgeXTData neben dem Plugin, wie in der portablen Ausgabe; dort sucht
# Surge seine Daten. Jede Datei wird mit ihrer Prüfsumme verglichen. Ohne Surge spielen die eigenen Synths.
import hashlib
import io
import os
import platform
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import surge_sounds  # noqa: E402

VERSION = "1.3.4"
RELEASE = f"https://github.com/surge-synthesizer/releases-xt/releases/download/{VERSION}/"
SOURCE = f"https://raw.githubusercontent.com/surge-synthesizer/surge/release_xt_{VERSION}/resources/data/"
PAKETE = {   # System: (Datei, SHA-256, MB)
    "Windows": (f"surge-xt-win64-{VERSION}-pluginsonly.zip",
                "564e162c560af07ad4ed47fe1bfcd827cf97a575de30d06c48249aad2e7c35e6", 49),
    "Linux": (f"surge-xt-linux-{VERSION}-pluginsonly.tar.gz",
              "dd431b75f5fa197c4bffa6ca27ca46970f0a94c834119bb1db7decdeec4c28db", 97),
}
PLUGIN = surge_sounds.PLUGIN
VERSUCHE = 3
LIZENZ = ("Surge XT von Surge Synth Team, GPL-3 (https://surge-synthesizer.github.io)\n"
          f"Plugin: {RELEASE}\nKlänge: {SOURCE}\n"
          "Die Klänge sind Werks- und Gast-Klänge von Surge XT: Luna, Vincent Zauhar, Claes Johanson, Vospi.\n")


def _laden(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as antwort:
        return antwort.read()


def _gepruft(url: str, sha: str) -> bytes:
    """Lädt url; bricht die Verbindung ab oder stimmt die Prüfsumme nicht, noch einmal. b"" wenn es nie klappt."""
    for _ in range(VERSUCHE):
        try:
            daten = _laden(url)
        except OSError as e:          # auch urllib.error.URLError und HTTPError
            print(f"    {e}")
            continue
        if hashlib.sha256(daten).hexdigest() == sha:
            return daten
        print("    Prüfsumme stimmt nicht, lade noch einmal")
    return b""


def _ziel(ziel: str, name: str) -> str:
    """Wohin ein Eintrag des Archivs kommt: nur was in Surge XT.vst3 liegt, nichts außerhalb des Ziels; sonst ""."""
    name = name.replace("\\", "/")
    if PLUGIN + "/" not in name + "/":
        return ""
    inner = name[name.index(PLUGIN):]
    target = os.path.normpath(os.path.join(ziel, inner))
    return target if target.startswith(os.path.normpath(ziel) + os.sep) else ""


def unpack(daten: bytes, ziel: str) -> int:
    """Das VST3 aus der ZIP (Windows) oder dem tar.gz (Linux) nach ziel; Rückgabe: Zahl der Dateien."""
    if daten[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(daten)) as z:
            return _schreiben([(e.filename, None if e.is_dir() else e) for e in z.infolist()], z.read, ziel)
    with tarfile.open(fileobj=io.BytesIO(daten), mode="r:gz") as t:
        eintraege = [(e.name, e if e.isfile() else None) for e in t.getmembers()]
        return _schreiben(eintraege, lambda e: t.extractfile(e).read(), ziel)


def _schreiben(eintraege: list, lesen, ziel: str) -> int:
    count = 0
    for name, eintrag in eintraege:
        target = _ziel(ziel, name)
        if eintrag is None or not target:
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(lesen(eintrag))
        count += 1
    return count


def klaenge(ordner: str) -> bool:
    """Die fünf Klänge nach ordner/SurgeXTData, je mit Prüfsumme."""
    ok = True
    for stimme, klang in surge_sounds.SOUNDS.items():
        ziel = os.path.join(ordner, surge_sounds.DATA, *klang.file.split("/"))
        if os.path.isfile(ziel):
            with open(ziel, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() == klang.sha256:
                    print(f"  {stimme}: schon da")
                    continue
        print(f"  {stimme}: {os.path.basename(klang.file)}", flush=True)
        daten = _gepruft(SOURCE + urllib.parse.quote(klang.file), klang.sha256)
        if not daten:
            print(f"Fehler: {klang.file} ließ sich nicht laden.")
            ok = False
            continue
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        with open(ziel, "wb") as f:
            f.write(daten)
    return ok


def setup(ordner: str = None, system: str = None) -> bool:
    ordner = ordner or surge_sounds.FOLDER
    system = system or platform.system()
    if system not in PAKETE:
        print(f"Für {system} lädt die App Surge XT nicht; installiere es von surge-synthesizer.github.io, die Klänge "
              "lädt sie trotzdem.")
    elif os.path.isdir(os.path.join(ordner, PLUGIN)):
        print(f"Surge XT {VERSION}: schon da")
    else:
        name, sha, mb = PAKETE[system]
        print(f"Lade Surge XT {VERSION} ({mb} MB) ...", flush=True)
        daten = _gepruft(RELEASE + name, sha)
        if not daten:
            print("Fehler: Surge XT ließ sich nicht laden. Abgebrochen.")
            return False
        os.makedirs(ordner, exist_ok=True)
        print(f"  {unpack(daten, ordner)} Dateien ausgepackt")
    print("Lade die Klänge ...")
    ok = klaenge(ordner)
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ)
    if ok and (os.path.isdir(os.path.join(ordner, PLUGIN)) or surge_sounds.plugin_path()):
        print(f"Fertig: Surge XT und {len(surge_sounds.SOUNDS)} Klänge in {ordner}")
        return True
    print("Nicht alles hat geklappt; noch einmal starten lädt nur, was fehlt.")
    return False


if __name__ == "__main__":
    sys.exit(0 if setup() else 1)

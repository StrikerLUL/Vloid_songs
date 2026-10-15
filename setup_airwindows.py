# setup_airwindows.py – lädt Airwindows Consolidated (VST3) nach tools/airwindows
#
# Fast 400 Airwindows-Effekte in einem Plugin; die App nutzt daraus Bandsättigung für den Gesang (ToTape9) und ein
# analoges Mischpult (Console7). Die Effekte sind MIT, das Plugin GPL-3 (LICENSE.gpl3 liegt dabei). Es gibt jede
# Woche eine neue Ausgabe unter demselben Release; welche Datei gerade aktuell ist und ihre Prüfsumme stehen in
# artifact_sha256sum.txt daneben. Ohne Plugin läuft die App weiter mit ihrer eigenen Sättigung.
import hashlib
import io
import os
import platform
import sys
import urllib.request
import zipfile

BASE = "https://github.com/baconpaul/airwin2rack/releases/download/DAWPlugin/"
SUMS = BASE + "artifact_sha256sum.txt"
PLUGIN = "Airwindows Consolidated.vst3"
ZIEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "airwindows")


def choose(sums: str, system: str = None) -> tuple:
    """(Dateiname, SHA-256) der passenden Ausgabe aus der Prüfsummenliste; (None, None) für dieses System nicht."""
    system = system or platform.system()
    wanted = {"Windows": ("dawplugin-windows-x64/", "-Windows.zip"), "Linux": ("build-docker-linux/", "-Linux.zip")}
    if system not in wanted:
        return None, None
    folder, ending = wanted[system]
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and folder in parts[1] and parts[1].endswith(ending):
            return os.path.basename(parts[1]), parts[0].lower()
    return None, None


def unpack(daten: bytes, ziel: str) -> int:
    """Das VST3 (und die Lizenz) aus der ZIP nach ziel; Rückgabe: Zahl der Dateien."""
    count = 0
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        for eintrag in z.infolist():
            name = eintrag.filename.replace("\\", "/")
            inner = name[name.index(PLUGIN):] if PLUGIN in name else os.path.basename(name)
            if eintrag.is_dir() or not (PLUGIN in name or inner == "LICENSE.gpl3"):
                continue
            target = os.path.normpath(os.path.join(ziel, inner))
            if not target.startswith(os.path.normpath(ziel) + os.sep):
                continue                      # nichts außerhalb des Zielordners
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(z.read(eintrag))
            count += 1
    return count


def setup() -> bool:
    print("Suche die aktuelle Ausgabe von Airwindows Consolidated ...")
    with urllib.request.urlopen(SUMS, timeout=60) as antwort:
        sums = antwort.read().decode("utf-8", "replace")
    name, sha = choose(sums)
    if not name:
        print(f"Für {platform.system()} gibt es hier keine passende Ausgabe. Abgebrochen.")
        return False
    print(f"Lade {name} ...")
    with urllib.request.urlopen(BASE + name, timeout=300) as antwort:
        daten = antwort.read()
    if hashlib.sha256(daten).hexdigest() != sha:
        print("Fehler: Die heruntergeladene Datei ist nicht die erwartete. Abgebrochen.")
        return False
    os.makedirs(ZIEL, exist_ok=True)
    count = unpack(daten, ZIEL)
    with open(os.path.join(ZIEL, "version.txt"), "w", encoding="utf-8") as f:
        f.write(name + "\n")
    print(f"Fertig: {count} Dateien in {ZIEL}")
    return count > 0


if __name__ == "__main__":
    sys.exit(0 if setup() else 1)

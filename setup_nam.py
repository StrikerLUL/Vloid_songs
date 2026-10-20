# setup_nam.py – lädt zwei Modelle echter Gitarren-Verstärker nach tools/nam
#
# Die Modelle sind für den Neural Amp Modeler (NAM, MIT) gemacht und stammen aus der Sammlung der NAM-Gemeinschaft
# (github.com/pelennor2170/NAM_models, GPL-3): ein Marshall JCM2000 im Crunch-Kanal (Tim R) für Overdrive-Gitarren
# und ein Peavey 6505+ im roten Kanal (Helga Behrens) für Distortion-Gitarren. Zusammen etwa 1 MB; jede Datei wird
# mit ihrer Prüfsumme verglichen. Ohne Modelle verzerrt die App die Gitarren wie bisher selbst (guitar_amp.py).
import hashlib
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import amp_models  # noqa: E402

COMMIT = "944ca6718581c60cc5365586d2f378d740e181f3"
QUELLE = f"https://raw.githubusercontent.com/pelennor2170/NAM_models/{COMMIT}/"
VERSUCHE = 3
LIZENZ = ("Verstärker-Modelle für den Neural Amp Modeler (https://github.com/sdatkinson/neural-amp-modeler, MIT)\n"
          "aus der Sammlung https://github.com/pelennor2170/NAM_models, GPL-3 (GNU General Public License v3)\n\n")


def _laden(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as antwort:
        return antwort.read()


def hole(amp, ordner: str) -> bool:
    ziel = os.path.join(ordner, amp.file)
    if os.path.isfile(ziel):
        with open(ziel, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == amp.sha256:
                print(f"  {amp.name}: schon da")
                return True
    print(f"  {amp.name} (von {amp.author}) ...", flush=True)
    for _ in range(VERSUCHE):
        try:
            daten = _laden(QUELLE + urllib.parse.quote(amp.file))
        except OSError as e:          # auch urllib.error.URLError und HTTPError
            print(f"    {e}")
            continue
        if hashlib.sha256(daten).hexdigest() != amp.sha256:
            print("    Prüfsumme stimmt nicht, lade noch einmal")
            continue
        with open(ziel + ".download", "wb") as f:
            f.write(daten)
        os.replace(ziel + ".download", ziel)
        return True
    print(f"Fehler: {amp.file} ließ sich nicht laden.")
    return False


def setup(ordner: str = None) -> bool:
    ordner = ordner or amp_models.FOLDER
    os.makedirs(ordner, exist_ok=True)
    print(f"Lade {len(amp_models.AMPS)} Verstärker-Modelle nach {ordner}")
    ok = all([hole(amp, ordner) for amp in amp_models.AMPS.values()])
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ)
        f.writelines(f"{a.file}\n  {a.name}, aufgenommen von {a.author}\n  {QUELLE}{urllib.parse.quote(a.file)}\n\n"
                     for a in amp_models.AMPS.values())
    print("Fertig." if ok else "Nicht alles hat geklappt; noch einmal starten lädt nur, was fehlt.")
    return ok


if __name__ == "__main__":
    sys.exit(0 if setup() else 1)

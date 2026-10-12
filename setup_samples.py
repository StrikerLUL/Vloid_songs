# setup_samples.py – lädt echte Orchester-Aufnahmen (VSCO 2 Community Edition) nach tools/samples
#
# Streicher, Blech- und Holzbläser, Harfe, Pauken und Stabspiele, aufgenommen von Versilian Studios, frei für alles
# (CC0). Geladen werden nur die Instrumente, die die App spielt (sample_library.py), Datei für Datei von GitHub.
# Was schon da ist, wird übersprungen; nach einem Abbruch macht der nächste Start dort weiter. Die App nimmt die
# Aufnahmen von selbst; ausschalten lassen sie sich in der App unter Pfade.
#
#   uv run setup_samples.py                       alles (etwa 1,2 GB)
#   uv run setup_samples.py --nur Harp Violin     nur Instrumente, deren Dateiname das enthält
import argparse
import os
import shutil
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import sample_library  # noqa: E402
import sfz  # noqa: E402

COMMIT = "6dd651d55dde97fd4028699be9d4481f26917891"      # feste Fassung, damit immer dieselben Dateien kommen
QUELLE = f"https://raw.githubusercontent.com/sgossner/VSCO-2-CE/{COMMIT}/"
LIZENZ = ("VSCO 2 Community Edition von Versilian Studios (Sam Gossner)\n"
          "  CC0 1.0, https://github.com/sgossner/VSCO-2-CE\n")
VERSUCHE = 3
GLEICHZEITIG = 8


def _laden(url: str, ziel: str) -> bool:
    """Lädt url nach ziel; erst vollständig geladen bekommt die Datei ihren Namen."""
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    tmp = ziel + ".download"
    fehler = None
    for _ in range(VERSUCHE):
        try:
            with urllib.request.urlopen(url, timeout=120) as antwort, open(tmp, "wb") as f:
                laenge = antwort.headers.get("Content-Length")
                shutil.copyfileobj(antwort, f, 1 << 20)
            if laenge is not None and os.path.getsize(tmp) != int(laenge):
                raise OSError("Verbindung mittendrin abgebrochen")
            os.replace(tmp, ziel)
            return True
        except OSError as e:            # auch urllib.error.URLError und HTTPError
            fehler = e
    if os.path.exists(tmp):
        os.remove(tmp)
    print(f"    Fehler bei {os.path.basename(ziel)}: {fehler}")
    return False


def _url(quelle: str, relativ: str) -> str:
    return quelle + urllib.parse.quote(relativ.replace(os.sep, "/"))


def hole(name: str, ordner: str = None, quelle: str = QUELLE) -> bool:
    """Ein Instrument: erst seine SFZ-Datei lesen, dann die fehlenden Aufnahmen laden, zuletzt die SFZ-Datei ablegen."""
    ordner = ordner or sample_library.FOLDER
    ziel = os.path.join(ordner, name)
    if os.path.isfile(ziel):
        print(f"  {name}: schon da")
        return True
    entwurf = ziel + ".sfz-download"
    if not _laden(_url(quelle, name), entwurf):
        return False
    try:
        aufnahmen = sorted({r.sample for r in sfz.parse(entwurf)})
        wurzel = os.path.abspath(ordner)
        if not aufnahmen or any(os.path.commonpath([wurzel, a]) != wurzel for a in aufnahmen):
            print(f"  {name}: unerwarteter Inhalt, übersprungen")
            return False
        fehlen = [a for a in aufnahmen if not os.path.isfile(a)]
        print(f"  {name}: {len(aufnahmen)} Aufnahmen, {len(fehlen)} zu laden", flush=True)
        with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
            ok = all(list(pool.map(lambda a: _laden(_url(quelle, os.path.relpath(a, wurzel)), a), fehlen)))
        if ok:
            os.replace(entwurf, ziel)
        return ok
    finally:
        if os.path.exists(entwurf):
            os.remove(entwurf)


def setup(nur: list = (), ordner: str = None, quelle: str = QUELLE) -> bool:
    ordner = ordner or sample_library.FOLDER
    auswahl = [f for f in sample_library.files() if not nur or any(n.lower() in f.lower() for n in nur)]
    if not auswahl:
        print("Kein Instrument passt zu --nur", " ".join(nur))
        return False
    print(f"Lade {len(auswahl)} Instrumente nach {ordner}")
    ok = all([hole(name, ordner, quelle) for name in auswahl])
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ)
    print("Fertig." if ok else "Nicht alles hat geklappt: noch einmal starten, es macht dort weiter.")
    return ok


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Lädt echte Orchester-Aufnahmen (VSCO 2, CC0) für die App")
    p.add_argument("--nur", nargs="+", default=[], metavar="NAME",
                   help="nur Instrumente, deren SFZ-Datei das enthält (z. B. Violin, Harp, Trumpet)")
    sys.exit(0 if setup(p.parse_args().nur) else 1)

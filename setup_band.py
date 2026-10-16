# setup_band.py – lädt Flügel, E-Bass und E-Gitarre aus echten Aufnahmen nach tools/samples/Band (v6 Nr. 3)
#
# Salamander Grand Piano: ein Yamaha C5, aufgenommen von Alexander Holm (CC BY 3.0). Von seinen 16 Anschlag-Schichten
# lädt das Skript jede zweite (8), das reicht für leise bis laute Töne und spart die Hälfte.
# Growlybass und Emily-Gitarre von Karoryfer Samples (CC0): ein E-Bass mit Fingern gespielt und eine E-Gitarre,
# direkt ins Pult gespielt (sauber, für den Verstärker in guitar_amp ideal). Von ihren wechselnden Aufnahmen pro Ton
# lädt das Skript zwei; Kratz- und Griffgeräusche lässt es weg.
# Jede Aufnahme kommt einzeln von GitHub, aus einer festen Fassung. Was schon da ist, wird übersprungen; nach einem
# Abbruch macht der nächste Start dort weiter. Erst wenn alle Aufnahmen eines Instruments da sind, schreibt das
# Skript seine SFZ-Datei (Klavier.sfz, Bass.sfz, Gitarre.sfz), und erst dann spielt die App es.
#
#   uv run setup_band.py                    alles (etwa 550 MB)
#   uv run setup_band.py --nur bass         nur ein Instrument: klavier, bass oder gitarre
import argparse
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import band_library  # noqa: E402
import sfz  # noqa: E402
from setup_samples import _laden  # noqa: E402

GITHUB = "https://raw.githubusercontent.com/"
GLEICHZEITIG = 4
VELTRACK = 30               # die Anschlag-Schichten sind schon leiser aufgenommen, der Anschlag regelt nur nach
ROUND_ROBINS = 2            # so viele wechselnde Aufnahmen pro Ton und Anschlag (Bass, Gitarre)
PIANO_RELEASE = 0.45        # so schnell legt sich der Dämpfer auf die Saite (die obersten Töne haben keinen)
# die geladenen Anschlag-Schichten des Flügels: (Name, leisester, lautester Anschlag), je zwei zusammengelegt
PIANO_LAYERS = (("v2", 1, 34), ("v4", 35, 43), ("v6", 44, 50), ("v8", 51, 64), ("v10", 65, 80), ("v12", 81, 96),
                ("v14", 97, 112), ("v16", 113, 127))
_PIANO_REGION = re.compile(r"<region>[^\n]*?(?:ampeg_release=(\S+)\s+)?lokey=(\d+)\s+hikey=(\d+)\s+"
                           r"pitch_keycenter=(\d+)\s+sample=(\S+?)\$VEL\.\$EXT")
_ROUND = re.compile(r"_rr(\d+)\.\w+$")


@dataclass(frozen=True)
class Quelle:
    key: str                # für --nur
    sfz_name: str           # die SFZ-Datei, die das Skript schreibt (band_library)
    ordner: str             # Unterordner mit den Aufnahmen
    repo: str
    commit: str             # feste Fassung, damit immer dieselben Dateien kommen
    vorlage: str            # Datei im Repo, aus der die Regionen kommen
    geraeusche_ab: int = 128    # ab diesem Ton liegen Geräusche statt Töne
    verschieben: int = 0        # Halbtöne: der Growlybass liegt wie notiert eine Oktave über dem, was er spielt
    lizenz: str = ""

    @property
    def url(self) -> str:
        return f"{GITHUB}{self.repo}/{self.commit}/"


QUELLEN = (
    Quelle("klavier", band_library.PIANO, "Salamander", "sfzinstruments/SalamanderGrandPiano",
           "3382bf9496bba2486f5ab0de55a264d1dfc38404", "Data/region.txt",
           lizenz="Salamander Grand Piano V3 von Alexander Holm\n  CC BY 3.0, "
                  "https://github.com/sfzinstruments/SalamanderGrandPiano\n"
                  "  Hier: 8 der 16 Anschlag-Schichten, ohne Pedal- und Loslass-Geräusche.\n"),
    Quelle("bass", band_library.BASS, "Growlybass", "sfzinstruments/karoryfer.growlybass",
           "4f483268fc66b5a6d5781d421c0d11b8d08d3fc6", "growlybass_clean.sfz", geraeusche_ab=81, verschieben=-12,
           lizenz="Growlybass von Karoryfer Samples\n  CC0 1.0, https://github.com/sfzinstruments/karoryfer.growlybass\n"),
    Quelle("gitarre", band_library.GUITAR, "Emily", "sfzinstruments/karoryfer.emilyguitar",
           "b4920dc662fd9cad6dcaccdeecffdd91c8725d8c", "emily_clean.sfz", geraeusche_ab=90,
           lizenz="Emily Guitar von Karoryfer Samples\n  CC0 1.0, https://github.com/sfzinstruments/karoryfer.emilyguitar\n"),
)


def klavier_regionen(text: str, ordner: str) -> list:
    """Aus Data/region.txt des Salamander-Flügels: die Regionen für die geladenen Anschlag-Schichten."""
    regionen = []
    for name, lo, hi in PIANO_LAYERS:
        for release, lokey, hikey, center, note in _PIANO_REGION.findall(text):
            regionen.append(sfz.Region(
                sample=os.path.join(ordner, "Samples", f"{note}{name}.flac"), lokey=int(lokey), hikey=int(hikey),
                keycenter=int(center), lovel=lo, hivel=hi, veltrack=VELTRACK,
                release=float(release) if release else PIANO_RELEASE))
    return regionen


def karoryfer_regionen(vorlage: str, geraeusche_ab: int, verschieben: int = 0) -> list:
    """
    Aus einer SFZ-Datei von Karoryfer: die Töne ohne Geräusche, pro Ton und Anschlag ROUND_ROBINS Aufnahmen, die sich
    den Zufall (lorand/hirand) neu teilen; um verschieben Halbtöne auf die Tasten gelegt, die so klingen.
    """
    gruppen = {}
    for r in sfz.parse(vorlage):
        runde = _ROUND.search(r.sample)
        if r.lokey >= geraeusche_ab or (runde and int(runde.group(1)) > ROUND_ROBINS):
            continue
        gruppen.setdefault((r.lokey, r.hikey, r.keycenter, r.lovel, r.hivel), []).append(r)
    regionen = []
    for gruppe in gruppen.values():
        gruppe.sort(key=lambda r: r.sample)
        for k, r in enumerate(gruppe):
            regionen.append(replace(r, veltrack=VELTRACK, lorand=round(k / len(gruppe), 4),
                                    hirand=round((k + 1) / len(gruppe), 4) if k + 1 < len(gruppe) else 1.0,
                                    lokey=r.lokey + verschieben, hikey=r.hikey + verschieben,
                                    keycenter=r.keycenter + verschieben))
    return regionen


def hole(quelle: Quelle, ordner: str = None, basis: str = None) -> bool:
    """Ein Instrument: Regionen lesen, fehlende Aufnahmen laden, zuletzt die SFZ-Datei schreiben."""
    ordner = ordner or band_library.FOLDER
    ziel = os.path.join(ordner, quelle.sfz_name)
    if os.path.isfile(ziel):
        print(f"  {quelle.key}: schon da")
        return True
    wurzel = os.path.join(ordner, quelle.ordner)
    os.makedirs(wurzel, exist_ok=True)
    basis = basis or quelle.url
    vorlage = os.path.join(wurzel, os.path.basename(quelle.vorlage) + ".download")
    if not _laden(basis + quelle.vorlage, vorlage):
        return False
    try:
        if quelle.key == "klavier":
            with open(vorlage, encoding="utf-8", errors="replace") as f:
                regionen = klavier_regionen(f.read(), wurzel)
        else:
            regionen = karoryfer_regionen(vorlage, quelle.geraeusche_ab, quelle.verschieben)
    finally:
        os.remove(vorlage)
    aufnahmen = sorted({r.sample for r in regionen})
    sicher = os.path.abspath(wurzel)
    if not aufnahmen or any(os.path.commonpath([sicher, os.path.abspath(a)]) != sicher for a in aufnahmen):
        print(f"  {quelle.key}: unerwarteter Inhalt, übersprungen")
        return False
    fehlen = [a for a in aufnahmen if not os.path.isfile(a)]
    print(f"  {quelle.key}: {len(aufnahmen)} Aufnahmen, {len(fehlen)} zu laden", flush=True)
    with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
        ok = all(list(pool.map(lambda a: _laden(basis + urllib.parse.quote(
            os.path.relpath(a, wurzel).replace(os.sep, "/")), a), fehlen)))
    if ok:
        sfz.write(ziel, regionen, f"{band_library.NAMES[quelle.sfz_name]}, geschrieben von setup_band.py, "
                                  "Lizenz in LIZENZ.txt")
    return ok


def auswahl(nur: list = ()) -> list:
    return [q for q in QUELLEN if not nur or q.key in [n.lower() for n in nur]]


def setup(nur: list = (), ordner: str = None, basis: dict = None) -> bool:
    """basis: {klavier/bass/gitarre: andere Adresse als GitHub} (für Tests)."""
    ordner = ordner or band_library.FOLDER
    gewaehlt = auswahl(nur)
    if not gewaehlt:
        print("Kein Instrument passt zu --nur", " ".join(nur), "(klavier, bass, gitarre)")
        return False
    print(f"Lade {', '.join(q.key for q in gewaehlt)} nach {ordner}")
    ok = all([hole(q, ordner, (basis or {}).get(q.key)) for q in gewaehlt])
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(q.lizenz for q in QUELLEN))
    print("Fertig." if ok else "Nicht alles hat geklappt: noch einmal starten, es macht dort weiter.")
    return ok


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Lädt Flügel, E-Bass und E-Gitarre aus echten Aufnahmen für die App")
    p.add_argument("--nur", nargs="+", default=[], metavar="NAME", help="nur klavier, bass oder gitarre")
    sys.exit(0 if setup(p.parse_args().nur) else 1)

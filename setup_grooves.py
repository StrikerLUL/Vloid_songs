# setup_grooves.py – lädt Grooves und Fills von echten Schlagzeugern (Groove MIDI Dataset, CC BY 4.0)
#
# Das Groove MIDI Dataset von Google Magenta sind 13,6 Stunden MIDI von zehn Schlagzeugern auf einem Roland-E-Drum,
# gespielt zum Metronom. Das Skript lädt es einmal (etwa 3 MB), sucht die geraden 4/4-Takte aus Pop, Rock, Funk,
# Soul, Punk und Hip-Hop heraus, macht daraus Phrasen aus vier Takten und Fills und legt sie in
# tools/grooves/grooves.json ab. Die App nimmt sie von selbst (grooves.py); ausschalten lassen sie sich unter Pfade.
#
#   uv run setup_grooves.py
import argparse
import csv
import io
import json
import os
import random
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import grooves  # noqa: E402
from setup_samples import _laden  # noqa: E402

QUELLE = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
LIZENZ = ("Groove MIDI Dataset von Google Magenta (Jon Gillick, Adam Roberts, Jesse Engel, Douglas Eck, David Bamman)\n"
          "CC BY 4.0, https://magenta.tensorflow.org/datasets/groove\n"
          "Hier ausgewählte Takte als JSON, Töne auf General MIDI umgelegt.\n")
STILE = sorted({s for styles in grooves.FAMILIES.values() for s in styles})
PHRASE_TAKTE = 4
PRO_STIL = 200                  # so viele Phrasen und Fills höchstens pro Stilrichtung
AUF_DEM_RASTER = 0.85           # so viele Schläge eines Takts müssen nah an einer Sechzehntel liegen (gerade Grooves)
RASTER_ABSTAND = 0.06           # nah heißt: so viele Schläge davon entfernt (Triolen liegen 0,08 daneben)
# Roland TD-11 → General MIDI: Rand-Schläge auf Snare und Toms, Kanten auf Hi-Hat, Becken und Ride
TD11 = {36: 36, 38: 38, 40: 38, 37: 37, 48: 48, 50: 48, 45: 45, 47: 45, 43: 43, 58: 43, 46: 46, 26: 46,
        42: 42, 22: 42, 44: 44, 49: 49, 55: 49, 57: 57, 52: 57, 51: 51, 59: 51, 53: 53}
KICK, SNARES, TIME = 36, (37, 38), (42, 44, 46, 51, 53)
TOMS = (43, 45, 48)


def _treffer(midi, bpm: float) -> list:
    """Alle Schläge als (Schlag ab Anfang, General-MIDI-Ton, Anschlag)."""
    spb = 60.0 / bpm
    out = []
    for inst in midi.instruments:
        for n in inst.notes:
            if n.pitch in TD11:
                out.append((n.start / spb, TD11[n.pitch], n.velocity))
    return sorted(out)


def _takte(treffer: list) -> dict:
    """{Taktnummer: [(Schlag im Takt, Ton, Anschlag)]}; ein Schlag knapp vor dem Taktstrich gehört zum Takt danach."""
    takte = {}
    for beat, pitch, vel in treffer:
        nummer = int((beat + 0.12) // 4)
        takte.setdefault(nummer, []).append((round(max(beat - nummer * 4, 0.0), 3), pitch, vel))
    return takte


def _gerade(takt: list) -> bool:
    if len(takt) < 4:
        return False
    nah = sum(abs(pos * 4 - round(pos * 4)) / 4 <= RASTER_ABSTAND for pos, _, _ in takt)
    return nah >= AUF_DEM_RASTER * len(takt)


def groove_takt(takt: list) -> bool:
    """Ein brauchbarer Groove-Takt: gerade, mit Bassdrum, Snare und Hi-Hat oder Ride."""
    pitches = {p for _, p, _ in takt}
    return _gerade(takt) and KICK in pitches and bool(pitches & set(SNARES)) and bool(pitches & set(TIME))


def phrasen(treffer: list) -> list:
    """Aufeinanderfolgende brauchbare Takte in Gruppen zu vier."""
    takte = _takte(treffer)
    out, lauf = [], []
    for nummer in range(max(takte, default=-1) + 1):
        takt = takte.get(nummer, [])
        if groove_takt(takt):
            lauf.append(takt)
            if len(lauf) == PHRASE_TAKTE:
                out.append(lauf)
                lauf = []
        else:
            lauf = []
    return out


def fill(treffer: list, dauer_schlaege: float):
    """Der letzte Takt einer Fill-Aufnahme, wenn darin Toms oder Snares wirbeln; sonst None."""
    anzahl = round(dauer_schlaege / 4)
    if anzahl < 1:
        return None
    takt = _takte(treffer).get(anzahl - 1, [])
    takt = [t for t in takt if t[0] < 3.9]
    zweite_haelfte = [p for pos, p, _ in takt if pos >= 2 and (p in TOMS or p in SNARES)]
    return takt if _gerade(takt) and len(zweite_haelfte) >= 2 else None


def sammeln(zip_pfad: str) -> dict:
    import pretty_midi
    phrases, fills = {}, {}
    with zipfile.ZipFile(zip_pfad) as z:
        info = next(n for n in z.namelist() if n.endswith("info.csv"))
        wurzel = info[:-len("info.csv")]
        for row in csv.DictReader(io.TextIOWrapper(z.open(info), encoding="utf-8")):
            stil = row["style"].split("/")[0]
            if row["time_signature"] != "4-4" or stil not in STILE:
                continue
            bpm = float(row["bpm"])
            midi = pretty_midi.PrettyMIDI(io.BytesIO(z.read(wurzel + row["midi_filename"])))
            treffer = _treffer(midi, bpm)
            if row["beat_type"] == "fill":
                found = fill(treffer, float(row["duration"]) * bpm / 60)
                if found:
                    fills.setdefault(stil, []).append({"style": stil, "bpm": bpm, "hits": found})
            else:
                for bars in phrasen(treffer):
                    phrases.setdefault(stil, []).append({"style": stil, "bpm": bpm, "bars": bars})
    rng = random.Random(7)          # feste Auswahl: jeder bekommt dieselben Grooves
    auswahl = {}
    for name, gruppen in (("phrases", phrases), ("fills", fills)):
        auswahl[name] = [p for stil in sorted(gruppen)
                         for p in sorted(rng.sample(gruppen[stil], min(PRO_STIL, len(gruppen[stil]))),
                                         key=lambda p: p["bpm"])]
    return {"version": 1, **auswahl}


def setup(ordner: str = None, quelle: str = QUELLE) -> bool:
    ordner = ordner or grooves.FOLDER
    os.makedirs(ordner, exist_ok=True)
    zip_pfad = os.path.join(ordner, "groove-midionly.zip")
    print(f"Lade das Groove MIDI Dataset nach {ordner}")
    if not _laden(quelle, zip_pfad):
        print("Nicht geklappt: noch einmal starten.")
        return False
    try:
        daten = sammeln(zip_pfad)
    except (zipfile.BadZipFile, KeyError, StopIteration, ValueError, OSError) as e:
        print(f"Die geladene Datei ist unbrauchbar: {e}")
        return False
    finally:
        os.remove(zip_pfad)
    if not daten["phrases"]:
        print("Keine passenden Grooves gefunden.")
        return False
    ziel = os.path.join(ordner, grooves.LIBRARY)
    with open(ziel + ".tmp", "w", encoding="utf-8") as f:
        json.dump(daten, f, separators=(",", ":"))
    os.replace(ziel + ".tmp", ziel)
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ)
    print(f"Fertig: {len(daten['phrases'])} Phrasen und {len(daten['fills'])} Fills.")
    return True


if __name__ == "__main__":
    argparse.ArgumentParser(description="Lädt Grooves und Fills von echten Schlagzeugern (CC BY 4.0)").parse_args()
    sys.exit(0 if setup() else 1)

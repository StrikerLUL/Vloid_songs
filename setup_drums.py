# setup_drums.py – lädt ein echtes Schlagzeug (DRS Kit von DrumGizmo, CC BY 4.0) nach tools/drums/DRSKit
#
# Das DRS Kit ist ein im Studio aufgenommenes Schlagzeug (DrumGizmo-Team und Jes Eiler von DRSDrums), jeder Schlag mit
# 13 Mikrofonen. Geladen werden nur die Trommeln und Becken, die die App spielt (drum_kit.py), und pro Schlag nur die
# Mikrofone, die man im Mix hört: Nahmikrofone, Overheads und Raum. Jeder Schlag wird gleich zu Stereo gemischt, die
# einzelnen Mikrofone danach gelöscht. Zuletzt schreibt das Skript DRSKit.sfz mit allen Anschlag-Schichten und
# wechselnden Aufnahmen. Was schon da ist, wird übersprungen; nach einem Abbruch macht der nächste Start dort weiter.
#
#   uv run setup_drums.py                 alles (etwa 130 MB Download, 60 MB Platz)
#   uv run setup_drums.py --nur Snare     nur Trommeln und Becken, deren Name das enthält
import argparse
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocaloid_generator"))
import drum_kit  # noqa: E402
from setup_samples import _laden  # noqa: E402

QUELLE = "https://raw.githubusercontent.com/sfzinstruments/DrumGizmo.DRSKit/master/DrumGizmo/DRSKit/"
LIZENZ = ("DRS Kit von DrumGizmo (Lars Muldjord, Bent Bisballe Nyeng) und Jes Eiler (DRSDrums),\n"
          "SFZ-Fassung von kinwie (sfzinstruments). CC BY 4.0, https://drumgizmo.org,\n"
          "https://github.com/sfzinstruments/DrumGizmo.DRSKit\n"
          "Jeder Schlag ist hier aus Nahmikrofon, Overheads und Raummikrofonen zu Stereo gemischt.\n")
GLEICHZEITIG = 8
ROOM_LEVEL = 0.7                # Raummikrofone etwas leiser als im DRS Kit: trockener, wie im Pop
RELEASE = 0.08                  # so schnell verstummt ein Schlag, wenn ihn ein neuer ablöst (offenes Hi-Hat)
VELTRACK = 30                   # die Anschlag-Schichten sind schon leiser aufgenommen, der Anschlag regelt nur nach
LEVELS = "pegel.json"           # pro Trommel: welche Schläge gemischt sind und wie laut sie waren
_LAYER = re.compile(r"#define\s+\$(v\d+)l\s+(\d+)\s+#define\s+\$\1h\s+(\d+)")
_HIT = re.compile(r"lovel=\$(v\d+)l.*?sample=\$instr/(\d+)-\$instr-\$mic.*?seq_length=(\d+)\s+seq_position=(\d+)")


def anschlag_schichten(text: str) -> dict:
    """Aus Data/macro.txt: {"v81": (1, 15), …}"""
    return {name: (int(lo), int(hi)) for name, lo, hi in _LAYER.findall(text)}


def schlaege(text: str, schichten: dict) -> list:
    """Aus Data/region/<Trommel>.txt: [{n, lovel, hivel, seq_length, seq_position}] für jede Aufnahme."""
    out = []
    for line in text.splitlines():
        m = _HIT.search(line) if "<region>" in line else None
        if m and m.group(1) in schichten:
            lo, hi = schichten[m.group(1)]
            out.append({"n": int(m.group(2)), "lovel": lo, "hivel": hi,
                        "seq_length": int(m.group(3)), "seq_position": int(m.group(4))})
    return out


def _text(url: str, ziel: str) -> str:
    if not _laden(url, ziel):
        raise OSError(f"{url} nicht geladen")
    try:
        with open(ziel, encoding="utf-8") as f:
            return f.read()
    finally:
        os.remove(ziel)


def mischen(spuren: list) -> np.ndarray:
    """
    Mono-Mikrofone [(Audio, Panorama -1 … 1, Nahmikrofon?)] zu Stereo (2, Samples). Nahmikrofone derselben Trommel
    (Snare oben und unten, Bassdrum vorn und hinten) zeigen in dieselbe Richtung: ein gegenphasiges wird umgedreht.
    """
    laenge = max(len(a) for a, _, _ in spuren)
    out = np.zeros((2, laenge), dtype=np.float32)
    erstes = None
    for audio, pan, nah in spuren:
        audio = np.pad(audio.astype(np.float32), (0, laenge - len(audio)))
        if nah and erstes is None:
            erstes = audio
        elif nah and float(np.dot(erstes[:2048], audio[:2048])) < 0:
            audio = -audio
        angle = (max(-1.0, min(1.0, pan)) + 1) * np.pi / 4
        out[0] += audio * np.float32(np.cos(angle) * np.sqrt(2))
        out[1] += audio * np.float32(np.sin(angle) * np.sqrt(2))
    return out


def _schlag(piece, n: int, ordner: str, quelle: str):
    """Lädt die Mikrofone eines Schlags, mischt ihn und legt ihn ab. Rückgabe: Lautstärke in dB oder None."""
    tmp = os.path.join(ordner, ".laden", piece.name, str(n))
    mics = [(m, pan, level, True) for m, pan, level in piece.close] + \
           [(m, pan, ROOM_LEVEL if m.startswith("Amb") else 1.0, False) for m, pan in drum_kit.ROOM]
    try:
        spuren, rate = [], None
        for mic, pan, level, nah in mics:
            datei = os.path.join(tmp, f"{mic}.flac")
            if not _laden(f"{quelle}Samples/{piece.name}/{n}-{piece.name}-{mic}.flac", datei):
                return None
            audio, r = sf.read(datei, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if rate is not None and r != rate:
                print(f"    {piece.name} {n}: Mikrofone mit verschiedenen Abtastraten")
                return None
            rate = r
            spuren.append((audio * np.float32(level), pan, nah))
        stereo = mischen(spuren)
        peak = float(np.abs(stereo).max())
        if peak <= 0:
            return None
        ziel = os.path.join(ordner, piece.name, f"{n}.flac")
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        sf.write(ziel + ".tmp", (stereo / peak * 0.95).T, rate, subtype="PCM_16", format="FLAC")
        os.replace(ziel + ".tmp", ziel)
        return round(20 * np.log10(peak / 0.95), 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _pegel(ordner: str, piece) -> dict:
    try:
        with open(os.path.join(ordner, piece.name, LEVELS), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def hole(piece, schichten: dict, ordner: str, quelle: str = QUELLE) -> bool:
    """Eine Trommel oder ein Becken: alle Schläge laden und mischen, was fehlt."""
    alt = _pegel(ordner, piece)
    if alt.get("fertig"):
        print(f"  {piece.name}: schon da")
        return True
    os.makedirs(os.path.join(ordner, piece.name), exist_ok=True)
    regionen = schlaege(_text(f"{quelle}Data/region/{piece.name}.txt",
                              os.path.join(ordner, piece.name, "region.txt")), schichten)
    if not regionen:
        print(f"  {piece.name}: unerwarteter Inhalt, übersprungen")
        return False
    lautstaerke = {int(k): v for k, v in alt.get("lautstaerke", {}).items()
                   if os.path.isfile(os.path.join(ordner, piece.name, f"{k}.flac"))}
    fehlen = [r["n"] for r in regionen if r["n"] not in lautstaerke]
    print(f"  {piece.name}: {len(regionen)} Schläge, {len(fehlen)} zu laden", flush=True)
    with ThreadPoolExecutor(max_workers=GLEICHZEITIG) as pool:
        for n, db in zip(fehlen, pool.map(lambda n: _schlag(piece, n, ordner, quelle), fehlen)):
            if db is not None:
                lautstaerke[n] = db
    fertig = all(r["n"] in lautstaerke for r in regionen)
    with open(os.path.join(ordner, piece.name, LEVELS), "w", encoding="utf-8") as f:
        json.dump({"fertig": fertig, "regionen": regionen, "lautstaerke": lautstaerke}, f)
    return fertig


def sfz_schreiben(ordner: str) -> int:
    """DRSKit.sfz aus allen fertigen Trommeln und Becken; Rückgabe: wie viele es sind."""
    zeilen = ["// DRS Kit (DrumGizmo), CC BY 4.0, siehe LIZENZ.txt. Geschrieben von setup_drums.py",
              f"<global> amp_veltrack={VELTRACK} ampeg_release={RELEASE}"]
    fertig = 0
    for piece in drum_kit.PIECES:
        daten = _pegel(ordner, piece)
        if not daten.get("fertig"):
            continue
        fertig += 1
        zeilen.append(f"<group> key={piece.key}")
        for r in daten["regionen"]:
            zeilen.append(f"<region> sample={piece.name}/{r['n']}.flac lovel={r['lovel']} hivel={r['hivel']} "
                          f"seq_length={r['seq_length']} seq_position={r['seq_position']} "
                          f"volume={daten['lautstaerke'][str(r['n'])] + piece.gain:.2f}")
    if fertig:
        with open(os.path.join(ordner, drum_kit.SFZ_NAME + ".tmp"), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen) + "\n")
        os.replace(os.path.join(ordner, drum_kit.SFZ_NAME + ".tmp"), os.path.join(ordner, drum_kit.SFZ_NAME))
    return fertig


def auswahl(nur: list = ()) -> list:
    """Die Trommeln zu --nur: ein genauer Name nur diese (Snare), sonst alle, die das enthalten (Tom, Crash)."""
    if not nur:
        return list(drum_kit.PIECES)
    found = []
    for n in (n.lower() for n in nur):
        exact = [p for p in drum_kit.PIECES if p.name.lower() == n]
        found += exact or [p for p in drum_kit.PIECES if n in p.name.lower()]
    return [p for p in drum_kit.PIECES if p in found]


def setup(nur: list = (), ordner: str = None, quelle: str = QUELLE) -> bool:
    ordner = ordner or drum_kit.FOLDER
    gewaehlt = auswahl(nur)
    if not gewaehlt:
        print("Keine Trommel passt zu --nur", " ".join(nur))
        return False
    os.makedirs(ordner, exist_ok=True)
    print(f"Lade {len(gewaehlt)} Trommeln und Becken nach {ordner}")
    try:
        schichten = anschlag_schichten(_text(f"{quelle}Data/macro.txt", os.path.join(ordner, "macro.txt")))
    except OSError as e:
        print(f"Konnte das DRS Kit nicht erreichen: {e}")
        return False
    ok = True
    for piece in gewaehlt:
        try:
            ok = hole(piece, schichten, ordner, quelle) and ok
        except OSError as e:
            print(f"  {piece.name}: {e}")
            ok = False
    shutil.rmtree(os.path.join(ordner, ".laden"), ignore_errors=True)
    with open(os.path.join(ordner, "LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ)
    anzahl = sfz_schreiben(ordner)
    print(f"Fertig: {anzahl} von {len(drum_kit.PIECES)} Trommeln und Becken spielbar." if ok else
          "Nicht alles hat geklappt: noch einmal starten, es macht dort weiter.")
    return ok


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Lädt ein echtes Schlagzeug (DRS Kit, CC BY 4.0) für die App")
    p.add_argument("--nur", nargs="+", default=[], metavar="NAME",
                   help="nur Trommeln und Becken, deren Name das enthält (z. B. Snare, Kdrum, Crash)")
    sys.exit(0 if setup(p.parse_args().nur) else 1)

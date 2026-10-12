# sample_library.py – echte Orchester-Instrumente aus Aufnahmen (VSCO 2 Community Edition, CC0)
#
# setup_samples.py lädt die Aufnahmen nach tools/samples. Streicher, Blechbläser, Holzbläser, Harfe, Pauken und
# Stabspiele spielen dann aus ihnen (mit dem Sampler in sfz.py) statt aus dem SoundFont. Kurze Töne nehmen die kurz
# gespielten Aufnahmen (Spiccato, Staccato). Satz-Programme verteilen ihre Töne nach der Tonhöhe auf die
# Instrumente: Streicher oben auf Geigen, darunter Bratschen, Celli und Kontrabässe; der Bläsersatz auf Trompeten,
# Posaunen und Tuba. Fehlt eine Datei, spielt das Instrument weiter aus dem SoundFont.
import copy
import functools
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pretty_midi

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "samples", "VSCO-2-CE")
SHORT_NOTE = 0.3        # kürzere Töne (Sekunden) spielen aus den kurz gespielten Aufnahmen
SWELL = 0.1             # langsam anschwellende Aufnahmen (Streicher) setzen später ein: nach 0,1 s fast laut, wie im Pop
REFERENCE_DB = -32.0    # jedes Instrument gleich laut: so laut (RMS) sind die lautesten 50 ms eines Tons mit Anschlag 100


@dataclass(frozen=True)
class Part:
    sustain: str            # SFZ-Datei für gehaltene Töne
    short: str = ""         # für kurze Töne (Spiccato, Staccato); leer = wie gehalten
    lowest: int = 0         # in einem Satz: ab diesem Ton spielt dieses Instrument

    def file(self, duration: float) -> str:
        if self.short and duration < SHORT_NOTE and os.path.isfile(path(self.short)):
            return self.short
        return self.sustain


def _one(sustain: str, short: str = "") -> tuple:
    return (Part(sustain, short),)


STRINGS = (Part("ViolinEnsSusVib.sfz", "ViolinEnsSpic.sfz", 62), Part("ViolaEnsSusVib.sfz", "ViolaEnsSpic.sfz", 50),
           Part("CelloEnsSusVib.sfz", "CelloEnsSpic.sfz", 38), Part("ContrabassSusVB.sfz", "ContrabassSpic.sfz"))
TREMOLO = (Part("ViolinEnsTrem.sfz", lowest=62), Part("ViolaEnsTrem.sfz", lowest=50),
           Part("CelloEnsTrem.sfz", lowest=38), Part("ContrabassTrem.sfz"))
PIZZICATO = (Part("ViolinEnsPizz.sfz", lowest=62), Part("ViolaEnsPizz.sfz", lowest=50),
             Part("CelloEnsPizz.sfz", lowest=38), Part("ContrabassPizz.sfz"))
BRASS = (Part("TrumpetSus.sfz", "TrumpetStac.sfz", 60), Part("TromboneSus.sfz", "TromboneStac.sfz", 46),
         Part("TubaSus.sfz", "TubaStac.sfz"))

# General-MIDI-Programm → Instrument(e), hohe Teile zuerst
PROGRAMS = {
    9: _one("Glockenspiel.sfz"), 12: _one("Marimba.sfz"), 13: _one("Xylophone.sfz"), 14: _one("TubularBells.sfz"),
    40: _one("SViolinVib.sfz", "SViolinSpic.sfz"),                  # Solo-Geige
    41: _one("ViolaEnsSusVib.sfz", "ViolaEnsSpic.sfz"),
    42: _one("CelloEnsSusVib.sfz", "CelloEnsSpic.sfz"),
    43: _one("ContrabassSusVB.sfz", "ContrabassSpic.sfz"),
    44: TREMOLO, 45: PIZZICATO, 46: _one("Harp.sfz"), 47: _one("Timpani.sfz"),
    48: STRINGS, 49: STRINGS,
    56: _one("TrumpetSus.sfz", "TrumpetStac.sfz"), 57: _one("TromboneSus.sfz", "TromboneStac.sfz"),
    58: _one("TubaSus.sfz", "TubaStac.sfz"), 59: _one("TrumpetStraightMuteSus.sfz"),
    60: _one("FHornSus.sfz", "FHornStac.sfz"), 61: BRASS,
    68: _one("OboeSusVib.sfz", "OboeStac.sfz"), 70: _one("BassoonSus.sfz", "BassoonStac.sfz"),
    71: _one("ClarinetSus.sfz", "ClarinetStac.sfz"), 72: _one("PiccoloSus.sfz", "PiccoloStac.sfz"),
    73: _one("FluteSusVib.sfz", "FluteStac.sfz"),
}


def path(name: str) -> str:
    return os.path.join(FOLDER, name)


def files() -> list:
    """Alle SFZ-Dateien, die die App nutzen kann."""
    return sorted({f for parts in PROGRAMS.values() for p in parts for f in (p.sustain, p.short) if f})


def installed() -> list:
    """Die vorhandenen SFZ-Dateien (setup_samples.py schreibt jede erst, wenn alle ihre Aufnahmen da sind)."""
    return [f for f in files() if os.path.isfile(path(f))]


def covers(inst: pretty_midi.Instrument) -> bool:
    """Spielt dieses Instrument aus den Aufnahmen? Nur wenn für alle seine Teile die Aufnahmen da sind."""
    parts = PROGRAMS.get(inst.program)
    return (not inst.is_drum and bool(inst.notes) and parts is not None
            and all(os.path.isfile(path(p.sustain)) for p in parts))


def render(inst: pretty_midi.Instrument, sample_rate: int = 44100) -> Optional[np.ndarray]:
    """Die Töne von inst aus den Aufnahmen, Rückgabe (2, Samples); None, wenn der Sampler nicht spielen kann."""
    import sfz
    parts = PROGRAMS[inst.program]
    groups = {}
    for note in inst.notes:
        part = next((p for p in parts if note.pitch >= p.lowest), parts[-1])
        groups.setdefault(part.file(note.end - note.start), []).append(note)
    pieces = []
    for name, notes in groups.items():
        try:
            instrument = sfz.load(path(name))
        except (OSError, ValueError) as e:
            log.warning("%s lässt sich nicht laden (%s), %s spielt aus dem SoundFont", name, e, inst.name or "Spur")
            return None
        audio = sfz.render(instrument, [_into_range(n, instrument) for n in notes], sample_rate, inst.program, SWELL)
        pieces.append(audio * np.float32(_level(path(name), os.path.getmtime(path(name)))))
    out = np.zeros((2, max(p.shape[1] for p in pieces)), dtype=np.float32)
    for p in pieces:
        out[:, :p.shape[1]] += p
    pan = next((cc.value for cc in inst.control_changes if cc.number == 10), None)
    if pan is not None:
        out = sfz.balance(out, (pan - 64) / 63)
    return out


@functools.lru_cache(maxsize=None)
def _level(sfz_path: str, mtime: float) -> float:
    """
    Faktor, der eine SFZ-Datei auf die gemeinsame Lautstärke bringt (die Aufnahmen sind sehr verschieden laut
    aufgenommen): gemessen an drei Tönen mit Anschlag 100 über ihren Tonumfang verteilt, der mittlere zählt.
    """
    import sfz
    instrument = sfz.load(sfz_path)
    levels = []
    for share in (0.25, 0.5, 0.75):
        pitch = round(instrument.low + (instrument.high - instrument.low) * share)
        mono = sfz.render(instrument, [pretty_midi.Note(100, pitch, 0.0, 1.0)], swell=SWELL).mean(axis=0)
        window = 2205
        if len(mono) >= window:
            mono = mono[:len(mono) // window * window].reshape(-1, window)
        levels.append(float(np.sqrt(np.mean(np.square(mono), axis=-1)).max()) if mono.size else 0.0)
    loudness = sorted(levels)[1]
    return 10 ** (REFERENCE_DB / 20) / loudness if loudness > 1e-6 else 1.0


def _into_range(note: pretty_midi.Note, instrument) -> pretty_midi.Note:
    """Töne außerhalb der Aufnahmen wandern um Oktaven hinein (wie in sound_library)."""
    pitch = note.pitch
    while pitch < instrument.low and pitch + 12 <= 127:
        pitch += 12
    while pitch > instrument.high and pitch - 12 >= 0:
        pitch -= 12
    if pitch == note.pitch:
        return note
    moved = copy.copy(note)
    moved.pitch = pitch
    return moved


def status() -> str:
    """Eine Zeile für die Oberfläche: ob die Orchester-Aufnahmen da sind."""
    have, total = len(installed()), len(files())
    if not have:
        return "Orchester-Aufnahmen fehlen: einmal uv run setup_samples.py ausführen"
    return f"Orchester-Aufnahmen (VSCO 2): {have} von {total} Instrumenten da"

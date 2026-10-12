# motifs.py – mehr Abwechslung in der Gesangsmelodie: zusätzliche Rhythmen und Gesten, und gelernte aus MIDI-Dateien
#
# Die Melodie (melody_writer.py) baut jeden Takt aus einem Rhythmus (Einsätze in Sechzehnteln) und einer Geste (wie
# die Töne im Takt steigen und fallen). Hier kommen zwei Quellen dazu, jede mit eigenem Schalter:
#   - mehr eingebaute: synkopierte J-Pop-Rhythmen, Schlüsse mit Vorhalt, Gesten wie Zickzack oder Umspielung
#   - gelernte: aus den MIDI-Dateien in einem Ordner (Standard vocaloid_generator/motive). Aus jeder Datei zählen
#     die einstimmigen Spuren in Gesangslage; jeder 4/4-Takt liefert seinen Rhythmus und, ab drei Tönen, seine Geste.
#     Häufige Rhythmen kommen öfter dran; etwa die Hälfte der Takte singt dann gelernte.
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.BASE_DIR, "motive")
MIDI_FILES = (".mid", ".midi")
KEEP_RHYTHMS = 12              # pro Silbenzahl die häufigsten
KEEP_GESTURES = 24
MIN_MELODY_PITCH = 55          # tiefere einstimmige Spuren sind eher Bässe
MAX_OVERLAP = 0.15             # mehr gleichzeitige Töne: keine Melodie
GESTURE_RANGE = 5.0            # Gesten werden auf höchstens so viele Halbtöne Ausschlag gebracht
STEPS_PER_BEAT = 4
BAR_STEPS = 16

# Mehr eingebaute Rhythmen (Einsätze in Sechzehnteln je Silbenzahl): Synkopen und Vorgezogenes wie im J-Pop
MORE_BODY = {
    2: [(3, 8), (6, 10), (0, 3)],
    3: [(0, 3, 6), (0, 6, 10), (2, 4, 8), (4, 8, 12), (0, 3, 10)],
    4: [(0, 3, 6, 12), (0, 6, 8, 12), (2, 6, 8, 12), (0, 2, 7, 10), (4, 6, 8, 12), (0, 3, 8, 11)],
    5: [(0, 3, 6, 10, 12), (0, 2, 4, 7, 10), (2, 4, 6, 8, 12), (0, 4, 6, 8, 11), (0, 3, 6, 8, 14)],
    6: [(0, 2, 4, 7, 10, 12), (0, 3, 4, 6, 8, 12), (2, 4, 6, 8, 10, 12), (0, 2, 4, 6, 10, 14),
        (0, 3, 6, 8, 11, 14)],
    7: [(0, 2, 4, 6, 7, 10, 12), (0, 1, 2, 4, 6, 8, 12), (2, 4, 6, 8, 10, 12, 14), (0, 2, 3, 6, 8, 11, 14)],
    8: [(0, 2, 4, 6, 7, 8, 10, 12), (0, 2, 4, 5, 6, 8, 10, 12), (0, 2, 3, 6, 8, 10, 11, 14)],
}
# Schlüsse (der letzte Takt einer Phrase, danach der lange Schlusston bis zum Atmen)
MORE_END = {
    2: [(2, 4), (0, 3)],
    3: [(0, 3, 6), (2, 4, 6), (0, 2, 3)],
    4: [(0, 2, 3, 6), (0, 3, 4, 6), (2, 3, 4, 6)],
    5: [(0, 2, 3, 4, 6), (0, 2, 4, 5, 6)],
}


def _span(k: int) -> list:
    return [i / (k - 1) for i in range(k)] if k > 1 else [0.0]


# Mehr Gesten: Abweichung der Töne eines Takts von der Phrasenkontur (k = Töne im Takt)
MORE_GESTURES = {
    "zigzag":  lambda k: [(1.5 if i % 2 else -0.5) + 1.0 * x for i, x in enumerate(_span(k))],
    "turn":    lambda k: [(0.0, 2.0, 0.0, -1.0, 0.0)[i % 5] for i in range(k)],
    "climb":   lambda k: [-3.0 + 6.0 * x for x in _span(k)],
    "hold_leap": lambda k: [0.0] * (k - 1) + [4.0] if k > 1 else [0.0],
    "dip_rise": lambda k: [2.0 - 10.0 * x if x < 0.5 else -3.0 + 10.0 * (x - 0.5) for x in _span(k)],
}
MORE_GESTURE_WEIGHTS = {
    "Chorus":    {"zigzag": 1, "hold_leap": 1, "turn": 1},
    "Verse":     {"turn": 1, "zigzag": 1, "dip_rise": 1},
    "PreChorus": {"climb": 2, "hold_leap": 1},
    "Bridge":    {"dip_rise": 1, "turn": 1},
}


@dataclass
class Motifs:
    """Was eine Melodie zusätzlich zu den eingebauten Rhythmen und Gesten nehmen darf."""
    body: dict = field(default_factory=dict)        # Silbenzahl → [Rhythmus]
    end: dict = field(default_factory=dict)
    gestures: dict = field(default_factory=dict)    # Name → Funktion k → Abweichungen
    gesture_weights: dict = field(default_factory=dict)   # Sektionsart → {Name: Gewicht}
    learned: dict = field(default_factory=dict)     # Silbenzahl → [Rhythmus], häufige mehrfach
    learned_gestures: list = field(default_factory=list)  # [(Abweichungen, Anzahl)]
    files: int = 0

    def __bool__(self) -> bool:
        return bool(self.body or self.end or self.gestures or self.learned or self.learned_gestures)

    def gesture(self, name: str, k: int) -> Optional[list]:
        if name in self.gestures:
            return self.gestures[name](k)
        if name.startswith("gelernt:"):
            shape = self.learned_gestures[int(name.split(":")[1])][0]
            return list(np.interp(_span(k), _span(len(shape)), shape))
        return None

    def weights(self, kind: str) -> dict:
        """Gewichte der zusätzlichen Gesten für eine Sektionsart; gelernte zusammen so schwer wie die eingebauten."""
        weights = dict(self.gesture_weights.get(kind, self.gesture_weights.get("Verse", {})))
        if self.learned_gestures:
            total = sum(count for _, count in self.learned_gestures)
            share = max(sum(weights.values()), 4)
            weights.update({f"gelernt:{i}": share * count / total for i, (_, count) in enumerate(self.learned_gestures)})
        return weights


def more() -> Motifs:
    return Motifs(body=MORE_BODY, end=MORE_END, gestures=MORE_GESTURES, gesture_weights=MORE_GESTURE_WEIGHTS)


def combine(extra: Optional[Motifs], learned: Optional[Motifs]) -> Optional[Motifs]:
    if not extra and not learned:
        return None
    extra, learned = extra or Motifs(), learned or Motifs()
    return Motifs(body=extra.body, end=extra.end, gestures=extra.gestures, gesture_weights=extra.gesture_weights,
                  learned=learned.learned, learned_gestures=learned.learned_gestures, files=learned.files)


def for_settings(settings) -> Optional[Motifs]:
    """Die Motive für einen Song nach seinen Schaltern; None = nur die eingebauten wie bisher."""
    learned = learn(folder(settings)) if settings.learned_motifs else None
    return combine(more() if settings.more_motifs else None, learned)


def folder(settings) -> str:
    return settings.motif_folder or FOLDER


def midi_files(path: str) -> list:
    if not os.path.isdir(path):
        return []
    return sorted(os.path.join(root, f) for root, _, files in os.walk(path) for f in files
                  if f.lower().endswith(MIDI_FILES))


_cache = {}


def learn(path: str) -> Optional[Motifs]:
    """Rhythmen und Gesten aus allen MIDI-Dateien im Ordner path (mit Unterordnern); None, wenn keine taugt."""
    files = midi_files(path)
    key = tuple((f, os.path.getmtime(f), os.path.getsize(f)) for f in files)
    if not files:
        return None
    if _cache.get(path, (None,))[0] == key:
        return _cache[path][1]
    rhythms, shapes, used = Counter(), Counter(), 0
    for f in files:
        try:
            bars = melody_bars(f)
        except Exception as e:       # noqa: BLE001 – kaputte MIDI-Dateien werfen sehr verschiedene Fehler
            log.warning("Motive: %s nicht lesbar (%s)", os.path.basename(f), e)
            continue
        if bars:
            used += 1
        for onsets, pitches in bars:
            rhythms[onsets] += 1
            shape = gesture_shape(pitches)
            if shape:
                shapes[shape] += 1
    learned = {}
    for onsets, count in rhythms.most_common():
        options = learned.setdefault(len(onsets), [])
        if len(set(options)) < KEEP_RHYTHMS:
            options.extend([onsets] * count)
    motifs = Motifs(learned=learned, learned_gestures=[(list(s), c) for s, c in shapes.most_common(KEEP_GESTURES)],
                    files=used) if rhythms else None
    if motifs:
        log.info("Motive aus %d MIDI-Dateien: %d Rhythmen, %d Gesten", used, len(rhythms), len(motifs.learned_gestures))
    _cache[path] = (key, motifs)
    return motifs


def melody_bars(path: str) -> list:
    """Alle 4/4-Takte der Melodie-Spuren einer MIDI-Datei: [(Einsätze in Sechzehnteln, Tonhöhen)]."""
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(path)
    beats = pm.get_beats()
    downbeats = pm.get_downbeats()
    if len(beats) < 2 or len(downbeats) < 1:
        return []
    beat_of_downbeat = np.searchsorted(beats, downbeats - 1e-6)
    bars = []
    for inst in pm.instruments:
        if not _is_melody(inst):
            continue
        per_bar = {}
        for n in sorted(inst.notes, key=lambda n: n.start):
            b = int(np.searchsorted(beats, n.start + 1e-6)) - 1
            if b < 0 or b + 1 >= len(beats):
                continue
            step = int(round((n.start - beats[b]) / (beats[b + 1] - beats[b]) * STEPS_PER_BEAT))
            d = int(np.searchsorted(downbeats, n.start + 1e-6)) - 1
            if d < 0:
                continue
            bar_beats = int((beat_of_downbeat[d + 1] if d + 1 < len(downbeats) else len(beats)) - beat_of_downbeat[d])
            if bar_beats != 4:
                continue                     # nur 4/4-Takte
            pos = int(b - beat_of_downbeat[d]) * STEPS_PER_BEAT + step
            if 0 <= pos < BAR_STEPS:
                per_bar.setdefault(d, {})[pos] = n.pitch       # gleichzeitige Töne: der letzte zählt
        for d in sorted(per_bar):
            onsets = tuple(sorted(per_bar[d]))
            if 1 <= len(onsets) <= 8:
                bars.append((onsets, [per_bar[d][s] for s in onsets]))
    return bars


def _is_melody(inst) -> bool:
    if inst.is_drum or len(inst.notes) < 8:
        return False
    notes = sorted(inst.notes, key=lambda n: n.start)
    overlaps = sum(1 for a, b in zip(notes, notes[1:]) if b.start < a.end - 0.05)   # Akkorde, nicht nur Legato
    return overlaps / len(notes) <= MAX_OVERLAP and np.mean([n.pitch for n in notes]) >= MIN_MELODY_PITCH


def gesture_shape(pitches: list) -> Optional[tuple]:
    """Die Geste eines Takts: Abstand jedes Tons zur Mitte des Takts, auf GESTURE_RANGE begrenzt; ab drei Tönen."""
    if len(pitches) < 3:
        return None
    mid = (max(pitches) + min(pitches)) / 2
    offsets = [p - mid for p in pitches]
    widest = max(abs(o) for o in offsets)
    if widest == 0:
        return None
    scale = min(1.0, GESTURE_RANGE / widest)
    return tuple(round(o * scale, 1) for o in offsets)


def status(settings) -> str:
    if not settings.learned_motifs:
        return "Gelernte Motive: aus"
    path = folder(settings)
    files = midi_files(path)
    if not files:
        return f"Gelernte Motive: keine MIDI-Dateien in {path}"
    found = learn(path)
    return f"Gelernte Motive: aus {found.files if found else 0} von {len(files)} MIDI-Dateien"

# song_helpers.py – Hilfsfunktionen, um generierte Songs in Tests zu untersuchen
from dataclasses import dataclass

import config

TEST_STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Drop", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]

# Einträge in den Spuren, die keine Noten sind
NON_NOTE_KEYS = ("silben", "melody_data", "plan", "vocal_melody", "harmony_data", "harmony_silben")

# Die Humanisierung verschiebt Noten um bis zu 20 ms; so weit darf die erste Note
# einer Sektion vor deren Anfang liegen
BOUNDARY_TOLERANCE = 0.035

SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
}
KEY_OFFSETS = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


@dataclass
class Song:
    tracks: dict
    structure: list
    bpm: float
    key: str
    mode: str
    output_dir: str

    def note_tracks(self):
        return {name: notes for name, notes in self.tracks.items() if name not in NON_NOTE_KEYS}


@dataclass
class Window:
    index: int
    type: str
    start: float
    end: float

    def contains(self, note) -> bool:
        return self.start - BOUNDARY_TOLERANCE <= note.start < self.end - BOUNDARY_TOLERANCE


def section_windows(structure, bpm, section_config=None):
    section_config = section_config or config.SECTION_CONFIG
    bar = 4 * 60.0 / bpm
    windows, t = [], 0.0
    for i, sec in enumerate(structure):
        length = section_config[sec]["bars"] * bar
        windows.append(Window(i, sec, t, t + length))
        t += length
    return windows


def scale_pitch_classes(key, mode):
    return {(KEY_OFFSETS[key] + i) % 12 for i in SCALE_INTERVALS[mode]}

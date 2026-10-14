# theory.py – Tonarten, Tonleitern und Akkorde (Stufen wie "IVmaj7" oder "bVII")
import re
from dataclasses import dataclass
from typing import Optional

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
KEY_OFFSETS = {name: i for i, name in enumerate(NOTE_NAMES)}
KEY_OFFSETS.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})

SCALES = {
    "major":    (0, 2, 4, 5, 7, 9, 11),
    "minor":    (0, 2, 3, 5, 7, 8, 10),
    "dorian":   (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
}

# Intervalle über dem Grundton; Werte über 12 sind Optionstöne (9 = 14)
QUALITIES = {
    "maj":   (0, 4, 7),
    "min":   (0, 3, 7),
    "dim":   (0, 3, 6),
    "aug":   (0, 4, 8),
    "sus2":  (0, 2, 7),
    "sus4":  (0, 5, 7),
    "7":     (0, 4, 7, 10),
    "maj7":  (0, 4, 7, 11),
    "m7":    (0, 3, 7, 10),
    "m7b5":  (0, 3, 6, 10),
    "7sus4": (0, 5, 7, 10),
    "6":     (0, 4, 7, 9),
    "add9":  (0, 4, 7, 14),
    "madd9": (0, 3, 7, 14),
    "maj9":  (0, 4, 7, 11, 14),
    "m9":    (0, 3, 7, 10, 14),
}
_SUFFIX_NAMES = {"maj": "", "min": "m", "m7": "m7", "madd9": "m(add9)", "add9": "(add9)"}

# Stufen relativ zur Dur-Tonleiter des Grundtons; "b"/"#" davor verschieben um einen Halbton
_DEGREES = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}
_ROMAN = re.compile(r"^(?P<acc>[b#]?)(?P<deg>VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)(?P<suffix>[^/]*)(?:/(?P<bass>\d))?$")


def key_pc(key: str) -> int:
    if key not in KEY_OFFSETS:
        raise ValueError(f"Unbekannte Tonart: {key}")
    return KEY_OFFSETS[key]


def scale_pcs(tonic: int, mode: str) -> tuple:
    return tuple((tonic + i) % 12 for i in SCALES.get(mode, SCALES["minor"]))


def is_minor(mode: str) -> bool:
    return mode in ("minor", "dorian", "phrygian")


@dataclass(frozen=True)
class Chord:
    root: int                 # Tonklasse 0–11
    quality: str
    bass: Optional[int] = None  # Tonklasse des Basstons bei Slash-Akkorden

    @property
    def intervals(self) -> tuple:
        return QUALITIES[self.quality]

    @property
    def pcs(self) -> tuple:
        """Alle Tonklassen des Akkords, Grundton zuerst."""
        return tuple(dict.fromkeys((self.root + i) % 12 for i in self.intervals))

    @property
    def triad_pcs(self) -> tuple:
        return tuple((self.root + i) % 12 for i in self.intervals[:3])

    @property
    def bass_pc(self) -> int:
        return self.root if self.bass is None else self.bass

    @property
    def fifth_pc(self) -> int:
        fifth = 6 if self.quality in ("dim", "m7b5") else 8 if self.quality == "aug" else 7
        return (self.root + fifth) % 12

    @property
    def is_minor(self) -> bool:
        return self.quality in ("min", "m7", "m9", "madd9", "dim", "m7b5")

    @property
    def name(self) -> str:
        text = NOTE_NAMES[self.root] + _SUFFIX_NAMES.get(self.quality, self.quality)
        return text if self.bass is None else f"{text}/{NOTE_NAMES[self.bass]}"

    def transposed(self, semitones: int) -> "Chord":
        bass = None if self.bass is None else (self.bass + semitones) % 12
        return Chord((self.root + semitones) % 12, self.quality, bass)


def parse_roman(symbol: str, tonic: int) -> Chord:
    """'IVmaj7' in C → Fmaj7, 'bVII' in A → G, 'v7' → Moll-Septakkord, 'I/3' → Grundton mit Terz im Bass."""
    m = _ROMAN.match(symbol)
    if not m:
        raise ValueError(f"Unbekannte Stufe: {symbol}")
    deg = m.group("deg")
    upper = deg.isupper()
    root = (tonic + _DEGREES[deg.upper()] + {"b": -1, "#": 1, "": 0}[m.group("acc")]) % 12
    suffix = m.group("suffix")
    if suffix == "":
        quality = "maj" if upper else "min"
    elif suffix == "7":
        quality = "7" if upper else "m7"
    elif suffix == "add9":
        quality = "add9" if upper else "madd9"
    elif suffix == "9":
        quality = "maj9" if upper else "m9"
    elif suffix in ("dim", "o"):
        quality = "dim"
    elif suffix in ("m7b5", "ø"):
        quality = "m7b5"
    elif suffix in QUALITIES:
        quality = suffix
    else:
        raise ValueError(f"Unbekannter Akkordzusatz in {symbol}: {suffix}")
    chord = Chord(root, quality)
    if m.group("bass"):
        # /3 = Terz, /5 = Quinte, /7 = Septime des Akkords im Bass
        idx = {"3": 1, "5": 2, "7": 3}[m.group("bass")]
        chord = Chord(root, quality, chord.pcs[idx] if idx < len(chord.pcs) else None)
    return chord


# Akkordnamen wie "F#m7", "Bbmaj7", "C/E": Grundton, Zusatz, Basston
_NAME = re.compile(r"^(?P<root>[A-Ga-g][#b]?)(?P<suffix>[^/]*)(?:/(?P<bass>[A-Ga-g][#b]?))?$")
_NAME_SUFFIXES = {
    "": "maj", "maj": "maj", "M": "maj", "m": "min", "min": "min", "-": "min", "7": "7", "dom7": "7",
    "maj7": "maj7", "M7": "maj7", "Δ": "maj7", "m7": "m7", "min7": "m7", "-7": "m7", "dim": "dim", "o": "dim",
    "m7b5": "m7b5", "ø": "m7b5", "aug": "aug", "+": "aug", "sus": "sus4", "sus4": "sus4", "sus2": "sus2",
    "7sus4": "7sus4", "6": "6", "add9": "add9", "(add9)": "add9", "madd9": "madd9", "m(add9)": "madd9",
    "9": "7", "maj9": "maj9", "m9": "m9",
}


def _note_pc(name: str) -> int:
    return KEY_OFFSETS[name[0].upper() + name[1:]]


def parse_chord_name(name: str) -> Chord:
    """'F#m7' → Fis-Moll-Septakkord, 'C/E' → C-Dur mit E im Bass, 'Bb' → B-Dur."""
    m = _NAME.match(name.strip())
    if not m or m.group("suffix") not in _NAME_SUFFIXES:
        raise ValueError(f"Unbekannter Akkord: {name}")
    bass = _note_pc(m.group("bass")) if m.group("bass") else None
    return Chord(_note_pc(m.group("root")), _NAME_SUFFIXES[m.group("suffix")], bass)


def nearest_pitch(pc: int, target: int) -> int:
    """Der Ton mit Tonklasse pc, der target am nächsten liegt."""
    base = target - ((target - pc) % 12)
    return base if target - base <= 6 else base + 12


def pitches_in_range(pcs, lo: int, hi: int) -> list:
    pcs = set(pcs)
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def voice_chord(chord: Chord, lo: int, hi: int, n_voices: int = 4, previous: Optional[list] = None,
                include_extensions: bool = True) -> list:
    """
    Akkord-Griff mit n Stimmen zwischen lo und hi. Mit previous wird der Griff gewählt, der am
    wenigsten springt (Stimmführung); sonst der Griff, der der Mitte der Lage am nächsten ist.
    """
    pcs = list(chord.pcs if include_extensions else chord.triad_pcs)
    if len(pcs) > n_voices:
        # Quinte fällt zuerst weg, dann alles über der vierten Stimme
        if chord.fifth_pc in pcs and len(pcs) > 3:
            pcs.remove(chord.fifth_pc)
        pcs = pcs[:n_voices]
    candidates = []
    pool = pitches_in_range(pcs, lo, hi)
    for start in pool:
        voicing = [start]
        needed = [pc for pc in pcs if pc != start % 12]
        cur = start
        while len(voicing) < n_voices:
            if not needed:
                needed = list(pcs)  # Verdopplung, wenn mehr Stimmen als Töne
            nxt = min((p for p in pool if p > cur and p % 12 in needed), default=None)
            if nxt is None:
                break
            voicing.append(nxt)
            needed.remove(nxt % 12)
            cur = nxt
        if len(voicing) == n_voices and set(p % 12 for p in voicing) >= set(pcs[:min(len(pcs), n_voices)]):
            candidates.append(voicing)
    if not candidates:
        return sorted(nearest_pitch(pc, (lo + hi) // 2) for pc in pcs[:n_voices])
    if previous:
        prev_center = sum(previous) / len(previous)

        def movement(v):
            return sum(min(abs(p - q) for q in previous) for p in v) + 0.3 * abs(sum(v) / len(v) - prev_center)
        return min(candidates, key=movement)
    center = (lo + hi) / 2
    return min(candidates, key=lambda v: abs(sum(v) / len(v) - center))



# song_plan.py – Der Bauplan eines Songs: Sektionen, Tonarten, Akkorde und Energie, alles in Schlägen
import random
from dataclasses import dataclass, field
from typing import Optional

from styles import CADENCES, SECTION_ENERGY, StyleProfile, progressions_for
from theory import Chord, is_minor, key_pc, parse_roman

BEATS_PER_BAR = 4
SLOW_BPM = 100
VOCAL_RANGE = (57, 79)       # A3 bis G5: Lage, in der die Melodie geschrieben wird
SHARED_PROGRESSION = {"Intro": "Chorus", "Outro": "Chorus", "Drop": "Chorus", "Build-up": "PreChorus"}


@dataclass
class ChordSlot:
    start: float   # Schlag ab Songanfang
    dur: float
    chord: Chord


@dataclass
class Section:
    kind: str
    occurrence: int          # 1 = erstes Vorkommen dieser Sektionsart
    index: int               # Position im Song
    start: float             # Schlag ab Songanfang
    bars: int
    tonic: int
    mode: str
    energy: float
    has_vocals: bool
    chords: list = field(default_factory=list)
    next_kind: Optional[str] = None
    prev_kind: Optional[str] = None
    is_last_of_kind: bool = False

    @property
    def beats(self) -> float:
        return self.bars * BEATS_PER_BAR

    @property
    def end(self) -> float:
        return self.start + self.beats

    def chord_at(self, beat: float) -> Chord:
        """Akkord, der zum Schlag beat (ab Songanfang) klingt."""
        for slot in self.chords:
            if slot.start <= beat < slot.start + slot.dur:
                return slot.chord
        return self.chords[-1].chord if beat >= self.start else self.chords[0].chord

    def bar_slots(self, bar: int) -> list:
        """Akkorde in Takt bar (0 = erster Takt der Sektion)."""
        lo = self.start + bar * BEATS_PER_BAR
        hi = lo + BEATS_PER_BAR
        return [s for s in self.chords if lo <= s.start < hi]


@dataclass
class SongPlan:
    bpm: float
    style: StyleProfile
    tonic: int
    mode: str
    sections: list
    progressions: dict       # Sektionsart → gewählte Akkordfolge (Stufen)
    vocal_range: tuple = VOCAL_RANGE

    @property
    def total_beats(self) -> float:
        return self.sections[-1].end if self.sections else 0.0

    @property
    def seconds_per_beat(self) -> float:
        return 60.0 / self.bpm

    def section_at(self, beat: float) -> Section:
        for sec in self.sections:
            if sec.start <= beat < sec.end:
                return sec
        return self.sections[-1] if beat >= self.sections[-1].start else self.sections[0]

    def chord_at(self, beat: float) -> Chord:
        return self.section_at(beat).chord_at(beat)


def _parse_progression(text: str) -> list:
    """'IV | V7 | iii7 vi' → [['IV'], ['V7'], ['iii7', 'vi']]"""
    return [bar.split() for bar in text.split("|") if bar.strip()]


def _colorize(chord: Chord, symbol: str, color: str, kind: str) -> Chord:
    """Klangfarbe des Stils: Septakkorde (City Pop) oder add9 (Ballade) statt reiner Dreiklänge."""
    if chord.quality not in ("maj", "min") or color == "triad":
        return chord
    degree = symbol.lstrip("b#").rstrip("0123456789/")
    if color == "seventh":
        if chord.quality == "min":
            return Chord(chord.root, "m7", chord.bass)
        if degree.upper() == "V":
            return Chord(chord.root, "7", chord.bass)
        return Chord(chord.root, "maj7", chord.bass)
    if color == "add9" and kind in ("Chorus", "Bridge", "Intro", "Outro"):
        return Chord(chord.root, "add9" if chord.quality == "maj" else "madd9", chord.bass)
    return chord


def _section_bars(kind: str, bars: int, progression: list, mode_class: str, next_kind: Optional[str]) -> list:
    """Akkordstufen pro Takt dieser Sektion, inklusive Abschluss-Kadenz."""
    out = [list(progression[b % len(progression)]) for b in range(bars)]
    cad = CADENCES[mode_class]
    if kind in ("Chorus", "Outro") and bars >= 4:
        out[-2] = cad["end"][0].split()
        out[-1] = [cad["end"][1]]
    elif kind in ("PreChorus", "Build-up") or (kind == "Bridge" and next_kind == "Chorus"):
        out[-1] = [cad["to_chorus"]]
    return out


def build_plan(style: StyleProfile, bpm: float, structure: list, key: str, mode: str, section_config: dict,
               rng: random.Random, min_bars: Optional[dict] = None) -> SongPlan:
    """
    Legt Tonart, Akkorde und Energie jeder Sektion fest. Gleiche Sektionsarten bekommen dieselbe
    Akkordfolge (der zweite Refrain klingt wie der erste). Der letzte Refrain kann einen Halbton
    höher liegen, wie im J-Pop üblich.
    min_bars: {Sektionsart: Takte}, damit lange Liedtexte hineinpassen.
    """
    tonic = key_pc(key)
    mode_class = "minor" if is_minor(mode) else "major"
    min_bars = min_bars or {}

    # Intro, Outro und Drop spielen den Refrain an, der Build-up baut wie der Pre-Chorus auf
    chosen, progressions = {}, {}
    for kind in dict.fromkeys(structure):
        bank = SHARED_PROGRESSION.get(kind, kind)
        if bank not in chosen:
            chosen[bank] = rng.choice(progressions_for(style.name, mode_class, bank))
        progressions[kind] = chosen[bank]

    n_chorus = structure.count("Chorus")
    last_chorus_idx = max((i for i, k in enumerate(structure) if k == "Chorus"), default=-1)
    modulation = style.modulate_final_chorus if n_chorus >= 2 else 0

    sections, counts, beat = [], {}, 0.0
    for idx, kind in enumerate(structure):
        cfg = section_config.get(kind, {"bars": 4, "has_vocals": True})
        bars = max(int(cfg.get("bars", 4)), 1)
        if bpm < SLOW_BPM and bars >= 8:
            bars //= 2      # langsame Songs: halb so viele Takte, sonst dauert ein Refrain eine Minute
        while bars < min_bars.get(kind, 0):
            bars *= 2
        counts[kind] = counts.get(kind, 0) + 1
        sec_tonic = tonic + (modulation if (modulation and idx >= last_chorus_idx) else 0)
        energy = SECTION_ENERGY.get(kind, 0.6)
        if kind == "Verse" and counts[kind] > 1:
            energy += 0.05
        if kind == "Chorus" and idx == last_chorus_idx and n_chorus > 1:
            energy = 1.0
        sec = Section(
            kind=kind, occurrence=counts[kind], index=idx, start=beat, bars=bars,
            tonic=sec_tonic % 12, mode=mode, energy=min(energy, 1.0),
            has_vocals=bool(cfg.get("has_vocals", True)),
            next_kind=structure[idx + 1] if idx + 1 < len(structure) else None,
            prev_kind=structure[idx - 1] if idx > 0 else None,
            is_last_of_kind=kind not in structure[idx + 1:],
        )
        prog = _parse_progression(progressions[kind])
        for b, symbols in enumerate(_section_bars(kind, bars, prog, mode_class, sec.next_kind)):
            dur = BEATS_PER_BAR / len(symbols)
            for j, sym in enumerate(symbols):
                chord = _colorize(parse_roman(sym, sec.tonic), sym, style.chord_color, kind)
                sec.chords.append(ChordSlot(beat + b * BEATS_PER_BAR + j * dur, dur, chord))
        sections.append(sec)
        beat += sec.beats

    # Vor dem höheren Schlussrefrain führt die Dominante schon in die neue Tonart
    if modulation and last_chorus_idx > 0:
        before = sections[last_chorus_idx - 1]
        last = before.chords[-1]
        if last.chord.root == (before.tonic + 7) % 12:
            last.chord = last.chord.transposed(modulation)

    return SongPlan(bpm=bpm, style=style, tonic=tonic, mode=mode, sections=sections, progressions=progressions)

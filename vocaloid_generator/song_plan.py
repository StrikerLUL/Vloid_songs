# song_plan.py – Der Bauplan eines Songs: Sektionen, Tonarten, Akkorde und Energie, alles in Schlägen
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from styles import CADENCES, SECTION_ENERGY, StyleProfile, progressions_for
from theory import Chord, is_minor, key_pc, parse_chord_name, parse_roman

log = logging.getLogger(__name__)

BEATS_PER_BAR = 4            # beim Komponieren; im 3/4-Takt rückt meter.py die Töne danach zurecht
SLOW_BPM = 100
VOCAL_RANGE = (57, 79)       # A3 bis G5: Lage, in der die Melodie geschrieben wird
SHARED_PROGRESSION = {"Intro": "Chorus", "Outro": "Chorus", "Drop": "Chorus", "Solo": "Chorus", "Build-up": "PreChorus",
                      "Rap": "Verse", "Interlude": "Chorus", "Spoken": "Verse"}


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
    # Abwechslung im Ablauf: "breakdown" (nur wenige Instrumente, kein Schlagzeug) oder "halftime" bis zum
    # Schlag resume, danach spielt die Sektion wie gewohnt
    feel: str = ""
    resume: Optional[float] = None
    bar_beats: float = BEATS_PER_BAR     # Schläge pro Takt; im fertigen Plan eines 3/4-Songs 3 (meter.Meter.plan)

    @property
    def beats(self) -> float:
        return self.bars * self.bar_beats

    @property
    def end(self) -> float:
        return self.start + self.beats

    def chord_at(self, beat: float) -> Chord:
        """Akkord, der zum Schlag beat (ab Songanfang) klingt."""
        for slot in self.chords:
            if slot.start <= beat < slot.start + slot.dur:
                return slot.chord
        return self.chords[-1].chord if beat >= self.start else self.chords[0].chord


@dataclass
class SongPlan:
    bpm: float
    style: StyleProfile
    tonic: int
    mode: str
    sections: list
    progressions: dict       # Sektionsart → gewählte Akkordfolge (Stufen)
    vocal_range: tuple = VOCAL_RANGE
    key_change: int = 0      # Halbtöne, um die der letzte Refrain höher liegt
    meter: str = "4/4"       # Takt (meter.py); komponiert wird in Vierer-Takten

    @property
    def bar_beats(self) -> float:
        return self.sections[0].bar_beats if self.sections else BEATS_PER_BAR

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


def parse_custom(text: str) -> list:
    """
    Eigene Akkorde: Takte durch "|" getrennt ("F | G | Em Am"), ohne "|" ist jeder Akkord ein Takt ("F G Em Am").
    Erlaubt sind Akkordnamen (Fmaj7, C/E, Bb) und Stufen (IV, vi7, bVII). Wirft ValueError bei Unbekanntem.
    """
    bars = _parse_progression(text) if "|" in text else [[token] for token in text.split()]
    for bar in bars:
        for token in bar:
            custom_chord(token, 0, 0)
    return bars


def check_custom(text: str) -> str:
    """Fehlermeldung zu eigenen Akkorden, leer wenn alles stimmt."""
    try:
        parse_custom(text)
    except ValueError as e:
        return str(e)
    return ""


def custom_chord(token: str, home: int, tonic: int) -> Chord:
    """Ein eigener Akkord in einer Sektion mit Grundton tonic. Akkordnamen gelten in der Tonart home und rücken
    mit, wenn der Schlussrefrain höher liegt; Stufen beziehen sich immer auf tonic."""
    try:
        return parse_roman(token, tonic)
    except ValueError:
        return parse_chord_name(token).transposed(tonic - home)


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
    if color == "add9" and kind in ("Chorus", "Bridge", "Intro", "Interlude", "Outro"):
        return Chord(chord.root, "add9" if chord.quality == "maj" else "madd9", chord.bass)
    return chord


def _section_bars(kind: str, bars: int, progression: list, mode_class: str, next_kind: Optional[str],
                  cadence: Optional[dict] = None) -> list:
    """Akkordstufen pro Takt dieser Sektion, inklusive Abschluss-Kadenz. cadence: die eigene des Stils (style_dna)."""
    out = [list(progression[b % len(progression)]) for b in range(bars)]
    cad = cadence or CADENCES[mode_class]
    if kind in ("Chorus", "Outro") and bars >= 4:
        out[-2] = cad["end"][0].split()
        out[-1] = [cad["end"][1]]
    elif kind in ("PreChorus", "Build-up") or (kind == "Bridge" and next_kind == "Chorus"):
        out[-1] = cad["to_chorus"].split()
    return out


def build_plan(style: StyleProfile, bpm: float, structure: list, key: str, mode: str, section_config: dict,
               rng: random.Random, min_bars: Optional[dict] = None, custom_chords: Optional[dict] = None,
               rerolls: Optional[dict] = None, meter: str = "4/4", spice: float = 0.0, spice_seed: str = "",
               own_chords: bool = False, split: bool = False, turn: str = "", taste=None,
               blend: tuple = ()) -> SongPlan:
    """
    Legt Tonart, Akkorde und Energie jeder Sektion fest. Gleiche Sektionsarten bekommen dieselbe
    Akkordfolge (der zweite Refrain klingt wie der erste). Der letzte Refrain kann einen oder zwei
    Halbtöne höher liegen, wie im J-Pop üblich; dazu würfelt arrange() Breakdowns und Halftime-Teile.
    min_bars: {Sektionsart: Takte}, damit lange Liedtexte hineinpassen.
    custom_chords: {Sektionsart: eigene Akkorde (parse_custom)}; sie gelten genau so, ohne Schlusskadenz.
    rerolls: {Sektionsart: eigener Zufall}, um nur die Akkordfolge dieser Sektion neu zu würfeln (Intro, Outro
    und Solo teilen sie mit dem Refrain).
    meter: im 6/8-Takt sind die Takte aus section_config 6/8-Takte (zwei pro Kompositionstakt), jeder mit eigenem
    Akkord; die Zeiten bleiben in Kompositionsschlägen (meter.Meter.plan rechnet sie um).
    spice: Akkord-Würze 0 bis 1 (chord_spice.py) mit eigenem Zufall aus spice_seed; 0 = wie bis 1.2.
    own_chords: die eigenen Akkordfolgen und Kadenzen des Stils (1.4.0, style_dna.py); aus = wie bis 1.3.
    split: J-Pop Energy als Anison-Band ohne Royal Road (1.5.0, style_dna.SPLIT_PROGRESSIONS), auch ohne own_chords.
    turn: die Akkordwendung des Produzenten (produzent.turn): der Refrain spielt sie, mit der Kadenz des Stils.
    taste: der Geschmack aus den Daumen für die Melodie (geschmack.Taste): beliebte Akkordfolgen kommen öfter.
    blend: (zweiter Stil, Anteil, Seed) einer Stil-Mischung (1.5.0, style_dna.blend): so viele Akkordfolgen kommen
    aus dem zweiten Stil.
    """
    import chord_spice
    import geschmack
    import style_dna
    tonic = key_pc(key)
    mode_class = "minor" if is_minor(mode) else "major"
    min_bars = min_bars or {}
    custom = _own_chords(custom_chords or {})
    split = split and style.name in style_dna.SPLIT_PROGRESSIONS
    own_chords = own_chords or split

    # Intro, Outro und Drop spielen den Refrain an, der Build-up baut wie der Pre-Chorus auf
    chosen, progressions = {}, {}
    for kind in dict.fromkeys(structure):
        bank = SHARED_PROGRESSION.get(kind, kind)
        if bank not in chosen:
            source = style.name
            if blend and random.Random(f"{blend[2]}:blend-chords:{bank}").random() < blend[1]:
                source = blend[0]
                log.info("Stil-Mischung: %s spielt Akkorde aus %s", bank, source)
            options = (own_chords and style_dna.progressions(source, mode_class, bank, split)) or \
                progressions_for(source, mode_class, bank)
            chosen[bank] = geschmack.pick(rng, options, taste, lambda p, b=bank: ("chords", b, p))
            other = next((r for k, r in (rerolls or {}).items() if SHARED_PROGRESSION.get(k, k) == bank), None)
            if other is not None and len(options) > 1:
                chosen[bank] = other.choice([p for p in options if p != chosen[bank]])
            if chord_spice.marusa(bank, mode_class, spice, random.Random(f"{spice_seed}:marusa")):
                chosen[bank] = chord_spice.MARUSA
                log.info("Akkord-Würze: der Refrain spielt die Marusa-Folge")
            if bank == "Chorus" and turn:
                chosen[bank] = turn
                log.info("Produzent: der Refrain spielt deine Akkordwendung %s", turn)
        progressions[kind] = custom.get(kind, custom.get(SHARED_PROGRESSION.get(kind, kind), (chosen[bank],)))[0]

    cadence = style_dna.cadences(style.name, mode_class, split) if own_chords else None
    if own_chords:
        log.info("Akkorde je Stil (%s): %s", style.name,
                 "; ".join(f"{kind} {chosen[SHARED_PROGRESSION.get(kind, kind)]}" for kind in dict.fromkeys(structure)
                           if kind in ("Verse", "PreChorus", "Chorus", "Bridge")))
    n_chorus = structure.count("Chorus")
    last_chorus_idx = max((i for i, k in enumerate(structure) if k == "Chorus"), default=-1)
    modulation = rng.choice(style.key_changes) if n_chorus >= 2 else 0

    sections, counts, beat = [], {}, 0.0
    for idx, kind in enumerate(structure):
        cfg = section_config.get(kind, {"bars": 4, "has_vocals": True})
        bars = max(int(cfg.get("bars", 4)), 1)
        if meter == "6/8":
            bars = (bars + 1) // 2      # zwei 6/8-Takte (je zwei punktierte Viertel) sind ein Kompositionstakt
        elif bpm < SLOW_BPM and bars >= 8:
            bars //= 2      # langsame Songs: halb so viele Takte, sonst dauert ein Refrain eine Minute
        while bars < min_bars.get(kind, 0):
            bars *= 2
        counts[kind] = counts.get(kind, 0) + 1
        sec_tonic = tonic + (modulation if (modulation and idx >= last_chorus_idx) else 0)
        energy = default_energy(kind, counts[kind], kind == "Chorus" and idx == last_chorus_idx and n_chorus > 1)
        sec = Section(
            kind=kind, occurrence=counts[kind], index=idx, start=beat, bars=bars,
            tonic=sec_tonic % 12, mode=mode, energy=energy,
            has_vocals=bool(cfg.get("has_vocals", True)),
            next_kind=structure[idx + 1] if idx + 1 < len(structure) else None,
            prev_kind=structure[idx - 1] if idx > 0 else None,
            is_last_of_kind=kind not in structure[idx + 1:],
        )
        own = custom.get(kind) or custom.get(SHARED_PROGRESSION.get(kind, kind))
        per_bar = 2 if meter == "6/8" else 1          # im 6/8-Takt ein Akkord pro 6/8-Takt
        chord_bars, bar_len = bars * per_bar, BEATS_PER_BAR / per_bar
        if own:
            bar_symbols = [own[1][b % len(own[1])] for b in range(chord_bars)]
        else:
            bar_symbols = _section_bars(kind, chord_bars, _parse_progression(progressions[kind]), mode_class,
                                        sec.next_kind, cadence)
            bar_symbols, spiced = chord_spice.season(bar_symbols, kind, mode_class, spice,
                                                     random.Random(f"{spice_seed}:{kind}:{chord_bars}"))
            if spiced and counts[kind] == 1:
                log.info("Akkord-Würze im %s: %s", kind, ", ".join(spiced))
        for b, symbols in enumerate(bar_symbols):
            dur = bar_len / len(symbols)
            for j, sym in enumerate(symbols):
                if own:
                    chord = custom_chord(sym, tonic, sec.tonic)
                else:
                    chord = _colorize(parse_roman(sym, sec.tonic), sym, style.chord_color, kind)
                sec.chords.append(ChordSlot(beat + b * bar_len + j * dur, dur, chord))
        sections.append(sec)
        beat += sec.beats

    # Vor dem höheren Schlussrefrain führt die Dominante schon in die neue Tonart
    if modulation and last_chorus_idx > 0:
        before = sections[last_chorus_idx - 1]
        last = before.chords[-1]
        if last.chord.root == (before.tonic + 7) % 12:
            last.chord = last.chord.transposed(modulation)

    arrange(sections, style, rng)
    return SongPlan(bpm=bpm, style=style, tonic=tonic, mode=mode, sections=sections, progressions=progressions,
                    key_change=modulation, meter=meter)


def default_energy(kind: str, occurrence: int, last_chorus: bool) -> float:
    """Die Energie einer Sektion, wie der Song sie ohne Spannungskurve hat: die zweite Strophe etwas mehr, der letzte
    von mehreren Refrains am meisten."""
    energy = SECTION_ENERGY.get(kind, 0.6)
    if kind == "Verse" and occurrence > 1:
        energy += 0.05
    if last_chorus:
        energy = 1.0
    return min(energy, 1.0)


def _own_chords(custom_chords: dict) -> dict:
    """{Sektionsart: (Text, Takte)} der eigenen Akkorde, die sich lesen lassen; die anderen spielen wie der Stil."""
    own = {}
    for kind, text in custom_chords.items():
        if not text.strip():
            continue
        try:
            own[kind] = (text.strip(), parse_custom(text))
        except ValueError as e:
            log.warning("Eigene Akkorde für %s nicht verstanden (%s), es spielen die Akkorde des Stils", kind, e)
    return own


def arrange(sections: list, style: StyleProfile, rng: random.Random) -> None:
    """
    Würfelt, wo der Song vom Gewohnten abweicht, jeweils für die erste Hälfte einer Sektion:
    der letzte Refrain beginnt leise (Ochisabi), die Bridge als Breakdown, die zweite Strophe im Halftime.
    """
    choruses = [s for s in sections if s.kind == "Chorus"]
    candidates = []
    if len(choruses) >= 2:
        candidates.append((choruses[-1], "breakdown", style.breakdown_chance))
    candidates += [(s, "breakdown", style.bridge_breakdown_chance) for s in sections if s.kind == "Bridge"]
    candidates += [(s, "halftime", style.halftime_chance) for s in sections if s.kind == "Verse" and s.occurrence >= 2]
    for sec, feel, chance in candidates:
        if rng.random() < chance and sec.bars >= 4:
            sec.feel = feel
            sec.resume = sec.start + (sec.bars // 2) * BEATS_PER_BAR


def describe_arrangement(plan: SongPlan) -> list:
    """Was an diesem Song besonders ist, in Worten (fürs Protokoll)."""
    out = [f"Schlussrefrain {plan.key_change} Halbton höher" if plan.key_change == 1 else
           f"Schlussrefrain {plan.key_change} Halbtöne höher"] if plan.key_change else []
    for sec in plan.sections:
        if sec.feel == "breakdown":
            out.append("leiser Anfang im letzten Refrain" if sec.kind == "Chorus" else f"{sec.kind} als Breakdown")
        elif sec.feel == "halftime":
            out.append(f"{sec.occurrence}. {sec.kind} beginnt im Halftime")
    return out


# ── Zeiten der Sektionen in Sekunden (für Gesang und Mix) ─────────────────────
def sections_in_seconds(plan) -> list:
    """[(Start, Ende in Sekunden, Sektionsart)]."""
    spb = plan.seconds_per_beat
    return [(sec.start * spb, sec.end * spb, sec.kind) for sec in plan.sections]


def final_chorus(plan) -> Optional[tuple]:
    """(Start, Ende) des letzten Refrains in Schlägen; bei leisem Anfang (Breakdown) ab dem vollen Teil."""
    choruses = [sec for sec in plan.sections if sec.kind == "Chorus" and sec.has_vocals] if plan else []
    if not choruses:
        return None
    sec = choruses[-1]
    return (sec.resume if sec.feel == "breakdown" and sec.resume is not None else sec.start), sec.end


def chorus_windows(plan) -> list:
    """[(Start, Ende in Sekunden)] der Refrains, ohne ihren leisen Anfang (Breakdown)."""
    if plan is None:
        return []
    spb = plan.seconds_per_beat
    # im leisen Anfang eines Refrains (Breakdown) bleibt der Gesang einfach
    return [((sec.resume if sec.feel == "breakdown" else sec.start) * spb, sec.end * spb)
            for sec in plan.sections if sec.kind == "Chorus"]

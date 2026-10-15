# orchestrator.py – Setzt Bauplan, Melodie, Begleitung und Schlagzeug zu einem Song zusammen
import logging
import os
import random
from dataclasses import replace

import pretty_midi

import grooves
from drums import CRASH, KICK, OPEN_HAT, HAT, PEDAL_HAT, RIDE, TAMBOURINE, TOMS, drum_section, lead_in
from lyrics import parse_lyrics
from melody_import import imported_bars
from melody_writer import harmony_line, melody_data, required_bars, write_vocal_melody
from parts import LAYER_PROGRAMS, PARTS, Ev, lead_hook, lead_solo
from song_plan import BEATS_PER_BAR, build_plan, describe_arrangement
from styles import get_style

log = logging.getLogger(__name__)

INSTRUMENTS = ("piano", "bass", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "perc",
               "drums", "melody")
TRACK_NAMES = {
    "piano": "Piano", "bass": "Bass", "guitar": "Guitar", "strings": "Strings", "synth": "Synth",
    "brass": "Brass", "bells": "Bells", "choir": "Choir", "counter": "Counter", "perc": "Percussion",
    "drums": "Drums", "melody": "Lead",
}
DRUM_TRACKS = ("drums", "perc")
# Stereobild: Unterspuren mit eigenem Panorama (MIDI-CC 10, 64 = Mitte)
LAYER_PAN = {"left": 22, "right": 106, "hats": 30, "cymbals": 98, "toms": 72}
DOUBLE_TRACKED = {"strummed", "palm_mute", "power_chords"}

# Zeitliche Ungenauigkeit wie bei echten Musikern, in Sekunden (bei jitter_scale = 1)
TIMING_SPREAD = {"drums": 0.003, "bass": 0.004, "piano": 0.006, "guitar": 0.006, "strings": 0.008,
                 "synth": 0.002, "brass": 0.006, "melody": 0.004, "bells": 0.003, "choir": 0.01,
                 "counter": 0.006, "perc": 0.006}
SWING_MAX = 1 / 6                       # Swing 0.5 schiebt die zweite Sechzehntel um 1/12 Schlag
# Bis zu diesem Swing (Stil plus Regler) spielt der echte Schlagzeuger: der Grundwert 0,12 ist nur ein Hauch, erst
# Stile, die wirklich swingen (Lo-Fi), spielen die eingebauten Grooves. Sein eigenes Timing ersetzt dann den Swing.
GROOVE_SWING_UNTIL = 0.2
SLIDE_SECONDS, SLIDE_STEPS = 0.08, 8     # so lange gleitet ein Bass-Slide, in so vielen Schritten
# Teile mit eigenem Zufall (wie settings.REROLLABLE): Akkorde und Ablauf, Gesangsmelodie, jedes Instrument
REROLLABLE = ("chords",) + INSTRUMENTS


def _default_lyrics() -> dict:
    from settings import DEFAULT_LYRICS
    return parse_lyrics(DEFAULT_LYRICS)


def orchestrate_song(genre: str, bpm: float, structure: list, key: str, mode: str, section_config: dict,
                     output_dir: str = None, lyrics: dict = None, swing: float = None,
                     jitter_scale: float = 1.0, instrument_styles: dict = None, style: str = None,
                     vocal_range: tuple = None, variations: dict = None, custom_chords: dict = None,
                     imported_melody: dict = None, melody_edits: dict = None, motifs=None,
                     melody_lengths: dict = None, real_grooves: bool = False, lively_bass: bool = False,
                     guitar_strums: bool = False, singable: bool = False) -> dict:
    """
    Komponiert den kompletten Song und schreibt eine MIDI-Datei pro Instrument nach output_dir.

    style: Name des Stils (z. B. "Dark Vocaloid"); ohne Angabe entscheidet genre.
    lyrics: {Sektion: [Silben]}; Sektionen ohne Text singen den Standardtext.
    swing: verschiebt jede zweite Sechzehntel nach hinten (0 bis 0,5), zusätzlich zum Swing des Stils.
    instrument_styles: {Instrument: Spielweise}; "default" nimmt die Spielweise des Stils.
    vocal_range: (tiefster, höchster Ton) der Gesangsmelodie, passend zur Stimme.
    variations: {Teil: Zähler} aus REROLLABLE; ein höherer Zähler würfelt nur diesen Teil neu, der Rest des
    Songs bleibt bei gleichem Seed gleich. "Teil:Sektionsart" (z. B. "melody:Chorus") würfelt ihn nur dort neu.
    custom_chords: {Sektionsart: eigene Akkorde}, siehe song_plan.parse_custom.
    imported_melody: {Sektionsart: Melodie aus melody_import.load}; dort singt sie statt der komponierten.
    melody_edits: {Schlag: Tonhöhe} (settings.edit_key): Töne der Gesangsmelodie, die von Hand geändert wurden.
    melody_lengths: {Schlag: Länge in Schlägen}: Töne, die von Hand kürzer oder länger gemacht wurden.
    motifs: zusätzliche Rhythmen und Gesten für die Gesangsmelodie (motifs.for_settings), None = nur eingebaute.
    real_grooves: Grooves und Fills echter Schlagzeuger (grooves.py), soweit geladen; Stile, die wirklich swingen (ab
    GROOVE_SWING_UNTIL), spielen weiter die eingebauten.
    lively_bass: Ghost-Notes und Slides im Bass. guitar_strums: Anschlagmuster je nach Energie statt eines festen.
    singable: die komponierte Gesangsmelodie auf Singbarkeit prüfen (melody_writer.make_singable).
    Rückgabe: {Instrument: [pretty_midi.Note]}, dazu "melody_data", "silben", "vocal_melody", die zweite
    Stimme für den Refrain ("harmony_data", "harmony_silben") und "plan".
    """
    profile = get_style(style or genre)
    dice = Dice(random.getrandbits(32), variations or {})
    swing = min(1.0, profile.swing + (swing or 0.0))     # Stile mit eigenem Swing (Lo-Fi) legen ihn dazu
    log.info("Komponiere: Stil %s, %s BPM, %s-%s", profile.name, bpm, key, mode)

    sung = {**_default_lyrics(), **(lyrics or {})}
    imported_melody = {kind: m for kind, m in (imported_melody or {}).items() if m and kind in structure}
    min_bars = {kind: max(required_bars(len(sung.get(kind, []))), imported_bars(imported_melody.get(kind, [])))
                for kind in set(structure) if section_config.get(kind, {}).get("has_vocals", True)}
    plan = build_plan(profile, bpm, structure, key, mode, section_config, dice.part("chords"), min_bars,
                      custom_chords=custom_chords, rerolls=dice.rerolled_kinds("chords"))
    if vocal_range:
        plan.vocal_range = tuple(vocal_range)
    vocal_notes = write_vocal_melody(plan, sung, dice.part("melody"), rerolls=dice.rerolled_kinds("melody"),
                                     imported=imported_melody, motifs=motifs, singable=singable)
    _apply_edits(vocal_notes, melody_edits or {}, melody_lengths or {})

    arrangement = describe_arrangement(plan)
    if arrangement:
        log.info("Ablauf: %s", ", ".join(arrangement))

    events = {inst: [] for inst in INSTRUMENTS}
    contexts = {inst: {"vocal": vocal_notes} for inst in PARTS}
    contexts["bass"]["lively"] = lively_bass and dice.label("bass")      # eigener Zufall: aus = wie bisher
    contexts["guitar"]["strums"] = guitar_strums and dice.label("guitar")
    drummer = grooves.for_song(bpm, dice.label("drums")) if real_grooves and swing < GROOVE_SWING_UNTIL else None
    seen = {}
    for sec in plan.sections:
        seen[sec.kind] = seen.get(sec.kind, 0) + 1
        rngs = {inst: dice.section(inst, sec.kind, seen[sec.kind]) for inst in INSTRUMENTS}
        for piece in _pieces(sec):
            for inst, part in PARTS.items():
                pattern = _pattern(profile, piece, inst, instrument_styles)
                for single in (pattern or "").split("+"):
                    if single:
                        events[inst] += part(single, piece, plan, rngs[inst], contexts[inst])
            lead = _pattern(profile, piece, "melody")
            if lead == "hook":
                events["melody"] += lead_hook(piece, plan, vocal_notes)
            elif lead == "solo":
                events["melody"] += lead_solo(piece, plan, vocal_notes, rngs["melody"])
            if piece.feel == "breakdown":
                events["drums"] += lead_in(piece, rngs["drums"])
            else:
                groove = "halftime" if piece.feel == "halftime" else profile.groove(sec.kind)
                events["drums"] += drum_section(piece, groove, rngs["drums"], drummer)

    _breaks_before_chorus(plan, events)
    _final_chord(plan, events)
    _spread_stereo(plan, profile, events, instrument_styles)

    tracks = {}
    for inst in INSTRUMENTS:
        swung = 0.0 if inst == "drums" and drummer is not None else swing     # der Schlagzeuger hat sein Timing
        tracks[inst] = _to_notes(events[inst], bpm, inst, dice.label(inst), swung, jitter_scale)
    out_dir = output_dir or _default_output()
    os.makedirs(out_dir, exist_ok=True)
    for inst in INSTRUMENTS:
        _write_midi(os.path.join(out_dir, f"{inst}.mid"), inst, events[inst], tracks[inst], profile, bpm)
    vocal_track = [pretty_midi.Note(velocity=100, pitch=n.pitch, start=n.start * 60 / bpm,
                                    end=(n.start + n.dur) * 60 / bpm) for n in vocal_notes]
    _write_simple_midi(os.path.join(out_dir, "vocal_melody.mid"), vocal_track, profile.programs["melody"], bpm)

    data, syllables = melody_data(vocal_notes)
    tracks["harmony_data"], tracks["harmony_silben"] = melody_data(harmony_line(plan, vocal_notes))
    tracks["vocal_melody"] = vocal_track
    tracks["melody_data"] = data
    tracks["silben"] = syllables
    tracks["plan"] = plan
    log.info("Song: %d Takte, %.0f Sekunden", plan.total_beats / BEATS_PER_BAR, plan.total_beats * 60 / bpm)
    return tracks


BREAKDOWN_ENERGY = 0.4


def _pieces(sec) -> list:
    """
    Die Sektion, wie die Band sie spielt: meist am Stück, bei Breakdown oder Halftime-Anfang in zwei Teilen.
    Der erste Teil trägt feel, der zweite spielt normal und setzt mit Crash wieder ein.
    """
    if not sec.feel or sec.resume is None:
        return [sec]
    bars = int(round((sec.resume - sec.start) / BEATS_PER_BAR))
    first = replace(sec, bars=bars, chords=[c for c in sec.chords if c.start < sec.resume], next_kind=sec.kind,
                    resume=None, energy=BREAKDOWN_ENERGY if sec.feel == "breakdown" else sec.energy)
    second = replace(sec, start=sec.resume, bars=sec.bars - bars, chords=[c for c in sec.chords if c.start >= sec.resume],
                     prev_kind=sec.kind, feel="", resume=None)
    return [first, second]


def _piece_at(plan, beat: float):
    pieces = _pieces(plan.section_at(beat))
    return next((p for p in pieces if p.start <= beat < p.end), pieces[-1])


def _apply_edits(vocal_notes: list, edits: dict, lengths: dict = None) -> None:
    """Von Hand geänderte Töne (Höhe, Länge) übernehmen; Band, zweite Stimme und Chor folgen ihnen. Ein längerer
    Ton endet spätestens, wo der nächste beginnt."""
    from settings import edit_key
    lengths = lengths or {}
    changed = 0
    for i, n in enumerate(vocal_notes):
        key = edit_key(n.start)
        pitch, length = edits.get(key), lengths.get(key)
        if pitch is not None:
            n.pitch = pitch
        if length is not None:
            following = [m.start for m in vocal_notes[i + 1:] if m.start > n.start]
            n.dur = min(length, min(following) - n.start) if following else length
        changed += pitch is not None or length is not None
    if edits or lengths:
        log.info("Geänderte Töne in der Melodie: %d von %d", changed, len(set(edits) | set(lengths)))


class Dice:
    """
    Der Zufall des Songs, aufgeteilt nach Teil und Sektion: was ein Teil in einer Sektion würfelt, ändert nichts
    an den anderen Teilen und Sektionen. Ein Zähler in variations ("bass" oder "bass:Chorus") gibt dem Teil im
    ganzen Song oder nur in dieser Sektionsart einen neuen Zufall.
    """

    def __init__(self, base: int, variations: dict):
        self.base = base
        self.variations = variations

    def label(self, part: str) -> str:
        return f"{self.base}:{part}:{int(self.variations.get(part, 0))}"

    def part(self, part: str) -> random.Random:
        return random.Random(self.label(part))

    def section(self, part: str, kind: str, occurrence: int) -> random.Random:
        """Der Zufall eines Teils in einer Sektion (occurrence: der wievielte Refrain usw.)."""
        again = int(self.variations.get(f"{part}:{kind}", 0))
        return random.Random(f"{self.label(part)}:{kind}{occurrence}:{again}")

    def rerolled_kinds(self, part: str) -> dict:
        """{Sektionsart: neuer Zufall} für die Sektionsarten, in denen dieser Teil neu gewürfelt wurde."""
        out = {}
        for key, n in self.variations.items():
            name, _, kind = key.partition(":")
            if name == part and kind:
                out[kind] = random.Random(f"{self.label(part)}:{kind}:{int(n)}")
        return out


def _default_output() -> str:
    import config
    return config.OUTPUT_ORDNER


# Sektionen, in denen ein Instrument mitspielt, das der Stil sonst gar nicht nutzt, wenn man ihm eine Spielweise gibt
FULL_BAND = ("Intro", "PreChorus", "Chorus", "Outro")


def _pattern(profile, sec, inst: str, overrides: dict = None):
    """Spielweise eines Instruments in einer Sektion (oder einem Teil aus _pieces): die vom Stil, oder die in der
    App gewählte."""
    pattern = profile.part(sec.kind, inst, sec.occurrence, sec.is_last_of_kind, sec.feel)
    chosen = (overrides or {}).get(inst)
    if not chosen or chosen == "default":
        return pattern
    if pattern:
        return chosen
    unused_by_style = not any(parts.get(inst) for parts in profile.parts.values())
    return chosen if unused_by_style and sec.kind in FULL_BAND else None


def _breaks_before_chorus(plan, events: dict) -> None:
    """Der letzte Schlag vor dem Refrain gehört dem Schlagzeug-Fill und dem Gesang: die Band setzt kurz aus."""
    for sec in plan.sections:
        if sec.next_kind != "Chorus" or sec.kind not in ("PreChorus", "Build-up"):
            continue
        cut = sec.end - 1.0
        for inst, evs in events.items():
            if inst in ("drums", "melody"):
                continue
            kept = []
            for e in evs:
                if cut - 1e-6 <= e.start < sec.end:
                    continue
                if e.start < cut < e.start + e.dur and e.start >= sec.start:
                    e.dur = cut - e.start
                kept.append(e)
            events[inst] = kept


def _final_chord(plan, events: dict) -> None:
    """Im letzten Takt klingt nur noch der Schlussakkord aus."""
    last = plan.sections[-1]
    if last.kind not in ("Outro", "Chorus"):
        return
    downbeat = last.end - BEATS_PER_BAR
    for inst, evs in events.items():
        kept = []
        for e in evs:
            if e.start > downbeat + 0.02:
                continue
            if abs(e.start - downbeat) <= 0.02 and inst not in DRUM_TRACKS:
                e.dur = BEATS_PER_BAR
            kept.append(e)
        if inst == "perc":
            kept = [e for e in kept if e.start < downbeat - 1e-6]
        if inst == "drums":
            kept = [e for e in kept if e.start < downbeat - 1e-6 or e.pitch in (KICK, CRASH)]
            if not any(abs(e.start - downbeat) <= 0.02 and e.pitch == CRASH for e in kept):
                kept.append(Ev(downbeat, 2.0, CRASH, 110))
        events[inst] = kept


def _spread_stereo(plan, profile, events: dict, overrides: dict = None) -> None:
    """Gitarren doppelt eingespielt links und rechts, Becken und Hi-Hats neben Kick und Snare."""
    for e in events["drums"]:
        if e.pitch in (HAT, PEDAL_HAT, OPEN_HAT, TAMBOURINE):
            e.layer = "hats"
        elif e.pitch in (CRASH, RIDE):
            e.layer = "cymbals"
        elif e.pitch in TOMS:
            e.layer = "toms"
    doubled = []
    for e in events["guitar"]:
        if _pattern(profile, _piece_at(plan, e.start), "guitar", overrides) in DOUBLE_TRACKED:
            e.layer = "left"
            doubled.append(Ev(e.start, e.dur, e.pitch, max(1, e.vel - 6), "right"))
    events["guitar"] += doubled


def _to_notes(evs: list, bpm: float, inst: str, label: str, swing: float, jitter_scale: float) -> list:
    """Schläge in Sekunden, mit Swing und kleinen Ungenauigkeiten. Jeder Ton würfelt für sich (label, Zeit, Höhe),
    damit ein neu gewürfelter Refrain die Töne in den anderen Sektionen nicht verschiebt."""
    spb = 60.0 / bpm
    spread = TIMING_SPREAD.get(inst, 0.004) * jitter_scale
    notes = []
    for e in sorted(evs, key=lambda e: (e.start, e.pitch)):
        rng = random.Random(f"{label}:{e.start:.4f}:{e.pitch}:{e.layer}")
        beat = e.start
        sixteenth = beat * 4
        if abs(sixteenth - round(sixteenth)) < 1e-6 and round(sixteenth) % 2 == 1:
            beat += swing * SWING_MAX * 0.5
        jitter = max(-2.5 * spread, min(2.5 * spread, rng.gauss(0.0, spread))) if spread else 0.0
        start = max(0.0, beat * spb + jitter)
        end = start + max(e.dur * spb, 0.02)
        vel = max(1, min(127, e.vel + rng.randint(-4, 4)))
        notes.append(pretty_midi.Note(velocity=vel, pitch=int(e.pitch), start=start, end=end))
    return notes


def _write_midi(path: str, inst: str, evs: list, notes: list, profile, bpm: float) -> None:
    """Eine Spur pro Klang: Unterspuren (z. B. Pad im Synth-Kanal) bekommen ihr eigenes Programm."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    ordered = sorted(evs, key=lambda e: (e.start, e.pitch))
    layers = {}
    for e, n in zip(ordered, notes):
        layers.setdefault(e.layer, []).append((e, n))
    if not layers:
        layers[""] = []
    for layer, pairs in layers.items():
        if inst == "drums":
            program, is_drum = profile.drum_kit, True
        elif inst == "perc":
            program, is_drum = profile.program("perc"), True
        else:
            # Unterspuren mit eigenem Klang: Pad, Pizzicato usw. für alle Stile, das Solo je nach Stil
            program, is_drum = LAYER_PROGRAMS.get(layer, profile.programs.get(layer, profile.program(inst))), False
        name = TRACK_NAMES[inst] + (f" {layer}" if layer else "")
        track = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
        track.notes = [n for _, n in pairs]
        track.pitch_bends = _slides(pairs)
        if layer in LAYER_PAN:
            track.control_changes.append(pretty_midi.ControlChange(number=10, value=LAYER_PAN[layer], time=0.0))
        pm.instruments.append(track)
    pm.write(path)


def _slides(pairs: list) -> list:
    """Pitch-Bends für Töne, die hineingleiten (Ev.slide): erst daneben, dann in SLIDE_SECONDS auf den Ton."""
    bends = []
    for e, n in pairs:
        if not e.slide:
            continue
        semitones = max(-2, min(2, e.slide))
        for k in range(SLIDE_STEPS + 1):
            share = 1 - k / SLIDE_STEPS
            value = round(semitones / 2 * 8191 * share * share)     # erst schnell, dann sanft ankommen
            bends.append(pretty_midi.PitchBend(value, max(0.0, n.start - 0.002) + k * SLIDE_SECONDS / SLIDE_STEPS))
    return bends


def _write_simple_midi(path: str, notes: list, program: int, bpm: float) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    track = pretty_midi.Instrument(program=program, name="Vocal Melody")
    track.notes = notes
    pm.instruments.append(track)
    pm.write(path)

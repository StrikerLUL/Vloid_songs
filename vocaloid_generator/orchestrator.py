# orchestrator.py – Setzt Bauplan, Melodie, Begleitung und Schlagzeug zu einem Song zusammen
import logging
import os
import random

import pretty_midi

from drums import CRASH, KICK, OPEN_HAT, HAT, PEDAL_HAT, RIDE, TAMBOURINE, TOMS, drum_section
from lyrics import parse_lyrics
from melody_writer import harmony_line, melody_data, required_bars, write_vocal_melody
from parts import LAYER_PROGRAMS, PARTS, Ev, lead_hook
from song_plan import BEATS_PER_BAR, build_plan
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


def _default_lyrics() -> dict:
    from settings import DEFAULT_LYRICS
    return parse_lyrics(DEFAULT_LYRICS)


def orchestrate_song(genre: str, bpm: float, structure: list, key: str, mode: str, section_config: dict,
                     output_dir: str = None, lyrics: dict = None, swing: float = None,
                     jitter_scale: float = 1.0, instrument_styles: dict = None, style: str = None,
                     vocal_range: tuple = None) -> dict:
    """
    Komponiert den kompletten Song und schreibt eine MIDI-Datei pro Instrument nach output_dir.

    style: Name des Stils (z. B. "Dark Vocaloid"); ohne Angabe entscheidet genre.
    lyrics: {Sektion: [Silben]}; Sektionen ohne Text singen den Standardtext.
    instrument_styles: {Instrument: Spielweise}; "default" nimmt die Spielweise des Stils.
    vocal_range: (tiefster, höchster Ton) der Gesangsmelodie, passend zur Stimme.
    Rückgabe: {Instrument: [pretty_midi.Note]}, dazu "melody_data", "silben", "vocal_melody", die zweite
    Stimme für den Refrain ("harmony_data", "harmony_silben") und "plan".
    """
    profile = get_style(style or genre)
    rng = random.Random(random.getrandbits(32))
    swing = profile.swing if swing is None else swing
    log.info("Komponiere: Stil %s, %s BPM, %s-%s", profile.name, bpm, key, mode)

    sung = {**_default_lyrics(), **(lyrics or {})}
    min_bars = {kind: required_bars(len(sung.get(kind, [])))
                for kind in set(structure) if section_config.get(kind, {}).get("has_vocals", True)}
    plan = build_plan(profile, bpm, structure, key, mode, section_config, rng, min_bars)
    if vocal_range:
        plan.vocal_range = tuple(vocal_range)
    vocal_notes = write_vocal_melody(plan, sung, rng)

    events = {inst: [] for inst in INSTRUMENTS}
    contexts = {inst: {"vocal": vocal_notes} for inst in PARTS}
    for sec in plan.sections:
        for inst, part in PARTS.items():
            pattern = _pattern(profile, sec, inst, instrument_styles)
            for single in (pattern or "").split("+"):
                if single:
                    events[inst] += part(single, sec, plan, rng, contexts[inst])
        if _pattern(profile, sec, "melody") == "hook":
            events["melody"] += lead_hook(sec, plan, vocal_notes)
        events["drums"] += drum_section(sec, profile.groove(sec.kind), rng)

    _breaks_before_chorus(plan, events)
    _final_chord(plan, events)
    _spread_stereo(plan, profile, events, instrument_styles)

    tracks = {}
    for inst in INSTRUMENTS:
        tracks[inst] = _to_notes(events[inst], bpm, inst, rng, swing, jitter_scale)
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


def _default_output() -> str:
    import config
    return config.OUTPUT_ORDNER


# Sektionen, in denen ein Instrument mitspielt, das der Stil sonst gar nicht nutzt, wenn man ihm eine Spielweise gibt
FULL_BAND = ("Intro", "PreChorus", "Chorus", "Outro")


def _pattern(profile, sec, inst: str, overrides: dict = None):
    """Spielweise eines Instruments in einer Sektion: die vom Stil, oder die in der App gewählte."""
    pattern = profile.part(sec.kind, inst, sec.occurrence, sec.is_last_of_kind)
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
        sec = plan.section_at(e.start)
        if _pattern(profile, sec, "guitar", overrides) in DOUBLE_TRACKED:
            e.layer = "left"
            doubled.append(Ev(e.start, e.dur, e.pitch, max(1, e.vel - 6), "right"))
    events["guitar"] += doubled


def _to_notes(evs: list, bpm: float, inst: str, rng: random.Random, swing: float, jitter_scale: float) -> list:
    spb = 60.0 / bpm
    spread = TIMING_SPREAD.get(inst, 0.004) * jitter_scale
    notes = []
    for e in sorted(evs, key=lambda e: (e.start, e.pitch)):
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
        layers.setdefault(e.layer, []).append(n)
    if not layers:
        layers[""] = []
    for layer, layer_notes in layers.items():
        if inst == "drums":
            program, is_drum = profile.drum_kit, True
        elif inst == "perc":
            program, is_drum = profile.program("perc"), True
        else:
            program, is_drum = LAYER_PROGRAMS.get(layer, profile.program(inst)), False
        name = TRACK_NAMES[inst] + (f" {layer}" if layer else "")
        track = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
        track.notes = layer_notes
        if layer in LAYER_PAN:
            track.control_changes.append(pretty_midi.ControlChange(number=10, value=LAYER_PAN[layer], time=0.0))
        pm.instruments.append(track)
    pm.write(path)


def _write_simple_midi(path: str, notes: list, program: int, bpm: float) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    track = pretty_midi.Instrument(program=program, name="Vocal Melody")
    track.notes = notes
    pm.instruments.append(track)
    pm.write(path)

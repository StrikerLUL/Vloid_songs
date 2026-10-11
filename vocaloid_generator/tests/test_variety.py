# test_variety.py – Abwechslung im Ablauf (leiser Schlussrefrain, Breakdown, Halftime) und Orchester in der Ballade
from dataclasses import replace

import numpy as np
import pretty_midi
import pytest

import config
import styles
from drums import CRASH, KICK, SNARE
from fx import render_fx
from melody_writer import harmony_line
from orchestrator import orchestrate_song
from pipeline import _chorus_windows, seed_everything
from song_plan import describe_arrangement

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]


def compose(tmp_path, style="J-Pop Energy", seed=5, bpm=160, **changes):
    if changes:
        styles.STYLES[style] = replace(styles.STYLES[style], **changes)
    seed_everything(seed)
    return orchestrate_song(genre=style, bpm=bpm, structure=STRUCTURE, key="A", mode="minor",
                            section_config=config.SECTION_CONFIG, output_dir=str(tmp_path), style=style)


@pytest.fixture(autouse=True)
def restore_styles(monkeypatch):
    monkeypatch.setattr(styles, "STYLES", dict(styles.STYLES))


def notes_between(tracks, inst, lo, hi):
    spb = 60.0 / tracks["plan"].bpm
    return [n for n in tracks[inst] if lo * spb - 0.03 <= n.start < hi * spb - 0.03]


@pytest.fixture(scope="module")
def varied(tmp_path_factory):
    """Ein Song, in dem alles Abwechslung vorkommt: leiser Schlussrefrain, Bridge als Breakdown, Halftime."""
    saved = dict(styles.STYLES)
    try:
        return compose(tmp_path_factory.mktemp("varied"), breakdown_chance=1.0, bridge_breakdown_chance=1.0,
                       halftime_chance=1.0, key_changes=(2,))
    finally:
        styles.STYLES.clear()
        styles.STYLES.update(saved)


def test_the_plan_says_what_is_special(varied):
    plan = varied["plan"]
    assert plan.key_change == 2
    assert describe_arrangement(plan) == ["Schlussrefrain 2 Halbtöne höher", "2. Verse beginnt im Halftime",
                                          "Bridge als Breakdown", "leiser Anfang im letzten Refrain"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    assert last.feel == "breakdown" and last.resume == last.start + last.beats / 2


def test_quiet_final_chorus_starts_without_band_and_drums(varied):
    plan = varied["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    quiet = (last.start, last.resume)
    assert not notes_between(varied, "bass", *quiet) and not notes_between(varied, "guitar", *quiet)
    assert notes_between(varied, "piano", *quiet) and notes_between(varied, "strings", *quiet)
    # Schlagzeug: nur der Wirbel im letzten Takt vor dem Einsatz
    drums = notes_between(varied, "drums", last.start, last.resume - 4)
    assert not drums
    roll = notes_between(varied, "drums", last.resume - 4, last.resume)
    assert sum(n.pitch == SNARE for n in roll) >= 10
    hits = {n.pitch for n in notes_between(varied, "drums", last.resume, last.resume + 0.1)}
    assert {CRASH, KICK} <= hits
    assert notes_between(varied, "bass", last.resume, last.end)


def test_quiet_part_is_softer_than_the_rest_of_the_chorus(varied):
    last = [s for s in varied["plan"].sections if s.kind == "Chorus"][-1]
    quiet = np.mean([n.velocity for n in notes_between(varied, "piano", last.start, last.resume)])
    loud = np.mean([n.velocity for n in notes_between(varied, "piano", last.resume, last.end)])
    assert quiet < loud - 15


def test_singer_is_alone_in_the_quiet_part(varied):
    plan = varied["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    spb = plan.seconds_per_beat
    harmony_starts = [t for t, _ in _starts(varied["harmony_data"])]
    assert not [t for t in harmony_starts if last.start <= t < last.resume]
    assert [t for t in harmony_starts if last.resume <= t < last.end]
    windows = _chorus_windows(plan)
    assert windows[-1] == (last.resume * spb, last.end * spb)


def _starts(data):
    t, out = 0.0, []
    for pitch, dur in data:
        if pitch is not None:
            out.append((t, pitch))
        t += dur
    return out


def test_halftime_verse_puts_the_snare_on_beat_three(varied):
    verse = [s for s in varied["plan"].sections if s.kind == "Verse"][1]
    snares = notes_between(varied, "drums", verse.start, verse.resume - 4)
    spb = varied["plan"].seconds_per_beat
    offsets = {round((n.start / spb) % 4) % 4 for n in snares if n.pitch == SNARE and n.velocity > 60}
    assert offsets == {2}
    later = notes_between(varied, "drums", verse.resume, verse.end - 4)
    assert {round((n.start / spb) % 4) % 4 for n in later if n.pitch == SNARE and n.velocity > 60} == {1, 3}


def test_transition_effects_wait_for_the_band(varied):
    plan = varied["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    fx = render_fx(plan, seed=1)
    spb = plan.seconds_per_beat

    def energy(beat):
        i = int(beat * spb * 44100)
        return float(np.mean(fx[:, i - 22050:i] ** 2))

    assert energy(last.resume) > 100 * energy(last.start)


def test_harmony_line_skips_quiet_parts(varied):
    plan = varied["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]

    class Note:
        def __init__(self, start):
            self.start, self.dur, self.pitch, self.syllable, self.strong = start, 1.0, 69, "ら", True

    line = harmony_line(plan, [Note(last.start + 1), Note(last.resume + 1)])
    assert [n.start for n in line] == [last.resume + 1]


def test_songs_differ_in_their_arrangement(tmp_path):
    seen = set()
    for seed in range(12):
        plan = compose(tmp_path / str(seed), seed=seed)["plan"]
        seen.add((plan.key_change, tuple(s.feel for s in plan.sections)))
    assert len(seen) >= 4


# ── Orchester in der Ballade ────────────────────────────────────────────────────
def test_ballade_brings_harp_timpani_pizzicato_and_horns(tmp_path):
    tracks = compose(tmp_path, style="Ballade", bpm=78, breakdown_chance=0.0)
    programs = {i.program for i in pretty_midi.PrettyMIDI(str(tmp_path / "strings.mid")).instruments if i.notes}
    assert {49, 45, 46, 47} <= programs     # Streicher, Pizzicato, Harfe, Pauken
    plan = tracks["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    before = plan.sections[last.index - 1]
    spb = plan.seconds_per_beat
    timpani = [i for i in pretty_midi.PrettyMIDI(str(tmp_path / "strings.mid")).instruments if i.program == 47][0]
    roll = [n for n in timpani.notes if (before.end - 4) * spb - 0.03 <= n.start < before.end * spb]
    assert len(roll) >= 30 and roll[-1].velocity > roll[0].velocity + 30
    assert tracks["brass"] and all(50 <= n.pitch <= 67 for n in tracks["brass"])
    first = [s for s in plan.sections if s.kind == "Chorus"][0]
    assert not notes_between(tracks, "brass", first.start, first.end)   # Hörner erst ab dem zweiten Refrain


def test_harp_glissando_rises_into_the_chorus(tmp_path):
    tracks = compose(tmp_path, style="Ballade", bpm=78, breakdown_chance=0.0)
    harp = [i for i in pretty_midi.PrettyMIDI(str(tmp_path / "strings.mid")).instruments if i.program == 46][0]
    plan = tracks["plan"]
    pre = next(s for s in plan.sections if s.kind == "PreChorus")
    spb = plan.seconds_per_beat
    gliss = sorted((n for n in harp.notes if (pre.end - 3) * spb - 0.03 <= n.start < pre.end * spb),
                   key=lambda n: n.start)
    pitches = [n.pitch for n in gliss]
    assert len(pitches) >= 8 and pitches == sorted(pitches)

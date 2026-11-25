from types import SimpleNamespace

import ensemble
from melody_writer import MelNote
from parts import Ev


def test_vocal_from_previous_section_still_gets_space():
    sections = [SimpleNamespace(start=0, end=2, kind="Verse", energy=0.5),
                SimpleNamespace(start=2, end=4, kind="Chorus", energy=0.8)]
    plan = SimpleNamespace(sections=sections, style=SimpleNamespace(name="Rock"))
    vocal = [MelNote(1, 2, 64, "あ")]
    events = {"bells": [Ev(2.25, 0.5, 65, 80), Ev(3.25, 0.5, 65, 80)]}
    result = ensemble.arrange(plan, events, vocal)
    assert result["removed"] == 1
    assert [e.start for e in events["bells"]] == [3.25]


def test_decoration_started_before_section_stops_before_new_vocal():
    sections = [SimpleNamespace(start=0, end=2, kind="Verse", energy=0.5),
                SimpleNamespace(start=2, end=4, kind="Chorus", energy=0.8)]
    plan = SimpleNamespace(sections=sections, style=SimpleNamespace(name="Rock"))
    vocal = [MelNote(2.25, 1, 64, "あ")]
    events = {"bells": [Ev(1.5, 1.5, 65, 80)]}
    result = ensemble.arrange(plan, events, vocal)
    assert result["trimmed"] == 1
    assert len(events["bells"]) == 1
    assert events["bells"][0].start == 1.5
    assert events["bells"][0].start + events["bells"][0].dur < vocal[0].start


def test_overlapping_kicks_preserve_the_strongest_accent_regardless_of_order():
    section = SimpleNamespace(start=0, end=4, chords=[SimpleNamespace(start=0)])
    kicks = [Ev(1, 0.1, 36, 100), Ev(1, 0.1, 35, 40)]
    assert ensemble.rhythm(section, kicks)["kicks"] == [(1, 100)]
    assert ensemble.rhythm(section, list(reversed(kicks)))["kicks"] == [(1, 100)]


def test_bass_follows_the_strength_of_the_kick_without_randomness():
    chord = SimpleNamespace(bass_pc=0)
    section = SimpleNamespace(start=0, end=4, energy=0.7, chords=[SimpleNamespace(start=0)],
                              chord_at=lambda _: chord)
    context = {"rhythm": {"anchors": [0], "kicks": [(1, 45), (2, 110)]}}
    notes = ensemble.bass_line("sync", section, None, context)
    by_time = {note.start: note for note in notes}
    assert by_time[1].vel < by_time[2].vel

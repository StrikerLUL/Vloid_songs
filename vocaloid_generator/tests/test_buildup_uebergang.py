from types import SimpleNamespace

import buildup
from parts import Ev


def test_instruments_from_intro_do_not_leak_into_quiet_verse():
    verse = SimpleNamespace(kind="Verse", occurrence=1, bars=8, feel="normal", start=8.0, end=40.0, energy=0.7)
    plan = SimpleNamespace(sections=[verse])
    held_bass = Ev(7.0, 2.0, 40, 80)
    bass_in_verse = Ev(9.0, 1.0, 40, 80)
    bass_at_entry = Ev(24.0, 1.0, 40, 80)
    events = {"bass": [held_bass, bass_in_verse, bass_at_entry], "piano": [Ev(8.0, 1.0, 60, 70)]}
    assert buildup.apply(plan, events)["verse"] == 8.0
    assert held_bass.dur == 1.0
    assert events["bass"] == [held_bass, bass_at_entry]

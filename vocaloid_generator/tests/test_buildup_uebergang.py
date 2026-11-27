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


def test_first_verse_has_only_the_chosen_accompaniment_until_band_entry():
    verse = SimpleNamespace(kind="Verse", occurrence=1, bars=8, feel="normal", start=8.0, end=40.0, energy=0.7)
    plan = SimpleNamespace(sections=[verse])
    held_guitar = Ev(7.0, 2.0, 55, 80)
    early_guitar = Ev(12.0, 2.0, 57, 80)
    returning_guitar = Ev(24.0, 2.0, 59, 80)
    piano = Ev(8.0, 4.0, 60, 70)
    events = {"piano": [piano], "guitar": [held_guitar, early_guitar, returning_guitar]}

    assert buildup.apply(plan, events)["verse"] == 8.0
    assert held_guitar.dur == 1.0
    assert events["guitar"] == [held_guitar, returning_guitar]
    assert events["piano"] == [piano]


def test_guitar_can_start_alone_when_piano_enters_later():
    verse = SimpleNamespace(kind="Verse", occurrence=1, bars=8, feel="normal", start=8.0, end=40.0, energy=0.7)
    guitar = Ev(8.0, 4.0, 55, 80)
    piano_later = Ev(24.0, 2.0, 60, 70)
    events = {"guitar": [guitar], "piano": [Ev(12.0, 1.0, 60, 70), piano_later]}

    assert buildup.apply(SimpleNamespace(sections=[verse]), events)["verse"] == 8.0
    assert events["guitar"] == [guitar]
    assert events["piano"] == [piano_later]

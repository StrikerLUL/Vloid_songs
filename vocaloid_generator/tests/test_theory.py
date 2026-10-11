# test_theory.py – Akkorde, Stufen, Griffe und der Bauplan eines Songs
import random

import pytest

import config
from song_plan import build_plan
from styles import STYLES, get_style
from theory import Chord, parse_roman, voice_chord

C, D, E, F, G, A, B = 0, 2, 4, 5, 7, 9, 11
STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]


@pytest.mark.parametrize("symbol,tonic,name", [
    ("IVmaj7", C, "Fmaj7"), ("V7", C, "G7"), ("iii7", C, "Em7"), ("vi", C, "Am"),
    ("bVII", A, "G"), ("bVI", A, "F"), ("v7", A, "Em7"), ("i", A, "Am"), ("V", A, "E"),
    ("I/3", C, "C/E"), ("ii7", F, "Gm7"), ("bIIImaj7", D, "Fmaj7"),
])
def test_roman_numerals(symbol, tonic, name):
    assert parse_roman(symbol, tonic).name == name


def test_unknown_numeral_is_rejected():
    with pytest.raises(ValueError):
        parse_roman("VIII", C)


def test_voicing_moves_as_little_as_possible():
    c = voice_chord(Chord(C, "maj"), 55, 76, 3)
    f = voice_chord(Chord(F, "maj"), 55, 76, 3, previous=c)
    assert {p % 12 for p in f} == {F, A, C}
    assert sum(min(abs(p - q) for q in c) for p in f) <= 4, (c, f)
    assert all(55 <= p <= 76 for p in c + f)


def plan_for(style, key="A", mode="minor", structure=STRUCTURE, seed=1):
    return build_plan(get_style(style), 160, structure, key, mode, config.SECTION_CONFIG, random.Random(seed))


@pytest.mark.parametrize("seed", range(5))
def test_minor_songs_rest_on_a_minor_tonic(seed):
    """Früher bekamen Moll-Tonarten Dur-Akkorde; jetzt endet jeder Refrain auf der Moll-Tonika."""
    plan = plan_for("J-Pop Energy", "A", "minor", seed=seed)
    for sec in plan.sections:
        if sec.kind == "Chorus":
            last = sec.chords[-1].chord
            assert last.root == sec.tonic and last.is_minor


@pytest.mark.parametrize("seed", range(5))
def test_pre_chorus_leads_into_the_chorus_with_the_dominant(seed):
    plan = plan_for("J-Pop Energy", "C", "major", seed=seed)
    for i, sec in enumerate(plan.sections):
        if sec.kind == "PreChorus":
            nxt = plan.sections[i + 1]
            assert sec.chords[-1].chord.root == (nxt.tonic + 7) % 12


def test_repeated_sections_share_their_chords():
    plan = plan_for("J-Pop Energy")
    verses = [s for s in plan.sections if s.kind == "Verse"]
    assert [c.chord for c in verses[0].chords] == [c.chord for c in verses[1].chords]
    choruses = [s for s in plan.sections if s.kind == "Chorus"]
    assert [c.chord for c in choruses[0].chords] == [c.chord for c in choruses[1].chords]


@pytest.mark.parametrize("seed", range(8))
def test_final_chorus_changes_key_as_the_plan_says(seed):
    plan = plan_for("J-Pop Energy", "A", "minor", seed=seed)
    up = plan.key_change
    assert up in get_style("J-Pop Energy").key_changes
    choruses = [s for s in plan.sections if s.kind == "Chorus"]
    assert [s.tonic for s in choruses] == [A, A, (A + up) % 12]
    assert plan.sections[-1].tonic == (A + up) % 12   # das Outro bleibt in der neuen Tonart
    bridge = plan.sections[choruses[-1].index - 1]
    assert bridge.chords[-1].chord.root == (A + up + 7) % 12   # Dominante der neuen Tonart


def test_key_changes_differ_between_songs():
    assert {plan_for("J-Pop Energy", seed=s).key_change for s in range(20)} == {0, 1, 2}


def test_rock_stays_in_key():
    plan = plan_for("Rock", "E", "minor")
    assert {s.tonic for s in plan.sections} == {E}


def test_every_style_arranges_every_section():
    for style in STYLES.values():
        for kind in config.SECTION_CONFIG:
            assert style.parts.get(kind), (style.name, kind)
            assert kind in style.grooves, (style.name, kind)


def test_city_pop_uses_seventh_chords():
    plan = plan_for("City Pop", "F", "major")
    qualities = {c.chord.quality for s in plan.sections for c in s.chords}
    assert qualities & {"maj7", "m7", "7"}

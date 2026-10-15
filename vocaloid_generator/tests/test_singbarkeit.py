# test_singbarkeit.py – Singbarkeits-Prüfung beim Komponieren (A5): keine großen Sprünge auf kurzen Silben, der
# höchste Ton nicht nur eine Sechzehntel lang, Atempause nach langen Phrasen
import pytest

import backing_vocals
import main
import melody_writer
import pipeline
from melody_writer import MelNote
from settings import SongSettings

SECTIONS = ["Verse", "Chorus"]


@pytest.fixture(scope="module")
def plan():
    tracks, _ = pipeline.compose(SongSettings(active_sections=SECTIONS, seed=5))
    return tracks["plan"]


def start_of(plan, kind="Chorus"):
    return next(sec.start for sec in plan.sections if sec.kind == kind)


def test_a_big_leap_onto_a_short_syllable_gets_smaller(plan):
    t = start_of(plan)
    lo = plan.vocal_range[0]
    notes = [MelNote(t, 1.0, lo + 2, "ら"), MelNote(t + 1, 0.25, lo + 14, "ら"), MelNote(t + 1.25, 1.0, lo + 4, "ら")]
    done = melody_writer.make_singable(plan, notes)
    assert done["leaps"] >= 1
    assert abs(notes[1].pitch - notes[0].pitch) <= melody_writer.MAX_SHORT_LEAP
    long_leap = [MelNote(t, 1.0, lo + 2, "ら"), MelNote(t + 1, 1.0, lo + 12, "ら")]
    before = [n.pitch for n in long_leap]
    melody_writer.make_singable(plan, long_leap)
    assert [n.pitch for n in long_leap] == before           # auf einem langen Ton darf sie springen


def test_the_top_note_is_not_only_a_sixteenth(plan):
    t = start_of(plan)
    lo = plan.vocal_range[0]
    notes = [MelNote(t + k * 0.5, 0.5, lo + 5, "ら") for k in range(3)]
    notes.insert(2, MelNote(t + 1.0, 0.25, lo + 9, "ら"))
    notes[3].start = t + 1.25
    done = melody_writer.make_singable(plan, notes)
    assert done["peaks"] >= 1
    top = max(n.pitch for n in notes)
    assert any(n.dur > melody_writer.SIXTEENTH for n in notes if n.pitch == top)


def test_a_long_line_gets_a_breath(plan):
    beat = 60.0 / plan.bpm
    t = start_of(plan, "Verse")
    lo = plan.vocal_range[0]
    count = int(melody_writer.LONG_PHRASE_SECONDS / beat) + 4
    notes = [MelNote(t + k, 1.0, lo + 4, "ら") for k in range(count)]
    done = melody_writer.make_singable(plan, notes)
    assert done["breaths"] >= 1
    gaps = [b.start - a.start - a.dur for a, b in zip(notes, notes[1:])]
    first = next(k for k, g in enumerate(gaps) if g > 0)
    assert gaps[first] * beat >= melody_writer.BREATH_SECONDS - 1e-6
    assert (notes[first].start + notes[first].dur - t) * beat >= melody_writer.LONG_PHRASE_SECONDS - 1.0


def test_a_held_vowel_is_not_cut_for_a_breath(plan):
    from lyrics import Mora
    beat = 60.0 / plan.bpm
    t = start_of(plan, "Verse")
    lo = plan.vocal_range[0]
    count = int(melody_writer.LONG_PHRASE_SECONDS / beat) + 2
    notes = [MelNote(t + k, 1.0, lo + 4, Mora("あ", melisma=True) if k else "か") for k in range(count)]
    assert melody_writer.make_singable(plan, notes)["breaths"] == 0


def test_composed_songs_are_singable_and_the_check_has_a_switch():
    s = SongSettings(active_sections=["Verse", "Chorus", "Verse", "Chorus"], seed=11)
    tracks, _ = pipeline.compose(s)
    plan = tracks["plan"]
    notes = backing_vocals.notes_of(tracks["melody_data"], tracks["silben"])
    for a, b in zip(notes, notes[1:]):
        if b.start - a.start - a.dur < melody_writer.LEAP_GAP and b.dur < melody_writer.SHORT_NOTE:
            assert abs(b.pitch - a.pitch) <= melody_writer.MAX_SHORT_LEAP
    assert melody_writer.make_singable(plan, notes) == {"leaps": 0, "peaks": 0, "breaths": 0}
    assert s.singable_melody and main.parse_args(["--ohne-singbarkeit"]).ohne_singbarkeit

"""Focused composition regressions: hook continuity and the final band entrance."""
import random
from types import SimpleNamespace

import pytest

import chorus_lift
from drums import CRASH
from melody_writer import SectionMelodyWriter
from parts import Ev
from song_plan import ChordSlot, Section, SongPlan
from styles import get_style
from theory import Chord


def section(start, occurrence, bar_beats=4, **kwargs):
    sec = Section("Chorus", occurrence, occurrence - 1, start, 8, 0, "major", 1.0, True,
                  bar_beats=bar_beats, **kwargs)
    sec.chords = [ChordSlot(start, sec.beats, Chord(0, "maj"))]
    return sec


@pytest.mark.parametrize("coherent", [False, True])
def test_uneven_chorus_answer_keeps_shared_hook_onsets(monkeypatch, coherent):
    sec = section(0, 1)
    plan = SongPlan(160, get_style("J-Pop Energy"), 0, "major", [sec], {})
    writer = SectionMelodyWriter(plan, sec, random.Random(19),
                                extras=("musical_coherence",) if coherent else ())
    monkeypatch.setattr(writer, "allocate", lambda words: (2, [["ら"] * n for n in (8, 9, 8, 8)]))
    calls = []
    original = writer.phrase_pitches

    def record(slots, start, role, prev, reference=None, words=None):
        calls.append((role, slots, reference))
        return original(slots, start, role, prev, reference, words)

    monkeypatch.setattr(writer, "phrase_pitches", record)
    notes = writer.write([])
    _, slots, reference = next(call for call in calls if call[0] == "H2")
    if coherent:
        assert reference
        old_steps = {slot.step for slot, _ in reference}
        new_steps = {slot.step for slot in slots}
        assert old_steps != new_steps
        assert len(old_steps & new_steps) >= 3
    else:
        assert reference is None  # opt-out retains the legacy composition path
    assert len([n for n in notes if not getattr(n.syllable, "melisma", False)]) == 33
    assert all(plan.vocal_range[0] <= n.pitch <= plan.vocal_range[1] for n in notes)
    assert all(n.dur > 0 and 0 <= n.start < sec.end for n in notes)


def test_hook_reference_guides_answer_without_losing_chord_cadence():
    sec = section(0, 1)
    plan = SongPlan(160, get_style("J-Pop Energy"), 0, "major", [sec], {})
    writer = SectionMelodyWriter(plan, sec, random.Random(19), extras=("musical_coherence",))
    original = writer.phrase_rhythm(8, 2, "H")
    answer = writer.phrase_rhythm(9, 2, "H2")
    reference = [(slot, 60 if i % 2 == 0 else 64) for i, slot in enumerate(original)]
    plain = writer.phrase_pitches(answer, 8, "H2", None)
    guided = writer.phrase_pitches(answer, 8, "H2", None, reference)
    refs = {slot.step: pitch for slot, pitch in reference}

    def distance(pitches):
        return sum(abs(pitch - refs[slot.step]) for slot, pitch in zip(answer, pitches) if slot.step in refs)

    assert distance(guided) < distance(plain)
    assert guided[-1] % 12 == sec.chords[0].chord.root
    assert all(p % 12 in sec.chords[0].chord.pcs for slot, p in zip(answer, guided) if slot.strong)


@pytest.mark.parametrize("bar_beats", [3, 4])
def test_final_lift_enters_after_breakdown_in_the_section_meter(bar_beats):
    first = section(0, 1, bar_beats)
    last = section(first.end, 2, bar_beats, feel="breakdown")
    last.resume = last.start + 2 * bar_beats
    middle = section(last.end, 3, bar_beats)
    # The extra non-final data must survive untouched.
    events = {
        "counter": [Ev(first.start + i * bar_beats, 1, 72, 80) for i in range(8)],
        "strings": [Ev(first.start, 1, 72, 50, "octave"),
                    Ev(last.start, 1, 60, 80), Ev(last.resume, 2, 60, 80),
                    Ev(last.resume, 2, 72, 40, "octave"), Ev(middle.start, 1, 60, 80)],
        "synth": [Ev(last.start, 1, 64, 80), Ev(last.resume, 2, 64, 80)],
        "drums": [Ev(last.resume, 1, CRASH, 90)],
    }
    result = chorus_lift.apply(SimpleNamespace(sections=[first, last]), events)
    assert result["full"] == last.resume
    assert result["layers"] == ["strings", "synth"]
    assert [e.start for e in events["counter"]] == [i * bar_beats for i in range(4, 8)]
    assert not any(e.layer == "octave" and last.start <= e.start < last.resume
                   for inst in ("strings", "synth") for e in events[inst])
    assert sum(e.layer == "octave" and e.start == last.resume for e in events["strings"]) == 1
    assert any(e.layer == "octave" and e.start == last.resume for e in events["synth"])
    assert [e.start for e in events["drums"]] == [last.resume, last.resume + 4 * bar_beats]
    assert any(e.start == middle.start and not e.layer for e in events["strings"])


@pytest.mark.parametrize("resume", [None, 64])
def test_full_breakdown_does_not_receive_a_lift(resume):
    first, last = section(0, 1), section(32, 2, feel="breakdown", resume=resume)
    events = {"synth": [Ev(32, 1, 60, 80)]}
    assert chorus_lift.apply(SimpleNamespace(sections=[first, last]), events)["full"] is None
    assert len(events["synth"]) == 1
    assert "drums" not in events

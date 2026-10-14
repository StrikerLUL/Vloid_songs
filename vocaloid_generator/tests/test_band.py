# test_band.py – Lebendige Band: Bass mit Ghost-Notes und Slides, Gitarre mit Anschlagmustern
import random

import pretty_midi
import pytest

import orchestrator
import parts
from orchestrator import orchestrate_song
from settings import SongSettings

BPM = 120


@pytest.fixture(scope="module")
def plan(tmp_path_factory):
    random.seed(3)
    tracks = orchestrate_song("pop", BPM, ["Verse", "Chorus"], "C", "major",
                              {"Verse": {"bars": 4}, "Chorus": {"bars": 4}},
                              output_dir=str(tmp_path_factory.mktemp("plan")), style="J-Pop Energy")
    return tracks["plan"]


def _part(fn, pattern, sec, plan, **ctx):
    return fn(pattern, sec, plan, random.Random(1), {"vocal": [], **ctx})


def test_bass_stays_as_before_when_switched_off(plan):
    for sec in plan.sections:
        for pattern in parts.LIVELY_BASS:
            assert _part(parts.bass, pattern, sec, plan) == _part(parts.bass, pattern, sec, plan, lively=False)


def test_bass_gets_ghost_notes_and_slides(plan):
    found_ghosts, found_slides = 0, 0
    for sec in plan.sections:
        plain = _part(parts.bass, "root", sec, plan)
        lively = _part(parts.bass, "root", sec, plan, lively="salz")
        ghosts = [e for e in lively if e.dur == parts.GHOST_LEN]
        assert len(lively) == len(plain) + len(ghosts)
        for g in ghosts:
            target = next(e for e in lively if abs(e.start - g.start - 0.25) < 1e-6 and e.dur != parts.GHOST_LEN)
            assert g.pitch == target.pitch and g.vel < target.vel / 2     # leise, eine Sechzehntel davor
        found_ghosts += len(ghosts)
        found_slides += sum(e.slide != 0 for e in lively)
        assert all(abs(e.slide) <= 2 for e in lively)
    assert found_ghosts and found_slides
    chorus = next(s for s in plan.sections if s.kind == "Chorus")
    again = _part(parts.bass, "root", chorus, plan, lively="salz")
    assert again == _part(parts.bass, "root", chorus, plan, lively="salz")      # gleicher Song, gleicher Bass


def test_busy_bass_patterns_stay_plain(plan):
    sec = plan.sections[0]
    assert _part(parts.bass, "driving", sec, plan, lively="salz") == _part(parts.bass, "driving", sec, plan)


def _section(plan, energy):
    from dataclasses import replace
    return replace(plan.sections[0], energy=energy)


def test_strums_follow_the_energy(plan):
    calm = _part(parts.guitar, "strummed", _section(plan, 0.2), plan, strums="salz")
    loud = _part(parts.guitar, "strummed", _section(plan, 0.95), plan, strums="salz")
    first_bar = [e for e in loud if e.start < plan.sections[0].start + 4 - 0.05]
    assert len({round(e.start * 4) for e in first_bar}) > len({round(e.start * 4) for e in calm if e.start < 4})
    assert any(e.dur == parts.MUTE_LEN for e in loud)                 # abgedämpfte Anschläge
    assert not any(e.dur == parts.MUTE_LEN for e in calm)


def test_down_strokes_ring_low_strings_louder_than_up_strokes(plan):
    sec = _section(plan, 0.55)
    events = sorted(_part(parts.guitar, "strummed", sec, plan, strums="salz"), key=lambda e: e.start)
    first = [e for e in events if e.start < sec.start + 0.1]
    assert len(first) == 6 and first[0].vel > first[-1].vel           # runter: tiefe Saite zuerst und lauter
    assert all(b.start > a.start for a, b in zip(first, first[1:]))


def test_strums_off_is_the_old_pattern(plan):
    sec = plan.sections[0]
    assert _part(parts.guitar, "strummed", sec, plan, strums=False) == _part(parts.guitar, "strummed", sec, plan)


def test_slides_become_pitch_bends():
    note = pretty_midi.Note(100, 40, 1.0, 2.0)
    bends = orchestrator._slides([(parts.Ev(2.0, 1.0, 40, 100, slide=-2), note),
                                  (parts.Ev(4.0, 1.0, 43, 100), pretty_midi.Note(100, 43, 2.0, 3.0))])
    assert bends[0].pitch == -8191 and bends[-1].pitch == 0
    assert bends[0].time < 1.0 < bends[-1].time <= 1.0 + orchestrator.SLIDE_SECONDS
    assert [b.pitch for b in bends] == sorted(b.pitch for b in bends)


def test_song_with_lively_band_writes_slides(tmp_path):
    random.seed(4)
    orchestrate_song("pop", BPM, ["Verse", "Chorus"], "C", "major", {"Verse": {"bars": 4}, "Chorus": {"bars": 4}},
                     output_dir=str(tmp_path), style="J-Pop Energy", instrument_styles={"bass": "root"},
                     lively_bass=True, guitar_strums=True)
    bass = pretty_midi.PrettyMIDI(str(tmp_path / "bass.mid"))
    assert any(inst.pitch_bends for inst in bass.instruments)


def test_switches_are_on_by_default():
    s = SongSettings()
    assert s.lively_bass and s.guitar_strums

# test_melodie_130.py – Melodie 1.3.0: beste Fassung (M1), Auftakte (M2), Spannungstöne (M3), Höhepunkt (M4),
# Triolen (M5)
import random

import pytest

import config
import melody_score
import pipeline
from melody_writer import MelNote, SectionMelodyWriter
from orchestrator import _default_lyrics
from settings import SongSettings
from song_plan import build_plan
from styles import get_style


def _plan(style="J-Pop Energy", structure=("Intro", "Verse", "PreChorus", "Chorus", "Outro"), seed=5, bpm=150):
    return build_plan(get_style(style), bpm, list(structure), "A", "minor", config.SECTION_CONFIG,
                      random.Random(seed), {})


def _line(pitches, step=0.5, strong_every=4):
    return [MelNote(i * step, step, p, "ら", i % strong_every == 0) for i, p in enumerate(pitches)]


def test_points_prefer_a_varied_melody_with_a_clear_peak():
    flat = _line([64] * 16)
    jumpy = _line([60, 72, 61, 73, 60, 71, 62, 74] * 2)
    good = _line([64, 65, 67, 69, 67, 65, 64, 62, 64, 67, 69, 72, 71, 69, 67, 64])
    good[11].dur = 1.0
    assert melody_score.score(good, "Chorus") > melody_score.score(flat, "Chorus")
    assert melody_score.score(good, "Chorus") > melody_score.score(jumpy, "Chorus")
    held = _line([64, 65, 67, 69])
    held[-1].syllable, held[-1].dur = "ん", 2.0
    assert melody_score.parts(held, "Verse")["text"] < 1.0


def test_the_chorus_should_go_higher_than_the_verse():
    verse = _line([60, 62, 64, 65, 64, 62] * 2)
    high = _line([67, 69, 71, 72, 71, 69] * 2)
    low = _line([57, 59, 60, 62, 60, 59] * 2)
    assert melody_score.parts(high, "Chorus", verse)["contrast"] > melody_score.parts(low, "Chorus", verse)["contrast"]


def test_the_best_of_many_melodies_sings(new_composition, tmp_path, monkeypatch):
    plan = _plan()
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    words = _default_lyrics()["Chorus"]
    picked = []
    real_pick = melody_score.pick
    monkeypatch.setattr(melody_score, "pick", lambda c, *a: picked.append((c, a, real_pick(c, *a))) or picked[-1][2])
    s = SongSettings(output_ordner=str(tmp_path), seed=11)
    on, _ = pipeline.compose(s)
    assert [a[0] for _, a, _ in picked] == ["Verse", "PreChorus", "Chorus", "Bridge"]
    assert all(len(c) == melody_score.CANDIDATES for c, _, _ in picked)
    candidates, args, (best, points, mean) = picked[2]
    assert points == max(melody_score.score(c, *args) for c in candidates) >= mean
    assert args[1], "der Refrain kennt die Strophe"
    off, _ = pipeline.compose(s.with_updates(best_melody=False))
    assert on["melody_data"] != off["melody_data"]
    # ohne Schalter schreibt der Schreiber jede Sektion nur einmal
    picked.clear()
    pipeline.compose(s.with_updates(best_melody=False))
    assert picked == []
    assert SectionMelodyWriter(plan, chorus, random.Random(1)).write(words)


def _song(tmp_path, **updates):
    s = SongSettings(output_ordner=str(tmp_path), seed=11).with_updates(**updates)
    tracks, _ = pipeline.compose(s)
    return tracks


@pytest.fixture
def written(monkeypatch):
    """Die Gesangsmelodie, wie melody_writer sie geschrieben hat (MelNotes mit ihren Merkmalen)."""
    import orchestrator
    seen = []
    real = orchestrator.write_vocal_melody
    monkeypatch.setattr(orchestrator, "write_vocal_melody", lambda *a, **k: seen.append(real(*a, **k)) or seen[-1])
    return seen


def _entries_before_the_bar(notes) -> list:
    """Töne nach einer Pause im letzten Schlag eines Takts: so beginnt eine Phrase mit Auftakt."""
    ordered = sorted(notes, key=lambda n: n.start)
    return [n for a, n in zip(ordered, ordered[1:]) if n.start - a.start - a.dur >= 0.25 - 1e-6
            and n.start % 4 >= 3 - 1e-6 and not n.pushed]


def test_phrases_start_before_the_bar_and_downbeats_are_pushed(new_composition, tmp_path, written):
    tracks = _song(tmp_path)
    notes, plan = written[-1], tracks["plan"]
    pushed = [n for n in notes if n.pushed]
    assert pushed and all(abs((n.start + 0.25) % 4) < 1e-6 for n in pushed)
    assert all(n.pitch % 12 in plan.chord_at(n.start + 0.25).pcs or not n.strong for n in pushed), "Akkord danach"
    assert len(_entries_before_the_bar(notes)) >= 2
    ordered = sorted(notes, key=lambda n: n.start)
    assert all(a.start + a.dur <= b.start + 1e-6 for a, b in zip(ordered, ordered[1:])), "nichts überlappt"
    for sec in plan.sections:            # alles bleibt in seiner Sektion
        assert all(n.start + n.dur <= sec.end + 1e-6 for n in notes if sec.start - 1e-6 <= n.start < sec.end)
    # aus: alle Phrasen beginnen im Takt und nichts ist vorgezogen
    _song(tmp_path, melody_pickups=False)
    assert not any(n.pushed for n in written[-1]) and not _entries_before_the_bar(written[-1])
    # im 3/4-Takt bleibt alles im Takt
    _song(tmp_path, meter="3/4")
    assert not any(n.pushed for n in written[-1])

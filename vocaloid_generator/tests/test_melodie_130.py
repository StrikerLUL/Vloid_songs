# test_melodie_130.py – Melodie 1.3.0: beste Fassung (M1), Auftakte (M2), Spannungstöne (M3), Höhepunkt (M4),
# Triolen (M5)
import random

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

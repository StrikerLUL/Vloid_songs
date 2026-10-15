# test_stil_effekte.py – Stil-Effekte auf dem Gesang (D7): Telefon, Stutter vor dem Refrain, harter Tune, Formanten
import importlib

import numpy as np
import pytest
import soundfile as sf

import main
import pipeline
import singing
import style_fx
import voice_fx
from settings import SongSettings
from voice_fx import SungNote

RATE = 48000


@pytest.fixture
def styles(monkeypatch):
    """Die echte Tabelle der Stile (conftest schaltet sie für alle anderen Tests ab)."""
    real = importlib.reload(style_fx).STYLES
    monkeypatch.setattr(style_fx, "STYLES", real)
    return real


def voice(notes, length, vibrato=0.0):
    t = np.arange(int(length * RATE)) / RATE
    f0 = np.zeros_like(t)
    for n in notes:
        on = (t >= n.start) & (t < n.end)
        f0[on] = 440 * 2 ** ((n.pitch - 69 + vibrato * np.sin(2 * np.pi * 5.5 * t[on])) / 12)
    phase = 2 * np.pi * np.cumsum(f0) / RATE
    return (0.25 * sum(np.sin(k * phase) / k for k in range(1, 8)) * (f0 > 0)).astype(np.float32)


def test_each_style_gets_its_effects_and_the_switches_take_them_away(styles):
    s = SongSettings()
    assert style_fx.effects_for("Future Bass", s) == {"telephone": True, "stutter": True, "hard_tune": True}
    assert style_fx.effects_for("Ballade", s) == {}
    assert style_fx.effects_for("Kawaii Chiptune", s.with_updates(formant_fx=False, stutter_fx=False)) == \
        {"hard_tune": True}
    args = main.parse_args(["--ohne-telefon", "--ohne-stutter", "--ohne-hardtune", "--ohne-formant"])
    assert args.ohne_telefon and args.ohne_stutter and args.ohne_hardtune and args.ohne_formant


def test_the_telephone_keeps_only_the_middle_band():
    rng = np.random.default_rng(0)
    audio = (0.1 * rng.standard_normal((2 * RATE, 1))).astype(np.float32)
    out = style_fx.telephone(audio, RATE, 0.5, 1.5)
    inside = np.abs(np.fft.rfft(out[int(0.6 * RATE):int(1.4 * RATE), 0]))
    f = np.fft.rfftfreq(int(0.8 * RATE), 1 / RATE)
    assert inside[f > 6000].mean() < 0.1 * inside[(f > 800) & (f < 2500)].mean()
    assert np.array_equal(out[:int(0.4 * RATE)], audio[:int(0.4 * RATE)])
    assert np.sqrt(np.mean(out[int(0.6 * RATE):int(1.4 * RATE)] ** 2)) == pytest.approx(0.1, rel=0.2)


def test_the_last_beat_before_the_chorus_stutters():
    beat = 0.5
    notes = [SungNote(1.0, 2.0, 64), SungNote(2.0, 2.4, 67)]
    audio = voice(notes, 4.0)[:, None].copy()
    assert style_fx.stutter(audio, RATE, notes, 3.0, beat) == 1
    piece = int(beat / 4 * RATE)
    start = int(2.5 * RATE)
    grains = [np.abs(audio[start + k * piece:start + (k + 1) * piece]).max() for k in range(4)]
    assert all(g > 0.05 for g in grains) and grains[-1] > grains[0]          # vier Silben, lauter werdend
    first = audio[start + 400:start + piece - 400, 0]
    assert np.allclose(first / grains[0], audio[start + piece + 400:start + 2 * piece - 400, 0] / grains[1], atol=0.05)
    assert style_fx.stutter(audio, RATE, [SungNote(0.1, 0.2, 60)], 3.0, beat) == 0   # davor nichts gesungen


def test_hard_tune_snaps_onto_the_notes_even_an_octave_lower(tmp_path):
    notes = [SungNote(0.3, 1.5, 62), SungNote(1.5, 2.7, 65)]
    sung = [SungNote(n.start, n.end, n.pitch - 12 + 0.3) for n in notes]     # eine Oktave tiefer, 30 Cent zu hoch
    path = str(tmp_path / "v.wav")
    sf.write(path, voice(sung, 3.0, vibrato=0.5), RATE, subtype="FLOAT")
    assert style_fx.hard_tune(path, notes)
    audio, _ = sf.read(path)
    f0, t = voice_fx._f0(np.ascontiguousarray(audio, dtype=np.float64), RATE)
    inside = (t > 0.6) & (t < 1.3) & (f0 > 0)
    midi = 69 + 12 * np.log2(f0[inside] / 440)
    assert np.median(midi) == pytest.approx(50.0, abs=0.1) and np.std(midi) < 0.2


def test_formants_move_and_the_pitch_stays(tmp_path):
    notes = [SungNote(0.2, 1.8, 64)]
    path = str(tmp_path / "v.wav")
    sf.write(path, voice(notes, 2.0), RATE, subtype="FLOAT")
    before, _ = sf.read(path)
    assert style_fx.formant(path, 1.1)
    after, _ = sf.read(path)
    f0, t = voice_fx._f0(np.ascontiguousarray(after, dtype=np.float64), RATE)
    inside = (t > 0.5) & (t < 1.5) & (f0 > 0)
    assert np.median(69 + 12 * np.log2(f0[inside] / 440)) == pytest.approx(64.0, abs=0.2)
    assert not np.allclose(before, after, atol=1e-3)


def test_the_pipeline_applies_the_effects_of_the_style(tmp_path, styles, monkeypatch):
    s = SongSettings(active_sections=["Verse", "Chorus"], style="Future Bass", seed=4)
    tracks, _ = pipeline.compose(s)
    seen = {}
    monkeypatch.setattr(style_fx, "apply", lambda path, notes, sections, bpm, effects: seen.update(effects) or ["x"])
    singing._style_effects(s, tracks, str(tmp_path / "v.wav"))
    assert seen == {"telephone": True, "stutter": True, "hard_tune": True}
    seen.clear()
    singing._style_effects(s.with_updates(style="Ballade"), tracks, str(tmp_path / "v.wav"))
    assert seen == {}


def test_apply_runs_on_a_real_track(tmp_path, styles):
    notes = [SungNote(0.5, 1.5, 64), SungNote(1.5, 2.0, 67), SungNote(4.0, 5.0, 69)]
    path = str(tmp_path / "v.wav")
    sf.write(path, voice(notes, 6.0), RATE, subtype="FLOAT")
    done = style_fx.apply(path, notes, [(0.0, 3.0, "Verse"), (3.0, 6.0, "Chorus")], 120,
                          {"telephone": True, "stutter": True, "hard_tune": True, "formant": 1.05})
    assert done == ["harter Tune im Refrain", "Telefon in der ersten Zeile", "Stutter vor 1 Refrain",
                    "Formanten ×1.05"]

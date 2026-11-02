"""Audio- und Ablaufregressionen für die gemeinsame Qualitätsprüfung."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

import pipeline
import rating
import render_status
import style_fx
import voice_fx
from settings import SongSettings


def test_review_covers_beginning_middle_end_and_antiphase_stereo(tmp_path):
    rate = 8000
    length = 100
    signal = np.linspace(0.05, 0.5, length * rate, dtype=np.float32)
    source = tmp_path / "song.wav"
    sf.write(source, np.column_stack((signal, -signal)), rate, subtype="FLOAT")
    paths = rating.excerpts(str(source), str(tmp_path / "review"), seconds=10)
    assert len(paths) >= 4
    means = [np.abs(sf.read(path)[0]).mean() for path in paths]
    assert means[0] < 0.1 and means[-1] > 0.4
    assert all(sf.info(path).duration == pytest.approx(10) for path in paths)


def test_weak_sections_cannot_hide_behind_a_good_chorus():
    good, poor = rating.Rating(9, 9, 9, 9), rating.Rating(1, 1, 1, 1)
    combined = rating.aggregate([good, poor, good])
    assert combined.overall < (9 + 1 + 9) / 3
    assert rating.aggregate([good, None]) is None


def test_multiple_review_clips_stay_with_their_variant(monkeypatch):
    a, b = SimpleNamespace(rating=None, history=None, seed=1), SimpleNamespace(rating=None, history=None, seed=2)
    monkeypatch.setattr(rating, "rate", lambda paths: [rating.Rating(v, v, v, v) for v in (8, 2, 6)])
    pipeline._rate([(a, ["verse.wav", "chorus.wav"]), (b, ["other.wav"])])
    assert a.rating.overall == pytest.approx(4.25)
    assert b.rating.overall == 6


def test_fallback_warning_survives_render_cache(tmp_path):
    wav = str(tmp_path / "piano.wav")
    render_status.record(wav, "Einfache Synthese", True, "SoundFont fehlt")
    assert "SoundFont fehlt" in render_status.warnings({"Klavier": wav})[0]
    render_status.record(wav, "SoundFont")
    assert not render_status.warnings({"Klavier": wav})


def test_old_saved_songs_keep_their_generation_mode(tmp_path):
    data = SongSettings().model_dump()
    del data["musical_coherence"], data["selective_vocals"]
    data["verlauf"] = {"erstellt": "2026-11-02T12:00:00"}
    source = tmp_path / "old-song.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    old = SongSettings.load(str(source))
    assert not old.musical_coherence and not old.selective_vocals
    assert SongSettings().musical_coherence and SongSettings().selective_vocals


def test_selective_vocals_leave_good_pitch_untouched(monkeypatch):
    note = voice_fx.SungNote(0, 1, 69)
    f0 = np.full(200, 440.0)
    checked = []
    def repitch(path, notes, curve, psola, gentle):
        checked.append(curve(f0, 0.005, notes, 0))
        return 0
    monkeypatch.setattr(voice_fx, "repitch", repitch)
    voice_fx.reshape("unused.wav", [note], intonation=0.5, ornaments=0.35, seed=1, selective=True)
    assert np.array_equal(checked[0], f0)


def test_selective_vocals_keep_large_user_changes_and_fix_drift(monkeypatch):
    note = voice_fx.SungNote(0, 1, 69)
    f0 = np.full(200, 440 * 2 ** (70 / 1200))
    checked = []
    monkeypatch.setattr(voice_fx, "repitch", lambda path, notes, curve, *args: checked.append(curve(f0, .005, notes, 0)) or .5)
    voice_fx.reshape("unused.wav", [note], intonation=0.5, selective=True)
    assert checked[0][100] < f0[100]


def test_natural_vocals_avoid_automatic_telephone_and_small_formant_shifts(monkeypatch):
    monkeypatch.setattr(style_fx, "STYLES", {"Future Bass": {"telephone": True, "stutter": True, "hard_tune": True},
                                           "Kawaii Chiptune": {"formant": 1.08}})
    natural = SongSettings(selective_vocals=True)
    assert style_fx.effects_for("Future Bass", natural) == {"hard_tune": True}
    assert style_fx.effects_for("Kawaii Chiptune", natural) == {}

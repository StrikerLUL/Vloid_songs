"""Benchmark artifacts must detect real changes without requiring audio models."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_audio import audio_metrics, compare_reports
from benchmark_music import measure


def test_audio_metrics_tone_silence_and_invalid():
    tone = np.sin(2 * np.pi * 100 * np.arange(1000) / 1000)[None, :]
    metrics = audio_metrics(tone, 1000)
    assert metrics["audio_rms"] == pytest.approx(2 ** -0.5)
    assert metrics["audio_centroid_hz"] == pytest.approx(100)
    assert metrics["audio_seconds"] == 1
    assert audio_metrics(np.zeros((2, 100)), 1000)["audio_centroid_hz"] == 0
    assert audio_metrics(tone * 2, 1000)["audio_clip_fraction"] > 0
    for audio in (np.array([[np.nan]]), np.zeros((2, 0)), np.zeros(10)):
        with pytest.raises(ValueError):
            audio_metrics(audio, 1000)


def test_centroid_preserves_antiphase_stereo_signal():
    tone = np.sin(2 * np.pi * 100 * np.arange(1000) / 1000)
    antiphase = np.stack([tone, -tone])
    metrics = audio_metrics(antiphase, 1000)
    assert metrics["audio_centroid_hz"] == pytest.approx(100)
    assert metrics["audio_rms"] == pytest.approx(2 ** -0.5)
    assert metrics["audio_centroid_hz"] == audio_metrics(np.stack([tone, tone]), 1000)["audio_centroid_hz"]


def test_comparison_deltas_and_incompatible_cases():
    baseline = {"schema_version": 1, "suite": {"audio": True}, "rows": [
        {"style": "Rock", "seed": 0, "coherent": True, "notes": 3, "audio_sha256": "old"}]}
    current = copy.deepcopy(baseline)
    current["rows"][0].update(notes=5, audio_sha256="new")
    result = compare_reports(current, baseline)[0]
    assert result["delta"] == {"notes": 2}
    assert result["audio_changed"]
    for change in (lambda r: r["rows"][0].update(seed=2),
                   lambda r: r["rows"].append(r["rows"][0]),
                   lambda r: r.update(suite={}),
                   lambda r: r["rows"][0].update(extra=3)):
        bad = copy.deepcopy(current)
        change(bad)
        with pytest.raises(ValueError):
            compare_reports(bad, baseline)


def test_fixed_seed_repeats_metrics_and_audio(tmp_path):
    first = measure("Rock", 140, 0, True, tmp_path / "a")
    second = measure("Rock", 140, 0, True, tmp_path / "b")
    first.pop("seconds")
    second.pop("seconds")
    assert first == second
    assert first["audio_rms"] > 0
    # FLOAT WAV headers may contain write-time metadata; compare decoded samples.
    a, rate_a = sf.read(next((tmp_path / "a").glob("*.wav")), dtype="float32")
    b, rate_b = sf.read(next((tmp_path / "b").glob("*.wav")), dtype="float32")
    assert rate_a == rate_b == 44100
    np.testing.assert_array_equal(a, b)

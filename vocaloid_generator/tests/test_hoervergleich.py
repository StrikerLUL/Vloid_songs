import importlib.util
import json
from pathlib import Path

import numpy as np
import pyloudnorm
import pytest
import soundfile as sf

spec = importlib.util.spec_from_file_location(
    "hoervergleich", Path(__file__).resolve().parents[2] / "scripts" / "hoervergleich.py")
vergleich = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vergleich)


def test_blind_comparison_matches_loudness_and_keeps_sources(tmp_path):
    rate = 48000
    t = np.arange(rate * 2) / rate
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    sf.write(first, 0.7 * np.sin(2 * np.pi * 440 * t), rate, subtype="FLOAT")
    sf.write(second, 0.1 * np.sin(2 * np.pi * 660 * t), rate, subtype="FLOAT")
    before = first.read_bytes(), second.read_bytes()
    folder = tmp_path / "duell"
    vergleich.prepare(first, second, folder, seed=3)
    a, _ = sf.read(folder / "A.wav")
    b, _ = sf.read(folder / "B.wav")
    meter = pyloudnorm.Meter(rate)
    assert abs(meter.integrated_loudness(a) - meter.integrated_loudness(b)) < 0.01
    assert max(np.max(np.abs(a)), np.max(np.abs(b))) <= 0.981
    assert {x["fassung"] for x in json.loads((folder / "aufloesung.json").read_text(encoding="utf-8"))["zuordnung"].values()} == {"vorher", "nachher"}
    assert first.read_bytes() == before[0] and second.read_bytes() == before[1]
    assert "Harmonie" in (folder / "hoerprotokoll.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="existiert bereits"):
        vergleich.prepare(first, second, folder)


def test_rejects_silence_and_mismatched_audio_without_output(tmp_path):
    rate = 48000
    first, second = tmp_path / "first.wav", tmp_path / "second.wav"
    sf.write(first, np.zeros(rate), rate)
    sf.write(second, np.ones(rate), rate)
    folder = tmp_path / "duell"
    with pytest.raises(ValueError, match="Keine messbare Lautheit"):
        vergleich.prepare(first, second, folder)
    assert not folder.exists()
    t = np.arange(rate) / rate
    sf.write(first, 0.2 * np.sin(2 * np.pi * 440 * t), rate)
    sf.write(second, 0.2 * np.sin(2 * np.pi * 440 * t[:-1]), rate)
    with pytest.raises(ValueError, match="gleiche Samplerate"):
        vergleich.prepare(first, second, folder)
    assert not folder.exists()

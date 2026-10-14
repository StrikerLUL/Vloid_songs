# test_gesangsklang.py – Gesangsklang wie im Vorbild: die Klangkurve in Terzbändern angleichen (D3)
import numpy as np
import pytest
from pedalboard import HighShelfFilter, Pedalboard

import mixer
import pipeline
import separation
from settings import ReferenceTrack, SongSettings

RATE = mixer.SAMPLE_RATE


def noise(seconds=6.0, level=0.1, seed=0):
    rng = np.random.default_rng(seed)
    return (level * rng.standard_normal((2, int(seconds * RATE)))).astype(np.float32)


def darker(audio, db=-6.0):
    return Pedalboard([HighShelfFilter(3000, db, 0.7)])(audio, RATE)


def test_the_curve_shows_where_a_voice_is_bright_or_dark():
    bright = separation.bands_db(noise())
    dark = separation.bands_db(darker(noise()))
    assert len(bright) == len(separation.BAND_CENTERS)
    assert abs(np.mean(bright)) < 1e-6
    top = [k for k, hz in enumerate(separation.BAND_CENTERS) if hz >= 6000]
    assert all(dark[k] < bright[k] - 3 for k in top)


def test_the_vocal_group_is_measured_with_its_curve_and_averaged():
    found = separation.measure({"vocals": noise(level=0.2), "drums": noise(level=0.1, seed=2)})
    assert len(found["vocals"]["bands"]) == len(separation.BAND_CENTERS) and "bands" not in found["drums"]


def test_the_vocal_gets_the_curve_of_the_reference_but_at_most_4_db():
    target = separation.bands_db(darker(noise(seed=4)))
    vocal = noise(seed=1)
    curve = mixer._match_curve(vocal, target)
    after = separation.bands_db(curve(vocal, RATE))
    top = [k for k, hz in enumerate(separation.BAND_CENTERS) if hz >= 6000]
    before = separation.bands_db(vocal)
    for k in top:
        assert after[k] - before[k] < -2.0                   # dunkler, wie das Vorbild
    extreme = [v + (40.0 if k == 10 else 0.0) for k, v in enumerate(before)]
    stretched = separation.bands_db(mixer._match_curve(vocal, extreme)(vocal, RATE))
    assert stretched[10] - before[10] < mixer.MAX_CURVE_DB + 1.0
    assert mixer._match_curve(vocal, before) is None         # schon gleich: nichts zu tun


def test_the_mix_takes_the_curve_instead_of_the_highs_step(caplog):
    vocal = noise(level=0.1, seed=1)
    tracks = {"vocals.wav": ("vocals", vocal.copy()), "drums.wav": ("drums", noise(level=0.08, seed=2))}
    measured = separation.measure({"vocals": vocal, "drums": tracks["drums.wav"][1]})
    target = {"vocals": {**measured["vocals"], "bands": separation.bands_db(darker(noise(seed=4)))}}
    with caplog.at_level("INFO", logger="mixer"):
        mixer._match_groups(tracks, target)
    assert "Gesang klingt wie im Vorbild" in caplog.text
    assert separation.tilt_db(tracks["vocals.wav"][1]) < separation.tilt_db(vocal) - 1.0


def test_the_curve_can_be_switched_off(tmp_path, monkeypatch):
    import reference
    import soundfile as sf
    path = str(tmp_path / "a.wav")
    sf.write(path, noise(2).T, RATE)
    monkeypatch.setattr(reference, "summarize", lambda *a: None)
    groups = {"vocals": {"level": -3.0, "tilt": -12.0, "bands": [0.0] * len(separation.BAND_CENTERS)}}
    monkeypatch.setattr(separation, "summarize", lambda refs: {k: dict(v) for k, v in groups.items()})
    s = SongSettings(reference_tracks=[ReferenceTrack(path=path)], ref_mastering=False, ref_energy=False,
                     ref_vocal_level=False)
    assert "bands" in pipeline._reference_targets(s, {}, str(tmp_path), True)["group_targets"]["vocals"]
    off = pipeline._reference_targets(s.with_updates(ref_vocal_curve=False), {}, str(tmp_path), True)
    assert off["group_targets"]["vocals"] == {"level": -3.0, "tilt": -12.0}


def test_summaries_average_the_curves(tmp_path, monkeypatch):
    import soundfile as sf
    a, b = str(tmp_path / "a.wav"), str(tmp_path / "b.wav")
    for p in (a, b):
        sf.write(p, noise(1).T, RATE)
    n = len(separation.BAND_CENTERS)
    measured = {a: {"vocals": {"level": -2.0, "tilt": -10.0, "bands": [3.0] * n}},
                b: {"vocals": {"level": -6.0, "tilt": -14.0, "bands": [-1.0] * n}}}
    monkeypatch.setattr(separation, "available", lambda: True)
    monkeypatch.setattr(separation, "profiles", lambda paths: measured)
    summary = separation.summarize([ReferenceTrack(path=a, weight=3.0), ReferenceTrack(path=b, weight=1.0)])
    assert summary["vocals"]["bands"] == pytest.approx([2.0] * n)

# test_mix_movement.py – Anlauf vor dem Refrain, Hall pro Sektion, breitere Refrains
import numpy as np
import pytest
import soundfile as sf

import mix_movement as mm
import pipeline
import mixdown
from mix_movement import Part
from mixer import mische_spuren

RATE = mm.SAMPLE_RATE
PARTS = [Part(0, 4, "Verse", 2), Part(4, 6, "PreChorus", 2), Part(6, 10, "Chorus", 2), Part(10, 12, "Chorus", 2),
         Part(12, 14, "Bridge", 2)]


def sine(hz, seconds, amp=0.3, phase=0.0):
    t = np.arange(int(seconds * RATE)) / RATE
    return (amp * np.sin(2 * np.pi * hz * t + phase)).astype(np.float32)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


def test_the_run_up_is_the_bar_before_each_chorus():
    assert mm.rise_windows(PARTS) == [(4, 6)]                   # der zweite Refrain folgt auf einen Refrain
    assert mm.rise_windows([Part(0, 4, "Chorus", 2), Part(4, 8, "Verse", 2)]) == []
    assert mm.rise_windows([Part(0, 1, "Intro", 2), Part(1, 5, "Chorus", 2)]) == [(0, 1)]


def test_the_run_up_takes_the_bass_away_and_gives_it_back_with_the_chorus():
    low = np.vstack([sine(100, 8)] * 2)
    moved = mm.rise(low, [(4, 6)])
    assert np.array_equal(moved[:, :4 * RATE], low[:, :4 * RATE])                      # vorher unberührt
    end = slice(int(5.8 * RATE), int(5.98 * RATE))
    assert rms(moved[:, end]) < 0.5 * rms(low[:, end])                                  # am Ende kaum noch Bass
    assert np.array_equal(moved[:, 6 * RATE:], low[:, 6 * RATE:])                      # im Refrain alles wieder da
    assert np.abs(np.diff(moved[0, int(5.9 * RATE):int(6.1 * RATE)])).max() < 0.05     # ohne Knacks


def test_choruses_are_wider_and_mono_stays_mono():
    width = mm.width_curve(PARTS, 14 * RATE)
    assert width[2 * RATE] == 1.0 and width[8 * RATE] == pytest.approx(1 + mm.CHORUS_WIDTH)
    stereo = np.vstack([sine(440, 14), sine(440, 14, phase=1.0)])
    wide = mm.widen(stereo, width)
    side = lambda a, t: rms(a[0, t * RATE:(t + 1) * RATE] - a[1, t * RATE:(t + 1) * RATE])  # noqa: E731
    assert side(wide, 2) == pytest.approx(side(stereo, 2), rel=1e-3)
    assert side(wide, 8) == pytest.approx(side(stereo, 8) * (1 + mm.CHORUS_WIDTH), rel=1e-3)
    mono = np.vstack([sine(440, 14)] * 2)
    assert np.allclose(mm.widen(mono, width), mono, atol=1e-6)


def test_reverb_follows_the_sections():
    curve = mm.reverb_curve(PARTS, 14 * RATE)
    assert curve[2 * RATE] == mm.REVERB["Verse"] and curve[13 * RATE] == mm.REVERB["Bridge"]
    assert mm.REVERB["Verse"] < mm.REVERB["Chorus"] < mm.REVERB["Bridge"]


def test_the_mixer_moves_only_with_sections(tmp_path):
    stems = []
    for name, hz in (("piano", 220), ("bass", 80)):
        path = tmp_path / f"{name}.wav"
        sf.write(str(path), np.stack([sine(hz, 14), sine(hz, 14, phase=0.5)], axis=1), RATE)
        stems.append(str(path))
    mische_spuren(stems, output_pfad=str(tmp_path / "still.wav"))
    mische_spuren(stems, output_pfad=str(tmp_path / "bewegt.wav"), movement=PARTS)
    still, _ = sf.read(str(tmp_path / "still.wav"))
    moved, _ = sf.read(str(tmp_path / "bewegt.wav"))
    end = slice(int(5.7 * RATE), int(5.95 * RATE))
    assert rms(moved[end]) < rms(still[end])


def test_the_pipeline_hands_over_the_sections(tmp_path):
    from settings import SongSettings
    tracks, _ = pipeline.compose(SongSettings(output_ordner=str(tmp_path), seed=3,
                                              active_sections=["Verse", "PreChorus", "Chorus"]))
    parts = mixdown._movement(tracks["plan"])
    assert [p.kind for p in parts] == ["Verse", "PreChorus", "Chorus"]
    assert parts[1].end == pytest.approx(parts[2].start) and parts[0].bar == pytest.approx(4 * 60 / tracks["plan"].bpm)
    assert mixdown._movement(None) is None

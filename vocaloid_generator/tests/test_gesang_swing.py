# test_gesang_swing.py – der Gesang swingt mit der Band (A6)
import numpy as np
import pytest
import soundfile as sf
from scipy.ndimage import uniform_filter1d

import main
import singing
import voice_fx
from settings import SongSettings
from voice_fx import SungNote

RATE, BPM = 48000, 90
SPB = 60 / BPM


@pytest.fixture
def swinging(monkeypatch):
    monkeypatch.setattr(singing, "VOCAL_SWING_FROM", 0.2)


def sixteenths(count, first_beat=1.0):
    """Ein Ton auf jeder Sechzehntel, 0,2 Schläge lang, dazwischen kurze Stille."""
    return [SungNote((first_beat + k * 0.25) * SPB, (first_beat + k * 0.25 + 0.2) * SPB, 60) for k in range(count)]


def write(path, notes, length=6.0):
    t = np.arange(int(length * RATE)) / RATE
    saw = 2 * ((t * 220) % 1) - 1
    x = np.zeros_like(t)
    for n in notes:
        a, b = int(n.start * RATE), int(n.end * RATE)
        x[a:b] = 0.3 * saw[a:b]
    sf.write(path, np.stack([x, x], 1), RATE, subtype="FLOAT")
    return len(x)


def onsets(path):
    y, _ = sf.read(path)
    loud = uniform_filter1d(np.abs(y[:, 0]), int(0.004 * RATE)) > 0.05
    rising = np.flatnonzero(loud[1:] & ~loud[:-1]) / RATE
    out = []
    for t in rising:
        if not out or t - out[-1] > 0.02:
            out.append(t)
    return out


def test_only_notes_on_the_second_sixteenth_swing():
    notes = sixteenths(8)
    assert [round(n.start / SPB, 2) for n in voice_fx.swung(notes, BPM)] == [1.25, 1.75, 2.25, 2.75]


def test_the_second_sixteenths_come_later_and_the_rest_stays(tmp_path):
    notes = sixteenths(12)
    path = str(tmp_path / "vocals.wav")
    length = write(path, notes)
    assert voice_fx.swing(path, notes, BPM, 0.0475) == 6
    shift = 0.0475 * SPB
    found = onsets(path)
    assert len(found) == len(notes)
    for k, (n, t) in enumerate(zip(notes, found)):
        expected = n.start + (shift if k % 2 else 0.0)
        assert t == pytest.approx(expected, abs=0.004)
    assert len(sf.read(path)[0]) == length


def test_without_second_sixteenths_the_take_stays_untouched(tmp_path):
    notes = [SungNote((1 + k * 0.5) * SPB, (1.4 + k * 0.5) * SPB, 60) for k in range(6)]
    path = str(tmp_path / "vocals.wav")
    write(path, notes)
    before = sf.read(path)[0]
    assert voice_fx.swing(path, notes, BPM, 0.0475) == 0
    assert np.array_equal(sf.read(path)[0], before)


def test_the_vocal_swings_only_when_the_band_swings_enough(swinging):
    assert singing._swing_amount(SongSettings(style="Lo-Fi")) == pytest.approx(0.57)
    assert singing._swing_amount(SongSettings(style="J-Pop Energy")) == 0.0          # Grundwert 0,12 allein nicht
    assert singing._swing_amount(SongSettings(style="City Pop", swing=0.3)) == pytest.approx(0.3)
    assert singing._swing_amount(SongSettings(style="Lo-Fi", vocal_swing=False)) == 0.0
    assert main.parse_args(["--ohne-gesangsswing"]).ohne_gesangsswing


def test_each_vocal_track_swings_after_its_own_notes(swinging, tmp_path, monkeypatch):
    for name in ("vocals.wav", "vocals_harmony.wav", "vocals_flaechen.wav"):
        (tmp_path / name).write_bytes(b"")
    calls = []
    monkeypatch.setattr(voice_fx, "swing", lambda path, notes, bpm, shift: calls.append(
        (path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], len(notes), round(shift, 4))) or 1)
    tracks = {"melody_data": [(None, 1.25), (60, 0.25), (62, 0.5)], "harmony_data": [(None, 1.0), (64, 1.0)]}
    singing._vocal_swing(SongSettings(style="Lo-Fi", bpm=BPM), tracks, str(tmp_path))
    # die Harmonie hat keinen Ton auf der zweiten Sechzehntel, die Flächen swingen nie
    assert calls == [("vocals.wav", 2, round(0.57 / 12, 4))]

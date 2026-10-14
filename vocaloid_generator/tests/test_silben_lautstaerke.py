# test_silben_lautstaerke.py – Lautstärke pro Silbe (C2): Betonungen lauter, Anlauf leiser, weicher Einsatz
import numpy as np
import pytest
import soundfile as sf

import main
import voice_fx
from lyrics import Mora
from settings import SongSettings

RATE = 48000


def test_accents_and_strong_beats_are_louder_and_pickups_softer():
    data = [(64, 1.0), (64, 1.0), (64, 1.0), (64, 0.5), (69, 0.5)]
    silben = [Mora("か", "L", True), Mora("ら", "H"), Mora("す", "H"), Mora("の", "L"), Mora("う", "L")]
    gains = [db for _, _, db in voice_fx.syllable_gains(data, silben, 120)]
    assert gains[0] == voice_fx.ACCENT_DB            # Schlag 1
    assert gains[1] == voice_fx.ACCENT_DB            # Wortakzent (L → H)
    assert gains[2] == voice_fx.ACCENT_DB            # Schlag 3
    assert gains[3] == voice_fx.PICKUP_DB            # kurz, vor dem Sprung nach oben
    assert gains[4] == 0.0


def test_a_held_vowel_keeps_the_level_of_its_syllable():
    data = [(64, 1.0), (66, 1.0)]
    gains = [db for _, _, db in voice_fx.syllable_gains(data, ["か", Mora("あ", melisma=True)], 120)]
    assert gains[1] == gains[0]


def test_the_curve_starts_each_phrase_softly_and_keeps_the_level(tmp_path):
    data = [(None, 1.0), (64, 1.0), (64, 1.0), (64, 1.0), (64, 1.0)]
    path = str(tmp_path / "v.wav")
    t = np.arange(int(3.0 * RATE)) / RATE
    tone = (0.3 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    sf.write(path, tone, RATE)
    assert voice_fx.syllable_dynamics(path, data, ["ら"] * 4, 120)
    out, _ = sf.read(path)
    onset = np.abs(out[int(0.5 * RATE):int(0.52 * RATE)]).max()
    later = np.abs(out[int(1.1 * RATE):int(1.4 * RATE)]).max()
    assert onset < 0.75 * later                       # weicher Einsatz
    sung = out[int(0.6 * RATE):int(2.5 * RATE)]
    assert np.sqrt(np.mean(sung ** 2)) == pytest.approx(np.sqrt(np.mean(tone[:len(sung)] ** 2)), rel=0.15)


def test_syllable_dynamics_has_a_switch():
    assert SongSettings().syllable_dynamics
    assert main.parse_args(["--ohne-silben-lautstaerke"]).ohne_silben_lautstaerke


# ── Echte Atmer (C1) ───────────────────────────────────────────────────────────
def test_recorded_breaths_are_used_when_there_are_some(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    folder = tmp_path / voice_fx.BREATH_FOLDER
    folder.mkdir()
    t = np.arange(int(0.4 * 44100)) / 44100
    sf.write(str(folder / "atmen kurz.wav"), np.concatenate([np.zeros(2000), 0.1 * np.sin(2 * np.pi * 2000 * t)]),
             44100)
    samples = voice_fx.breath_samples(RATE)
    assert len(samples) == 1 and samples[0][0] == pytest.approx(0.4, abs=0.01)    # Stille vorn abgeschnitten

    notes = [voice_fx.SungNote(1.5, 2.5, 64), voice_fx.SungNote(4.0, 5.0, 64)]
    path = str(tmp_path / "v.wav")
    tt = np.arange(int(6 * RATE)) / RATE
    sung = np.where(((tt >= 1.5) & (tt < 2.5)) | ((tt >= 4.0) & (tt < 5.0)), 0.3 * np.sin(2 * np.pi * 330 * tt), 0)
    for recorded, expect in ((True, True), (False, False)):
        sf.write(path, sung.astype(np.float32), RATE)
        assert voice_fx.add_breaths(path, notes, recorded=recorded) == 2
        out, _ = sf.read(path)
        before = out[int(3.5 * RATE):int(3.9 * RATE)]
        spectrum = np.abs(np.fft.rfft(before))
        f = np.fft.rfftfreq(len(before), 1 / RATE)
        peak = f[np.argmax(spectrum)]
        assert (abs(peak - 2000) < 30) == expect

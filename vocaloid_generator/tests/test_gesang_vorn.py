# test_gesang_vorn.py – der Gesang sitzt vorn: die Band macht Platz, der Gesang reitet auf der Band (vocal_mix.py)
import numpy as np
import pytest
import soundfile as sf

import mixer
import vocal_mix

RATE = 44100


def stereo(mono):
    return np.stack([mono, mono]).astype(np.float32)


def noise(seconds, seed=0):
    return np.random.default_rng(seed).standard_normal(int(seconds * RATE)).astype(np.float32) * 0.1


def tone(seconds, freq, on=(0.0, None), level=0.3):
    t = np.arange(int(seconds * RATE)) / RATE
    out = level * np.sin(2 * np.pi * freq * t)
    end = on[1] if on[1] is not None else seconds
    out[(t < on[0]) | (t >= end)] = 0.0
    return out.astype(np.float32)


def band_db(audio, freq, start, end, width=0.15):
    """Pegel (dB) eines Signals im Bereich freq ± width (Anteil) zwischen start und end (Sekunden)."""
    x = audio[int(start * RATE):int(end * RATE)]
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    sel = (f > freq * (1 - width)) & (f < freq * (1 + width))
    return 10 * np.log10(spec[sel].sum())


def test_the_band_makes_room_where_the_vocal_is_loud():
    band = stereo(noise(4.0))
    vocal = stereo(tone(4.0, 1000.0, on=(1.0, 3.0)))
    out = vocal_mix.unmask(band, vocal, RATE)
    assert out.shape == band.shape
    change = band_db(out[0], 1000, 1.5, 2.5, 0.05) - band_db(band[0], 1000, 1.5, 2.5, 0.05)
    assert -3.2 < change < -1.5                                    # in der Stimme: 1,5 bis 3 dB Platz
    assert abs(band_db(out[0], 1000, 3.5, 3.95) - band_db(band[0], 1000, 3.5, 3.95)) < 0.3   # danach wieder voll
    assert abs(band_db(out[0], 80, 1.5, 2.5, 0.3) - band_db(band[0], 80, 1.5, 2.5, 0.3)) < 0.3  # Bass bleibt
    assert abs(band_db(out[0], 5000, 1.5, 2.5) - band_db(band[0], 5000, 1.5, 2.5)) < 0.5      # andere Frequenzen auch


def test_without_vocal_the_band_stays_as_it_is():
    band = stereo(noise(2.0))
    assert np.array_equal(vocal_mix.unmask(band, np.zeros_like(band), RATE), band)


def test_the_vocal_rides_up_where_the_band_gets_much_louder():
    seconds = 8.0
    vocal = stereo(tone(seconds, 600.0) + tone(seconds, 1200.0, level=0.1))
    loud = np.ones(int(seconds * RATE), dtype=np.float32)
    loud[int(6.0 * RATE):] = 10 ** (8 / 20)                       # die letzten zwei Sekunden 8 dB lauter
    band = stereo(noise(seconds) * loud)
    gain = 20 * np.log10(vocal_mix.ride_gain(vocal, band, RATE))
    assert np.abs(gain[int(1.0 * RATE):int(5.0 * RATE)]).max() < 0.5
    assert gain[int(7.0 * RATE):int(7.8 * RATE)].mean() == pytest.approx(vocal_mix.RIDE_MAX_DB, abs=0.5)


def test_small_differences_are_not_ridden():
    seconds = 8.0
    level = np.ones(int(seconds * RATE), dtype=np.float32)
    level[int(4.0 * RATE):] = 10 ** (1 / 20)                      # der Refrain singt 1 dB lauter: das bleibt
    vocal = stereo((tone(seconds, 600.0) + tone(seconds, 1200.0, level=0.1)) * level)
    band = stereo(noise(seconds))
    gain = 20 * np.log10(vocal_mix.ride_gain(vocal, band, RATE))
    assert np.abs(gain).max() < 0.3


def test_mix_with_room_for_the_vocal(tmp_path):
    seconds = 4.0
    paths = {}
    for name, audio in (("vocals", tone(seconds, 1000.0, on=(1.0, 3.0))), ("piano", noise(seconds, 2)),
                        ("drums", noise(seconds, 3) * 0.5)):
        paths[name] = str(tmp_path / f"{name}.wav")
        sf.write(paths[name], audio, RATE)
    outs = {}
    for switch in (False, True):
        outs[switch] = str(tmp_path / f"mix_{switch}.wav")
        mixer.mische_spuren(list(paths.values()), output_pfad=outs[switch], unmask=switch, ride=switch)
    plain, _ = sf.read(outs[False])
    seated, _ = sf.read(outs[True])
    assert np.isfinite(seated).all() and np.max(np.abs(seated)) > 0.1
    assert not np.allclose(plain, seated)


def test_switches_for_the_vocal_in_front():
    import main
    from settings import SongSettings
    s = SongSettings()
    assert s.vocal_unmask and s.vocal_ride
    args = main.parse_args(["--ohne-platz", "--ohne-nachfuehren"])
    assert args.ohne_platz and args.ohne_nachfuehren

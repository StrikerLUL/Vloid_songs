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


# ── Hall und Delay (D4) ────────────────────────────────────────────────────────
def test_the_plate_has_a_tempo_predelay_and_decays():
    assert vocal_mix.predelay(120) == pytest.approx(0.0625)
    assert vocal_mix.predelay(300) == pytest.approx(0.025) and vocal_mix.predelay(40) == pytest.approx(0.08)
    impulse = np.zeros((2, 3 * RATE), dtype=np.float32)
    impulse[:, 0] = 1.0
    wet = vocal_mix.plate(impulse, RATE, 120)
    assert np.abs(wet[:, :int(0.06 * RATE)]).max() < 1e-4           # erst nach dem Pre-Delay
    early = np.sqrt(np.mean(wet[:, int(0.1 * RATE):int(0.3 * RATE)] ** 2))
    late = np.sqrt(np.mean(wet[:, int(1.4 * RATE):int(1.6 * RATE)] ** 2))
    assert 20 * np.log10(late / early) < -30
    assert not np.allclose(wet[0], wet[1])                            # breit


def test_an_own_impulse_response_replaces_the_plate(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    assert vocal_mix.user_impulse("plate", RATE) is None
    (tmp_path / vocal_mix.IR_FOLDER).mkdir()
    ir = np.zeros(4800, dtype=np.float32)
    ir[2400] = 1.0                                                    # 50 ms Echo bei 48 kHz
    sf.write(str(tmp_path / vocal_mix.IR_FOLDER / "EMT Platte.wav"), ir, 48000)
    found = vocal_mix.user_impulse("plate", RATE)
    assert found.shape[0] == 2 and np.argmax(np.abs(found[0])) == pytest.approx(0.05 * RATE, abs=3)
    assert vocal_mix.user_impulse("room", RATE) is None


def test_the_delay_steps_back_while_the_vocal_sings():
    seconds = 4.0
    vocal = stereo(tone(seconds, 440.0, on=(0.0, 2.0)))
    wet = stereo(noise(seconds))
    ducked = vocal_mix.duck(wet, vocal, RATE)

    def db(a, start, end):
        return 10 * np.log10(np.mean(a[:, int(start * RATE):int(end * RATE)] ** 2))

    assert db(ducked, 0.5, 1.8) - db(wet, 0.5, 1.8) == pytest.approx(vocal_mix.DUCK_DB, abs=1.0)
    assert abs(db(ducked, 3.2, 3.9) - db(wet, 3.2, 3.9)) < 0.5


def test_mix_with_plate_and_ducked_delay(tmp_path):
    seconds = 4.0
    paths = []
    for name, audio in (("vocals", tone(seconds, 600.0, on=(0.5, 2.5))), ("piano", noise(seconds, 2) * 0.3)):
        paths.append(str(tmp_path / f"{name}.wav"))
        sf.write(paths[-1], audio, RATE)
    out = str(tmp_path / "mix.wav")
    mixer.mische_spuren(paths, output_pfad=out, vocal_chain=True, vocal_space=[(0.0, 4.0, "Chorus")],
                        convolution=True, ducked_delay=True)
    audio, _ = sf.read(out)
    assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.1

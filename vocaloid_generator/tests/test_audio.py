# test_audio.py – SoundFont-Rendering, einfacher Notfall-Klang, Mix und Mastering
import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
import mixer
from mixer import master, midi_zu_wav, mische_spuren
import renderer
from renderer import render_midi

# FluidSynth nur, wenn die Bibliothek da ist (unter Windows nach setup_fluidsynth.py)
ENGINES = ["tinysoundfont"] + (["fluidsynth"] if renderer._fluidsynth() else [])


def midi_with(program=0, is_drum=False, pitches=(60, 64, 67), pan=None):
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for i, p in enumerate(pitches):
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=p, start=i * 0.25, end=i * 0.25 + 0.5))
    if pan is not None:
        inst.control_changes.append(pretty_midi.ControlChange(10, pan, 0.0))
    pm.instruments.append(inst)
    return pm


def rms(audio):
    return np.sqrt(np.mean(audio ** 2, axis=-1))


@pytest.mark.parametrize("engine", ENGINES)
def test_soundfont_renders_in_stereo(engine):
    audio = render_midi(midi_with(0), config.SOUNDFONT_PFAD, engine=engine)
    assert audio.shape[0] == 2 and audio.dtype == np.float32
    assert np.all(rms(audio) > 1e-3)


@pytest.mark.parametrize("engine", ENGINES)
def test_drums_render_as_real_hits(engine):
    """Früher kamen ohne FluidSynth beim Schlagzeug nur NaN-Werte (ein Knacken) heraus."""
    audio = render_midi(midi_with(0, is_drum=True, pitches=(36, 38, 42, 49)), config.SOUNDFONT_PFAD, engine=engine)
    assert not np.isnan(audio).any()
    assert np.all(rms(audio) > 1e-3)
    assert audio.std() > 1e-3


@pytest.mark.parametrize("engine", ENGINES)
def test_pan_controller_moves_the_sound(engine):
    audio = render_midi(midi_with(29, pan=0), config.SOUNDFONT_PFAD, engine=engine)
    left, right = rms(audio)
    assert left > 3 * right


def test_missing_soundfont_falls_back_to_basic_synthesis(tmp_path):
    path = tmp_path / "drums.mid"
    midi_with(0, is_drum=True, pitches=(36, 38, 42)).write(str(path))
    wav = tmp_path / "drums.wav"
    midi_zu_wav(str(path), str(wav), is_drum=True, soundfont_pfad=str(tmp_path / "fehlt.sf2"))
    audio, sr = sf.read(str(wav))
    assert sr == 44100 and not np.isnan(audio).any() and np.abs(audio).max() > 0.01


def test_stems_keep_their_dynamics(tmp_path):
    loud, soft = tmp_path / "loud.mid", tmp_path / "soft.mid"
    for path, vel in ((loud, 120), (soft, 40)):
        pm = midi_with(33, pitches=(40, 43, 45))
        for n in pm.instruments[0].notes:
            n.velocity = vel
        pm.write(str(path))
        midi_zu_wav(str(path), str(path.with_suffix(".wav")))
    a, _ = sf.read(str(loud.with_suffix(".wav")))
    b, _ = sf.read(str(soft.with_suffix(".wav")))
    assert rms(a.T).mean() > 2 * rms(b.T).mean()


@pytest.fixture
def stems(tmp_path):
    paths = []
    for name, program, drum, pitches in (("drums", 0, True, (36, 42, 38, 42) * 8), ("bass", 33, False, (33, 33, 40, 38) * 8),
                                         ("piano", 0, False, (60, 64, 67, 72) * 8)):
        mid = tmp_path / f"{name}.mid"
        midi_with(program, drum, pitches).write(str(mid))
        midi_zu_wav(str(mid), str(tmp_path / f"{name}.wav"), is_drum=drum)
        paths.append(str(tmp_path / f"{name}.wav"))
    return paths


def test_mix_hits_the_target_loudness_without_clipping(tmp_path, stems):
    out = tmp_path / "mix.wav"
    mische_spuren(stems, output_pfad=str(out), bpm=120)
    audio, sr = sf.read(str(out))
    assert audio.shape[1] == 2
    assert np.abs(audio).max() <= 10 ** (-0.3 / 20) + 1e-3
    assert mixer._loudness(audio.T) == pytest.approx(mixer.MASTER_LUFS, abs=1.0)


SR_TEST = mixer.SAMPLE_RATE


def _test_signals() -> dict:
    rng = np.random.default_rng(3)
    t = np.arange(SR_TEST * 12) / SR_TEST
    song = 0.3 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t))
    song = song + 0.05 * rng.standard_normal(t.size)
    song = np.stack([song, 0.8 * song]).astype(np.float32)
    quiet, tail = song.copy(), song.copy()
    quiet[:, SR_TEST * 3:SR_TEST * 6] *= 0.01
    tail[:, -SR_TEST * 5:] = 0                                      # stilles Ende: dort wurde es früher langsam
    return {"Lied": song, "leise Stelle": quiet, "stilles Ende": tail, "kurz": song[:, :int(SR_TEST * 0.7)].copy(),
            "ungerade Länge": song[:, :SR_TEST * 7 + 1234].copy(), "Mono": song[:1].copy(),
            "Bass": np.stack([np.sin(2 * np.pi * 50 * t)] * 2).astype(np.float32) * 0.5}


def test_loudness_matches_pyloudnorm():
    import pyloudnorm
    for name, audio in _test_signals().items():
        expected = pyloudnorm.Meter(SR_TEST).integrated_loudness(audio.T.astype(np.float64))
        assert mixer._loudness(audio) == pytest.approx(expected, abs=0.01), name
    assert mixer._loudness(np.zeros((2, SR_TEST), dtype=np.float32)) == float("-inf")
    assert mixer._loudness(np.full((2, SR_TEST), 1e-6, dtype=np.float32)) == float("-inf")   # unter -70 LUFS


def test_muted_and_soloed_tracks(tmp_path, stems):
    solo = tmp_path / "solo.wav"
    mische_spuren(stems, output_pfad=str(solo), solos={"piano": True}, bpm=120)
    muted = tmp_path / "muted.wav"
    mische_spuren(stems, output_pfad=str(muted), mutes={"piano": True}, bpm=120)
    a, _ = sf.read(str(solo))
    b, _ = sf.read(str(muted))
    assert a.shape == b.shape and not np.allclose(a, b)


def test_master_limits_peaks():
    rng = np.random.default_rng(0)
    loud = (rng.standard_normal((2, 44100 * 3)) * 0.5).astype(np.float32)
    out = master(loud, limiter_threshold=-1.0)
    assert np.abs(out).max() <= 10 ** (-1.0 / 20) + 1e-4


def test_reference_song_sets_the_tone_and_the_platform_the_loudness(tmp_path):
    """Mit Vorbild-Song gleicht das Mastering die Klangfarbe an ihn an; die Lautheit bleibt die gewählte."""
    from scipy.signal import butter, sosfilt
    sr, n = 44100, 44100 * 12
    rng = np.random.default_rng(0)
    t = np.arange(n) / sr
    reference = np.clip(rng.standard_normal((2, n)) * 0.2 + 0.3 * np.sin(2 * np.pi * 110 * t), -0.95, 0.95)
    sf.write(tmp_path / "vorbild.wav", reference.T, sr)
    tone = 0.2 * np.sin(2 * np.pi * 220 * t) * (1 + 0.5 * np.sin(2 * np.pi * 2 * t))
    dark = np.vstack([tone, tone]) + sosfilt(butter(2, 800, fs=sr, output="sos"), rng.standard_normal((2, n)) * 0.05)
    sf.write(tmp_path / "piano.wav", dark.T, sr)

    def brightness(audio):
        spec = np.abs(np.fft.rfft(audio.mean(axis=0))) ** 2
        return spec[np.fft.rfftfreq(audio.shape[1], 1 / sr) > 4000].sum() / spec.sum()

    plain, matched = tmp_path / "normal.wav", tmp_path / "vorbild_mix.wav"
    mische_spuren([str(tmp_path / "piano.wav")], output_pfad=str(plain))
    mische_spuren([str(tmp_path / "piano.wav")], output_pfad=str(matched), reference=str(tmp_path / "vorbild.wav"),
                  target_lufs=-14.0)
    a, _ = sf.read(plain, always_2d=True)
    b, _ = sf.read(matched, always_2d=True)
    assert mixer._loudness(b.T.astype(np.float32)) == pytest.approx(-14.0, abs=0.5)
    assert brightness(b.T) > 5 * brightness(a.T)


def test_missing_reference_song_falls_back_to_normal_mastering(tmp_path):
    sr = 44100
    t = np.arange(sr * 3) / sr
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    sf.write(tmp_path / "piano.wav", np.vstack([tone, tone]).T, sr)
    out = tmp_path / "mix.wav"
    mische_spuren([str(tmp_path / "piano.wav")], output_pfad=str(out), reference=str(tmp_path / "fehlt.mp3"))
    assert out.exists()

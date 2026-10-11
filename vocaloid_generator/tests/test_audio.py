# test_audio.py – SoundFont-Rendering, einfacher Notfall-Klang, Mix und Mastering
import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
import mixer
from mixer import master, midi_zu_wav, mische_spuren
from renderer import render_midi


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


def test_soundfont_renders_in_stereo():
    audio = render_midi(midi_with(0), config.SOUNDFONT_PFAD)
    assert audio.shape[0] == 2 and audio.dtype == np.float32
    assert np.all(rms(audio) > 1e-3)


def test_drums_render_as_real_hits():
    """Früher kamen ohne FluidSynth beim Schlagzeug nur NaN-Werte (ein Knacken) heraus."""
    audio = render_midi(midi_with(0, is_drum=True, pitches=(36, 38, 42, 49)), config.SOUNDFONT_PFAD)
    assert not np.isnan(audio).any()
    assert np.all(rms(audio) > 1e-3)
    assert audio.std() > 1e-3


def test_pan_controller_moves_the_sound():
    audio = render_midi(midi_with(29, pan=0), config.SOUNDFONT_PFAD)
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

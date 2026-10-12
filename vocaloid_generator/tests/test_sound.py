# test_sound.py – Neue Stile, Drum-Machine, Gitarren-Verstärker, Lo-Fi-Klang, VST-Klänge und paralleles Rendern
import base64
import os

import numpy as np
import pretty_midi
import pytest
import soundfile as sf
from scipy.signal import welch

import config
import drum_machine
import guitar_amp
import mixer
import orchestrator
import pipeline
import reference
import synth_engine
import vst_sounds
from drums import GROOVES
from parts import PARTS
from preset_manager import PRESETS
from settings import SongSettings
from styles import STYLES, get_style

NEW_STYLES = ("Future Bass", "Drum and Bass", "Lo-Fi", "Idol-Pop")
SR = 44100


def make_settings(tmp_path, **updates):
    base = {"active_sections": ["Intro", "Verse", "Chorus"], "output_ordner": str(tmp_path / "out")}
    return SongSettings().with_updates(**{**base, **updates})


def band_share(audio: np.ndarray, lo: float, hi: float) -> float:
    mono = audio if audio.ndim == 1 else audio.mean(axis=0)
    f, p = welch(mono, SR, nperseg=4096)
    return float(p[(f >= lo) & (f < hi)].sum() / p.sum())


def drum_midi(notes: list, pan: int = None) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(0, is_drum=True, name="Drums")
    inst.notes = [pretty_midi.Note(110, pitch, start, start + 0.1) for pitch, start in notes]
    if pan is not None:
        inst.control_changes.append(pretty_midi.ControlChange(10, pan, 0.0))
    pm.instruments.append(inst)
    return pm


# ── Stile ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(STYLES))
def test_every_style_is_complete(name):
    profile = STYLES[name]
    assert all(groove in GROOVES or groove in ("build", None) for groove in profile.grooves.values())
    assert all(voice in synth_engine.VOICES for layers in profile.voices.values() for voice in layers.values())
    assert profile.drum_machine in ("", *drum_machine.MACHINES)
    assert name in PRESETS and name in reference.STYLE_TRAITS
    assert pipeline.genre_for_style(name) in ("J-Pop", "EDM", "Rock", "Lo-Fi")


def test_lofi_is_its_own_style_now():
    assert get_style("Lo-Fi").name == "Lo-Fi" and get_style("Lo-Fi").texture == "lofi"


FULL = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Drop",
        "Chorus", "Outro"]


@pytest.mark.parametrize("name", NEW_STYLES)
def test_new_styles_play_every_part_they_name(tmp_path, name):
    s = make_settings(tmp_path, style=name, active_sections=FULL)
    tracks, _ = pipeline.compose(s, seed=4)
    named = {inst for parts in STYLES[name].parts.values() for inst, pattern in parts.items() if pattern}
    silent = [inst for inst in named & set(PARTS) if inst != "melody" and not tracks[inst]]
    assert not silent, f"{name}: {silent} spielen nicht"
    assert tracks["drums"]


def test_style_swing_comes_on_top_of_the_setting(tmp_path, monkeypatch):
    seen = []
    real = orchestrator._to_notes
    monkeypatch.setattr(orchestrator, "_to_notes", lambda evs, bpm, inst, rng, swing, jitter: seen.append(swing)
                        or real(evs, bpm, inst, rng, swing, jitter))
    for style in ("Lo-Fi", "J-Pop Energy"):
        pipeline.compose(make_settings(tmp_path, style=style, swing=0.1, active_sections=["Chorus"]), seed=1)
    assert seen[0] == pytest.approx(0.1 + get_style("Lo-Fi").swing) and seen[-1] == pytest.approx(0.1)


def test_rolling_bass_holds_until_the_next_hit_or_chord(tmp_path):
    s = make_settings(tmp_path, style="Drum and Bass", active_sections=["Chorus"], channels={"bass": {"style": "rolling"}})
    tracks, _ = pipeline.compose(s, seed=2)
    notes = sorted(tracks["bass"], key=lambda n: n.start)
    spb = 60 / s.bpm
    assert all(b.start - a.end > -0.03 for a, b in zip(notes, notes[1:]))      # nichts überlappt
    assert np.median([n.end - n.start for n in notes]) > spb                    # lange Töne


def test_future_bass_chords_are_wide_stabs_with_their_own_voice(tmp_path):
    s = make_settings(tmp_path, style="Future Bass", active_sections=["Chorus"])
    pipeline.compose(s, seed=3)
    names = [i.name for i in pretty_midi.PrettyMIDI(os.path.join(s.output_dir(), "synth.mid")).instruments]
    assert "Synth saw" in names and get_style("Future Bass").voices["synth"]["saw"] == "fb_chord"


# ── Eigene Synth-Stimmen ────────────────────────────────────────────────────────
def dominant(audio: np.ndarray) -> float:
    f, p = welch(audio.mean(axis=0), SR, nperseg=16384)
    return float(f[np.argmax(p)])


def test_sub_bass_is_a_pure_low_tone():
    audio = synth_engine.render_notes([pretty_midi.Note(100, 33, 0.0, 1.0)], "sub")   # A1, 55 Hz
    assert dominant(audio) == pytest.approx(55, abs=3)
    assert band_share(audio, 0, 200) > 0.95


def test_reese_bass_is_low_but_moves():
    audio = synth_engine.render_notes([pretty_midi.Note(100, 33, 0.0, 2.0)], "reese")
    assert band_share(audio, 0, 400) > 0.8
    bright = [band_share(audio[:, k:k + SR // 4], 400, 2000) for k in range(0, SR * 2 - SR // 4, SR // 4)]
    assert max(bright) > 1.5 * min(bright)          # der Filter geht auf und zu


def test_future_bass_chord_falls_into_its_note(monkeypatch):
    def onset_pitch(audio):
        start = audio.mean(axis=0)[:int(0.02 * SR)] * np.hanning(int(0.02 * SR))
        spectrum = np.abs(np.fft.rfft(start, 1 << 18))
        f = np.fft.rfftfreq(1 << 18, 1 / SR)
        band = (f > 380) & (f < 520)
        return f[band][np.argmax(spectrum[band])]

    note = pretty_midi.Note(100, 69, 0.0, 0.5)
    bent = synth_engine.render_notes([note], "fb_chord")
    monkeypatch.setattr(synth_engine, "FB_BEND_SEMITONES", 0.0)
    straight = synth_engine.render_notes([note], "fb_chord")
    assert onset_pitch(bent) > onset_pitch(straight) + 5
    assert dominant(bent[:, int(0.15 * SR):int(0.45 * SR)]) == pytest.approx(440, rel=0.03)
    assert np.abs(bent[0] - bent[1]).mean() > 0.1 * np.abs(bent).mean()    # breit im Stereobild


# ── Drum-Machine ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("machine", drum_machine.MACHINES)
def test_drum_machine_kick_is_low_and_hats_are_high(machine):
    rng = np.random.default_rng(0)
    kick, hat = drum_machine.kick(machine, rng), drum_machine.cymbal(machine, rng, 0.15, 0.022, 7000)
    assert band_share(kick, 0, 150) > 0.7
    assert band_share(hat, 6000, 22050) > 0.8


def test_808_kick_rings_longer_than_909():
    rng = np.random.default_rng(0)

    def length(audio):
        return np.nonzero(np.abs(audio) > 0.05 * np.abs(audio).max())[0][-1] / SR

    assert length(drum_machine.kick("808", rng)) > 1.4 * length(drum_machine.kick("909", rng))


def test_each_kick_stops_the_one_before():
    audio, _ = drum_machine.render(drum_midi([(36, 0.0), (36, 0.3)]), "808")
    alone, _ = drum_machine.render(drum_midi([(36, 0.3)]), "808")
    assert np.allclose(audio[:, int(0.32 * SR):], alone[:, int(0.32 * SR):], atol=1e-6)


def test_open_hat_stops_when_the_closed_hat_comes():
    audio, rest = drum_machine.render(drum_midi([(46, 0.0), (42, 0.3)]), "808")
    level = np.abs(audio).max(axis=0)
    window = int(0.02 * SR)
    before = level[int(0.25 * SR):int(0.25 * SR) + window].max()
    after = level[int(0.45 * SR):int(0.45 * SR) + window].max()          # geschlossenes Hi-Hat ist da längst aus
    alone, _ = drum_machine.render(drum_midi([(46, 0.0)]), "808")
    assert after < 0.05 * before
    assert np.abs(alone).max(axis=0)[int(0.45 * SR):int(0.45 * SR) + window].max() > 0.2 * before
    assert not rest


def test_drum_machine_keeps_pan_and_leaves_unknown_notes_to_the_soundfont():
    audio, rest = drum_machine.render(drum_midi([(42, 0.0), (81, 0.5)], pan=20), "909")
    assert np.abs(audio[0]).sum() > 2 * np.abs(audio[1]).sum()
    assert [n.pitch for inst in rest for n in inst.notes] == [81]


def test_midi_to_wav_with_the_drum_machine(tmp_path):
    midi = str(tmp_path / "drums.mid")
    drum_midi([(36, 0.0), (38, 0.5), (42, 0.25), (81, 0.75)]).write(midi)
    wav = str(tmp_path / "drums.wav")
    mixer.midi_zu_wav(midi, wav, is_drum=True, instrument_type="drums", drum_machine="808", library=False)
    audio, _ = sf.read(wav)
    assert np.abs(audio).max() > 0.05


def test_drum_sound_follows_the_choice_or_the_style():
    s = SongSettings(style="Future Bass")
    assert pipeline._drum_machine(s) == "808"
    assert pipeline._drum_machine(s.with_updates(channels={"drums": {"style": "soundfont"}})) is None
    assert pipeline._drum_machine(SongSettings(style="Rock", channels={"drums": {"style": "909"}})) == "909"
    assert pipeline._drum_machine(SongSettings(style="Rock")) is None


# ── Gitarren-Verstärker ─────────────────────────────────────────────────────────
def power_chords(program: int, pan: int = None) -> pretty_midi.Instrument:
    inst = pretty_midi.Instrument(program, name="Guitar left" if pan else "Guitar")
    for k in range(8):
        inst.notes += [pretty_midi.Note(100, p, k * 0.25, k * 0.25 + 0.22) for p in (40, 47, 52)]
    if pan is not None:
        inst.control_changes.append(pretty_midi.ControlChange(10, pan, 0.0))
    return inst


def test_only_distorted_guitars_go_through_the_amp():
    assert guitar_amp.wants_amp(power_chords(30)) and guitar_amp.wants_amp(power_chords(29))
    assert not guitar_amp.wants_amp(power_chords(27)) and not guitar_amp.wants_amp(power_chords(25))


def test_amp_and_cabinet_take_the_fizz_away():
    played = guitar_amp.play(power_chords(30), config.SOUNDFONT_PFAD, library=False)
    pm = pretty_midi.PrettyMIDI()
    pm.instruments = [power_chords(30)]
    from renderer import render_midi
    sampled = render_midi(pm, config.SOUNDFONT_PFAD, library=False)
    assert played is not None and played.shape[0] == 2
    assert band_share(played, 6000, 22050) < 0.5 * band_share(sampled, 6000, 22050)
    assert band_share(played, 0, 80) < 0.05


def test_amped_guitar_keeps_its_place_in_the_stereo_image():
    played = guitar_amp.play(power_chords(30, pan=22), config.SOUNDFONT_PFAD, library=False)
    assert np.abs(played[0]).sum() > 2 * np.abs(played[1]).sum()


def test_cabinet_from_an_impulse_response(tmp_path):
    t = np.arange(2048) / SR
    ir = (np.random.default_rng(1).standard_normal(2048) * np.exp(-t / 0.003)).astype(np.float32)
    path = str(tmp_path / "box.wav")
    sf.write(path, ir, SR)
    noise = np.random.default_rng(2).standard_normal((1, SR)).astype(np.float32) * 0.1
    assert guitar_amp.cabinet(noise, path).shape == noise.shape
    broken = str(tmp_path / "kaputt.wav")
    open(broken, "wb").write(b"keine wav")
    assert band_share(guitar_amp.cabinet(noise, broken), 8000, 22050) < 0.02     # eingebaute Box


def test_midi_to_wav_amps_guitars_unless_switched_off(tmp_path):
    pm = pretty_midi.PrettyMIDI()
    pm.instruments = [power_chords(30, pan=22)]
    midi = str(tmp_path / "guitar.mid")
    pm.write(midi)
    for amp in (True, False):
        mixer.midi_zu_wav(midi, str(tmp_path / f"{amp}.wav"), instrument_type="guitar", library=False, amp=amp)
    amped, _ = sf.read(str(tmp_path / "True.wav"))
    sampled, _ = sf.read(str(tmp_path / "False.wav"))
    assert band_share(amped.T, 6000, 22050) < band_share(sampled.T, 6000, 22050)


# ── Lo-Fi-Klang ─────────────────────────────────────────────────────────────────
def test_lofi_dulls_the_band_without_making_it_louder():
    noise = np.random.default_rng(3).standard_normal((2, SR * 2)).astype(np.float32) * 0.1
    assert band_share(mixer._lofi(noise), 9000, 22050) < 0.2 * band_share(noise, 9000, 22050)
    t = np.arange(SR * 2) / SR
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220, 277, 330, 440)) * 0.1
    band = np.vstack([chord, chord]).astype(np.float32)
    assert np.sqrt(np.mean(mixer._lofi(band) ** 2)) == pytest.approx(np.sqrt(np.mean(band ** 2)), rel=0.15)


def test_lofi_tape_wobbles_the_pitch():
    t = np.arange(SR * 4) / SR
    tone = np.vstack([np.sin(2 * np.pi * 1000 * t)] * 2).astype(np.float32) * 0.3
    wobbly = mixer._lofi(tone)[0]
    zero = np.nonzero(np.diff(np.signbit(wobbly)))[0]
    periods = np.diff(zero[zero > SR // 10])
    assert periods.std() > 0.05                     # gleichmäßiger Ton schwankt jetzt


def test_vinyl_crackles_quietly():
    vinyl = mixer._vinyl(SR * 5)
    assert mixer._loudness(vinyl) == pytest.approx(mixer.VINYL_LUFS, abs=1.0)
    assert np.abs(vinyl).max() > 6 * np.sqrt(np.mean(vinyl ** 2))   # einzelne Knackser


def test_mix_with_lofi_texture_crackles(tmp_path):
    t = np.arange(SR * 2) / SR
    path = str(tmp_path / "piano.wav")
    sf.write(path, np.stack([0.2 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32), SR)
    outs = {}
    for texture in ("", "lofi"):
        out = str(tmp_path / f"mix{texture}.wav")
        mixer.mische_spuren([path], output_pfad=out, texture=texture)
        outs[texture], _ = sf.read(out)
    assert band_share(outs["lofi"].T, 2000, 9000) > 3 * band_share(outs[""].T, 2000, 9000)


# ── VST-Klänge pro Spur ─────────────────────────────────────────────────────────
def test_vst_plays_chosen_parts_or_else_synth_and_lead():
    s = SongSettings(vst_path="C:/Surge XT.vst3")
    assert pipeline._vst_for(s, "synth") == ("C:/Surge XT.vst3", "") and pipeline._vst_for(s, "bass") == (None, "")
    chosen = s.with_updates(vst_sounds={"bass": "QUJD", "gitarre": "x"})
    assert chosen.vst_sounds == {"bass": "QUJD"}
    assert pipeline._vst_for(chosen, "bass") == ("C:/Surge XT.vst3", "QUJD")
    assert pipeline._vst_for(chosen, "synth") == (None, "")
    assert pipeline._vst_for(SongSettings(vst_sounds={"bass": "QUJD"}), "bass") == (None, "")


class FakePlugin:
    is_instrument = True

    def __init__(self):
        self.raw_state = b""

    def __call__(self, messages, duration, sample_rate, num_channels):
        self.messages = messages
        return np.full((2, int(duration * sample_rate)), 0.1, dtype=np.float32)


def test_vst_render_loads_the_saved_sound(tmp_path, monkeypatch):
    plugin = FakePlugin()
    monkeypatch.setattr(mixer, "load_plugin", lambda path: plugin)
    path = tmp_path / "Surge XT.vst3"
    path.write_bytes(b"")
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(0)
    inst.notes = [pretty_midi.Note(100, 60, 0.0, 0.5)]
    pm.instruments = [inst]
    audio = mixer._render_vst(pm, str(path), vst_sounds.encode(b"<patch name='Reese'/>"))
    assert plugin.raw_state == b"<patch name='Reese'/>" and audio.shape[0] == 2


def test_choosing_a_sound_opens_the_instrument_in_its_own_process(monkeypatch):
    calls = []

    class Done:
        returncode, stderr = 0, ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        assert open(cmd[3]).read() == "ALT"
        open(cmd[4], "w").write(base64.b64encode(b"neu").decode())
        return Done()

    monkeypatch.setattr(vst_sounds.subprocess, "run", fake_run)
    assert vst_sounds.choose("C:/Surge XT.vst3", "ALT") == base64.b64encode(b"neu").decode()
    assert calls[0][1].endswith("vst_sounds.py") and calls[0][2] == "C:/Surge XT.vst3"

    class Failed:
        returncode, stderr = 1, "kein Instrument"

    monkeypatch.setattr(vst_sounds.subprocess, "run", lambda cmd, **kw: Failed())
    assert vst_sounds.choose("C:/kaputt.vst3") is None


def test_surge_is_found_where_it_is_usually_installed(tmp_path, monkeypatch):
    plugin = tmp_path / "Surge XT.vst3"
    monkeypatch.setattr(vst_sounds, "_surge_candidates", lambda: (str(tmp_path / "fehlt.vst3"), str(plugin)))
    assert vst_sounds.find_surge() == ""
    plugin.mkdir()
    assert vst_sounds.find_surge() == str(plugin)


# ── Paralleles Rendern ──────────────────────────────────────────────────────────
@pytest.mark.slow
def test_rendering_in_parallel_gives_the_same_tracks(tmp_path, monkeypatch):
    s = make_settings(tmp_path, style="Future Bass", active_sections=["Chorus"], sound_library=False)
    tracks, _ = pipeline.compose(s, seed=6)
    results = {}
    for workers in (1, 4):
        monkeypatch.setattr(pipeline, "RENDER_WORKERS", workers)
        wavs = pipeline._render_instruments(s, tracks, s.output_dir(), lambda f, m: None)
        results[workers] = {inst: sf.read(path)[0] for inst, path in wavs.items()}
    assert results[1].keys() == results[4].keys() and len(results[1]) >= 5
    for inst in results[1]:
        assert np.allclose(results[1][inst], results[4][inst], atol=1e-6), inst

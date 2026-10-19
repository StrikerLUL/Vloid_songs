# test_instrumente_130.py – Instrumente 1.3.0: Surge-XT-Klänge (I8), Verstärker (I9), Druck im Mix (I10)
import hashlib
import importlib.util
import io
import json
import os
import struct
import tarfile
import zipfile

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import amp_models
import config
import einrichten
import guitar_amp
import main
import mixdown
import mixer
import rendering
import surge_sounds
from airwindows import juce_decode, juce_encode
from settings import SongSettings

SR = mixer.SAMPLE_RATE
REAL_SURGE = os.path.join(config.REPO_ROOT, "tools", "surge")
REAL_NAM = os.path.join(config.REPO_ROOT, "tools", "nam")


def _module(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(config.REPO_ROOT, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── I8: Surge-XT-Klänge ─────────────────────────────────────────────────────────
PRIVATE = b"xyz" + struct.pack("<q", 3) + b"JUCEPrivateData"


def _surge_state(patch=b"alter Klang"):
    """So sieht raw_state von Surge XT aus: VC2!, Länge, XML; im IComponent der Klang und der JUCE-Block."""
    xml = (b'<?xml version="1.0"?><VST3PluginState><IComponent>' + juce_encode(patch + PRIVATE).encode() +
           b"</IComponent></VST3PluginState>")
    return b"VC2!" + struct.pack("<I", len(xml)) + xml


def _fxp(polymode=4):
    xml = f'<patch><a_polymode type="0" value="{polymode}" /><a_octave type="0" value="0" /></patch>'.encode()
    return b"CcnK" + b"\0" * 56 + b"sub3" + struct.pack("<I", len(xml)) + b"\0" * 24 + xml + b"WT-Daten"


def test_a_surge_patch_goes_into_the_plugin_state_and_mono_patches_play_chords():
    fxp = _fxp(polymode=12)                 # zweistellig: das XML wird kürzer, die Länge im Kopf muss mit
    poly = surge_sounds.polyphonic(fxp)
    assert b'<a_polymode type="0" value="0" />' in poly and poly.endswith(b"WT-Daten")
    size = struct.unpack("<I", poly[64:68])[0]
    assert poly[92:92 + size].endswith(b"</patch>") and len(poly) == len(fxp) - 1
    assert surge_sounds.polyphonic(b"kein Surge-Klang" * 8) == b"kein Surge-Klang" * 8
    state = surge_sounds.with_patch(_surge_state(), poly)
    assert state[:4] == b"VC2!" and struct.unpack("<I", state[4:8])[0] == len(state) - 8
    inner = state[state.index(b"<IComponent>") + 12:state.index(b"</IComponent>")]
    assert juce_decode(inner.decode()) == poly[60:] + PRIVATE, "der Klang ohne Kopf, der JUCE-Block bleibt"
    with pytest.raises(ValueError):
        surge_sounds.with_patch(b"VC2!\0\0\0\0<xml/>", poly)


def test_surge_plays_the_own_synths_when_it_is_set_up_and_switched_on(tmp_path, monkeypatch):
    played = []

    def render(notes, voice, rate, path=""):
        played.append(voice)
        if voice not in surge_sounds.SOUNDS:
            return None
        return np.full((2, int(rate * (max(n.end for n in notes) + 0.5))), 0.25, np.float32)
    monkeypatch.setattr(surge_sounds, "render", render)
    midi = pretty_midi.PrettyMIDI()
    for name in ("Synth", "Synth saw", "Synth pad"):
        inst = pretty_midi.Instrument(81, name=name)
        inst.notes = [pretty_midi.Note(100, p, 0.0, 1.0) for p in (60, 64, 67)]
        midi.instruments.append(inst)
    midi.write(str(tmp_path / "synth.mid"))
    voices = {"": "pluck", "saw": "fb_chord", "pad": "pad"}
    for surge in (True, False):
        played.clear()
        wav = str(tmp_path / f"synth_{surge}.wav")
        mixer.midi_zu_wav(str(tmp_path / "synth.mid"), wav, instrument_type="synth", voices=voices, surge=surge)
        assert played == (["pluck", "fb_chord", "pad"] if surge else [])
        audio, _ = sf.read(wav)
        assert (np.median(audio[int(0.2 * SR):int(0.8 * SR), 0]) > 0.45) == surge, "zwei Surge-Unterspuren"
    # in der App: eingerichtet, eingeschaltet, kein Entwurf und eine Spur mit eigener Stimme
    monkeypatch.setattr(surge_sounds, "covers", lambda voice: voice in surge_sounds.SOUNDS)
    s = SongSettings(style="Future Bass", output_ordner=str(tmp_path))
    assert s.surge_sounds and rendering._render_job(s, str(tmp_path), "synth")["surge"] is True
    assert rendering._render_job(s, str(tmp_path), "piano")["surge"] is False
    assert rendering._render_job(s.with_updates(surge_sounds=False), str(tmp_path), "synth")["surge"] is False
    assert rendering._render_job(s.with_updates(draft=True), str(tmp_path), "synth")["surge"] is False
    assert rendering._render_job(SongSettings(style="Ballade"), str(tmp_path), "synth")["surge"] is False, "nur Pad"
    assert main.parse_args(["--ohne-surge-klaenge"]).off_surge_sounds
    assert einrichten.find("surge").script == "setup_surge.py" and not surge_sounds.installed()


def test_setup_unpacks_only_the_plugin_and_checks_every_sound(tmp_path, monkeypatch):
    setup = _module("setup_surge")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Surge XT.vst3/Contents/x86_64-win/Surge XT.vst3", b"dll")
        z.writestr("Surge XT.vst3/desktop.ini", b"ini")
        z.writestr("Surge XT Effects.vst3/Contents/x86_64-win/Surge XT Effects.vst3", b"fx")
        z.writestr("Surge XT.exe", b"exe")
        z.writestr("Surge XT.vst3/../../boese.txt", b"x")
    target = tmp_path / "surge"
    assert setup.unpack(buffer.getvalue(), str(target)) == 2
    assert (target / "Surge XT.vst3" / "Contents" / "x86_64-win" / "Surge XT.vst3").read_bytes() == b"dll"
    assert not (tmp_path / "boese.txt").exists() and not (target / "Surge XT.exe").exists()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as t:
        for name, data in (("./Surge XT.vst3/Contents/x86_64-linux/Surge XT.so", b"so"), ("./surge-xt-cli", b"cli")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    assert setup.unpack(buffer.getvalue(), str(tmp_path / "linux")) == 1
    assert (tmp_path / "linux" / "Surge XT.vst3" / "Contents" / "x86_64-linux" / "Surge XT.so").exists()
    # die Klänge: falscher Inhalt wird nicht abgelegt, richtiger landet in SurgeXTData
    sounds = {v: surge_sounds.Sound(k.file, hashlib.sha256(v.encode()).hexdigest()) for v, k in
              surge_sounds.SOUNDS.items()}
    monkeypatch.setattr(surge_sounds, "SOUNDS", sounds)
    urls = []
    monkeypatch.setattr(setup, "_laden", lambda url: urls.append(url) or b"falsch")
    assert not setup.klaenge(str(target)) and not (target / surge_sounds.DATA).exists()
    assert len(urls) == setup.VERSUCHE * len(sounds) and "release_xt_1.3.4" in urls[0] and "%20" in urls[0]
    voice = {setup.SOURCE + setup.urllib.parse.quote(k.file): v for v, k in sounds.items()}
    monkeypatch.setattr(setup, "_laden", lambda url: voice[url].encode())
    monkeypatch.setattr(surge_sounds, "FOLDER", str(target))
    assert setup.klaenge(str(target)) and surge_sounds.installed()
    assert open(surge_sounds.patch_path("reese"), "rb").read() == b"reese"


@pytest.mark.skipif(not os.path.isdir(os.path.join(REAL_SURGE, surge_sounds.PLUGIN)), reason="setup_surge.py nicht gelaufen")
def test_the_real_surge_plays_every_sound_as_loud_as_the_own_synth(monkeypatch):
    from synth_engine import render_notes
    monkeypatch.setattr(surge_sounds, "FOLDER", REAL_SURGE)
    for voice in surge_sounds.SOUNDS:
        notes = [pretty_midi.Note(100, p, k * 0.5, k * 0.5 + 0.4) for k in range(4)
                 for p in ((40,) if voice == "reese" else (60, 64, 67))]
        audio = surge_sounds.render(notes, voice, SR)
        assert audio is not None and audio.shape[0] == 2, voice
        own = render_notes(notes, voice)
        assert np.sqrt(np.mean(audio ** 2)) == pytest.approx(np.sqrt(np.mean(own ** 2)), rel=1e-3), voice
    chip = surge_sounds.render([pretty_midi.Note(100, p, 0.0, 1.0) for p in (60, 64, 67)], "chip", SR)
    spectrum = np.abs(np.fft.rfft(chip.mean(axis=0)[:SR]))
    freqs = np.fft.rfftfreq(SR, 1 / SR)
    heard = [f for f in (261.6, 329.6, 392.0) if spectrum[(freqs > f * 0.98) & (freqs < f * 1.02)].max() >
             0.1 * spectrum.max()]
    assert len(heard) == 3, "der Chip-Lead spielt Akkorde"


# ── I9: Verstärker-Modelle (NAM) ────────────────────────────────────────────────
def _small_nam(seed=0, gated=False):
    """Ein kleines WaveNet wie in einer .nam-Datei: zwei Stapel, Gewichte in der Reihenfolge von NAM."""
    layers = [dict(input_size=1, condition_size=1, head_size=2, channels=3, kernel_size=3, dilations=[1, 2, 4],
                   activation="Tanh", gated=gated, head_bias=False),
              dict(input_size=3, condition_size=1, head_size=1, channels=2, kernel_size=3, dilations=[1, 2],
                   activation="Tanh", gated=gated, head_bias=True)]
    count = 0
    for spec in layers:
        ch, k, mid = spec["channels"], spec["kernel_size"], spec["channels"] * (2 if gated else 1)
        count += ch * spec["input_size"] + len(spec["dilations"]) * (mid * ch * k + mid + mid + ch * ch + ch)
        count += spec["head_size"] * ch + (spec["head_size"] if spec["head_bias"] else 0)
    weights = np.random.default_rng(seed).standard_normal(count + 1) * 0.5
    weights[-1] = 0.5                                                   # head_scale
    return {"version": "0.5.0", "architecture": "WaveNet", "weights": weights.tolist(),
            "config": {"layers": layers, "head": None, "head_scale": 0.5}}


def _slow_nam(data, x):
    """Wie PyTorch rechnet: Conv1d ohne Polsterung, Ausrichtung am Ende, vorne Stille so lang wie der Vorlauf."""
    w, pos = np.asarray(data["weights"]), [0]

    def take(*shape):
        n = int(np.prod(shape))
        pos[0] += n
        return w[pos[0] - n:pos[0]].reshape(shape)

    def conv(x, weight, bias, d=1):
        k = weight.shape[2]
        n = x.shape[1] - (k - 1) * d
        out = sum(weight[:, :, j] @ x[:, j * d:j * d + n] for j in range(k))
        return out + (bias[:, None] if bias is not None else 0)
    arrays = []
    for spec in data["config"]["layers"]:
        ch, k, mid = spec["channels"], spec["kernel_size"], spec["channels"] * (2 if spec["gated"] else 1)
        rechannel = take(ch, spec["input_size"], 1)
        layers = [(d, take(mid, ch, k), take(mid), take(mid, 1, 1), take(ch, ch, 1), take(ch)) for d in spec["dilations"]]
        arrays.append((rechannel, layers, take(spec["head_size"], ch, 1),
                       take(spec["head_size"]) if spec["head_bias"] else None, k, ch, spec["gated"]))
    scale = w[pos[0]]
    reach = sum((k - 1) * sum(layer[0] for layer in layers) for _, layers, _, _, k, _, _ in arrays)
    x = np.concatenate([np.zeros(reach), x])[None, :]
    y, head = x, None
    for rechannel, layers, head_w, head_b, k, ch, gated in arrays:
        length = y.shape[1] - (k - 1) * sum(layer[0] for layer in layers)
        y = conv(y, rechannel, None)
        for d, weight, bias, mixer_w, out_w, out_b in layers:
            z = conv(y, weight, bias, d)
            z = z + conv(x, mixer_w, None)[:, -z.shape[1]:]
            act = np.tanh(z[:ch]) / (1 + np.exp(-z[ch:])) if gated else np.tanh(z)
            y = y[:, -act.shape[1]:] + conv(act, out_w, out_b)
            head = act[:, -length:] if head is None else head[:, -length:] + act[:, -length:]
        head = conv(head, head_w, head_b)
    return scale * head[0]


def test_distorted_guitars_play_through_a_real_amp_model(tmp_path, monkeypatch):
    x = (np.sin(np.arange(400) / 7.0) * 0.4).astype(np.float32)
    x[150:300] = 0.0                                        # eine Pause: dort rechnet das Modell nicht, gleich bleibt es
    for gated in (False, True):
        data = _small_nam(seed=3, gated=gated)
        net = amp_models.WaveNet(data)
        assert net.reach == 2 * 7 + 2 * 3
        monkeypatch.setattr(amp_models, "BLOCK", 64)        # über Blockgrenzen hinweg gleich
        assert np.allclose(net(x), _slow_nam(data, x.astype(np.float64)), atol=1e-5)
    with pytest.raises(ValueError):
        amp_models.WaveNet({**_small_nam(), "architecture": "LSTM"})
    with pytest.raises(ValueError):
        amp_models.WaveNet({**_small_nam(), "weights": _small_nam()["weights"][:-5]})
    # eingerichtet: die Modelle liegen in FOLDER, play rechnet in der Rate des Modells und gibt dieselbe Form zurück
    monkeypatch.setattr(amp_models, "FOLDER", str(tmp_path))
    for program, amp in amp_models.AMPS.items():
        with open(tmp_path / amp.file, "w", encoding="utf-8") as f:
            json.dump(_small_nam(seed=program), f)
    assert amp_models.installed() and amp_models.play(x, 27, SR) is None
    played = amp_models.play(x[None, :], 30, SR)
    assert played.shape == (1, 400) and np.all(np.isfinite(played)) and np.abs(played).max() > 1e-3
    # die Gitarre: mit Modell anders, aber so laut wie der eingebaute Verzerrer
    inst = pretty_midi.Instrument(30, name="Guitar")
    inst.notes = [pretty_midi.Note(100, p, 0.0, 1.5) for p in (40, 47, 52)]
    calls = []
    real = amp_models.play
    monkeypatch.setattr(amp_models, "play", lambda audio, program, rate: calls.append(program) or real(audio, program, rate))
    own = guitar_amp.play(inst, mixer.SOUNDFONT_PFAD)
    modeled = guitar_amp.play(inst, mixer.SOUNDFONT_PFAD, models=True)
    assert calls == [30] and own.shape == modeled.shape and not np.allclose(own, modeled)
    assert np.sqrt(np.mean(modeled ** 2)) == pytest.approx(np.sqrt(np.mean(own ** 2)), rel=1e-3)
    # in der App: Schalter, Verstärker und Box an, kein Entwurf
    s = SongSettings(style="Rock", output_ordner=str(tmp_path))
    assert s.amp_models and rendering._render_job(s, str(tmp_path), "guitar")["amp_models"] is True
    for off in ({"amp_models": False}, {"guitar_amp": False}, {"draft": True}):
        assert rendering._render_job(s.with_updates(**off), str(tmp_path), "guitar")["amp_models"] is False, off
    assert main.parse_args(["--ohne-verstaerker-modelle"]).off_amp_models
    assert einrichten.find("nam").script == "setup_nam.py"


def test_setup_loads_the_amp_models_only_with_the_right_checksum(tmp_path, monkeypatch):
    setup = _module("setup_nam")
    amp = amp_models.Amp("Test Amp.nam", hashlib.sha256(b"richtig").hexdigest(), "Test", "Jemand")
    urls = []
    monkeypatch.setattr(setup, "_laden", lambda url: urls.append(url) or b"falsch")
    assert not setup.hole(amp, str(tmp_path)) and not (tmp_path / "Test Amp.nam").exists()
    assert len(urls) == setup.VERSUCHE and urls[0].endswith("Test%20Amp.nam") and setup.COMMIT in urls[0]
    monkeypatch.setattr(setup, "_laden", lambda url: b"richtig")
    assert setup.hole(amp, str(tmp_path)) and (tmp_path / "Test Amp.nam").read_bytes() == b"richtig"
    monkeypatch.setattr(setup, "_laden", lambda url: pytest.fail("schon da, nicht noch einmal laden"))
    assert setup.hole(amp, str(tmp_path))


@pytest.mark.skipif(not os.path.isdir(REAL_NAM), reason="setup_nam.py nicht gelaufen")
def test_the_real_amp_models_distort_a_clean_guitar(monkeypatch):
    monkeypatch.setattr(amp_models, "FOLDER", REAL_NAM)
    t = np.arange(SR) / SR
    clean = (0.4 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    for program in amp_models.AMPS:
        out = amp_models.play(clean, program, SR)
        assert out is not None and out.shape == clean.shape and np.all(np.isfinite(out))
        spectrum = np.abs(np.fft.rfft(out[SR // 4:]))
        freqs = np.fft.rfftfreq(len(out[SR // 4:]), 1 / SR)
        partial = lambda f: spectrum[(freqs > f - 3) & (freqs < f + 3)].max()      # noqa: E731
        assert partial(330) > 0.05 * partial(110), "der Verstärker verzerrt: Obertöne"


# ── I10: Druck im Mix ───────────────────────────────────────────────────────────


def _drums(seconds=4.0):
    """Laute Schläge mit leisem Nachklang: Bassdrum auf jedem Schlag, dazwischen leise Ghost-Notes."""
    t = np.arange(int(SR * seconds)) / SR
    out = np.zeros_like(t)
    for k in range(int(seconds * 2)):
        start = int(k * 0.5 * SR)
        n = int(0.2 * SR)
        hit = (1.0 if k % 2 == 0 else 0.08) * np.exp(-np.arange(n) / (0.03 * SR)) * np.sin(2 * np.pi * 60 *
                                                                                          np.arange(n) / SR)
        out[start:start + n] += hit[:len(out) - start]
    return np.stack([out, out]).astype(np.float32) * 0.5


def test_parallel_bus_and_multiband_compression_add_punch(tmp_path):
    drums = _drums()
    punchy = mixer.parallel_compress(drums)
    assert mixer._loudness(punchy) == pytest.approx(mixer._loudness(drums), abs=0.6), "gleich laut"
    ghost = slice(int(0.5 * SR), int(0.6 * SR))
    hit = slice(0, int(0.1 * SR))
    ratio = lambda x: np.abs(x[0, ghost]).max() / np.abs(x[0, hit]).max()      # noqa: E731
    assert ratio(punchy) > 1.3 * ratio(drums), "leise Schläge kommen nach vorn"
    # Bus-Kompressor: alle Spuren der Band werden gemeinsam leiser, wo die Summe laut ist; der Gesang nicht
    loud, quiet = np.ones((2, SR), np.float32) * 0.5, np.ones((2, SR), np.float32) * 0.5
    loud[:, SR // 2:] *= 0.05
    quiet[:, SR // 2:] *= 0.05
    voice = np.ones((2, SR), np.float32) * 0.3
    tracks = {"a": ("drums", loud.copy()), "b": ("piano", quiet.copy()), "c": ("vocals", voice.copy())}
    mixer.glue_band(tracks)
    early, late = slice(SR // 4, SR // 2 - 100), slice(3 * SR // 4, SR - 1)
    for path, before in (("a", loud), ("b", quiet)):
        cut_early = tracks[path][1][0, early].mean() / before[0, early].mean()
        cut_late = tracks[path][1][0, late].mean() / before[0, late].mean()
        assert cut_early < 0.95 and cut_late == pytest.approx(1.0, abs=0.02)
    assert np.array_equal(tracks["c"][1], voice)
    # Mehrband: still bleibt alles, wie es war; laute Bässe werden für sich verdichtet
    noise = np.random.default_rng(1).standard_normal((2, SR)).astype(np.float32) * 1e-3
    assert np.allclose(mixer.multiband(noise), noise, atol=1e-5)
    t = np.arange(SR) / SR
    boom = np.stack([np.sin(2 * np.pi * 60 * t) * 0.9 + np.sin(2 * np.pi * 5000 * t) * 0.01] * 2).astype(np.float32)
    squeezed = mixer.multiband(boom)

    def band(x, lo, hi):
        spec = np.abs(np.fft.rfft(x[0]))
        freqs = np.fft.rfftfreq(len(x[0]), 1 / SR)
        return spec[(freqs > lo) & (freqs < hi)].max()
    assert band(squeezed, 50, 70) < 0.8 * band(boom, 50, 70)
    assert band(squeezed, 4900, 5100) == pytest.approx(band(boom, 4900, 5100), rel=0.1), "die Höhen bleiben"
    # in der App: der Schalter kommt beim Mix an, aus klingt es wie bisher
    s = SongSettings(output_ordner=str(tmp_path))
    tracks = {"plan": None}
    assert mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=False)["punch"] is True
    assert mixdown.mix_arguments(s.with_updates(mix_punch=False), tracks, str(tmp_path), has_vocals=False)["punch"] \
        is False
    paths = []
    for name, audio in (("drums", drums), ("piano", boom[:, :len(drums[0])] if boom.shape[1] >= drums.shape[1]
                                           else np.pad(boom, ((0, 0), (0, drums.shape[1] - boom.shape[1]))))):
        path = tmp_path / f"{name}.wav"
        sf.write(path, audio.T, SR, subtype="FLOAT")
        paths.append(str(path))
    on, off = tmp_path / "an.wav", tmp_path / "aus.wav"
    mixer.mische_spuren(paths, output_pfad=str(on), punch=True)
    mixer.mische_spuren(paths, output_pfad=str(off), punch=False)
    assert not np.allclose(sf.read(on)[0], sf.read(off)[0], atol=1e-3)

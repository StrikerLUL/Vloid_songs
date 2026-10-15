# test_voice.py – Lebendiger Gesang: Atmer, Echo auf dem letzten Wort, Vibrato und Übergänge, Fassungen, Chor im
# letzten Refrain und VOICEVOX als Engine (gegen ein nachgebautes VOICEVOX im Test)
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import soundfile as sf

import main
import mixer
import pipeline
import vocal_synthesizer
import voice_fx
import voicevox
from settings import SongSettings
from voicevox import running as real_running

RATE = 24000


def hz(midi):
    return 440.0 * 2 ** ((np.asarray(midi, dtype=float) - 69) / 12)


def tone(f0, rate=RATE):
    """Eine Stimme mit Obertönen, die der Tonhöhenkurve f0 (Hz je Abtastwert, 0 = still) folgt."""
    phase = 2 * np.pi * np.cumsum(f0) / rate
    voice = sum(np.sin(k * phase) / k for k in range(1, 6))
    return (0.25 * voice * (f0 > 0)).astype(np.float32)


def sung(notes, length, rate=RATE, vibrato=0.0, glide=0.0):
    """Gesang zu den Noten: optional mit Vibrato (Halbtöne) und Gleiten (Sekunden) an gebundenen Übergängen."""
    t = np.arange(int(length * rate)) / rate
    midi = np.full(len(t), np.nan)
    for n in notes:
        midi[(t >= n.start) & (t < n.end)] = n.pitch
    if glide:
        for a, b in zip(notes, notes[1:]):
            zone = np.abs(t - b.start) < glide
            x = (t[zone] - b.start + glide) / (2 * glide)
            midi[zone] = a.pitch + (b.pitch - a.pitch) * (1 - np.cos(np.pi * x)) / 2
    if vibrato:
        for n in notes:
            zone = (t >= n.start + 0.25) & (t < n.end - 0.05)
            midi[zone] += vibrato * np.sin(2 * np.pi * 5.5 * (t[zone] - n.start))
    return tone(np.where(np.isnan(midi), 0.0, hz(np.nan_to_num(midi))), rate)


def measured_pitch(audio, rate, frame=0.005):
    import pyworld as pw
    x = np.ascontiguousarray(audio, dtype=np.float64)
    f0, t = pw.dio(x, rate, f0_floor=70.0, f0_ceil=1100.0, frame_period=frame * 1000)
    f0 = pw.stonemask(x, f0, t, rate)
    return f0, t


def write(path, audio, rate=RATE):
    sf.write(str(path), audio, rate, subtype="FLOAT")
    return str(path)


N = voice_fx.SungNote


# ── Noten und Phrasen ──────────────────────────────────────────────────────────
def test_timeline_binds_short_rests_and_splits_phrases_at_long_ones():
    data = [(None, 2.0), (60, 1.0), (None, 0.5), (62, 1.0), (None, 2.0), (64, 2.0)]
    notes = voice_fx.timeline(data, 120, transpose=-12)
    assert [(n.start, n.end, n.pitch) for n in notes] == [(1.0, 1.75, 48), (1.75, 2.25, 50), (3.25, 4.25, 52)]
    assert [len(p) for p in voice_fx.phrases(notes)] == [2, 1]


def test_excerpt_keeps_only_the_notes_in_the_window_with_their_syllables():
    data = [(None, 4.0), (60, 1.0), (62, 1.0), (None, 2.0), (64, 1.0), (65, 3.0), (67, 4.0)]
    silben = ["a", "b", "c", "d", "e"]
    part, syllables = voice_fx.excerpt(data, silben, 8.0, 12.0)
    assert part == [(64, 1.0), (65, 3.0)] and syllables == ["c", "d"]
    part, syllables = voice_fx.excerpt(data, silben, 6.0, 9.0)
    assert part == [(None, 2.0), (64, 1.0)] and syllables == ["c"]


# ── Atmer ──────────────────────────────────────────────────────────────────────
def test_breaths_come_before_phrases_and_stay_quiet(tmp_path):
    notes = [N(1.0, 2.0, 64), N(2.0, 3.0, 67), N(4.0, 5.5, 65), N(5.55, 6.0, 64)]
    path = write(tmp_path / "vocals.wav", sung(notes, 7.0))
    before, _ = sf.read(path)
    assert voice_fx.add_breaths(path, notes, seed=1) == 2      # vor 1,0 s und vor 4,0 s; 5,55 s ist dieselbe Phrase
    after, _ = sf.read(path)
    added = after - before

    def rms(a, b):
        return float(np.sqrt(np.mean(added[int(a * RATE):int(b * RATE)] ** 2)))
    assert rms(0.5, 0.94) > 0 and rms(3.5, 3.94) > 0
    assert rms(0.0, 0.3) == 0 and rms(3.0, 3.3) == 0 and rms(6.0, 7.0) == 0
    singing = float(np.sqrt(np.mean(before[int(1.2 * RATE):int(2.8 * RATE)] ** 2)))
    assert 10 ** (-30 / 20) < np.abs(added).max() / singing < 10 ** (-10 / 20)
    spectrum = np.abs(np.fft.rfft(added[int(0.5 * RATE):int(0.94 * RATE)]))
    freqs = np.fft.rfftfreq(int(0.94 * RATE) - int(0.5 * RATE), 1 / RATE)
    assert spectrum[(freqs > 800) & (freqs < 3000)].mean() > 4 * spectrum[freqs < 150].mean()


def test_breaths_can_be_switched_off(tmp_path, monkeypatch):
    s = SongSettings(active_sections=["Verse"], output_ordner=str(tmp_path), vocal_engine="Vorschau", breaths=False,
                     final_choir=False)
    tracks, _ = pipeline.compose(s, seed=2)
    called = []
    monkeypatch.setattr(voice_fx, "add_breaths", lambda *a, **k: called.append(a) or 0)
    monkeypatch.setattr(pipeline, "_sing_preview", lambda s_, t_, wav: write(wav, np.zeros(RATE)) and True)
    pipeline._synthesize_vocals(s, tracks, str(tmp_path))
    assert not called
    pipeline._synthesize_vocals(s.with_updates(breaths=True), tracks, str(tmp_path))
    assert called


# ── Echo auf dem letzten Wort ──────────────────────────────────────────────────
def test_echo_throws_go_on_section_ends_and_every_second_chorus_line():
    spb = 0.5
    phrase_starts = [0, 4, 8, 12, 16, 20, 24, 28]          # zwei Sektionen à vier Phrasen, je 3 Schläge lang
    notes = [N(s * spb + k * spb, s * spb + (k + 1) * spb, 60) for s in phrase_starts for k in range(3)]
    sections = [(0.0, 16 * spb, "Verse"), (16 * spb, 32 * spb, "Chorus")]
    windows = voice_fx.throw_windows(notes, 120, sections)
    assert windows == [(7.0, 7.5), (11.0, 11.5), (15.0, 15.5)]
    # ohne Sektionen nur da, wo zwei Schläge Pause sind
    assert voice_fx.throw_windows(notes, 120) == [(15.0, 15.5)]


def test_echo_throw_answers_right_then_left():
    length = 4 * mixer.SAMPLE_RATE
    vocals = np.zeros((2, length), dtype=np.float32)
    burst = slice(int(0.5 * mixer.SAMPLE_RATE), int(0.6 * mixer.SAMPLE_RATE))
    vocals[:, burst] = np.sin(np.linspace(0, 400 * np.pi, burst.stop - burst.start))
    echo = mixer._echo_throws(vocals, [(0.5, 0.6)], bpm=120)
    step = 0.75 * 0.5

    def energy(ch, at):
        a = int((0.5 + at) * mixer.SAMPLE_RATE)
        return float(np.sum(echo[ch, a:a + int(0.1 * mixer.SAMPLE_RATE)] ** 2))
    assert energy(1, step) > 10 * energy(0, step)          # erstes Echo rechts
    assert energy(0, 2 * step) > 10 * energy(1, 2 * step)  # zweites links
    assert energy(1, 3 * step) < energy(1, step)           # und es wird leiser
    assert np.abs(echo[:, :burst.start + int(0.3 * mixer.SAMPLE_RATE)]).max() < 1e-3


# ── Vibrato und Übergänge ──────────────────────────────────────────────────────
def curve(notes, frame=0.005, vibrato=0.4, glide=0.06, length=3.0):
    t = np.arange(int(length / frame)) * frame
    midi = np.full(len(t), np.nan)
    for n in notes:
        midi[(t >= n.start) & (t < n.end)] = n.pitch
    for a, b in zip(notes, notes[1:]):
        zone = np.abs(t - b.start) < glide
        x = (t[zone] - b.start + glide) / (2 * glide)
        midi[zone] = a.pitch + (b.pitch - a.pitch) * (1 - np.cos(np.pi * x)) / 2
    for n in notes:
        zone = (t >= n.start + 0.25) & (t < n.end - 0.05)
        midi[zone] += vibrato * np.sin(2 * np.pi * 5.5 * (t[zone] - n.start))
    return t, np.where(np.isnan(midi), 0.0, hz(np.nan_to_num(midi)))


def depth(f0, t, note):
    sel = (t > note.start + 0.35) & (t < note.end - 0.15)
    midi = 69 + 12 * np.log2(f0[sel] / 440)
    return float(np.std(midi - np.mean(midi)) * np.sqrt(2))


def test_vibrato_can_be_removed_or_deepened():
    notes = [N(0.0, 1.5, 60), N(1.5, 3.0, 64)]
    t, f0 = curve(notes)
    assert depth(f0, t, notes[0]) == pytest.approx(0.4, abs=0.05)
    assert depth(voice_fx.shape_pitch(f0, 0.005, notes, vibrato=0.0), t, notes[0]) < 0.06
    assert depth(voice_fx.shape_pitch(f0, 0.005, notes, vibrato=2.0), t, notes[1]) == pytest.approx(0.8, abs=0.1)
    # ohne eigenes Vibrato kommt eines dazu
    _, straight = curve(notes, vibrato=0.0)
    assert depth(voice_fx.shape_pitch(straight, 0.005, notes, vibrato=2.0), t, notes[0]) > 0.2
    assert np.allclose(voice_fx.shape_pitch(f0, 0.005, notes), f0)


def test_glides_can_snap_or_stretch():
    notes = [N(0.0, 1.5, 60), N(1.5, 3.0, 64)]
    t, f0 = curve(notes, vibrato=0.0)

    def at(curve_hz, sec):
        return float(69 + 12 * np.log2(curve_hz[int(round(sec / 0.005))] / 440))
    assert at(f0, 1.48) == pytest.approx(61.0, abs=0.1)
    snapped = voice_fx.shape_pitch(f0, 0.005, notes, glide=0.0)
    assert at(snapped, 1.48) == pytest.approx(60, abs=0.05) and at(snapped, 1.52) == pytest.approx(64, abs=0.05)
    stretched = voice_fx.shape_pitch(f0, 0.005, notes, glide=2.0)
    assert at(stretched, 1.43) > 60.3 and at(stretched, 1.57) < 63.7
    assert np.all(np.abs(np.diff(69 + 12 * np.log2(stretched / 440))) < 0.5)   # keine Sprünge


@pytest.mark.parametrize("psola", [True, False])
def test_reshaped_track_sings_without_vibrato(tmp_path, psola):
    notes = [N(0.3, 1.5, 62), N(1.5, 2.7, 65)]
    path = write(tmp_path / "vocals.wav", sung(notes, 3.0, vibrato=0.5, glide=0.05))
    assert not voice_fx.reshape(path, notes)                 # 1 und 1: nichts zu tun
    assert voice_fx.reshape(path, notes, vibrato=0.0, psola=psola)
    audio, rate = sf.read(path)
    f0, t = measured_pitch(audio, rate)
    limit = 0.2 if psola else 0.15                          # PSOLA lässt etwas mehr übrig, dafür bleibt der Klang
    assert depth(f0, t, notes[0]) < limit and depth(f0, t, notes[1]) < limit
    inside = (t > 0.6) & (t < 1.3)
    assert np.median(f0[inside]) == pytest.approx(hz(62), rel=0.01)


def test_psola_is_used_when_parselmouth_is_there_and_world_otherwise(tmp_path, monkeypatch):
    notes = [N(0.3, 1.5, 62)]
    path = write(tmp_path / "vocals.wav", sung(notes, 2.0, vibrato=0.5))
    used = []
    for name in ("_psola", "_world"):
        real = getattr(voice_fx, name)
        monkeypatch.setattr(voice_fx, name, lambda *a, real=real, name=name: used.append(name) or real(*a))
    voice_fx.reshape(path, notes, vibrato=0.0)
    voice_fx.reshape(path, notes, vibrato=0.0, psola=False)
    monkeypatch.setattr(voice_fx, "psola_available", lambda: False)
    voice_fx.reshape(path, notes, vibrato=0.0)
    assert used == ["_psola", "_world", "_world"]
    assert SongSettings().psola_reshape and main.parse_args(["--ohne-psola"]).ohne_psola


# ── Fassungen ──────────────────────────────────────────────────────────────────
def test_takes_vary_the_style_shift_around_the_chosen_one():
    assert voice_fx.take_shifts(0, 1) == [0]
    assert voice_fx.take_shifts(0, 3) == [0, 1, -1]
    assert voice_fx.take_shifts(6, 3) == [6, 5]


def test_the_take_on_pitch_wins(tmp_path, monkeypatch):
    data = [(None, 2.0), (64, 2.0), (67, 2.0), (None, 1.0), (69, 3.0)]
    notes = voice_fx.timeline(data, 120)
    detune = {0: 0.6, 1: 0.0, -1: -0.9}                   # StyleShift +1 singt in diesem Test am saubersten
    sung_with = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        sung_with.append(style_shift)
        shifted = [N(n.start, n.end, n.pitch + detune[style_shift]) for n in notes]
        write(wav, sung(shifted, 6.0))
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    s = SongSettings(vocal_takes=3, bpm=120, even_takes=False)
    wav = str(tmp_path / "vocals.wav")
    pipeline._neutrino_lead(s, data, "vocals.xml", wav, str(tmp_path), "MERROW")
    assert sung_with == [0, 1, -1]
    assert sorted(os.listdir(tmp_path)) == ["vocals.wav"]
    f0, t = measured_pitch(sf.read(wav)[0], RATE)
    assert np.median(f0[(t > 1.2) & (t < 1.8)]) == pytest.approx(hz(64), rel=0.01)


def test_pitch_error_counts_dropouts(tmp_path):
    notes = [N(0.2, 1.0, 64), N(1.0, 1.8, 67)]
    clean = sung(notes, 2.0)
    broken = clean.copy()
    broken[int(1.1 * RATE):int(1.7 * RATE)] = 0
    assert voice_fx.pitch_error(write(tmp_path / "a.wav", clean), notes) < 30
    assert voice_fx.pitch_error(write(tmp_path / "b.wav", broken), notes) > 200


# ── Chor im letzten Refrain ────────────────────────────────────────────────────
def test_choir_from_the_lead_only_sings_in_the_final_chorus(tmp_path):
    notes = [N(0.2 + k * 0.5, 0.7 + k * 0.5, 64 + k % 3) for k in range(10)]
    lead = write(tmp_path / "vocals.wav", sung(notes, 6.0))
    out = str(tmp_path / "vocals_chor.wav")
    assert voice_fx.choir_from_lead(lead, out, (2.0, 4.0))
    choir, rate = sf.read(out)
    level = np.abs(choir).max(axis=1)
    assert level[:int(1.9 * rate)].max() < 1e-4 and level[int(5.0 * rate):].max() < 1e-4
    assert level[int(2.5 * rate):int(3.5 * rate)].max() > 0.05
    left, right = choir[int(2 * rate):int(4 * rate)].T
    assert np.corrcoef(left, right)[0, 1] < 0.9               # breit, nicht in der Mitte


@pytest.fixture
def fake_neutrino(tmp_path, monkeypatch):
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "REINA", "KIRITAN"):
        (root / "model" / singer).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    calls = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        calls.append((os.path.basename(xml), os.path.basename(model_dir), style_shift))
        t = np.arange(48000 * 2) / 48000
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * t), 48000)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, calls


def test_neutrino_choir_sings_with_the_other_voices(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    s = SongSettings(active_sections=["Verse", "Chorus", "Verse", "Chorus"], output_ordner=str(tmp_path / "out"),
                     neutrino_pfad=str(root), singer="MERROW", harmonies=False)
    tracks, _ = pipeline.compose(s, seed=3)
    out = s.output_dir()
    pipeline._synthesize_vocals(s, tracks, out)
    choir_calls = [c for c in calls if c[0].startswith("vocals_chor")]
    assert sorted(c[1] for c in choir_calls) == ["KIRITAN", "REINA"]
    start, _ = pipeline._final_chorus(tracks["plan"])
    choir, rate = sf.read(os.path.join(out, "vocals_chor.wav"))
    first = np.argmax(np.abs(choir).max(axis=1) > 1e-3) / rate
    assert first == pytest.approx(start * 60 / s.bpm, abs=0.02)
    assert not [f for f in os.listdir(out) if f.startswith("vocals_chor_")]


def test_without_other_voices_the_choir_is_the_same_voice_brighter_and_darker(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    for other in ("REINA", "KIRITAN"):
        os.rmdir(root / "model" / other)
    s = SongSettings(active_sections=["Chorus"], output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root),
                     harmonies=False, style_shift=1)
    tracks, _ = pipeline.compose(s, seed=3)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    # der Chor singt wie der Refrain (StyleShift 1 + 1), eine Stimme dunkler, eine heller
    assert [(c[1], c[2]) for c in calls if c[0].startswith("vocals_chor")] == [("MERROW", 0), ("MERROW", 4)]


def test_choir_and_echo_can_be_switched_off(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"),
                     neutrino_pfad=str(root), harmonies=False, final_choir=False, echo_throws=False,
                     section_style=False, sung_pads=False, adlibs=False)
    tracks, _ = pipeline.compose(s, seed=3)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert [c[0] for c in calls] == ["vocals.xml"]
    assert not os.path.exists(os.path.join(s.output_dir(), "vocals_chor.wav"))
    assert pipeline._throw_windows(s, tracks) == []
    assert pipeline._throw_windows(s.with_updates(echo_throws=True), tracks)


def test_muting_the_vocals_mutes_every_vocal_layer(tmp_path):
    rate = mixer.SAMPLE_RATE
    t = np.arange(2 * rate) / rate
    paths = []
    for name, f in (("vocals", 440), ("vocals_harmony", 550), ("vocals_chor", 660), ("piano", 220)):
        paths.append(str(tmp_path / f"{name}.wav"))
        sf.write(paths[-1], 0.2 * np.sin(2 * np.pi * f * t), rate)
    out = str(tmp_path / "mix.wav")
    mixer.mische_spuren(paths, output_pfad=out, mutes={"vocals": True})
    mix, _ = sf.read(out)
    spectrum = np.abs(np.fft.rfft(mix[:, 0]))
    freqs = np.fft.rfftfreq(len(mix), 1 / rate)

    def peak(f):
        return spectrum[np.abs(freqs - f) < 5].max()
    assert peak(220) > 100 * max(peak(440), peak(550), peak(660))


# ── VOICEVOX ───────────────────────────────────────────────────────────────────
SINGERS = [
    {"name": "波音リツ", "styles": [{"id": 6000, "name": "ノーマル", "type": "sing"}]},
    {"name": "四国めたん", "styles": [{"id": 3002, "name": "ノーマル", "type": "frame_decode"},
                                      {"id": 3003, "name": "あまあま", "type": "frame_decode"}]},
    {"name": "ずんだもん", "styles": [{"id": 3001, "name": "ノーマル", "type": "frame_decode"}]},
]


class FakeVoicevox(BaseHTTPRequestHandler):
    """Antwortet wie VOICEVOX: f0 je Rahmen aus den Noten, gesungen wird ein Ton mit Obertönen."""
    requests = []
    unknown = {"ゔ"}

    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/version":
            self._send(200, "0.16.0")
        elif path == "/singers":
            self._send(200, SINGERS)
        else:
            self._send(404, {"detail": "Not Found"})

    def do_POST(self):
        url = urlparse(self.path)
        speaker = int(parse_qs(url.query)["speaker"][0])
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeVoicevox.requests.append((url.path, speaker, body))
        if url.path == "/sing_frame_audio_query":
            notes = body["notes"]
            assert notes[0]["lyric"] == "" and notes[0]["key"] is None
            for n in notes:
                if n["lyric"] in self.unknown:
                    return self._send(400, {"detail": f"lyricが不正です: {n['lyric']}"})
                assert (n["key"] is None) == (n["lyric"] == "")
            f0 = [float(hz(n["key"])) if n["key"] is not None else 0.0 for n in notes for _ in range(n["frame_length"])]
            self._send(200, {"f0": f0, "volume": [0.5] * len(f0), "volumeScale": 1.0, "outputSamplingRate": RATE,
                             "outputStereo": False,
                             "phonemes": [{"phoneme": "a", "frame_length": n["frame_length"]} for n in notes]})
        elif url.path == "/frame_synthesis":
            f0 = np.repeat(np.asarray(body["f0"]), 256)
            buffer = io.BytesIO()
            sf.write(buffer, tone(f0) * (0.5 + 0.5 * (speaker == 3002)), RATE, format="WAV")
            self._send(200, buffer.getvalue(), "audio/wav")


@pytest.fixture
def fake_voicevox(monkeypatch):
    FakeVoicevox.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoicevox)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(voicevox, "running", real_running)
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_voicevox_score_counts_frames_without_drift():
    data = [(None, 1.0)] + [(60 + k % 5, 0.75) for k in range(40)] + [(None, 0.5), (62, 1.0)]
    silben = ["ら", "っ", "la", "ゃ", "ん"] * 8 + ["き"]
    notes = voicevox.score(data, silben, 137, transpose=0)["notes"]
    assert notes[0] == {"key": None, "frame_length": voicevox.PAD_FRAMES + round(60 / 137 * 93.75), "lyric": ""}
    sung_frames = sum(n["frame_length"] for n in notes) - 2 * voicevox.PAD_FRAMES
    assert sung_frames == round((1.0 + 40 * 0.75 + 0.5 + 1.0) * 60 / 137 * voicevox.FRAME_RATE)
    lyrics = [n["lyric"] for n in notes if n["lyric"]]
    assert "っ" not in lyrics and "la" not in lyrics and "ら" in lyrics and "ん" in lyrics
    assert notes[-1]["lyric"] == "" and all(n["frame_length"] >= 1 for n in notes)


def test_voicevox_sings_in_time_with_the_song(tmp_path, fake_voicevox):
    data = [(None, 4.0), (64, 2.0), (None, 2.0), (67, 2.0)]
    wav = str(tmp_path / "vocals.wav")
    seen = []

    def pitch(f0, frame, offset):
        seen.append((frame, offset))
        return f0 * 2 ** (1 / 12)                          # einen Halbton höher

    voicevox.sing(data, ["か", "ゔ"], 120, wav, fake_voicevox, singer=3002, pitch=pitch)
    assert seen == [(1 / 93.75, -voicevox.PAD_FRAMES / 93.75)]
    audio, rate = sf.read(wav)
    onset = np.argmax(np.abs(audio) > 0.01) / rate
    assert onset == pytest.approx(2.0, abs=0.02)
    f0, t = measured_pitch(audio, rate)
    assert np.median(f0[(t > 2.3) & (t < 2.8)]) == pytest.approx(hz(65), rel=0.01)
    query = [r for r in FakeVoicevox.requests if r[0] == "/sing_frame_audio_query"]
    assert [q[1] for q in query] == [6000, 6000]            # Lehrer-Stimme; „ゔ“ beim zweiten Mal als „ら“
    assert [n["lyric"] for n in query[-1][2]["notes"] if n["lyric"]] == ["か", "ら"]
    assert [r[1] for r in FakeVoicevox.requests if r[0] == "/frame_synthesis"] == [3002]


def test_voicevox_lists_its_singers(fake_voicevox):
    assert voicevox.singers(fake_voicevox) == {6000: "波音リツ (ノーマル)", 3002: "四国めたん (ノーマル)",
                                               3003: "四国めたん (あまあま)", 3001: "ずんだもん (ノーマル)"}
    assert voicevox.pick_singer(fake_voicevox, 3001) == (3001, "ずんだもん (ノーマル)")
    assert voicevox.pick_singer(fake_voicevox, 999)[0] == 6000
    assert voicevox.others(fake_voicevox, 3002) == [6000, 3001]       # andere Figuren, nicht めたん noch einmal


def test_without_neutrino_voicevox_sings_lead_harmony_and_choir(tmp_path, fake_voicevox):
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"),
                     neutrino_pfad=str(tmp_path / "kein-neutrino"), voicevox_url=fake_voicevox, voicevox_singer=3002)
    tracks, _ = pipeline.compose(s, seed=4)
    vocals = pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert vocals and os.path.exists(vocals)
    out = s.output_dir()
    assert os.path.exists(os.path.join(out, "vocals_harmony.wav"))
    synth = [r[1] for r in FakeVoicevox.requests if r[0] == "/frame_synthesis"]
    assert synth[:2] == [3002, 3002] and sorted(synth[2:]) == [3001, 6000]
    choir, rate = sf.read(os.path.join(out, "vocals_chor.wav"))
    data, _ = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], *pipeline._final_chorus(tracks["plan"]))
    first = pipeline._final_chorus(tracks["plan"])[0] + (data[0][1] if data[0][0] is None else 0.0)
    assert np.argmax(np.abs(choir).max(axis=1) > 1e-3) / rate == pytest.approx(first * 60 / s.bpm, abs=0.03)


def test_voicevox_gets_the_vibrato_and_glide_settings(tmp_path, fake_voicevox, monkeypatch):
    s = SongSettings(active_sections=["Verse"], output_ordner=str(tmp_path / "out"), vocal_engine="VOICEVOX",
                     voicevox_url=fake_voicevox, vibrato=0.0, glide=2.0, harmonies=False, final_choir=False)
    tracks, _ = pipeline.compose(s, seed=4)
    shaped = []
    monkeypatch.setattr(voice_fx, "shape_pitch", lambda f0, frame, notes, v, g, offset: shaped.append((v, g)) or f0)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert shaped == [(0.0, 2.0)]


def test_missing_voicevox_falls_back_to_the_preview_voice(tmp_path, monkeypatch):
    s = SongSettings(active_sections=["Verse"], output_ordner=str(tmp_path / "out"), vocal_engine="VOICEVOX",
                     neutrino_pfad=str(tmp_path / "kein-neutrino"), final_choir=False, breaths=False)
    tracks, _ = pipeline.compose(s, seed=4)
    previews = []
    monkeypatch.setattr(pipeline, "_sing_preview", lambda s_, t_, wav: previews.append(wav) or write(wav, np.zeros(RATE)))
    assert pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert len(previews) == 1

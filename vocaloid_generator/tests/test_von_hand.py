# test_von_hand.py – Von Hand nachbessern (Gesang 1.1): eigene Gesangsspur (E1), Noten für Tuning-Tools (E2) und eine
# Phrase neu singen (E3), dazu das Gedächtnis für schon Gesungenes
import os
import zipfile

import numpy as np
import pytest
import soundfile as sf
from test_sektions_stil import level, phrase_levels, singing_neutrino, song  # noqa: F401 – singing_neutrino ist eine Fixture

import exporter
import main
import own_vocal
import pipeline
import singing
import vocal_check
import vocal_synthesizer
import voice_fx
from settings import edit_key
from voice_fx import SungNote

RATE = 48000


def tone(spans, length, rate=RATE):
    t = np.arange(int(length * rate)) / rate
    out = np.zeros_like(t)
    for a, b in spans:
        on = (t >= a) & (t < b)
        out[on] = 0.3 * np.sin(2 * np.pi * 330 * t[on])
    return out


# ── E1: eigene Gesangsspur ─────────────────────────────────────────────────────
def test_the_own_track_is_aligned_to_the_notes():
    notes = [SungNote(2.0, 3.0, 60), SungNote(3.5, 4.5, 62), SungNote(6.0, 7.5, 64)]
    late = tone([(4.0, 5.0), (5.5, 6.5), (8.0, 9.5)], 11)            # ein Takt Vorlauf bei 120 BPM
    assert own_vocal.offset(late, RATE, notes, 120) == pytest.approx(2.0, abs=0.02)
    early = tone([(1.5, 2.5), (3.0, 4.0), (5.5, 7.0)], 9)
    assert own_vocal.offset(early, RATE, notes, 120) == pytest.approx(-0.5, abs=0.02)


def test_place_resamples_and_cuts_the_lead_in(tmp_path):
    notes = [SungNote(2.0, 3.0, 60), SungNote(3.5, 4.5, 62)]
    src = str(tmp_path / "eigen.wav")
    sf.write(src, np.stack([tone([(4.0, 5.0), (5.5, 6.5)], 8, 44100)] * 2, axis=1), 44100)
    out = str(tmp_path / "vocals.wav")
    assert own_vocal.place(src, notes, 120, out) == pytest.approx(2.0, abs=0.02)
    audio, rate = sf.read(out)
    assert rate == RATE and audio.ndim == 1
    assert np.abs(audio[int(2.2 * RATE):int(2.8 * RATE)]).max() > 0.2 and np.abs(audio[:int(1.9 * RATE)]).max() < 1e-3
    assert own_vocal.place(src, notes, 120, out, align=False) == 0.0


def test_the_own_track_replaces_the_lead_and_neutrino_sings_the_rest(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, harmonies=True, section_style=False)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    os.makedirs(out, exist_ok=True)
    xml = vocal_synthesizer.erstelle_musicxml(tracks["melody_data"], tracks["silben"], s.bpm,
                                              str(tmp_path / "eigen.xml"), 0)
    vocal_synthesizer.neutrino_synthese(xml, str(tmp_path / "sung.wav"), str(root), "MERROW")
    sung, _ = sf.read(str(tmp_path / "sung.wav"))
    bar = 4 * 60.0 / s.bpm
    sf.write(str(tmp_path / "eigen.wav"), np.concatenate([np.zeros(int(bar * RATE)), 0.5 * sung]), RATE)
    calls.clear()
    s = s.with_updates(own_vocal=str(tmp_path / "eigen.wav"))
    singing._synthesize_vocals(s, tracks, out)
    names = [c[0] for c in calls]
    assert "vocals.xml" not in names and "vocals_harmony.xml" in names
    lead, _ = sf.read(os.path.join(out, "vocals.wav"))
    n = min(len(lead), len(sung))
    assert np.corrcoef(lead[:n], sung[:n])[0, 1] > 0.95                    # an den Noten ausgerichtet
    assert vocal_check.describe(vocal_check.read(out)) == ("Hauptstimme aus der eigenen Gesangsspur eigen.wav", False)
    assert not os.path.exists(os.path.join(out, "vocals_double.wav"))


def test_a_missing_own_track_lets_the_engine_sing(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, section_style=False, own_vocal=str(tmp_path / "fehlt.wav"))
    tracks, _ = pipeline.compose(s)
    singing._synthesize_vocals(s, tracks, s.output_dir())
    assert [c[0] for c in calls] == ["vocals.xml"]


def test_own_track_switches_on_the_command_line():
    args = main.parse_args(["--eigener-gesang", "x.wav", "--ohne-ausrichten", "--noten-zip", "n.zip"])
    assert args.eigener_gesang == "x.wav" and args.ohne_ausrichten and args.noten_zip == "n.zip"


# ── E2: Noten für Tuning-Tools ─────────────────────────────────────────────────
def test_the_notes_go_out_with_a_readme(tmp_path):
    class Result:
        output_dir = str(tmp_path)
    for name in ("vocals.xml", "vocals.ust", "vocal_melody.mid"):
        (tmp_path / name).write_text("x")
    target = exporter.exportiere_noten(Result(), str(tmp_path / "export" / "noten.zip"))
    with zipfile.ZipFile(target) as z:
        assert sorted(z.namelist()) == ["LIESMICH.txt", "vocal_melody.mid", "vocals.ust", "vocals.xml"]
        assert "Eigene Gesangsspur" in z.read("LIESMICH.txt").decode("utf-8")
    empty = tmp_path / "leer"
    empty.mkdir()
    Result.output_dir = str(empty)
    with pytest.raises(FileNotFoundError):
        exporter.exportiere_noten(Result(), str(tmp_path / "n.zip"))


# ── Gedächtnis und E3: eine Phrase neu singen ──────────────────────────────────
def test_what_neutrino_sang_is_not_sung_again(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, harmonies=True)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    singing._synthesize_vocals(s, tracks, out)
    first = len(calls)
    assert first >= 2 and os.listdir(os.path.join(out, singing.TAKE_CACHE))
    before, _ = sf.read(os.path.join(out, "vocals.wav"))
    calls.clear()
    singing._synthesize_vocals(s.with_updates(glide=0.5), tracks, out)     # anderer Schlüssel, dieselben Noten
    assert calls == []
    singing._synthesize_vocals(s.with_updates(reuse_steps=False), tracks, out)
    assert len(calls) == first                                              # ohne Wiederverwenden singt alles neu
    assert len(before)


def test_one_phrase_is_sung_again_with_its_own_voice_and_style(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, section_style=False)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    singing._synthesize_vocals(s, tracks, out)
    notes = voice_fx.timeline(tracks["melody_data"], s.bpm, vocal_synthesizer.stimmlage(s.singer)[2])
    second = voice_fx.phrases(notes)[1]
    key = edit_key((second[0].start + 0.01) * s.bpm / 60)                # ein Ton der Phrase genügt
    calls.clear()
    fixed = s.with_updates(phrase_fixes={key: {"style_shift": 3, "singer": "REINA"}})
    singing._synthesize_vocals(fixed, tracks, out)
    assert calls == [("vocals_phrase_1.xml", "REINA", 3)]                  # nur die Phrase, der Rest aus dem Gedächtnis
    levels = [v for _, v in phrase_levels(os.path.join(out, "vocals.wav"), tracks, s)]
    assert levels[1] == pytest.approx(level(3), rel=0.1)
    assert all(v == pytest.approx(level(0), rel=0.1) for k, v in enumerate(levels) if k != 1)
    assert not [f for f in os.listdir(out) if "_phrase_" in f or "_fassung_" in f]


def test_a_phrase_fix_with_a_missing_voice_sings_with_the_singer(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, section_style=False)
    tracks, _ = pipeline.compose(s)
    notes = voice_fx.timeline(tracks["melody_data"], s.bpm, vocal_synthesizer.stimmlage(s.singer)[2])
    key = edit_key(voice_fx.phrases(notes)[0][0].start * s.bpm / 60)
    s = s.with_updates(phrase_fixes={key: {"style_shift": -2, "singer": "GIBTSNICHT"}})
    singing._synthesize_vocals(s, tracks, s.output_dir())
    assert ("vocals_phrase_1.xml", "MERROW", -2) in calls

# test_humming.py – eine gesummte Melodie in Noten verwandeln (mit einer künstlichen, etwas schiefen Stimme)
import os

import numpy as np
import pretty_midi
import soundfile as sf

import humming
import main
import melody_import
import pipeline
from settings import SongSettings

RATE = 22050
BPM = 100
# Schlag, Dauer, Tonhöhe: Tonleiter hoch, ein Ton zweimal, ein langer Ton mit Vibrato
TUNE = [(0, 1, 60), (1, 1, 62), (2, 0.5, 64), (2.5, 0.5, 64), (3, 2, 67), (5, 1, 65), (6, 2, 64)]


def hum(path, tune=TUNE, bpm=BPM, cents=30, silence=0.37):
    """Eine Stimme mit Obertönen, Vibrato und Rauschen, um cents zu hoch, nach silence Sekunden Stille."""
    beat = 60 / bpm
    y = np.zeros(int((silence + (tune[-1][0] + tune[-1][1]) * beat + 0.5) * RATE))
    for start, dur, pitch in tune:
        a, n = int((silence + start * beat) * RATE), int((dur * beat - 0.05) * RATE)
        t = np.arange(n) / RATE
        f = 440 * 2 ** ((pitch + cents / 100 - 69) / 12) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t))
        phase = 2 * np.pi * np.cumsum(f) / RATE
        envelope = np.minimum(1, t / 0.03) * np.minimum(1, (n / RATE - t) / 0.04)
        y[a:a + n] += 0.3 * envelope * (np.sin(phase) + 0.4 * np.sin(2 * phase) + 0.2 * np.sin(3 * phase))
    y += 0.003 * np.random.default_rng(1).standard_normal(len(y))
    sf.write(str(path), y, RATE)
    return str(path)


def test_a_hummed_tune_becomes_its_notes(tmp_path):
    found = humming.quantize(humming.notes(humming.pitches(hum(tmp_path / "summen.wav"))), BPM)
    assert found == TUNE


def test_the_notes_land_as_midi_the_app_can_sing(tmp_path):
    target = humming.target_for(hum(tmp_path / "mein lied.wav"), str(tmp_path / "out"))
    assert target == str(tmp_path / "out" / "summen" / "mein lied.mid")
    assert humming.transcribe(str(tmp_path / "mein lied.wav"), BPM, target) == len(TUNE)
    assert pretty_midi.PrettyMIDI(target).estimate_tempo() > 0
    assert melody_import.load(target) == [(float(s), float(d), p) for s, d, p in TUNE]


def test_silence_noise_and_broken_files_give_no_melody(tmp_path):
    sf.write(str(tmp_path / "still.wav"), np.zeros(RATE * 2), RATE)
    sf.write(str(tmp_path / "rauschen.wav"), 0.1 * np.random.default_rng(2).standard_normal(RATE * 2), RATE)
    (tmp_path / "kaputt.wav").write_bytes(b"RIFF kaputt")
    for name in ("still.wav", "rauschen.wav", "kaputt.wav"):
        assert humming.transcribe(str(tmp_path / name), BPM, str(tmp_path / f"{name}.mid")) is None
        assert not os.path.exists(tmp_path / f"{name}.mid")


def test_overlapping_and_same_step_notes_are_cleaned_up():
    beat = 60 / 120
    found = [(0.0, 0.6 * beat, 60), (0.05 * beat, 0.3 * beat, 62), (0.5 * beat, 1.2 * beat, 64)]
    assert humming.quantize(found, 120) == [(0.0, 0.5, 60), (0.5, 0.75, 64)]


def test_cli_hums_the_melody(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(main, "generate_song", lambda settings, progress=None: seen.append(settings) or
                        pipeline.SongResult(seed=1, output_dir=str(tmp_path), settings=settings))
    SongSettings(output_ordner=str(tmp_path / "out"), bpm=BPM).save()
    assert main.main(["--summen", hum(tmp_path / "idee.wav")]) == 0
    assert seen[-1].melody_midi == str(tmp_path / "out" / "summen" / "idee.mid")
    assert main.main(["--summen", str(tmp_path / "fehlt.wav")]) == 1

# test_preview.py – geänderte Töne sofort anhören (Synth über der Band, nur um die Änderungen herum)
import os

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import preview
from pipeline import SongResult
from settings import SongSettings

BPM = 120           # ein Schlag = 0,5 s, ein Takt = 2 s


@pytest.fixture
def song(tmp_path):
    out = str(tmp_path)
    pm = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    voice = pretty_midi.Instrument(0)
    voice.notes = [pretty_midi.Note(100, 60 + i, i * 0.5, i * 0.5 + 0.4) for i in range(16)]   # ein Ton pro Schlag
    pm.instruments.append(voice)
    pm.write(os.path.join(out, "vocal_melody.mid"))
    t = np.arange(10 * 44100) / 44100
    sf.write(os.path.join(out, "piano.wav"), np.stack([0.2 * np.sin(2 * np.pi * 220 * t)] * 2, axis=1), 44100)
    sf.write(os.path.join(out, "bass.wav"), 0.2 * np.sin(2 * np.pi * 55 * t[:22050 * 10]), 22050)   # mono, 22 kHz
    return SongResult(seed=1, output_dir=out, settings=SongSettings(bpm=BPM),
                      wav_files={"piano": os.path.join(out, "piano.wav"), "bass": os.path.join(out, "bass.wav")})


def test_the_melody_takes_new_pitches_and_lengths(song):
    notes, changed = preview.edited_melody(song, {"4": 70}, {"5": 3.0, "15": 1.5})
    assert [n.pitch for n in changed] == [70, 65, 75]
    assert notes[4].pitch == 70 and notes[4].end == pytest.approx(2.4)          # Länge unverändert
    assert notes[5].end == pytest.approx(3.0)                                    # endet am nächsten Ton
    assert notes[15].end == pytest.approx(7.5 + 0.75)                            # der letzte darf länger werden
    assert preview.edited_melody(song, {}, {})[1] == []


def test_the_preview_plays_around_the_changes(song):
    path = preview.render(song, {"6": 72}, {})
    assert path == os.path.join(song.output_dir, preview.FILE)
    data, rate = sf.read(path)
    assert len(data) == pytest.approx((3.4 + 2 - 1) * rate, abs=2)                # ein Takt davor und danach
    assert 0.1 < np.max(np.abs(data)) <= 0.9
    spectrum = np.abs(np.fft.rfft(data[int(2 * rate):int(2.35 * rate)].mean(axis=1)))
    freqs = np.fft.rfftfreq(int(0.35 * rate), 1 / rate)
    assert abs(freqs[np.argmax(spectrum * (freqs > 400))] - 523.25) < 15          # der geänderte Ton: C5


def test_without_changes_or_melody_there_is_no_preview(song, tmp_path):
    assert preview.render(song, {}, {}) is None
    os.remove(os.path.join(song.output_dir, "vocal_melody.mid"))
    assert preview.render(song, {"6": 72}, {}) is None

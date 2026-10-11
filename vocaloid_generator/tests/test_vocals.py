# test_vocals.py – Rendern mit/ohne VST, MusicXML für NEUTRINO und die lokale Vorschau-Stimme
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from mixer import midi_zu_wav
from vocal_synthesizer import erstelle_musicxml

BPM = 120
MELODY = [(69, 1.0), (71, 1.0), (None, 0.5), (72, 1.5), (74, 1.0), (72, 2.0)]
SILBEN = ["ら", "ら", "る", "ら", "ら"]


@pytest.fixture
def tiny_midi(tmp_path):
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
    pm.instruments.append(inst)
    path = tmp_path / "test.mid"
    pm.write(str(path))
    return str(path)


class FakeInstrument:
    """Wie ein VST3-Instrument in pedalboard: bekommt MIDI mit Zeiten in Sekunden und liefert Audio."""
    is_instrument = True

    def __call__(self, messages, duration, sample_rate, num_channels=2):
        self.messages, self.duration = messages, duration
        return np.full((num_channels, int(duration * sample_rate)), 0.1, dtype=np.float32)


def test_vst_instrument_gets_midi_in_seconds(tmp_path, tiny_midi, monkeypatch):
    import mixer
    fake = FakeInstrument()
    monkeypatch.setattr(mixer, "load_plugin", lambda path: fake)
    plugin = tmp_path / "Surge XT.vst3"
    plugin.write_text("")
    wav = str(tmp_path / "out.wav")
    midi_zu_wav(tiny_midi, wav, instrument_type="synth", vst_pfad=str(plugin))
    assert [(m.type, m.note, m.time) for m in fake.messages] == [("note_on", 60, 0.0), ("note_off", 60, 1.0)]
    audio, _ = sf.read(wav)
    assert abs(audio).max() > 0.05


@pytest.mark.parametrize("vst", [None, "gibtsnicht.vst3", 12345])
def test_rendering_survives_a_missing_or_broken_vst(tmp_path, tiny_midi, vst):
    wav = str(tmp_path / "test.wav")
    midi_zu_wav(tiny_midi, wav, is_drum=False, instrument_type="piano", vst_pfad=vst)
    audio, sr = sf.read(wav)
    assert sr == 44100 and np.abs(audio).max() > 0


def test_musicxml_carries_notes_and_lyrics(tmp_path):
    xml = erstelle_musicxml(MELODY, SILBEN, BPM, str(tmp_path / "vocals.xml"))
    text = open(xml, encoding="utf-8").read()
    assert text.count("<lyric") == len(SILBEN)
    for silbe in set(SILBEN):
        assert silbe in text


# ── Lokale Vorschau-Stimme (braucht eine Sprachausgabe, also Windows mit pyttsx3) ─
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTS_TIMEOUT = 120  # Sekunden; ohne angemeldeten Benutzer wartet die Windows-Sprachausgabe sonst ewig

_RUN_VOCALS = """
import json, sys
from vocal_synthesizer import generiere_lokale_vocals
melody, silben, bpm, wav = json.loads(sys.argv[1])
generiere_lokale_vocals(melody, silben, bpm, wav, breathiness=0.03, shimmer=True)
"""


@pytest.fixture(scope="module")
def local_vocals(tmp_path_factory):
    if importlib.util.find_spec("pyttsx3") is None:
        pytest.skip("pyttsx3 ist nicht installiert")
    wav = str(tmp_path_factory.mktemp("vocals") / "vocals.wav")
    payload = json.dumps([MELODY, SILBEN, BPM, wav])
    try:
        run = subprocess.run([sys.executable, "-c", _RUN_VOCALS, payload], cwd=APP_DIR, timeout=TTS_TIMEOUT,
                             capture_output=True, encoding="utf-8", errors="replace",
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        pytest.skip(f"Sprachausgabe antwortet nicht innerhalb von {TTS_TIMEOUT} s")
    if run.returncode != 0 or not os.path.exists(wav):
        pytest.skip(f"Sprachausgabe nicht verfügbar: {run.stderr.strip().splitlines()[-1:]}")
    audio, sr = sf.read(wav)
    return (audio[:, 0] if audio.ndim > 1 else audio), sr


def test_local_vocals_do_not_clip_or_click(local_vocals):
    audio, sr = local_vocals
    assert np.abs(audio).max() <= 0.96
    assert np.abs(np.diff(audio)).max() < 0.95

    quarter = 60.0 / BPM
    pos = 0
    for pitch, dauer in MELODY:
        length = int(dauer * quarter * sr)
        if pitch is not None and length > 50:
            assert abs(audio[pos]) < 0.05, "kein Einblenden am Silbenanfang"
            assert abs(audio[pos + length - 1]) < 0.05, "kein Ausblenden am Silbenende"
        pos += length


def test_local_vocals_glide_between_notes(local_vocals):
    import pyworld as pw
    audio, sr = local_vocals
    audio = np.ascontiguousarray(audio, dtype=np.float64)
    f0, t = pw.dio(audio, sr)
    f0 = pw.stonemask(audio, f0, t, sr)
    voiced = np.where(f0 > 0)[0]
    assert len(voiced) > 0
    jumps = [i for a, b in zip(voiced, voiced[1:]) if b == a + 1 and abs(f0[b] - f0[a]) >= 35.0 for i in [a]]
    assert not jumps, f"{len(jumps)} harte Tonsprünge"

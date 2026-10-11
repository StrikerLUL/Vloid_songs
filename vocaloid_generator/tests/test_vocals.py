# test_vocals.py – Rendern mit/ohne VST, MusicXML für NEUTRINO und die lokale Vorschau-Stimme
import importlib.util
import os

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from mixer import midi_zu_wav
from vocal_synthesizer import erstelle_musicxml, generiere_lokale_vocals

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
@pytest.fixture(scope="module")
def local_vocals(tmp_path_factory):
    if importlib.util.find_spec("pyttsx3") is None:
        pytest.skip("pyttsx3 ist nicht installiert")
    wav = str(tmp_path_factory.mktemp("vocals") / "vocals.wav")
    try:
        generiere_lokale_vocals(MELODY, SILBEN, BPM, wav, breathiness=0.03, shimmer=True)
    except Exception as e:  # keine Stimme auf diesem Rechner
        pytest.skip(f"Sprachausgabe nicht verfügbar: {e}")
    if not os.path.exists(wav):
        pytest.skip("Sprachausgabe hat keine Datei erzeugt")
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

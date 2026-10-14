# test_accompaniment.py – KI-Begleitung (Versuch) mit einem nachgebauten Anticipatory Music Transformer
import json
import os
import sys

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import accompaniment
import einrichten
import main
import pipeline
import systemcheck
from settings import SongSettings

# Statt des Modells: zu jedem Ton der Melodie ein Klavierton eine Oktave tiefer und ein Streicherton, dazu Bass und
# Schlagzeug, die die App nicht übernehmen darf. Wie oft es lief, steht in aufrufe.txt.
FAKE_WORKER = '''
import json, os, sys
job = json.load(open(sys.argv[1], encoding="utf-8"))
mode = os.environ.get("BEGLEITUNG_ART", "")
if mode == "kaputt":
    print("CUDA out of memory", file=sys.stderr)
    sys.exit(1)
notes = []
for start, end, pitch, instr in job["notes"]:
    if instr == 53:
        if mode != "nur-bass":
            notes += [[start, end, pitch - 12, 0], [start, end + 0.5, pitch - 5, 48]]
        notes += [[start, end, 40, 33], [start, start + 0.1, 42, 128]]
json.dump({"notes": notes, "model": "nachgebaut"}, open(job["output"], "w", encoding="utf-8"))
with open(os.path.join(os.path.dirname(__file__), "aufrufe.txt"), "a") as f:
    f.write(str(job["seed"]) + " ")
print("Begleitung bis 8 von 8 Sekunden")
print("BEGLEITET " + json.dumps({"device": "cpu", "model": "nachgebaut", "notes": len(notes)}))
'''


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    worker = tmp_path / "worker" / "accompaniment_worker.py"
    worker.parent.mkdir()
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(accompaniment, "python", lambda: sys.executable)
    monkeypatch.setattr(accompaniment, "WORKER", str(worker))
    return worker.parent / "aufrufe.txt"


@pytest.fixture
def song(tmp_path):
    settings = SongSettings(output_ordner=str(tmp_path / "out"), seed=4, active_sections=["Verse", "Chorus"],
                            section_bars={"Verse": 2, "Chorus": 2})
    tracks, seed = pipeline.compose(settings)
    return settings, tracks, seed


def sections(tracks):
    return pipeline._section_energies(tracks["plan"])


# ── Zuordnung ─────────────────────────────────────────────────────────────────────
def test_programs_land_in_the_channels_of_the_app():
    found = {p: accompaniment.channel_for(p) for p in (0, 11, 19, 25, 33, 41, 48, 52, 53, 57, 73, 81, 89, 105, 118)}
    assert found == {0: "piano", 11: "bells", 19: "synth", 25: "guitar", 33: None, 41: "strings", 48: "strings",
                     52: "choir", 53: None, 57: "brass", 73: "counter", 81: "synth", 89: "synth", 105: "guitar",
                     118: None}


def test_melody_bass_and_groove_are_given(song):
    _, tracks, _ = song
    given = accompaniment.given_notes(tracks)
    instruments = {i for *_, i in given}
    assert instruments == {accompaniment.MELODY, accompaniment.BASS, accompaniment.DRUMS}
    drums = [p for _, _, p, i in given if i == accompaniment.DRUMS]
    assert set(drums) <= set(accompaniment.GROOVE)
    assert len([1 for *_, i in given if i == accompaniment.MELODY]) == len(tracks["vocal_melody"])
    assert given == sorted(given)


# ── Schreiben und übernehmen ──────────────────────────────────────────────────────
def test_the_model_replaces_the_accompaniment(song, fake_model):
    settings, tracks, seed = song
    out = settings.output_dir()
    bass_before = [(n.start, n.pitch) for n in tracks["bass"]]
    melody = len(tracks["vocal_melody"])
    assert accompaniment.accompany(tracks, out, settings.bpm, seed, sections(tracks))
    assert len(tracks["piano"]) == melody and len(tracks["strings"]) == melody
    assert [(n.start, n.pitch) for n in tracks["bass"]] == bass_before        # Bass und Schlagzeug bleiben
    for channel in ("guitar", "synth", "brass"):                              # was das Modell nicht spielt, schweigt
        assert tracks[channel] == [] and not os.path.exists(os.path.join(out, f"{channel}.mid"))
    piano = pretty_midi.PrettyMIDI(os.path.join(out, "piano.mid"))
    assert [i.program for i in piano.instruments] == [0]
    assert len(piano.instruments[0].notes) == melody
    # wo der Song mehr Energie hat, spielt das Klavier kräftiger
    quiet, loud = min(sections(tracks), key=lambda p: p[2]), max(sections(tracks), key=lambda p: p[2])
    def velocities(part):
        return {n.velocity for n in tracks["piano"] if part[0] <= n.start < part[1]}
    assert max(velocities(quiet)) < min(velocities(loud))
    # gleiche Vorgabe und gleicher Seed: nicht noch einmal schreiben
    again, _ = pipeline.compose(settings, seed)
    assert accompaniment.accompany(again, out, settings.bpm, seed, sections(again))
    assert fake_model.read_text().split() == [str(seed)]
    assert len(again["piano"]) == melody


def test_without_the_model_everything_stays(song):
    settings, tracks, seed = song
    piano = list(tracks["piano"])
    assert not accompaniment.available()
    assert not accompaniment.accompany(tracks, settings.output_dir(), settings.bpm, seed)
    assert tracks["piano"] == piano


@pytest.mark.parametrize("mode", ["kaputt", "nur-bass"])
def test_a_useless_answer_keeps_the_composed_accompaniment(song, fake_model, monkeypatch, mode):
    monkeypatch.setenv("BEGLEITUNG_ART", mode)
    settings, tracks, seed = song
    out = settings.output_dir()
    piano = list(tracks["piano"])
    assert not accompaniment.accompany(tracks, out, settings.bpm, seed)
    assert tracks["piano"] == piano and os.path.exists(os.path.join(out, "piano.mid"))


# ── Im Song, Schalter, Einrichten, Systemcheck ────────────────────────────────────
@pytest.fixture
def quiet_singer(monkeypatch):
    def sing(settings, tracks, wav):      # die Windows-Sprachausgabe hängt in der CI (siehe test_vocals.py)
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * np.arange(4 * 44100) / 44100), 44100)
        return True
    monkeypatch.setattr(pipeline, "_sing_preview", sing)


def test_a_song_with_ai_accompaniment(song, fake_model, quiet_singer):
    settings, _, _ = song
    result = pipeline.generate_song(settings.with_updates(ai_accompaniment=True), keep_history=False)
    out = result.output_dir
    assert "piano" in result.wav_files and "guitar" not in result.wav_files
    assert os.path.exists(os.path.join(out, accompaniment.RESULT_FILE))
    assert fake_model.read_text().split() == ["4"]


def test_switched_off_or_draft_the_model_is_not_asked(song, fake_model, monkeypatch):
    settings, tracks, _ = song
    monkeypatch.setattr(accompaniment, "accompany", lambda *a, **kw: pytest.fail("nicht gefragt"))
    assert settings.ai_accompaniment is False
    assert pipeline.generate_song(settings.with_updates(channels={"vocals": {"enabled": False}}),
                                  keep_history=False).mix_wav
    draft = pipeline.draft_settings(settings.with_updates(ai_accompaniment=True))
    assert draft.draft and draft.ai_accompaniment
    assert pipeline.generate_song(draft, keep_history=False).mix_wav


def test_cli_switches_the_ai_accompaniment(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(main, "generate_song", lambda settings, progress=None: seen.append(settings) or
                        pipeline.SongResult(seed=1, output_dir=str(tmp_path), settings=settings))
    assert main.main(["--ki-begleitung"]) == 0
    assert main.main(["--ohne-ki-begleitung"]) == 0
    assert main.main([]) == 0
    assert [s.ai_accompaniment for s in seen] == [True, False, False]


def test_offered_in_the_setup_but_not_preselected():
    found = einrichten.find("begleitung")
    assert found.script == "setup_begleitung.py" and not found.recommended
    assert not einrichten.is_installed(found)


def test_systemcheck_lets_the_model_write(tmp_path, fake_model):
    ok, message = systemcheck.check_accompaniment(SongSettings(), str(tmp_path))
    assert ok is True and "mit 64 Tönen" in message
    assert json.loads((tmp_path / accompaniment.RESULT_FILE).read_text())["notes"]


def test_systemcheck_without_the_model_is_grey(tmp_path):
    assert systemcheck.check_accompaniment(SongSettings(), str(tmp_path))[0] is None

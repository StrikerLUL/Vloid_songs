# test_rating.py – mehrere Fassungen automatisch bewerten (Audiobox Aesthetics, hier mit nachgebautem Modell)
import json
import os
import sys

import numpy as np
import pytest
import soundfile as sf

import config
import history
import main
import pipeline
import rating
from pipeline import SongResult, generate_variants
from rating import Rating
from settings import SongSettings

sys.path.insert(0, config.REPO_ROOT)
import setup_bewertung  # noqa: E402

RATE = 8000

# Nachgebautes Modell: CE ist die Länge der Datei in Sekunden, PQ die Zahl der Dateien, HF_HOME steht in den Daten
FAKE_WORKER = '''
import json, os, sys
import soundfile as sf
rows = [{"CE": sf.info(p).duration, "CU": 5.0, "PC": 4.0, "PQ": float(len(sys.argv) - 1),
         "home": os.environ.get("HF_HOME", "")} for p in sys.argv[1:]]
print("Modell geladen")
print("BEWERTUNG " + json.dumps(rows))
'''


def wav(path, seconds, amp=0.1):
    sf.write(str(path), np.full((int(seconds * RATE), 2), amp, dtype=np.float32), RATE)
    return str(path)


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    worker = tmp_path / "worker.py"
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(rating, "python", lambda: sys.executable)
    monkeypatch.setattr(rating, "WORKER", str(worker))
    return worker


def test_the_excerpt_is_the_loudest_part(tmp_path):
    data = np.full((60 * RATE, 2), 0.01, dtype=np.float32)
    data[40 * RATE:] = 0.5                                                  # die letzten 20 Sekunden: der Refrain
    sf.write(str(tmp_path / "song.wav"), data, RATE)
    clip = rating.excerpt(str(tmp_path / "song.wav"), str(tmp_path / "clip.wav"))
    out, rate = sf.read(clip)
    assert len(out) == 30 * rate and np.mean(np.abs(out)) > 0.3
    short = rating.excerpt(wav(tmp_path / "kurz.wav", 5), str(tmp_path / "kurz_clip.wav"))
    assert sf.info(short).duration == pytest.approx(5)
    assert rating.excerpt(str(tmp_path / "fehlt.wav"), str(tmp_path / "x.wav")) is None


def test_ratings_come_from_the_model_in_its_own_environment(tmp_path, fake_model):
    assert rating.available()
    found = rating.rate([wav(tmp_path / "a.wav", 2), wav(tmp_path / "b.wav", 4)])
    assert [r.enjoyment for r in found] == [2.0, 4.0]
    assert found[0] == Rating(enjoyment=2.0, usefulness=5.0, complexity=4.0, quality=2.0)
    assert found[1].overall == 3.0 and found[1].describe() == "Note 3.0 (Hörspaß 4.0, Klang 2.0)"
    assert Rating.from_dict(found[1].to_dict()) == found[1]
    assert Rating.from_dict({"enjoyment": "x"}) is None


def test_the_model_cache_stays_in_the_tools_folder(tmp_path, fake_model):
    fake_model.write_text(FAKE_WORKER.replace('"CU": 5.0', '"CU": float(os.environ["HF_HOME"].startswith('
                                              f'{json.dumps(rating.FOLDER)}))'), encoding="utf-8")
    assert rating.rate([wav(tmp_path / "a.wav", 1)])[0].usefulness == 1.0


def test_a_broken_or_missing_model_rates_nothing(tmp_path, fake_model):
    fake_model.write_text("import sys\nprint('kaputt', file=sys.stderr)\nsys.exit(1)\n", encoding="utf-8")
    assert rating.rate([wav(tmp_path / "a.wav", 1), wav(tmp_path / "b.wav", 1)]) == [None, None]
    fake_model.write_text("print('BEWERTUNG kein json')\n", encoding="utf-8")
    assert rating.rate([wav(tmp_path / "a.wav", 1)]) == [None]


def test_without_setup_nothing_is_rated(tmp_path):
    assert not rating.available()
    assert rating.rate([wav(tmp_path / "a.wav", 1)]) == [None]
    assert "setup_bewertung.py" in rating.status()


# ── Fassungen ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def rated_variants(tmp_path, monkeypatch):
    """Erzeugen ist nachgebaut: Fassung k ist k Sekunden lang, das nachgebaute Modell mag lange Fassungen."""
    out = str(tmp_path / "out")
    made = []

    def fake_song(settings, progress=None, seed=None):
        made.append(settings)
        seconds = [2, 5, 3][(len(made) - 1) % 3]
        os.makedirs(out, exist_ok=True)
        mix = wav(os.path.join(out, "final_mix.wav"), seconds)        # jede Fassung überschreibt den Mix
        settings = settings.with_updates(seed=len(made))
        entry = history.record(mix, settings, out)
        progress(1.0, "Fertig")
        return SongResult(seed=len(made), output_dir=out, mix_wav=mix, settings=settings, history=entry.audio)

    monkeypatch.setattr(pipeline, "generate_song", fake_song)
    monkeypatch.setattr(main, "generate_song", fake_song)
    return SongSettings(output_ordner=out)


def test_variants_get_a_rating_and_the_best_is_found(rated_variants, fake_model):
    steps = []
    results = generate_variants(rated_variants, 3, progress=lambda f, msg: steps.append((f, msg)))
    assert [r.rating.enjoyment for r in results] == [2.0, 5.0, 3.0]
    assert pipeline.best(results).seed == 2
    assert any(msg == "Bewerte die Fassungen..." for _, msg in steps)
    saved = {e.settings.seed: Rating.from_dict(e.rating) for e in history.entries(rated_variants.output_ordner)}
    assert saved[2].enjoyment == 5.0 and saved[1].enjoyment == 2.0


def test_the_switch_turns_the_rating_off(rated_variants, fake_model):
    results = generate_variants(rated_variants.with_updates(auto_rating=False), 3)
    assert all(r.rating is None for r in results)
    assert pipeline.best(results).seed == 3                                 # ohne Noten: die letzte
    assert all(e.rating is None for e in history.entries(rated_variants.output_ordner))


def test_a_single_song_is_not_rated(rated_variants, fake_model):
    [result] = generate_variants(rated_variants, 1)
    assert result.rating is None


def test_cli_names_the_best_version(rated_variants, fake_model, caplog):
    rated_variants.save()
    with caplog.at_level("INFO"):
        assert main.main(["--varianten", "3"]) == 0
    assert "Beste Fassung: Seed 2, Note 4.0" in caplog.text
    assert main.main(["--varianten", "2", "--ohne-bewertung"]) == 0
    assert SongSettings.load().auto_rating is True                          # nur für diesen Aufruf


# ── setup_bewertung.py ──────────────────────────────────────────────────────────────

def test_setup_builds_its_own_environment(monkeypatch):
    commands = []
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: "/bin/uv")
    monkeypatch.setattr(setup_bewertung.subprocess, "run",
                        lambda cmd, **kw: commands.append(cmd) or type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(rating, "rate", lambda paths: [Rating(6.0, 5.0, 4.0, 7.0)])
    assert setup_bewertung.setup()
    venv, install = commands
    assert venv[:3] == ["/bin/uv", "venv", os.path.join(rating.FOLDER, "venv")]
    assert install[install.index("--python") + 1] == rating.python()
    assert install[install.index("--torch-backend") + 1] == "auto" and "audiobox_aesthetics==0.0.4" in install
    commands.clear()
    assert setup_bewertung.setup(cpu=True)
    assert commands[-1][commands[-1].index("--torch-backend") + 1] == "cpu"


def test_setup_needs_uv_and_a_working_model(monkeypatch):
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: None)
    assert not setup_bewertung.setup()
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: "/bin/uv")
    monkeypatch.setattr(setup_bewertung.subprocess, "run", lambda cmd, **kw: type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(rating, "rate", lambda paths: [None])
    assert not setup_bewertung.setup()

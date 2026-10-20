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


MISSING_REQUESTS = """import sys
print('Traceback (most recent call last):', file=sys.stderr)
print('  File "audiobox_aesthetics/utils.py", line 12, in <module>', file=sys.stderr)
print("ModuleNotFoundError: No module named 'requests'", file=sys.stderr)
sys.exit(1)
"""


def test_a_missing_package_is_named_and_offered_again(tmp_path, fake_model):
    """Audiobox braucht requests, gibt es aber nicht an (seit huggingface_hub 1.0 kommt es nicht mehr mit)."""
    import einrichten
    os.makedirs(rating.FOLDER)
    fake_model.write_text(MISSING_REQUESTS, encoding="utf-8")
    assert rating.rate([wav(tmp_path / "a.wav", 1)]) == [None]
    assert rating.missing_package() == "requests" and not rating.complete()
    assert "„requests“" in rating.problem() and "Einrichten" in rating.problem()
    assert rating.status() == rating.problem()
    assert not einrichten.is_installed(einrichten.find("rating"))        # der Assistent bietet sie wieder an
    fake_model.write_text(FAKE_WORKER, encoding="utf-8")                 # neu eingerichtet: läuft wieder
    assert rating.rate([wav(tmp_path / "a.wav", 1)])[0] is not None
    assert rating.missing_package() is None and rating.complete()
    assert einrichten.is_installed(einrichten.find("rating"))
    assert rating.problem() == "Die Bewertung lief nicht (Protokoll ansehen)"


def hf_cache_with_links(home):
    """
    So legte huggingface_hub das Modell bis 1.2.1 an: jede Datei eine Verknüpfung in den Speicher daneben, große über
    einen zweiten Verweis in den gemeinsamen Speicher hub/blobs. Zwei Fassungen teilen sich config.json.
    """
    repo = os.path.join(home, "hub", "models--facebook--audiobox-aesthetics")
    for folder in ("blobs", os.path.join("snapshots", "alt"), os.path.join("snapshots", "neu")):
        os.makedirs(os.path.join(repo, folder))
    os.makedirs(os.path.join(home, "hub", "blobs", "ab"))
    with open(os.path.join(repo, "blobs", "c0f1"), "w", encoding="utf-8") as f:
        f.write('{"output_dim": 4}')
    with open(os.path.join(home, "hub", "blobs", "ab", "abcd"), "wb") as f:
        f.write(b"gewichte")
    try:
        os.symlink(os.path.join("..", "..", "blobs", "ab", "abcd"), os.path.join(repo, "blobs", "e5"))
        for rev in ("alt", "neu"):
            os.symlink(os.path.join("..", "..", "blobs", "c0f1"), os.path.join(repo, "snapshots", rev, "config.json"))
        os.symlink(os.path.join("..", "..", "blobs", "e5"), os.path.join(repo, "snapshots", "neu", "model.safetensors"))
    except OSError:
        pytest.skip("hier lassen sich keine Verknüpfungen anlegen")
    return repo


def test_links_from_older_versions_become_real_files(tmp_path, fake_model):
    """Manche Windows-PCs öffnen die Verknüpfungen nicht: „[Errno 22] Invalid argument“ bei config.json."""
    repo = hf_cache_with_links(rating.model_folder())
    assert rating.rate([wav(tmp_path / "a.wav", 1)])[0] is not None
    for rev, name in (("alt", "config.json"), ("neu", "config.json"), ("neu", "model.safetensors")):
        path = os.path.join(repo, "snapshots", rev, name)
        assert os.path.isfile(path) and not os.path.islink(path)
    with open(os.path.join(repo, "snapshots", "alt", "config.json"), encoding="utf-8") as f:
        assert f.read() == '{"output_dim": 4}'
    with open(os.path.join(repo, "snapshots", "neu", "model.safetensors"), "rb") as f:
        assert f.read() == b"gewichte"
    # verschoben, nicht kopiert: die Gewichte liegen nur einmal da, und kein Verweis zeigt mehr ins Leere
    assert not os.path.exists(os.path.join(rating.model_folder(), "hub", "blobs", "ab", "abcd"))
    assert not os.path.lexists(os.path.join(repo, "blobs", "e5"))
    assert config.hf_without_links(rating.model_folder()) == 0             # danach ist nichts mehr zu tun


def test_the_model_is_loaded_as_real_files(tmp_path, fake_model):
    fake_model.write_text(FAKE_WORKER.replace('"CU": 5.0', '"CU": float(os.environ["HF_HUB_DISABLE_SYMLINKS"])'),
                          encoding="utf-8")
    assert rating.rate([wav(tmp_path / "a.wav", 1)])[0].usefulness == 1.0
    assert config.hf_without_links(str(tmp_path / "gibt-es-nicht")) == 0


@pytest.mark.parametrize("worker", ["rating_worker", "accompaniment_worker", "polish_worker"])
def test_workers_switch_links_off_in_older_huggingface_hub(worker, monkeypatch):
    """huggingface_hub vor 2.0 kennt HF_HUB_DISABLE_SYMLINKS nicht; dort schalten die Worker es selbst ab."""
    import importlib
    import types
    package, download = types.ModuleType("huggingface_hub"), types.ModuleType("huggingface_hub.file_download")
    download.are_symlinks_supported = lambda cache_dir=None: True
    package.file_download = download
    monkeypatch.setitem(sys.modules, "huggingface_hub", package)
    monkeypatch.setitem(sys.modules, "huggingface_hub.file_download", download)
    importlib.import_module(worker).without_links()
    assert download.are_symlinks_supported("tools") is False


def test_without_setup_nothing_is_rated(tmp_path):
    assert not rating.available()
    assert rating.rate([wav(tmp_path / "a.wav", 1)]) == [None]
    assert "setup_bewertung.py" in rating.status()


# ── Fassungen ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def rated_variants(tmp_path, monkeypatch):
    """Erzeugen ist nachgebaut: Fassung k ist 2, 5 oder 3 Sekunden lang, das nachgebaute Modell mag lange Fassungen.
    Mit Seed (pipeline.bring_back) entsteht dieselbe Fassung noch einmal."""
    out = str(tmp_path / "out")
    made = []

    def fake_song(settings, progress=None, seed=None, keep_history=True):
        made.append(settings)
        settings = settings.with_updates(seed=len(made) if settings.seed is None else settings.seed)
        os.makedirs(out, exist_ok=True)
        mix = wav(os.path.join(out, "final_mix.wav"), [2, 5, 3][(settings.seed - 1) % 3])   # überschreibt den Mix
        entry = history.record(mix, settings, out) if keep_history else None
        progress(1.0, "Fertig")
        return SongResult(seed=settings.seed, output_dir=out, mix_wav=mix, settings=settings,
                          history=entry.audio if entry else None)

    monkeypatch.setattr(pipeline, "generate_song", fake_song)
    monkeypatch.setattr(main, "generate_song", fake_song)
    return SongSettings(output_ordner=out)


def test_variants_get_a_rating_and_the_best_is_found(rated_variants, fake_model):
    steps = []
    results = generate_variants(rated_variants, 3, progress=lambda f, msg: steps.append((f, msg)))
    assert [r.rating.enjoyment for r in results] == [2.0, 5.0, 3.0]
    assert pipeline.best(results).seed == 2
    # die beste ist nicht die letzte: sie entsteht im Ausgabeordner noch einmal, Player und Export passen zu ihr
    assert sf.info(pipeline.best(results).mix_wav).duration == pytest.approx(5.0)
    assert pipeline.best(results).history and len(history.entries(rated_variants.output_ordner)) == 3
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
    assert "requests" in install                    # Audiobox importiert es, gibt es aber nicht als Abhängigkeit an
    commands.clear()
    assert setup_bewertung.setup(cpu=True)
    assert commands[-1][commands[-1].index("--torch-backend") + 1] == "cpu"


def test_setup_takes_the_python_of_the_setup_exe(monkeypatch, tmp_path):
    """Sonst sucht uv ein Python in AppData, wo Windows seine Verknüpfungen sperren kann (os error 448)."""
    commands = []
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: "/bin/uv")
    monkeypatch.setattr(setup_bewertung.subprocess, "run",
                        lambda cmd, **kw: commands.append(cmd) or type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(rating, "rate", lambda paths: [Rating(6.0, 5.0, 4.0, 7.0)])
    assert setup_bewertung.setup()
    assert commands[0][commands[0].index("--python") + 1] == "3.12"           # aus dem Quellcode gestartet
    python = tmp_path / "python" / "python.exe"
    python.parent.mkdir()
    python.write_text("")
    monkeypatch.setattr(config, "BUNDLED_PYTHON", str(python))
    commands.clear()
    assert setup_bewertung.setup()
    assert commands[0][commands[0].index("--python") + 1] == str(python)


def test_setup_needs_uv_and_a_working_model(monkeypatch):
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: None)
    assert not setup_bewertung.setup()
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: "/bin/uv")
    monkeypatch.setattr(setup_bewertung.subprocess, "run", lambda cmd, **kw: type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(rating, "rate", lambda paths: [None])
    assert not setup_bewertung.setup()


def test_an_update_tops_up_an_existing_environment(monkeypatch, tmp_path):
    """Die Setup.exe ruft nach jedem Update setup_bewertung.py --ergaenzen: Neue Pakete kommen dazu, ohne Modell-Probe."""
    commands = []
    monkeypatch.setattr(setup_bewertung.shutil, "which", lambda name: "/bin/uv")
    monkeypatch.setattr(setup_bewertung.subprocess, "run",
                        lambda cmd, **kw: commands.append(cmd) or type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(rating, "rate", lambda paths: pytest.fail("ergänzen lädt das Modell nicht"))
    assert setup_bewertung.ergaenzen() and commands == []                    # nicht eingerichtet: nichts zu tun
    python = tmp_path / "venv-python"
    python.write_text("")
    monkeypatch.setattr(rating, "python", lambda: str(python))
    os.makedirs(rating.FOLDER)
    with open(os.path.join(rating.FOLDER, rating.INCOMPLETE), "w") as f:
        f.write("requests")
    assert setup_bewertung.ergaenzen()
    [install] = commands
    assert install[1:3] == ["pip", "install"] and install[install.index("--python") + 1] == str(python)
    assert set(setup_bewertung.PAKETE) <= set(install) and "requests" in install
    assert rating.complete()
    monkeypatch.setattr(setup_bewertung.subprocess, "run", lambda cmd, **kw: type("Done", (), {"returncode": 1})())
    assert not setup_bewertung.ergaenzen()


def test_the_setup_exe_tops_up_the_rating():
    starter = open(os.path.join(config.REPO_ROOT, "Vloid Songs starten.bat"), encoding="utf-8").read()
    einrichten = starter[starter.index('if "%~1"=="--einrichten"'):starter.index("app.py")]
    assert "setup_bewertung.py --ergaenzen" in einrichten
    assert einrichten.index("sync --frozen") < einrichten.index("--ergaenzen") < einrichten.index("exit /b 0")

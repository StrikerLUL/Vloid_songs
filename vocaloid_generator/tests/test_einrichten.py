# test_einrichten.py – Einrichten aus der App, Systemcheck, Updates und die neuen Befehle in main.py
import io
import json
import os
import zipfile

import pytest

import config
import einrichten
import main
import pipeline
import systemcheck
import updates
from settings import SongSettings


# ── Einrichten ──────────────────────────────────────────────────────────────────
@pytest.fixture
def scripts(tmp_path, monkeypatch):
    """Zwei kleine Setup-Skripte: eines klappt und schreibt eine Datei, eines geht schief."""
    root = tmp_path / "programm"
    root.mkdir()
    (root / "setup_gut.py").write_text("import sys\nprint('lade', sys.argv[1:])\nopen('gut.txt', 'w').write('ok')\n")
    (root / "setup_schlecht.py").write_text("import sys\nprint('kaputt')\nsys.exit(4)\n")
    monkeypatch.setattr(config, "REPO_ROOT", str(root))
    monkeypatch.setattr(einrichten, "COMPONENTS", ())
    einrichten.register(einrichten.Component("gut", "Gut", "klappt", "1 MB", "setup_gut.py",
                                             lambda: (root / "gut.txt").exists(), args=("--schnell",)))
    einrichten.register(einrichten.Component("schlecht", "Schlecht", "geht schief", "1 MB", "setup_schlecht.py",
                                             lambda: False, recommended=False))
    einrichten.register(einrichten.Component("fehlt", "Fehlt", "kein Skript", "1 MB", "setup_fehlt.py",
                                             lambda: 1 / 0))
    return root


def test_install_runs_the_scripts_and_logs_their_output(scripts):
    assert [c.key for c in einrichten.missing()] == ["gut", "schlecht", "fehlt"]   # eine kaputte Prüfung: fehlt
    lines, steps = [], []
    results = einrichten.install(["gut", "schlecht", "fehlt"], lines.append, lambda f, m: steps.append(m))
    assert results == {"gut": True, "schlecht": False, "fehlt": False}
    assert any("lade ['--schnell']" in line for line in lines)
    assert any("kaputt" in line for line in lines)
    assert any("setup_fehlt.py fehlt" in line for line in lines)
    assert steps[0] == "Gut (1 von 3)" and steps[-1] == "Fertig"
    assert [c.key for c in einrichten.missing()] == ["schlecht", "fehlt"]
    log_text = open(einrichten.log_path(), encoding="utf-8").read()
    assert "── Gut ──" in log_text and "kaputt" in log_text


def test_wizard_is_done_once_finished():
    assert not einrichten.wizard_done()
    einrichten.mark_wizard_done()
    assert einrichten.wizard_done()
    einrichten.mark_wizard_done(False)
    assert not einrichten.wizard_done()


def test_every_component_has_its_script():
    for c in einrichten.COMPONENTS:
        assert os.path.isfile(os.path.join(config.REPO_ROOT, c.script)), c.script
    lines = einrichten.status_lines(SongSettings())
    assert "NEUTRINO" in lines[0] and len(lines) == len(einrichten.components()) + 1


def test_cli_installs_what_is_missing(scripts):
    assert main.main(["--einrichten", "gut"]) == 0
    assert (scripts / "gut.txt").exists()
    assert main.main(["--einrichten", "alles"]) == 1          # schlecht geht schief
    assert main.main(["--einrichten", "gibtsnicht"]) == 1


# ── Systemcheck ─────────────────────────────────────────────────────────────────
def test_checks_run_on_and_record_failures(monkeypatch):
    monkeypatch.setattr(systemcheck, "CHECKS", ())
    systemcheck.register("a", "Geht", lambda s, folder: (True, "gut"))
    systemcheck.register("b", "Fehlt", lambda s, folder: (None, "nicht eingerichtet"))
    systemcheck.register("c", "Kaputt", lambda s, folder: 1 / 0)
    systemcheck.register("d", "Langsam", lambda s, folder: (True, "ACE"), slow=True)
    systemcheck.register("x", "Vor b", lambda s, folder: (True, "x"), before="b")
    results = systemcheck.run_all(SongSettings())
    assert [r.key for r in results] == ["a", "x", "b", "c"]          # „Langsam“ nur bei gründlich
    assert [r.ok for r in results] == [True, True, None, False]
    assert "ZeroDivisionError" in results[3].message
    assert systemcheck.summary(results) == "1 Problem: Kaputt"
    when, loaded = systemcheck.load()
    assert [r.key for r in loaded] == ["a", "x", "b", "c"] and loaded[3].symbol == "✗"
    assert [r.key for r in systemcheck.run_all(SongSettings(), thorough=True, only=("d",))] == ["d"]
    assert systemcheck.summary(systemcheck.run_all(SongSettings(), only=("a", "b"))) == \
        "Alles läuft (nicht eingerichtet: Fehlt)"


def test_real_quick_checks_pass_here():
    results = systemcheck.run_all(SongSettings(), only=("space", "instruments", "mp3", "neutrino", "soundfonts",
                                                        "samples", "rating", "polish"), thorough=True)
    found = {r.key: r for r in results}
    assert config.DATA_DIR in found["space"].message          # ob genug Platz ist, hängt vom Rechner ab
    assert found["instruments"].ok, found["instruments"].message
    assert found["neutrino"].ok is None and found["rating"].ok is None and found["polish"].ok is None


def test_song_check_makes_a_short_song(monkeypatch):
    monkeypatch.setattr(pipeline, "_sing_preview", lambda *a, **k: False)    # keine Sprachausgabe in der CI
    ok, message = systemcheck.check_song(SongSettings(neutrino_pfad="fehlt"), "")
    assert ok and "ohne Gesang" in message
    assert os.path.isdir(os.path.join(config.DATA_DIR, systemcheck.FOLDER))


def test_cli_system_check(monkeypatch):
    monkeypatch.setattr(systemcheck, "CHECKS", ())
    systemcheck.register("a", "Geht", lambda s, folder: (True, "gut"))
    assert main.main(["--system-pruefen"]) == 0
    systemcheck.register("b", "Kaputt", lambda s, folder: (False, "nein"))
    assert main.main(["--system-pruefen"]) == 1


def test_cli_error_report(tmp_path):
    target = tmp_path / "bericht.zip"
    assert main.main(["--fehlerbericht", str(target)]) == 0
    with zipfile.ZipFile(target) as z:
        assert "system.txt" in z.namelist()


# ── Updates ─────────────────────────────────────────────────────────────────────
def test_versions_compare_as_numbers():
    assert updates.parse_version("v1.10.0") == (1, 10, 0)
    assert updates.newer("v1.10.0", "1.9.3") and not updates.newer("1.0.0", "1.0.0")
    assert not updates.newer("kaputt", "0.1.0")


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_latest_release_is_read_and_cached(monkeypatch):
    asked = []
    release = {"tag_name": "v9.0.0", "body": "## Neu\n- alles", "html_url": "https://example.org/r",
               "assets": [{"name": "notes.txt", "browser_download_url": "x"},
                          {"name": "VloidSongs-Setup-9.0.0.exe", "browser_download_url": "https://example.org/s.exe"}]}

    def urlopen(request, timeout=None):
        asked.append(request.full_url)
        return Answer(json.dumps(release).encode())
    monkeypatch.setattr(updates.urllib.request, "urlopen", urlopen)
    found = updates.available(force=True)
    assert found.version == "v9.0.0" and found.setup_url == "https://example.org/s.exe"
    assert updates.latest().version == "v9.0.0" and len(asked) == 1      # einmal am Tag reicht

    def offline(request, timeout=None):
        raise OSError("kein Netz")
    monkeypatch.setattr(updates.urllib.request, "urlopen", offline)
    assert updates.latest(force=True).version == "v9.0.0"              # ohne Netz: das Gemerkte
    os.remove(os.path.join(config.DATA_DIR, updates.CACHE_FILE))
    assert updates.latest(force=True) is None


def test_whats_new_comes_from_the_changelog(tmp_path, monkeypatch):
    log = tmp_path / "CHANGELOG.md"
    log.write_text("# Änderungen\n\n## 1.0.0 – 2026-10-14\n\n- Installer\n- Drums\n\n## 0.2.0\n\n- alt\n",
                   encoding="utf-8")
    assert updates.changes("1.0.0", str(log)) == "- Installer\n- Drums"
    assert updates.changes("0.2.0", str(log)) == "- alt"
    assert updates.changes("3.0.0", str(log)) == ""


def test_whats_new_shows_once_per_version_and_not_on_first_start(monkeypatch):
    import settings
    monkeypatch.setattr(updates, "changes", lambda version=updates.VERSION, path=None: "- neu")
    seen = os.path.join(config.DATA_DIR, updates.SEEN_FILE)
    if os.path.exists(seen):
        os.remove(seen)
    assert updates.unseen_changes() == ""              # allererster Start: keine Einstellungen da
    os.remove(seen)
    SongSettings().save()
    assert os.path.exists(settings.SETTINGS_PATH)
    assert updates.unseen_changes() == "- neu"         # nach dem Update auf diese Version
    assert updates.unseen_changes() == ""              # aber nur einmal
    with open(seen, "w") as f:
        f.write("0.0.1")
    assert updates.unseen_changes() == "- neu"


def test_changelog_has_this_version():
    assert updates.changes(), "CHANGELOG.md braucht einen Abschnitt für die aktuelle Version"


def test_every_help_page_exists_and_this_version_has_its_news():
    from version import VERSION
    for name in ("ANLEITUNG.md", "FEHLERBEHEBUNG.md", "TESTLISTE.md", "CREDITS.md", "CHANGELOG.md"):
        assert os.path.isfile(os.path.join(config.REPO_ROOT, name)), name
    assert updates.changes(VERSION)
    assert updates.parse_version(VERSION) >= (1, 0, 0)

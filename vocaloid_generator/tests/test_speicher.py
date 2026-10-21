# test_speicher.py – Platz auf der Festplatte: Bausteine, Songs, Projekte, Zwischenspeicher (v6 Nr. 18)
import os
from types import SimpleNamespace

import pytest

import config
import history
import project
import reference
import speicher


def fill(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * n)


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", str(tmp_path))
    folders = {"soundfonts": str(tmp_path / "tools" / "soundfonts"), "grooves": str(tmp_path / "tools" / "grooves"),
               "rating": str(tmp_path / "tools" / "bewertung")}
    monkeypatch.setattr(speicher, "_folders", lambda: folders)
    fill(os.path.join(folders["soundfonts"], "a.sf2"), 3000)
    fill(os.path.join(folders["soundfonts"], "sub", "b.sf2"), 2000)
    fill(os.path.join(folders["grooves"], "g.mid"), 500)
    return folders


def test_each_installed_part_shows_its_size_and_can_be_removed(tools, tmp_path):
    found = {u.key: u.bytes for u in speicher.components()}
    assert found == {"soundfonts": 5000, "grooves": 500}          # ohne Ordner kein Eintrag
    assert speicher.remove("soundfonts") == 5000 and not os.path.exists(tools["soundfonts"])
    assert speicher.remove("soundfonts") == 0
    tools["grooves"] = str(tmp_path / "anderswo")
    fill(os.path.join(tools["grooves"], "g.mid"), 10)
    with pytest.raises(ValueError):
        speicher.remove("grooves")                                # nur Ordner unter tools
    assert os.path.exists(tools["grooves"])


def test_caches_are_cleared_but_the_current_log_stays():
    fill(reference.CACHE, 100)
    fill(os.path.join(config.LOG_DIR, "vloid_songs.log"), 50)
    fill(os.path.join(config.LOG_DIR, "vloid_songs.log.1"), 70)
    fill(os.path.join(config.DATA_DIR, "Fehlerberichte", "f.zip"), 30)
    assert sorted(os.path.basename(p) for p in speicher.caches()) == \
        sorted(["Fehlerberichte", os.path.basename(reference.CACHE), "vloid_songs.log.1"])
    assert speicher.clear_caches() == 200
    assert speicher.caches() == [] and os.path.exists(os.path.join(config.LOG_DIR, "vloid_songs.log"))


def test_projects_can_go_while_the_songs_stay(tmp_path, monkeypatch):
    out = str(tmp_path / "songs")
    entries = []
    for name, kept in (("a", False), ("b", True), ("c", False)):
        audio = os.path.join(out, "verlauf", f"{name}.mp3")
        fill(audio, 1000)
        fill(os.path.join(project.folder(audio), project.FILE), 10)
        fill(os.path.join(project.folder(audio), "vocals.flac"), 4000)
        entries.append(SimpleNamespace(audio=audio, kept=kept))
    monkeypatch.setattr(history, "entries", lambda folder: entries)
    total, projects, count = speicher.songs(out)
    assert (total, projects, count) == (3 * 5010, 3 * 4010, 3)
    assert speicher.drop_projects(out) == 2 * 4010
    assert [project.available(e.audio) for e in entries] == [False, True, False]   # der Favorit behält seins
    assert all(os.path.exists(e.audio) for e in entries)
    assert speicher.drop_projects(out, keep_favorites=False) == 4010


def test_sizes_read_like_the_explorer():
    assert speicher.describe(None) == "…" and speicher.describe(0) == "0 KB" and speicher.describe(1500) == "2 KB"
    assert speicher.describe(350_000_000) == "350 MB" and speicher.describe(1_234_000_000) == "1,2 GB"
    assert speicher.describe(20_400_000_000) == "20 GB" and speicher.describe(5_500_000) == "5,5 MB"


def test_every_part_from_the_setup_has_its_folder():
    """Was sich einrichten lässt, zeigt die Speicher-Übersicht auch an und lässt sich dort entfernen (auch Surge XT
    und die Verstärker-Modelle aus 1.3.0)."""
    import einrichten
    assert {c.key for c in einrichten.COMPONENTS} == set(speicher._folders())

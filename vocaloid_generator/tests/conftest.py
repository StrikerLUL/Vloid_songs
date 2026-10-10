# conftest.py – gemeinsame Test-Einrichtung
import os
import sys

import pytest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Tests lesen und schreiben nie die echten Einstellungen der App."""
    import settings
    monkeypatch.setattr(settings, "SETTINGS_PATH", str(tmp_path / "user_settings.json"))
    monkeypatch.setattr(settings, "LEGACY_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture(scope="session")
def jpop_song(tmp_path_factory):
    """Ein kompletter J-Pop-Song mit Drop und Tonartwechsel, fest gesät."""
    import config
    from orchestrator import orchestrate_song
    from pipeline import seed_everything
    from song_helpers import Song, TEST_STRUCTURE

    out = tmp_path_factory.mktemp("jpop")
    seed_everything(1234)
    tracks = orchestrate_song(
        genre="J-Pop", bpm=160, structure=TEST_STRUCTURE, key="B", mode="minor",
        section_config=config.SECTION_CONFIG, output_dir=str(out),
    )
    return Song(tracks=tracks, structure=TEST_STRUCTURE, bpm=160, key="B", mode="minor", output_dir=str(out))

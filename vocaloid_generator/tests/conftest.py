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


@pytest.fixture(autouse=True)
def without_sound_library(tmp_path, monkeypatch):
    """Tests klingen gleich, ob setup_soundfonts.py und setup_samples.py gelaufen sind oder nicht: ohne beides."""
    import sample_library
    import sound_library
    monkeypatch.setattr(sound_library, "FOLDER", str(tmp_path / "soundfonts"))
    monkeypatch.setattr(sample_library, "FOLDER", str(tmp_path / "samples"))


@pytest.fixture(autouse=True)
def isolated_motifs(tmp_path, monkeypatch):
    """MIDI-Dateien im echten Motiv-Ordner ändern die Melodien der Tests nicht."""
    import motifs
    monkeypatch.setattr(motifs, "FOLDER", str(tmp_path / "motive"))


@pytest.fixture(autouse=True)
def without_rating(tmp_path, monkeypatch):
    """Eine eingerichtete Bewertung (setup_bewertung.py) bewertet in den Tests nicht mit."""
    import rating
    monkeypatch.setattr(rating, "FOLDER", str(tmp_path / "bewertung"))


@pytest.fixture(autouse=True)
def without_polish(tmp_path, monkeypatch):
    """Ein eingerichteter Klang-Veredler (setup_ace_step.py) veredelt in den Tests nicht mit."""
    import polish
    monkeypatch.setattr(polish, "FOLDER", str(tmp_path / "ace-step"))


@pytest.fixture(autouse=True)
def isolated_references(tmp_path, monkeypatch):
    """Vorbild-Bibliothek und Messungen liegen im Testordner, nie bei den echten Songs."""
    import reference
    monkeypatch.setattr(reference, "LIBRARY", str(tmp_path / "vorbilder"))
    monkeypatch.setattr(reference, "CACHE", str(tmp_path / "vorbild_messungen.json"))


@pytest.fixture(autouse=True)
def without_voicevox(monkeypatch):
    """Ein VOICEVOX, das zufällig auf dem Rechner läuft, singt in den Tests nicht mit."""
    import voicevox
    monkeypatch.setattr(voicevox, "running", lambda url=None, timeout=None: False)


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


@pytest.fixture(autouse=True)
def without_surge(monkeypatch):
    """Ein installiertes Surge XT taucht in den Tests nicht auf."""
    import vst_sounds
    monkeypatch.setattr(vst_sounds, "_surge_candidates", lambda: ())

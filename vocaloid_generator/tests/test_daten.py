# test_daten.py – Der Datenordner: wo Songs und Einstellungen liegen und der Umzug aus dem Programmordner
import json
import os

import pytest

import config
import userdata


@pytest.fixture
def places(tmp_path, monkeypatch):
    """Ein alter Programmordner und ein leerer Dokumente-Ordner, beide im Testordner."""
    program = tmp_path / "Vloid_songs" / "vocaloid_generator"
    program.mkdir(parents=True)
    documents = tmp_path / "Dokumente" / "Vloid Songs"
    monkeypatch.setattr(config, "BASE_DIR", str(program))
    monkeypatch.setattr(config, "default_data_dir", lambda: str(documents))
    return program, documents


def test_data_dir_follows_env_choice_and_default(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_ENV, str(tmp_path / "eigener"))
    assert config.data_dir() == str(tmp_path / "eigener")
    monkeypatch.delenv(config.DATA_ENV)
    choice = tmp_path / "datenordner.txt"
    monkeypatch.setattr(config, "DATA_CHOICE", str(choice))
    assert config.data_dir() == config.default_data_dir()
    assert config.default_data_dir().endswith("Vloid Songs")
    choice.write_text("programmordner\n")
    assert config.data_dir() == config.BASE_DIR
    choice.write_text(str(tmp_path / "stick"))
    assert config.data_dir() == str(tmp_path / "stick")


def test_the_tests_never_touch_the_real_data_folder():
    assert config.data_dir() == os.path.abspath(os.environ[config.DATA_ENV])
    assert config.OUTPUT_ORDNER.startswith(config.data_dir())
    import settings
    assert not settings.SETTINGS_PATH.startswith(config.default_data_dir())


def test_migrate_moves_old_data_into_the_documents_folder(places):
    program, documents = places
    (program / "output" / "verlauf").mkdir(parents=True)
    (program / "output" / "verlauf" / "song.mp3").write_bytes(b"mp3")
    (program / "vorlagen").mkdir()
    (program / "vorlagen" / "Rock.json").write_text("{}")
    (program / "user_settings.json").write_text(json.dumps({
        "bpm": 99, "output_ordner": str(program / "output"),
        "reference_folder": str(program / "vorbilder"), "neutrino_pfad": "C:/NEUTRINO"}))
    moved = userdata.migrate(str(documents))
    assert (documents / "Songs" / "verlauf" / "song.mp3").read_bytes() == b"mp3"
    assert (documents / "Vorlagen" / "Rock.json").exists()
    assert not (program / "output").exists() and not (program / "user_settings.json").exists()
    assert str(documents / "Songs") in moved
    data = json.loads((documents / "Einstellungen.json").read_text())
    assert data["bpm"] == 99
    assert data["output_ordner"] == ""                              # der Standard: Songs im Datenordner
    assert data["reference_folder"] == str(documents / "Vorbilder")  # zeigt jetzt auf den neuen Ort
    assert data["neutrino_pfad"] == "C:/NEUTRINO"                   # alles andere bleibt


def test_migrate_merges_and_never_overwrites(places):
    program, documents = places
    (documents / "Songs").mkdir(parents=True)
    (documents / "Songs" / "neu.mp3").write_bytes(b"neu")
    (documents / "Einstellungen.json").write_text('{"bpm": 150}')
    (program / "output").mkdir()
    (program / "output" / "neu.mp3").write_bytes(b"alt")
    (program / "output" / "alt.mp3").write_bytes(b"alt")
    (program / "user_settings.json").write_text('{"bpm": 99}')
    userdata.migrate(str(documents))
    assert (documents / "Songs" / "neu.mp3").read_bytes() == b"neu"
    assert (documents / "Songs" / "alt.mp3").read_bytes() == b"alt"
    assert json.loads((documents / "Einstellungen.json").read_text())["bpm"] == 150
    assert (program / "output" / "neu.mp3").exists()            # was nicht umziehen konnte, bleibt liegen
    assert userdata.migrate(str(documents)) == []                # ein zweiter Start ändert nichts


def test_migrate_back_into_the_program_folder(places):
    program, documents = places
    (documents / "Songs").mkdir(parents=True)
    (documents / "Songs" / "a.mp3").write_bytes(b"a")
    userdata.migrate(str(program))
    assert (program / "Songs" / "a.mp3").exists() and not (documents / "Songs").exists()


def test_migrate_does_nothing_when_the_folder_is_set_by_env(places, monkeypatch):
    program, documents = places
    (program / "output").mkdir()
    assert userdata.migrate() == []
    assert (program / "output").exists()


def test_import_from_an_old_program_folder(places, tmp_path):
    program, documents = places
    old = tmp_path / "Downloads" / "Vloid_songs-main"
    (old / "vocaloid_generator" / "output").mkdir(parents=True)
    (old / "vocaloid_generator" / "output" / "s.mp3").write_bytes(b"s")
    (old / "vocaloid_generator" / "user_settings.json").write_text(
        json.dumps({"output_ordner": str(old / "vocaloid_generator" / "output"),
                    "neutrino_pfad": str(old / "NEUTRINO-windows-v3.1")}))
    (old / "NEUTRINO-windows-v3.1" / "bin").mkdir(parents=True)
    (old / "tools" / "samples").mkdir(parents=True)
    (old / "tools" / "samples" / "x.flac").write_bytes(b"x")
    new_program = tmp_path / "Programs" / "Vloid Songs"
    new_program.mkdir(parents=True)
    moved = userdata.import_from(str(old / "vocaloid_generator"), str(documents), str(new_program))
    assert (documents / "Songs" / "s.mp3").exists()
    assert (new_program / "NEUTRINO-windows-v3.1" / "bin").is_dir()
    assert (new_program / "tools" / "samples" / "x.flac").exists()
    assert len(moved) == 4
    data = json.loads((documents / "Einstellungen.json").read_text())
    assert data["output_ordner"] == ""
    assert data["neutrino_pfad"] == str(new_program / "NEUTRINO-windows-v3.1")


def test_choose_program_folder_is_remembered(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_CHOICE", str(tmp_path / "datenordner.txt"))
    assert not userdata.in_program_folder()
    userdata.choose_program_folder(True)
    assert userdata.in_program_folder()
    userdata.choose_program_folder(False)
    assert not userdata.in_program_folder() and not (tmp_path / "datenordner.txt").exists()

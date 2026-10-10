# test_settings.py – Einstellungs-Modell: Prüfung, altes Format, Laden und Speichern
import json
import os

import pytest
from pydantic import ValidationError

import config
import settings
from settings import CHANNELS, SongSettings

REPO_SETTINGS = os.path.join(config.BASE_DIR, "settings.json")


def test_defaults_are_valid_and_complete():
    s = SongSettings()
    assert set(s.channels) == set(CHANNELS)
    assert s.channels["drums"].volume == 1.0
    assert all(sec in config.SECTION_CONFIG for sec in s.active_sections)


def test_flat_keys_are_written_with_sharps():
    assert SongSettings(key="Bb").key == "A#"
    assert SongSettings(key="Eb").key == "D#"


@pytest.mark.parametrize("field,value", [
    ("key", "H"), ("bpm", 10), ("bpm", 999), ("scale", "lydian"),
    ("active_sections", ["Verse", "Gibtsnicht"]), ("swing", 2.0), ("seed", -1),
])
def test_invalid_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        SongSettings(**{field: value})


def test_channel_values_are_checked():
    with pytest.raises(ValidationError):
        SongSettings(channels={"piano": {"volume": 5.0}})


def test_partial_channels_are_completed_with_defaults():
    s = SongSettings(channels={"bass": {"volume": 0.5}})
    assert s.channels["bass"].volume == 0.5
    assert s.channels["bass"].pan == 0.0
    assert s.channels["piano"].pan == -0.25


def test_with_updates_returns_a_checked_copy():
    s = SongSettings()
    t = s.with_updates(bpm=100, key="Db")
    assert (t.bpm, t.key) == (100, "C#")
    assert s.bpm == 160
    with pytest.raises(ValidationError):
        s.with_updates(bpm=1000)


def test_flat_format_round_trip():
    s = SongSettings(bpm=99, channels={"guitar": {"mute": True, "style": "power_chords"}})
    flat = s.to_flat()
    assert flat["mute_guitar"] is True and flat["style_guitar"] == "power_chords"
    assert "style_vocals" not in flat
    assert SongSettings.from_flat(flat) == s


def test_repo_settings_file_loads_completely(caplog):
    s = SongSettings.load(REPO_SETTINGS)
    assert "Ungültige" not in caplog.text
    with open(REPO_SETTINGS, encoding="utf-8") as f:
        flat = json.load(f)
    assert s.bpm == flat["bpm"]
    assert s.channels["guitar"].pan == flat["pan_guitar"]


def test_save_and_load_round_trip(tmp_path):
    s = SongSettings(bpm=128, style="Rock", seed=42, channels={"drums": {"solo": True}})
    s.save()
    assert os.path.exists(settings.SETTINGS_PATH)
    assert SongSettings.load() == s


def test_load_prefers_new_file_over_legacy(tmp_path):
    with open(settings.LEGACY_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"bpm": 90, "volume_bass": 0.3}, f)
    assert SongSettings.load().bpm == 90
    assert SongSettings.load().channels["bass"].volume == 0.3

    SongSettings(bpm=111).save()
    assert SongSettings.load().bpm == 111


def test_broken_file_gives_defaults(tmp_path):
    path = tmp_path / "kaputt.json"
    path.write_text("{ nicht json", encoding="utf-8")
    assert SongSettings.load(str(path)) == SongSettings()


def test_invalid_values_in_file_fall_back_individually(tmp_path, caplog):
    path = tmp_path / "alt.json"
    path.write_text(json.dumps({"bpm": 5000, "key": "D", "style": "Rock"}), encoding="utf-8")
    s = SongSettings.load(str(path))
    assert (s.bpm, s.key, s.style) == (160, "D", "Rock")
    assert "bpm" in caplog.text


def test_missing_paths_fall_back_to_defaults(tmp_path):
    s = SongSettings(
        output_ordner=r"C:\Users\jemand\gibtsnicht\output",
        soundfont_pfad=str(tmp_path / "fehlt.sf2"),
        neutrino_pfad=str(tmp_path / "fehlt"),
    )
    assert s.output_dir() == config.OUTPUT_ORDNER
    assert s.soundfont_file() == config.SOUNDFONT_PFAD
    assert s.neutrino_dir() == config.NEUTRINO_PFAD


def test_existing_paths_are_used(tmp_path):
    sf2 = tmp_path / "eigener.sf2"
    sf2.write_bytes(b"")
    out = tmp_path / "neu"  # existiert noch nicht, der Elternordner aber schon
    s = SongSettings(output_ordner=str(out), soundfont_pfad=str(sf2), neutrino_pfad=str(tmp_path))
    assert s.output_dir() == str(out)
    assert s.soundfont_file() == str(sf2)
    assert s.neutrino_dir() == str(tmp_path)


def test_instrument_styles_cover_all_instruments():
    styles = SongSettings(channels={"bass": {"style": "lazy"}}).instrument_styles()
    assert styles["bass"] == "lazy"
    assert set(styles) == set(settings.INSTRUMENTS)

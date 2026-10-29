# test_speicher_160.py – Arbeitsdateien außerhalb von OneDrive, Warnung bei wenig Platz (1.6.0)
import json
import os
import shutil
from collections import namedtuple

import pytest

import history
import speicher
import systemcheck
from settings import SongSettings


@pytest.fixture
def onedrive(tmp_path, monkeypatch):
    """Ein Ausgabeordner in OneDrive und ein Arbeitsordner auf dem Rechner (wie %LOCALAPPDATA%)."""
    monkeypatch.setenv(speicher.LOCAL_ENV, str(tmp_path / "lokal"))
    monkeypatch.setattr(speicher, "_earlier", {})
    for var in speicher.CLOUD_ENV:
        monkeypatch.delenv(var, raising=False)
    songs = tmp_path / "OneDrive" / "Dokumente" / "Vloid Songs" / "Songs"
    songs.mkdir(parents=True)
    return str(songs)


def test_sync_folders_are_recognised(tmp_path, monkeypatch):
    for var in speicher.CLOUD_ENV:
        monkeypatch.delenv(var, raising=False)
    assert speicher.cloud(str(tmp_path / "OneDrive" / "Dokumente")) == "OneDrive"
    assert speicher.cloud(str(tmp_path / "OneDrive - Firma GmbH" / "Musik")) == "OneDrive"
    assert speicher.cloud(str(tmp_path / "Dropbox" / "Songs")) == "Dropbox"
    assert speicher.cloud(str(tmp_path / "Musik" / "OneDrive-Ideen")) == ""
    monkeypatch.setenv("OneDrive", str(tmp_path / "Wolke"))
    assert speicher.cloud(str(tmp_path / "Wolke" / "Dokumente")) == "OneDrive"
    assert speicher.cloud(str(tmp_path / "Wolken")) == ""


def test_with_local_cache_the_work_moves_out_of_onedrive_and_the_old_history_stays(onedrive, tmp_path):
    old = SongSettings(output_ordner=onedrive, local_cache=False, seed=7, style="Rock")
    assert old.output_dir() == onedrive
    mp3 = os.path.join(onedrive, "alt.mp3")
    open(mp3, "wb").write(b"ID3")
    history.record(mp3, old, onedrive)
    s = SongSettings(output_ordner=onedrive, seed=8)
    work = s.output_dir()
    assert work == str(tmp_path / "lokal" / "Songs") and os.path.isdir(work)
    assert speicher.cloud(work) == ""
    assert [e.settings.seed for e in history.entries(work)] == [7]           # der alte Verlauf bleibt sichtbar
    new = os.path.join(work, "neu.mp3")
    open(new, "wb").write(b"ID3")
    entry = history.record(new, s, work)
    assert sorted(e.settings.seed for e in history.entries(work)) == [7, 8]
    copy = speicher.cloud_copy(work, entry.audio)
    assert copy == os.path.join(onedrive, speicher.SHARED, os.path.basename(entry.audio)) and os.path.isfile(copy)
    assert "liegt in OneDrive" in speicher.where(s)
    os.makedirs(os.path.join(onedrive, "_gesungen"))
    assert os.path.join(onedrive, "_gesungen") in speicher.caches()


def test_a_song_lands_outside_onedrive_and_its_mp3_inside(onedrive, monkeypatch):
    import pipeline
    import qualitaet
    s = qualitaet.apply(SongSettings(output_ordner=onedrive, seed=3, active_sections=["Chorus"]), "Schnell")
    s.channels["vocals"].enabled = False        # ohne Gesang (die Vorschau-Stimme hängt in der Windows-CI)
    result = pipeline.generate_song(s, seed=3)
    assert result.output_dir == s.output_dir() != onedrive
    assert os.path.isfile(result.mix_wav) and not os.path.exists(os.path.join(onedrive, "final_mix.wav"))
    shared = os.listdir(os.path.join(onedrive, speicher.SHARED))
    assert len(shared) == 1 and os.path.basename(result.history) == shared[0]


def test_little_free_space_warns(tmp_path, monkeypatch):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage(100e9, 97e9, 3e9))
    assert "Nur noch 3,0 GB frei" in speicher.low_space(str(tmp_path / "gibt es noch nicht" / "Songs"))
    ok, text = systemcheck.check_space(SongSettings(output_ordner=str(tmp_path)), str(tmp_path))
    assert not ok and text.startswith("Wenig Platz")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage(100e9, 50e9, 50e9))
    assert speicher.low_space(str(tmp_path)) == ""


def test_without_onedrive_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(speicher, "_earlier", {})
    s = SongSettings(output_ordner=str(tmp_path))
    assert s.output_dir() == str(tmp_path) and speicher.where(s) == ""
    assert speicher.cloud_copy(str(tmp_path), str(tmp_path / "x.mp3")) is None
    json.dumps(speicher._earlier)

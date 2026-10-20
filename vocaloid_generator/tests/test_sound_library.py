# test_sound_library.py – zusätzliche SoundFonts für einzelne Instrumente und ihr Download
import hashlib
import os
import shutil
import sys

import numpy as np
import pretty_midi
import pytest

import config
import renderer
import sound_library
from renderer import render_midi
from sound_library import Sound

sys.path.insert(0, config.REPO_ROOT)
import setup_soundfonts  # noqa: E402

ENGINES = ["tinysoundfont"] + (["fluidsynth"] if renderer._fluidsynth() else [])
MAIN = os.path.basename(config.SOUNDFONT_PFAD)


def midi_with(program=0, is_drum=False, pitches=(60, 64, 67), pans=(None,)):
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    for pan in pans:
        inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
        for i, p in enumerate(pitches):
            inst.notes.append(pretty_midi.Note(velocity=100, pitch=p, start=i * 0.25, end=i * 0.25 + 0.5))
        if pan is not None:
            inst.control_changes.append(pretty_midi.ControlChange(10, pan, 0.0))
        pm.instruments.append(inst)
    return pm


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Eine Klangbibliothek, deren einziger SoundFont eine Kopie des Haupt-SoundFonts ist."""
    folder = tmp_path / "lib"
    folder.mkdir()
    shutil.copy(config.SOUNDFONT_PFAD, folder / MAIN)
    monkeypatch.setattr(sound_library, "FOLDER", str(folder))
    return folder


def test_missing_files_leave_the_main_soundfont_in_charge():
    assert sound_library.installed() == []
    assert sound_library.find(0) is None and sound_library.find(16, is_drum=True) is None


def test_every_mapped_sound_names_a_downloaded_file():
    files = {d.datei for d in setup_soundfonts.DOWNLOADS}
    sounds = list(sound_library.PROGRAMS.values()) + list(sound_library.KITS.values())
    assert {s.file for s in sounds} == files


@pytest.mark.parametrize("engine", ENGINES)
def test_a_program_plays_from_its_library_sound(library, monkeypatch, engine):
    # Programm 29 (verzerrte Gitarre) klingt mit der Bibliothek wie Preset 0 (Flügel)
    monkeypatch.setattr(sound_library, "PROGRAMS", {29: Sound(MAIN, 0)})
    piano = render_midi(midi_with(0), config.SOUNDFONT_PFAD, engine=engine, library=False)
    mapped = render_midi(midi_with(29), config.SOUNDFONT_PFAD, engine=engine)
    plain = render_midi(midi_with(29), config.SOUNDFONT_PFAD, engine=engine, library=False)
    assert np.allclose(mapped, piano, atol=1e-5)
    assert not np.allclose(plain, piano, atol=1e-3)


@pytest.mark.parametrize("engine", ENGINES)
def test_kits_remap_their_drum_notes(library, monkeypatch, engine):
    monkeypatch.setattr(sound_library, "KITS", {16: Sound(MAIN, 0, bank=128, notes={50: 45})})
    remapped = render_midi(midi_with(16, True, (50,)), config.SOUNDFONT_PFAD, engine=engine)
    low_tom = render_midi(midi_with(0, True, (45,)), config.SOUNDFONT_PFAD, engine=engine, library=False)
    assert np.allclose(remapped, low_tom, atol=1e-5)


def test_notes_outside_the_sampled_range_move_by_octaves():
    guitar = Sound("x.sf2", low=35, high=86)
    assert guitar.pitch(28) == 40 and guitar.pitch(90) == 78 and guitar.pitch(60) == 60


@pytest.mark.parametrize("engine", ENGINES)
def test_own_pan_spreads_double_tracked_guitars(library, monkeypatch, engine):
    monkeypatch.setattr(sound_library, "PROGRAMS", {29: Sound(MAIN, 29, own_pan=True)})
    left = render_midi(midi_with(29, pitches=(40, 47, 52), pans=(22,)), config.SOUNDFONT_PFAD, engine=engine)
    both = render_midi(midi_with(29, pitches=(40, 47, 52), pans=(22, 106)), config.SOUNDFONT_PFAD, engine=engine)
    l, r = np.sqrt(np.mean(left ** 2, axis=1))
    assert l > 3 * r
    l, r = np.sqrt(np.mean(both ** 2, axis=1))
    assert 0.8 < l / r < 1.25


def test_sf3_only_with_fluidsynth(library, monkeypatch):
    os.rename(library / MAIN, library / "x.sf3")
    monkeypatch.setattr(sound_library, "PROGRAMS", {0: Sound("x.sf3", 0)})
    assert sound_library.find(0) is not None
    assert sound_library.find(0, sf3=False) is None


# ── setup_soundfonts.py ──────────────────────────────────────────────────────────
def _download(path, datei, archiv=False, sha=None):
    data = open(path, "rb").read()
    return setup_soundfonts.Download(datei, path.as_uri(), sha or hashlib.sha256(data).hexdigest(), 1, "CC0",
                                     archiv=archiv)


def test_download_checks_the_checksum(tmp_path):
    src = tmp_path / "quelle.sf2"
    src.write_bytes(b"RIFF" + bytes(100))
    ziel = tmp_path / "soundfonts"
    assert setup_soundfonts.hole(_download(src, "gut.sf2"), str(ziel))
    assert (ziel / "gut.sf2").read_bytes() == src.read_bytes()
    assert not setup_soundfonts.hole(_download(src, "falsch.sf2", sha="0" * 64), str(ziel))
    assert sorted(os.listdir(ziel)) == ["gut.sf2"]


def test_a_dropped_connection_is_tried_again(tmp_path, monkeypatch):
    """Bricht die Verbindung ab, lädt das Skript noch einmal, statt die Datei gleich aufzugeben."""
    import urllib.request
    src = tmp_path / "quelle.sf2"
    src.write_bytes(b"RIFF" + bytes(100))
    real, calls = urllib.request.urlopen, []

    def flaky(url, timeout=None):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionResetError("Verbindung getrennt")
        return real(url, timeout=timeout)

    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    ziel = tmp_path / "soundfonts"
    assert setup_soundfonts.hole(_download(src, "gut.sf2"), str(ziel))
    assert len(calls) == 2 and (ziel / "gut.sf2").read_bytes() == src.read_bytes()


def test_download_unpacks_the_soundfont_from_a_7z_archive(tmp_path):
    import py7zr
    inner = tmp_path / "Gitarre 2020.sf2"
    inner.write_bytes(b"RIFF" + bytes(50))
    archiv = tmp_path / "gitarre.7z"
    with py7zr.SevenZipFile(archiv, "w") as z:
        z.write(inner, "Gitarre-SF2/Gitarre 2020.sf2")
        z.writestr(b"Lizenz", "Gitarre-SF2/LICENSE.txt")
    ziel = tmp_path / "soundfonts"
    assert setup_soundfonts.hole(_download(archiv, "Gitarre 2020.sf2", archiv=True), str(ziel))
    assert sorted(os.listdir(ziel)) == ["Gitarre 2020.sf2"]
    assert (ziel / "Gitarre 2020.sf2").read_bytes() == inner.read_bytes()

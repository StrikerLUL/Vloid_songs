# conftest.py – gemeinsame Test-Einrichtung
import atexit
import os
import shutil
import sys
import tempfile

import pytest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
# Vor jedem Import der App: die Tests schreiben nie in den echten Datenordner (Dokumente\Vloid Songs)
os.environ["VLOID_DATEN"] = tempfile.mkdtemp(prefix="vloid-test-daten-")
atexit.register(shutil.rmtree, os.environ["VLOID_DATEN"], ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Jeder Test hat seinen eigenen Datenordner: Vermerke wie „Assistent fertig“ gelten nicht für den nächsten."""
    import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "daten"))
    monkeypatch.setattr(config, "LOG_DIR", str(tmp_path / "daten" / "Protokolle"))


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Tests lesen und schreiben nie die echten Einstellungen der App."""
    import settings
    monkeypatch.setattr(settings, "SETTINGS_PATH", str(tmp_path / "user_settings.json"))
    monkeypatch.setattr(settings, "LEGACY_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture(autouse=True)
def without_sound_library(tmp_path, monkeypatch):
    """Tests klingen gleich, ob die Setup-Skripte (Klänge, Aufnahmen, Band, Schlagzeug, Grooves) gelaufen sind: ohne
    alles."""
    import band_library
    import drum_kit
    import grooves
    import sample_library
    import sound_library
    monkeypatch.setattr(sound_library, "FOLDER", str(tmp_path / "soundfonts"))
    monkeypatch.setattr(band_library, "FOLDER", str(tmp_path / "band"))
    monkeypatch.setattr(sample_library, "FOLDER", str(tmp_path / "samples"))
    monkeypatch.setattr(drum_kit, "FOLDER", str(tmp_path / "drums"))
    monkeypatch.setattr(grooves, "FOLDER", str(tmp_path / "grooves"))


@pytest.fixture(autouse=True)
def without_airwindows(tmp_path, monkeypatch):
    """Ein eingerichtetes Airwindows (setup_airwindows.py) färbt die Mixe der Tests nicht."""
    import airwindows
    monkeypatch.setattr(airwindows, "FOLDER", str(tmp_path / "airwindows"))
    monkeypatch.setattr(airwindows, "system_folders", lambda: ())


@pytest.fixture(autouse=True)
def without_style_fx(monkeypatch):
    """Stil-Effekte (Telefon, Stutter, harter Tune, Formanten) ändern die Gesangsspuren der Tests nicht;
    test_stil_effekte.py holt sie sich zurück."""
    import style_fx
    monkeypatch.setattr(style_fx, "STYLES", {})


@pytest.fixture(autouse=True)
def without_vocal_swing(monkeypatch):
    """Der Gesang swingt in den Tests nicht mit (Lo-Fi-Songs bleiben wie bisher); test_gesang_swing.py holt es sich
    zurück."""
    import singing
    monkeypatch.setattr(singing, "VOCAL_SWING_FROM", 2.0)


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
def without_demucs(tmp_path, monkeypatch):
    """Ein eingerichtetes Demucs (setup_demucs.py) zerlegt in den Tests keine Vorbilder."""
    import separation
    monkeypatch.setattr(separation, "FOLDER", str(tmp_path / "demucs"))
    monkeypatch.setattr(separation, "CACHE", str(tmp_path / "vorbild_gruppen.json"))


@pytest.fixture(autouse=True)
def without_accompaniment(tmp_path, monkeypatch):
    """Eine eingerichtete KI-Begleitung (setup_begleitung.py) schreibt in den Tests nicht mit."""
    import accompaniment
    monkeypatch.setattr(accompaniment, "FOLDER", str(tmp_path / "begleitung"))


@pytest.fixture(autouse=True)
def without_polish(tmp_path, monkeypatch):
    """Ein eingerichteter Klang-Veredler (setup_ace_step.py) veredelt in den Tests nicht mit."""
    import polish
    monkeypatch.setattr(polish, "FOLDER", str(tmp_path / "ace-step"))
    monkeypatch.setattr(polish, "TIMEOUT", 120)     # das nachgebaute Modell braucht Sekunden, nicht eine Stunde


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


@pytest.fixture(autouse=True)
def not_cancelled():
    """Ein Abbruch in einem Test bricht den nächsten nicht ab."""
    import cancel
    cancel.reset()
    yield
    cancel.reset()


@pytest.fixture
def neutrino_attrappe(tmp_path, monkeypatch):
    """NEUTRINO als Attrappe hinter vocal_synthesizer._run: die echten Aufrufe, aber Sinus statt Stimme.
    Rückgabe: (NEUTRINO-Ordner, Liste der aufgerufenen Programme)."""
    import subprocess

    import numpy as np
    import soundfile as sf

    import singing
    import vocal_synthesizer
    root = tmp_path / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "model" / "MERROW").mkdir(parents=True)
    for name in ("musicXMLtoLabel.exe", "NEUTRINO.exe"):
        (root / "bin" / name).write_bytes(b"")
    calls = []
    lengths = {}

    def run(cmd, cwd, timeout):
        name = os.path.basename(cmd[0])
        calls.append(name)
        if name == "musicXMLtoLabel.exe":
            import music21
            xml = cmd[1]
            beats = float(music21.converter.parse(xml).highestTime)
            lengths[cmd[2]] = beats * 60.0 / vocal_synthesizer._tempo_aus_musicxml(xml)
            for path in cmd[2:4]:
                with open(path, "w") as f:
                    f.write("label")
        else:
            sr = 48000
            t = np.arange(int(lengths[cmd[1]] * sr)) / sr
            sf.write(cmd[5], (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), sr)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(vocal_synthesizer, "_run", run)
    # die Windows-Sprachausgabe der Vorschau-Stimme hängt in der CI: sie darf hier nie singen
    monkeypatch.setattr(singing, "_sing_preview", lambda *a, **k: pytest.fail("die Vorschau-Stimme sang"))
    return root, calls


@pytest.fixture(autouse=True)
def without_idol_calls(monkeypatch):
    """Keine Idol-Rufe (v6 Nr. 15): die Songs der Tests singen wie bisher; test_idol_rufe.py holt sie sich zurück."""
    import backing_vocals
    monkeypatch.setattr(backing_vocals, "IDOL_CALLS", {})


@pytest.fixture(autouse=True)
def without_vocal_chops(monkeypatch):
    """Keine Vocal Chops (v6 Nr. 14): die Mixe der Tests klingen wie bisher; test_vocal_chops.py holt sie sich zurück."""
    import vocal_chops
    monkeypatch.setattr(vocal_chops, "CHOP_STYLES", {})


@pytest.fixture(autouse=True)
def without_ritardando(monkeypatch):
    """Kein Ritardando am Ende (v6 Nr. 16): Balladen der Tests enden wie bisher; test_ritardando.py holt es sich
    zurück."""
    import ritardando
    monkeypatch.setattr(ritardando, "STYLES", {})

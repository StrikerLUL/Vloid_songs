# test_projekt.py – Songs als Projekt aufheben und wieder öffnen (v6 Nr. 5)
import os

import numpy as np
import soundfile as sf

import history
import main
import pipeline
import project
from settings import SongSettings


def song_settings(tmp_path, root, **kw):
    s = SongSettings(active_sections=["Verse", "Chorus"], section_bars={"Verse": 4, "Chorus": 4},
                     output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                     harmonies=False, final_choir=False, breaths=False, phrase_expression=False,
                     syllable_dynamics=False, harmony_double=False, sung_pads=False, adlibs=False, polish=False,
                     auto_rating=False, vocal_versions=False)
    return s.with_updates(**kw)


def neutrino_runs(calls) -> int:
    return sum(name == "NEUTRINO.exe" for name in calls)


def test_a_reopened_song_keeps_its_vocals_and_is_not_sung_again(tmp_path, neutrino_attrappe):
    root, calls = neutrino_attrappe
    first = pipeline.generate_song(song_settings(tmp_path, root))
    sung, _ = sf.read(first.vocals_wav, always_2d=True)
    assert project.available(first.history)
    assert os.path.exists(os.path.join(project.folder(first.history), "vocals.flac"))
    pipeline.generate_song(song_settings(tmp_path, root, seed=6))      # der nächste Song überschreibt den Ordner
    entry = history.entries(first.output_dir)[1]
    assert entry.audio == first.history
    restored = entry.restore(song_settings(tmp_path, root, seed=99))
    ok, message = project.unpack(entry.audio, restored, restored.output_dir())
    assert ok and "wieder geöffnet" in message
    before = neutrino_runs(calls)
    again = pipeline.generate_song(restored, keep_history=False)
    assert neutrino_runs(calls) == before                               # nicht neu gesungen
    reopened, _ = sf.read(again.vocals_wav, always_2d=True)
    assert reopened.shape == sung.shape and np.max(np.abs(reopened - sung)) < 1e-4    # FLAC mit 24 Bit
    assert len(history.entries(first.output_dir)) == 2                  # nicht noch einmal im Verlauf


def test_a_song_with_a_spoken_line_is_reopened_without_singing_again(tmp_path, neutrino_attrappe):
    """Die Zeilen der Sektion „Sprechen“ singt die Engine nie (VOICEVOX spricht sie): auch dann bleibt beim Wieder-Öffnen
    der aufgehobene Gesang, statt dass NEUTRINO alles neu singt."""
    root, calls = neutrino_attrappe
    spoken = dict(active_sections=["Verse", "Spoken"], section_bars={"Verse": 4, "Spoken": 4},
                  lyrics="[Verse]\nよ る の ま ち\n[Sprechen]\nき み の な ま え を よ ん だ")
    first = pipeline.generate_song(song_settings(tmp_path, root, **spoken))
    pipeline.generate_song(song_settings(tmp_path, root, seed=6, **spoken))
    entry = history.entries(first.output_dir)[1]
    restored = entry.restore(song_settings(tmp_path, root, seed=99, **spoken))
    ok, _ = project.unpack(entry.audio, restored, restored.output_dir())
    before = neutrino_runs(calls)
    pipeline.generate_song(restored, keep_history=False)
    assert ok and neutrino_runs(calls) == before


def test_changed_notes_are_sung_again(tmp_path, neutrino_attrappe):
    root, _ = neutrino_attrappe
    first = pipeline.generate_song(song_settings(tmp_path, root))
    entry = history.entries(first.output_dir)[0]
    other = entry.restore(entry.settings).with_updates(lyrics="[Verse]\nらららら\n[Chorus]\nるるる")
    ok, message = project.unpack(entry.audio, other, other.output_dir())
    assert not ok and "neu gesungen" in message


def test_without_the_switch_nothing_is_kept_and_deleting_takes_the_project_along(tmp_path, neutrino_attrappe):
    root, _ = neutrino_attrappe
    plain = pipeline.generate_song(song_settings(tmp_path, root, keep_projects=False))
    assert not project.available(plain.history)
    kept = pipeline.generate_song(song_settings(tmp_path, root, seed=6))
    assert project.size(kept.history) > 0
    history.delete(history.entries(kept.output_dir)[0])
    assert not os.path.exists(project.folder(kept.history))
    assert [e.audio for e in history.entries(kept.output_dir)] == [plain.history]   # der Ordner ist kein Eintrag


def test_reopen_from_the_command_line(tmp_path, neutrino_attrappe):
    root, calls = neutrino_attrappe
    s = song_settings(tmp_path, root)
    pipeline.generate_song(s)
    pipeline.generate_song(s.with_updates(seed=6))
    path = str(tmp_path / "einstellungen.json")
    s.save(path)
    before = neutrino_runs(calls)
    assert main.main(["--settings", path, "--oeffnen", "2"]) == 0
    assert neutrino_runs(calls) == before
    assert main.main(["--settings", path, "--oeffnen", "7"]) == 1

# test_cli.py – Kommandozeile: Optionen landen in den Einstellungen
import json

import pytest

import main
from pipeline import SongResult
from settings import SongSettings


@pytest.fixture
def captured(monkeypatch, tmp_path):
    seen = {}

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        progress(1.0, "Fertig")
        return SongResult(seed=settings.seed or 1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"))

    monkeypatch.setattr(main, "generate_song", fake_generate)
    return seen


def test_options_override_saved_settings(captured, tmp_path):
    SongSettings(bpm=100, style="Rock").save()
    out = tmp_path / "songs"
    code = main.main(["--seed", "7", "--bpm", "140", "--key", "F#", "--scale", "dorian", "--output", str(out)])
    s = captured["settings"]
    assert code == 0
    assert (s.seed, s.bpm, s.key, s.scale, s.style) == (7, 140, "F#", "dorian", "Rock")
    assert s.output_ordner == str(out)


def test_settings_file_option(captured, tmp_path):
    path = tmp_path / "eigene.json"
    path.write_text(json.dumps({"bpm": 77, "style": "Ballade"}), encoding="utf-8")
    assert main.main(["--settings", str(path)]) == 0
    assert (captured["settings"].bpm, captured["settings"].style) == (77, "Ballade")


def test_invalid_option_is_rejected(captured):
    with pytest.raises(SystemExit):
        main.main(["--key", "H"])


def test_failure_returns_exit_code_1(monkeypatch):
    def boom(settings, progress=None, seed=None):
        raise RuntimeError("Keine Audiospuren zum Mischen vorhanden.")
    monkeypatch.setattr(main, "generate_song", boom)
    assert main.main([]) == 1

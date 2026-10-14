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


def test_vocal_options(captured):
    assert main.main(["--engine", "VOICEVOX", "--voicevox-stimme", "3002", "--fassungen", "3", "--vibrato", "0",
                      "--uebergaenge", "1.5", "--ohne-atmer", "--ohne-chor"]) == 0
    s = captured["settings"]
    assert (s.vocal_engine, s.voicevox_singer, s.vocal_takes, s.vibrato, s.glide) == ("VOICEVOX", 3002, 3, 0.0, 1.5)
    assert (s.breaths, s.echo_throws, s.final_choir) == (False, True, False)


def test_sound_options(captured):
    SongSettings(channels={"piano": {"volume": 0.3}}).save()
    assert main.main(["--style", "Lo-Fi", "--schlagzeug", "909", "--ohne-verstaerker", "--box", "C:/box.wav",
                      "--ohne-lofi-klang", "--ohne-samples", "--ohne-bewegung", "--ohne-vorbild-gruppen"]) == 0
    s = captured["settings"]
    assert (s.style, s.channels["drums"].style, s.guitar_amp, s.cabinet_ir, s.lofi_texture, s.samples) == \
        ("Lo-Fi", "909", False, "C:/box.wav", False, False)
    assert s.mix_movement is False and s.ref_stems is False
    assert s.channels["piano"].volume == 0.3


def test_composition_options(captured, tmp_path):
    SongSettings(custom_chords={"Bridge": "F G"}).save()
    assert main.main(["--seed", "4", "--akkorde", "Chorus=F G Em Am", "--akkorde", "Verse=vi IV I V",
                      "--melodie-midi", "C:/melodie.mid", "--melodie-sektion", "Verse", "--refrain", "2"]) == 0
    s = captured["settings"]
    assert s.custom_chords == {"Bridge": "F G", "Chorus": "F G Em Am", "Verse": "vi IV I V"}
    assert (s.melody_midi, s.melody_midi_section) == ("C:/melodie.mid", "Verse")
    assert s.variations == {"melody:Chorus": 2}
    assert main.main(["--akkorde", "Bridge="]) == 0
    assert captured["settings"].custom_chords == {}


@pytest.mark.parametrize("args", [["--akkorde", "Chorus=F Fxyz"], ["--akkorde", "Refrain=F G"],
                                  ["--akkorde", "F G"], ["--neu", "melody:Refrain"], ["--neu", "kazoo"]])
def test_bad_composition_options_are_rejected(captured, args):
    with pytest.raises(SystemExit):
        main.main(args)


def test_chorus_choices_from_the_command_line(monkeypatch, tmp_path, caplog):
    import pipeline

    def fake_hooks(settings, count, progress=None):
        return [pipeline.HookChoice(n, settings.with_updates(seed=9, variations={"melody:Chorus": n}),
                                    str(tmp_path / f"{n}.wav")) for n in range(1, count + 1)]

    monkeypatch.setattr(main, "hook_choices", fake_hooks)
    caplog.set_level("INFO")
    assert main.main(["--refrains", "2"]) == 0
    assert "--seed 9 --refrain 2" in caplog.text

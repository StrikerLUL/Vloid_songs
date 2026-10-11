# test_pipeline.py – Von den Einstellungen bis zur fertigen Datei
import os

import pytest

import pipeline
from pipeline import compose, generate_song, genre_for_style
from settings import INSTRUMENTS, STYLE_OPTIONS, SongSettings

SHORT = ["Intro", "Verse", "Chorus", "Outro"]


def make_settings(tmp_path, **updates):
    base = {"active_sections": SHORT, "output_ordner": str(tmp_path / "out")}
    return SongSettings().with_updates(**{**base, **updates})


def note_list(tracks, inst):
    return [(round(n.start, 6), n.pitch, n.velocity) for n in tracks[inst]]


@pytest.mark.parametrize("style,genre", [
    ("J-Pop Energy", "J-Pop"), ("Kawaii Chiptune", "EDM"), ("Ballade", "Lo-Fi"), ("Rock", "Rock"), ("EDM", "EDM"),
])
def test_preset_styles_map_to_engine_genres(style, genre):
    assert genre_for_style(style) == genre


def test_settings_reach_the_orchestrator(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(pipeline, "orchestrate_song", lambda **kw: seen.update(kw) or {})
    s = make_settings(tmp_path, style="City Pop", bpm=90, key="Eb", scale="dorian", swing=0.3, jitter=0.01,
                      lyrics="[Chorus]\nら ら る", channels={"bass": {"style": "lazy"}})
    compose(s, seed=5)
    assert seen["genre"] == "Lo-Fi" and seen["bpm"] == 90
    assert (seen["key"], seen["mode"]) == ("D#", "dorian")
    assert seen["structure"] == SHORT
    assert seen["output_dir"] == str(tmp_path / "out")
    assert seen["lyrics"] == {"Chorus": ["ら", "ら", "る"]}
    assert seen["swing"] == 0.3
    assert seen["jitter_scale"] == pytest.approx(0.5)
    assert seen["instrument_styles"]["bass"] == "lazy"


def test_same_seed_gives_the_same_song(tmp_path):
    s = make_settings(tmp_path)
    a, seed_a = compose(s, seed=42)
    b, seed_b = compose(s, seed=42)
    c, _ = compose(s, seed=43)
    assert seed_a == seed_b == 42
    for inst in INSTRUMENTS:
        assert note_list(a, inst) == note_list(b, inst), inst
    assert any(note_list(a, inst) != note_list(c, inst) for inst in INSTRUMENTS)


def test_seed_from_settings_is_used_and_a_new_one_drawn_otherwise(tmp_path):
    _, seed = compose(make_settings(tmp_path, seed=777))
    assert seed == 777
    _, seed = compose(make_settings(tmp_path))
    assert isinstance(seed, int) and seed > 0


def test_midi_files_go_to_the_configured_folder(tmp_path):
    s = make_settings(tmp_path)
    os.makedirs(s.output_dir())
    tracks, _ = compose(s, seed=1)
    for inst in INSTRUMENTS:
        if tracks[inst]:
            assert os.path.exists(os.path.join(s.output_dir(), f"{inst}.mid")), inst


def test_lyrics_from_the_app_are_sung(tmp_path):
    lyrics = "[Verse]\nあ い う え お か き く け こ\n[Chorus]\nさ し す せ そ"
    tracks, _ = compose(make_settings(tmp_path, lyrics=lyrics, active_sections=["Verse", "Chorus"]), seed=3)
    assert tracks["silben"] == "あ い う え お か き く け こ さ し す せ そ".split()
    sung = [d for d in tracks["melody_data"] if d[0] is not None]
    assert len(sung) == len(tracks["melody"])


def test_choosing_a_style_changes_the_part(tmp_path):
    default, _ = compose(make_settings(tmp_path), seed=11)
    styled, _ = compose(make_settings(tmp_path, channels={"bass": {"style": "driving"}}), seed=11)
    assert note_list(default, "bass") != note_list(styled, "bass")


@pytest.mark.parametrize("inst,style", [
    (inst, style) for inst, styles in STYLE_OPTIONS.items() for style in styles if style != "default"
])
def test_every_style_in_the_app_produces_notes(tmp_path, inst, style):
    tracks, _ = compose(make_settings(tmp_path, active_sections=["Chorus"], channels={inst: {"style": style}}), seed=2)
    assert tracks[inst], f"{inst} mit Stil {style} ist stumm"


# ── Kompletter Ablauf mit Audio ─────────────────────────────────────────────────
@pytest.mark.slow
def test_generate_song_renders_and_mixes(tmp_path):
    s = make_settings(tmp_path, active_sections=["Intro", "Chorus"], channels={
        "vocals": {"enabled": False}, "guitar": {"enabled": False}, "brass": {"enabled": False},
    })
    out = s.output_dir()
    os.makedirs(out)
    stale = os.path.join(out, "brass.wav")
    open(stale, "wb").close()

    steps = []
    result = generate_song(s, progress=lambda f, msg: steps.append(f), seed=9)

    assert result.seed == 9
    assert os.path.exists(result.mix_wav)
    assert result.vocals_wav is None
    assert "guitar" not in result.wav_files and "brass" not in result.wav_files
    assert not os.path.exists(stale), "alte Spur wäre mitgemischt worden"
    assert {"piano", "bass", "drums"} <= set(result.wav_files)
    assert steps == sorted(steps) and steps[-1] == 1.0
    if result.mp3:
        assert os.path.getsize(result.mp3) > 0


def test_generate_song_without_any_track_fails_clearly(tmp_path):
    s = make_settings(tmp_path, channels={ch: {"enabled": False} for ch in (*INSTRUMENTS, "vocals")})
    with pytest.raises(RuntimeError, match="Keine Audiospuren"):
        generate_song(s, seed=1)


def test_mp3_export_without_ffmpeg_leaves_no_empty_file(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    from pydub import AudioSegment

    from exporter import exportiere_song

    wav = str(tmp_path / "mix.wav")
    sf.write(wav, np.zeros((4410, 2), dtype=np.float32), 44100)
    mp3 = str(tmp_path / "song.mp3")
    monkeypatch.setattr(AudioSegment, "converter", str(tmp_path / "kein-ffmpeg.exe"))

    assert exportiere_song(wav, mp3) is None
    assert not os.path.exists(mp3)

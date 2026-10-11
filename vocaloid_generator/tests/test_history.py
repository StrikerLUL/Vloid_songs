# test_history.py – Neu würfeln pro Spur, Verlauf, Varianten und Export als ZIP
import json
import os
import zipfile

import pytest

import history
import main
import orchestrator
import pipeline
from pipeline import SongResult, compose, generate_variants
from settings import INSTRUMENTS, REROLLABLE, SongSettings

SHORT = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]


def make_settings(tmp_path, **updates):
    base = {"active_sections": SHORT, "output_ordner": str(tmp_path / "out"), "seed": 21}
    return SongSettings().with_updates(**{**base, **updates})


def notes(tracks, inst):
    return [(round(n.start, 6), n.pitch, n.velocity) for n in tracks[inst]]


def chords(tracks):
    return [(sec.kind, [(c.start, str(c.chord)) for c in sec.chords]) for sec in tracks["plan"].sections]


# ── Neu würfeln pro Spur ────────────────────────────────────────────────────────
def test_orchestrator_and_settings_agree_on_the_parts():
    assert orchestrator.REROLLABLE == REROLLABLE


@pytest.mark.parametrize("part", ["drums", "bass", "piano", "counter"])
def test_rerolling_an_instrument_changes_only_that_instrument(tmp_path, part):
    s = make_settings(tmp_path)
    before, _ = compose(s)
    after, _ = compose(s.rerolled(part))
    assert notes(before, part) != notes(after, part)
    for inst in INSTRUMENTS:
        if inst != part:
            assert notes(before, inst) == notes(after, inst), inst
    assert before["silben"] == after["silben"] and before["melody_data"] == after["melody_data"]


def test_rerolling_the_melody_keeps_chords_and_band(tmp_path):
    s = make_settings(tmp_path)
    before, _ = compose(s)
    after, _ = compose(s.rerolled("melody"))
    assert before["melody_data"] != after["melody_data"]
    assert chords(before) == chords(after)
    for inst in ("drums", "bass", "piano", "strings"):
        assert notes(before, inst) == notes(after, inst), inst


def test_rerolling_the_chords_gives_new_chords(tmp_path):
    s = make_settings(tmp_path)
    before, _ = compose(s)
    after, _ = compose(s.rerolled("chords"))
    assert chords(before) != chords(after)


def test_the_same_variation_comes_back(tmp_path):
    s = make_settings(tmp_path).rerolled("bass").rerolled("bass")
    a, _ = compose(s)
    b, _ = compose(s)
    assert notes(a, "bass") == notes(b, "bass")
    assert s.variations == {"bass": 2}


def test_variations_are_checked():
    s = SongSettings(variations={"bass": 2, "drums": 0, "kazoo": 3})
    assert s.variations == {"bass": 2}
    with pytest.raises(ValueError):
        s.rerolled("kazoo")


# ── Verlauf ─────────────────────────────────────────────────────────────────────
def fake_song(tmp_path, name="final_song.mp3", content=b"ID3 song"):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_finished_songs_land_in_the_history_with_their_settings(tmp_path):
    out = str(tmp_path / "out")
    s = make_settings(tmp_path, style="City Pop", bpm=95, reference_track="C:/vorbild.mp3").rerolled("melody")
    entry = history.record(fake_song(tmp_path), s, out)

    assert entry.audio.startswith(os.path.join(out, "verlauf"))
    with open(entry.audio, "rb") as f:
        assert f.read() == b"ID3 song"
    [found] = history.entries(out)
    assert found.name == entry.name
    restored = found.settings
    assert (restored.style, restored.bpm, restored.seed) == ("City Pop", 95, 21)
    assert restored.variations == {"melody": 1}
    assert [r.path for r in restored.reference_tracks] == ["C:/vorbild.mp3"]
    assert "City Pop" in found.title and "Seed 21" in found.title


def test_restoring_keeps_the_paths_of_this_computer(tmp_path):
    out = str(tmp_path / "out")
    old = make_settings(tmp_path, neutrino_pfad="D:/alt/NEUTRINO", bpm=120)
    history.record(fake_song(tmp_path), old, out)
    current = make_settings(tmp_path, neutrino_pfad="C:/neu/NEUTRINO", bpm=150)

    restored = history.entries(out)[0].restore(current)
    assert restored.bpm == 120
    assert restored.neutrino_pfad == "C:/neu/NEUTRINO"


def test_history_keeps_the_newest_songs_and_all_favorites(tmp_path):
    out = str(tmp_path / "out")
    first = history.record(fake_song(tmp_path), make_settings(tmp_path, seed=1), out, keep=3)
    history.set_favorite(first, True)
    for seed in range(2, 7):
        history.record(fake_song(tmp_path), make_settings(tmp_path, seed=seed), out, keep=3)

    kept = history.entries(out)
    assert [e.settings.seed for e in kept] == [6, 5, 4, 1]
    assert kept[-1].favorite
    assert len(os.listdir(history.folder(out))) == 8


def test_songs_in_the_same_second_do_not_overwrite_each_other(tmp_path):
    out = str(tmp_path / "out")
    s = make_settings(tmp_path)
    a = history.record(fake_song(tmp_path), s, out)
    b = history.record(fake_song(tmp_path), s, out)
    assert a.audio != b.audio
    assert len(history.entries(out)) == 2


def test_history_without_mp3_keeps_the_wav(tmp_path):
    out = str(tmp_path / "out")
    entry = history.record(fake_song(tmp_path, "final_mix.wav", b"RIFF"), make_settings(tmp_path), out)
    assert entry.audio.endswith(".wav")
    assert history.entries(out)[0].audio == entry.audio


def test_broken_history_files_are_skipped(tmp_path):
    out = str(tmp_path / "out")
    history.record(fake_song(tmp_path), make_settings(tmp_path), out)
    broken = os.path.join(history.folder(out), "20200101-000000_kaputt_1")
    with open(broken + ".json", "w", encoding="utf-8") as f:
        f.write("{kein json")
    open(broken + ".mp3", "wb").close()
    assert len(history.entries(out)) == 1


# ── Varianten ───────────────────────────────────────────────────────────────────
@pytest.fixture
def generated(monkeypatch, tmp_path):
    seen = []

    def fake_generate(settings, progress=None, seed=None):
        seen.append(settings)
        progress(1.0, "Fertig")
        return SongResult(seed=settings.seed or len(seen), output_dir=str(tmp_path), settings=settings)

    monkeypatch.setattr(pipeline, "generate_song", fake_generate)
    monkeypatch.setattr(main, "generate_song", fake_generate)
    return seen


def test_variants_draw_a_new_seed_for_every_song(tmp_path, generated):
    steps = []
    results = generate_variants(make_settings(tmp_path).rerolled("bass"), 3,
                                progress=lambda f, msg: steps.append((f, msg)))
    assert len(results) == 3
    assert all(s.seed is None and s.variations == {} for s in generated)
    assert steps[-1][0] == 1.0 and steps[0][1].startswith("Variante 1/3")


def test_variants_of_one_part_keep_the_song(tmp_path, generated):
    generate_variants(make_settings(tmp_path), 3, parts=("melody",))
    assert [s.seed for s in generated] == [21, 21, 21]
    assert [s.variations for s in generated] == [{"melody": 1}, {"melody": 2}, {"melody": 3}]


def test_variants_of_one_part_need_a_seed(tmp_path, generated):
    with pytest.raises(ValueError, match="Seed"):
        generate_variants(make_settings(tmp_path, seed=None), 2, parts=("drums",))


# ── Kommandozeile ───────────────────────────────────────────────────────────────
def test_cli_rerolls_a_part_of_the_last_song(tmp_path, generated):
    out = str(tmp_path / "out")
    history.record(fake_song(tmp_path), make_settings(tmp_path, seed=99, bpm=133), out)
    assert main.main(["--output", out, "--neu", "drums", "--neu", "bass"]) == 0
    [s] = generated
    assert (s.seed, s.bpm) == (99, 133)
    assert s.variations == {"drums": 1, "bass": 1}


def test_cli_takes_a_song_from_the_history(tmp_path, generated):
    out = str(tmp_path / "out")
    for seed in (5, 6):
        history.record(fake_song(tmp_path), make_settings(tmp_path, seed=seed), out)
    assert main.main(["--output", out, "--aus-verlauf", "2", "--bpm", "111"]) == 0
    assert (generated[0].seed, generated[0].bpm) == (5, 111)


def test_cli_reroll_without_history_fails(tmp_path, generated):
    assert main.main(["--output", str(tmp_path / "leer"), "--neu", "melody"]) == 1
    assert generated == []


def test_cli_lists_the_history(tmp_path, generated, caplog):
    out = str(tmp_path / "out")
    history.record(fake_song(tmp_path), make_settings(tmp_path, style="Rock"), out)
    with caplog.at_level("INFO", logger="vocaloid"):
        assert main.main(["--output", out, "--verlauf"]) == 0
    assert generated == []
    assert "Rock" in caplog.text


def test_cli_exports_a_zip(tmp_path, generated, monkeypatch):
    import exporter
    zipped = {}
    monkeypatch.setattr(exporter, "exportiere_projekt", lambda result, path: zipped.setdefault(path, result) and path)
    target = str(tmp_path / "song.zip")
    assert main.main(["--output", str(tmp_path / "out"), "--zip", target]) == 0
    assert target in zipped


# ── Export als ZIP ──────────────────────────────────────────────────────────────
def test_project_zip_has_mix_stems_midi_and_settings(tmp_path):
    from exporter import exportiere_projekt

    out = tmp_path / "out"
    out.mkdir()
    for name in ("final_song.mp3", "final_mix.wav", "piano.wav", "drums.wav", "fx.wav", "vocals.wav",
                 "piano.mid", "drums.mid", "vocal_melody.mid", "vocals.xml", "vocals_harmony.xml", "alt.wav"):
        (out / name).write_bytes(b"x")
    s = make_settings(tmp_path, bpm=128).rerolled("drums")
    result = SongResult(
        seed=21, output_dir=str(out), settings=s,
        midi_files={"piano": str(out / "piano.mid"), "drums": str(out / "drums.mid")},
        wav_files={"piano": str(out / "piano.wav"), "drums": str(out / "drums.wav"), "fx": str(out / "fx.wav")},
        vocals_wav=str(out / "vocals.wav"), mix_wav=str(out / "final_mix.wav"), mp3=str(out / "final_song.mp3"),
    )
    path = exportiere_projekt(result, str(tmp_path / "export" / "song.zip"))

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        info = z.read("song.txt").decode("utf-8")
        settings = json.loads(z.read("einstellungen.json"))
    assert names == {
        "final_song.mp3", "final_mix.wav", "Spuren/piano.wav", "Spuren/drums.wav", "Spuren/fx.wav",
        "Spuren/vocals.wav", "MIDI/piano.mid", "MIDI/drums.mid", "MIDI/vocal_melody.mid", "Gesang/vocals.xml",
        "einstellungen.json", "song.txt",
    }
    assert "128 BPM" in info and "Seed: 21" in info and "drums 1x" in info
    assert SongSettings.model_validate(settings).variations == {"drums": 1}

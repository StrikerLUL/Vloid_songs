# test_alltag.py – Für jeden Tag: schneller Entwurf, Song-Bibliothek
import os

import pytest

import history
import main
import pipeline
from pipeline import SongResult, compose, draft_settings, generate_song
from settings import INSTRUMENTS, SongSettings


def _settings(tmp_path, **updates) -> SongSettings:
    base = {"active_sections": ["Intro", "Chorus"], "output_ordner": str(tmp_path / "out")}
    return SongSettings().with_updates(**{**base, **updates})


# ── Entwurf ───────────────────────────────────────────────────────────────────
def test_draft_skips_the_slow_steps_and_keeps_the_real_song(tmp_path):
    s = _settings(tmp_path, vocal_takes=3, polish=True, samples=True)
    draft = draft_settings(s)
    assert draft.draft and not s.draft
    assert draft.output_dir() == os.path.join(str(tmp_path / "out"), pipeline.DRAFT_FOLDER)
    assert not draft.channels["vocals"].enabled and draft.channels["melody"].enabled
    assert (draft.vocal_takes, draft.polish, draft.samples, draft.reuse_steps) == (1, False, False, False)
    assert s.channels["vocals"].enabled and s.polish                  # die eigenen Einstellungen bleiben
    assert draft_settings(draft) == draft                             # kein Entwurf vom Entwurf


def test_draft_folder_works_on_a_fresh_install(tmp_path):
    s = _settings(tmp_path, output_ordner=str(tmp_path / "neu" / "Songs"))
    os.makedirs(tmp_path / "neu")
    assert draft_settings(s).output_dir() == str(tmp_path / "neu" / "Songs" / pipeline.DRAFT_FOLDER)


def test_draft_and_real_song_share_the_notes(tmp_path):
    s = _settings(tmp_path)
    full, _ = compose(s, seed=42)
    sketch, _ = compose(draft_settings(s), seed=42)
    for inst in (*INSTRUMENTS, "vocal_melody"):
        if inst in full:
            assert [(n.start, n.pitch) for n in full[inst]] == [(n.start, n.pitch) for n in sketch[inst]], inst


@pytest.mark.slow
def test_draft_song_has_no_mp3_and_stays_out_of_the_history(tmp_path):
    s = _settings(tmp_path, channels={"guitar": {"enabled": False}, "brass": {"enabled": False}})
    out = s.output_dir()
    os.makedirs(out)
    real_mp3 = os.path.join(out, "final_song.mp3")
    open(real_mp3, "wb").write(b"der letzte richtige Song")

    result = generate_song(draft_settings(s), seed=9)

    assert result.output_dir.endswith(pipeline.DRAFT_FOLDER) and os.path.isfile(result.mix_wav)
    assert result.mp3 is None and result.audio == result.mix_wav and result.vocals_wav is None
    assert "melody" in result.wav_files                               # die Lead-Stimme spielt die Melodie
    assert result.history is None and history.entries(out) == [] and history.entries(result.output_dir) == []
    assert open(real_mp3, "rb").read() == b"der letzte richtige Song"


def test_command_line_draft(monkeypatch, tmp_path):
    seen = {}

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        return SongResult(seed=1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"))

    monkeypatch.setattr(main, "generate_song", fake_generate)
    assert main.main(["--entwurf", "--output", str(tmp_path / "songs")]) == 0
    assert seen["settings"].draft and seen["settings"].output_ordner == str(tmp_path / "songs" / "Entwurf")
    assert main.main(["--output", str(tmp_path / "songs")]) == 0
    assert not seen["settings"].draft


# ── Song-Bibliothek ───────────────────────────────────────────────────────────
def _record(tmp_path, out, nr, keep=30, **updates):
    song = tmp_path / f"song{nr}.mp3"
    song.write_bytes(b"ID3")
    return history.record(str(song), SongSettings(seed=nr, **updates), out, keep=keep)


def _by_seed(out) -> dict:
    return {e.settings.seed: e for e in history.entries(out)}


def test_songs_get_a_name_and_a_note_and_are_found_again(tmp_path):
    out = str(tmp_path / "out")
    a = _record(tmp_path, out, 1, style="Rock")
    b = _record(tmp_path, out, 4711, style="Ballade")
    history.set_details(a, label=" Sommerregen ", note="Refrain gut, Bridge zu lang")
    history.set_details(b, note="ruhig")
    found = {e.settings.seed: e for e in history.entries(out)}
    assert (found[1].label, found[1].note) == ("Sommerregen", "Refrain gut, Bridge zu lang")
    assert "„Sommerregen“" in found[1].title
    every = history.entries(out)
    assert [e.settings.seed for e in history.find(every, "sommer")] == [1]
    assert [e.settings.seed for e in history.find(every, "bridge rock")] == [1]      # jedes Wort muss passen
    assert [e.settings.seed for e in history.find(every, "ballade")] == [4711]
    assert [e.settings.seed for e in history.find(every, "4711")] == [4711]
    assert history.find(every, "jazz") == []
    history.set_details(found[1], label="")                           # Name weg, Notiz bleibt
    again = _by_seed(out)[1]
    assert again.label == "" and again.note.startswith("Refrain")


def test_favorites_filter_and_sorting(tmp_path):
    out = str(tmp_path / "out")
    for nr, score in ((1, 6.5), (2, None), (3, 8.0)):
        entry = _record(tmp_path, out, nr)
        if score:
            history.set_rating(entry.audio, {"overall": score})
    songs = _by_seed(out)
    history.set_favorite(songs[2], True)
    every = history.entries(out)
    assert [e.settings.seed for e in history.find(every)] == [e.settings.seed for e in every]   # wie gespeichert
    assert [e.settings.seed for e in history.find(every, favorites=True)] == [2]
    assert [e.settings.seed for e in history.find(every, sort="bewertung")] == [3, 1, 2]   # ohne Note zuletzt
    history.set_details(songs[1], label="Zebra")
    history.set_details(songs[3], label="Anfang")
    assert [e.label for e in history.find(history.entries(out), sort="name")][:2] == ["Anfang", "Zebra"]


def test_named_and_album_songs_stay_and_zero_keeps_everything(tmp_path):
    out = str(tmp_path / "out")
    named = _record(tmp_path, out, 1)
    history.set_details(named, label="Behalten")
    album = _record(tmp_path, out, 2)
    history.set_album(album.audio, "Nacht 1")
    for nr in range(3, 7):
        _record(tmp_path, out, nr, keep=2)
    assert [e.settings.seed for e in history.entries(out)] == [6, 5, 2, 1]
    for nr in range(7, 10):
        _record(tmp_path, out, nr, keep=0)
    assert len(history.entries(out)) == 7
    assert SongSettings().history_keep == 30


def test_history_size_belongs_to_the_computer_not_the_song(tmp_path):
    out = str(tmp_path / "out")
    _record(tmp_path, out, 1, history_keep=5)
    assert history.entries(out)[0].restore(SongSettings(history_keep=0)).history_keep == 0


def test_command_line_searches_and_sorts_the_history(tmp_path, caplog):
    out = str(tmp_path / "out")
    for nr, style in ((1, "Rock"), (2, "Ballade"), (3, "Rock")):
        _record(tmp_path, out, nr, style=style)
    history.set_rating(_by_seed(out)[1].audio, {"overall": 9.0})
    number = [e.settings.seed for e in history.entries(out)].index(1) + 1
    with caplog.at_level("INFO", logger="vocaloid"):
        assert main.main(["--output", out, "--verlauf", "rock", "--sortieren", "bewertung"]) == 0
    lines = [r.getMessage() for r in caplog.records if "Seed" in r.getMessage()]
    assert len(lines) == 2 and "Seed 1" in lines[0] and "Note 9.0" in lines[0]
    assert lines[0].startswith(f"{number:2d}.")                       # die Nummer für --aus-verlauf

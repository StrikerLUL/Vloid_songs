# test_alltag.py – Für jeden Tag: Entwurf, Song-Bibliothek, Album über Nacht, Fertig für YouTube
import os
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

import album
import cancel
import history
import karaoke
import main
import pipeline
import youtube
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


# ── Album über Nacht ─────────────────────────────────────────────────────────
def test_album_plan_takes_the_styles_in_turn_with_their_typical_values(tmp_path):
    base = SongSettings(style="J-Pop Energy", seed=99, variations={"melody": 2}, lyrics="[Chorus]\nら ら")
    songs = album.plan(base, 5, ["Rock", "Ballade"], seed=1)
    assert [s.style for s in songs] == ["Rock", "Ballade", "Rock", "Ballade", "Rock"]
    assert all(s.seed is None and s.variations == {} for s in songs)
    assert all(s.lyrics == base.lyrics for s in songs)
    assert len({(s.key, s.bpm) for s in songs}) > 1                   # eigene Tonart und eigenes Tempo
    from preset_manager import preset_settings
    rock = preset_settings("Rock", base)
    same = album.plan(base.with_updates(album_vary=False), 3, ["Rock"])
    assert {(s.key, s.bpm) for s in same} == {(rock.key, rock.bpm)}
    assert abs(songs[0].bpm - rock.bpm) <= rock.bpm * album.TEMPO_SPREAD + 1
    with pytest.raises(ValueError):
        album.plan(base, album.MAX_SONGS + 1, ["Rock"])


def test_album_lyrics_come_one_file_per_song(tmp_path):
    folder = tmp_path / "texte"
    folder.mkdir()
    (folder / "2 zweiter.txt").write_text("[Chorus]\nふたつ", encoding="utf-8")
    (folder / "1 erster.txt").write_text("\ufeff[Chorus]\nひとつ", encoding="utf-8")       # mit BOM aus Notepad
    (folder / "leer.txt").write_text("  ", encoding="utf-8")
    (folder / "bild.png").write_bytes(b"x")
    texts = album.lyric_files(str(folder))
    assert texts == ["[Chorus]\nひとつ", "[Chorus]\nふたつ"]
    songs = album.plan(SongSettings(), 3, ["Rock"], texts)
    assert [s.lyrics for s in songs] == [texts[0], texts[1], texts[0]]
    assert album.lyric_files(str(tmp_path / "fehlt")) == [] and album.lyric_files("") == []


@pytest.fixture
def overnight(monkeypatch, tmp_path):
    """Erzeugen nachgestellt: jeder Song legt eine MP3 ab und landet im Verlauf; Song 2 scheitert."""
    made = []

    def fake_song(settings, progress=None, seed=None):
        nr = len(made) + 1
        made.append(settings)
        progress(0.5, "Rendere...")
        if nr == 2:
            raise RuntimeError("NEUTRINO ist abgestürzt")
        out = settings.output_dir()
        os.makedirs(out, exist_ok=True)
        mp3 = os.path.join(out, "final_song.mp3")
        with open(mp3, "wb") as f:
            f.write(f"ID3 Song {nr}".encode())
        settings = settings.with_updates(seed=1000 + nr)
        entry = history.record(mp3, settings, out, keep=settings.history_keep)
        return SongResult(seed=settings.seed, output_dir=out, mix_wav=mp3, mp3=mp3, settings=settings,
                          history=entry.audio)

    monkeypatch.setattr(pipeline, "generate_song", fake_song)
    return made


def test_album_overnight_sorts_by_rating_and_survives_a_failed_song(tmp_path, overnight, monkeypatch):
    import rating
    notes = iter([6.0, 9.0, 7.5])
    monkeypatch.setattr(rating, "available", lambda: True)
    monkeypatch.setattr(rating, "excerpt", lambda audio, target: audio)
    monkeypatch.setattr(rating, "rate", lambda paths: [rating.Rating(n, 5.0, 5.0, n) for n, _ in zip(notes, paths)])
    s = SongSettings(output_ordner=str(tmp_path / "out"), history_keep=2)
    steps = []
    made = album.make(s, 4, ["Rock", "Ballade"], progress=lambda f, m: steps.append((f, m)), name="Erste Nacht")

    assert len(overnight) == 4 and made.failed == 1 and not made.cancelled
    assert os.path.dirname(made.folder) == os.path.join(str(tmp_path / "out"), album.FOLDER)
    assert made.folder.endswith("Erste Nacht")
    names = sorted(os.listdir(made.folder))
    assert names[:3] == [os.path.basename(p) for p in made.files] and len(made.files) == 3
    assert [r.seed for r in made.results] == [1003, 1004, 1001]       # Noten 9.0, 7.5, 6.0
    assert names[0].startswith("01 Rock") and open(made.files[0], "rb").read() == b"ID3 Song 3"
    playlist = open(os.path.join(made.folder, album.PLAYLIST), encoding="utf-8").read()
    assert playlist.startswith("#EXTM3U") and os.path.basename(made.files[1]) in playlist
    tracklist = open(os.path.join(made.folder, album.TRACKLIST), encoding="utf-8").read()
    assert "Note 9.0" in tracklist and "1 Songs sind fehlgeschlagen" in tracklist
    entries = history.entries(str(tmp_path / "out"))
    assert len(entries) == 3 and all(e.album == "Erste Nacht" for e in entries)   # bleiben trotz history_keep=2
    assert [f for f, _ in steps] == sorted(f for f, _ in steps) and steps[-1][0] == 1.0
    assert "Album 1/4 (Rock)" in steps[0][1]


def test_album_can_be_cancelled_and_keeps_finished_songs(tmp_path, overnight, monkeypatch):
    def stop_during_third(fraction, message):
        if "Album 3/" in message:
            cancel.request()

    try:
        made = album.make(SongSettings(output_ordner=str(tmp_path / "out")), 5, ["Rock"], progress=stop_during_third)
    finally:
        cancel.reset()
    assert made.cancelled and len(overnight) == 3                     # Song 4 und 5 fangen nicht mehr an
    assert len(made.files) == 2 and made.failed == 1 and all(os.path.isfile(f) for f in made.files)
    assert "abgebrochen" in made.describe()
    assert SongSettings().album_vary and "album_vary" in history.MACHINE_FIELDS


def test_album_from_the_command_line(tmp_path, overnight, monkeypatch):
    out = str(tmp_path / "out")
    assert main.main(["--output", out, "--album", "3", "--album-stile", "Rock, Ballade", "--album-gleich",
                      "--album-name", "Test"]) == 0
    assert [s.style for s in overnight] == ["Rock", "Ballade", "Rock"]
    assert not overnight[0].album_vary
    [folder] = os.listdir(os.path.join(out, album.FOLDER))
    assert folder.endswith("Test") and len(history.entries(out)) == 2
    assert main.main(["--output", out, "--album", "2", "--album-stile", "Polka"]) == 1
    assert main.main(["--output", out, "--album", "99"]) == 1


# ── Fertig für YouTube ───────────────────────────────────────────────────────
def _ffmpeg_can_render() -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    filters = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " ass " in filters and " showwaves " in filters


def _finished_song(tmp_path, lyrics: bool = True, **updates) -> SongResult:
    out = tmp_path / "out"
    out.mkdir(parents=True)
    t = np.arange(3 * 22050) / 22050
    tone = (0.3 * np.sin(2 * np.pi * 330 * t) * np.linspace(0.2, 1.0, t.size)).astype(np.float32)
    sf.write(str(out / "final_mix.wav"), np.stack([tone, tone], axis=1), 22050)
    if lyrics:
        found = [{"start": 0.5, "end": 2.5, "syllables": [[0.5, 1.5, "よ"], [1.5, 2.5, "る"]]}]
        karaoke.save(str(out / karaoke.FILE), found)
    s = SongSettings(output_ordner=str(out), seed=77, style="City Pop", bpm=96, key="F", scale="major",
                     singer="KIRITAN", **updates)
    return SongResult(seed=77, output_dir=str(out), mix_wav=str(out / "final_mix.wav"), settings=s)


def test_title_image_has_the_size_and_colors_of_the_style(tmp_path):
    from PIL import Image
    audio = tmp_path / "song.wav"
    sf.write(str(audio), np.random.default_rng(1).normal(0, 0.1, (44100, 2)).astype(np.float32), 44100)
    path = youtube.title_image(str(tmp_path / "bild.png"), "Sommerregen", "City Pop · 96 BPM", "City Pop", str(audio))
    image = Image.open(path).convert("RGB")
    assert image.size == youtube.IMAGE_SIZE
    top, bottom, _ = (youtube._rgb(c) for c in youtube.PALETTES["City Pop"])
    assert np.allclose(image.getpixel((5, 0)), top, atol=3)
    assert np.allclose(image.getpixel((5, youtube.IMAGE_SIZE[1] - 1)), bottom, atol=3)
    centre = np.asarray(image.crop((300, 150, 980, 280)))
    assert (centre.min(axis=2) > 240).any()                          # der Titel in Weiß
    plain = youtube.title_image(str(tmp_path / "leer.png"), "", style="Unbekannt", bars=False)
    assert Image.open(plain).size == youtube.IMAGE_SIZE


def test_description_names_the_voice(tmp_path):
    result = _finished_song(tmp_path, duet_singer="ITAKO")
    text = youtube.description(result, "Sommerregen")
    assert text.startswith("Sommerregen\n") and "City Pop · 96 BPM · F Dur" in text
    assert "NEUTRINO, Stimme KIRITAN und ITAKO" in text and "Seed 77" in text
    assert "VOICEVOX:" in youtube.description(_finished_song(tmp_path / "v", vocal_engine="VOICEVOX"), "x")
    quiet = _finished_song(tmp_path / "q", channels={"vocals": {"enabled": False}})
    assert "NEUTRINO" not in youtube.description(quiet, "x")


@pytest.mark.skipif(not _ffmpeg_can_render(), reason="ffmpeg mit libass fehlt")
@pytest.mark.parametrize("lyrics", [True, False])
def test_youtube_folder_has_mp3_video_image_and_description(tmp_path, lyrics):
    result = _finished_song(tmp_path, lyrics)
    steps = []
    package = youtube.make(result, "Sommerregen", progress=lambda f, m: steps.append(f))
    assert package.folder.startswith(str(tmp_path / "out" / youtube.FOLDER)) and "Sommerregen" in package.folder
    assert sorted(os.listdir(package.folder)) == ["Beschreibung.txt", "Sommerregen.mp3", "Sommerregen.mp4",
                                                  "Titelbild.png"]
    assert package.problems == [] and os.path.getsize(package.video) > 5000
    assert steps == sorted(steps) and steps[-1] == 1.0
    again = youtube.make(result)                                      # zweimal: eigener Ordner, Titel aus dem Stil
    assert again.folder != package.folder and "City Pop (Seed 77)" in again.folder


def test_youtube_folder_without_ffmpeg_still_has_image_and_text(tmp_path, monkeypatch):
    from pydub import AudioSegment
    monkeypatch.setattr(AudioSegment, "converter", str(tmp_path / "kein-ffmpeg"))
    monkeypatch.setattr(karaoke, "find_ffmpeg", lambda: None)
    package = youtube.make(_finished_song(tmp_path), "Ohne")
    assert sorted(os.listdir(package.folder)) == ["Beschreibung.txt", "Ohne.wav", "Titelbild.png"]
    assert package.video is None and "ohne ffmpeg nur als WAV" in package.describe() and "ffmpeg" in package.describe()
    with pytest.raises(RuntimeError, match="Song fehlt"):
        youtube.make(SongResult(seed=1, output_dir=str(tmp_path)))


def test_youtube_from_the_command_line(tmp_path, monkeypatch):
    made = []
    result = _finished_song(tmp_path)
    monkeypatch.setattr(main, "generate_song", lambda settings, progress=None, seed=None: result)
    monkeypatch.setattr(youtube, "make", lambda r, title="", progress=None: made.append((r, title)) or
                        youtube.Package(str(tmp_path), title))
    assert main.main(["--youtube", "Mein Titel"]) == 0
    assert made == [(result, "Mein Titel")]

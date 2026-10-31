# test_video_171.py – „Die Videos gehen nicht mehr“ (1.7.1)
#
# In der einfachen Ansicht (ab Werk an) gab es keinen Knopf fürs Video, die Video-Vorschau war ohne geänderte Töne
# immer ausgegraut, ein Fehler außer RuntimeError verschwand still („Fertig“, aber kein Video), ein Klick neben die
# Namensfrage brach das Video ohne ein Wort ab, die Partikel って stand als „xtsute“ in den Romaji, und KI-Bilder, die
# in 1024×576 nicht gingen, fielen ganz weg.
import asyncio
import os

import pytest_asyncio
from nicegui import ElementFilter
from nicegui.testing.user_simulation import user_simulation

import bilder
import karaoke
import musikvideo
import pipeline
import youtube
from gui import page
from pipeline import SongResult
from settings import SongSettings
from test_app import fake_generation, write_song  # noqa: F401 – das Fixture gilt so auch hier


async def until(condition, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    assert condition()


def marked(user, marker: str) -> list:
    """Alle Elemente mit dieser Markierung, auch ausgeblendete (user.find sieht nur sichtbare)."""
    with user:
        return list(ElementFilter(marker=marker))


def _settings(tmp_path, **extra) -> SongSettings:
    return SongSettings(output_ordner=str(tmp_path / "out"), seed=None, setup_wizard=False, update_check=False,
                        **{"simple_view": False, **extra})


@pytest_asyncio.fixture
async def simple_user(tmp_path):
    _settings(tmp_path, simple_view=True).save()
    async with user_simulation(root=page.build) as user:
        yield user


@pytest_asyncio.fixture
async def user(tmp_path):
    _settings(tmp_path).save()
    async with user_simulation(root=page.build) as user:
        yield user


def _fake_video(made: list, tmp_path):
    def fake(result, path=None, label="", preview=False, progress=None):
        made.append((result.seed, label, preview))
        path = str(tmp_path / ("video_vorschau.mp4" if preview else "lyric_video.mp4"))
        open(path, "wb").close()
        return path
    return fake


async def test_the_simple_view_has_the_video_buttons(simple_user, fake_generation, monkeypatch, tmp_path):  # noqa: F811
    made = []
    monkeypatch.setattr(pipeline, "lyric_video", _fake_video(made, tmp_path))
    await simple_user.open("/")
    simple_user.find(marker="simple-generate").click()
    await simple_user.should_see("Seed 1000", retries=50)
    for marker in ("video", "video-preview", "youtube"):
        assert [e.visible for e in marked(simple_user, marker)] == [True], marker
    assert not marked(simple_user, "zip")[0].visible and not marked(simple_user, "notes-zip")[0].visible
    simple_user.find(marker="video").click()
    await simple_user.should_see("Wie heißt der Song?", retries=50)
    simple_user.find(marker="video-name-skip").click()
    await simple_user.should_see("Lyric-Video gespeichert", retries=50)
    assert made == [(1000, "", False)]


async def test_the_video_preview_is_enabled_without_edited_notes(user, fake_generation, monkeypatch,  # noqa: F811
                                                                 tmp_path):
    made = []
    monkeypatch.setattr(pipeline, "lyric_video", _fake_video(made, tmp_path))
    monkeypatch.setattr(page.media, "open_folder", lambda path: True)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    await until(lambda: marked(user, "video-preview")[0].enabled)
    assert not marked(user, "preview-edits")[0].enabled          # „Vorschau“ der Notenänderungen: es gibt keine
    user.find(marker="video-preview").click()
    await user.should_see("Wie heißt der Song?", retries=50)
    user.find(marker="video-name").type("Leuchtturm")
    user.find(marker="video-name").trigger("keydown.enter")        # Enter reicht
    await until(lambda: made == [(1000, "Leuchtturm", True)])


async def test_an_unexpected_error_is_shown_and_not_called_done(user, fake_generation, monkeypatch):  # noqa: F811
    def broken(result, path=None, label="", preview=False, progress=None):
        raise ValueError("images do not match")

    monkeypatch.setattr(pipeline, "lyric_video", broken)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="video").click()
    await user.should_see("Wie heißt der Song?", retries=50)
    user.find(marker="video-name-skip").click()
    await user.should_see("Das Lyric-Video ging nicht: ValueError: images do not match", retries=50)
    await until(lambda: marked(user, "step")[0].text.startswith("Video ging nicht"))
    assert marked(user, "video")[0].enabled                      # die App bleibt bedienbar


async def test_cancelling_the_name_question_says_so(user, fake_generation, monkeypatch, tmp_path):  # noqa: F811
    made = []
    monkeypatch.setattr(pipeline, "lyric_video", _fake_video(made, tmp_path))
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="video").click()
    await user.should_see("Wie heißt der Song?", retries=50)
    dialog = next(e for e in marked(user, "video-name")[0].ancestors() if type(e).__name__ == "Dialog")
    assert "persistent" in dialog.props                          # ein Klick daneben schließt nicht still
    user.find(marker="video-name-cancel").click()
    await user.should_see("es entsteht kein Video", retries=50)
    assert made == []


def test_the_particle_tte_is_written_tte_not_xtsute():
    assert karaoke._kana_romaji("って") == "tte"
    assert karaoke._kana_romaji("っち") == "tchi"
    assert karaoke._kana_romaji("あっ") == "a"
    assert karaoke._kana_romaji("すきって") == "sukitte"
    line = [[0.0, 0.4, "す", True], [0.5, 0.9, "き", False], [1.0, 1.4, "っ", True], [1.5, 1.9, "て", False]]
    assert karaoke.romaji(line) == "suki tte"


def test_sharp_pictures_fall_back_to_the_old_size(tmp_path, monkeypatch):
    sizes = []

    def run(jobs, folder, size=bilder.SIZE):
        sizes.append(tuple(size))
        if tuple(size) == bilder.SHARP_SIZE:
            return False                                          # z. B. zu wenig Grafikspeicher
        for job in jobs:
            open(job["path"], "wb").close()
        return True

    monkeypatch.setattr(bilder, "available", lambda: True)
    monkeypatch.setattr(bilder, "song_prompts", lambda result: {"Chorus": "stars", "Verse": "rain"})
    monkeypatch.setattr(bilder, "_run", run)
    result = SongResult(seed=3, output_dir=str(tmp_path))
    found = bilder.for_song(result, sharp=True)
    assert sizes == [bilder.SHARP_SIZE, bilder.SIZE] and set(found) == {"Chorus", "Verse"}


def test_youtube_keeps_mp3_and_cover_when_the_video_breaks(tmp_path, monkeypatch):
    result = write_song(str(tmp_path / "out"), 7)
    result.settings = SongSettings(seed=7)

    def broken(*args, **kwargs):
        raise IndexError("list index out of range")

    monkeypatch.setattr(musikvideo, "for_song", broken)
    package = youtube.make(result, "Probe")
    assert package.audio and os.path.exists(package.audio) and package.image and package.description
    assert package.video is None and any("IndexError" in p for p in package.problems)


# ── Ein Song aus dem Verlauf bekommt sein Video (auch nach einem Neustart oder Update) ──────────────────────────────
LYRICS = ("[Verse]\n雨の街を 君を追いかけて\n忘れた傘を 握りしめたまま\n\n"
          "[Chorus]\nパスワード 今 輝いて\n既読のまま 夜を越えて\n")


def _in_history(tmp_path, keep_map: bool = True, forget: tuple = (), **extra):
    """Ein komponierter Song mit Text im Verlauf, sein Gesang als Projekt (nur der Fingerabdruck der Noten zählt).
    keep_map=False: wie vor 1.7.1 ohne Songkarte im Projekt. forget: Schalter, die in seiner Datei fehlen (älter)."""
    import json

    import numpy as np
    import soundfile as sf

    import history
    import project
    out = tmp_path / "out"
    s = SongSettings().with_updates(output_ordner=str(out), seed=5, lyrics=LYRICS, style="Ballade",
                                    active_sections=["Intro", "Verse", "Chorus", "Outro"], **extra)
    tracks, _ = pipeline.compose(s)
    pipeline._write_karaoke(s, tracks, str(out))
    sf.write(str(out / "final_mix.wav"), np.zeros((22050, 2), np.float32), 22050)
    sf.write(str(out / "vocals.wav"), np.zeros((22050, 2), np.float32), 22050)
    entry = history.record(str(out / "final_mix.wav"), s, str(out))
    project.save(str(out), tracks, entry.audio)
    if keep_map:
        project.keep_map(str(out), entry.audio)
    if forget:
        with open(entry.info, encoding="utf-8") as f:
            data = json.load(f)
        with open(entry.info, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in data.items() if k not in forget}, f)
        entry = history.entries(str(out))[0]
    return s, entry, karaoke.load(str(out / karaoke.FILE)), str(out)


def _another_song(out: str) -> None:
    """Danach entstand ein anderer Song im Ausgabeordner."""
    import songkarte
    songkarte.save(os.path.join(out, songkarte.FILE), songkarte.Map(style="Rock", seed=99))
    karaoke.save(os.path.join(out, karaoke.FILE), [])


def _no_compose(monkeypatch):
    def compose(*args, **kwargs):
        raise AssertionError("die Noten hätten nicht neu geschrieben werden dürfen")
    monkeypatch.setattr(pipeline, "compose", compose)


def test_a_song_from_the_history_keeps_its_timing_after_another_song(tmp_path, monkeypatch):
    import project
    s, entry, lines, out = _in_history(tmp_path)
    assert lines and project.has_map(entry.audio)
    _another_song(out)
    _no_compose(monkeypatch)
    result = pipeline.from_history(entry, SongSettings(output_ordner=out))
    assert result.output_dir == project.folder(entry.audio) and result.share_dir == out
    assert result.audio == entry.audio and result.seed == 5 and result.history == entry.audio
    assert karaoke.load(os.path.join(result.output_dir, karaoke.FILE)) == lines
    seen = []
    monkeypatch.setattr(musikvideo, "for_song", lambda result, path, *a, **kw: seen.append(path) or path)
    pipeline.lyric_video(result)
    assert seen == [os.path.join(out, "lyric_video.mp4")]          # in den Ausgabeordner, nicht in den Verlauf


def test_the_newest_song_takes_its_files_from_the_output_folder(tmp_path, monkeypatch):
    import project
    s, entry, lines, out = _in_history(tmp_path, keep_map=False)
    assert not project.has_map(entry.audio)
    _no_compose(monkeypatch)
    result = pipeline.from_history(entry, SongSettings(output_ordner=out))
    assert project.has_map(entry.audio)
    assert karaoke.load(os.path.join(result.output_dir, karaoke.FILE)) == lines


def test_an_older_song_is_written_again_and_checked_against_its_singing(tmp_path):
    import json

    import project
    s, entry, lines, out = _in_history(tmp_path, keep_map=False)
    _another_song(out)
    result = pipeline.from_history(entry, SongSettings(output_ordner=out))
    assert karaoke.load(os.path.join(result.output_dir, karaoke.FILE)) == lines
    assert os.path.isfile(os.path.join(out, "piano.mid"))           # die MIDI-Dateien im Ordner blieben

    for name in project.MAP_FILES[:2]:                              # sein Gesang passt nicht mehr zu den Noten
        os.remove(os.path.join(project.folder(entry.audio), name))
    path = os.path.join(project.folder(entry.audio), project.FILE)
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**saved, "notes": "anders"}, f)
    try:
        pipeline.from_history(entry, SongSettings(output_ordner=out))
    except RuntimeError as e:
        assert "Wieder öffnen" in str(e)
    else:
        raise AssertionError("ein Video mit verrutschten Silben")


def test_switches_the_song_did_not_know_yet_stay_off(tmp_path, new_170):
    import project
    s, entry, lines, out = _in_history(tmp_path, keep_map=False, forget=("section_registers",),
                                       section_registers=False)
    assert entry.settings.section_registers                        # so lädt 1.7 den Song aus 1.6: mit dem Schalter
    on, _ = pipeline.compose(entry.settings.with_updates(output_ordner=str(tmp_path / "probe")))
    assert project.notes_print(on) != project.notes_of(entry.audio)   # … und schriebe andere Noten
    _another_song(out)
    result = pipeline.from_history(entry, SongSettings(output_ordner=out))
    assert karaoke.load(os.path.join(result.output_dir, karaoke.FILE)) == lines


def test_the_video_takes_the_look_from_the_video_tab():
    result = SongResult(seed=1, output_dir="x", settings=SongSettings(video_tidy=True, music_video=True, bpm=99))
    now = SongSettings(video_tidy=False, video_romaji=False, music_video=True, bpm=140)
    looked = pipeline.with_look(result, now)
    assert not looked.settings.video_tidy and not looked.settings.video_romaji and looked.settings.bpm == 99
    assert result.settings.video_tidy                               # der Song selbst bleibt


async def test_after_a_restart_the_video_comes_from_the_history(user, monkeypatch, tmp_path):
    import history
    out = str(tmp_path / "out")
    song = write_song(out, 42)
    s = SongSettings(output_ordner=out, seed=42)
    older = history.record(song.mix_wav, s.with_updates(seed=41), out)
    newest = history.record(song.mix_wav, s, out)
    history.set_details(newest, label="Leuchtturm")
    history.set_details(older, label="Fuchsfeuer")
    read, made = [], []

    def from_history(entry, current=None, progress=None):
        read.append(entry.audio)
        return SongResult(seed=entry.settings.seed, output_dir=out, mix_wav=entry.audio, settings=entry.settings,
                          history=entry.audio)

    monkeypatch.setattr(pipeline, "from_history", from_history)
    monkeypatch.setattr(pipeline, "lyric_video", _fake_video(made, tmp_path))
    await user.open("/")
    user.find(marker="video").click()                               # kein Song geladen: der neueste im Verlauf
    await user.should_see("Lyric-Video gespeichert", retries=50)
    assert read == [newest.audio] and made == [(42, "Leuchtturm", False)]
    user.find(marker="tab-Verlauf").click()
    await user.should_see(marker="history-video", retries=50)
    from nicegui.testing.user_interaction import UserInteraction
    second = sorted(marked(user, "history-video"), key=lambda e: e.id)[1]
    UserInteraction(user, {second}, None).click()                   # der ältere, beim Film-Symbol im Verlauf
    await until(lambda: len(made) == 2)
    assert read[-1] == older.audio and made[-1] == (41, "Fuchsfeuer", False)

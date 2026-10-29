# test_video_150.py – Das Musikvideo folgt dem Song (1.5.0 V1 bis V13)
import json
import os
import shutil

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

import bilder
import karaoke
import lyric_helper
import musikvideo
import pipeline
import songkarte
import tags
import textmotive
import video_szenen as szenen
import youtube
from lyrics import section_lines, shown_parts, sung_lines
from pipeline import SongResult
from settings import SongSettings
from test_handling import has_ffmpeg_with_subtitles

LYRICS = ("[Verse]\n雨の街を 君を追いかけて\n> Durch die Stadt im Regen lauf ich dir nach\n忘れた傘を 握りしめたまま\n\n"
          "[Chorus]\n星のように 輝いて\n> Leuchte wie die Sterne\n既読のまま 夜を越えて\n")


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    """Ein komponierter Song mit Text, Übersetzung, Liedtext zum Mitlesen und Songkarte im Ordner."""
    out = tmp_path_factory.mktemp("musikvideo")
    s = SongSettings().with_updates(output_ordner=str(out), seed=5, lyrics=LYRICS, style="Ballade",
                                    active_sections=["Intro", "Verse", "Chorus", "Outro"])
    tracks, _ = pipeline.compose(s)
    pipeline._write_karaoke(s, tracks, str(out))
    return s, tracks, str(out)


def _audio(path, seconds: float) -> str:
    rate = 22050
    t = np.arange(int(seconds * rate)) / rate
    beat = (np.sin(2 * np.pi * 2 * t) > 0.95).astype(np.float32)
    tone = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.3 * beat * np.random.default_rng(1).normal(0, 1, t.size)
    sf.write(str(path), tone.astype(np.float32), rate)
    return str(path)


# ── V1: Songkarte ───────────────────────────────────────────────────────────────
def test_the_song_map_knows_sections_chords_drums_and_melody(made):
    s, tracks, out = made
    found = songkarte.load(os.path.join(out, songkarte.FILE))
    assert [sec.kind for sec in found.sections] == ["Intro", "Verse", "Chorus", "Outro"]
    assert found.style == "Ballade" and found.length > 20 and len(found.beats) > 30
    assert found.chords and all(start < end for start, end, _ in found.chords)
    assert found.kicks and found.melody and found.melody == sorted(found.melody)
    chorus = found.sections[2]
    assert found.section_at(chorus.start + 0.1) is chorus and found.label(chorus) == "Refrain"
    beat, phase = found.beat_at(found.beats[4] + 0.01)
    assert beat == 4 and 0 < phase < 0.2
    assert found.chord_at(found.chords[0][0])[0] == found.chords[0][2]
    again = songkarte.Map.from_dict(json.loads(json.dumps(found.to_dict())))
    assert again == found
    assert songkarte.load(os.path.join(out, "fehlt.json")) is None            # Songs von 1.4: ohne Karte


def test_youtube_chapters_start_at_zero_and_are_ten_seconds_apart():
    sections = [songkarte.Section(kind, n, start, end, 0.5, True) for kind, n, start, end in (
        ("Intro", 1, 0.0, 8.0), ("Verse", 1, 8.0, 30.0), ("Chorus", 1, 30.0, 34.0), ("Verse", 2, 34.0, 60.0),
        ("Chorus", 2, 60.0, 90.0), ("Outro", 1, 90.0, 100.0))]
    found = songkarte.Map(sections=sections, length=100.0)
    marks = songkarte.chapters(found)
    assert marks == [(0.0, "Strophe 1"), (30.0, "Strophe 2"), (60.0, "Refrain 2"), (90.0, "Outro")]
    assert all(b[0] - a[0] >= 10 for a, b in zip(marks, marks[1:]))
    assert songkarte.timestamp(65) == "1:05" and songkarte.timestamp(3725) == "1:02:05"


def test_the_description_lists_chapters_only_with_the_switch(made, tmp_path):
    s, _, out = made
    result = SongResult(seed=5, output_dir=out, settings=s.with_updates(singer="ITAKO"))
    text = youtube.description(result, "Vergessener Schirm")
    assert "0:00 Intro" in text and "Strophe" in text and "Refrain" in text
    plain = youtube.description(SongResult(seed=5, output_dir=out, settings=s.with_updates(youtube_chapters=False)),
                                "x")
    assert "0:00" not in plain
    assert youtube.credits(result) == ["Gesang: NEUTRINO, Stimme ITAKO", "Musik, Melodie und Arrangement: Vloid Songs"]


# ── V2: Text wie geschrieben, Romaji, Übersetzung ─────────────────────────────
def test_translation_lines_are_shown_but_never_sung():
    lines = sung_lines(LYRICS)
    written, sung, german = lines["Verse"][0]
    assert written == "雨の街を 君を追いかけて" and german == "Durch die Stadt im Regen lauf ich dir nach"
    assert len(lines["Verse"]) == 2 and lines["Verse"][1][2] == ""
    assert all(">" not in "".join(syl) for syl in section_lines(LYRICS)["Verse"])
    assert "Durch die Stadt" not in tags.lyric_text(LYRICS)
    checked = lyric_helper.check(SongSettings(lyrics=LYRICS))
    assert not any("Durch die Stadt" in str(section) for section in checked)


def test_the_lines_carry_kanji_romaji_and_german(made):
    _, _, out = made
    found = karaoke.load(os.path.join(out, karaoke.FILE))
    first = found[0]
    assert first["text"] == "雨の街を 君を追いかけて"
    assert first["romaji"].startswith("ame no machi o kimi o")
    assert first["de"] == "Durch die Stadt im Regen lauf ich dir nach"
    assert any(line.get("text") == "既読のまま 夜を越えて" and line["de"] == "" for line in found)


def test_romaji_are_sung_kana_grouped_by_written_words():
    line = [[i * 0.3, i * 0.3 + 0.3, kana] for i, kana in enumerate("きみ を お い か け て")]
    line = [item for item in line if item[2] != " "]
    assert karaoke.romaji(line, "君を追いかけて") == "kimi o oikakete"
    assert karaoke._kana_romaji("ふぁいと") == "faito" and karaoke._kana_romaji("すきー") == "sukii"


def test_the_words_light_up_one_after_another_in_time(made):
    _, _, out = made
    line = karaoke.load(os.path.join(out, karaoke.FILE))[0]
    parts = musikvideo.chunks(line, kanji=True)
    assert "".join(text for text, _ in parts).replace(" ", "") == "雨の街を君を追いかけて"
    total = sum(cs for _, cs in parts)
    assert abs(total - (line["syllables"][-1][1] - line["syllables"][0][0]) * 100) <= len(parts)
    kana = musikvideo.chunks(line, kanji=False)
    assert len(kana) == len(line["syllables"]) and kana[0][0] == line["syllables"][0][2]
    assert [n for _, n in shown_parts("君を追いかけて")][0] >= 2


# ── V8: Bilder aus dem Text ────────────────────────────────────────────────────
def test_words_in_the_text_bring_their_pictures():
    assert set(textmotive.find("雨の街を")) == {"rain", "city"}
    assert "chat" in textmotive.find("既読のまま") and "stars" in textmotive.find("星のように")
    assert "petals" in textmotive.find("花びらが舞う") and not textmotive.find("はなしあい")
    lines = [{"text": "雨の街"}, {"text": "雨が降る"}, {"text": "星"}]
    assert textmotive.weather(lines) == "rain" and textmotive.weather([{"text": "ねこ"}]) is None


# ── V6, V7, V12: Szenen ────────────────────────────────────────────────────────
@pytest.mark.parametrize("style", list(szenen.SCENES) + ["Textkunst"])
def test_every_scene_paints_its_own_picture_and_keeps_the_text_band_calm(style):
    scene = szenen.for_style("Rock" if style == "Textkunst" else style, style if style == "Textkunst" else "")
    painter = szenen.Painter(scene, szenen.motion(scene, "Stil"), seed=3, lyric_chars="雨の街を",
                             weather="rain")
    frame = szenen.Frame(t=12.3, kind="Chorus", chorus=True, energy=0.9, beat=8, beat_pulse=1.0, kick=1.0,
                         bands=np.linspace(0, 1, musikvideo.BANDS), wave=np.sin(np.linspace(0, 9, 160)),
                         notes=[[11.5, 12.5, 64], [12.5, 13.0, 67]], singing=True, song_progress=0.4,
                         sections=[(0, 0.5, "Verse"), (0.5, 1, "Chorus")], motifs={"stars"})
    image = np.asarray(painter.frame(frame), dtype=float)
    assert image.shape == (szenen.H, szenen.W, 3) and image.std() > 10
    band = image[int(szenen.H * 0.55):int(szenen.H * 0.75), int(szenen.W * 0.3):int(szenen.W * 0.7)]
    assert band.mean() < image.mean() + 25                                  # hinter dem Text wird es nicht heller


def test_flashes_are_rare_and_never_glaring():
    painter = szenen.Painter(szenen.for_style("Future Bass"), szenen.LIVELY)
    lit = [t / 30 for t in range(90) if painter.allowed_flash(t / 30, 1.0) > 0]
    starts = [t for i, t in enumerate(lit) if i == 0 or t - lit[i - 1] > 0.05]
    for t in starts:
        assert sum(1 for x in starts if t <= x < t + 1.0) <= szenen.FLASHES_PER_SECOND
    assert max(painter.allowed_flash(9.0 + k, 1.0) for k in range(3)) <= szenen.MAX_FLASH
    calm = szenen.Painter(szenen.for_style("Future Bass"), szenen.CALM)
    assert calm.allowed_flash(0.0, 0.5) < painter.allowed_flash(20.0, 0.5)


def test_motion_follows_the_style_unless_chosen():
    assert szenen.motion(szenen.for_style("Ballade"), "Stil") == szenen.CALM
    assert szenen.motion(szenen.for_style("Rock"), "Stil") == szenen.LIVELY
    assert szenen.motion(szenen.for_style("Rock"), "ruhig") == szenen.CALM
    assert szenen.for_style("Rock", "Lo-Fi").name == "Zimmer" and szenen.for_style("Rock", "Textkunst").pixel
    with pytest.raises(ValueError):
        SongSettings(video_scene="Unbekannt")


# ── V3, V4, V5, V10: was im Video steht ────────────────────────────────────────
def test_each_part_of_the_video_has_its_switch(made):
    s, _, out = made
    found = songkarte.load(os.path.join(out, songkarte.FILE))
    lines = karaoke.load(os.path.join(out, karaoke.FILE))
    scene = szenen.for_style(s.style)

    def text(**off) -> str:
        opts = musikvideo.options_from(s.with_updates(**off))
        return musikvideo.ass(lines, scene, opts, s.style, "Vergessener Schirm", "Ballade", ("Gesang: X",), found,
                              found.length + 2)
    full = text()
    assert ",Romaji," in full and ",Deutsch," in full and ",Chord," in full and ",Title," in full
    assert "Refrain" in full and "雨の" in full and "ame no machi" in full and "Gesang: X" in full
    assert ",Romaji," not in text(video_romaji=False) and ",Deutsch," not in text(video_german=False)
    assert ",Chord," not in text(video_chords=False)
    assert ",Title," not in text(video_titles=False) and "Gesang: X" not in text(video_titles=False)
    assert "雨" not in text(video_kanji=False).split("[Events]")[1].split("Romaji")[0]

    def painted(**off) -> np.ndarray:
        opts = musikvideo.options_from(s.with_updates(**off))
        painter = szenen.Painter(scene, 1.0, 1, "雨", "rain" if opts.words else None, False, None, {}, None,
                                 opts.melody_line, opts.spectrum, opts.hud)
        timeline = musikvideo.Timeline(found, lines, None, found.length)
        frame = timeline.frame(found.melody[3][0] + 0.05)
        frame.bands = np.full(musikvideo.BANDS, 0.8)
        return np.asarray(painter.frame(frame), dtype=float)
    base = painted()
    for name in ("video_melody_line", "video_spectrum", "video_hud", "video_words"):
        assert np.abs(painted(**{name: False}) - base).mean() > 0.05, name


def test_the_timeline_follows_sections_beats_and_drums(made):
    _, _, out = made
    found = songkarte.load(os.path.join(out, songkarte.FILE))
    timeline = musikvideo.Timeline(found, [], None, found.length)
    chorus = next(sec for sec in found.sections if sec.kind == "Chorus")
    f = timeline.frame(chorus.start + 0.01)
    assert f.chorus and f.change > 0.9 and f.kind == "Chorus"
    assert timeline.frame(found.kicks[2] + 0.01).kick > 0.9
    assert timeline.frame(0.0).fade == 0 and timeline.frame(found.length / 2).fade == 1
    assert musikvideo.preview_start(found, []) == pytest.approx(chorus.start - 0.5)


# ── Einbau: Lyric-Video, Vorschau, YouTube ─────────────────────────────────────
def test_the_music_video_replaces_the_lyric_video_only_with_the_switch(made, tmp_path, monkeypatch):
    s, _, out = made
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"ID3")
    seen = []
    monkeypatch.setattr(musikvideo, "render", lambda audio, path, lines, found, style, opts, *args, **kw:
                        seen.append((path, args[5], args[6], opts.romaji)) or path)
    monkeypatch.setattr(karaoke, "video", lambda audio, lines, path, *args, **kw: seen.append(("alt", path)) or path)
    result = SongResult(seed=5, output_dir=out, mp3=str(mp3), settings=s)
    pipeline.lyric_video(result)
    pipeline.lyric_video(result, preview=True)
    pipeline.lyric_video(SongResult(seed=5, output_dir=out, mp3=str(mp3), settings=s.with_updates(music_video=False)))
    found = songkarte.load(os.path.join(out, songkarte.FILE))
    assert seen[0] == (os.path.join(out, "lyric_video.mp4"), 0.0, None, True)
    assert seen[1][0] == os.path.join(out, "video_vorschau.mp4")
    assert seen[1][1] == pytest.approx(musikvideo.preview_start(found, [])) and seen[1][2] == musikvideo.PREVIEW_SECONDS
    assert seen[2] == ("alt", os.path.join(out, "lyric_video.mp4"))


@pytest.mark.skipif(not has_ffmpeg_with_subtitles() or not shutil.which("ffprobe"), reason="ffmpeg mit libass fehlt")
def test_the_music_video_is_full_hd_with_sound(made, tmp_path):
    import subprocess
    s, _, out = made
    found = songkarte.load(os.path.join(out, songkarte.FILE))
    lines = karaoke.load(os.path.join(out, karaoke.FILE))
    audio = _audio(tmp_path / "song.wav", found.length + 1)
    steps = []
    video = musikvideo.render(audio, str(tmp_path / "v" / "video.mp4"), lines, found, "Textkunst",
                              musikvideo.Options(scene="Textkunst"), "Titel", start=lines[0]["start"], seconds=1.5,
                              progress=lambda f, m: steps.append(f))
    probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,width,height",
                            "-of", "json", video], capture_output=True, text=True)
    streams = json.loads(probe.stdout)["streams"]
    assert {st["codec_type"] for st in streams} == {"video", "audio"}
    assert next(st for st in streams if st["codec_type"] == "video")["width"] == 1920
    assert os.listdir(tmp_path / "v") == ["video.mp4"] and steps[-1] == 1.0


# ── V9: eigene Figur ───────────────────────────────────────────────────────────
def test_the_own_figure_opens_its_mouth_while_singing(tmp_path):
    closed, opened = tmp_path / "zu.png", tmp_path / "auf.png"
    Image.new("RGBA", (200, 400), (255, 0, 0, 255)).save(closed)
    Image.new("RGBA", (200, 400), (0, 0, 255, 255)).save(opened)
    s = SongSettings(video_figure=str(closed), video_figure_open=str(opened))
    opts = musikvideo.options_from(s)
    assert opts.figure == (str(closed), str(opened))
    painter = szenen.Painter(szenen.for_style("Lo-Fi"), szenen.CALM, figure=opts.figure)
    quiet = np.asarray(painter.frame(szenen.Frame(t=5.0, singing=False)), dtype=float)
    sung = np.asarray(painter.frame(szenen.Frame(t=5.0, singing=True)), dtype=float)
    assert quiet[..., 0].sum() > sung[..., 0].sum() and sung[..., 2].sum() > quiet[..., 2].sum()
    assert musikvideo.options_from(SongSettings(video_figure=str(tmp_path / "fehlt.png"))).figure == ()


# ── V13: KI-Bilder ─────────────────────────────────────────────────────────────
def test_ai_pictures_are_painted_once_per_section_kind_and_reused(made, tmp_path, monkeypatch):
    s, _, out = made
    asked = []

    def fake_run(jobs, folder):
        asked.append([job["prompt"] for job in jobs])
        for job in jobs:
            Image.new("RGB", bilder.SIZE, (10, 200, 30)).save(job["path"])
        return True
    monkeypatch.setattr(bilder, "available", lambda: True)
    monkeypatch.setattr(bilder, "_run", fake_run)
    result = SongResult(seed=5, output_dir=out, settings=s)
    found = bilder.for_song(result)
    assert set(found) == {"Intro", "Verse", "Chorus", "Outro"} and all(os.path.exists(p) for p in found.values())
    prompts = asked[0]
    assert all("quiet window at night" in p and "no humans" in p for p in prompts)
    assert any("rain" in p for p in prompts) and any("vivid" in p for p in prompts)
    assert bilder.for_song(result) == found and len(asked) == 1               # schon gemalt: nicht noch einmal
    monkeypatch.setattr(musikvideo, "render", lambda *args, **kw: kw.get("pictures") or args[5].pictures)
    assert musikvideo.for_song(SongResult(seed=5, output_dir=out, mp3=_audio(tmp_path / "a.wav", 2), settings=s),
                               str(tmp_path / "v.mp4")) == found
    assert musikvideo.for_song(SongResult(seed=5, output_dir=out, mp3=_audio(tmp_path / "a.wav", 2),
                                          settings=s.with_updates(ai_backgrounds=False)), str(tmp_path / "v.mp4")) == {}


def test_without_the_model_there_are_no_pictures(made):
    s, _, out = made
    assert not bilder.available() and bilder.for_song(SongResult(seed=5, output_dir=out, settings=s)) == {}
    assert "setup_bilder.py" in bilder.status()


def test_a_picture_replaces_the_drawn_scene_of_its_section(tmp_path):
    picture = tmp_path / "chorus.png"
    Image.new("RGB", (640, 360), (0, 180, 0)).save(picture)
    painter = szenen.Painter(szenen.for_style("Rock"), szenen.CALM, pictures={"Chorus": str(picture)}, roll=False,
                             spectrum=False, hud=False)
    green = np.asarray(painter.frame(szenen.Frame(t=3.0, kind="Chorus", chorus=True)), dtype=float)
    drawn = np.asarray(painter.frame(szenen.Frame(t=3.0, kind="Verse")), dtype=float)
    assert green[20:80, 20:200, 1].mean() > 150 and drawn[20:80, 20:200, 1].mean() < 120

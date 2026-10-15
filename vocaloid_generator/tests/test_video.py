# test_video.py – Lyric-Video in 1080p, in den Farben des Stils oder vor einem eigenen Bild (v6 Nr. 20)
import json
import os
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

import karaoke
import main
import pipeline
import youtube
from pipeline import SongResult
from settings import SongSettings
from test_handling import has_ffmpeg_with_subtitles

FOUND = [{"start": 0.5, "end": 2.5, "syllables": [[0.5, 1.5, "よ"], [1.5, 2.5, "る"]]}]


def song(tmp_path, seconds=3):
    rate = 22050
    t = np.arange(seconds * rate) / rate
    audio = tmp_path / "song.wav"
    sf.write(str(audio), (0.3 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), rate)
    return str(audio)


def test_every_style_sings_in_a_color_that_stands_out_from_white():
    assert karaoke.colors("") == karaoke.PLAIN
    for style in youtube.PALETTES:
        sung, wave, edge = karaoke.colors(style)
        assert karaoke._lightness(youtube._rgb(sung)) < karaoke.LIGHT, style
        assert wave == youtube.PALETTES[style][2] and karaoke._lightness(youtube._rgb(edge)) < 0.3
    plain = karaoke.ass(FOUND)
    assert "Style: Line,Meiryo,90,&H008B4FFF,&H00FFFFFF,&H00301A1A" in plain       # ohne Stil wie bis 1.1, in 1080p
    rock = karaoke.ass(FOUND, style="Rock")
    assert "&H00356BFF" in rock and "&H008B4FFF" not in rock                       # #ff6b35, das Orange von Rock


def test_the_video_takes_the_colors_of_the_style_only_with_the_switch(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    karaoke.save(str(out / karaoke.FILE), FOUND)
    mp3 = out / "final_song.mp3"
    mp3.write_bytes(b"ID3")
    seen = []
    monkeypatch.setattr(karaoke, "video", lambda audio, lines, path, title="", background=None, style="":
                        seen.append((background, style)) or path)
    for s in (SongSettings(style="Rock"), SongSettings(style="Rock", video_colors=False),
              SongSettings(style="Rock", video_background=str(tmp_path / "bild.png"))):
        pipeline.lyric_video(SongResult(seed=1, output_dir=str(out), mp3=str(mp3), settings=s))
    assert seen == [(None, "Rock"), (None, ""), (str(tmp_path / "bild.png"), "Rock")]


def test_a_missing_own_picture_is_reported(tmp_path):
    with pytest.raises(RuntimeError, match="Hintergrundbild"):
        karaoke.video(song(tmp_path), FOUND, str(tmp_path / "v.mp4"), ffmpeg="ffmpeg",
                      background=str(tmp_path / "fehlt.png"))


def test_the_title_picture_grows_with_the_video():
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as folder:
        path = youtube.title_image(os.path.join(folder, "bild.png"), "Titel", "Rock · 160 BPM", "Rock", bars=False,
                                   size=karaoke.VIDEO_SIZE)
        with Image.open(path) as image:
            assert image.size == (1920, 1080)


def _size(path: str) -> tuple:
    probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "json", path], capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    return stream["width"], stream["height"]


@pytest.mark.skipif(not has_ffmpeg_with_subtitles() or not shutil.which("ffprobe"), reason="ffmpeg mit libass fehlt")
def test_the_video_is_full_hd_in_the_style_gradient_or_on_an_own_picture(tmp_path):
    from PIL import Image
    audio = song(tmp_path)
    out = karaoke.video(audio, FOUND, str(tmp_path / "video" / "lyric_video.mp4"), "Test", style="Idol-Pop")
    assert _size(out) == (1920, 1080)
    assert sorted(os.listdir(tmp_path / "video")) == ["lyric_video.ass", "lyric_video.mp4"]   # Verlauf aufgeräumt
    picture = tmp_path / "eigenes.jpg"
    Image.new("RGB", (800, 800), (20, 120, 60)).save(picture)
    out = karaoke.video(audio, FOUND, str(tmp_path / "eigen.mp4"), "Test", background=str(picture), style="Rock")
    assert _size(out) == (1920, 1080) and os.path.exists(picture)


def test_the_command_line_sets_picture_and_colors():
    args = main.parse_args(["--video-hintergrund", "bild.png", "--ohne-stilfarben"])
    assert args.video_hintergrund == "bild.png" and args.ohne_stilfarben

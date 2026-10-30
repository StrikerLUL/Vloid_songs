# test_vorbild_link_160.py – Ein Video-Link als Vorbild (1.6.0): nur der Ton, nur zum Messen, danach gelöscht
import os

import pytest

import vorbild_link
from test_lieder_150 import BPM, SONG, write_song

URL = "https://www.youtube.com/watch?v=abc123"


@pytest.fixture
def fake_download(monkeypatch):
    """_download ohne Netz: legt den Testsong in den temporären Ordner und merkt sich den Ordner."""
    seen = []

    def download(url, folder, progress=None):
        seen.append(folder)
        return write_song(os.path.join(folder, "ton.wav")), "Mein Lied"
    monkeypatch.setattr(vorbild_link, "_download", download)
    return seen


def test_a_link_is_measured_and_its_sound_deleted(fake_download, monkeypatch):
    found = vorbild_link.measure(URL)
    assert (found.title, found.bpm, found.key, found.scale) == ("Mein Lied", BPM, "D", "major")
    template = found.structure()
    assert template.structure() == [kind for kind, *_ in SONG] and template.path == URL
    assert template.custom_chords()["Verse"] == "vi | IV | I | V"
    assert not os.path.exists(fake_download[0])                     # der Ton liegt nicht mehr da
    assert "120 BPM, D Dur" in found.describe()
    monkeypatch.setattr(vorbild_link, "_download", lambda *a, **k: pytest.fail("nicht neu laden"))
    assert vorbild_link.measure(URL).bpm == BPM                      # aus vorbild_links.json
    assert [m.url for m in vorbild_link.load()] == [URL]
    vorbild_link.forget(URL)
    assert vorbild_link.load() == []


def test_a_failed_download_leaves_nothing_behind(monkeypatch, tmp_path):
    folders = []

    def broken(url, folder, progress=None):
        folders.append(folder)
        open(os.path.join(folder, "ton.part"), "wb").write(b"halb")
        raise RuntimeError("Video nicht verfügbar")
    monkeypatch.setattr(vorbild_link, "_download", broken)
    with pytest.raises(RuntimeError):
        vorbild_link.measure(URL)
    assert not os.path.exists(folders[0]) and vorbild_link.load() == []
    with pytest.raises(ValueError):
        vorbild_link.measure("kein link")


def test_yt_dlp_loads_only_the_sound_of_short_videos(monkeypatch, tmp_path):
    import yt_dlp
    used = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            used.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            open(os.path.join(tmp_path, "ton.webm"), "wb").write(b"\x1a\x45\xdf\xa3")
            return {"title": "Titel"}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    audio, title = vorbild_link._download(URL, str(tmp_path))
    assert (os.path.basename(audio), title) == ("ton.webm", "Titel")
    assert used["format"].startswith("bestaudio") and used["noplaylist"]
    assert used["match_filter"]({"duration": 3600}) and used["match_filter"]({"duration": 240}) is None
    assert vorbild_link.available()

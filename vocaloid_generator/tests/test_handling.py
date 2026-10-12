# test_handling.py – Bedienung: Text zum Mitlesen, Lyric-Video, schnelleres Neu-Rendern, Längen der Sektionen
# und von Hand geänderte Töne
import os
import shutil
import subprocess

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import karaoke
import main
import pipeline
from lyrics import Mora, section_lines
from pipeline import SongResult, compose
from settings import DEFAULT_LYRICS, INSTRUMENTS, SongSettings, edit_key

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]


def make_settings(tmp_path, **updates):
    base = {"active_sections": STRUCTURE, "output_ordner": str(tmp_path / "out"), "seed": 21}
    return SongSettings().with_updates(**{**base, **updates})


def note(start, end, pitch=64):
    return pretty_midi.Note(velocity=100, pitch=pitch, start=start, end=end)


def has_ffmpeg_with_subtitles() -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    filters = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " ass " in filters and " showwaves " in filters


# ── Text zum Mitlesen ───────────────────────────────────────────────────────────────
def test_lines_follow_the_written_lyrics(tmp_path):
    s = make_settings(tmp_path)
    tracks, _ = compose(s)
    lengths = {k: [len(line) for line in v] for k, v in section_lines(DEFAULT_LYRICS).items()}
    found = karaoke.lines(tracks["vocal_melody"], tracks["silben"], s.bpm, tracks["plan"], lengths)
    written = ["".join(line) for line in section_lines(DEFAULT_LYRICS)["Verse"]]
    assert [karaoke.text(line) for line in found[:len(written)]] == written
    for line in found:
        starts = [syl[0] for syl in line["syllables"]]
        assert starts == sorted(starts) and line["start"] == starts[0] and line["end"] >= starts[-1]
    assert [line["start"] for line in found] == sorted(line["start"] for line in found)


def test_without_line_lengths_a_pause_starts_a_new_line():
    notes = [note(0, 0.4), note(0.5, 0.9), note(2.0, 2.4), note(2.5, 2.9)]     # 120 BPM: ein Schlag = 0,5 s
    found = karaoke.lines(notes, ["か", "な", "は", "な"], 120)
    assert [karaoke.text(line) for line in found] == ["かな", "はな"]


def test_a_melisma_lengthens_the_syllable_before():
    notes = [note(0, 0.5), note(0.5, 1.0), note(1.0, 1.5)]
    found = karaoke.lines(notes, ["そ", Mora("お", melisma=True), "ら"], 120)
    assert found[0]["syllables"] == [[0.0, 1.0, "そ"], [1.0, 1.5, "ら"]]


def test_repeated_lyrics_start_their_lines_again():
    notes = [note(i * 0.25, i * 0.25 + 0.2) for i in range(10)]
    found = karaoke.lines(notes, list("あいうえおあいうえお"), 120, line_lengths={"": [3, 2]})
    assert [karaoke.text(line) for line in found] == ["あいう", "えお", "あいう", "えお"]


def test_long_lines_are_split_at_the_longest_pause():
    notes = [note(i * 0.2, i * 0.2 + 0.15) for i in range(12)] + [note(3.0 + i * 0.2, 3.15 + i * 0.2) for i in range(12)]
    found = karaoke.lines(notes, ["ら"] * 24, 60)       # 60 BPM: die Pause ist kürzer als ein Schlag
    assert [len(line["syllables"]) for line in found] == [12, 12]


def test_lyrics_file_round_trip(tmp_path):
    path = str(tmp_path / karaoke.FILE)
    found = [{"start": 1.0, "end": 2.0, "syllables": [[1.0, 2.0, "あ"]]}]
    karaoke.save(path, found)
    assert karaoke.load(path) == found
    assert karaoke.load(str(tmp_path / "fehlt.json")) == []


def test_subtitles_color_each_syllable_in_time():
    found = [{"start": 2.0, "end": 3.0, "syllables": [[2.0, 2.5, "よ"], [2.5, 3.0, "{る}"]]},
             {"start": 4.0, "end": 5.0, "syllables": [[4.0, 5.0, "の"]]}]
    text = karaoke.ass(found, title="J-Pop Energy · 160 BPM")
    events = [line for line in text.splitlines() if line.startswith("Dialogue:")]
    assert sum(",Line," in e for e in events) == 2 and sum(",Next," in e for e in events) == 1
    assert sum(",Title," in e for e in events) == 1
    first = next(e for e in events if ",Line," in e)
    assert "0:00:01.00,0:00:03.00" in first                       # erscheint eine Sekunde vorher
    assert "{\\k100}{\\kf50}よ{\\kf50}(る)" in first               # Vorlauf, dann Silbe für Silbe
    assert "{\\pos(" in first and "Fontname" in text


def test_the_video_needs_ffmpeg_and_lyrics(tmp_path, monkeypatch):
    monkeypatch.setattr(karaoke, "find_ffmpeg", lambda: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        karaoke.video("song.wav", [{"start": 0, "end": 1, "syllables": [[0, 1, "あ"]]}], str(tmp_path / "v.mp4"))
    with pytest.raises(RuntimeError, match="Text"):
        karaoke.video("song.wav", [], str(tmp_path / "v.mp4"), ffmpeg="ffmpeg")


@pytest.mark.skipif(not has_ffmpeg_with_subtitles(), reason="ffmpeg mit libass fehlt")
def test_lyric_video_is_rendered(tmp_path):
    rate = 22050
    t = np.arange(3 * rate) / rate
    audio = tmp_path / "song.wav"
    sf.write(str(audio), (0.3 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), rate)
    found = [{"start": 0.5, "end": 2.5, "syllables": [[0.5, 1.5, "よ"], [1.5, 2.5, "る"]]}]
    out = karaoke.video(str(audio), found, str(tmp_path / "video" / "lyric_video.mp4"), "Test")
    assert os.path.getsize(out) > 5000
    assert os.path.exists(tmp_path / "video" / "lyric_video.ass")


def test_the_pipeline_writes_the_lyrics_and_builds_the_video_from_them(tmp_path, monkeypatch):
    s = make_settings(tmp_path)
    tracks, _ = compose(s)
    out = s.output_dir()
    pipeline._write_karaoke(s, tracks, out)
    found = karaoke.load(os.path.join(out, karaoke.FILE))
    assert found and karaoke.text(found[0]) == "".join(section_lines(DEFAULT_LYRICS)["Verse"][0])
    mp3 = tmp_path / "out" / "final_song.mp3"
    mp3.write_bytes(b"ID3")
    seen = {}
    monkeypatch.setattr(karaoke, "video", lambda audio, lines, path, title="": seen.update(
        audio=audio, lines=lines, path=path, title=title) or path)
    path = pipeline.lyric_video(SongResult(seed=21, output_dir=out, mp3=str(mp3), settings=s))
    assert path == os.path.join(out, "lyric_video.mp4") and seen["lines"] == found
    assert seen["title"].startswith(s.style)


# ── Nur neu rendern, was sich geändert hat ─────────────────────────────────────────
@pytest.fixture
def counted_renders(monkeypatch):
    import mixer
    rendered = []

    def fake_render(midi_pfad, wav_pfad, **kwargs):
        rendered.append(os.path.basename(midi_pfad)[:-4])
        sf.write(wav_pfad, np.zeros((100, 2), dtype=np.float32), 44100)

    monkeypatch.setattr(mixer, "midi_zu_wav", fake_render)
    return rendered


def test_unchanged_tracks_are_not_rendered_again(tmp_path, counted_renders):
    s = make_settings(tmp_path)
    tracks, _ = compose(s)
    out = s.output_dir()
    first = pipeline._render_instruments(s, tracks, out, lambda f, m: None)
    active = sorted(counted_renders)
    assert active and sorted(first) == active

    counted_renders.clear()
    again = pipeline._render_instruments(s, tracks, out, lambda f, m: None)
    assert counted_renders == [] and again == first

    rerolled = s.rerolled("drums")
    tracks, _ = compose(rerolled)
    pipeline._render_instruments(rerolled, tracks, out, lambda f, m: None)
    assert counted_renders == ["drums"]

    counted_renders.clear()
    louder = rerolled.with_updates(guitar_amp=False)        # ein anderer Klang: alles neu
    pipeline._render_instruments(louder, tracks, out, lambda f, m: None)
    assert sorted(counted_renders) == active


def test_a_switched_off_track_leaves_no_old_wav(tmp_path, counted_renders):
    s = make_settings(tmp_path)
    tracks, _ = compose(s)
    out = s.output_dir()
    pipeline._render_instruments(s, tracks, out, lambda f, m: None)
    channels = {ch: data.model_dump() for ch, data in s.channels.items()}
    channels["piano"]["enabled"] = False
    without_piano = s.with_updates(channels=channels)
    files = pipeline._render_instruments(without_piano, tracks, out, lambda f, m: None)
    assert "piano" not in files and not os.path.exists(os.path.join(out, "piano.wav"))


# ── Länge der Sektionen ─────────────────────────────────────────────────────────────
def test_section_lengths(tmp_path):
    s = make_settings(tmp_path, section_bars={"Chorus": 8, "Intro": 2, "Kazoo": 4, "Verse": 0})
    assert s.section_bars == {"Chorus": 8, "Intro": 2}
    assert s.section_config()["Chorus"]["bars"] == 8 and s.section_config()["Verse"]["bars"] == 16
    plan = compose(s)[0]["plan"]
    assert {sec.kind: sec.bars for sec in plan.sections}["Chorus"] == 8
    assert {sec.kind: sec.bars for sec in plan.sections}["Intro"] == 2


# ── Von Hand geänderte Töne ─────────────────────────────────────────────────────────
def chorus_notes(tracks):
    plan = tracks["plan"]
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    spb = plan.seconds_per_beat
    return [n for n in tracks["vocal_melody"] if chorus.start <= n.start / spb < chorus.end], spb


def test_edited_notes_are_sung_and_the_rest_stays(tmp_path):
    s = make_settings(tmp_path)
    before, _ = compose(s)
    notes, spb = chorus_notes(before)
    target = notes[2]
    key = edit_key(target.start / spb)
    after, _ = compose(s.with_updates(melody_edits={key: target.pitch + 3}))
    changed = [(a.start, a.pitch, b.pitch) for a, b in zip(before["vocal_melody"], after["vocal_melody"])
               if a.pitch != b.pitch]
    assert changed == [(target.start, target.pitch, target.pitch + 3)]
    assert before["harmony_data"] != after["harmony_data"]          # die zweite Stimme folgt
    for inst in ("drums", "bass", "piano"):
        assert [(n.start, n.pitch) for n in before[inst]] == [(n.start, n.pitch) for n in after[inst]]


def test_edits_are_checked_and_dropped_with_a_new_melody():
    s = SongSettings(seed=3, melody_edits={"12.26": 200, "3": -4, "x": 60})
    assert s.melody_edits == {"12.25": 127, "3": 0}
    assert s.rerolled("bass").melody_edits == s.melody_edits
    assert s.rerolled("melody").melody_edits == {} and s.rerolled("chords:Chorus").melody_edits == {}


# ── Kommandozeile ───────────────────────────────────────────────────────────────────
@pytest.fixture
def captured(monkeypatch, tmp_path):
    seen = {}

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        return SongResult(seed=settings.seed or 1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"),
                          settings=settings)

    monkeypatch.setattr(main, "generate_song", fake_generate)
    return seen


def test_cli_section_lengths_and_video(captured, monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(main, "lyric_video", lambda result, path=None: made.append(path) or "video.mp4")
    assert main.main(["--takte", "Chorus=8", "--takte", "Intro=2", "--lyric-video"]) == 0
    assert captured["settings"].section_bars == {"Chorus": 8, "Intro": 2}
    assert made == [None]
    assert main.main(["--lyric-video", str(tmp_path / "v.mp4")]) == 0 and made[-1] == str(tmp_path / "v.mp4")


@pytest.mark.parametrize("value", ["Chorus=0", "Chorus=acht", "Refrain=8", "Chorus"])
def test_cli_rejects_bad_lengths(captured, value):
    with pytest.raises(SystemExit):
        main.main(["--takte", value])


def test_cli_video_failure_is_reported(captured, monkeypatch):
    def fail(result, path=None):
        raise RuntimeError("Für das Lyric-Video fehlt ffmpeg")
    monkeypatch.setattr(main, "lyric_video", fail)
    assert main.main(["--lyric-video"]) == 1


def test_instruments_constant_is_complete():
    assert "drums" in INSTRUMENTS

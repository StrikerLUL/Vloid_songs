# test_remix.py – Remix in einem anderen Stil (v6 Nr. 8): Melodie, Text und Akkorde bleiben, die Band wechselt
import pytest

import main
import pipeline
import vorlagen
from preset_manager import PRESETS
from settings import SongSettings

SECTIONS = ["Intro", "Verse", "Chorus", "Outro"]


def song(**kw):
    return SongSettings(seed=11, active_sections=SECTIONS, **kw)


def chords(tracks):
    return [(slot.start, slot.chord) for sec in tracks["plan"].sections for slot in sec.chords]


def notes(tracks, inst):
    return [(round(n.start, 4), n.pitch) for n in tracks[inst]]


@pytest.mark.parametrize("style", ["Lo-Fi", "Rock", "Future Bass"])
def test_the_remix_keeps_melody_lyrics_and_chords_and_changes_the_band(style):
    original = song()
    before, _ = pipeline.compose(original)
    remixed = pipeline.remix(original, style)
    assert (remixed.style, remixed.bpm) == (style, PRESETS[style]["bpm"])
    assert (remixed.remix_from, remixed.remix_bpm) == ("J-Pop Energy", 160)
    assert remixed.singer == original.singer and remixed.key == original.key
    assert {ch: c.volume for ch, c in remixed.channels.items() if ch in PRESETS[style]["volumes"]} == \
        PRESETS[style]["volumes"]
    after, _ = pipeline.compose(remixed)
    assert after["melody_data"] == before["melody_data"] and after["silben"] == before["silben"]
    assert chords(after) == chords(before)
    assert after["plan"].style.name == style and after["plan"].bpm == remixed.bpm
    assert notes(after, "drums") != notes(before, "drums")
    assert after["drums"][-1].end != pytest.approx(before["drums"][-1].end)       # anderes Tempo


def test_a_remix_of_a_remix_starts_from_the_song_and_its_style_brings_it_back():
    original = song()
    before, _ = pipeline.compose(original)
    twice = pipeline.remix(pipeline.remix(original, "Rock"), "Lo-Fi")
    assert (twice.remix_from, twice.remix_bpm) == ("J-Pop Energy", 160)
    back = pipeline.remix(twice, "J-Pop Energy")
    assert (back.style, back.bpm, back.remix_from, back.remix_bpm) == ("J-Pop Energy", 160, "", 0)
    again, _ = pipeline.compose(back.with_updates(channels=original.channels))
    for inst in ("drums", "bass", "piano"):
        assert notes(again, inst) == notes(before, inst)


def test_a_remix_needs_a_song_and_counts_dotted_quarters_in_six_eight():
    with pytest.raises(ValueError):
        pipeline.remix(SongSettings(), "Rock")
    waltz = pipeline.remix(song(meter="6/8", bpm=60), "Rock")
    assert waltz.bpm == round(PRESETS["Rock"]["bpm"] / 1.5) and waltz.remix_bpm == 60


def test_the_command_line_and_templates(tmp_path, monkeypatch):
    assert main.parse_args(["--remix", "Rock", "--seed", "3"]).remix == "Rock"
    assert "remix_from" in vorlagen.NOT_IN_TEMPLATE and "remix_bpm" in vorlagen.NOT_IN_TEMPLATE
    made = []
    monkeypatch.setattr(main, "generate_song", lambda s, *a, **k: made.append(s))
    assert main.main(["--remix", "Rock"]) == 1                     # ohne Seed gibt es keinen Song zum Remixen
    assert made == []

# test_vocal_chops.py – Vocal Chops im Drop (v6 Nr. 14): Schnipsel der Hauptstimme, geschnitten und umgestimmt
import os

import numpy as np
import pytest
import soundfile as sf

import main
import mixer
import pipeline
import vocal_chops
from pipeline import SongResult
from settings import SongSettings

SECTIONS = ["Intro", "Verse", "Chorus", "Drop", "Chorus"]
REAL_STYLES = dict(vocal_chops.CHOP_STYLES)        # beim Einlesen noch nicht von conftest abgeschaltet
RATE = 48000


@pytest.fixture
def chops_on(monkeypatch):
    monkeypatch.setattr(vocal_chops, "CHOP_STYLES", REAL_STYLES)


def compose(style="Future Bass", meter="4/4", **kw):
    s = SongSettings(active_sections=SECTIONS, section_bars={"Intro": 2, "Verse": 4, "Chorus": 4, "Drop": 2},
                     seed=5, style=style, meter=meter, **kw)
    return s, pipeline.compose(s)[0]


def hz(pitch):
    return 440.0 * 2 ** ((pitch - 69) / 12)


def sung(tracks, bpm, path):
    """Ein Gesang aus Sinustönen: jeder Ton klingt auf seiner Tonhöhe, so lässt sich das Umstimmen nachmessen."""
    spb = 60.0 / bpm
    total = sum(d for _, d in tracks["melody_data"]) * spb
    audio = np.zeros(int(total * RATE) + RATE, dtype=np.float32)
    t = 0.0
    for pitch, dur in tracks["melody_data"]:
        if pitch is not None:
            a, b = int(t * spb * RATE), int((t + dur) * spb * RATE)
            audio[a:b] = 0.3 * np.sin(2 * np.pi * hz(pitch) * np.arange(b - a) / RATE)
        t += dur
    sf.write(path, audio, RATE)
    return path


def test_the_riff_ends_each_section_with_a_stutter(chops_on):
    _, tracks = compose()
    plan = tracks["plan"]
    drop = next(sec for sec in plan.sections if sec.kind == "Drop")
    riff = vocal_chops.hits(plan, drop)
    assert [round(t - drop.start, 2) for t, _, _ in riff] == \
        [t for t, _ in vocal_chops.PATTERN] + [4 + t for t, _ in vocal_chops.STUTTER]
    assert [k for _, _, k in riff[:3]] == [0, 1, 2]
    assert [sec.kind for sec in vocal_chops.sections(plan)] == ["Intro", "Drop"]       # Future Bass auch im Intro
    _, tracks = compose("J-Pop Energy")
    assert [sec.kind for sec in vocal_chops.sections(tracks["plan"])] == ["Drop"]
    _, tracks = compose("Ballade")
    assert vocal_chops.sections(tracks["plan"]) == []


@pytest.mark.parametrize("meter, bar", [("3/4", 3), ("6/8", 2)])
def test_the_riff_keeps_to_the_meter(chops_on, meter, bar):
    _, tracks = compose(meter=meter)
    plan = tracks["plan"]
    drop = next(sec for sec in plan.sections if sec.kind == "Drop")
    riff = vocal_chops.hits(plan, drop)
    assert riff and all(drop.start <= t and t + d <= drop.end + 1e-6 for t, d, _ in riff)
    assert all((t - drop.start) % bar < bar for t, _, _ in riff)
    if meter == "6/8":
        assert [round((t - drop.start) % bar, 3) for t, _, _ in riff[:4]] == [0, 0.667, 1, 1.667]


def test_chops_play_only_in_the_drop_and_on_the_chord_tones(chops_on, tmp_path):
    s, tracks = compose()
    plan = tracks["plan"]
    vocals = sung(tracks, s.bpm, str(tmp_path / "vocals.wav"))
    path = vocal_chops.render(plan, tracks["melody_data"], tracks["silben"], s.bpm, vocals, str(tmp_path / "chops.wav"))
    audio, rate = sf.read(path, always_2d=True)
    assert rate == RATE and audio.shape[1] == 2
    spb = 60.0 / s.bpm
    places = [(sec.start * spb, sec.end * spb) for sec in vocal_chops.sections(plan)]
    loud = np.abs(audio).max(axis=1) > 1e-4
    seconds = np.flatnonzero(loud) / rate
    assert all(any(a - 0.01 <= x <= b + 0.5 for a, b in places) for x in seconds[::500])
    drop = next(sec for sec in plan.sections if sec.kind == "Drop")
    pieces = vocal_chops.snippets(sf.read(vocals)[0], RATE, tracks["melody_data"], tracks["silben"], s.bpm, plan)
    center = int(np.median([p for _, p in pieces]))
    for beat, dur, k in vocal_chops.hits(plan, drop)[:4]:
        target = vocal_chops.pitch(plan, beat, k, center)
        assert target % 12 in plan.chord_at(beat).pcs
        a = int((beat * spb + 0.01) * rate)
        piece = audio[a:a + int(0.08 * rate)].mean(axis=1)
        spectrum = np.abs(np.fft.rfft(piece * np.hanning(len(piece)), 8 * len(piece)))
        found = np.argmax(spectrum) * rate / (8 * len(piece))
        assert found == pytest.approx(hz(target), rel=0.03)


def test_without_a_drop_or_a_long_note_there_are_no_chops(chops_on, tmp_path):
    s, tracks = compose("Ballade")
    vocals = sung(tracks, s.bpm, str(tmp_path / "vocals.wav"))
    assert vocal_chops.render(tracks["plan"], tracks["melody_data"], tracks["silben"], s.bpm, vocals,
                              str(tmp_path / "a.wav")) is None
    s, tracks = compose()
    sf.write(str(tmp_path / "still.wav"), np.zeros(RATE * 60, dtype=np.float32), RATE)
    assert vocal_chops.render(tracks["plan"], tracks["melody_data"], tracks["silben"], s.bpm,
                              str(tmp_path / "still.wav"), str(tmp_path / "b.wav")) is None


def test_the_song_mixes_the_chops_only_with_the_switch(chops_on, tmp_path):
    s, tracks = compose()
    out = str(tmp_path)
    result = SongResult(seed=5, output_dir=out, settings=s, vocals_wav=sung(tracks, s.bpm, str(tmp_path / "vocals.wav")))
    assert pipeline._vocal_chops(s, tracks, result, out) == [os.path.join(out, vocal_chops.FILE)]
    assert mixer._track_key(os.path.join(out, vocal_chops.FILE)) == "chops"
    assert pipeline._vocal_chops(s.with_updates(vocal_chops=False), tracks, result, out) == []
    assert not os.path.exists(os.path.join(out, vocal_chops.FILE))           # alte Chops verschwinden
    assert main.parse_args(["--ohne-chops"]).ohne_chops and SongSettings().vocal_chops

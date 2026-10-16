# test_idol_rufe.py – Idol-Rufe (v6 Nr. 15): „はい！はい！“ mehrerer Stimmen in den Lücken des Refrains
import os

import numpy as np
import pytest
import soundfile as sf

import backing_vocals
import main
import mixer
import pipeline
import singing
import vocal_synthesizer
from settings import SongSettings

SECTIONS = ["Verse", "Chorus", "Verse", "Chorus", "Chorus"]
REAL_CALLS = dict(backing_vocals.IDOL_CALLS)          # beim Einlesen noch nicht von conftest abgeschaltet


@pytest.fixture
def calls_on(monkeypatch):
    monkeypatch.setattr(backing_vocals, "IDOL_CALLS", REAL_CALLS)


def compose(style, meter="4/4", **kw):
    tracks, _ = pipeline.compose(SongSettings(active_sections=SECTIONS, seed=3, style=style, meter=meter, **kw))
    return tracks, backing_vocals.notes_of(tracks["melody_data"], tracks["silben"])


def per_chorus(plan, calls):
    return [[n for n in calls if sec.start - 1.0 <= n.start < sec.end] for sec in backing_vocals.choruses(plan)]


@pytest.mark.parametrize("meter", ["4/4", "3/4"])
def test_idol_pop_calls_on_free_offbeats_in_every_chorus(calls_on, meter):
    tracks, notes = compose("Idol-Pop", meter)
    plan = tracks["plan"]
    calls = backing_vocals.notes_of(tracks["call_data"], tracks["call_silben"])
    assert [c.start for c in calls] == pytest.approx([c.start for c in backing_vocals.calls(plan, notes)])
    assert all(found for found in per_chorus(plan, calls))
    lo, hi = plan.vocal_range
    offbeats = (1, 3) if meter == "4/4" else (1, 2)
    for c in calls:
        assert not any(n.start < c.start + c.dur - 1e-6 and n.start + n.dur > c.start + 1e-6 for n in notes)
        assert lo - 5 <= c.pitch <= hi
        if str(c.syllable) == "は":
            sec = plan.section_at(c.start)
            assert sec.kind == "Chorus" and round(c.start - sec.start) % plan.bar_beats in offbeats
            assert c.pitch % 12 in plan.chord_at(c.start).pcs
    text = "".join(str(c.syllable) for c in calls)
    assert text.startswith("ふふ") and "はい" in text                      # „ふっふー“ in den Refrain hinein
    first = backing_vocals.choruses(plan)[0]
    assert calls[0].start == pytest.approx(first.start - 1.0)


def test_at_most_two_calls_in_a_row(calls_on):
    from melody_writer import MelNote
    tracks, _ = compose("Idol-Pop")
    plan = tracks["plan"]
    last = backing_vocals.choruses(plan)[-1]
    # die Hauptstimme singt nur auf jedem vierten Takt: lange Lücken
    sparse = [MelNote(last.start + 16 * k, 4.0, 64, "ら") for k in range(4)]
    calls = [c for c in backing_vocals.calls(plan, sparse) if str(c.syllable) == "は" and c.start >= last.start]
    gaps = [b.start - a.start for a, b in zip(calls, calls[1:])]
    assert len(calls) == 8 and gaps.count(2.0) == 4                   # je Lücke zwei, dann Ruhe


def test_jpop_and_rock_call_only_in_the_last_chorus_and_ballads_never(calls_on):
    for style, word in (("J-Pop Energy", "はい"), ("Rock", "おい")):
        tracks, notes = compose(style)
        calls = backing_vocals.calls(tracks["plan"], notes)
        *earlier, last = per_chorus(tracks["plan"], calls)
        assert word in "".join(str(c.syllable) for c in last)
        assert not any(str(c.syllable) in "はお" for found in earlier for c in found)
    tracks, _ = compose("Ballade")
    assert "call_data" not in tracks


def test_without_the_switch_there_are_no_calls(calls_on):
    tracks, _ = compose("Idol-Pop", idol_calls=False)
    assert "call_data" not in tracks
    assert main.parse_args(["--ohne-idol-rufe"]).ohne_idol_rufe and SongSettings().idol_calls


# ── gesungen ───────────────────────────────────────────────────────────────────
@pytest.fixture
def neutrino(tmp_path, monkeypatch):
    root = tmp_path / "NEUTRINO"
    for name in ("MERROW", "KIRITAN", "ITAKO"):
        (root / "model" / name).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    sung = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        sung.append((os.path.basename(xml), os.path.basename(model_dir), style_shift))
        t = np.arange(48000 * 3) / 48000
        sf.write(wav, 0.2 * np.sin(2 * np.pi * (300 + 20 * len(sung)) * t), 48000)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, sung


def _sing(tmp_path, root, **kw):
    s = SongSettings(active_sections=SECTIONS, output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), seed=3,
                     style="Idol-Pop", final_choir=False, harmonies=False, sung_pads=False, adlibs=False, **kw)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    singing._synthesize_vocals(s, tracks, out)
    return out


def test_several_voices_shout_the_calls(tmp_path, calls_on, neutrino):
    root, sung = neutrino
    out = _sing(tmp_path, root, singer="MERROW")
    calls = [(model, shift) for xml, model, shift in sung if xml.startswith("vocals_rufe_")]
    assert [model for model, _ in calls] == ["MERROW", "ITAKO", "KIRITAN"]       # die Hauptstimme und zwei weitere
    audio, _ = sf.read(os.path.join(out, "vocals_rufe.wav"))
    assert audio.ndim == 2 and not np.allclose(audio[:, 0], audio[:, 1])          # links und rechts verschieden
    assert [f for f in os.listdir(out) if f.startswith("vocals_rufe_")] == []
    assert mixer._track_key(os.path.join(out, "vocals_rufe.wav")) == "gang"
    assert "vocals_rufe.wav" in singing.VOCAL_FILES


def test_alone_the_singer_shouts_brighter_and_darker(tmp_path, calls_on, neutrino):
    root, sung = neutrino
    for name in ("KIRITAN", "ITAKO"):
        (root / "model" / name).rmdir()
    _sing(tmp_path, root, singer="MERROW")
    shifts = [shift for xml, model, shift in sung if xml.startswith("vocals_rufe_")]
    assert len(shifts) == 3 == len(set(shifts))

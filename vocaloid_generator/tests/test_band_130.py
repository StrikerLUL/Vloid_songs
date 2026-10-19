# test_band_130.py – Band 1.3.0: Kime und Fills (I2), Intro-Riff (I1), Groove (I3), Bass-Läufe (I4), Läufe (I5),
# Anison-Grooves (I6), Aufbau in der Sektion (I7)
import pytest

import config
import kime
import pipeline
from orchestrator import orchestrate_song
from pipeline import seed_everything
from settings import SongSettings

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Outro"]
BPM = 120
SPB = 60 / BPM


def _song(tmp_path, extras=(), style="J-Pop Energy", seed=7, structure=STRUCTURE):
    seed_everything(seed)
    return orchestrate_song(genre="J-Pop", bpm=BPM, structure=list(structure), key="C", mode="major",
                            section_config=config.SECTION_CONFIG, output_dir=str(tmp_path), style=style,
                            extras={name: True for name in extras})


def _beats(notes, start, end):
    """Töne, die zwischen den Schlägen start und end anfangen, als (Schlag, Tonhöhe)."""
    return [(round(n.start / SPB * 4) / 4, n.pitch) for n in notes if start - 0.06 <= n.start / SPB < end - 0.06]


def test_the_band_plays_kime_stops_and_fills(tmp_path, monkeypatch, new_composition):
    monkeypatch.setattr(kime, "PRE_KIME", 1.0)
    monkeypatch.setattr(kime, "VERSE_STOP", 1.0)
    monkeypatch.setattr(kime, "PHRASE_FILL", 1.0)
    tracks = _song(tmp_path, ["kime"])
    plain = _song(tmp_path / "ohne")
    plan = tracks["plan"]
    pre = next(sec for sec in plan.sections if sec.kind == "PreChorus")
    bar = pre.end - 4
    onsets = {b - bar for inst in ("piano", "bass", "guitar") for b, _ in _beats(tracks[inst], bar, pre.end)}
    assert onsets and len(onsets) <= 5, "alle spielen dieselben Akzente"
    assert len({b - bar for b, _ in _beats(plain["piano"], bar, pre.end)}) > len(onsets)
    crashes = [b for b, p in _beats(tracks["drums"], bar, pre.end) if p == 49]
    assert len(crashes) >= 3
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    stop = verse.start + 7 * 4 + 2
    for inst in ("piano", "bass", "guitar"):
        assert [b for b, _ in _beats(tracks[inst], stop, stop + 2)] in ([], [stop] * len(_beats(tracks[inst], stop,
                                                                                            stop + 2)))
    assert tracks["melody_data"] == plain["melody_data"], "der Gesang bleibt"
    # aus: der Song bleibt wie in 1.2
    s = SongSettings(output_ordner=str(tmp_path / "s"), seed=3)
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(kime=False))
    assert [(n.start, n.pitch) for n in on["piano"]] != [(n.start, n.pitch) for n in off["piano"]]


def test_phrase_fills_run_to_the_next_chord(tmp_path, monkeypatch, new_composition):
    monkeypatch.setattr(kime, "PRE_KIME", 0.0)
    monkeypatch.setattr(kime, "PRE_STOP", 0.0)
    monkeypatch.setattr(kime, "VERSE_STOP", 0.0)
    monkeypatch.setattr(kime, "PHRASE_FILL", 1.0)
    seen = {}
    real = kime.apply
    monkeypatch.setattr(kime, "apply", lambda *a: seen.setdefault("done", real(*a)))
    tracks = _song(tmp_path, ["kime"])
    fills = seen["done"]["fills"]
    assert fills and all(inst in kime.FILLERS for inst, _ in fills)
    inst, bar = fills[0]
    run = sorted(_beats(tracks[inst], bar + 3, bar + 4))
    assert len(run) >= 3
    assert all(b >= bar + 3 - 0.05 for b, _ in run)
    pitches = [p for _, p in run]
    assert pitches == sorted(pitches) or pitches == sorted(pitches, reverse=True), "ein Lauf in eine Richtung"


def test_the_song_has_its_own_riff_and_an_interlude(tmp_path, new_composition):
    import riff
    tracks = _song(tmp_path, ["intro_riff"])
    plain = _song(tmp_path / "ohne")
    plan = tracks["plan"]
    kinds = [sec.kind for sec in plan.sections]
    assert kinds == STRUCTURE[:4] + ["Interlude"] + STRUCTURE[4:]
    intro, interlude, outro = (next(s for s in plan.sections if s.kind == k) for k in ("Intro", "Interlude", "Outro"))
    lead = tracks["melody"]
    in_intro = _beats(lead, intro.start, intro.end)
    assert in_intro and in_intro != _beats(plain["melody"], intro.start, intro.end), "nicht die Refrain-Melodie"
    figure = [(b - intro.start, p) for b, p in in_intro if b < intro.start + 8]
    again = [(b - intro.start - 8, p) for b, p in in_intro if b >= intro.start + 8]
    assert [b for b, _ in figure] == [b for b, _ in again][:len(figure)], "die Figur kehrt wieder"
    assert _beats(lead, interlude.start, interlude.end) and _beats(lead, outro.start, outro.end)
    for b, p in in_intro:                 # betonte Töne (auf 1 und 3) liegen im Akkord
        if b % 2 == 0:
            assert p % 12 in plan.chord_at(b).pcs
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    quiet = [n.velocity for n in lead if last.start + last.beats / 2 <= n.start / SPB < last.end]
    loud = sorted(n.velocity for n in lead if intro.start <= n.start / SPB < intro.end)
    assert quiet and max(quiet) < loud[len(loud) // 2], "im letzten Refrain leise"
    assert riff.with_interlude(["Intro", "Chorus", "Outro"]) == ["Intro", "Chorus", "Outro"]
    # aus: Intro wie bisher, kein Zwischenspiel
    s = SongSettings(output_ordner=str(tmp_path / "s"), seed=3)
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(intro_riff=False))
    assert "Interlude" in [x.kind for x in on["plan"].sections]
    assert "Interlude" not in [x.kind for x in off["plan"].sections]

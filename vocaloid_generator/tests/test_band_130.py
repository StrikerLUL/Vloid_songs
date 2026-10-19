# test_band_130.py – Band 1.3.0: Kime und Fills (I2), Intro-Riff (I1), Groove (I3), Bass-Läufe (I4), Läufe (I5),
# Anison-Grooves (I6), Aufbau in der Sektion (I7)
import copy
import random

import pytest

import anison
import band_runs
import bass_runs
import buildup
import config
import drums
import groove_feel
import kime
import pipeline
from parts import Ev
from orchestrator import orchestrate_song
from pipeline import seed_everything
from settings import SongSettings

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Outro"]
BPM = 120
SPB = 60 / BPM


def _song(tmp_path, extras=(), style="J-Pop Energy", seed=7, structure=STRUCTURE, bpm=BPM):
    seed_everything(seed)
    return orchestrate_song(genre="J-Pop", bpm=bpm, structure=list(structure), key="C", mode="major",
                            section_config=config.SECTION_CONFIG, output_dir=str(tmp_path), style=style,
                            extras={name: True for name in extras})


def _capture(monkeypatch, module, name="apply"):
    """Ruft module.name wie sonst auf und hebt die Töne davor und danach auf (Schläge, vor Swing und Takt)."""
    seen = {}
    real = getattr(module, name)

    def wrapper(*args):
        events = next(a for a in args if isinstance(a, dict))
        seen["plan"] = next((a for a in args if hasattr(a, "sections")), None)
        seen["before"] = {k: [copy.copy(e) for e in v] for k, v in events.items()}
        seen["done"] = real(*args)
        seen["after"] = {k: [copy.copy(e) for e in v] for k, v in events.items()}
        return seen["done"]
    monkeypatch.setattr(module, name, wrapper)
    return seen


def _at(evs, start, end, layer=None):
    return sorted((e for e in evs if start - 1e-6 <= e.start < end - 1e-6 and (layer is None or e.layer == layer)),
                  key=lambda e: (e.start, e.pitch))


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


def test_the_band_plays_in_the_pocket_of_the_drummer(tmp_path, new_composition):
    kick, snare, hat = drums.KICK, drums.SNARE, drums.HAT
    events = {"drums": [Ev(0.03, 0.2, kick, 120), Ev(0.5, 0.1, hat, 50), Ev(1.02, 0.2, snare, 110),
                        Ev(1.5, 0.1, hat, 50), Ev(8.03, 0.2, kick, 120)],
              "bass": [Ev(0.0, 0.5, 36, 80), Ev(0.5, 0.5, 36, 80), Ev(0.75, 0.25, 36, 80), Ev(8.0, 1.0, 36, 80)],
              "piano": [Ev(0.0, 1.0, 60, 70), Ev(1.0, 1.0, 64, 70)], "melody": [Ev(0.0, 1.0, 72, 90)]}
    moved = groove_feel.apply(events, until=8.0)
    bass, piano = events["bass"], events["piano"]
    assert bass[0].start == pytest.approx(0.03), "der Bass liegt mit der Bassdrum knapp hinter dem Raster"
    assert piano[0].start == pytest.approx(0.03 * groove_feel.FOLLOWERS["piano"])
    assert piano[1].start == pytest.approx(1.0 + 0.02 * groove_feel.FOLLOWERS["piano"])
    assert bass[0].vel > bass[1].vel, "wo die Bassdrum spielt, betont die Band"
    assert bass[2].vel < 80, "wo das Schlagzeug schweigt, etwas leiser"
    assert bass[3].start == 8.0 and bass[3].vel == 80, "der Schlussakkord bleibt"
    assert events["melody"][0].start == 0.0, "die Leadmelodie hat ihr eigenes Timing"
    assert moved["bass"] == 1 and moved["piano"] == 2
    assert groove_feel.apply({"bass": [Ev(0.0, 1.0, 36, 80)]}) == {}
    # im Song: mit den eingebauten Grooves (genau im Raster) betont die Band, das Timing bleibt
    tracks = _song(tmp_path, ["band_groove"])
    plain = _song(tmp_path / "ohne")
    assert [n.velocity for n in tracks["bass"]] != [n.velocity for n in plain["bass"]]
    assert [round(n.start, 4) for n in tracks["bass"]] == [round(n.start, 4) for n in plain["bass"]]
    assert tracks["melody_data"] == plain["melody_data"]


def test_the_bass_runs_fills_jumps_octaves_and_plays_funk(tmp_path, monkeypatch, new_composition):
    for name in ("RUN_SHARE", "FILL_SHARE", "OCTAVE_SHARE", "FUNK_SHARE"):
        monkeypatch.setattr(bass_runs, name, 1.0)
    seen = _capture(monkeypatch, bass_runs)
    tracks = _song(tmp_path, ["bass_runs"])
    done, plan, before, after = seen["done"], seen["plan"], seen["before"]["bass"], seen["after"]["bass"]
    assert done["runs"] and done["fills"] and done["octaves"] and not done["funk"]
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    bar = verse.start + 3 * 4                      # Ende der ersten Vier-Takt-Phrase: Fill auf Schlag 4
    fill = _at(after, bar + 3, bar + 4)
    assert [e.start - bar for e in fill] == [3.0, 3.25, 3.5, 3.75]
    pitches = [e.pitch for e in fill]
    assert pitches == sorted(pitches, reverse=True), "Oktave, Septime, Quinte und zurück"
    runs = 0
    for sec in plan.sections:
        for b in range(1, sec.bars - 1, 2):
            bar = sec.start + b * 4
            if (b + 1) % 4 == 0:
                continue
            run, nxt = _at(after, bar + 3, bar + 4), _at(after, bar + 4, bar + 4.25)
            if len(run) < 2 or not nxt or len(_at(before, bar + 3, bar + 4)) >= len(run):
                continue
            steps = [b.pitch - a.pitch for a, b in zip(run, run[1:])]
            toward = nxt[0].pitch - run[0].pitch
            assert all(0 < abs(d) <= 2 and d * toward > 0 for d in steps), "Tonleiter in Richtung des Grundtons"
            assert abs(nxt[0].pitch - run[-1].pitch) <= 2
            runs += 1
    assert runs >= 2
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    was = {(e.start, e.pitch) for e in _at(before, chorus.start, chorus.end)}
    jumped = [e for e in _at(after, chorus.start, chorus.end) if (e.start, e.pitch - 12) in was and e.start % 1 == 0.5]
    assert jumped, "im Refrain springen Achtel auf dem „und“ in die Oktave"
    assert all(e.pitch <= bass_runs.HI for e in after)
    # City Pop: funkige Oktaven mit abgedämpften Tönen davor
    _song(tmp_path / "city", ["bass_runs"], style="City Pop")
    assert seen["done"]["funk"]
    city = seen["after"]["bass"]
    dead = [e for e in city if e.dur == bass_runs.DEAD_LEN]
    assert dead and any(o.pitch == d.pitch + 12 and abs(o.start - d.start - 0.25) < 1e-6 for d in dead for o in city)
    # aus: der Bass wie bisher, der Gesang bleibt
    plain = _song(tmp_path / "ohne")
    assert [(n.start, n.pitch) for n in tracks["bass"]] != [(n.start, n.pitch) for n in plain["bass"]]
    assert tracks["melody_data"] == plain["melody_data"]


def test_piano_and_strings_run_glide_and_play_the_hook(tmp_path, monkeypatch, new_composition):
    monkeypatch.setattr(band_runs, "PHRASE_RUN", 1.0)
    seen = _capture(monkeypatch, band_runs)
    tracks = _song(tmp_path, ["band_runs"])
    done, plan, after = seen["done"], seen["plan"], seen["after"]
    assert done["runs"] and done["glissandi"] and done["strings"] and done["hooks"]
    pre = next(sec for sec in plan.sections if sec.kind == "PreChorus")
    gliss = _at(after["piano"], pre.end - 2, pre.end, layer="gliss")
    assert len(gliss) == band_runs.GLISS_NOTES
    assert [e.pitch for e in gliss] == sorted(e.pitch for e in gliss) and gliss[-1].pitch - gliss[0].pitch >= 22
    up = [e for e in _at(after["strings"], pre.end - 2, pre.end) if not e.layer]
    land = [e for e in _at(after["strings"], pre.end, pre.end + 0.05) if not e.layer]
    if up:
        assert len(up) == band_runs.STRING_RUN and [e.pitch for e in up] == sorted(e.pitch for e in up)
        assert any(e.pitch % 12 == plan.chord_at(pre.end).root and e.pitch > up[-1].pitch for e in land)
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    half = chorus.start + chorus.bars // 2 * 4
    hook = _at(after["piano"], chorus.start, half, layer="hook")
    sung = {n.pitch % 12 for n in seen_vocal(tracks, chorus.start, half)}
    assert hook and {e.pitch % 12 for e in hook} <= sung, "das Klavier spielt die Melodie des Gesangs"
    assert all(any(o.pitch == e.pitch + 12 and o.start == e.start for o in hook) for e in hook[::2])
    assert not _at(after["piano"], half, chorus.end, layer="hook")
    plain = _song(tmp_path / "ohne")
    assert [(n.start, n.pitch) for n in tracks["piano"]] != [(n.start, n.pitch) for n in plain["piano"]]
    assert tracks["melody_data"] == plain["melody_data"]


def seen_vocal(tracks, start, end):
    return [n for n in tracks["vocal_melody"] if start - 0.01 <= n.start / SPB < end - 0.01]


def test_fast_anime_songs_get_anison_grooves_rolls_and_stops(tmp_path, monkeypatch, new_composition):
    for name in ("TWO_BEAT_SHARE", "DISCO_SHARE", "TOM_SHARE", "STOP_SHARE", "ROLL_SHARE"):
        monkeypatch.setattr(anison, name, 1.0)
    picked = []
    real = anison.groove_for
    monkeypatch.setattr(anison, "groove_for", lambda sec, *a: picked.append((sec.kind, sec.occurrence, real(sec, *a)))
                        or picked[-1][2])
    seen = _capture(monkeypatch, anison)
    structure = ["Intro", "Verse", "Chorus", "Verse", "PreChorus", "Chorus", "Outro"]
    tracks = _song(tmp_path, ["anison_grooves"], structure=structure, bpm=170)
    grooves = {(kind, n): g for kind, n, g in picked}
    assert grooves[("Chorus", 1)] == "two_beat" and grooves[("PreChorus", 1)] == "disco"
    assert grooves[("Verse", 1)] == "tom_verse" and grooves[("Verse", 2)] != "tom_verse"
    two = drums.GROOVES["two_beat"]
    assert [s for s, _ in two[drums.KICK]] == [0, 4, 8, 12] and [s for s, _ in two[drums.SNARE]] == [2, 6, 10, 14]
    plan, after = seen["plan"], seen["after"]
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    roll = [e for e in _at(after["drums"], verse.end - 2, verse.end) if e.pitch == drums.SNARE]
    assert len(roll) == 16 and roll[-1].vel > roll[0].vel, "Wirbel in den Refrain, immer lauter"
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    bar = chorus.end - 4
    assert seen["done"]["stops"] == [bar]
    assert {e.pitch for e in _at(after["drums"], bar, bar + 0.05)} == {drums.CRASH, drums.KICK}
    for inst, evs in after.items():
        if inst != "melody":
            assert not _at(evs, bar + 0.05, bar + 3), f"{inst} schweigt im Becken-Stopp"
    # langsam oder ein anderer Stil: wie bisher
    assert not anison.plays("Ballade", 170) and not anison.plays("J-Pop Energy", 120)
    picked.clear()
    _song(tmp_path / "langsam", ["anison_grooves"], structure=structure)
    assert all(g not in ("two_beat", "disco", "tom_verse") for _, _, g in picked)
    plain = _song(tmp_path / "ohne", structure=structure, bpm=170)
    assert [(n.start, n.pitch) for n in tracks["drums"]] != [(n.start, n.pitch) for n in plain["drums"]]
    assert tracks["melody_data"] == plain["melody_data"]


def test_the_first_verse_starts_alone_and_choruses_grow(tmp_path, monkeypatch, new_composition):
    seen = _capture(monkeypatch, buildup)
    tracks = _song(tmp_path, ["section_buildup"])
    done, plan, after = seen["done"], seen["plan"], seen["after"]
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    assert done["verse"] == verse.start
    enter = verse.start + buildup.WAIT_BARS * 4
    playing = {inst for inst, evs in after.items() if _at(evs, verse.start, enter - 1)}
    assert playing and playing <= set(buildup.ALONE), "die Strophe beginnt nur mit Klavier oder Gitarre"
    assert {e.pitch for e in _at(after["drums"], enter, enter + 0.05)} >= {drums.CRASH, drums.KICK}
    assert _at(after["bass"], enter, enter + 4), "danach spielt die Band"
    assert len(done["choruses"]) >= 1
    for half in done["choruses"]:
        chorus = next(sec for sec in plan.sections if sec.start < half < sec.end)
        layer = [e for evs in after.values() for e in _at(evs, chorus.start, chorus.end, layer="octave")]
        assert layer and min(e.start for e in layer) >= half - 1e-6, "die Schicht kommt in der zweiten Hälfte"
        assert any(e.pitch == drums.CRASH for e in _at(after["drums"], half, half + 0.05))
    plain = _song(tmp_path / "ohne")
    assert len(tracks["bass"]) < len(plain["bass"])
    assert tracks["melody_data"] == plain["melody_data"]

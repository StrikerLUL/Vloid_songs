# test_spannung_160.py – Die Spannungskurve (1.6.0): gezeichnete Energie je Sektion lenkt Schlagzeug, Besetzung und Mix
import random

import numpy as np
import pytest
import soundfile as sf

import config
import mixdown
import mixer
import pipeline
import spannung
from settings import SongSettings
from song_plan import BEATS_PER_BAR, build_plan
from styles import get_style


def _plan(structure: list):
    return build_plan(get_style("J-Pop Energy"), 160, structure, "A", "minor", config.SECTION_CONFIG,
                      random.Random(1))


def _by_key(plan) -> dict:
    return {spannung.key(sec.kind, sec.occurrence): sec for sec in plan.sections}


def test_without_a_drawing_and_with_the_mood_in_the_middle_the_song_stays_as_it_was():
    s = SongSettings()
    assert spannung.extras(s) is None and "tension" not in pipeline.composition_extras(s)
    assert spannung.extras(s.with_updates(tension_curve=False, mood=0.0, tension={"Chorus#2": 1.0})) is None
    plan = _plan(s.active_sections)
    before = [(sec.energy, sec.feel, sec.resume) for sec in plan.sections]
    assert spannung.apply(plan, None) == {"drawn": [], "breakdowns": [], "lifted": [], "thin": []}
    assert [(sec.energy, sec.feel, sec.resume) for sec in plan.sections] == before
    # die Regler stehen dort, wo build_plan die Energie hinlegt
    assert [p.value for p in spannung.points(s)] == [sec.energy for sec in plan.sections]
    assert not any(p.drawn for p in spannung.points(s))


def test_drawn_points_set_the_energy_the_mood_moves_the_rest():
    s = SongSettings(tension={"Verse#2": 0.15, "Chorus": 1.0}, mood=1.0)
    assert s.tension == {"Verse#2": 0.15, "Chorus#1": 1.0}       # ohne Nummer: das erste Vorkommen
    plan = _plan(s.active_sections)
    normal = {k: sec.energy for k, sec in _by_key(plan).items()}
    plan.sections[-2].feel, plan.sections[-2].resume = "breakdown", plan.sections[-2].start + 16  # gewürfelt
    wanted = {**spannung.extras(s), "drawn": {**s.tension, "Chorus#3": 0.9}}
    done = spannung.apply(plan, wanted)
    by = _by_key(plan)
    assert (by["Verse#2"].energy, by["Verse#2"].feel) == (0.15, "breakdown")
    assert by["Verse#2"].resume == by["Verse#2"].start + by["Verse#2"].bars // 2 * BEATS_PER_BAR
    assert by["Chorus#1"].energy == 1.0 and by["Chorus#3"].feel == "" and by["Chorus#3"].resume is None
    assert by["Verse#1"].energy == pytest.approx(normal["Verse#1"] + spannung.MOOD_SHIFT)
    assert by["Intro#1"].energy == 1.0                            # nie über 1
    assert done["breakdowns"] == ["Verse#2"] and done["lifted"] == ["Chorus#3"]
    assert done["thin"] == [(by["Verse#2"].start, by["Verse#2"].end)]
    calm = _plan(s.active_sections)
    done = spannung.apply(calm, spannung.extras(SongSettings(mood=0.0)))
    assert done["drawn"] == done["breakdowns"] == []
    quiet = [k for k, sec in _by_key(calm).items() if sec.energy < spannung.THIN_BELOW]
    assert {"Verse#1", "Verse#2", "Bridge#1"} <= set(quiet) and len(done["thin"]) == len(quiet)


def test_drawing_a_point_back_to_the_style_takes_it_out():
    s = SongSettings()
    s.tension = spannung.draw(s, "Chorus#2", 0.5)
    assert s.tension == {"Chorus#2": 0.5}
    assert next(p for p in spannung.points(s) if p.key == "Chorus#2").drawn
    s.tension = spannung.draw(s, "Bridge#1", 0.2)
    assert spannung.draw(s, "Chorus#2", 0.9) == {"Bridge#1": 0.2}
    moody = s.with_updates(mood=0.0)
    assert next(p for p in spannung.points(moody) if p.key == "Verse#1").normal == pytest.approx(0.2)


def test_with_the_tension_curve_drums_band_and_mix_follow_the_drawing(tmp_path):
    s = SongSettings(output_ordner=str(tmp_path), seed=4, tension_curve=True,
                     tension={"Verse#2": 0.15, "Chorus#1": 1.0, "Bridge#1": 0.2})
    on, _ = pipeline.compose(s)
    off, _ = pipeline.compose(s.with_updates(tension_curve=False))
    plan = on["plan"]
    spb = plan.seconds_per_beat
    by = _by_key(plan)

    def notes(tracks, inst, sec, until=None):
        a, b = sec.start * spb, (until or sec.end) * spb
        return [n for n in tracks[inst] if a - 1e-3 <= n.start < b - 1e-3]

    verse = by["Verse#2"]
    assert verse.feel == "breakdown" and _by_key(off["plan"])["Verse#2"].feel != "breakdown"
    assert len(notes(on, "drums", verse, verse.resume)) < len(notes(off, "drums", verse, verse.resume)) / 2
    loud = [n.velocity for n in notes(on, "drums", by["Chorus#1"])]
    normal = [n.velocity for n in notes(off, "drums", _by_key(off["plan"])["Chorus#1"])]
    assert np.mean(loud) > np.mean(normal)
    for sec in (verse, by["Bridge#1"]):
        assert sum(len(notes(on, inst, sec)) for inst in spannung.THIN) <= \
            sum(len(notes(off, inst, sec)) for inst in spannung.THIN)
        assert not notes(on, "brass", sec) and not notes(on, "counter", sec)
    # nur die Spannungskurve, ohne den Lautstärke-Bogen aus 1.7.0 (der hat eigene Tests in test_lyric_video_170)
    alone = s.with_updates(dynamic_arc=False)
    rides = mixdown.mix_arguments(alone, on, str(tmp_path), has_vocals=False)["tension"]
    assert [(round(a / spb), db) for a, _, db in rides] == [
        (round(by["Chorus#1"].start), 0.6), (round(verse.start), -2.1), (round(by["Bridge#1"].start), -1.2)]
    assert mixdown.mix_arguments(alone.with_updates(tension_curve=False), on, str(tmp_path), has_vocals=False)[
        "tension"] == []


def test_the_mix_rides_the_band_in_drawn_sections_but_not_the_voice(tmp_path):
    rate = mixer.SAMPLE_RATE
    length = 6 * rate
    noise = np.random.default_rng(1).normal(0, 0.05, (2, length)).astype(np.float32)
    tracks = {"drums.wav": ("drums", noise.copy()), "vocals.wav": ("vocals", noise.copy())}
    mixer._ride_tension(tracks, [(2.0, 4.0, -4.0)], length)
    drums = tracks["drums.wav"][1]
    assert np.allclose(drums[:, :2 * rate], noise[:, :2 * rate])
    assert np.allclose(drums[:, int(2.5 * rate):int(3.5 * rate)], noise[:, int(2.5 * rate):int(3.5 * rate)] * 10 ** -0.2,
                       atol=1e-6)
    assert np.array_equal(tracks["vocals.wav"][1], noise)
    paths = []
    for name in ("drums", "vocals"):
        paths.append(str(tmp_path / f"{name}.wav"))
        sf.write(paths[-1], noise.T, rate)

    def quiet_part(**extra) -> float:
        out = str(tmp_path / "mix.wav")
        mixer.mische_spuren(paths, output_pfad=out, **extra)
        mix, _ = sf.read(out)
        rms = lambda a, b: float(np.sqrt(np.mean(mix[int(a * rate):int(b * rate)] ** 2)))   # noqa: E731
        return rms(2.5, 3.5) / rms(0.5, 1.5)

    assert quiet_part(tension=[(2.0, 4.0, -4.0)]) < quiet_part() * 0.9

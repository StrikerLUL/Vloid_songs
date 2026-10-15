# test_ritardando.py – Ritardando am Ende einer Ballade (v6 Nr. 16)
import os

import pretty_midi
import pytest

import main
import pipeline
import ritardando
from settings import SongSettings

REAL_STYLES = dict(ritardando.STYLES)        # beim Einlesen noch nicht von conftest abgeschaltet
BPM = 80


@pytest.fixture
def rit_on(monkeypatch):
    monkeypatch.setattr(ritardando, "STYLES", REAL_STYLES)


def compose(tmp_path, name, **kw):
    s = SongSettings(seed=4, bpm=BPM, output_ordner=str(tmp_path / name),
                     **{"style": "Ballade", "active_sections": ["Verse", "Chorus", "Outro"], **kw})
    return s, pipeline.compose(s)[0]


def test_the_tempo_falls_step_by_step_and_the_clock_follows():
    rit = (10.0, 18.0)
    clock = ritardando.warp(rit)
    assert clock(5.0) == 5.0 and clock(10.0) == 10.0
    tempi = [ritardando.factor(b / 2, rit) for b in range(20, 36)]
    assert tempi[0] < 1.0 and all(a > b for a, b in zip(tempi, tempi[1:])) and tempi[-1] > ritardando.END_TEMPO
    assert ritardando.factor(18.0, rit) == ritardando.END_TEMPO
    assert clock(18.0) - clock(10.0) == pytest.approx(sum(0.5 / t for t in tempi))
    assert clock(20.0) - clock(18.0) == pytest.approx(2 / ritardando.END_TEMPO)
    assert ritardando.warp(None) is None


def test_a_ballad_slows_down_and_holds_the_last_chord(tmp_path, rit_on):
    s, slow = compose(tmp_path, "rit")
    plan = slow["plan"]
    outro = plan.sections[-1]
    start, final = ritardando.window(plan, "Ballade")
    assert final == outro.end - 4 and start == final - 8
    _, steady = compose(tmp_path, "steady", ritardando=False)
    spb = 60 / BPM
    before = [n for n in steady["piano"] if n.start < start * spb - 0.05]
    assert [(round(n.start, 4), n.pitch) for n in slow["piano"][:len(before)]] == \
        [(round(n.start, 4), n.pitch) for n in before]                          # bis dahin ändert sich nichts
    chord_slow = [n for n in slow["piano"] if n.end == max(m.end for m in slow["piano"])]
    last_slow = max(n.end for n in slow["piano"])
    last_steady = max(n.end for n in steady["piano"])
    longer = (8 * (1 / 0.82 - 1) + 4 * (ritardando.FERMATA / ritardando.END_TEMPO - 1)) * spb   # ungefähr
    assert last_slow - last_steady == pytest.approx(longer, rel=0.25) and chord_slow
    pm = pretty_midi.PrettyMIDI(os.path.join(s.output_dir(), "piano.mid"))
    times, tempi = pm.get_tempo_changes()
    assert tempi[0] == pytest.approx(BPM) and tempi[-1] == pytest.approx(BPM * ritardando.END_TEMPO)
    assert times[1] == pytest.approx(start * spb)
    res = pm.resolution
    late = [n for inst in pm.instruments for n in inst.notes if n.start > start * spb]
    assert late and all(min(pm.time_to_tick(n.start) % (res // 4), res // 4 - pm.time_to_tick(n.start) % (res // 4))
                        < res // 16 for n in late)                                # die Noten bleiben im Raster
    assert main.parse_args(["--ohne-ritardando"]).ohne_ritardando and SongSettings().ritardando


def test_only_ballads_that_end_without_singing(tmp_path, rit_on):
    _, pop = compose(tmp_path, "pop", style="J-Pop Energy")
    assert ritardando.window(pop["plan"], "J-Pop Energy") is None
    _, sung = compose(tmp_path, "sung", active_sections=["Verse", "Chorus"])
    assert ritardando.window(sung["plan"], "Ballade") is None
    for takt, bar in (("3/4", 3), ("6/8", 4)):       # im 6/8-Takt hat ein Takt des Plans zwei Takte
        _, waltz = compose(tmp_path, takt.replace("/", "-"), meter=takt)
        start, final = ritardando.window(waltz["plan"], "Ballade")
        assert final == waltz["plan"].sections[-1].end - bar and final - start == 2 * bar

# test_laufzeit.py – Restzeit aus früheren Läufen und die Meldung, wenn ein Song fertig ist (v6 Nr. 10)
import subprocess
import sys

import pytest

import laufzeit
from gui.page import Job
from settings import SongSettings


def test_the_estimate_follows_earlier_runs_and_how_fast_this_one_is():
    runs = [{"marks": [[0.3, 30.0], [0.6, 60.0], [1.0, 100.0]], "total": 100.0}]
    assert laufzeit.remaining(runs, 0.3, 30.0) == pytest.approx(70.0)
    assert laufzeit.remaining(runs, 0.3, 60.0) == pytest.approx(140.0)            # doppelt so langsam bis hier
    assert laufzeit.remaining(runs, 0.45, 45.0) == pytest.approx(55.0)            # dazwischen gerade gerechnet
    three = runs + [{"marks": [[0.5, 10.0], [1.0, 20.0]], "total": 20.0},
                    {"marks": [[0.5, 50.0], [1.0, 200.0]], "total": 200.0}]
    assert laufzeit.remaining(three, 0.5, 50.0) == pytest.approx(50.0)            # der mittlere von dreien
    assert laufzeit.remaining([], 0.5, 20.0) == pytest.approx(20.0)              # ohne frühere Läufe: bisheriges Tempo
    assert laufzeit.remaining([], 0.05, 20.0) is None
    assert laufzeit.describe(None) == "" and laufzeit.describe(42) == "noch etwa 40 s"
    assert laufzeit.describe(170) == "noch etwa 3 Min."


def test_runs_are_kept_per_kind_in_the_data_folder():
    what = laufzeit.kind(SongSettings(vocal_engine="NEUTRINO"), 1)
    assert laufzeit.past(what) == []
    for k in range(laufzeit.KEEP + 3):
        laufzeit.record(what, [(0.5, 5.0 + k), (1.0, 10.0 + k)], 10.0 + k)
    kept = laufzeit.past(what)
    assert len(kept) == laufzeit.KEEP and kept[-1]["total"] == 10.0 + laufzeit.KEEP + 2
    assert laufzeit.past(laufzeit.kind(SongSettings(vocal_engine="NEUTRINO"), 1, draft=True)) == []


def test_the_job_shows_the_rest_and_remembers_itself():
    what = "Song|1|NEUTRINO"
    laufzeit.record(what, [(0.5, 60.0), (1.0, 120.0)], 120.0)
    job = Job()
    job.start(what)
    job.started -= 30.0                         # 30 Sekunden ist er schon unterwegs
    job.report(0.5, "Synthetisiere Gesang...")
    assert job.remaining == "noch etwa 30 s"    # doppelt so schnell wie der letzte
    job.finish()
    assert len(laufzeit.past(what)) == 2 and laufzeit.past(what)[-1]["marks"][-1][0] == 1.0
    plain = Job()
    plain.start()
    plain.report(0.5, "Refrain")
    assert plain.remaining == ""


def test_windows_gets_a_notice_after_long_runs(monkeypatch):
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.append(cmd))
    monkeypatch.setattr(sys, "platform", "win32")
    assert not laufzeit.notify("Vloid Songs", "Song fertig", 5.0)
    assert laufzeit.notify("Vloid Songs", "Song fertig: Rock's Seed 3", 90.0)
    [cmd] = started
    assert cmd[0] == "powershell" and "Song fertig: Rock''s Seed 3" in cmd[-1] and "ToastNotification" in cmd[-1]
    monkeypatch.setattr(sys, "platform", "linux")
    assert not laufzeit.notify("Vloid Songs", "Song fertig", 90.0) and len(started) == 1

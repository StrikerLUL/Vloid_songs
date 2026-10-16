# test_separation.py – Mix pro Instrument wie die Vorbilder: zerlegen (mit einem nachgebauten Demucs), messen,
# zusammenfassen und angleichen
import os
import sys

import numpy as np
import pytest
import soundfile as sf

import einrichten
import mixer
import mixdown
import separation
import systemcheck
from settings import ReferenceTrack, SongSettings

RATE = mixer.SAMPLE_RATE

# Statt Demucs: Gesang ist die Hälfte des Songs, Schlagzeug ein Viertel, Bass und Rest je ein Achtel
FAKE_WORKER = '''
import json, os, sys
import soundfile as sf
args = sys.argv[1:]
done = []
for source, folder in zip(args[::2], args[1::2]):
    data, rate = sf.read(source, dtype="float32", always_2d=True)
    os.makedirs(folder, exist_ok=True)
    for name, share in (("vocals", 0.5), ("drums", 0.25), ("bass", 0.125), ("other", 0.125)):
        sf.write(os.path.join(folder, name + ".wav"), data * share, rate, subtype="FLOAT")
    done.append(folder)
with open(os.path.join(os.path.dirname(__file__), "aufrufe.txt"), "a") as f:
    f.write("x")
print("Fortschritt ...")
print("ZERLEGT " + json.dumps({"device": "cpu", "done": done}))
'''


@pytest.fixture
def fake_demucs(tmp_path, monkeypatch):
    worker = tmp_path / "worker" / "separation_worker.py"
    worker.parent.mkdir()
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(separation, "python", lambda: sys.executable)
    monkeypatch.setattr(separation, "WORKER", str(worker))
    return worker.parent / "aufrufe.txt"


def noise(seconds=6.0, level=0.1, seed=0):
    rng = np.random.default_rng(seed)
    return (level * rng.standard_normal((2, int(seconds * RATE)))).astype(np.float32)


def tone(hz, seconds=6.0, level=0.2):
    t = np.arange(int(seconds * RATE)) / RATE
    return np.stack([level * np.sin(2 * np.pi * hz * t)] * 2).astype(np.float32)


def write(path, audio):
    sf.write(path, audio.T, RATE, subtype="FLOAT")
    return str(path)


# ── Messen ────────────────────────────────────────────────────────────────────────
def test_highs_make_a_group_brighter():
    assert separation.tilt_db(noise()) > separation.tilt_db(tone(200) + 0.01 * noise())


def test_measure_gives_each_group_its_level_against_the_song():
    found = separation.measure({"vocals": tone(800, level=0.2), "bass": tone(80, level=0.1),
                                "other": tone(500, level=1e-5)})
    assert set(found) == {"vocals", "bass"}            # der fast stille Rest fehlt
    assert found["vocals"]["level"] > found["bass"]["level"]
    assert found["vocals"]["level"] < 0


def test_describe_names_the_groups():
    assert separation.describe({"vocals": {"level": -3.0, "tilt": 0}}) == "Gesang -3.0 dB"
    assert separation.describe({}) == "nichts hörbar"


# ── Zerlegen ──────────────────────────────────────────────────────────────────────
def test_without_demucs_nothing_is_separated(tmp_path):
    assert not separation.available()
    assert separation.separate([write(tmp_path / "a.wav", noise())], [str(tmp_path / "a")]) == []
    assert separation.summarize([ReferenceTrack(path=str(tmp_path / "a.wav"))]) is None


def test_references_are_separated_once_and_cached(tmp_path, fake_demucs):
    ref = write(tmp_path / "vorbild.wav", noise(8))
    found = separation.profiles([ref])[ref]
    assert set(found) == {"vocals", "drums", "bass", "other"}
    # Gesang halb so laut wie alles, Schlagzeug ein Viertel: 6 dB Abstand
    assert found["vocals"]["level"] - found["drums"]["level"] == pytest.approx(6.0, abs=0.1)
    assert separation.profiles([ref])[ref] == found
    assert fake_demucs.read_text() == "x"               # das zweite Mal kam aus dem Cache


def test_an_unreadable_reference_does_not_mix_up_the_others(tmp_path, fake_demucs):
    bad = tmp_path / "kaputt.mp3"
    bad.write_text("kein Audio")
    good = write(tmp_path / "gut.wav", noise(8))
    found = separation.profiles([str(bad), good])
    assert list(found) == [good]
    assert found[good]["vocals"]["level"] > found[good]["drums"]["level"]


def test_a_failing_worker_leaves_the_mix_alone(tmp_path, fake_demucs):
    (fake_demucs.parent / "separation_worker.py").write_text("import sys\nsys.exit(3)\n")
    ref = write(tmp_path / "vorbild.wav", noise(8))
    assert separation.profiles([ref]) == {}
    assert separation.summarize([ReferenceTrack(path=ref)]) is None


def test_summary_weighs_the_references(tmp_path, fake_demucs, monkeypatch):
    a, b = write(tmp_path / "a.wav", noise(4)), write(tmp_path / "b.wav", noise(4, seed=1))
    measured = {a: {"vocals": {"level": -2.0, "tilt": -10.0}, "drums": {"level": -8.0, "tilt": -4.0}},
                b: {"vocals": {"level": -6.0, "tilt": -14.0}}}
    monkeypatch.setattr(separation, "profiles", lambda paths: measured)
    summary = separation.summarize([ReferenceTrack(path=a, weight=3.0), ReferenceTrack(path=b, weight=1.0),
                                    ReferenceTrack(path=str(tmp_path / "aus.wav"), enabled=False)])
    assert summary["vocals"] == {"level": -3.0, "tilt": -11.0}
    assert summary["drums"] == {"level": -8.0, "tilt": -4.0}


# ── Angleichen im Mixer ───────────────────────────────────────────────────────────
def song_tracks():
    return {"drums.wav": ("drums", noise(level=0.08)), "perc.wav": ("perc", noise(level=0.02, seed=3)),
            "bass.wav": ("bass", tone(70, level=0.25)), "vocals.wav": ("vocals", tone(900, level=0.1)),
            "piano.wav": ("piano", tone(440, level=0.05)), "fx.wav": ("fx", noise(level=0.01, seed=5))}


def measure_groups(tracks):
    groups = {}
    for key, audio in tracks.values():
        name = "fx" if key == "fx" else mixer._group_of(key)
        groups[name] = groups.get(name, 0) + audio
    return separation.measure(groups)


def test_each_group_gets_as_loud_and_bright_as_in_the_references():
    tracks = song_tracks()
    before = measure_groups(tracks)
    targets = {"vocals": {"level": before["vocals"]["level"] + 3.0, "tilt": before["vocals"]["tilt"]},
               "drums": {"level": before["drums"]["level"] - 2.0, "tilt": before["drums"]["tilt"] + 2.0},
               "bass": {"level": before["bass"]["level"], "tilt": before["bass"]["tilt"]}}
    mixer._match_groups(tracks, targets)
    after = measure_groups(tracks)
    for group in targets:
        assert after[group]["level"] == pytest.approx(targets[group]["level"], abs=0.6), group
    assert after["drums"]["tilt"] == pytest.approx(targets["drums"]["tilt"], abs=1.0)
    # der Rest (Klavier) und die Effekte haben keine Vorgabe und bleiben, wie sie sind
    assert np.array_equal(tracks["piano.wav"][1], tone(440, level=0.05))
    assert np.array_equal(tracks["fx.wav"][1], noise(level=0.01, seed=5))


def test_groups_move_at_most_6_db_and_4_db_of_highs():
    tracks = song_tracks()
    before = tracks["bass.wav"][1].copy()
    mixer._match_groups(tracks, {"bass": {"level": 30.0, "tilt": 50.0}})
    gain = 20 * np.log10(np.std(tracks["bass.wav"][1]) / np.std(before))
    assert gain == pytest.approx(mixer.MAX_REFERENCE_DB, abs=0.2)


def test_the_mix_uses_the_group_targets(tmp_path, caplog):
    paths = [write(tmp_path / f"{key}.wav", audio) for key, audio in
             (("drums", noise(level=0.08)), ("bass", tone(70)), ("vocals", tone(900, level=0.1)))]
    out = str(tmp_path / "mix.wav")
    with caplog.at_level("INFO", logger="mixer"):
        mixer.mische_spuren(paths, output_pfad=out, group_targets={"drums": {"level": -3.0, "tilt": -8.0}})
    assert os.path.exists(out)
    assert "Mix wie die Vorbilder: Schlagzeug" in caplog.text


# ── Schalter, Vorbild-Ziele, Einrichten, Systemcheck ─────────────────────────────
def test_reference_targets_take_the_groups_instead_of_the_vocal_guess(tmp_path, monkeypatch):
    import reference
    path = write(tmp_path / "a.wav", noise(4))
    summary = reference.Summary(bpm=120, key="C", scale="major", style="Rock", contrast_db=3.0, vocal_db=-4.0,
                                names=["a.wav"])
    monkeypatch.setattr(reference, "summarize", lambda *a: summary)
    groups = {"vocals": {"level": -3.0, "tilt": -12.0}, "drums": {"level": -6.0, "tilt": -5.0}}
    monkeypatch.setattr(separation, "summarize", lambda refs: {k: dict(v) for k, v in groups.items()})
    s = SongSettings(reference_tracks=[ReferenceTrack(path=path)], ref_mastering=False, ref_energy=False)
    targets = mixdown._reference_targets(s, {}, str(tmp_path), has_vocals=True)
    assert targets == {"group_targets": groups}
    # ohne Gesang im Song zählt die Schätzung nicht und der Gesang der Vorbilder auch nicht
    assert mixdown._reference_targets(s, {}, str(tmp_path), has_vocals=False) == \
        {"group_targets": {"drums": groups["drums"]}}
    # ausgeschaltet bleibt es bei der Schätzung
    off = s.with_updates(ref_stems=False)
    assert mixdown._reference_targets(off, {}, str(tmp_path), has_vocals=True) == {"vocal_ratio_db": -4.0}


def test_reference_targets_survive_a_broken_separation(tmp_path, monkeypatch):
    def boom(refs):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(separation, "summarize", boom)
    s = SongSettings(reference_tracks=[ReferenceTrack(path=write(tmp_path / "a.wav", noise(4)))],
                     ref_mastering=False, ref_energy=False, ref_vocal_level=False)
    assert mixdown._reference_targets(s, {}, str(tmp_path), has_vocals=True) == {}


def test_demucs_is_offered_in_the_setup_but_not_preselected():
    found = einrichten.find("demucs")
    assert found.script == "setup_demucs.py" and not found.recommended
    assert not einrichten.is_installed(found)


def test_systemcheck_separates_a_tone(tmp_path, fake_demucs):
    ok, message = systemcheck.check_demucs(SongSettings(), str(tmp_path))
    assert ok is True and "zerlegt" in message


def test_systemcheck_without_demucs_is_grey(tmp_path):
    assert systemcheck.check_demucs(SongSettings(), str(tmp_path))[0] is None

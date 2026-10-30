# test_hoer_duell_160.py – Hör-Duell (1.6.0): blind vergleichen, die Gewinner übernehmen
import json
import os
import random
import zipfile

import numpy as np
import soundfile as sf

import fehlerbericht
import hoer_duell
from settings import SongSettings

RATE = 22050


def tone(path: str, gain: float, wobble: float = 0.0) -> str:
    t = np.linspace(0, 2.0, 2 * RATE, endpoint=False)
    wave = gain * np.sin(2 * np.pi * 440 * t) + wobble * np.sin(2 * np.pi * 660 * t)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.stack([wave, wave], axis=1).astype(np.float32), RATE)
    return path


def fake_render(monkeypatch, effect: dict):
    """render() schreibt einen Ton; effect: {Feld: Einfluss auf den Klang} – fehlt ein Feld, klingt es gleich."""
    calls = []

    def render(settings, folder, seed, progress=None):
        calls.append(settings)
        wobble = sum(amount for field, amount in effect.items() if getattr(settings, field))
        loud = 0.2 if getattr(settings, "mix_punch") else 0.6        # ohne „Druck“ lauter: das Duell gleicht es an
        return tone(os.path.join(folder, "final_mix.wav"), loud, wobble)
    monkeypatch.setattr(hoer_duell, "render", render)
    return calls


def test_the_plan_takes_the_chosen_groups_and_switches_that_are_off_come_back_with_their_default():
    s = SongSettings(harmonies=False, chord_spice=0.0)
    voice = hoer_duell.plan(s, ["stimme"])
    assert voice and all(c.group == "stimme" for c in voice)
    assert hoer_duell.on_value(s, hoer_duell.BY_FIELD["harmonies"]) is True
    assert hoer_duell.on_value(s, hoer_duell.BY_FIELD["chord_spice"]) == 0.5
    assert hoer_duell.on_value(SongSettings(chord_spice=0.8), hoer_duell.BY_FIELD["chord_spice"]) == 0.8
    assert len(hoer_duell.plan(s)) == len(hoer_duell.CANDIDATES)
    assert len(hoer_duell.plan(s, ["mix"], limit=2)) == 2


def test_a_duel_renders_both_sides_equally_loud_in_random_order(monkeypatch, tmp_path):
    calls = fake_render(monkeypatch, {"mix_punch": 0.3})
    duel = hoer_duell.prepare(SongSettings(), hoer_duell.BY_FIELD["mix_punch"], str(tmp_path), seed=7, number=1,
                              rng=random.Random(1))
    assert [c.mix_punch for c in calls] == [True, False]
    assert all(c.active_sections == ["Chorus"] and not c.polish and not c.hearing_check and not c.producer_tag
               for c in calls)
    a, _ = sf.read(duel.a)
    b, _ = sf.read(duel.b)
    assert not duel.identical
    assert abs(hoer_duell._loudness(a, RATE) - hoer_duell._loudness(b, RATE)) < 0.5
    sides = {hoer_duell.prepare(SongSettings(), hoer_duell.BY_FIELD["mix_punch"], str(tmp_path), 7, 1,
                                rng=random.Random(n)).a_is_on for n in range(12)}
    assert sides == {True, False}
    assert sorted(os.listdir(tmp_path)) == ["01_A.wav", "01_B.wav", "lauf"]


def test_a_switch_that_changes_nothing_is_skipped_and_changes_nothing(monkeypatch, tmp_path):
    fake_render(monkeypatch, {})
    s = SongSettings()
    duel = hoer_duell.prepare(s, hoer_duell.BY_FIELD["amp_models"], str(tmp_path), 7, 1)
    assert duel.identical
    entry = hoer_duell.record(duel, "a", s)
    assert entry["choice"] == "gleich" and entry["auto"]
    assert hoer_duell.changes(s) == {} and hoer_duell.inaudible() == set()


def test_the_winners_become_the_settings_and_same_sounding_switches_go_off_and_hide(monkeypatch, tmp_path):
    fake_render(monkeypatch, {"mix_punch": 0.3, "soft_vocal_chain": 0.2, "harmonies": 0.1})
    s = SongSettings()
    picks = {}
    for field, liked in (("mix_punch", "ohne"), ("soft_vocal_chain", "mit"), ("harmonies", "gleich")):
        duel = hoer_duell.prepare(s, hoer_duell.BY_FIELD[field], str(tmp_path), 7, 1)
        choice = "gleich" if liked == "gleich" else ("a" if (liked == "mit") == duel.a_is_on else "b")
        picks[field] = hoer_duell.record(duel, choice, s)["choice"]
    assert picks == {"mix_punch": "ohne", "soft_vocal_chain": "mit", "harmonies": "gleich"}
    assert hoer_duell.changes(s) == {"mix_punch": False, "harmonies": False}
    changed = hoer_duell.apply(s)
    assert not changed.mix_punch and not changed.harmonies and changed.soft_vocal_chain
    assert hoer_duell.inaudible() == {"harmonies"}
    assert "3 Funktionen verglichen: 1 klingen mit besser, 1 ohne, 1" in hoer_duell.summary()
    saved = json.load(open(hoer_duell.path(), encoding="utf-8"))
    assert [e["field"] for e in saved["entries"]] == ["mix_punch", "soft_vocal_chain", "harmonies"]
    # eine spätere Entscheidung gilt
    duel = hoer_duell.prepare(s, hoer_duell.BY_FIELD["mix_punch"], str(tmp_path), 7, 2)
    hoer_duell.record(duel, "a" if duel.a_is_on else "b", s)
    assert "mix_punch" not in hoer_duell.changes(s)
    hoer_duell.forget()
    assert hoer_duell.load() == []


def test_the_error_report_carries_the_duels(monkeypatch, tmp_path):
    fake_render(monkeypatch, {"mix_punch": 0.3})
    duel = hoer_duell.prepare(SongSettings(), hoer_duell.BY_FIELD["mix_punch"], str(tmp_path), 7, 1)
    hoer_duell.record(duel, "gleich", SongSettings())
    report = fehlerbericht.save(str(tmp_path / "bericht.zip"), SongSettings())
    with zipfile.ZipFile(report) as z:
        assert "hoer_duell.json" in z.namelist()


def test_a_real_duel_renders_the_chorus_twice_and_hears_when_nothing_changes(tmp_path):
    s = SongSettings(output_ordner=str(tmp_path / "out"), seed=3, style="Rock", bpm=170)
    s.channels["vocals"].enabled = False        # ohne Gesang (die Vorschau-Stimme hängt in der Windows-CI)
    folder = str(tmp_path / "duell")
    punch = hoer_duell.prepare(s, hoer_duell.BY_FIELD["mix_punch"], folder, 3, 1)
    assert not punch.identical
    a, rate = sf.read(punch.a)
    assert 10 < len(a) / rate < 40             # ein Refrain, nicht der ganze Song
    choir = hoer_duell.prepare(s, hoer_duell.BY_FIELD["final_choir"], folder, 3, 2)
    assert choir.identical                       # ohne Gesang singt auch kein Chor

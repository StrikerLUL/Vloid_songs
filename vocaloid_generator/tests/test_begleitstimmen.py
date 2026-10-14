# test_begleitstimmen.py – Begleitstimmen wie in Produktionen: Harmonien mit Abwechslung und gedoppelt, gesungene
# Flächen, Ad-libs im letzten Refrain (backing_vocals.py)
import os

import numpy as np
import pytest
import soundfile as sf

import backing_vocals
import main
import mixer
import pipeline
import vocal_synthesizer
from lyrics import Mora
from settings import SongSettings

SECTIONS = ["Verse", "Chorus", "Verse", "Chorus", "Chorus"]


@pytest.fixture(scope="module")
def song():
    tracks, _ = pipeline.compose(SongSettings(active_sections=SECTIONS, seed=3))
    return tracks, backing_vocals.notes_of(tracks["melody_data"], tracks["silben"])


def in_section(notes, sec):
    return [n for n in notes if sec.start <= n.start < sec.end]


def test_each_chorus_gets_its_own_harmony(song):
    tracks, notes = song
    plan = tracks["plan"]
    first, middle, last = backing_vocals.choruses(plan)
    assert backing_vocals.harmony_modes(plan) == {first.start: "ends", middle.start: "below", last.start: "above"}
    harmony = backing_vocals.notes_of(tracks["harmony_data"], tracks["harmony_silben"])
    assert 0 < len(in_section(harmony, first)) < len(in_section(notes, first)) / 2   # nur Phrasenenden
    below = in_section(harmony, middle)
    melody = {n.start: n.pitch for n in in_section(notes, middle)}
    assert sum(h.pitch < melody[h.start] for h in below) > 0.8 * len(below)
    above = in_section(harmony, last)
    melody = {n.start: n.pitch for n in in_section(notes, last)}
    assert sum(h.pitch > melody[h.start] for h in above) > 0.6 * len(above)


def test_without_variety_the_harmony_is_the_third_above_as_before(song):
    tracks, _ = song
    plain, _ = pipeline.compose(SongSettings(active_sections=SECTIONS, seed=3, harmony_variety=False,
                                             sung_pads=False, adlibs=False))
    assert "octave_data" not in plain and "pads" not in plain and "adlib_data" not in plain
    harmony = backing_vocals.notes_of(plain["harmony_data"], plain["harmony_silben"])
    assert len(harmony) > len(backing_vocals.notes_of(tracks["harmony_data"], tracks["harmony_silben"]))


def test_the_octave_only_sings_when_it_fits_the_voice(song):
    from melody_writer import MelNote
    tracks, _ = song
    plan = tracks["plan"]
    last = backing_vocals.choruses(plan)[-1]
    lo, hi = plan.vocal_range
    narrow = [MelNote(last.start + k, 1.0, lo + 2 + k % 4, "ら") for k in range(8)]
    line = backing_vocals.octave(plan, narrow)
    assert [n.pitch - m.pitch for n, m in zip(line, narrow)] == [12] * 8
    wide = [MelNote(last.start + k, 1.0, lo + 3 * k, "ら") for k in range(8)]       # über zwei Oktaven
    assert backing_vocals.octave(plan, wide) == []


def test_sung_pads_hold_the_chord_tones_on_u_and_a(song):
    tracks, _ = song
    plan = tracks["plan"]
    lines = backing_vocals.pads(plan)
    assert len(lines) == backing_vocals.PAD_VOICES and all(lines)
    lo = plan.vocal_range[0]
    choruses = backing_vocals.choruses(plan)
    for line in lines:
        for n in line:
            sec = plan.section_at(n.start)
            assert sec.kind == "Chorus" and lo <= n.pitch <= lo + backing_vocals.PAD_RANGE + 1
            assert n.pitch % 12 in sec.chord_at(n.start).pcs
            assert n.syllable == ("あ" if sec.start == choruses[-1].start else "う")
    assert [len(d) for d, _ in tracks["pads"]]


def test_adlibs_answer_in_the_gaps_of_the_final_chorus(song):
    tracks, notes = song
    plan = tracks["plan"]
    last = backing_vocals.choruses(plan)[-1]
    ad = backing_vocals.adlibs(plan, notes)
    assert ad and all(last.start <= n.start < last.end + 1 for n in ad)
    assert any(isinstance(n.syllable, Mora) and n.syllable.melisma for n in ad)       # „いぇー“: der Vokal gehalten
    sung = {str(n.syllable) for n in in_section(notes, last)}
    assert any(str(n.syllable) in sung for n in ad if not getattr(n.syllable, "melisma", False))   # Echo
    ends = [n.start + n.dur for n in ad]
    assert all(b.start >= a.start + a.dur - 1e-6 for a, b in zip(ad, ad[1:]))
    assert max(ends) <= plan.total_beats + 1e-6


# ── im ganzen Ablauf ───────────────────────────────────────────────────────────
@pytest.fixture
def neutrino(tmp_path, monkeypatch):
    root = tmp_path / "NEUTRINO"
    (root / "model" / "MERROW").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    calls = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        calls.append((os.path.basename(xml), style_shift))
        t = np.arange(48000 * 3) / 48000
        rng = np.random.default_rng(len(calls))          # jede Fassung etwas anders
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * t) + 0.01 * rng.standard_normal(len(t)), 48000)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, calls


def test_neutrino_sings_every_backing_voice(tmp_path, neutrino):
    root, calls = neutrino
    s = SongSettings(active_sections=SECTIONS, output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), seed=3,
                     final_choir=False, section_style=False)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    pipeline._synthesize_vocals(s, tracks, out)
    names = [c[0] for c in calls]
    assert names.count("vocals_harmony.xml") == 2                     # gedoppelt
    assert [n for n in names if n.startswith("vocals_flaechen_")] == [f"vocals_flaechen_{k}.xml" for k in (1, 2, 3)]
    assert "vocals_adlibs.xml" in names
    assert ("vocals_harmony_2.xml" in names) == bool(any(p for p, _ in tracks.get("octave_data", [])))
    harmony, _ = sf.read(os.path.join(out, "vocals_harmony.wav"))
    assert harmony.ndim == 2 and not np.allclose(harmony[:, 0], harmony[:, 1])      # links und rechts verschieden
    pads, _ = sf.read(os.path.join(out, "vocals_flaechen.wav"))
    assert pads.ndim == 2
    assert os.path.exists(os.path.join(out, "vocals_adlibs.wav"))
    leftovers = [f for f in os.listdir(out) if f.startswith(("vocals_flaechen_", "vocals_adlibs.xml", "vocals_harmony_2b"))]
    assert leftovers == []


def test_backing_voices_can_be_switched_off(tmp_path, neutrino):
    root, calls = neutrino
    s = SongSettings(active_sections=SECTIONS, output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), seed=3,
                     final_choir=False, section_style=False, harmony_double=False, sung_pads=False, adlibs=False,
                     harmony_variety=False)
    tracks, _ = pipeline.compose(s)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert [c[0] for c in calls] == ["vocals.xml", "vocals_harmony.xml"]


def test_sung_pads_replace_the_keyboard_choir_and_doubled_harmony_stays_wide(tmp_path, monkeypatch):
    rate = mixer.SAMPLE_RATE
    t = np.arange(4 * rate) / rate
    choir = str(tmp_path / "choir.wav")
    sf.write(choir, 0.2 * np.sin(2 * np.pi * 330 * t), rate)
    out = str(tmp_path / "mix.wav")
    mixer.mische_spuren([choir], output_pfad=out, sung_pads=[(1.0, 3.0)], reverb={"choir": 0.0})
    mix, _ = sf.read(out)
    level = np.abs(mix).max(axis=1)
    assert level[int(1.5 * rate):int(2.5 * rate)].max() < 0.02 * level[:int(0.9 * rate)].max()

    widened = []
    widen = mixer._widen
    monkeypatch.setattr(mixer, "_widen", lambda audio, *a: widened.append(1) or widen(audio, *a))
    left, right = np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 550 * t)
    pair = str(tmp_path / "vocals_harmony.wav")
    sf.write(pair, 0.2 * np.stack([left, right], axis=1), rate)
    mixer.mische_spuren([pair], output_pfad=out)
    assert widened == []                                  # links und rechts gesungen: schon breit
    sf.write(pair, 0.2 * left, rate)
    mixer.mische_spuren([pair], output_pfad=out)
    assert widened == [1]


def test_backing_switches_on_the_command_line():
    args = main.parse_args(["--ohne-harmonie-wechsel", "--ohne-doppel-harmonie", "--ohne-flaechen", "--ohne-adlibs"])
    assert args.ohne_harmonie_wechsel and args.ohne_doppel_harmonie and args.ohne_flaechen and args.ohne_adlibs
    s = SongSettings()
    assert s.harmony_variety and s.harmony_double and s.sung_pads and s.adlibs

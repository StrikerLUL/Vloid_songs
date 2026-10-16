# test_takt.py – 3/4- und 6/8-Takt (v6 Nr. 17)
import os
import random

import music21
import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
import main
import meter
import pipeline
import vocal_synthesizer
from drums import CLAP, GROOVES, KICK, SNARE
from neutrino_score import ScoreOptions
from orchestrator import orchestrate_song
from settings import SongSettings

STRUCTURE = ["Intro", "Verse", "Chorus", "Outro"]
BPM = 120


def song(tmp_path, takt, seed=7, **kw):
    random.seed(seed)
    out = str(tmp_path / takt.replace("/", "-"))
    return orchestrate_song("J-Pop", BPM, STRUCTURE, "C", "major", config.SECTION_CONFIG, output_dir=out,
                            meter=takt, **kw), out


def beats(notes, bpm=BPM):
    return [n.start * bpm / 60 for n in notes]


# ── Umrechnen ─────────────────────────────────────────────────────────────────────
def test_the_time_map_drops_one_beat_in_three_four_and_makes_triplets_in_six_eight():
    three, six = meter.get("3/4"), meter.get("6/8")
    assert [three.time(b) for b in (0, 1, 2, 3, 4, 5, 7)] == [0, 1, 2, 2, 3, 4, 5]
    assert three.onset(2.0) is None and three.onset(2.5) is None and three.onset(3.0) == 2.0
    assert three.onset(3.0 - meter.EARLY / 2) == pytest.approx(2.0 - meter.EARLY / 2)   # knapp vor dem Schlag
    assert three.onset(2.0, drop=1) == 1.0 and three.onset(1.0, drop=1) is None
    assert [six.time(b) for b in (0, 0.25, 0.5, 0.75, 1.0)] == pytest.approx([0, 1 / 3, 2 / 3, 5 / 6, 1.0])
    for m in (three, six):
        for b in np.arange(0, 8, 0.25):
            if m.onset(b) is not None:
                assert m.compose_time(m.time(b)) == pytest.approx(b)
    assert meter.get("4/4").time(5.25) == 5.25 and meter.get(None).plain and meter.get("7/8").plain


def test_halftime_grooves_lose_the_second_beat_instead():
    assert meter.drum_drop(GROOVES["halftime"]) == 1
    assert meter.drum_drop({KICK: [(0, 100)], SNARE: [(4, 100), (12, 100)]}) == 2
    assert meter.drum_drop({KICK: [(0, 100)], CLAP: [(8, 100)]}) == 1


# ── Song ──────────────────────────────────────────────────────────────────────────
def test_four_four_stays_as_it_was(tmp_path):
    random.seed(7)
    before = orchestrate_song("J-Pop", BPM, STRUCTURE, "C", "major", config.SECTION_CONFIG,
                              output_dir=str(tmp_path / "a"))
    after, out = song(tmp_path, "4/4")
    for inst in ("drums", "bass", "piano", "vocal_melody"):
        assert [(n.start, n.pitch) for n in before[inst]] == [(n.start, n.pitch) for n in after[inst]]
    changes = pretty_midi.PrettyMIDI(os.path.join(out, "piano.mid")).time_signature_changes
    assert [(t.numerator, t.denominator) for t in changes] == [(4, 4)]


def test_a_waltz_has_three_beats_a_kick_on_one_and_every_syllable(tmp_path):
    tracks, out = song(tmp_path, "3/4")
    plan = tracks["plan"]
    assert plan.meter == "3/4" and plan.bar_beats == 3
    assert all(sec.start % 3 == 0 for sec in plan.sections)
    assert plan.total_beats == 3 * sum(sec.bars for sec in plan.sections)
    verse = next(sec for sec in plan.sections if sec.kind == "Verse")
    downbeats = [verse.start + 3 * b for b in range(verse.bars)]
    kick_beats = [b for n, b in zip(tracks["drums"], beats(tracks["drums"])) if n.pitch == KICK]
    on_one = sum(any(abs(k - d) < 0.1 for k in kick_beats) for d in downbeats)
    assert on_one >= 0.8 * len(downbeats)
    # die Gesangsmelodie ist im Takt geschrieben: Sechzehntel, und jede Silbe singt
    sung = beats(tracks["vocal_melody"])
    assert all(abs(b * 4 - round(b * 4)) < 1e-6 for b in sung)
    assert len(tracks["vocal_melody"]) == len(tracks["silben"]) > 0
    assert any(b % 3 == 2 for b in sung)                  # auch der dritte Schlag wird gesungen
    pm = pretty_midi.PrettyMIDI(os.path.join(out, "drums.mid"))
    assert [(t.numerator, t.denominator) for t in pm.time_signature_changes] == [(3, 4)]
    assert pm.get_tempo_changes()[1][0] == pytest.approx(BPM)
    assert max(n.end for n in tracks["drums"]) <= plan.total_beats * 60 / BPM + 3


def test_six_eight_swings_in_triplets(tmp_path):
    tracks, out = song(tmp_path, "6/8")
    plan = tracks["plan"]
    assert plan.meter == "6/8"
    six_eight_bars = 2 * sum(sec.bars for sec in plan.sections)
    assert six_eight_bars == sum(config.SECTION_CONFIG[k]["bars"] + config.SECTION_CONFIG[k]["bars"] % 2
                                 for k in STRUCTURE)
    assert plan.total_beats == 2 * six_eight_bars        # zwei punktierte Viertel pro Takt
    sung = beats(tracks["vocal_melody"])
    assert all(abs(b * 6 - round(b * 6)) < 1e-6 for b in sung)
    assert any(abs(b % 1 - 1 / 3) < 1e-6 or abs(b % 1 - 2 / 3) < 1e-6 for b in sung)   # Achtel der Triole
    kick_beats = [b for n, b in zip(tracks["drums"], beats(tracks["drums"])) if n.pitch == KICK]
    assert sum(abs(b - round(b)) < 0.05 for b in kick_beats) > 0.5 * len(kick_beats)
    pm = pretty_midi.PrettyMIDI(os.path.join(out, "vocal_melody.mid"))
    assert [(t.numerator, t.denominator) for t in pm.time_signature_changes] == [(6, 8)]
    assert pm.get_tempo_changes()[1][0] == pytest.approx(BPM * 1.5, rel=1e-4)    # MIDI zählt Viertel


def test_hand_edits_land_on_the_note_in_six_eight(tmp_path):
    tracks, _ = song(tmp_path, "6/8")
    six = meter.get("6/8")
    notes = sorted(tracks["vocal_melody"], key=lambda n: n.start)
    target = next(n for n in notes if abs((n.start * BPM / 60) % 1 - 1 / 3) < 1e-6)
    start = target.start * BPM / 60
    following = next((n.start * BPM / 60 for n in notes if n.start > target.start + 1e-6), start + 10)
    edits = {six.edit_key(start): target.pitch + 2}            # so speichert die Oberfläche die Änderungen
    lengths = {six.edit_key(start): six.edit_length(start, start + 2 / 3)}
    again, _ = song(tmp_path / "b", "6/8", melody_edits=SongSettings(melody_edits=edits).melody_edits,
                    melody_lengths=SongSettings(melody_lengths=lengths).melody_lengths)
    moved = next(n for n in again["vocal_melody"] if abs(n.start - target.start) < 1e-6)
    assert moved.pitch == target.pitch + 2
    assert (moved.end - moved.start) * BPM / 60 == pytest.approx(min(2 / 3, following - start), abs=1e-6)


@pytest.mark.parametrize("takt, step, expected", [("3/4", 1.0, [0, 1, 2, 3, 4, 5]),
                                                    ("6/8", 0.5, [0, 1 / 3, 2 / 3, 1, 4 / 3, 5 / 3])])
def test_an_own_melody_keeps_its_rhythm(tmp_path, takt, step, expected):
    own = [(i * step, step, 60 + i) for i in range(6)]          # Viertel im 3/4-, Achtel im 6/8-Takt
    tracks, _ = song(tmp_path, takt, imported_melody={"Chorus": own})
    chorus = next(sec for sec in tracks["plan"].sections if sec.kind == "Chorus")
    sung = [b - chorus.start for b in beats(tracks["vocal_melody"]) if b >= chorus.start - 1e-6][:6]
    assert sung == pytest.approx(expected, abs=1e-6)


# ── Noten für NEUTRINO ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("takt, lead_in, factor", [("4/4", 4.0, 1.0), ("3/4", 3.0, 1.0), ("6/8", 3.0, 1.5)])
def test_musicxml_has_the_meter_and_a_full_bar_lead_in(tmp_path, takt, lead_in, factor):
    xml = vocal_synthesizer.erstelle_musicxml([(64, 1.0), (None, 2.0), (67, 2 / 3)], ["ら", "ら"], 100,
                                              str(tmp_path / "v.xml"), options=ScoreOptions(meter=takt))
    score = music21.converter.parse(xml)
    ts = score.recurse().getElementsByClass(music21.meter.TimeSignature).first()
    assert ts.ratioString == takt
    elems = list(score.recurse().notesAndRests)
    assert elems[0].isRest and float(elems[0].quarterLength) == lead_in
    assert float(elems[1].quarterLength) == pytest.approx(1.0 * factor)
    assert vocal_synthesizer._vorlauf_aus_musicxml(xml) == lead_in
    assert vocal_synthesizer._tempo_aus_musicxml(xml) == pytest.approx(100 * factor)


def test_neutrino_output_is_cut_by_one_bar_of_the_meter(tmp_path, neutrino_attrappe):
    root, _ = neutrino_attrappe
    xml = vocal_synthesizer.erstelle_musicxml([(64, 2.0)], ["ら"], 120, str(tmp_path / "v.xml"),
                                              options=ScoreOptions(meter="6/8"))
    wav = str(tmp_path / "v.wav")
    vocal_synthesizer.neutrino_synthese(xml, wav, str(root), str(root / "model" / "MERROW"))
    audio, rate = sf.read(wav)
    assert len(audio) / rate == pytest.approx(2.0 * 60 / 120, abs=0.02)     # zwei punktierte Viertel, ohne Vorlauf


@pytest.mark.parametrize("takt", ["3/4", "6/8"])
def test_a_whole_song_sings_on_the_band(tmp_path, neutrino_attrappe, takt):
    from test_fassungen import song_settings
    root, _ = neutrino_attrappe
    s = song_settings(tmp_path, root, meter=takt, bpm=90, id3_tags=False, vocal_versions=False)
    result = pipeline.generate_song(s, keep_history=False)
    vocal, rate = sf.read(os.path.join(result.output_dir, "vocals.wav"), always_2d=True)
    tracks = pipeline.compose(s)[0]
    melody = sum(beats for _, beats in tracks["melody_data"]) * 60 / s.bpm
    assert len(vocal) / rate == pytest.approx(melody, abs=0.02)      # der Vorlauf ist genau einen Takt lang
    assert os.path.isfile(result.mix_wav)


# ── Einstellung, Kommandozeile ─────────────────────────────────────────────────────
def test_the_meter_is_a_setting_and_a_command_line_option(tmp_path):
    assert SongSettings().meter == "4/4"
    with pytest.raises(ValueError):
        SongSettings(meter="5/4")
    s = SongSettings(meter="3/4", active_sections=["Verse", "Chorus"], section_bars={"Verse": 4, "Chorus": 4},
                     output_ordner=str(tmp_path), seed=3)
    tracks, _ = pipeline.compose(s)
    assert tracks["plan"].meter == "3/4"
    assert main.parse_args(["--takt", "6/8"]).takt == "6/8"

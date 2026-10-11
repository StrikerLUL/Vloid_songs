# test_production.py – neue Instrumente, Abwechslung pro Sektion, eigene Synths, FX und Gesangsvorbereitung
import os
import stat
import sys
import textwrap

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
from fx import render_fx
from mixer import _deess, _double, midi_zu_wav
from orchestrator import orchestrate_song
from pipeline import seed_everything
from styles import get_style
from synth_engine import VOICES, render_notes
from vocal_synthesizer import VORLAUF_SCHLAEGE, erstelle_musicxml, neutrino_info, neutrino_synthese, stimmlage

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]


def compose(tmp_path, style="J-Pop Energy", bpm=160, key="A", mode="minor", seed=3, **kw):
    seed_everything(seed)
    return orchestrate_song(genre=style, bpm=bpm, structure=STRUCTURE, key=key, mode=mode,
                            section_config=config.SECTION_CONFIG, output_dir=str(tmp_path), style=style, **kw)


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    return compose(tmp_path_factory.mktemp("prod"))


def beats(tracks, notes):
    spb = 60.0 / tracks["plan"].bpm
    return [n.start / spb for n in notes]


def sections_with(tracks, inst):
    plan = tracks["plan"]
    return [(plan.section_at(b + 0.02).kind, plan.section_at(b + 0.02).occurrence) for b in beats(tracks, tracks[inst])]


# ── Neue Instrumente und Abwechslung ─────────────────────────────────────────────
def test_second_verse_gets_a_countermelody_first_does_not(song):
    where = set(sections_with(song, "counter"))
    assert ("Verse", 2) in where
    assert ("Verse", 1) not in where


def test_final_chorus_adds_choir_and_bells_double_the_hook(song):
    plan = song["plan"]
    last = [s for s in plan.sections if s.kind == "Chorus"][-1]
    assert ("Chorus", last.occurrence) in set(sections_with(song, "choir"))
    spb = plan.seconds_per_beat
    sung = {(round(n.start, 3), n.pitch) for n in song["vocal_melody"] if last.start <= n.start / spb < last.end}
    doubled = [n for n in song["bells"] if last.start <= n.start / spb < last.end and n.pitch < 100]
    matches = sum(1 for n in doubled if any(abs(n.start - s) < 0.03 and (n.pitch - p) % 12 == 0 and n.pitch > p
                                            for s, p in sung))
    assert matches >= 0.8 * len(sung)


def test_countermelody_only_answers_in_gaps(song):
    """Die Gegenstimme spielt nie gleichzeitig mit einer kurzen Gesangsnote."""
    for n in song["counter"]:
        for m in song["vocal_melody"]:
            short = (m.end - m.start) < 1.5 * 60.0 / song["plan"].bpm
            assert not (short and m.start < n.end - 1e-3 and n.start < m.end - 1e-3)


def test_countermelody_stays_in_key(song):
    plan = song["plan"]
    from theory import scale_pcs
    for n, b in zip(song["counter"], beats(song, song["counter"])):
        b = round(b * 4) / 4                    # Swing und menschliche Ungenauigkeit herausrechnen
        sec = plan.section_at(b)
        chord = sec.chord_at(b)
        assert n.pitch % 12 in set(scale_pcs(sec.tonic, sec.mode)) | set(chord.pcs)


def test_percussion_is_a_drum_track(tmp_path):
    compose(tmp_path)
    perc = pretty_midi.PrettyMIDI(str(tmp_path / "perc.mid")).instruments[0]
    assert perc.is_drum and perc.notes


def test_sections_combine_several_patterns(song):
    """"arp+supersaw": im Refrain spielen Arpeggio und Supersaw-Fläche zusammen."""
    tmp = song["plan"]
    chorus = next(s for s in tmp.sections if s.kind == "Chorus")
    spb = tmp.seconds_per_beat
    in_chorus = [n for n in song["synth"] if chorus.start <= n.start / spb < chorus.end]
    durations = {round(n.end - n.start, 2) for n in in_chorus}
    assert min(durations) < 0.2 * spb * 4 and max(durations) >= 2 * spb


@pytest.mark.parametrize("style", ["Kawaii Chiptune", "Rock", "Ballade", "City Pop", "Dark Vocaloid"])
def test_every_style_still_composes(tmp_path, style):
    tracks = compose(tmp_path, style=style)
    assert tracks["drums"] or style == "Ballade"
    assert tracks["bass"]


# ── Gesangslage und zweite Stimme ────────────────────────────────────────────────
@pytest.mark.parametrize("singer", ["MERROW", "REINA", "NAKUMO"])
def test_melody_fits_the_singer(tmp_path, singer):
    lo, hi, shift = stimmlage(singer)
    tracks = compose(tmp_path, style="Kawaii Chiptune", vocal_range=(lo, hi))
    pitches = [n.pitch for n in tracks["vocal_melody"]]
    assert min(pitches) >= lo - 2 and max(pitches) <= hi + 2
    if singer == "NAKUMO":
        assert shift == -12


def test_harmony_sings_the_chorus_only_and_consonant(song):
    plan = song["plan"]
    spb = plan.seconds_per_beat
    data, syllables = song["harmony_data"], song["harmony_silben"]
    t = 0.0
    sung = {round(n.start / spb, 3): n.pitch for n in song["vocal_melody"]}
    for pitch, dur in data:
        if pitch is not None:
            assert plan.section_at(t + 0.01).kind == "Chorus"
            interval = abs(pitch - sung[round(t, 3)]) % 12
            assert interval in (3, 4, 5, 7, 8, 9), interval
        t += dur
    assert len(syllables) == sum(1 for p, _ in data if p is not None)


# ── Eigene Synths ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("voice", sorted(VOICES))
def test_synth_voices_render_clean_stereo(voice):
    notes = [pretty_midi.Note(100, p, i * 0.3, i * 0.3 + 0.25) for i, p in enumerate((60, 72, 84, 96))]
    audio = render_notes(notes, voice)
    assert audio.shape[0] == 2 and not np.isnan(audio).any()
    assert 0.01 < np.abs(audio).max() < 2.0
    spectrum = np.abs(np.fft.rfft(audio.mean(axis=0)))
    freqs = np.fft.rfftfreq(audio.shape[1], 1 / 44100)
    assert spectrum[freqs > 19000].sum() < 0.01 * spectrum.sum(), "Aliasing über 19 kHz"


def test_supersaw_is_wide_and_the_pad_fades_in():
    saw = render_notes([pretty_midi.Note(100, 60, 0.0, 1.0)], "supersaw")
    side, mid = (saw[0] - saw[1]) / 2, (saw[0] + saw[1]) / 2
    assert np.sqrt((side ** 2).mean()) > 0.2 * np.sqrt((mid ** 2).mean())
    pad = render_notes([pretty_midi.Note(100, 60, 0.0, 2.0)], "pad")
    assert np.abs(pad[:, :2205]).max() < 0.5 * np.abs(pad[:, 22050:30000]).max()


def test_style_voices_replace_soundfont_layers(tmp_path):
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    for name in ("Synth", "Synth saw"):
        inst = pretty_midi.Instrument(program=81, name=name)
        inst.notes.append(pretty_midi.Note(100, 64, 0.0, 1.0))
        pm.instruments.append(inst)
    path = str(tmp_path / "synth.mid")
    pm.write(path)
    out = str(tmp_path / "synth.wav")
    midi_zu_wav(path, out, instrument_type="synth", voices=get_style("J-Pop Energy").voices["synth"])
    audio, sr = sf.read(out)
    assert sr == 44100 and np.abs(audio).max() > 0.01


# ── FX ───────────────────────────────────────────────────────────────────────────
def test_risers_end_on_the_chorus_and_impacts_start_there(song):
    plan = song["plan"]
    audio = render_fx(plan, seed=1)
    chorus = next(s for s in plan.sections if s.kind == "Chorus")
    hit = int(chorus.start * plan.seconds_per_beat * 44100)
    before = np.abs(audio[:, hit - 4410:hit]).mean()
    long_before = np.abs(audio[:, hit - 4 * 44100:hit - 3 * 44100]).mean()
    assert before > 3 * long_before, "Riser wird bis zur Eins lauter"
    low = audio[:, hit:hit + 4410].mean(axis=0)
    assert np.abs(low).max() > 0.2, "Impact auf der Eins"


def test_styles_without_fx_stay_silent(song):
    plan = song["plan"]
    from dataclasses import replace
    plan.style = replace(plan.style, fx="none")
    try:
        assert not np.any(render_fx(plan))
    finally:
        plan.style = get_style("J-Pop Energy")


# ── Gesang nachbearbeiten ────────────────────────────────────────────────────────
def test_deesser_tames_sibilants_and_keeps_the_voice():
    sr = 44100
    t = np.arange(sr) / sr
    voice = 0.3 * np.sin(2 * np.pi * 300 * t)
    hiss = np.zeros_like(t)
    hiss[20000:24000] = 0.4 * np.random.default_rng(0).standard_normal(4000)
    from scipy.signal import butter, sosfilt
    hiss = sosfilt(butter(4, [6000, 9000], "bandpass", fs=sr, output="sos"), hiss)
    audio = np.vstack([voice + hiss, voice + hiss]).astype(np.float32)
    out = _deess(audio)
    assert np.abs(out[0, 20500:23500] - voice[20500:23500]).max() < 0.8 * np.abs(hiss[20500:23500]).max()
    assert np.allclose(out[0, :15000], audio[0, :15000], atol=1e-3)


def test_doubling_only_in_the_chorus():
    sr = 44100
    t = np.arange(3 * sr) / sr
    mono = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    audio = np.vstack([mono, mono])
    out = _double(audio, [(1.0, 2.0)])
    assert np.allclose(out[:, :int(0.9 * sr)], audio[:, :int(0.9 * sr)])
    assert np.abs(out[:, int(1.3 * sr):int(1.7 * sr)] - audio[:, int(1.3 * sr):int(1.7 * sr)]).max() > 0.02


# ── MusicXML und NEUTRINO ────────────────────────────────────────────────────────
def test_musicxml_starts_with_a_lead_in_and_binds_short_rests(tmp_path):
    from music21 import converter
    xml = erstelle_musicxml([(64, 1.0), (None, 0.25), (66, 0.75), (None, 2.0), (67, 1.0)],
                            ["ら", "り", "る"], 120, str(tmp_path / "v.xml"), transpose=-12)
    score = converter.parse(xml).stripTies()           # 1,25 Schläge schreibt music21 als gebundene Noten
    elems = list(score.flatten().notesAndRests)
    assert elems[0].isRest and float(elems[0].duration.quarterLength) == VORLAUF_SCHLAEGE
    notes = [e for e in elems if e.isNote]
    assert [n.pitch.midi for n in notes][:1] == [52]
    assert float(notes[0].duration.quarterLength) == 1.25        # kurze Pause angebunden
    assert sum(float(e.duration.quarterLength) for e in elems) == VORLAUF_SCHLAEGE + 5.0


FAKE_LABEL = """\
    #!{python}
    import sys
    for path in sys.argv[2:4]:
        open(path, "w").write("label")
"""
FAKE_NEUTRINO = """\
    #!{python}
    import sys, numpy as np, soundfile as sf
    args = sys.argv[1:]
    with open(sys.argv[0] + ".args", "w") as f:
        f.write(repr(args))
    sr = 48000
    audio = np.zeros(int(sr * 3.0), dtype=np.float32)
    audio[sr:] = 0.5                     # ab Sekunde 1 (Ende des Vorlauf-Takts bei 240 BPM) singt es
    sf.write(args[4], audio, sr)
"""


@pytest.mark.skipif(os.name == "nt", reason="die Attrappen sind Python-Skripte, keine Windows-Programme")
def test_neutrino_v3_writes_the_wav_and_cuts_the_lead_in(tmp_path):
    root = tmp_path / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "model" / "MERROW").mkdir(parents=True)
    for name, body in (("musicXMLtoLabel.exe", FAKE_LABEL), ("NEUTRINO.exe", FAKE_NEUTRINO)):
        exe = root / "bin" / name
        exe.write_text(textwrap.dedent(body).format(python=sys.executable))
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 240, str(tmp_path / "v.xml"))
    out = str(tmp_path / "vocals.wav")
    neutrino_synthese(xml, out, str(root), str(root / "model" / "MERROW"))
    args = eval((root / "bin" / "NEUTRINO.exe.args").read_text())
    assert args[4].endswith(".wav") and args[5].rstrip("/\\").endswith("MERROW")
    audio, sr = sf.read(out)
    assert sr == 48000 and abs(len(audio) - 2 * sr) < 10
    assert audio[:100].min() > 0.4, "der Vorlauf-Takt ist abgeschnitten"


RUN_BAT = "\n".join([
    "@echo off",
    "set BASENAME=sample1",
    "set NumThreads=3",
    "set ModelDir=MERROW",
    "set StyleShift=0",
    "set InferenceMode=3",
    "echo %date% %time% : start NEUTRINO",
    r"bin\NEUTRINO.exe score\label\full\%BASENAME%.lab score\label\timing\%BASENAME%.lab output\%BASENAME%.f0"
    r" output\%BASENAME%.melspec output\%BASENAME%.wav model\%ModelDir%\ -n %NumThreads% -k %StyleShift%"
    r" -d %InferenceMode% -t",
])


@pytest.mark.skipif(os.name == "nt", reason="die Attrappen sind Python-Skripte, keine Windows-Programme")
def test_neutrino_v3_takes_its_options_from_run_bat(tmp_path):
    """Die Run.bat der installierten Version gibt die Optionen vor, unsere Dateien und Threads ersetzen ihre."""
    root = tmp_path / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "model" / "REINA").mkdir(parents=True)
    for name, body in (("musicXMLtoLabel.exe", FAKE_LABEL), ("NEUTRINO.exe", FAKE_NEUTRINO)):
        exe = root / "bin" / name
        exe.write_text(textwrap.dedent(body).format(python=sys.executable))
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    (root / "Run.bat").write_text(RUN_BAT)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 240, str(tmp_path / "v.xml"))
    neutrino_synthese(xml, str(tmp_path / "vocals.wav"), str(root), str(root / "model" / "REINA"), threads=5)
    args = eval((root / "bin" / "NEUTRINO.exe.args").read_text())
    assert args[0].endswith("full.lab") and args[1].endswith("timing.lab") and args[4].endswith(".wav")
    assert args[5].rstrip("/\\").endswith("REINA")
    assert args[6:] == ["-n", "5", "-k", "0", "-d", "3", "-t"]


@pytest.mark.skipif(os.name == "nt", reason="die Attrappen sind Python-Skripte, keine Windows-Programme")
def test_style_shift_reaches_neutrino(tmp_path):
    root = tmp_path / "NEUTRINO-windows-v3.2.5" / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "model" / "MERROW").mkdir(parents=True)
    for name, body in (("musicXMLtoLabel.exe", FAKE_LABEL), ("NEUTRINO.exe", FAKE_NEUTRINO)):
        exe = root / "bin" / name
        exe.write_text(textwrap.dedent(body).format(python=sys.executable))
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    xml = erstelle_musicxml([(64, 4.0)], ["ら"], 240, str(tmp_path / "v.xml"))
    neutrino_synthese(xml, str(tmp_path / "vocals.wav"), str(root), str(root / "model" / "MERROW"), style_shift=2)
    args = eval((root / "bin" / "NEUTRINO.exe.args").read_text())
    assert args[args.index("-k") + 1] == "2"
    assert neutrino_info(str(root)) == "NEUTRINO v3 (v3.2.5), Stimmen: MERROW"


def test_neutrino_failure_raises_instead_of_faking_a_voice(tmp_path):
    with pytest.raises(FileNotFoundError):
        neutrino_synthese(str(tmp_path / "v.xml"), str(tmp_path / "o.wav"), str(tmp_path / "fehlt"), "x")

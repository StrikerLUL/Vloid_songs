# test_sektions_stil.py – Strophe ruhig, Refrain kräftig (StyleShift pro Sektion) und Fassungen ohne Farbsprung
import logging
import os

import numpy as np
import pytest
import soundfile as sf

import main
import pipeline
import vocal_synthesizer
import voice_fx
from settings import SongSettings
from voice_fx import SungNote

RATE = 48000


def level(shift):
    """So laut singt die Attrappe mit diesem StyleShift: daran erkennt der Test, welche Fassung wo singt."""
    return 0.05 + 0.02 * (shift + 6)


@pytest.fixture
def singing_neutrino(tmp_path, monkeypatch):
    """NEUTRINO, das die Töne der MusicXML als Sinus singt (stumm in den Pausen), so laut wie level(StyleShift).
    noisy: jede Fassung klingt eine Spur anders (wie ein NEUTRINO, das nicht jedes Mal dasselbe singt)."""
    import music21
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "REINA"):
        (root / "model" / singer).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    calls = []
    state = {"noisy": False, "rng": np.random.default_rng(1)}

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        calls.append((os.path.basename(xml), os.path.basename(model_dir), style_shift))
        score = music21.converter.parse(xml)
        bpm = vocal_synthesizer._tempo_aus_musicxml(xml)
        spb = 60.0 / bpm
        length = (float(score.highestTime) - vocal_synthesizer.VORLAUF_SCHLAEGE) * spb
        t = np.arange(int(length * RATE)) / RATE
        audio = np.zeros_like(t)
        for n in score.recurse().notes:
            start = (float(n.getOffsetInHierarchy(score)) - vocal_synthesizer.VORLAUF_SCHLAEGE) * spb
            on = (t >= start) & (t < start + float(n.quarterLength) * spb)
            audio[on] = level(style_shift) * np.sin(2 * np.pi * n.pitch.frequency * t[on])
        if state["noisy"]:
            audio += 1e-3 * state["rng"].standard_normal(len(audio))
        sf.write(wav, audio.astype(np.float32), RATE)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, calls, state


def song(tmp_path, root, **kw):
    s = SongSettings(active_sections=["Verse", "Chorus"], section_bars={"Verse": 4, "Chorus": 4},
                     output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                     harmonies=False, final_choir=False, breaths=False, phrase_expression=False)
    return s.with_updates(**kw)


def phrase_levels(path, tracks, s):
    """[(Sektionsart, Pegel)] je Phrase der fertigen Hauptstimme."""
    audio, rate = sf.read(path, always_2d=True)
    mono = audio.mean(axis=1)
    notes = voice_fx.timeline(tracks["melody_data"], s.bpm, vocal_synthesizer.stimmlage(s.singer)[2])
    groups = voice_fx.phrases(notes)
    kinds = voice_fx.phrase_kinds(groups, pipeline._sections_in_seconds(tracks["plan"]))
    out = []
    for group, kind in zip(groups, kinds):
        a, b = int((group[0].start + 0.05) * rate), int((group[-1].end - 0.05) * rate)
        out.append((kind, float(np.sqrt(2 * np.mean(mono[a:b] ** 2)))))
    return out


# ── StyleShift pro Sektion ─────────────────────────────────────────────────────
def test_verse_and_chorus_are_sung_with_their_own_style_shift(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, style_shift=1)
    tracks, _ = pipeline.compose(s)
    vocals = pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert sorted(shift for _, _, shift in calls) == [0, 2]           # Strophe 1 − 1, Refrain 1 + 1
    assert all(name.startswith("vocals_stil_") for name, _, _ in calls)
    found = phrase_levels(vocals, tracks, s)
    assert {kind for kind, _ in found} == {"Verse", "Chorus"}
    for kind, sung in found:
        assert sung == pytest.approx(level(0 if kind == "Verse" else 2), rel=0.1), kind
    assert not [f for f in os.listdir(s.output_dir()) if "_stil_" in f or "_fassung_" in f]


def test_section_style_can_be_switched_off(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    s = song(tmp_path, root, section_style=False)
    tracks, _ = pipeline.compose(s)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert calls == [("vocals.xml", "MERROW", 0)]


def test_excerpts_keep_the_length_and_only_the_chosen_notes():
    data = [(None, 1.0), (64, 1.0), (65, 0.5), (None, 2.0), (67, 1.0)]
    part, silben = voice_fx.only_notes(data, ["か", "き", "く"], {1, 2})
    assert part == [(None, 1.0), (None, 1.0), (65, 0.5), (None, 2.0), (67, 1.0)]
    assert silben == ["き", "く"]


def test_a_phrase_belongs_to_the_section_it_mostly_sits_in():
    groups = [[SungNote(0.0, 1.0, 60)], [SungNote(3.5, 6.0, 60)], [SungNote(9.0, 9.5, 60)]]
    sections = [(0.0, 4.0, "Verse"), (4.0, 8.0, "Chorus")]
    assert voice_fx.phrase_kinds(groups, sections) == ["Verse", "Chorus", ""]


def test_harmony_and_choir_sing_like_the_chorus(tmp_path, singing_neutrino):
    root, calls, _ = singing_neutrino
    assert pipeline._chorus_shift(SongSettings(style_shift=1)) == 2
    assert pipeline._chorus_shift(SongSettings(style_shift=6, chorus_style_shift=3)) == 6
    assert pipeline._chorus_shift(SongSettings(style_shift=1, section_style=False)) == 1
    s = song(tmp_path, root, harmonies=True, final_choir=True)
    tracks, _ = pipeline.compose(s)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    others = [(name, shift) for name, _, shift in calls if not name.startswith("vocals_stil_")]
    assert others and all(shift == 1 for _, shift in others)


def test_without_style_shift_support_the_song_is_still_sung(tmp_path, singing_neutrino, monkeypatch, caplog):
    root, calls, _ = singing_neutrino
    sing = vocal_synthesizer.neutrino_synthese

    def ignores_style_shift(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        sing(xml, wav, neutrino_dir, model_dir, 0)                    # wie die Ausgabe mit Tuning-Tool (.ex)
        vocal_synthesizer.LETZTER_LAUF["styleshift"] = False if style_shift else None
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", ignores_style_shift)
    s = song(tmp_path, root)
    tracks, _ = pipeline.compose(s)
    with caplog.at_level(logging.WARNING):
        vocals = pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert caplog.text.count("keinen StyleShift") == 1
    assert all(sung == pytest.approx(level(0), rel=0.1) for _, sung in phrase_levels(vocals, tracks, s))


def test_neutrino_reports_style_shift_and_graphics_card(neutrino_attrappe, tmp_path, monkeypatch):
    root, _ = neutrino_attrappe
    from vocal_synthesizer import LETZTER_LAUF, erstelle_musicxml, neutrino_synthese
    xml = erstelle_musicxml([(64, 1.0), (65, 1.0)], ["ら", "ら"], 120, str(tmp_path / "a.xml"))
    model = str(root / "model" / "MERROW")
    neutrino_synthese(xml, str(tmp_path / "a.wav"), str(root), model, style_shift=1)
    assert LETZTER_LAUF["styleshift"] is True and LETZTER_LAUF["grafikkarte"] is True
    run = vocal_synthesizer._run

    def on_the_processor(cmd, cwd, timeout):
        done = run(cmd, cwd, timeout)
        done.stdout = vocal_synthesizer.CPU_MELDUNG if cmd[0].endswith("NEUTRINO.exe") else ""
        return done

    monkeypatch.setattr(vocal_synthesizer, "_run", on_the_processor)
    neutrino_synthese(xml, str(tmp_path / "b.wav"), str(root), model)
    assert LETZTER_LAUF["grafikkarte"] is False and LETZTER_LAUF["styleshift"] is None


# ── Fassungen ohne Farbsprung ──────────────────────────────────────────────────
def lead(tmp_path, root, s):
    data = [(None, 2.0), (64, 2.0), (67, 2.0), (None, 2.0), (69, 2.0)]
    xml = vocal_synthesizer.erstelle_musicxml(data, ["ら"] * 3, s.bpm, str(tmp_path / "vocals.xml"))
    wav = str(tmp_path / "vocals.wav")
    pipeline._neutrino_lead(s, data, xml, wav, str(root), "MERROW", (), ["ら"] * 3, ())
    return wav


def test_takes_keep_the_style_shift_unless_neutrino_sings_the_same_every_time(tmp_path, singing_neutrino):
    root, calls, state = singing_neutrino
    s = SongSettings(vocal_takes=2, bpm=120)
    lead(tmp_path, root, s)
    assert [shift for _, _, shift in calls] == [0, 0, 1]      # gleich gesungen: die zweite eine Stufe heller
    assert pipeline._neutrino_repeats(str(root)) is True
    calls.clear()
    lead(tmp_path, root, s)
    assert [shift for _, _, shift in calls] == [0, 1]         # gemerkt: gleich heller

    pipeline._remember_repeats(str(root), False)
    state["noisy"] = True
    calls.clear()
    lead(tmp_path, root, s)
    assert [shift for _, _, shift in calls] == [0, 0]
    calls.clear()
    lead(tmp_path, root, s.with_updates(even_takes=False))
    assert [shift for _, _, shift in calls] == [0, 1]
    assert sorted(os.listdir(tmp_path)) == ["NEUTRINO", "daten", "vocals.wav", "vocals.xml"]


def sung(notes, length, detune=None, crack=None):
    t = np.arange(int(length * RATE)) / RATE
    audio = np.zeros_like(t)
    for i, n in enumerate(notes):
        on = (t >= n.start) & (t < n.end)
        pitch = n.pitch + (detune or {}).get(i, 0.0)
        freq = np.full(on.sum(), 440 * 2 ** ((pitch - 69) / 12))
        if crack is not None and i == crack:
            freq[len(freq) // 2:len(freq) // 2 + int(0.03 * RATE)] *= 2 ** (5 / 12)   # ein Kiekser mitten im Ton
        phase = 2 * np.pi * np.cumsum(freq) / RATE
        audio[on] = 0.3 * np.sin(phase)
    return audio.astype(np.float32)


def test_small_deviations_do_not_switch_takes_but_wrong_notes_and_cracks_do(tmp_path):
    notes = [SungNote(0.2, 0.7, 69), SungNote(0.7, 1.2, 72), SungNote(2.2, 2.7, 67), SungNote(2.7, 3.2, 71)]
    first = str(tmp_path / "a.wav")
    second = str(tmp_path / "b.wav")
    # die erste Fassung singt die erste Phrase 30 Cent tief (ein schöner Schleifer) und die zweite einen Ganzton daneben
    sf.write(first, sung(notes, 4.0, {0: -0.3, 1: -0.3, 2: 2.0}), RATE)
    sf.write(second, sung(notes, 4.0), RATE)
    assert voice_fx.comp([first, second], notes, str(tmp_path / "x.wav")) == [1, 1]
    assert voice_fx.comp([first, second], notes, str(tmp_path / "y.wav"),
                         tolerance=voice_fx.GROSS_CENTS) == [0, 1]
    sf.write(second, sung(notes, 4.0, crack=0), RATE)
    assert voice_fx.comp([second, first], notes, str(tmp_path / "z.wav"),
                         tolerance=voice_fx.GROSS_CENTS)[0] == 1


def test_section_options_on_the_command_line(monkeypatch, tmp_path):
    seen = {}

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        return pipeline.SongResult(seed=1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"))

    monkeypatch.setattr(main, "generate_song", fake_generate)
    assert main.main(["--ohne-sektions-stil", "--strophe-stil", "-2", "--refrain-stil", "3",
                      "--ohne-gleiche-fassungen"]) == 0
    s = seen["settings"]
    assert (s.section_style, s.verse_style_shift, s.chorus_style_shift, s.even_takes) == (False, -2, 3, False)
    assert main.main([]) == 0
    s = seen["settings"]
    assert (s.section_style, s.verse_style_shift, s.chorus_style_shift, s.even_takes) == (True, -1, 1, True)

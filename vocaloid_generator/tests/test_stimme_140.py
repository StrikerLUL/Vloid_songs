# test_stimme_140.py – Stimme 1.4.0: Wohlfühlbereich der NEUTRINO-Stimmen, sanfte Nachbearbeitung, weichere
# Gesangskette
import logging

import numpy as np
import pytest
import soundfile as sf

import mixdown
import mixer
import pipeline
import singing
import style_fx
import vocal_synthesizer
import vocal_tone
import voice_fx
from settings import SongSettings
from test_sektions_stil import singing_neutrino, song  # noqa: F401 – das Fixture gilt so auch hier
from voice_fx import SungNote

RATE = 48000


# ── Wohlfühlbereich ────────────────────────────────────────────────────────────
def test_every_neutrino_voice_has_its_comfort_tempo():
    for singer in vocal_synthesizer.STIMMEN:
        (lo, hi), styles = vocal_synthesizer.komfort(singer)
        assert 60 <= lo < hi <= 200 and styles, singer
    assert vocal_synthesizer.komfort("merrow") == vocal_synthesizer.komfort("MERROW")
    assert vocal_synthesizer.komfort("UNBEKANNT") is None


def test_the_hint_names_voices_that_sing_this_tempo_better():
    hint = vocal_synthesizer.komfort_hinweis("MERROW", 166, "Rock", ("MERROW", "AOI", "SOMA", "REINA"))
    assert "80 bis 140" in hint and "166 BPM" in hint and "verschleift" in hint
    named = hint.split("singen schöner: ")[1]
    assert "AOI" not in named and named.index("SOMA") < named.index("REINA")    # beide Rock, SOMA zuerst installiert
    assert vocal_synthesizer.komfort_hinweis("MERROW", 145) == ""                # im Spielraum
    assert vocal_synthesizer.komfort_hinweis("UNBEKANNT", 300) == ""
    slow = vocal_synthesizer.komfort_hinweis("RUNO", 80)
    assert "wackeln" in slow and "Etwas schneller" in slow


def test_styleshift_arrives_only_where_neutrino_takes_it(tmp_path):
    def neutrino(name, bat=None, nsf=False):
        root = tmp_path / name
        (root / "bin").mkdir(parents=True)
        (root / "bin" / "NEUTRINO.exe").write_text("")
        if nsf:
            (root / "bin" / "NSF.exe").write_text("")
        if bat is not None:
            (root / "Run.bat").write_text(bat)
        return str(root)
    assert not vocal_synthesizer.kennt_styleshift(neutrino("alt", "NEUTRINO.exe %full% -n 3 -t"))
    assert vocal_synthesizer.kennt_styleshift(neutrino("neu", "set StyleShift=0\nNEUTRINO.exe -k %StyleShift%"))
    assert vocal_synthesizer.kennt_styleshift(neutrino("ohne_bat"))
    assert not vocal_synthesizer.kennt_styleshift(neutrino("NEUTRINO-Windows-v3.1.0"))
    assert vocal_synthesizer.kennt_styleshift(neutrino("NEUTRINO-Windows-v3.2.2"))
    assert vocal_synthesizer.kennt_styleshift(neutrino("v2", "NEUTRINO.exe", nsf=True))


def test_the_voice_comfort_names_better_voices_and_sings_in_one_piece(tmp_path, singing_neutrino, monkeypatch,  # noqa: F811
                                                                      caplog):
    monkeypatch.setattr(singing, "VOICE_COMFORT", True)
    singing._NO_STYLESHIFT_SAID.clear()
    root, calls, _ = singing_neutrino
    (root / "Run.bat").write_text("NEUTRINO.exe %full% %timing% -n 3 -t")      # 3.0 bis 3.2.1: ohne StyleShift
    s = song(tmp_path, root, style_shift=1, bpm=170)
    tracks, _ = pipeline.compose(s)
    with caplog.at_level(logging.INFO, logger="singing"):
        singing._synthesize_vocals(s, tracks, s.output_dir())
    assert calls == [("vocals.xml", "MERROW", 1)], "am Stück, nicht in Strophe und Refrain zerlegt"
    assert "MERROW singt laut NEUTRINO am schönsten bei 80 bis 140 BPM" in caplog.text and "REINA" in caplog.text
    assert "kennt keinen StyleShift" in caplog.text
    calls.clear()
    caplog.clear()
    off = s.with_updates(voice_comfort=False)
    with caplog.at_level(logging.INFO, logger="singing"):
        singing._synthesize_vocals(off, tracks, off.output_dir())
    assert sorted(shift for _, _, shift in calls) == [0, 2]
    assert "am schönsten" not in caplog.text
    # mit StyleShift (3.2.2) singen Strophe und Refrain wie bisher je mit ihrem eigenen
    calls.clear()
    (root / "Run.bat").write_text("NEUTRINO.exe %full% -k %StyleShift% -n 3 -t")
    new = s.with_updates(output_ordner=str(tmp_path / "neu"))       # sonst kommt der Gesang von eben wieder
    tracks, _ = pipeline.compose(new)
    singing._synthesize_vocals(new, tracks, new.output_dir())
    assert sorted(shift for _, _, shift in calls) == [0, 2]


# ── Sanfte Nachbearbeitung ────────────────────────────────────────────────────
def _tone(path, seconds=2.0, hz=220.0):
    t = np.arange(int(seconds * RATE)) / RATE
    audio = 0.3 * np.sin(2 * np.pi * hz * t) + 0.05 * np.sin(2 * np.pi * 2 * hz * t)
    sf.write(path, audio.astype(np.float32), RATE, subtype="FLOAT")
    return audio


def test_gentle_reshape_only_touches_what_changes(tmp_path, monkeypatch, singing_neutrino):  # noqa: F811
    monkeypatch.setattr(voice_fx, "GENTLE_CENTS", 4.0)
    notes = [SungNote(0.1, 0.9, 57), SungNote(1.0, 1.9, 57)]

    def curve(f0, frame, phrase, offset):         # nur die zweite Note wird einen Viertelton höher
        t = offset + np.arange(len(f0)) * frame
        return np.where((t > 1.2) & (f0 > 0), f0 * 2 ** (50 / 1200), f0)
    gentle, whole = str(tmp_path / "sanft.wav"), str(tmp_path / "ganz.wav")
    original = _tone(gentle)
    _tone(whole)
    share = voice_fx.repitch(gentle, notes, curve, psola=False, gentle=True)
    assert 0 < share < 0.6
    assert voice_fx.repitch(whole, notes, curve, psola=False) == 1.0
    soft, _ = sf.read(gentle)
    hard, _ = sf.read(whole)
    early = slice(int(0.2 * RATE), int(0.8 * RATE))
    assert np.allclose(soft[early], original[early], atol=1e-6), "die erste Note bleibt, wie sie gesungen wurde"
    assert not np.allclose(hard[early], original[early], atol=1e-3)
    late = slice(int(1.4 * RATE), int(1.8 * RATE))
    assert not np.allclose(soft[late], original[late], atol=1e-3)
    nothing = str(tmp_path / "nichts.wav")
    _tone(nothing)
    assert voice_fx.repitch(nothing, notes, lambda f0, *a: f0, psola=False, gentle=True) == 0.0

    # der Schalter kommt bei der Hauptstimme an
    root, _, _ = singing_neutrino
    used = []
    monkeypatch.setattr(voice_fx, "reshape", lambda path, notes, **kw: used.append(kw["gentle"]) or False)
    s = song(tmp_path, root)
    tracks, _ = pipeline.compose(s)
    singing._synthesize_vocals(s, tracks, s.output_dir())
    singing._synthesize_vocals(s.with_updates(gentle_reshape=False), tracks, s.output_dir())
    assert used == [True, False]


def test_gentle_reshape_drops_formant_shifts_you_hardly_hear(monkeypatch):
    monkeypatch.setattr(style_fx, "STYLES", {"Idol-Pop": {"formant": 1.04}, "Kawaii Chiptune": {"formant": 1.08}})
    monkeypatch.setattr(style_fx, "FORMANT_MIN_SHIFT", 0.06)
    s = SongSettings()
    assert style_fx.effects_for("Idol-Pop", s) == {}
    assert style_fx.effects_for("Kawaii Chiptune", s) == {"formant": 1.08}
    assert style_fx.effects_for("Idol-Pop", s.with_updates(gentle_reshape=False)) == {"formant": 1.04}


# ── Weichere Gesangskette ─────────────────────────────────────────────────────
def test_the_soft_chain_lets_the_attacks_through(tmp_path, monkeypatch):
    monkeypatch.setattr(vocal_tone, "SOFT", vocal_tone.SOFT_CHAIN)
    hard = vocal_tone.STANDARD
    soft = vocal_tone.softened(hard)
    assert soft.ratio <= 3 < hard.ratio and soft.attack_ms > hard.attack_ms
    assert soft.presence_db < hard.presence_db and soft.presence_q < hard.presence_q
    assert "3:1 in 6 ms" in soft.describe()
    out = str(tmp_path)
    s = SongSettings(output_ordner=out)
    assert mixdown._vocal_tone(s, out).ratio == soft.ratio
    assert mixdown._vocal_tone(s.with_updates(soft_vocal_chain=False), out).ratio == hard.ratio
    assert mixdown._vocal_tone(s.with_updates(vocal_tone=False), out) == soft
    assert mixdown._vocal_tone(s.with_updates(vocal_tone=False, soft_vocal_chain=False), out) is None

    # Silbeneinsätze: kurze laute Spitzen auf einem leiseren Ton; die weiche Kette lässt sie stehen
    t = np.arange(int(1.5 * 44100)) / 44100
    voice = 0.15 * np.sin(2 * np.pi * 330 * t)
    for start in np.arange(0.1, 1.4, 0.25):
        hit = (t >= start) & (t < start + 0.01)
        voice[hit] *= 4
    path = str(tmp_path / "vocals.wav")
    sf.write(path, voice.astype(np.float32), 44100)

    def crest(tone, name):
        mix = str(tmp_path / name)
        mixer.mische_spuren([path], output_pfad=mix, vocal_tone=tone)
        audio, _ = sf.read(mix, always_2d=True)
        mono = audio.mean(axis=1)
        return float(np.max(np.abs(mono)) / np.sqrt(np.mean(mono ** 2)))
    assert crest(soft, "weich.wav") > crest(hard, "hart.wav")


@pytest.mark.parametrize("name", ["voice_comfort", "gentle_reshape", "soft_vocal_chain"])
def test_the_voice_switches_are_on_by_default(name):
    assert getattr(SongSettings(), name) is True

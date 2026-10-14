# test_gesang.py – Comping aus mehreren Fassungen, Ausdruck pro Phrase, Studio-Gesangskette und Romaji
import os

import numpy as np
import pytest
import soundfile as sf

import mixer
import voice_fx
from lyrics import romaji_to_kana, syllables
from voice_fx import SungNote

RATE = 48000


def sing(path, notes, wrong=(), length=4.0, level=0.3):
    """Eine Fassung: Sinus auf den Noten; Noten mit Index in wrong singt sie einen Ganzton daneben."""
    t = np.arange(int(length * RATE)) / RATE
    audio = np.zeros_like(t)
    for i, n in enumerate(notes):
        pitch = n.pitch + (2 if i in wrong else 0)
        on = (t >= n.start) & (t < n.end)
        audio[on] = level * np.sin(2 * np.pi * 440 * 2 ** ((pitch - 69) / 12) * t[on])
    sf.write(path, np.stack([audio, audio], axis=1).astype(np.float32), RATE)
    return str(path)


# zwei Phrasen mit einer Pause von einer Sekunde dazwischen
NOTES = [SungNote(0.2, 0.7, 69), SungNote(0.7, 1.2, 72), SungNote(2.2, 2.7, 67), SungNote(2.7, 3.2, 71)]


def test_comp_takes_each_phrase_from_the_cleanest_take(tmp_path):
    first = sing(tmp_path / "a.wav", NOTES, wrong=(2, 3))         # zweite Phrase daneben
    second = sing(tmp_path / "b.wav", NOTES, wrong=(0, 1))        # erste Phrase daneben
    out, double = str(tmp_path / "comp.wav"), str(tmp_path / "double.wav")
    choice = voice_fx.comp([first, second], NOTES, out, double, [(2.0, 4.0)])
    assert choice == [0, 1]
    assert voice_fx.pitch_error(out, NOTES) < 20
    assert voice_fx.pitch_error(first, NOTES) > 80 and voice_fx.pitch_error(second, NOTES) > 80
    doubled, _ = sf.read(double)
    assert np.max(np.abs(doubled[:int(1.9 * RATE)])) < 1e-4            # außerhalb des Refrains still
    assert np.max(np.abs(doubled[int(2.3 * RATE):int(3.1 * RATE)])) > 0.1


def test_phrases_split_at_pauses():
    assert [len(p) for p in voice_fx.phrases(NOTES)] == [2, 2]
    assert voice_fx._cut_points(voice_fx.phrases(NOTES)) == [pytest.approx(1.7)]


def test_expression_rises_to_the_peak_and_softens_the_end():
    sections = [(0.0, 2.0, "Verse"), (2.0, 4.0, "Chorus")]
    curve = voice_fx.expression_curve(NOTES, sections, 4 * RATE, RATE)
    at = lambda s: float(curve[int(s * RATE)])  # noqa: E731
    assert at(0.95) > at(0.3)                          # zum höchsten Ton hin lauter
    assert at(1.19) < at(0.95) - 2                     # das Ende klingt weicher aus
    assert at(2.95) > at(0.95)                         # der Refrain liegt weiter vorn als die Strophe
    assert np.max(np.abs(curve)) < 6


def test_express_changes_level_but_keeps_the_song(tmp_path):
    path = sing(tmp_path / "v.wav", NOTES)
    before, _ = sf.read(path)
    assert voice_fx.express(path, NOTES, [(0.0, 4.0, "Chorus")])
    after, _ = sf.read(path)
    assert after.shape == before.shape
    peak = slice(int(0.8 * RATE), int(1.0 * RATE))
    assert np.sqrt(np.mean(after[peak] ** 2)) > np.sqrt(np.mean(before[peak] ** 2))
    assert not voice_fx.express(path, [], [])


def test_smooth_is_a_moving_average():
    step = np.r_[np.zeros(100), np.ones(100)].astype(np.float32)
    out = voice_fx.smooth(step, 20)
    assert out[0] == 0 and out[-1] == 1 and 0.4 < out[100] < 0.6
    assert np.allclose(voice_fx.smooth(np.full(50, 3.0), 7), 3.0)


# ── Studio-Gesangskette im Mixer ────────────────────────────────────────────────
def test_saturation_is_gentle():
    x = np.linspace(-0.5, 0.5, 1001, dtype=np.float32)[None].repeat(2, axis=0)
    y = mixer._saturate(x)
    assert np.all(np.abs(y) <= np.abs(x) + 1e-6) and np.allclose(y[:, 500], 0)
    assert np.max(np.abs(y - x)) < 0.1


def test_vocal_space_is_drier_in_the_verse():
    plate, delay = mixer._vocal_space([(0.0, 2.0, "Verse"), (2.0, 4.0, "Chorus")], 4 * mixer.SAMPLE_RATE)
    assert plate[mixer.SAMPLE_RATE] < plate[3 * mixer.SAMPLE_RATE]
    assert delay[mixer.SAMPLE_RATE] < delay[3 * mixer.SAMPLE_RATE]


def test_real_double_is_mixed_as_its_own_track(tmp_path):
    assert mixer._track_key(str(tmp_path / "vocals_double.wav")) == "double"
    rate = mixer.SAMPLE_RATE
    t = np.arange(3 * rate) / rate
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    for name in ("vocals", "vocals_double", "piano"):
        sf.write(tmp_path / f"{name}.wav", np.stack([tone, tone], axis=1), rate)
    stems = [str(tmp_path / f"{n}.wav") for n in ("vocals", "vocals_double", "piano")]
    for chain in (True, False):
        out = str(tmp_path / f"mix_{chain}.wav")
        mixer.mische_spuren(stems, output_pfad=out, vocal_chain=chain, vocal_space=[(0.0, 3.0, "Chorus")],
                            double_windows=[(0.0, 3.0)])
        audio, _ = sf.read(out)
        assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.1


# ── Romaji ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("line, sung", [
    ("kimi no koe", "きみ の こえ"),
    ("konnichiwa sekai", "こんにちわ せかい"),
    ("Tōkyō no yoru", "とうきょう の よる"),
    ("kitto zutto issho da yo!", "きっと ずっと いっしょ だ よ"),
    ("matcha hon'ya", "まっちゃ ほんや"),
    ("君 no koe", "君 の こえ"),
    ("I love you", "I love you"),                    # Englisch bleibt
    ("baby kimi wo aishiteru", "baby kimi wo aishiteru"),
    ("la la la", "la la la"),
])
def test_romaji_becomes_kana(line, sung):
    assert romaji_to_kana(line) == sung


def test_romaji_can_be_switched_off():
    assert syllables("kimi no koe") == ["き", "み", "の", "こ", "え"]
    assert syllables("kimi no koe", romaji=False) == ["kimi", "no", "koe"]


def test_romaji_lyrics_reach_the_song():
    from pipeline import compose
    from settings import SongSettings
    text = "[Verse]\nkimi no koe ga kikoeru\n[Chorus]\nzutto issho ni iyou"
    tracks, _ = compose(SongSettings(lyrics=text, active_sections=["Verse", "Chorus"], seed=3))
    assert "き" in tracks["silben"] and not any(s.isascii() for s in tracks["silben"])
    tracks, _ = compose(SongSettings(lyrics=text, active_sections=["Verse", "Chorus"], seed=3, romaji=False))
    assert "kimi" in tracks["silben"]


def test_vocal_settings_have_switches():
    from settings import SongSettings
    s = SongSettings()
    assert s.vocal_comping and s.phrase_expression and s.vocal_chain and s.romaji
    assert os.path.exists(os.path.join(os.path.dirname(voice_fx.__file__), "requirements.txt"))


# ── im ganzen Ablauf ───────────────────────────────────────────────────────────
def test_two_takes_are_comped_and_double_the_chorus(tmp_path, neutrino_attrappe, caplog):
    import logging

    import pipeline
    from settings import SongSettings
    root, calls = neutrino_attrappe
    s = SongSettings(active_sections=["Verse", "Chorus"], section_bars={"Verse": 4, "Chorus": 4},
                     output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root), singer="MERROW", seed=5,
                     vocal_takes=2, harmonies=False, final_choir=False)
    tracks, _ = pipeline.compose(s)
    out = s.output_dir()
    with caplog.at_level(logging.INFO):
        vocals = pipeline._synthesize_vocals(s, tracks, out)
    assert calls.count("NEUTRINO.exe") == 2
    assert "Phrasen aus den saubersten Fassungen" in caplog.text
    assert os.path.exists(os.path.join(out, "vocals_double.wav"))
    assert not any(n.startswith("vocals_fassung") for n in os.listdir(out))
    assert sf.info(vocals).frames > 0

    # ohne Comping: die sauberste ganze Fassung, keine Doppelung
    pipeline._synthesize_vocals(s.with_updates(vocal_comping=False), tracks, out)
    assert not os.path.exists(os.path.join(out, "vocals_double.wav"))

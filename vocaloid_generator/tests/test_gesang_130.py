# test_gesang_130.py – Gesang 1.3.0: Tonhöhe glätten (G1), Härte zähmen (G2), Verzierungen (G3), Groove (G4),
# Gruppe (G5), Lesungen (G6), Sprechzeilen (G7), DiffSinger-Ausdruck (G8)
import numpy as np
import pytest

import mixdown
import mixer
import resonance
from settings import SongSettings

SR = 44100


def _voice(seconds=4.0, boost_from=2.0, f0=440.0):
    """Eine Stimme aus Obertönen; ab boost_from sticht der Bereich um 3,5 kHz deutlich heraus."""
    t = np.arange(int(SR * seconds)) / SR
    out = np.zeros_like(t)
    for h in range(1, 40):
        f = f0 * h
        if f > 16000:
            break
        amp = 1 / h * (np.where(t > boost_from, 6.0, 1.0) if 3200 < f < 3800 else 1.0)
        out += amp * np.sin(2 * np.pi * f * t)
    return np.stack([out, out]).astype(np.float32) * 0.1


def _band_db(audio, lo, hi, part):
    seg = audio[0, part]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)
    return 10 * np.log10(spec[(freqs > lo) & (freqs < hi)].sum())


@pytest.fixture
def tamer(monkeypatch):
    monkeypatch.setattr(resonance, "MAX_CUT_DB", 6.0)      # conftest.py schaltet es ab


def test_only_what_sticks_out_gets_quieter(tamer):
    voice = _voice()
    tamed = resonance.tame(voice, SR)
    calm, harsh = slice(SR // 2, SR + SR // 2), slice(5 * SR // 2, 7 * SR // 2)
    assert _band_db(tamed, 3200, 3800, harsh) - _band_db(voice, 3200, 3800, harsh) < -2.0
    for lo, hi in ((800, 1400), (5500, 7000)):
        assert abs(_band_db(tamed, lo, hi, harsh) - _band_db(voice, lo, hi, harsh)) < 0.5
    assert abs(_band_db(tamed, 3200, 3800, calm) - _band_db(voice, 3200, 3800, calm)) < 0.5
    assert tamed.shape == voice.shape
    quiet = voice * 0.0
    assert resonance.tame(quiet, SR) is quiet


def test_the_mix_tames_the_voice_only_with_the_switch(tamer, tmp_path, monkeypatch):
    s = SongSettings(output_ordner=str(tmp_path))
    assert mixdown.mix_arguments(s, {}, str(tmp_path), has_vocals=True)["tame"] is True
    assert mixdown.mix_arguments(s.with_updates(resonance_tamer=False), {}, str(tmp_path), has_vocals=True)["tame"] \
        is False
    import soundfile as sf
    path = tmp_path / "vocals.wav"
    sf.write(str(path), _voice().T, SR)
    calls = []
    real = resonance.tame
    monkeypatch.setattr(resonance, "tame", lambda a, r: calls.append(len(a[0])) or real(a, r))
    mixer.mische_spuren([str(path)], output_pfad=str(tmp_path / "mix.wav"), tame=True)
    mixer.mische_spuren([str(path)], output_pfad=str(tmp_path / "mix2.wav"), tame=False)
    assert len(calls) == 1


# ── G6: Wörter richtig lesen ────────────────────────────────────────────────────
@pytest.fixture
def smart(monkeypatch):
    import readings
    monkeypatch.setattr(readings, "ACTIVE", True)


def test_particles_and_number_words_are_sung_like_spoken(smart):
    import pipeline
    text = "[Verse]\nきみは そらへ\nわたしははしる\n[Chorus]\nもう一回 三本の花\n明日も一歩ずつ\nゆめをみた"
    sung = pipeline.sung_lyrics(SongSettings(lyrics=text))
    assert "".join(sung["Verse"]) == "きみわそらえわたしわはしる"     # は in はしる gehört zum Verb
    assert "".join(sung["Chorus"]) == "もういっかいさんぼんのはなあしたもいっぽずつゆめおみた"
    written = pipeline.sung_lyrics(SongSettings(lyrics=text, smart_readings=False))
    assert "".join(written["Verse"]) == "きみはそらへわたしははしる"
    assert "".join(written["Chorus"]).startswith("もういちかい")


def test_spaced_kana_keep_their_syllables_and_only_true_particles_change(smart):
    from lyrics import syllables
    assert syllables("な に か が は じ ま る", smart=True) == list("なにかがはじまる")
    assert syllables("ふ り む か な い で は し り だ せ", smart=True) == list("ふりむかないではしりだせ")
    assert syllables("き み は そ ら へ", smart=True) == list("きみわそらえ")


def test_numbers_and_counters_follow_the_sound_changes():
    from readings import respell
    pairs = {"十回": "じゅっかい", "三十分": "さんじゅっぷん", "十分": "じゅうぶん", "六本": "ろっぽん", "何匹": "なんびき",
             "三階": "さんがい", "四分": "よんぷん", "三百回": "さんびゃっかい", "一ヶ月": "いっかげつ",
             "精一杯": "精一杯", "唯一本気": "唯一本気", "一回り": "ひとまわり", "千本桜": "せんぼんざくら"}
    assert {word: respell(word) for word in pairs} == pairs


def test_own_readings_from_the_file_always_apply(tmp_path):
    import config
    import pipeline
    import readings
    text = "[Verse]\n星空の下 Tokyo"
    assert readings.own_readings() == {}
    readings.ensure_file()
    assert readings.own_readings() == {}          # die Anleitung allein ändert nichts
    with open(readings.path(), "a", encoding="utf-8") as f:
        f.write("星空=ほしぞら\nTokyo = トウキョウ\nkaputt\n")
    assert readings.path().startswith(config.DATA_DIR)
    assert readings.own_readings() == {"星空": "ほしぞら", "Tokyo": "とうきょう"}
    sung = pipeline.sung_lyrics(SongSettings(lyrics=text, smart_readings=False))
    assert "".join(sung["Verse"]) == "ほしぞらのしたとうきょう"


def test_the_text_helper_shows_what_was_read_differently(smart, tmp_path):
    import lyric_helper
    import readings
    with open(readings.ensure_file(), "a", encoding="utf-8") as f:
        f.write("星空=ほしぞら\n")
    s = SongSettings(lyrics="[Verse]\nきみは 星空へ\nもう一回だけ\nよるのまち")
    lines = lyric_helper.check(s)[0].lines
    assert [line.changes for line in lines] == [[("星空", "ほしぞら"), ("は", "わ"), ("へ", "え")],
                                                [("一回", "いっかい")], []]
    off = lyric_helper.check(s.with_updates(smart_readings=False))[0].lines
    assert [line.changes for line in off] == [[("星空", "ほしぞら")], [], []]

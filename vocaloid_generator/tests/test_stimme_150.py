# test_stimme_150.py – Stimme 1.5.0: Ausdruck aus dem Text (St2), lange Töne, die leben (St3), eine Doppelung im
# Refrain, die wie ein zweiter Take wandert (St5)
import numpy as np
import soundfile as sf

import mixer
import singing
import voice_fx
from lyrics import Mora
from settings import SongSettings

RATE = 48000
BPM = 120          # ein Schlag = 0,5 s


def _wav(path, seconds: float) -> str:
    t = np.arange(int(seconds * RATE)) / RATE
    tone = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.05 * np.sin(2 * np.pi * 3300 * t)
    sf.write(path, np.stack([tone, tone], axis=1).astype(np.float32), RATE, subtype="FLOAT")
    return path


def _rms(path, start: float, end: float) -> float:
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    part = audio[int(start * rate):int(end * rate)]
    return float(np.sqrt((part ** 2).mean()))


# Zwei Phrasen mit einer Pause: „なみだ“ (leise), dann „はしれ“ (laut); dazwischen eine neutrale
MELODY = [(64, 1.0), (65, 1.0), (67, 1.0), (None, 1.0), (67, 1.0), (69, 1.0), (71, 1.0), (None, 1.0),
          (60, 1.0), (62, 1.0), (64, 1.0)]
SILBEN = [Mora(m) for m in "なみだはしれあおい"]


def test_lines_with_soft_or_loud_words_are_sung_softer_or_stronger():
    assert voice_fx.text_mood(list("なみだがとまらない")) == -1
    assert voice_fx.text_mood(list("はしれ")) == 1 and voice_fx.text_mood(["ハ", "シ", "レ"]) == 1
    assert voice_fx.text_mood(list("あおいそら")) == 0


def test_text_expression_and_swells_shape_the_sung_track_only_with_their_switches(tmp_path):
    def sing(**switches):
        path = _wav(str(tmp_path / f"gesang_{len(switches)}_{sorted(switches.items())}.wav"), 6.0)
        tracks = {"melody_data": MELODY, "silben": SILBEN, "plan": None}
        s = SongSettings(bpm=BPM, breaths=False, syllable_dynamics=False, phrase_expression=False, final_choir=False,
                         **switches)
        singing._liven(s, tracks, str(tmp_path), path)
        return path
    plain = sing(text_expression=False, note_swells=False)
    text = sing(note_swells=False)
    swells = sing(text_expression=False)
    # Phrase 1 (0–1,5 s) „なみだ“ leiser, Phrase 2 (2–3,5 s) „はしれ“ lauter, Phrase 3 (4–5,5 s) bleibt
    assert _rms(text, 0.2, 1.3) < 0.9 * _rms(plain, 0.2, 1.3)
    assert _rms(text, 2.2, 3.3) > 1.1 * _rms(plain, 2.2, 3.3)
    assert abs(_rms(text, 4.2, 5.3) - _rms(plain, 4.2, 5.3)) < 0.01 * _rms(plain, 4.2, 5.3)
    # gebundene Töne von 0,5 s schwellen nicht an; ein langer schon
    assert np.allclose(sf.read(swells)[0], sf.read(plain)[0], atol=1e-6)


def test_a_held_note_in_the_middle_of_a_phrase_swells():
    notes = [voice_fx.SungNote(0.0, 0.4, 60), voice_fx.SungNote(0.4, 1.6, 62), voice_fx.SungNote(1.6, 2.0, 64)]
    curve = voice_fx.swell_curve(notes, int(2.2 * RATE), RATE)
    assert curve[int(0.5 * RATE)] < 0.5 and curve[int(1.4 * RATE)] > 1.5
    assert abs(curve[int(1.9 * RATE)]) < 0.1, "der letzte Ton der Phrase schwillt nicht (er klingt weich aus)"


def test_the_living_double_wanders_like_a_second_take():
    rng = np.random.default_rng(1)          # Rauschen: der Abstand lässt sich eindeutig messen
    voice = np.convolve(rng.normal(0, 0.2, 4 * mixer.SAMPLE_RATE), np.ones(8) / 8, "same").astype(np.float32)
    audio = np.stack([voice, voice])
    fixed = mixer._double(audio, [(0.0, 4.0)]) - audio
    living = mixer._double(audio, [(0.0, 4.0)], living=True) - audio
    assert not np.allclose(fixed, living)

    def lag(extra, at):
        a = slice(int(at * mixer.SAMPLE_RATE), int((at + 0.4) * mixer.SAMPLE_RATE))
        ref = voice[a]
        return max(range(300, 1600), key=lambda k: float(np.dot(ref, extra[0][a.start + k:a.stop + k])))
    times = (0.5, 1.5, 2.5, 3.2)
    assert max(lag(fixed, at) for at in times) - min(lag(fixed, at) for at in times) <= 25
    assert max(lag(living, at) for at in times) - min(lag(living, at) for at in times) > 100, "der Abstand wandert"
    s = SongSettings()
    assert s.living_double and s.text_expression and s.note_swells


# ── St4 Hör-Check ──────────────────────────────────────────────────────────────────
def _line(text: str, start: float, end: float) -> dict:
    """Eine Zeile wie in liedtext.json: gesungen wird, wie die App den Text liest."""
    import lyrics
    kana = lyrics.to_kana(text)
    step = (end - start) / len(kana)
    return {"start": start, "end": end, "text": text,
            "syllables": [[start + k * step, start + (k + 1) * step, m] for k, m in enumerate(kana)]}


LINES = [_line("既読のままの恋", 0.0, 2.0), _line("君を追いかけて", 3.0, 4.0)]


def test_the_hearing_check_marks_lines_one_cannot_understand():
    import hoercheck
    words = [{"start": 0.1, "end": 0.9, "word": "既読"}, {"start": 0.9, "end": 2.0, "word": "のままの恋"},
             {"start": 3.1, "end": 3.9, "word": "あめがふる"}]
    found = hoercheck.compare(LINES, words)
    assert [line.clear for line in found] == [True, False]
    assert found[0].score > 0.9 and found[1].heard == "あめがふる" and not found[0].readings
    assert "君=きみ" in found[1].readings
    text, warn = hoercheck.describe(found)
    assert warn and "1 von 2" in text and "君を追いかけて" in text
    assert "gehört:   あめがふる" in hoercheck.report(found)
    # gleiche Laute, aber ein anderes Wort geschrieben: vielleicht hat die App falsch gelesen
    import lyrics
    other = [{"start": 0.1, "end": 1.9, "word": "X" + lyrics.to_kana("既読") + "のままの恋"}]
    doubtful = hoercheck.compare(LINES[:1], other)[0]
    assert doubtful.clear and doubtful.doubtful and doubtful.readings == [f"既読={lyrics.to_kana('既読')}"]
    assert "Lesung prüfen: 既読=" in hoercheck.describe([doubtful])[0]
    assert hoercheck.similarity("きみを", "キミオ") == 1.0          # を/お und Katakana zählen gleich


def test_the_hearing_check_runs_after_singing_only_with_its_switch(tmp_path, monkeypatch):
    import hoercheck
    import karaoke
    import pipeline
    from gui import media
    out = str(tmp_path)
    karaoke.save(str(tmp_path / karaoke.FILE), LINES)
    vocals = _wav(str(tmp_path / "vocals.wav"), 4.0)
    heard = []
    monkeypatch.setattr(hoercheck, "available", lambda: True)
    monkeypatch.setattr(hoercheck, "transcribe", lambda audio, folder: heard.append(audio) or [
        {"start": 0.1, "end": 1.9, "word": "既読のままの恋"}, {"start": 3.1, "end": 3.9, "word": "君を追いかけて"}])
    result = pipeline.SongResult(seed=1, output_dir=out, vocals_wav=vocals)
    pipeline._hearing_check(SongSettings(), result, lambda f, m: None)
    assert heard == [vocals] and len(result.hearing) == 2 and all(line.clear for line in result.hearing)
    assert media.hearing(result) == ("Hör-Check: alle 2 Zeilen verständlich", False)
    assert (tmp_path / hoercheck.REPORT_FILE).exists()
    pipeline._hearing_check(SongSettings(hearing_check=False), result, lambda f, m: None)
    assert len(heard) == 1 and result.hearing == [] and not (tmp_path / hoercheck.REPORT_FILE).exists()
    pipeline._hearing_check(SongSettings(draft=True), result, lambda f, m: None)
    assert len(heard) == 1
    monkeypatch.undo()
    assert "setup_hoercheck.py" in hoercheck.status()

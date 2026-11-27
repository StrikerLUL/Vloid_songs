# test_neutrino_noten.py – Noten, die NEUTRINO gut singen kann: Haltezeichen, Atemzeichen, schnelle Stellen, Englisch
import music21
import pytest

import neutrino_score
from lyrics import Mora, english_to_kana, syllables
from neutrino_score import ScoreOptions, build
from vocal_synthesizer import erstelle_musicxml

ON = ScoreOptions()


def lyrics_of(notes):
    return [n.lyric for n in notes if n.pitch is not None]


def total(notes):
    return sum(n.beats for n in notes)


def test_long_vowel_becomes_the_hold_mark():
    silben = syllables("タワー の ゆめ")
    assert [str(s) for s in silben] == ["た", "わ", "あ", "の", "ゆ", "め"]
    assert silben[2].melisma and not silben[1].melisma
    melody = [(64 + i, 1.0) for i in range(6)]
    assert lyrics_of(build(melody, silben, 120, ON)) == ["た", "わ", "ー", "の", "ゆ", "め"]
    assert lyrics_of(build(melody, silben, 120, None)) == ["た", "わ", "あ", "の", "ゆ", "め"]
    off = ScoreOptions(long_vowels=False)
    assert lyrics_of(build(melody, silben, 120, off))[2] == "あ"


def test_melisma_from_the_melody_writer_is_held_but_not_after_a_rest():
    held = Mora("あ", melisma=True)
    melody = [(64, 1.0), (66, 1.0), (None, 2.0), (67, 1.0)]
    assert lyrics_of(build(melody, ["か", held, held], 120, ON)) == ["か", "ー", "あ"]


def test_breath_mark_after_two_bars_of_singing_at_a_short_rest():
    melody = [(64, 1.0)] * 9 + [(None, 0.25)] + [(65, 1.0)] * 3
    notes = build(melody, ["ら"] * 12, 120, ON)
    assert [n.breath for n in notes].index(True) == 8          # der Ton vor der kleinen Pause
    assert all(n.pitch is not None for n in notes)              # die Pause bleibt gebunden
    assert total(notes) == pytest.approx(12.25)
    assert not any(n.breath for n in build(melody, ["ら"] * 12, 120, None))
    assert not any(n.breath for n in build(melody, ["ら"] * 12, 120, ScoreOptions(breath_marks=False)))


def test_breath_waits_for_a_known_word_boundary():
    melody = [(64, 1.0)] * 8 + [(None, 0.25), (65, 1.0), (None, 0.25), (67, 1.0)]
    words = [Mora("ら", word_start=i == 0) for i in range(8)] + [Mora("あ"), Mora("ら", word_start=True)]
    notes = build(melody, words, 120, ON)
    assert [i for i, n in enumerate(notes) if n.breath] == [8]
    assert total(notes) == pytest.approx(10.5)
    assert lyrics_of(notes) == ["ら"] * 8 + ["あ", "ら"]
    # Unannotated text keeps the previous behavior instead of assuming nonexistent word boundaries.
    plain = build(melody, [str(s) for s in words], 120, ON)
    assert [i for i, n in enumerate(plain) if n.breath] == [7]
    one_boundary = [Mora(str(s), word_start=i == 0) for i, s in enumerate(words)]
    assert [i for i, n in enumerate(build(melody, one_boundary, 120, ON)) if n.breath] == [7]


def test_breath_respects_word_boundaries_from_real_japanese_text():
    words = syllables("きみのこえがとどく ありがとう ね", True, True)
    assert len(words) == 15 and words[9].word_start and not words[10].word_start
    melody = [(64, 1.0)] * 10 + [(None, 0.25)] + [(65, 1.0)] * 4 + [(None, 0.25), (67, 1.0)]
    notes = build(melody, words, 120, ON)
    assert not notes[9].breath  # kein Atmer zwischen あ und り in ありがとう
    assert lyrics_of(notes) == [str(word) for word in words]


def test_long_uninterrupted_phrase_waits_for_the_next_known_word():
    melody = [(64, 1.0)] * 18
    words = [Mora("ら", word_start=i in (0, 8, 17)) for i in range(18)]
    notes = build(melody, words, 120, ON)
    assert [i for i, n in enumerate(notes) if n.breath] == [16]
    assert total(notes) == pytest.approx(18)


def test_a_line_without_any_rest_breathes_on_a_long_note_after_four_bars():
    melody = [(64, 0.5)] * 32 + [(65, 2.0)] + [(64, 0.5)] * 8
    notes = build(melody, ["ら"] * 41, 120, ON)
    breaths = [i for i, n in enumerate(notes) if n.breath]
    assert breaths == [32]


@pytest.mark.parametrize("gap, prefix", [(0.25, 8), (0.0, 16)])
def test_breath_waits_until_a_held_vowel_is_finished(gap, prefix):
    held = Mora("あ", melisma=True)
    melody = ([(64, 1.0)] * prefix + ([(None, gap)] if gap else []) + [(65, 1.0)]
              + ([(None, gap)] if gap else []) + [(67, 1.0)])
    syllables = ["ら"] * (prefix - 1) + ["か", held, "ら"]
    notes = build(melody, syllables, 120, ON)
    sung = [n for n in notes if n.pitch is not None]
    assert not sung[prefix - 1].breath
    assert sung[prefix].lyric == "ー"
    assert sung[prefix].breath
    assert total(notes) == pytest.approx(prefix + 2 * gap + 2)
    without_breaths = build(melody, syllables, 120, ScoreOptions(breath_marks=False))
    assert not any(n.breath for n in without_breaths)
    assert lyrics_of(without_breaths)[prefix] == "ー"


def test_fast_notes_share_a_note_as_diphthong():
    melody = [(64, 0.25), (65, 0.25), (64, 0.25), (70, 0.25), (64, 1.0)]
    silben = ["か", "い", "た", "い", "ん"]
    fast = build(melody, silben, 180, ON)                       # Sechzehntel bei 180 BPM: 83 ms
    assert lyrics_of(fast) == ["かい", "た", "い", "ん"]           # たい nicht: der zweite Ton springt eine Quarte
    assert total(fast) == pytest.approx(2.0)
    assert lyrics_of(build(melody, silben, 120, ON)) == silben  # bei 120 BPM schafft NEUTRINO die Sechzehntel
    assert lyrics_of(build(melody, silben, 180, ScoreOptions(fast_diphthongs=False))) == silben


def test_fast_diphthongs_respect_known_word_boundaries():
    melody = [(64, 0.25), (65, 0.25)]
    assert lyrics_of(build(melody, [Mora("か", word_start=True), Mora("い")], 180, ON)) == ["かい"]
    separate = [Mora("か", word_start=True), Mora("い", word_start=True)]
    assert lyrics_of(build(melody, separate, 180, ON)) == ["か", "い"]
    assert total(build(melody, separate, 180, ON)) == pytest.approx(0.5)


def test_musicxml_has_breath_marks_and_keeps_its_length(tmp_path):
    melody = [(64, 1.0)] * 9 + [(None, 0.25)] + [(65, 0.75)] + [(None, 2.0)] + [(64, 0.25), (64, 0.25), (67, 1.5)]
    silben = ["ら"] * 10 + ["か", "い", "ら"]
    plain = erstelle_musicxml(melody, silben, 200, str(tmp_path / "alt.xml"))
    better = erstelle_musicxml(melody, silben, 200, str(tmp_path / "neu.xml"), options=ON)
    assert "breath-mark" in open(better, encoding="utf-8").read()
    assert "breath-mark" not in open(plain, encoding="utf-8").read()
    assert "かい" in open(better, encoding="utf-8").read()
    length = [float(music21.converter.parse(p).highestTime) for p in (plain, better)]
    assert length[0] == pytest.approx(length[1])


def test_options_follow_the_settings():
    from settings import SongSettings
    opts = neutrino_score.options(SongSettings(breath_marks=False))
    assert opts == ScoreOptions(long_vowels=True, breath_marks=False, fast_diphthongs=True)


def test_breath_spacing_is_configurable_without_changing_words_or_duration():
    from settings import SongSettings
    melody = [(64, 1.0)] * 24
    words = [Mora("ら", word_start=i % 2 == 0) for i in range(24)]
    shorter = build(melody, words, 120, neutrino_score.options(SongSettings(breath_phrase_scale=0.5)))
    normal = build(melody, words, 120, neutrino_score.options(SongSettings()))
    longer = build(melody, words, 120, neutrino_score.options(SongSettings(breath_phrase_scale=2.0)))
    assert [i for i, note in enumerate(shorter) if note.breath] == [7, 15, 23]
    assert [i for i, note in enumerate(normal) if note.breath] == [15]
    assert not any(note.breath for note in longer)
    assert all(total(notes) == 24 and lyrics_of(notes) == [str(word) for word in words]
               for notes in (shorter, normal, longer))
    off = build(melody, words, 120, neutrino_score.options(SongSettings(breath_marks=False,
                                                                        breath_phrase_scale=0.5)))
    assert not any(note.breath for note in off)


@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_custom_breath_spacing_respects_word_and_held_vowel_boundaries(scale):
    count = int(16 * scale)
    melody = [(64, 1.0)] * count + [(65, 1.0), (67, 1.0)]
    words = [Mora("ら", word_start=i == 0) for i in range(count - 1)]
    words += [Mora("か"), Mora("あ", melisma=True), Mora("ら", word_start=True)]
    notes = build(melody, words, 120, ScoreOptions(breath_phrase_scale=scale))
    assert not notes[count - 1].breath
    assert notes[count].lyric == "ー" and notes[count].breath
    assert total(notes) == count + 2


def test_breath_spacing_keeps_old_settings_and_changes_vocal_cache(tmp_path):
    from settings import SongSettings
    import singing
    original = SongSettings.model_validate({})
    changed = original.with_updates(breath_phrase_scale=1.5)
    assert neutrino_score.options(original).breath_phrase_scale == 1.0
    assert singing._vocal_key(original, {}) != singing._vocal_key(changed, {})
    path = tmp_path / "settings.json"
    path.write_text(changed.model_dump_json(), encoding="utf-8")
    assert SongSettings.model_validate_json(path.read_text(encoding="utf-8")).breath_phrase_scale == 1.5


@pytest.mark.parametrize("word, kana", [("love", "ラブ"), ("yeah", "イェー"), ("Baby,", "ベイビー"),
                                        ("forever", "フォーエバー")])
def test_english_words_become_katakana(word, kana):
    assert english_to_kana(word) == kana


def test_english_lines_are_sung_in_katakana_and_romaji_lines_stay_romaji():
    assert [str(s) for s in syllables("I love you", True, True)] == ["あ", "い", "ら", "ぶ", "ゆ", "う"]
    assert [str(s) for s in syllables("kimi no koe love", True, True)] == ["き", "み", "の", "こ", "え", "ら", "ぶ"]
    assert syllables("I love you", True, False) == ["I", "love", "you"]
    assert [str(s) for s in syllables("君 の love", True, True)] == ["き", "み", "の", "ら", "ぶ"]


def test_unknown_gibberish_stays_as_written_instead_of_breaking():
    assert english_to_kana("123") == "123"

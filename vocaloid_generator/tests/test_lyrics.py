# test_lyrics.py – Liedtext aus der App in Silben pro Sektion
import pytest

from lyrics import morae, normalize_section, parse_lyrics, syllables
from settings import DEFAULT_LYRICS


def test_default_lyrics_cover_all_sung_sections():
    parsed = parse_lyrics(DEFAULT_LYRICS)
    assert set(parsed) == {"Verse", "PreChorus", "Chorus", "Bridge"}
    assert parsed["Verse"][:3] == ["よ", "る", "の"]


@pytest.mark.parametrize("header,expected", [
    ("Pre-Chorus", "PreChorus"), ("prechorus", "PreChorus"), ("PRE CHORUS", "PreChorus"),
    ("chorus", "Chorus"), ("Build-Up", "Build-up"), (" Verse ", "Verse"), ("Solo", "Solo"),
])
def test_section_names_are_normalized(header, expected):
    assert normalize_section(header) == expected


def test_lines_are_joined_and_text_before_first_header_is_ignored():
    text = "Notiz ohne Sektion\n[Chorus]\nら ら\n\nる る\n[Verse]\n"
    assert parse_lyrics(text) == {"Chorus": ["ら", "ら", "る", "る"]}


def test_repeated_headers_extend_the_section():
    assert parse_lyrics("[Verse]\na b\n[Chorus]\nc\n[Verse]\nd") == {"Verse": ["a", "b", "d"], "Chorus": ["c"]}


@pytest.mark.parametrize("text", ["", None, "nur Text", "[Verse]\n\n"])
def test_empty_input_gives_no_sections(text):
    assert parse_lyrics(text) == {}


@pytest.mark.parametrize("text,expected", [
    ("よるのまち", ["よ", "る", "の", "ま", "ち"]),
    ("きゃっと", ["きゃ", "っ", "と"]),
    ("タワー", ["た", "わ", "あ"]),
    ("ありがとう！", ["あ", "り", "が", "と", "う"]),
])
def test_kana_without_spaces_is_split_into_morae(text, expected):
    assert syllables(text) == expected


def test_kanji_are_read_and_particles_sung_as_spoken():
    assert syllables("夜の街を歩いてた") == ["よ", "る", "の", "ま", "ち", "お", "あ", "る", "い", "て", "た"]
    assert syllables("今日は")[-1] == "わ"


def test_reading_in_brackets_overrides_the_dictionary():
    assert syllables("君[きみ]")[:2] == ["き", "み"]


def test_spaced_kana_and_latin_words_stay_as_they_were():
    assert syllables("よ る の") == ["よ", "る", "の"]
    assert syllables("la la") == ["la", "la"]
    assert morae("ー") == []

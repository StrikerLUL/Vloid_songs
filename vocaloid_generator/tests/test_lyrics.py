# test_lyrics.py – Liedtext aus der App in Silben pro Sektion
import pytest

from lyrics import normalize_section, parse_lyrics
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

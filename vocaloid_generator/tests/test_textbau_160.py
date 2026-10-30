# test_textbau_160.py – Text-Baukasten (1.6.0): von Hand geschriebene Zeilen, passend zur Melodie zusammengesetzt
import random

import pytest

import lyric_helper
import textbaukasten as t
from lyrics import TRANSLATION, syllables
from settings import SongSettings


def test_the_kit_has_600_pieces_and_every_theme_every_role_and_mood():
    assert t.count() == 600
    for theme, lines in t.LINES.items():
        roles = {role: [line for line in lines if line.role == role] for role in "VPCB"}
        assert all(len(found) >= 12 for found in roles.values()), theme
        assert {line.mood for line in lines} == {"h", "n", "d"}, theme
        assert all(5 <= line.count <= 18 for line in lines), theme
        assert len({line.text for line in lines}) == len(lines), theme
        assert len(t.TITLE_WORDS[theme]) == 6
    assert all("{}" in line.text and "{}" in line.german for line in t.HOOK_LINES)


def _pieces() -> list:
    lines = [line for lines in t.LINES.values() for line in lines]
    return lines + [hook.fill(word) for hook in t.HOOK_LINES for words in t.TITLE_WORDS.values() for word in words]


@pytest.mark.parametrize("smart", [True, False])
def test_the_app_sings_every_piece_as_it_is_meant(smart):
    """Partikel は/へ als わ/え, Wörter, die das Wörterbuch falsch liest (既読, 世界中, 走り出そう), mit Lesung von
    Hand; mit „Partikel erkennen“ und ohne."""
    wrong = []
    for line in _pieces():
        sung = [t._same(s) for s in syllables(line.text, romaji=True, english=True, smart=smart)
                if not getattr(s, "melisma", False)]
        if sung != [t._same(s) for s in line.sung]:
            wrong.append(f"{line.text}: {''.join(sung)} statt {line.kana}")
    assert wrong == []


def test_a_song_fits_the_phrases_rhymes_and_starts_and_ends_the_chorus_with_the_title_word():
    s = SongSettings(bpm=150)
    hook = t.title_word("Feuerwerk")
    assert hook.text == "花火"
    song = t.build(s, "sommer", "hell", hook, seed=3)
    text = song.text()
    sections = {sec.name: sec for sec in lyric_helper.check(s, text)}
    assert list(sections) == ["Verse", "PreChorus", "Chorus", "Verse#2", "PreChorus#2", "Bridge"]
    assert all(sec.phrases == len(sec.lines) and not sec.longer for sec in sections.values())
    assert all(line.status == "gut" for sec in sections.values() for line in sec.lines)
    chorus = sections["Chorus"].lines
    assert "花火" in chorus[0].text and "花火" in chorus[-1].text and chorus[0].text != chorus[-1].text
    assert chorus[1].rhyme == chorus[2].rhyme
    verse = sections["Verse"].lines
    assert verse[0].rhyme == verse[2].rhyme or verse[1].rhyme == verse[3].rhyme
    assert {line.text for line in sections["Verse"].lines}.isdisjoint(line.text for line in sections["Verse#2"].lines)
    rows = [row for row in text.splitlines() if row and not row.startswith("[")]
    assert all(TRANSLATION.match(b) and not TRANSLATION.match(a) for a, b in zip(rows[::2], rows[1::2]))
    assert next(p for p in song.parts if p.kind == "Chorus").shared == 3
    assert t.check(song, s) == []
    assert t.build(s, "sommer", "hell", hook, seed=3).text() == text      # derselbe Seed, derselbe Text


def test_the_mood_and_the_tempo_choose_the_lines():
    slow = SongSettings(bpm=80, active_sections=["Intro", "Verse", "Chorus", "Outro"])
    sad = t.build(slow, "abschied", "traurig", seed=1)
    lines = [line for part in sad.parts for line in part.lines if line.role != "H"]
    assert sum(line.mood in ("d", "n") for line in lines) == len(lines)
    assert [p.header for p in sad.parts] == ["[Verse]", "[Chorus]"]
    assert sad.hook in t.TITLE_WORDS["abschied"]
    once = t.build(SongSettings(numbered_lyrics=False), "liebe", seed=2)
    assert [p.header for p in once.parts] == ["[Verse]", "[Pre-Chorus]", "[Chorus]", "[Bridge]"]


def test_a_line_can_be_swapped_for_another_that_fits_as_well():
    s = SongSettings()
    song = t.build(s, "nacht", "bittersüß", seed=5)
    before = song.text()
    old = song.parts[0].lines[1]
    new = t.swap(song, 0, 1, random.Random(1))
    assert new.text != old.text and new.role == "V" and new.text not in before
    assert abs(new.count - song.parts[0].target) <= 6
    chorus = next(i for i, p in enumerate(song.parts) if p.kind == "Chorus")
    hook = t.swap(song, chorus, 0, random.Random(2))
    assert hook.role == "H" and song.hook.text in hook.text
    assert song.text().count("\n> ") == before.count("\n> ")


def test_own_title_words():
    assert t.title_word("feuerwerk").text == "花火"
    assert t.title_word("既読").text == "既読[きどく]"
    own = t.title_word("星屑", "Sternenstaub")
    assert (own.kana, own.german) == ("ほしくず", "Sternenstaub")
    assert t.title_word("Banane") is None and t.title_word("  ") is None
    song = t.build(SongSettings(), "traum", "hell", own, seed=4)
    assert "星屑" in song.parts[2].lines[0].text and "Sternenstaub" in song.parts[2].lines[0].german

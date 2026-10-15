# test_text_helfer.py – Text-Helfer Zeile für Zeile (v6 Nr. 12): Silben gegen Platz, Reime, Lesungen
import lyric_helper
import lyrics
from settings import SongSettings

TEXT = ("[Verse]\nよるのまちをあるく\nきみのこえがきこえる\n"
        "あさまでずっとはしりつづけるよもうとまらないこころのなかでさけぶこえがきこえるからいまはただまえへ\nあ\n"
        "[Chorus]\n夜の街\n君[きみ]の声[こえ]")


def test_each_line_gets_its_room_like_the_melody_gives_it():
    assert lyric_helper.room("Verse", 16, 160) == (15, 48, 4)       # vier Phrasen à vier Takte, 6 Sekunden
    assert lyric_helper.room("Intro", 8, 160) == (0, 0, 0)
    assert lyric_helper.room("Verse", 16, 160, "3/4")[0] < 15        # kürzere Takte, weniger Platz
    verse, chorus = lyric_helper.check(SongSettings(bpm=160), TEXT)
    assert [line.status for line in verse.lines] == ["gut", "gut", "zu viel", "wenig"]
    assert verse.lines[0].describe() == "9 Silben (Platz für etwa 15)"
    assert verse.lines[3].describe().startswith("1 Silbe: lange Töne")
    assert "höchstens 48" in verse.lines[2].describe()
    assert [line.letter for line in verse.lines] == ["A", "A", "B", "C"]          # あるく / きこえる: auf う
    assert [line.rhyme for line in verse.lines] == ["う", "う", "え", "あ"]
    assert chorus.note() == "4 Phrasen, 2 Zeilen: der Text wird wiederholt."
    assert verse.note() == ""


def test_kanji_show_how_they_are_read():
    _, chorus = lyric_helper.check(SongSettings(), TEXT)
    assert [line.reading for line in chorus.lines] == ["よるのまち", "きみのこえ"]
    assert not any(line.unread for line in chorus.lines)


def test_without_a_dictionary_kanji_without_a_reading_are_marked(monkeypatch):
    monkeypatch.setattr(lyrics, "_tagger", lambda: None)
    _, chorus = lyric_helper.check(SongSettings(), TEXT)
    assert [line.unread for line in chorus.lines] == [True, False]       # 君[きみ]の声[こえ] hat seine Lesung von Hand


def test_too_much_text_makes_the_section_longer_and_many_lines_share_phrases():
    many = "[Verse]\n" + "\n".join(["あいうえおかきくけこ"] * 6)
    [verse] = lyric_helper.check(SongSettings(bpm=160), many)
    assert verse.note() == "6 Zeilen auf 4 Phrasen: Zeilen teilen sich eine Phrase."
    assert verse.lines[0].room == 10                                    # 15 · 4/6
    huge = "[Verse]\n" + "\n".join(["あいうえおかきくけこさしすせそ" * 4] * 4)
    [verse] = lyric_helper.check(SongSettings(bpm=160, section_bars={"Verse": 4}), huge)
    assert verse.longer == 32 and "32 statt 4 Takte" in verse.note()



def test_slow_songs_and_six_eight_count_bars_like_the_plan():
    slow = lyric_helper.check(SongSettings(bpm=80), "[Verse]\nよるのまち")[0]
    assert slow.bars == 8                              # langsame Songs: halb so viele Takte (song_plan.SLOW_BPM)
    rocking = lyric_helper.check(SongSettings(bpm=60, meter="6/8"), "[Verse]\nよるのまち")[0]
    assert rocking.bars == 8                           # zwei 6/8-Takte sind ein Takt der Melodie

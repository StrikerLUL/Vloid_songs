# test_eigene_texte.py – Eigener Text für eine wiederholte Strophe oder einen Refrain („[Verse 2]“, v6 Nr. 1)
import pytest

import karaoke
import pipeline
from lyrics import Mora, kind_of, normalize_section, parse_lyrics, section_lines, shared_only
from melody_writer import MelNote, fit_text
from settings import SongSettings

LYRICS = "[Verse]\nよるのまちをあるく\n[Verse 2]\nあさのひかりがまぶしいねきみと\n[Chorus]\nらららら るるる"


@pytest.mark.parametrize("header,expected", [
    ("Verse 2", "Verse#2"), ("Verse2", "Verse#2"), ("2. Strophe", "Verse#2"), ("Refrain 3", "Chorus#3"),
    ("Pre-Chorus 2", "PreChorus#2"), ("Chorus 1", "Chorus"), ("Strophe", "Verse"), ("Vorrefrain", "PreChorus"),
])
def test_numbered_headers_name_one_occurrence(header, expected):
    assert normalize_section(header) == expected
    assert kind_of(normalize_section(header)) == expected.split("#")[0]


def test_numbered_text_is_kept_apart_and_can_be_dropped():
    parsed = parse_lyrics(LYRICS)
    assert set(parsed) == {"Verse", "Verse#2", "Chorus"}
    assert parsed["Verse#2"][:3] == ["あ", "さ", "の"]
    assert set(shared_only(parsed)) == {"Verse", "Chorus"}


def _melody():
    """Vier Takte: Achtel, eine lange Note mit Melisma, Viertel und eine Pause."""
    notes = [MelNote(i * 0.5, 0.5, 60 + i, f"s{i}", i % 2 == 0) for i in range(6)]
    notes += [MelNote(3.0, 2.0, 67, "s6", True), MelNote(5.0, 1.0, 65, Mora("o", melisma=True)), MelNote(6.0, 1.0, 64, "s7")]
    notes += [MelNote(8.0 + i, 1.0, 62, f"t{i}", i == 0) for i in range(4)]
    return notes


KANA = "かなしいねそらよるのまちをあるくひかりがまぶしい"


def _sung(notes):
    return [n.syllable for n in notes if not getattr(n.syllable, "melisma", False)]


def test_same_number_of_syllables_keeps_the_rhythm():
    melody = _melody()
    words = list(KANA[:len(_sung(melody))])        # bei Fremdwörtern wird der Melisma-Ton gebunden
    fitted = fit_text(melody, words)
    assert [(n.start, n.dur, n.pitch) for n in fitted] == [(n.start, n.dur, n.pitch) for n in melody]
    assert _sung(fitted) == words


def test_more_syllables_split_long_notes_on_the_same_pitch():
    melody = _melody()
    words = list(KANA[:len(_sung(melody)) + 4])
    fitted = fit_text(melody, words)
    assert _sung(fitted) == words
    assert {n.pitch for n in fitted} == {n.pitch for n in melody}               # die Melodie bleibt
    assert fitted[0].start == melody[0].start and fitted[-1].start + fitted[-1].dur == 12.0
    assert min(n.dur for n in fitted) >= 0.25
    assert [n.start for n in fitted] == sorted(n.start for n in fitted)


def test_fewer_syllables_hold_the_vowel_or_tie_the_note():
    melody = _melody()
    words = ["か", "な", "し", "い", "ね", "そ", "ら", "よ", "る"]               # drei weniger als Töne mit Silben
    fitted = fit_text(melody, words)
    assert _sung(fitted) == words
    held = [n for n in fitted if getattr(n.syllable, "melisma", False)]
    assert all(str(n.syllable) in "あいうえおん" for n in held)
    assert sum(n.dur for n in fitted) <= sum(n.dur for n in melody) + 1e-9


def test_a_short_text_is_repeated_like_in_the_first_occurrence():
    melody = _melody()
    fitted = fit_text(melody, ["ら", "い"])
    assert _sung(fitted)[:4] == ["ら", "い", "ら", "い"] and len(_sung(fitted)) >= 8


def _settings(tmp_path, **updates):
    return SongSettings().with_updates(**{"active_sections": ["Verse", "Chorus", "Verse", "Chorus"],
                                          "output_ordner": str(tmp_path / "out"), "seed": 4, "lyrics": LYRICS,
                                          **updates})


def _per_section(tracks, bpm):
    spb = 60.0 / bpm
    sections = {}
    for note, syllable in zip(sorted(tracks["vocal_melody"], key=lambda n: n.start), tracks["silben"]):
        sec = tracks["plan"].section_at(note.start / spb + 1e-6)
        if not getattr(syllable, "melisma", False):
            sections.setdefault((sec.kind, sec.occurrence), []).append(str(syllable))
    return sections


def test_the_second_verse_sings_its_own_text(tmp_path):
    s = _settings(tmp_path)
    tracks, _ = pipeline.compose(s)
    sung = _per_section(tracks, s.bpm)
    own = parse_lyrics(LYRICS)["Verse#2"]
    first = parse_lyrics(LYRICS)["Verse"]
    assert sung[("Verse", 2)][:len(own)] == own
    assert sung[("Verse", 1)][:len(first)] == first
    assert sung[("Chorus", 1)] == sung[("Chorus", 2)]


def test_switched_off_every_verse_sings_the_first_text(tmp_path):
    s = _settings(tmp_path, numbered_lyrics=False)
    tracks, _ = pipeline.compose(s)
    sung = _per_section(tracks, s.bpm)
    assert sung[("Verse", 2)] == sung[("Verse", 1)]


def test_lines_to_read_along_follow_the_own_text(tmp_path):
    s = _settings(tmp_path)
    tracks, _ = pipeline.compose(s)
    lengths = {k: [len(line) for line in v] for k, v in section_lines(LYRICS).items()}
    found = karaoke.lines(tracks["vocal_melody"], tracks["silben"], s.bpm, tracks["plan"], lengths)
    assert "".join(parse_lyrics(LYRICS)["Verse#2"]) in [karaoke.text(line) for line in found]

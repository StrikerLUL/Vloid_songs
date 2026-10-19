# test_melodie_130.py – Melodie 1.3.0: beste Fassung (M1), Auftakte (M2), Spannungstöne (M3), Höhepunkt (M4),
# Triolen (M5)
import random

import pytest

import config
import melody_score
import pipeline
from melody_writer import MelNote, SectionMelodyWriter
from orchestrator import _default_lyrics
from settings import SongSettings
from song_plan import build_plan
from styles import get_style


def _plan(style="J-Pop Energy", structure=("Intro", "Verse", "PreChorus", "Chorus", "Outro"), seed=5, bpm=150):
    return build_plan(get_style(style), bpm, list(structure), "A", "minor", config.SECTION_CONFIG,
                      random.Random(seed), {})


def _line(pitches, step=0.5, strong_every=4):
    return [MelNote(i * step, step, p, "ら", i % strong_every == 0) for i, p in enumerate(pitches)]


def test_points_prefer_a_varied_melody_with_a_clear_peak():
    flat = _line([64] * 16)
    jumpy = _line([60, 72, 61, 73, 60, 71, 62, 74] * 2)
    good = _line([64, 65, 67, 69, 67, 65, 64, 62, 64, 67, 69, 72, 71, 69, 67, 64])
    good[11].dur = 1.0
    assert melody_score.score(good, "Chorus") > melody_score.score(flat, "Chorus")
    assert melody_score.score(good, "Chorus") > melody_score.score(jumpy, "Chorus")
    held = _line([64, 65, 67, 69])
    held[-1].syllable, held[-1].dur = "ん", 2.0
    assert melody_score.parts(held, "Verse")["text"] < 1.0


def test_the_chorus_should_go_higher_than_the_verse():
    verse = _line([60, 62, 64, 65, 64, 62] * 2)
    high = _line([67, 69, 71, 72, 71, 69] * 2)
    low = _line([57, 59, 60, 62, 60, 59] * 2)
    assert melody_score.parts(high, "Chorus", verse)["contrast"] > melody_score.parts(low, "Chorus", verse)["contrast"]


def test_the_best_of_many_melodies_sings(new_composition, tmp_path, monkeypatch):
    plan = _plan()
    chorus = next(sec for sec in plan.sections if sec.kind == "Chorus")
    words = _default_lyrics()["Chorus"]
    picked = []
    real_pick = melody_score.pick
    # die Punkte im Moment der Wahl (danach rücken Höhepunkt und Akkord-Netz noch einzelne Töne)
    monkeypatch.setattr(melody_score, "pick", lambda c, *a: picked.append(
        (c, a, real_pick(c, *a), [melody_score.score(x, *a) for x in c])) or picked[-1][2])
    s = SongSettings(output_ordner=str(tmp_path), seed=11)
    on, _ = pipeline.compose(s)
    assert [a[0] for _, a, _, _ in picked] == ["Verse", "PreChorus", "Chorus", "Bridge"]
    assert all(len(c) == melody_score.CANDIDATES for c, _, _, _ in picked)
    candidates, args, (best, points, mean), scores = picked[2]
    assert points == max(scores) >= mean
    assert args[1], "der Refrain kennt die Strophe"
    off, _ = pipeline.compose(s.with_updates(best_melody=False))
    assert on["melody_data"] != off["melody_data"]
    # ohne Schalter schreibt der Schreiber jede Sektion nur einmal
    picked.clear()
    pipeline.compose(s.with_updates(best_melody=False))
    assert picked == []
    assert SectionMelodyWriter(plan, chorus, random.Random(1)).write(words)


def _song(tmp_path, **updates):
    s = SongSettings(output_ordner=str(tmp_path), seed=11).with_updates(**updates)
    tracks, _ = pipeline.compose(s)
    return tracks


@pytest.fixture
def written(monkeypatch):
    """Die Gesangsmelodie, wie melody_writer sie geschrieben hat (MelNotes mit ihren Merkmalen)."""
    import orchestrator
    seen = []
    real = orchestrator.write_vocal_melody
    monkeypatch.setattr(orchestrator, "write_vocal_melody", lambda *a, **k: seen.append(real(*a, **k)) or seen[-1])
    return seen


def _entries_before_the_bar(notes) -> list:
    """Töne nach einer Pause im letzten Schlag eines Takts: so beginnt eine Phrase mit Auftakt."""
    ordered = sorted(notes, key=lambda n: n.start)
    return [n for a, n in zip(ordered, ordered[1:]) if n.start - a.start - a.dur >= 0.25 - 1e-6
            and n.start % 4 >= 3 - 1e-6 and not n.pushed]


def test_phrases_start_before_the_bar_and_downbeats_are_pushed(new_composition, tmp_path, written):
    tracks = _song(tmp_path)
    notes, plan = written[-1], tracks["plan"]
    pushed = [n for n in notes if n.pushed]
    assert pushed and all(abs((n.start + 0.25) % 4) < 1e-6 for n in pushed)
    assert all(n.pitch % 12 in plan.chord_at(n.start + 0.25).pcs or not n.strong for n in pushed), "Akkord danach"
    assert len(_entries_before_the_bar(notes)) >= 2
    ordered = sorted(notes, key=lambda n: n.start)
    assert all(a.start + a.dur <= b.start + 1e-6 for a, b in zip(ordered, ordered[1:])), "nichts überlappt"
    for sec in plan.sections:            # alles bleibt in seiner Sektion
        assert all(n.start + n.dur <= sec.end + 1e-6 for n in notes if sec.start - 1e-6 <= n.start < sec.end)
    # aus: alle Phrasen beginnen im Takt und nichts ist vorgezogen
    _song(tmp_path, melody_pickups=False)
    assert not any(n.pushed for n in written[-1]) and not _entries_before_the_bar(written[-1])
    # im 3/4-Takt bleibt alles im Takt
    _song(tmp_path, meter="3/4")
    assert not any(n.pushed for n in written[-1])


def test_leaning_tones_resolve_and_long_chorus_tones_take_colors(new_composition, tmp_path, written):
    tracks = _song(tmp_path)
    notes, plan = written[-1], tracks["plan"]
    ordered = sorted(notes, key=lambda n: n.start)
    leaning = [(a, b) for a, b in zip(ordered, ordered[1:]) if a.tension and getattr(b.syllable, "melisma", False)
               and abs(b.start - a.start - a.dur) < 1e-6 and 1 <= a.pitch - b.pitch <= 2]
    assert leaning, "Vorhalte, die einen Schritt hinunter auf denselben Vokal gehen"
    for a, b in leaning:
        chord = plan.chord_at(a.start + (0.25 if a.pushed else 0))
        assert a.pitch % 12 not in chord.pcs and b.pitch % 12 in chord.pcs
    colors = [n for n in ordered if n.tension and n.dur >= 1.5]
    assert colors, "lange Töne auf der None oder großen Septime"
    for n in colors:
        chord = plan.chord_at(n.start + (0.25 if n.pushed else 0))
        assert (n.pitch - chord.root) % 12 in (2, 11)
    _song(tmp_path, melody_tensions=False)
    assert not any(n.tension for n in written[-1])


def test_the_last_chorus_ends_on_the_highest_note_of_the_song(new_composition, tmp_path, written):
    tracks = _song(tmp_path, melody_tensions=False)
    notes, plan = written[-1], tracks["plan"]
    sung = [n for n in notes if not getattr(n.syllable, "melisma", False)]
    top = max(n.pitch for n in sung)
    assert [n for n in sung if n.pitch == top] == [max(sung, key=lambda n: n.start)], "einmal, ganz am Ende"
    last = [sec for sec in plan.sections if sec.kind == "Chorus"][-1]
    assert last.start <= max(sung, key=lambda n: n.start).start < last.end
    first = next(sec for sec in plan.sections if sec.kind == "Chorus")
    hook = max(n.pitch for n in sung if first.start <= n.start < first.end)
    assert all(n.pitch < hook for n in sung if plan.section_at(n.start).kind in ("Verse", "PreChorus", "Bridge"))
    _song(tmp_path, melody_tensions=False, melody_climax=False)
    off = [n for n in written[-1] if not getattr(n.syllable, "melisma", False)]
    assert max(n.pitch for n in off) < top or len([n for n in off if n.pitch == max(m.pitch for m in off)]) > 1


def test_chord_spice_adds_dominants_borrowed_chords_and_a_walking_bass():
    import chord_spice
    bars = [["I"], ["vi"], ["IV"], ["V"], ["I"], ["iii"], ["vi"], ["IV"], ["I"], ["IV", "V"], ["I"]]
    seen = set()
    for seed in range(40):
        spiced, done = chord_spice.season(bars, "Chorus", "major", 1.0, random.Random(seed))
        assert len(spiced) == len(bars)
        seen.update(d.split(" vor ")[0] if " vor " in d else d for d in done)
        for bar in spiced:            # jede Stufe lässt sich lesen
            for symbol in bar:
                from theory import parse_roman
                parse_roman(symbol, 0)
    assert {"III7", "laufender Bass", "sus4", "iv", "bVI bVII", "I7"} <= seen, seen
    assert chord_spice.season(bars, "Chorus", "major", 0.0, random.Random(1)) == (bars, [])


def test_the_song_gets_spicier_chords_only_with_the_slider(new_composition, tmp_path):
    def chords(**updates):
        plan = _song(tmp_path, **updates)["plan"]
        return [(slot.start, slot.chord) for sec in plan.sections for slot in sec.chords]
    spicy = chords(chord_spice=1.0)
    plain = chords(chord_spice=0)
    assert spicy != plain
    assert chords(chord_spice=0) == plain
    # die Würze ist für jede Wiederholung gleich: beide Refrains spielen dieselben Akkorde
    plan = _song(tmp_path, chord_spice=1.0)["plan"]
    refrains = [[(s.start - sec.start, s.chord.transposed(-sec.tonic)) for s in sec.chords]
                for sec in plan.sections if sec.kind == "Chorus"]
    assert all(r == refrains[0] for r in refrains)


def _thirds(notes) -> list:
    return [n for n in notes if abs(n.start * 3 - round(n.start * 3)) < 1e-6 and abs(n.start * 4 - round(n.start * 4)) > 1e-6]


def test_triplets_and_dotted_rhythms_reach_neutrino_as_real_tuplets(new_composition, tmp_path, written):
    import re

    import vocal_synthesizer
    from melody_writer import melody_data
    tracks = _song(tmp_path, style="City Pop", bpm=100, melody_tensions=False)
    notes = sorted(written[-1], key=lambda n: n.start)
    thirds = _thirds(notes)
    assert thirds, "Achteltriolen"
    for n in thirds:          # jede Triole füllt ihren Schlag: der Ton davor beginnt eine Triolen-Achtel früher
        before = max((m for m in notes if m.start < n.start - 1e-6), key=lambda m: m.start)
        assert abs(n.start - before.start - 1 / 3) < 1e-6
    dotted = [n for n in notes if abs(n.start % 1 - 0.75) < 1e-6 and not n.pushed
              and any(abs(m.start - (n.start - 0.75)) < 1e-6 and abs(m.dur - 0.75) < 1e-6 for m in notes)]
    assert dotted, "punktierte Achtel mit Sechzehntel"
    data, syllables = melody_data(notes)
    xml = vocal_synthesizer.erstelle_musicxml(data, syllables, 100, str(tmp_path / "triolen.musicxml"))
    text = open(xml, encoding="utf-8").read()
    assert "<time-modification>" in text and "<actual-notes>3</actual-notes>" in text
    import music21
    lead_in = vocal_synthesizer._vorlauf_aus_musicxml(xml)
    assert abs(float(music21.converter.parse(xml).highestTime) - lead_in - sum(d for _, d in data)) < 0.01
    # aus und im 3/4-Takt: alles im Sechzehntel-Raster
    _song(tmp_path, style="City Pop", bpm=100, melody_tensions=False, melody_triplets=False)
    assert not _thirds(written[-1])
    _song(tmp_path, style="City Pop", bpm=100, meter="3/4")
    assert not _thirds(written[-1])
    assert re.search("actual-notes", open(vocal_synthesizer.erstelle_musicxml(
        [(64, 1.0), (None, 0.5), (65, 0.5)], ["ら", "ら"], 100, str(tmp_path / "gerade.musicxml")),
        encoding="utf-8").read()) is None

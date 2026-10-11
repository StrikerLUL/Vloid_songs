# test_composition.py – Eigene Akkorde, eigene MIDI-Melodie, Refrain-Auswahl, Solo und Neu-Würfeln pro Sektion
import random

import pretty_midi
import pytest
import soundfile as sf

import config
import melody_import
import pipeline
from pipeline import compose, hook_choices
from settings import INSTRUMENTS, SongSettings, is_rerollable
from song_plan import BEATS_PER_BAR, build_plan, check_custom, custom_chord, parse_custom
from styles import get_style
from theory import parse_chord_name

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Outro"]


def make_settings(tmp_path, **updates):
    base = {"active_sections": STRUCTURE, "output_ordner": str(tmp_path / "out"), "seed": 21, "key": "C",
            "scale": "major"}
    return SongSettings().with_updates(**{**base, **updates})


def plan_for(structure=STRUCTURE, seed=3, **kwargs):
    return build_plan(get_style("J-Pop Energy"), 160, structure, "C", "major", config.SECTION_CONFIG,
                      random.Random(seed), **kwargs)


def section_chords(plan, kind):
    return [slot.chord.name for sec in plan.sections if sec.kind == kind for slot in sec.chords]


def vocal_by_kind(tracks):
    """{Sektionsart: [(Schlag, Dauer, Tonhöhe)]} der Gesangsmelodie, Schläge ab Sektionsanfang."""
    plan, spb = tracks["plan"], 60 / tracks["plan"].bpm
    out = {}
    for n in tracks["vocal_melody"]:
        sec = plan.section_at(n.start / spb + 1e-6)
        out.setdefault((sec.kind, sec.index), []).append(
            (round(n.start / spb - sec.start, 4), round((n.end - n.start) / spb, 4), n.pitch))
    return out


def notes_by_section(tracks, inst):
    plan, spb = tracks["plan"], 60 / tracks["plan"].bpm
    out = {}
    for n in tracks[inst]:
        sec = plan.section_at(n.start / spb + 0.01)
        out.setdefault((sec.kind, sec.index), []).append((round(n.start, 6), n.pitch, n.velocity))
    return out


def write_midi(path, notes, offset_bars=0, extra_tracks=()):
    """notes: [(Schlag, Dauer, Tonhöhe)] bei 120 BPM (ein Schlag = 0,5 s)."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    melody = pretty_midi.Instrument(program=0, name="Melodie")
    for beat, dur, pitch in notes:
        start = (beat + offset_bars * BEATS_PER_BAR) * 0.5
        melody.notes.append(pretty_midi.Note(90, pitch, start, start + dur * 0.5))
    pm.instruments.append(melody)
    pm.instruments.extend(extra_tracks)
    pm.write(str(path))
    return str(path)


# ── Akkordnamen und eigene Akkorde ────────────────────────────────────────────────
@pytest.mark.parametrize("name,root,quality,bass", [
    ("F#m7", 6, "m7", None), ("C/E", 0, "maj", 4), ("Bb", 10, "maj", None), ("Ebmaj7", 3, "maj7", None),
    ("Gsus4", 7, "sus4", None), ("am", 9, "min", None), ("Bdim", 11, "dim", None),
])
def test_chord_names(name, root, quality, bass):
    chord = parse_chord_name(name)
    assert (chord.root, chord.quality, chord.bass) == (root, quality, bass)


@pytest.mark.parametrize("name", ["H7", "Fxyz", "", "C/X"])
def test_unknown_chord_names_are_rejected(name):
    with pytest.raises(ValueError):
        parse_chord_name(name)


def test_custom_chords_text():
    assert parse_custom("F G Em Am") == [["F"], ["G"], ["Em"], ["Am"]]
    assert parse_custom("F | G | Em Am") == [["F"], ["G"], ["Em", "Am"]]
    assert parse_custom("IV V iii vi") == [["IV"], ["V"], ["iii"], ["vi"]]
    assert check_custom("F G Em Am") == ""
    assert "Fxyz" in check_custom("F Fxyz")


def test_chord_names_move_with_a_key_change_and_numerals_follow_the_section():
    assert custom_chord("F", 0, 0).name == "F"
    assert custom_chord("F", 0, 2).name == "G"         # Schlussrefrain einen Ganzton höher
    assert custom_chord("IV", 0, 2).name == "G"
    assert custom_chord("vi", 9, 9).name == "F#m"


def test_own_chords_play_exactly_as_written():
    plan = plan_for(custom_chords={"Chorus": "F G Em Am", "Verse": "vi | IV | I V"})
    chorus = next(s for s in plan.sections if s.kind == "Chorus")
    assert [s.chord.name for s in chorus.chords][:5] == ["F", "G", "Em", "Am", "F"]
    assert len(chorus.chords) == chorus.bars           # ein Akkord pro Takt, wiederholt bis zum Ende
    verse = next(s for s in plan.sections if s.kind == "Verse")
    assert [s.chord.name for s in verse.chords][:4] == ["Am", "F", "C", "G"]
    assert [s.dur for s in verse.chords][:4] == [4.0, 4.0, 2.0, 2.0]
    # Intro und Outro spielen die eigenen Akkorde des Refrains
    assert section_chords(plan, "Intro")[:4] == ["F", "G", "Em", "Am"]


def test_unreadable_own_chords_fall_back_to_the_style(caplog):
    assert section_chords(plan_for(custom_chords={"Chorus": "F Fxyz"}), "Chorus") == \
        section_chords(plan_for(), "Chorus")
    assert "nicht verstanden" in caplog.text


def test_own_chords_leave_the_other_sections_alone():
    plain, own = plan_for(), plan_for(custom_chords={"Chorus": "F G Em Am"})
    for kind in ("Verse", "PreChorus"):
        assert section_chords(plain, kind) == section_chords(own, kind)


def test_rerolling_the_chords_of_one_section():
    plain, again = plan_for(), plan_for(rerolls={"Chorus": random.Random(5)})
    assert section_chords(plain, "Chorus") != section_chords(again, "Chorus")
    for kind in ("Verse", "PreChorus"):
        assert section_chords(plain, kind) == section_chords(again, kind)
    # Das Intro teilt die Akkorde mit dem Refrain, also würfelt es sie mit
    assert section_chords(plain, "Intro") != section_chords(plan_for(rerolls={"Intro": random.Random(5)}), "Intro")


# ── Neu würfeln pro Sektion ─────────────────────────────────────────────────────────
def test_section_keys_are_checked():
    assert is_rerollable("melody:Chorus") and is_rerollable("bass") and is_rerollable("drums:Solo")
    assert not is_rerollable("melody:Refrain") and not is_rerollable("kazoo:Chorus")
    s = SongSettings(variations={"melody:Chorus": 2, "bass:Kazoo": 1, "bass": 1})
    assert s.variations == {"melody:Chorus": 2, "bass": 1}
    assert s.rerolled("melody:Chorus").variations["melody:Chorus"] == 3
    with pytest.raises(ValueError):
        s.rerolled("melody:Kazoo")


def test_rerolling_the_chorus_melody_keeps_the_verse(tmp_path):
    s = make_settings(tmp_path)
    before, after = compose(s)[0], compose(s.rerolled("melody:Chorus"))[0]
    a, b = vocal_by_kind(before), vocal_by_kind(after)
    assert [a[k] for k in a if k[0] == "Chorus"] != [b[k] for k in b if k[0] == "Chorus"]
    for key in a:
        if key[0] != "Chorus":
            assert a[key] == b[key], key
    for inst in ("drums", "bass", "piano", "strings"):
        assert before[inst] and notes_by_section(before, inst) == notes_by_section(after, inst), inst


def test_rerolling_the_drums_of_the_verse_only(tmp_path):
    s = make_settings(tmp_path)
    before, after = compose(s)[0], compose(s.rerolled("drums:Verse"))[0]
    a, b = notes_by_section(before, "drums"), notes_by_section(after, "drums")
    changed = {key[0] for key in a if a[key] != b.get(key)}
    assert changed == {"Verse"}
    for inst in INSTRUMENTS:
        if inst != "drums":
            assert notes_by_section(before, inst) == notes_by_section(after, inst), inst
    assert before["melody_data"] == after["melody_data"]


def test_rerolling_the_chorus_chords_keeps_the_verse_melody(tmp_path):
    s = make_settings(tmp_path)
    before, after = compose(s)[0], compose(s.rerolled("chords:Chorus"))[0]
    assert section_chords(before["plan"], "Chorus") != section_chords(after["plan"], "Chorus")
    assert section_chords(before["plan"], "Verse") == section_chords(after["plan"], "Verse")
    a, b = vocal_by_kind(before), vocal_by_kind(after)
    assert [a[k] for k in a if k[0] == "Verse"] == [b[k] for k in b if k[0] == "Verse"]


# ── Eigene Melodie aus MIDI ─────────────────────────────────────────────────────────
TUNE = [(0, 1, 64), (1, 1, 67), (2, 0.5, 69), (2.5, 0.5, 67), (3, 1, 64),
        (4, 1.5, 62), (5.5, 0.5, 64), (6, 2, 60)]


def test_loading_a_melody(tmp_path):
    drums = pretty_midi.Instrument(program=0, is_drum=True)
    drums.notes = [pretty_midi.Note(100, 36, i * 0.25, i * 0.25 + 0.1) for i in range(40)]
    pad = pretty_midi.Instrument(program=89)
    pad.notes = [pretty_midi.Note(60, p, 0, 4) for p in (48, 52, 55)]
    # Leicht neben dem Raster und mit einem Zweiklang auf Schlag 4: der höhere Ton gilt
    notes = [(b + 0.02, d, p) for b, d, p in TUNE] + [(4, 1.5, 55)]
    path = write_midi(tmp_path / "tune.mid", notes, offset_bars=2, extra_tracks=(drums, pad))
    melody = melody_import.load(path)
    assert melody == [(float(b), float(d), p) for b, d, p in TUNE]
    assert melody_import.imported_bars(melody) == 2


def test_overlapping_notes_become_one_line(tmp_path):
    path = write_midi(tmp_path / "legato.mid", [(0, 3, 60), (1, 1, 62)])
    assert melody_import.load(path) == [(0.0, 1.0, 60), (1.0, 1.0, 62)]


def test_files_without_a_melody_are_rejected(tmp_path):
    broken = tmp_path / "kaputt.mid"
    broken.write_bytes(b"kein MIDI")
    with pytest.raises(ValueError):
        melody_import.load(str(broken))
    drums = pretty_midi.Instrument(program=0, is_drum=True)
    drums.notes = [pretty_midi.Note(100, 36, 0, 0.1)]
    pm = pretty_midi.PrettyMIDI()
    pm.instruments.append(drums)
    pm.write(str(tmp_path / "drums.mid"))
    with pytest.raises(ValueError):
        melody_import.load(str(tmp_path / "drums.mid"))


@pytest.mark.parametrize("end,bars", [(0, 0), (4, 1), (6, 2), (12, 4), (32, 8), (60, 16)])
def test_imported_length_in_bars(end, bars):
    melody = [(0.0, float(end), 60)] if end else []
    assert melody_import.imported_bars(melody) == bars


def test_own_melody_fills_the_section_in_the_vocal_range():
    plan = plan_for()
    chorus = next(s for s in plan.sections if s.kind == "Chorus")
    low = [(b, d, p - 24) for b, d, p in TUNE]           # zwei Oktaven zu tief geschrieben
    notes = melody_import.fit(low, plan, chorus, ["ら", "ら", "ら"])
    assert len(notes) == len(TUNE) * chorus.bars // 2      # zwei Takte, so oft es passt
    assert [n.pitch for n in notes[:len(TUNE)]] == [p for _, _, p in TUNE]
    assert notes[len(TUNE)].start == chorus.start + 2 * BEATS_PER_BAR
    assert all(n.start < chorus.end for n in notes)
    assert [n.strong for n in notes[:3]] == [True, True, True] and not notes[3].strong


def test_the_chorus_sings_the_own_melody(tmp_path):
    path = write_midi(tmp_path / "tune.mid", TUNE)
    s = make_settings(tmp_path)
    plain, own = compose(s)[0], compose(s.with_updates(melody_midi=path))[0]
    a, b = vocal_by_kind(plain), vocal_by_kind(own)
    first_chorus = next(k for k in b if k[0] == "Chorus")
    assert [(start, pitch % 12) for start, _, pitch in b[first_chorus][:len(TUNE)]] == \
        [(float(beat), p % 12) for beat, _, p in TUNE]
    for key in a:                                       # Strophe und Pre-Chorus bleiben komponiert
        if key[0] in ("Verse", "PreChorus"):
            assert a[key] == b[key], key


def test_a_long_own_melody_makes_the_section_longer(tmp_path):
    long = [(b * 4.0, 4.0, 60 + b % 5) for b in range(32)]    # 32 Takte, mehr als MAX_BARS
    path = write_midi(tmp_path / "lang.mid", long)
    tracks = compose(make_settings(tmp_path, melody_midi=path, melody_midi_section="Verse"))[0]
    verse = next(s for s in tracks["plan"].sections if s.kind == "Verse")
    assert verse.bars == melody_import.MAX_BARS


def test_a_missing_melody_file_composes_as_usual(tmp_path, caplog):
    s = make_settings(tmp_path)
    plain = compose(s)[0]
    missing = compose(s.with_updates(melody_midi=str(tmp_path / "fehlt.mid")))[0]
    assert plain["melody_data"] == missing["melody_data"]
    assert "nicht gefunden" in caplog.text


def test_melody_settings_are_checked():
    with pytest.raises(ValueError):
        SongSettings(melody_midi_section="Refrain")
    s = SongSettings(custom_chords={"Chorus": "F G", "Kazoo": "C", "Verse": "  "})
    assert s.custom_chords == {"Chorus": "F G"}


# ── Solo ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("style", ["J-Pop Energy", "Kawaii Chiptune", "Ballade"])
def test_the_solo_plays_the_lead_over_the_band(tmp_path, style):
    structure = ["Verse", "Chorus", "Solo", "Chorus"]
    tracks = compose(make_settings(tmp_path, style=style, active_sections=structure))[0]
    plan, spb = tracks["plan"], 60 / tracks["plan"].bpm
    solo = next(s for s in plan.sections if s.kind == "Solo")
    lead = [n for n in tracks["melody"] if solo.start <= n.start / spb < solo.end]
    assert len(lead) >= 16
    assert not [n for n in tracks["vocal_melody"] if solo.start <= n.start / spb < solo.end]
    assert notes_by_section(tracks, "drums").get(("Solo", solo.index))
    pm = pretty_midi.PrettyMIDI(str(tmp_path / "out" / "melody.mid"))
    [solo_track] = [i for i in pm.instruments if i.name.endswith("solo")]
    assert solo_track.program == get_style(style).programs["solo"]
    # Das Solo endet auf dem Grundton der Sektion
    assert max(lead, key=lambda n: n.start).pitch % 12 == solo.chords[-1].chord.root


def test_rerolling_the_solo(tmp_path):
    s = make_settings(tmp_path, active_sections=["Verse", "Chorus", "Solo", "Chorus"])
    before, after = compose(s)[0], compose(s.rerolled("melody:Solo"))[0]
    a, b = notes_by_section(before, "melody"), notes_by_section(after, "melody")
    assert {key[0] for key in a if a[key] != b.get(key)} == {"Solo"}
    assert before["melody_data"] == after["melody_data"]


# ── Drei Refrain-Melodien zur Auswahl ─────────────────────────────────────────────
def test_three_chorus_melodies_to_choose_from(tmp_path):
    s = make_settings(tmp_path, active_sections=["Verse", "Chorus"], bpm=160)
    choices = hook_choices(s)
    assert [c.number for c in choices] == [1, 2, 3]
    assert [c.settings.variations for c in choices] == [{"melody:Chorus": n} for n in (1, 2, 3)]
    assert all(c.settings.seed == 21 and c.settings.output_ordner == s.output_ordner for c in choices)
    previews = [sf.read(c.preview) for c in choices]
    seconds = pipeline.HOOK_BARS * BEATS_PER_BAR * 60 / 160
    assert all(rate == 44100 and abs(len(audio) / rate - seconds - 1.0) < 0.05 for audio, rate in previews)
    assert len({audio[: rate * 4].tobytes() for audio, rate in previews}) == 3
    # Nehmen: derselbe Song mit genau dieser Refrain-Melodie
    chosen = compose(choices[1].settings)[0]
    again = compose(s.rerolled("melody:Chorus").rerolled("melody:Chorus"))[0]
    assert chosen["melody_data"] == again["melody_data"]


def test_hooks_without_a_seed_get_one(tmp_path):
    choices = hook_choices(make_settings(tmp_path, seed=None, active_sections=["Chorus"]), count=1)
    assert choices[0].settings.seed is not None


def test_no_hooks_for_an_own_melody_or_without_vocals(tmp_path):
    with pytest.raises(ValueError):
        hook_choices(make_settings(tmp_path, melody_midi="C:/tune.mid", melody_midi_section="Chorus"))
    with pytest.raises(ValueError):
        hook_choices(make_settings(tmp_path, active_sections=["Intro", "Outro"]))
    assert pipeline.hook_kind(make_settings(tmp_path, active_sections=["Intro", "Verse", "Bridge"])) == "Verse"


def test_templates_keep_own_chords_but_not_the_melody_file(tmp_path):
    import vorlagen
    s = SongSettings(custom_chords={"Chorus": "F G Em Am"}, melody_midi="C:/tune.mid", melody_midi_section="Verse")
    vorlagen.save("Akkorde", s, str(tmp_path))
    applied = vorlagen.apply("Akkorde", SongSettings(), str(tmp_path))
    assert applied.custom_chords == {"Chorus": "F G Em Am"}
    assert (applied.melody_midi, applied.melody_midi_section) == ("", "Chorus")

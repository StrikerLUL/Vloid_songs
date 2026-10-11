# test_arrangement.py – Musikalische Regeln eines komponierten Songs
import numpy as np
import pretty_midi
import pytest

import config
from drums import CRASH, GHOST_VELOCITY, KICK, SNARE
from melody_writer import VOCAL_HI, VOCAL_LO
from orchestrator import orchestrate_song
from pipeline import seed_everything
from styles import get_style
from theory import scale_pcs

SHORT_CONFIG = {
    "Intro": {"bars": 4, "has_vocals": False},
    "Verse": {"bars": 8, "has_vocals": True},
    "PreChorus": {"bars": 4, "has_vocals": True},
    "Chorus": {"bars": 8, "has_vocals": True},
    "Outro": {"bars": 4, "has_vocals": False},
}
SHORT_STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]


def compose(tmp_path, style="J-Pop Energy", key="A", mode="minor", bpm=150, structure=SHORT_STRUCTURE,
            section_config=SHORT_CONFIG, seed=7, **kw):
    seed_everything(seed)
    return orchestrate_song(genre=style, bpm=bpm, structure=structure, key=key, mode=mode,
                            section_config=section_config, output_dir=str(tmp_path), style=style, **kw)


def seconds(tracks, beat):
    return beat * 60.0 / tracks["plan"].bpm


def in_section(tracks, sec, notes, tolerance=0.03):
    lo, hi = seconds(tracks, sec.start) - tolerance, seconds(tracks, sec.end) - tolerance
    return [n for n in notes if lo <= n.start < hi]


def chord_at_note(tracks, note):
    plan = tracks["plan"]
    return plan.chord_at(note.start / (60.0 / plan.bpm) + 0.02)


@pytest.fixture(scope="module")
def styled_songs(tmp_path_factory):
    songs = {}
    for style, key, mode, bpm in [("Rock", "E", "minor", 140), ("Kawaii Chiptune", "C", "major", 170),
                                  ("City Pop", "F", "major", 105), ("Ballade", "G", "major", 78),
                                  ("Dark Vocaloid", "D", "minor", 170)]:
        songs[style] = compose(tmp_path_factory.mktemp(style.replace(" ", "")), style, key, mode, bpm)
    return songs


# ── Stile ───────────────────────────────────────────────────────────────────────
def test_rock_uses_band_instruments_only(styled_songs):
    tracks = styled_songs["Rock"]
    assert tracks["guitar"] and tracks["bass"] and tracks["drums"]
    assert not tracks["synth"] and not tracks["strings"] and not tracks["brass"] and not tracks["piano"]


def test_chiptune_uses_synths_and_no_guitar(styled_songs):
    tracks = styled_songs["Kawaii Chiptune"]
    assert tracks["synth"] and tracks["bass"]
    assert not tracks["guitar"]


def test_city_pop_has_electric_piano_guitar_and_brass(styled_songs, tmp_path):
    tracks = styled_songs["City Pop"]
    assert tracks["piano"] and tracks["guitar"] and tracks["brass"]


def test_ballade_starts_without_drums(styled_songs):
    tracks = styled_songs["Ballade"]
    intro = tracks["plan"].sections[0]
    assert not in_section(tracks, intro, tracks["drums"])
    assert in_section(tracks, intro, tracks["piano"])


def test_each_style_writes_its_own_sounds(tmp_path):
    compose(tmp_path, "City Pop", "F", "major", 105)
    piano = pretty_midi.PrettyMIDI(str(tmp_path / "piano.mid")).instruments[0]
    drums = pretty_midi.PrettyMIDI(str(tmp_path / "drums.mid")).instruments[0]
    assert piano.program == get_style("City Pop").programs["piano"]   # E-Piano
    assert drums.is_drum and drums.program == get_style("City Pop").drum_kit


# ── Harmonie ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("style", ["Rock", "Kawaii Chiptune", "City Pop", "Ballade", "Dark Vocaloid"])
def test_accompaniment_plays_the_chords(styled_songs, style):
    tracks = styled_songs[style]
    plan = tracks["plan"]
    for inst in ("piano", "guitar", "strings", "synth", "brass"):
        for n in tracks[inst]:
            beat = n.start / (60.0 / plan.bpm) + 0.02
            now, soon = plan.chord_at(beat), plan.chord_at(beat + 0.55)
            ninth = {(now.root + 2) % 12, (soon.root + 2) % 12}
            assert n.pitch % 12 in set(now.pcs) | set(soon.pcs) | ninth, (style, inst, n.pitch, now.name)


def test_bass_plays_roots_on_the_beat(jpop_song):
    tracks = jpop_song.tracks
    plan = tracks["plan"]
    on_beat = [n for n in tracks["bass"] if abs((n.start / (60 / plan.bpm)) % 1) < 0.05]
    good = [n for n in on_beat if n.pitch % 12 in (chord_at_note(tracks, n).bass_pc, chord_at_note(tracks, n).fifth_pc)]
    assert len(good) / len(on_beat) > 0.9
    assert all(28 <= n.pitch <= 55 for n in tracks["bass"])


# ── Melodie ─────────────────────────────────────────────────────────────────────
def chorus_melodies(tracks):
    plan = tracks["plan"]
    out = []
    for sec in plan.sections:
        if sec.kind == "Chorus":
            notes = in_section(tracks, sec, tracks["vocal_melody"])
            out.append([(round(n.start - seconds(tracks, sec.start), 4), n.pitch) for n in notes])
    return out


def test_every_chorus_sings_the_same_hook(jpop_song):
    first, second, final = chorus_melodies(jpop_song.tracks)
    assert first == second
    assert [t for t, _ in final] == [t for t, _ in first]
    assert all(b - a == 1 for (_, a), (_, b) in zip(first, final)), "Schlussrefrain einen Halbton höher"


def test_chorus_repeats_its_opening_phrase(jpop_song):
    tracks = jpop_song.tracks
    sec = next(s for s in tracks["plan"].sections if s.kind == "Chorus")
    phrase = sec.beats / 4 * 60 / tracks["plan"].bpm
    notes = [(t, p) for t, p in chorus_melodies(tracks)[0]]
    first = [(round(t, 3), p) for t, p in notes if t < phrase - 0.01]
    third = [(round(t - 2 * phrase, 3), p) for t, p in notes if 2 * phrase - 0.01 <= t < 3 * phrase - 0.01]
    assert first and first == third


def test_long_melody_notes_are_chord_tones(jpop_song):
    tracks = jpop_song.tracks
    spb = 60 / tracks["plan"].bpm
    long_notes = [n for n in tracks["vocal_melody"] if n.end - n.start >= spb * 0.99]
    assert long_notes
    for n in long_notes:
        assert n.pitch % 12 in chord_at_note(tracks, n).pcs, (n.pitch, chord_at_note(tracks, n).name)


def test_melody_stays_in_key_and_singable(jpop_song):
    tracks = jpop_song.tracks
    plan = tracks["plan"]
    for n in tracks["vocal_melody"]:
        sec = plan.section_at(n.start / (60 / plan.bpm) + 0.01)
        allowed = set(scale_pcs(sec.tonic, sec.mode)) | set(chord_at_note(tracks, n).pcs)
        assert n.pitch % 12 in allowed
        assert VOCAL_LO <= n.pitch <= VOCAL_HI + 2
    intervals = np.abs(np.diff([n.pitch for n in tracks["vocal_melody"]]))
    assert np.mean(intervals <= 4) > 0.8, "überwiegend Schritte und kleine Sprünge"


def test_melody_data_stays_in_sync_with_the_band(jpop_song):
    tracks = jpop_song.tracks
    spb = 60 / tracks["plan"].bpm
    t, starts = 0.0, []
    for pitch, dur in tracks["melody_data"]:
        if pitch is not None:
            starts.append(t * spb)
        t += dur
    assert np.allclose(starts, [n.start for n in tracks["vocal_melody"]], atol=1e-3)
    assert len(tracks["silben"]) == len(tracks["vocal_melody"])


def test_short_lyrics_are_repeated_to_fill_the_section(tmp_path):
    tracks = compose(tmp_path, lyrics={"Verse": ["ら", "り", "る"], "Chorus": ["あ", "い"], "PreChorus": ["お"]})
    verse = [s for s in tracks["silben"]][:9]
    assert verse == ["ら", "り", "る"] * 3


def test_long_lyrics_make_the_section_longer(tmp_path):
    lyrics = {"Verse": ["ら"] * 200}
    tracks = compose(tmp_path, lyrics=lyrics)
    verse = next(s for s in tracks["plan"].sections if s.kind == "Verse")
    assert verse.bars > SHORT_CONFIG["Verse"]["bars"]
    assert tracks["silben"].count("ら") >= 200


def test_slow_songs_use_half_as_many_bars(tmp_path):
    tracks = compose(tmp_path, style="Ballade", bpm=78)
    verse = next(s for s in tracks["plan"].sections if s.kind == "Verse")
    assert verse.bars == SHORT_CONFIG["Verse"]["bars"] // 2


def test_intro_plays_the_chorus_hook(jpop_song):
    tracks = jpop_song.tracks
    plan = tracks["plan"]
    intro = plan.sections[0]
    chorus = next(s for s in plan.sections if s.kind == "Chorus")
    lead = in_section(tracks, intro, tracks["melody"])
    hook = in_section(tracks, chorus, tracks["vocal_melody"])[:len(lead)]
    assert lead and [n.pitch for n in lead] == [n.pitch for n in hook]


# ── Schlagzeug und Dynamik ──────────────────────────────────────────────────────
def test_chorus_starts_with_a_crash_and_kick(jpop_song):
    tracks = jpop_song.tracks
    for sec in tracks["plan"].sections:
        if sec.kind == "Chorus":
            t0 = seconds(tracks, sec.start)
            hits = {n.pitch for n in tracks["drums"] if abs(n.start - t0) < 0.03}
            assert {CRASH, KICK} <= hits


def test_snare_roll_before_the_chorus(jpop_song):
    tracks = jpop_song.tracks
    for sec in tracks["plan"].sections:
        if sec.kind == "PreChorus":
            last_bar = seconds(tracks, sec.end - 4)
            snares = [n for n in tracks["drums"] if n.pitch == SNARE and last_bar - 0.03 <= n.start < seconds(tracks, sec.end) - 0.03]
            assert len(snares) >= 10
            assert snares[-1].velocity > snares[0].velocity


def test_band_breaks_on_the_last_beat_before_the_chorus(jpop_song):
    tracks = jpop_song.tracks
    for sec in tracks["plan"].sections:
        if sec.kind == "PreChorus":
            lo, hi = seconds(tracks, sec.end - 1) + 0.03, seconds(tracks, sec.end) - 0.03
            for inst in ("piano", "bass", "guitar", "strings", "synth", "brass"):
                assert not [n for n in tracks[inst] if lo <= n.start < hi], inst


def test_ghost_notes_are_quiet(jpop_song):
    snares = [n.velocity for n in jpop_song.tracks["drums"] if n.pitch == SNARE]
    ghosts = [v for v in snares if v <= GHOST_VELOCITY + 4]
    assert ghosts and max(ghosts) < min(v for v in snares if v not in ghosts)


def test_chorus_is_louder_than_verse(jpop_song):
    tracks = jpop_song.tracks
    sections = tracks["plan"].sections
    verse = next(s for s in sections if s.kind == "Verse")
    chorus = next(s for s in sections if s.kind == "Chorus")
    for inst in ("piano", "bass", "drums"):
        v = np.mean([n.velocity for n in in_section(tracks, verse, tracks[inst])])
        c = np.mean([n.velocity for n in in_section(tracks, chorus, tracks[inst])])
        assert c > v + 8, (inst, v, c)


def test_song_ends_on_one_chord(jpop_song):
    tracks = jpop_song.tracks
    last_bar = seconds(tracks, tracks["plan"].total_beats - 4)
    for name in ("piano", "bass", "guitar", "strings"):
        late = [n for n in tracks[name] if n.start > last_bar + 0.03]
        assert not late, name


def test_guitars_are_double_tracked_left_and_right(jpop_song):
    midi = pretty_midi.PrettyMIDI(jpop_song.output_dir + "/guitar.mid")
    pans = sorted(cc.value for inst in midi.instruments for cc in inst.control_changes if cc.number == 10)
    assert pans and pans[0] < 40 and pans[-1] > 88


# ── Viele Tonarten und Tempi ────────────────────────────────────────────────────
@pytest.mark.parametrize("key,mode,bpm", [
    ("A", "minor", 160), ("C", "major", 160), ("E", "minor", 160), ("D", "phrygian", 160),
    ("G", "dorian", 160), ("A", "minor", 90), ("A", "minor", 200),
])
def test_all_pitched_notes_fit_key_or_chord(tmp_path, key, mode, bpm):
    tracks = compose(tmp_path, key=key, mode=mode, bpm=bpm, seed=99, structure=["Intro", "Verse", "PreChorus", "Chorus", "Outro"],
                     section_config=config.SECTION_CONFIG)
    plan = tracks["plan"]
    for name in ("piano", "guitar", "strings", "synth", "melody", "vocal_melody"):
        for n in tracks[name]:
            beat = n.start / (60 / bpm) + 0.02
            sec = plan.section_at(beat)
            allowed = set(scale_pcs(sec.tonic, sec.mode)) | set(plan.chord_at(beat).pcs) | set(plan.chord_at(beat + 0.55).pcs)
            assert n.pitch % 12 in allowed, (name, n.pitch)

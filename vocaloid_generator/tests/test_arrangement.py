# test_arrangement.py – Musikalische Regeln des Orchestrators (übernommen aus den alten Prüfskripten)
import re

import numpy as np
import pretty_midi
import pytest

import config
from humanizer import humanize_notes
from orchestrator import ALLOWED_INSTRUMENTS, PATTERN_MAP, get_section_key, orchestrate_song
from pipeline import seed_everything
from song_helpers import scale_pitch_classes, section_windows

SHORT_CONFIG = {
    "Intro": {"bars": 2, "has_vocals": False},
    "Verse": {"bars": 4, "has_vocals": True},
    "Chorus": {"bars": 4, "has_vocals": True},
    "Outro": {"bars": 2, "has_vocals": False},
}
SHORT_STRUCTURE = ["Intro", "Verse", "Chorus", "Outro"]


@pytest.fixture(scope="module")
def genre_songs(tmp_path_factory):
    songs = {}
    for genre, bpm, key, mode in [("Rock", 120, "A", "minor"), ("EDM", 128, "C", "major"), ("Lo-Fi", 75, "F", "major")]:
        seed_everything(7)
        out = tmp_path_factory.mktemp(genre.lower())
        songs[genre] = (orchestrate_song(genre=genre, bpm=bpm, structure=SHORT_STRUCTURE, key=key, mode=mode,
                                         section_config=SHORT_CONFIG, output_dir=str(out)), bpm, out)
    return songs


# ── Genres ──────────────────────────────────────────────────────────────────────
def test_rock_uses_band_instruments_only(genre_songs):
    tracks = genre_songs["Rock"][0]
    assert tracks["guitar"] and tracks["bass"]
    assert not tracks["synth"] and not tracks["strings"] and not tracks["brass"]


def test_edm_uses_synths_and_no_acoustic_instruments(genre_songs):
    tracks = genre_songs["EDM"][0]
    assert tracks["synth"] and tracks["bass"]
    assert not tracks["guitar"] and not tracks["strings"] and not tracks["brass"]


def test_lofi_has_piano_and_strings(genre_songs):
    tracks = genre_songs["Lo-Fi"][0]
    assert tracks["piano"] and tracks["strings"]


def test_humanized_velocities_and_timing_vary(genre_songs):
    for genre, (tracks, _, _) in genre_songs.items():
        bass = tracks["bass"]
        assert len({n.velocity for n in bass}) > 1, genre
        assert len({n.start for n in bass}) > 1, genre


@pytest.mark.parametrize("instrument", ["bass", "piano"])
def test_humanization_spread_depends_on_genre(instrument):
    # Gleiche Noten auf dem Raster, nur der Humanizer entscheidet über die Streuung
    bpm = 120
    grid = 60.0 / bpm  # nur Viertel, damit kein Swing greift

    def humanized(genre):
        seed_everything(3)
        notes = [pretty_midi.Note(velocity=90, pitch=40, start=i * grid, end=i * grid + 0.1) for i in range(1, 401)]
        humanize_notes(notes, genre, instrument, bpm, swing=0.0)
        offsets = [n.start - i * grid for i, n in enumerate(notes, start=1)]
        return np.var([n.velocity for n in notes]), np.var(offsets)

    edm, rock, lofi = humanized("EDM"), humanized("Rock"), humanized("Lo-Fi")
    assert edm[0] < rock[0] < lofi[0]
    assert edm[1] < rock[1] < lofi[1]


def test_midi_files_are_written_to_the_output_folder(genre_songs):
    _, _, out = genre_songs["Lo-Fi"]
    pm = pretty_midi.PrettyMIDI(str(out / "piano.mid"))
    assert len(pm.instruments) == 1 and pm.instruments[0].notes


# ── Kompletter J-Pop-Song ───────────────────────────────────────────────────────
def test_every_note_is_in_the_key_of_its_section(jpop_song):
    windows = section_windows(jpop_song.structure, jpop_song.bpm)
    beat = 60.0 / jpop_song.bpm
    occurrences = {}
    keys = []
    for w in windows:
        occurrences[w.type] = occurrences.get(w.type, 0) + 1
        keys.append(get_section_key(w.type, occurrences[w.type], jpop_song.key, jpop_song.mode, structure=jpop_song.structure))

    for name, notes in jpop_song.note_tracks().items():
        if name == "drums":
            continue
        for note in notes:
            idx = next(i for i, w in enumerate(windows) if w.contains(note))
            allowed = scale_pitch_classes(keys[idx], jpop_song.mode)
            if note.start >= windows[idx].end - beat and idx + 1 < len(windows):
                # Überleitungsnoten im letzten Schlag nehmen den Grundton der nächsten Sektion vorweg
                allowed |= scale_pitch_classes(keys[idx + 1], jpop_song.mode)
            assert note.pitch % 12 in allowed, f"{name}: Pitch {note.pitch} liegt nicht in {keys[idx]} {jpop_song.mode}"


def test_every_track_has_velocity_dynamics(jpop_song):
    for name, notes in jpop_song.note_tracks().items():
        if notes:
            velocities = [n.velocity for n in notes]
            assert len(set(velocities)) > 1 and np.var(velocities) > 0.5, name


def test_sections_follow_the_arrangement_plan(jpop_song):
    patterns = PATTERN_MAP["j-pop"]
    for w in section_windows(jpop_song.structure, jpop_song.bpm):
        melody = [n for n in jpop_song.tracks["melody"] if w.contains(n)]
        assert bool(melody) == config.SECTION_CONFIG[w.type]["has_vocals"], f"Melodie in {w.type} #{w.index}"

        allowed = ALLOWED_INSTRUMENTS.get(w.type, [])
        for inst, pattern in patterns.get(w.type, {}).items():
            notes = [n for n in jpop_song.tracks[inst] if w.contains(n)]
            expected = pattern is not None and inst in allowed
            assert bool(notes) == expected, f"{inst} in {w.type} #{w.index}: erwartet {'aktiv' if expected else 'still'}"


def test_chorus_phrases_have_an_arch_contour(jpop_song):
    for w in section_windows(jpop_song.structure, jpop_song.bpm):
        if w.type != "Chorus":
            continue
        notes = sorted((n for n in jpop_song.tracks["melody"] if w.contains(n)), key=lambda n: n.start)
        phrases, current = [], []
        for n in notes:
            if current and n.start - current[-1].end > 0.15:
                phrases.append(current)
                current = []
            current.append(n)
        phrases.append(current)
        for phrase in (p for p in phrases if len(p) >= 4):
            pitches = [n.pitch for n in phrase]
            peaks = [i for i, p in enumerate(pitches) if p == max(pitches)]
            assert any(i >= len(phrase) // 2 for i in peaks), f"Höhepunkt zu früh: {pitches}"
            assert pitches[-1] < pitches[0], f"Phrase endet nicht tiefer: {pitches}"


def test_adjacent_sections_use_different_progressions(jpop_song):
    roots = jpop_song.tracks["section_roots"]
    for a, b in zip(roots, roots[1:]):
        if {"Intro", "Outro"} & {a["type"], b["type"]}:
            continue
        assert a["roots"] != b["roots"], f"{a['type']} und {b['type']} haben dieselbe Akkordfolge"


def test_velocity_rises_from_intro_to_chorus(jpop_song):
    # Gleiche Instrumente vergleichen: das Intro hat kein Schlagzeug, dessen leise Hi-Hats den Schnitt sonst drücken
    windows = section_windows(jpop_song.structure, jpop_song.bpm)
    first = {name: next(w for w in windows if w.type == name) for name in ("Intro", "Verse", "Chorus")}
    for inst in ("piano", "bass"):
        means = [np.mean([n.velocity for n in jpop_song.tracks[inst] if first[name].contains(n)])
                 for name in ("Intro", "Verse", "Chorus")]
        assert means[0] < means[1] < means[2], f"{inst}: {means}"


def test_drop_is_kick_and_bass_only(jpop_song):
    drop = next(w for w in section_windows(jpop_song.structure, jpop_song.bpm) if w.type == "Drop")
    for name, notes in jpop_song.note_tracks().items():
        if name in ("drums", "bass"):
            continue
        assert not [n for n in notes if drop.contains(n)], f"{name} spielt im Drop"
    drums = [n for n in jpop_song.tracks["drums"] if drop.contains(n)]
    assert drums and all(n.pitch == 36 for n in drums)
    assert [n for n in jpop_song.tracks["bass"] if drop.contains(n)]


def test_final_chorus_is_a_semitone_higher_and_louder(jpop_song):
    choruses = [w for w in section_windows(jpop_song.structure, jpop_song.bpm) if w.type == "Chorus"]
    second, final = choruses[1], choruses[-1]

    def notes(track, window):
        return [n for n in jpop_song.tracks[track] if window.contains(n)]

    def pitch_class_shift(track):
        # Der Bass klappt hohe Töne eine Oktave nach unten, deshalb Tonklassen statt Mittelwert vergleichen
        before = np.bincount([n.pitch % 12 for n in notes(track, second)], minlength=12)
        after = np.bincount([n.pitch % 12 for n in notes(track, final)], minlength=12)
        overlap = [np.minimum(before, np.roll(after, -k)).sum() for k in range(12)]
        return int(np.argmax(overlap))

    assert pitch_class_shift("bass") == 1
    assert np.mean([n.velocity for n in notes("bass", final)]) > np.mean([n.velocity for n in notes("bass", second)]) + 10.0


@pytest.mark.xfail(reason="Jeder Refrain bekommt bisher eine neue Melodie; die Hook zu wiederholen ist für Phase 2 geplant",
                   strict=False)
def test_final_chorus_melody_is_higher(jpop_song):
    choruses = [w for w in section_windows(jpop_song.structure, jpop_song.bpm) if w.type == "Chorus"]

    def mean_pitch(window):
        return np.mean([n.pitch for n in jpop_song.tracks["melody"] if window.contains(n)])

    assert mean_pitch(choruses[-1]) - mean_pitch(choruses[1]) >= 0.99


def test_ghost_snares_are_quiet(jpop_song):
    for note in (n for n in jpop_song.tracks["drums"] if n.pitch == 40):
        assert 20 <= note.velocity <= 40


def test_default_lyrics_are_natural_japanese():
    assert re.search(r"[ぁ-ん]\s+[ぁ-ん]", config.SONG_TEXT_VERSE) is None


# ── Viele Tonarten und Tempi (aus dem alten Stresstest) ─────────────────────────
@pytest.mark.parametrize("key,mode,bpm", [
    ("A", "minor", 160), ("C", "major", 160), ("E", "minor", 160), ("D", "phrygian", 160),
    ("G", "dorian", 160), ("A", "minor", 90), ("A", "minor", 200),
])
def test_scale_locking_holds_for_many_keys(tmp_path, key, mode, bpm):
    seed_everything(99)
    structure = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]
    tracks = orchestrate_song(genre="J-Pop", bpm=bpm, structure=structure, key=key, mode=mode,
                              section_config=config.SECTION_CONFIG, output_dir=str(tmp_path))
    final_key = get_section_key("Chorus", 1, key, mode, structure=structure)
    allowed = scale_pitch_classes(key, mode) | scale_pitch_classes(final_key, mode)
    for name, notes in tracks.items():
        if name in ("drums", "silben", "melody_data", "section_roots"):
            continue
        assert all(n.pitch % 12 in allowed for n in notes), name

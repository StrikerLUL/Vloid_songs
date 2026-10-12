# test_motifs.py – mehr eingebaute Rhythmen und Gesten, und gelernte aus MIDI-Dateien
import collections
import os

import pretty_midi
import pytest

import main
import motifs
import pipeline
from melody_writer import BAR_STEPS, END_RELEASE, GESTURES
from settings import SongSettings

SPB = 0.5          # 120 BPM


def write_midi(path, bars, time_signature=(4, 4), extra_tracks=True):
    """Eine Melodie-Spur; bars: pro Takt [(Sechzehntel, Tonhöhe)]. Dazu Akkorde, Bass und Schlagzeug."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    pm.time_signature_changes.append(pretty_midi.TimeSignature(*time_signature, 0.0))
    steps_per_bar = time_signature[0] * 4
    melody = pretty_midi.Instrument(0, name="Melodie")
    for b, notes in enumerate(bars):
        for step, pitch in notes:
            start = (b * steps_per_bar + step) * SPB / 4
            melody.notes.append(pretty_midi.Note(90, pitch, start, start + SPB / 4))
    pm.instruments.append(melody)
    if extra_tracks:
        chords, bass, drums = pretty_midi.Instrument(0), pretty_midi.Instrument(33), pretty_midi.Instrument(0, is_drum=True)
        for b in range(len(bars)):
            t = b * steps_per_bar * SPB / 4
            chords.notes += [pretty_midi.Note(70, p, t, t + 1.5) for p in (60, 64, 67)]
            bass.notes += [pretty_midi.Note(90, 36, t + k * 0.5, t + k * 0.5 + 0.4) for k in range(4)]
            drums.notes += [pretty_midi.Note(100, 36, t + k * 0.5, t + k * 0.5 + 0.1) for k in range(4)]
        pm.instruments += [chords, bass, drums]
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    pm.write(str(path))
    return str(path)


def offbeat_song(path, bars=14):
    """Jeder Takt nur auf den ungeraden Sechzehnteln, mit 2 bis 8 Tönen: so singen die eingebauten Motive nie."""
    return write_midi(path, [[(1 + 2 * i, 64 + i % 3) for i in range(2 + b % 7)] for b in range(bars)])


def test_the_melody_track_is_found_and_split_into_bars(tmp_path):
    two_bars = [[(0, 60), (4, 62), (8, 64), (12, 65)], [(0, 67), (6, 65), (8, 64)]]
    path = write_midi(tmp_path / "a.mid", two_bars * 2)
    assert motifs.melody_bars(path) == [((0, 4, 8, 12), [60, 62, 64, 65]), ((0, 6, 8), [67, 65, 64])] * 2
    assert motifs.melody_bars(write_midi(tmp_path / "kurz.mid", two_bars)) == []      # zu wenig Töne


def test_bars_in_three_four_are_skipped(tmp_path):
    path = write_midi(tmp_path / "walzer.mid", [[(0, 60), (4, 62), (8, 64)]] * 8, time_signature=(3, 4))
    assert motifs.melody_bars(path) == []


def test_learning_keeps_the_common_rhythms_and_gestures(tmp_path):
    folder = tmp_path / "motive"
    write_midi(folder / "a.mid", [[(0, 60), (3, 64), (6, 67), (10, 64)]] * 6 + [[(0, 60), (8, 62)]] * 2)
    write_midi(folder / "unter" / "b.MIDI", [[(0, 72), (3, 71), (6, 69), (10, 67)]] * 3)
    (folder / "kaputt.mid").write_bytes(b"keine MIDI-Datei")
    learned = motifs.learn(str(folder))
    assert learned.files == 2
    assert collections.Counter(learned.learned[4]) == {(0, 3, 6, 10): 9}      # häufig = öfter gewählt
    assert learned.learned[2] == [(0, 8)] * 2
    shapes = dict((tuple(s), n) for s, n in learned.learned_gestures)
    assert shapes[(-3.5, 0.5, 3.5, 0.5)] == 6 and shapes[(2.5, 1.5, -0.5, -2.5)] == 3
    assert motifs.learn(str(folder)) is learned                               # unverändert: aus dem Speicher
    assert motifs.learn(str(tmp_path / "leer")) is None


def test_gestures_are_limited_and_need_three_notes():
    assert motifs.gesture_shape([60, 72, 60]) == (-5.0, 5.0, -5.0)
    assert motifs.gesture_shape([60, 62]) is None
    assert motifs.gesture_shape([64, 64, 64]) is None


def test_more_rhythms_and_gestures_fit_the_bar():
    for count, options in motifs.MORE_BODY.items():
        for onsets in options:
            assert len(onsets) == count and list(onsets) == sorted(set(onsets)) and onsets[-1] < BAR_STEPS
    for count, options in motifs.MORE_END.items():
        assert all(len(o) == count and o[-1] < END_RELEASE for o in options)
    extra = motifs.more()
    for name in motifs.MORE_GESTURES:
        assert name not in GESTURES
        for k in range(1, 9):
            assert len(extra.gesture(name, k)) == k
    for kind, weights in motifs.MORE_GESTURE_WEIGHTS.items():
        assert set(weights) <= set(motifs.MORE_GESTURES)


def _odd_bars(settings):
    """Takte der Gesangsmelodie, die nur auf ungeraden Sechzehnteln singen."""
    tracks, _ = pipeline.compose(settings)
    spb = tracks["plan"].seconds_per_beat
    bars = collections.defaultdict(list)
    for n in tracks["vocal_melody"]:
        steps = round(n.start / spb * 4)
        bars[steps // BAR_STEPS].append(steps % BAR_STEPS)
    return sum(1 for steps in bars.values() if all(s % 2 for s in steps))


@pytest.fixture
def song(tmp_path):
    return SongSettings(output_ordner=str(tmp_path / "out"), seed=5, active_sections=["Verse", "Chorus"])


def test_the_melody_sings_learned_rhythms(song):
    offbeat_song(os.path.join(motifs.FOLDER, "lied.mid"))
    assert _odd_bars(song) >= 3
    assert _odd_bars(song.with_updates(learned_motifs=False)) == 0
    assert "aus 1 von 1 MIDI-Dateien" in motifs.status(song)


def test_an_own_motif_folder(song, tmp_path):
    offbeat_song(tmp_path / "meine" / "lied.mid")
    assert _odd_bars(song) == 0
    assert _odd_bars(song.with_updates(motif_folder=str(tmp_path / "meine"))) >= 3


def test_without_both_switches_the_melody_is_the_old_one(song):
    assert motifs.for_settings(song.with_updates(more_motifs=False, learned_motifs=False)) is None
    assert motifs.for_settings(song.with_updates(learned_motifs=False)).body == motifs.MORE_BODY
    melodies = []
    for more in (True, False):
        tracks, _ = pipeline.compose(song.with_updates(more_motifs=more, learned_motifs=False))
        melodies.append([(round(n.start, 4), n.pitch) for n in tracks["vocal_melody"]])
    assert melodies[0] != melodies[1]


def test_status_without_files(song):
    assert "keine MIDI-Dateien" in motifs.status(song)
    assert motifs.status(song.with_updates(learned_motifs=False)) == "Gelernte Motive: aus"


def test_cli_motif_options(song, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(main, "generate_song", lambda settings, progress=None: seen.append(settings) or
                        pipeline.SongResult(seed=1, output_dir=str(tmp_path), settings=settings))
    song.save()
    assert main.main(["--motive", str(tmp_path / "meine"), "--ohne-motive"]) == 0
    s = seen[-1]
    assert (s.motif_folder, s.more_motifs, s.learned_motifs) == (str(tmp_path / "meine"), False, False)

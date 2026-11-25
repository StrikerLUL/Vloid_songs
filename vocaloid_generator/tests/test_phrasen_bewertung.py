import pytest

import melody_score
import musicality
from lyrics import Mora
from melody_writer import MelNote


def test_recovery_does_not_join_movements_from_different_phrases():
    notes = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 67, "ら"),
             MelNote(4, 1, 60, "ら"), MelNote(5, 1, 62, "ら")]
    old = melody_score.parts(notes, "Verse")
    new = melody_score.parts(notes, "Verse", extras=("musical_coherence",))
    assert old["recovery"] == pytest.approx(0.7)
    assert new["recovery"] == pytest.approx(0.5)
    notes.append(MelNote(6, 1, 69, "ら"))
    notes.append(MelNote(7, 1, 67, "ら"))
    assert melody_score.parts(notes, "Verse", extras=("musical_coherence",))["recovery"] == 1.0


def test_repeated_pitch_run_restarts_after_phrase_pause():
    notes = [MelNote(t, 1, 60, "ら") for t in (0, 1, 2, 5, 6, 7)]
    old = melody_score.parts(notes, "Verse")
    new = melody_score.parts(notes, "Verse", extras=("musical_coherence",))
    assert old["runs"] < new["runs"]
    assert new["runs"] == 1.0


def test_held_vowel_does_not_create_a_false_phrase_break():
    notes = [MelNote(0, 1, 60, "か"), MelNote(1, 2, 60, Mora("あ", melisma=True)),
             MelNote(3, 1, 60, "ら"), MelNote(4, 1, 60, "ら"), MelNote(5, 1, 60, "ら")]
    assert melody_score.parts(notes, "Verse", extras=("musical_coherence",))["runs"] == pytest.approx(0.7)


def test_prepared_phrase_peak_is_considered_only_in_coherent_mode():
    prepared = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 64, "ら"), MelNote(2, 1, 65, "ら", strong=True)]
    abrupt = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 58, "ら"), MelNote(2, 1, 65, "ら", strong=True)]
    assert melody_score.parts(prepared, "Verse")["arc"] == 0
    assert melody_score.parts(prepared, "Verse", extras=("musical_coherence",))["arc"] == 1
    assert melody_score.parts(abrupt, "Verse", extras=("musical_coherence",))["arc"] == -1


def test_prepared_peak_does_not_replace_a_more_harmonious_candidate(monkeypatch):
    prepared = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 64, "ら"), MelNote(2, 1, 65, "ら", strong=True)]
    abrupt = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 58, "ら"), MelNote(2, 1, 65, "ら", strong=True)]
    monkeypatch.setattr(melody_score, "score", lambda notes, *args: 10.2 if notes is prepared else 10.0)
    monkeypatch.setattr(musicality, "harmony_scores", lambda notes, plan: {"harmony": 0.8 if notes is prepared else 0.9})
    selected, _, _ = melody_score.pick([prepared, abrupt], "Verse", extras=("musical_coherence",), plan=object())
    assert selected == 1

"""Regressionen für musikalische Entscheidungen; auch ohne Audio-Engines mit unittest ausführbar."""
import copy
import json
import random
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ensemble
import geschmack
import melody_score
import musicality
import sound_palettes
from config import SECTION_CONFIG
from lyrics import Mora
from melody_writer import MelNote, SectionMelodyWriter, write_vocal_melody
from parts import Ev
from song_character import choose
from song_plan import ChordSlot, Section, SongPlan, build_plan
from styles import STYLES, get_style
from theory import Chord


def plan_with_chords():
    section = Section("Chorus", 1, 0, 0, 2, 0, "major", 0.8, True,
                      [ChordSlot(0, 4, Chord(0, "maj")), ChordSlot(4, 4, Chord(6, "maj"))])
    return SongPlan(120, get_style("Ballade"), 0, "major", [section], {})


class MusicalCoherenceTests(unittest.TestCase):
    def test_score_hears_the_harmony_instead_of_only_intervals(self):
        plan = plan_with_chords()
        a = [MelNote(0, 1, 60, "ら"), MelNote(1, 1, 64, "ら"), MelNote(2, 1, 67, "ら")]
        b = [MelNote(n.start, n.dur, n.pitch + 1, n.syllable) for n in a]
        self.assertAlmostEqual(melody_score.score(a, "Chorus"), melody_score.score(b, "Chorus"))
        self.assertGreater(melody_score.score(a, "Chorus", plan=plan), melody_score.score(b, "Chorus", plan=plan))

    def test_held_note_is_checked_after_the_chord_changes(self):
        plan = plan_with_chords()
        note = MelNote(3, 2, 64, "あ", strong=True)
        before = musicality.harmony_scores([note], plan)["harmony"]
        fitted = musicality.fit_harmony(plan, [note])
        self.assertEqual(len(fitted), 2)
        self.assertEqual([(n.start, n.dur) for n in fitted], [(3, 1), (4, 1)])
        self.assertTrue(fitted[-1].syllable.melisma)
        self.assertEqual(fitted[-1].pitch % 12 in plan.chord_at(4).pcs, True)
        self.assertGreater(musicality.harmony_scores(fitted, plan)["harmony"], before)

    def test_short_diatonic_passage_and_intentional_color_survive(self):
        plan = plan_with_chords()
        passage = MelNote(1, 0.25, 71, "ら")
        color = MelNote(2, 1.5, 71, "あ", tension=True)
        self.assertEqual([n.pitch for n in musicality.fit_harmony(plan, [passage, color])], [71, 71])

    def test_words_and_lines_are_not_repeated_to_fill_a_section(self):
        words = [Mora(c, word_start=i == 0, line_start=i == 0) for i, c in enumerate("きみのこえ")]
        plan = plan_with_chords()
        writer = SectionMelodyWriter(plan, plan.sections[0], random.Random(1), extras=("musical_coherence",))
        _, chunks = writer.allocate(words)
        self.assertEqual([str(w) for chunk in chunks for w in chunk], list("きみのこえ"))
        self.assertEqual(copy.deepcopy(words)[0].line_start, True)

    def test_word_boundaries_are_preferred(self):
        words = [Mora(c, word_start=i % 3 == 0) for i, c in enumerate("きみのこえがとどく")]
        chunks = musicality.split_text(words, 3)
        self.assertTrue(all(chunk[0].word_start for chunk in chunks))
        self.assertEqual(sum(map(len, chunks)), len(words))

    def test_selected_candidates_are_not_changed_after_scoring(self):
        plan = build_plan(get_style("City Pop"), 110, ["Verse", "Chorus", "Chorus"], "A", "minor",
                          SECTION_CONFIG, random.Random(1), spice=0.5, spice_seed="1", own_chords=True)
        words = {k: list("きみのこえがきこえるよほしのひかりをおいかけて") for k in ("Verse", "Chorus")}
        captured = []
        original = melody_score.pick
        def pick(candidates, *args, **kwargs):
            result = original(candidates, *args, **kwargs)
            chosen = candidates[result[0]]
            captured.append((chosen, copy.deepcopy(chosen)))
            return result
        with patch.object(melody_score, "pick", pick):
            notes = write_vocal_melody(plan, words, random.Random(1), singable=True,
                                      extras={"best_melody": True, "musical_coherence": True, "melody_climax": True})
        self.assertTrue(captured)
        for chosen, before in captured:
            self.assertEqual([asdict(n) for n in chosen], [asdict(n) for n in before])
        self.assertTrue(all(a.start + a.dur <= b.start + 1e-6 for a, b in zip(notes, notes[1:])))

    def test_bass_uses_actual_kicks_and_stops_at_chord_changes(self):
        plan = plan_with_chords()
        section = plan.sections[0]
        drums = [Ev(0, 0.1, 36, 100), Ev(1.5, 0.1, 36, 95), Ev(5.75, 0.1, 36, 95)]
        notes = ensemble.bass_line("sync", section, plan, {"rhythm": ensemble.rhythm(section, drums)})
        self.assertTrue({0, 1.5, 4, 5.75}.issubset({n.start for n in notes}))
        self.assertTrue(all(n.start >= 4 or n.start + n.dur <= 4 for n in notes))

    def test_band_answers_instead_of_colliding_with_the_singer(self):
        plan = plan_with_chords()
        vocal = [MelNote(0, 2, 64, "あ")]
        events = {"piano": [Ev(0, 1, 60, 90)], "bells": [Ev(0, 1, 65, 80), Ev(3, 0.5, 67, 80)]}
        before = ensemble.score(events, vocal)
        result = ensemble.arrange(plan, events, vocal)
        self.assertGreater(result["removed"], 0)
        self.assertEqual([n.start for n in events["bells"]], [3])
        self.assertGreater(ensemble.score(events, vocal), before)

    def test_bass_microtiming_is_not_applied_twice(self):
        import groove_feel
        events = {"drums": [Ev(0.04, .1, 36, 100)], "bass": [Ev(0.04, .5, 36, 90)]}
        groove_feel.apply(events, already_following=("bass",))
        self.assertEqual(events["bass"][0].start, .04)

    def test_palettes_are_chosen_atomically_and_reproducibly(self):
        self.assertFalse(set(STYLES) - set(sound_palettes.PALETTES))
        for style in STYLES:
            character = choose(style, "42", coherent=True)
            palette = next(p for p in sound_palettes.PALETTES[style] if p["name"] == character.palette)
            self.assertEqual(character, choose(style, "42", coherent=True))
            self.assertEqual(character.voices, palette["voices"])
            self.assertTrue(all(character.programs[k] == v for k, v in palette["programs"].items()))

    def test_melody_preferences_survive_json_and_transposition(self):
        notes = [MelNote(i, 1, p, "ら") for i, p in enumerate([60, 62, 64, 67])]
        features = musicality.melody_features(notes)
        moved = [MelNote(n.start, n.dur, n.pitch + 3, n.syllable) for n in notes]
        self.assertEqual(features, musicality.melody_features(moved))
        entry = SimpleNamespace(thumbs={"melodie": 1}, character={"melody_features": {"Chorus": features}},
                                settings=SimpleNamespace(singer="", vocal_engine="Vorschau", style="Ballade"))
        taste = geschmack.learn([entry])
        loaded = geschmack.from_snapshot(json.loads(json.dumps([[list(k), v] for k, v in taste.scores.items()])))
        self.assertEqual(taste.scores, loaded.scores)
        self.assertGreater(musicality.preference(notes, "Chorus", loaded), 0)


if __name__ == "__main__":
    unittest.main()

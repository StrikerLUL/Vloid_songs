# test_stile_150.py – die drei neuen Stile aus 1.5.0: Wafuu-Rock (Taiko, Fünftonleiter), Electro-Swing (Walking Bass,
# Swing, Four-on-the-Floor) und Hyperpop (808, Wirbel-Hi-Hats, hohe Stimme)
import random

import config
import drums
import parts
import pipeline
import style_dna
from drums import GROOVES
from melody_writer import SectionMelodyWriter
from preset_manager import PRESETS
from rezepte import RECIPES
from settings import STYLE_OPTIONS, SongSettings
from song_plan import build_plan
from styles import get_style

NEW = ("Wafuu-Rock", "Electro-Swing", "Hyperpop")
STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Outro"]


def _plan(style: str, mode: str, seed: int = 5):
    return build_plan(get_style(style), 120, STRUCTURE, "D", mode, config.SECTION_CONFIG, random.Random(seed), {},
                      own_chords=True)


def test_the_new_styles_can_be_chosen_everywhere():
    for name in NEW:
        assert name in PRESETS and get_style(name).name == name
        assert any(r.values.get("style") == name for r in RECIPES), name
    assert "walking" in STYLE_OPTIONS["bass"] and "taiko" in STYLE_OPTIONS["perc"]


def test_electro_swing_walks_the_bass_in_quarters_towards_the_next_chord(tmp_path):
    s = SongSettings(output_ordner=str(tmp_path), seed=2, style="Electro-Swing", active_sections=["Verse", "Chorus"])
    tracks, _ = pipeline.compose(s)
    plan = tracks["plan"]
    beat = 60.0 / s.bpm
    notes = sorted(tracks["bass"], key=lambda n: n.start)
    on_beat = [n for n in notes if abs(n.start / beat - round(n.start / beat)) < 0.2]
    assert len(on_beat) > 0.9 * len(notes), "Viertel auf den Schlägen"
    approaches = changes = 0
    for sec in plan.sections:
        for a, b in zip(sec.chords, sec.chords[1:]):
            if b.chord.bass_pc == a.chord.bass_pc or a.dur < 2:
                continue
            last = min(notes, key=lambda n: abs(n.start - (b.start - 1) * beat))
            root = min(notes, key=lambda n: abs(n.start - b.start * beat))
            changes += 1
            approaches += abs(last.pitch - root.pitch) == 1
    assert changes and approaches > 0.8 * changes, "ein Halbton vor jedem neuen Grundton"
    assert get_style("Electro-Swing").swing >= 0.4
    floor = GROOVES[get_style("Electro-Swing").grooves["Chorus"]]
    assert [step for step, _ in floor[drums.KICK]] == [0, 4, 8, 12], "Four-on-the-Floor"


def test_wafuu_rock_plays_taiko_toms(tmp_path):
    s = SongSettings(output_ordner=str(tmp_path), seed=3, style="Wafuu-Rock", active_sections=["Chorus"])
    tracks, _ = pipeline.compose(s)
    toms = [n.pitch for n in tracks["perc"]]
    assert toms and set(toms) <= {parts.TAIKO_LOW, parts.TAIKO_HIGH}
    assert get_style("Wafuu-Rock").programs["counter"] == 106          # Shamisen
    assert get_style("Wafuu-Rock").programs["piano"] == 107            # Koto


def test_wafuu_rock_sings_in_the_japanese_pentatonic():
    def share(avoid: bool) -> float:
        hits = total = 0
        for seed in range(4):
            plan = _plan("Wafuu-Rock", "minor", seed)
            for sec in plan.sections:
                if sec.kind not in ("Verse", "Chorus"):
                    continue
                writer = SectionMelodyWriter(plan, sec, random.Random(seed), None, {"melody_character": True})
                if not avoid:
                    writer.avoid = ()
                for n in writer.write(["ら"] * 20):
                    total += 1
                    hits += (n.pitch - sec.tonic) % 12 in (2, 8)
        return hits / total

    assert style_dna.character("Wafuu-Rock").avoid["minor"] == (2, 8)
    assert share(True) < 0.6 * share(False), "zweite und sechste Stufe selten"


def test_the_other_styles_avoid_nothing():
    plan = _plan("Rock", "minor")
    sec = next(s for s in plan.sections if s.kind == "Verse")
    assert SectionMelodyWriter(plan, sec, random.Random(1), None, {"melody_character": True}).avoid == ()


def test_hyperpop_is_808_with_rolling_hats_and_a_high_voice(tmp_path):
    style = get_style("Hyperpop")
    assert style.drum_machine == "808" and style.vocal_center >= 70
    hats = [step for step, _ in GROOVES[style.grooves["Chorus"]][drums.HAT]]
    assert any(step % 1 for step in hats), "Hi-Hat-Wirbel zwischen den Sechzehnteln"
    s = SongSettings(output_ordner=str(tmp_path), seed=1, style="Hyperpop", active_sections=["Chorus"])
    tracks, _ = pipeline.compose(s)
    assert tracks["drums"] and tracks["bass"] and tracks["synth"]

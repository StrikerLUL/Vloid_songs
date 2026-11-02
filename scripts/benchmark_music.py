"""Vergleicht Kompositionsregeln mit denselben Stilen, Texten und Seeds, ohne Audio-Modelle.

python scripts/benchmark_music.py --seeds 5 --output /tmp/vloid-benchmark.json
Die Messwerte prüfen Konsistenz und Harmonie; sie ersetzen keinen Hörvergleich.
"""
import argparse
import copy
import json
import random
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vocaloid_generator"))

import melody_score
from config import SECTION_CONFIG
from melody_writer import write_vocal_melody
from musicality import harmony_scores
from song_plan import build_plan
from styles import get_style

STYLES = (("J-Pop Energy", 160), ("Ballade", 80), ("City Pop", 110), ("Rock", 140))
STRUCTURE = ["Verse", "PreChorus", "Chorus", "Verse", "Chorus", "Bridge", "Chorus"]
TEXT = {k: list("きみのこえがきこえるよほしのひかりをおいかけて") for k in STRUCTURE}
EXTRAS = ("best_melody", "melody_pickups", "melody_tensions", "melody_climax", "melody_triplets",
          "melody_character", "section_registers", "key_words", "catchy_chorus")


def measure(style, bpm, seed, coherent):
    plan = build_plan(get_style(style), bpm, STRUCTURE, "A", "minor", SECTION_CONFIG, random.Random(seed),
                      spice=0.5, spice_seed=str(seed), own_chords=True)
    captured = []
    original = melody_score.pick
    def pick(candidates, *args, **kwargs):
        result = original(candidates, *args, **kwargs)
        chosen = candidates[result[0]]
        captured.append((chosen, copy.deepcopy(chosen)))
        return result
    started = time.monotonic()
    with patch.object(melody_score, "pick", pick):
        notes = write_vocal_melody(plan, TEXT, random.Random(seed), singable=True,
                                  extras=EXTRAS + (("musical_coherence",) if coherent else ()))
    changed = sum(sum(asdict(a) != asdict(b) for a, b in zip(after, before)) + abs(len(after) - len(before))
                  for after, before in captured)
    ordered = sorted(notes, key=lambda n: n.start)
    return {"style": style, "seed": seed, "coherent": coherent, "notes": len(notes),
            "changed_after_selection": changed,
            "overlaps": sum(a.start + a.dur > b.start + 1e-6 for a, b in zip(ordered, ordered[1:])),
            **harmony_scores(notes, plan), "seconds": round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds muss mindestens 1 sein")
    rows = [measure(style, bpm, seed, coherent) for style, bpm in STYLES
            for seed in range(args.seeds) for coherent in (False, True)]
    report = {"seed_count": args.seeds, "rows": rows}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for coherent in (False, True):
        group = [r for r in rows if r["coherent"] == coherent]
        print("Gemeinsam" if coherent else "Bisherig", json.dumps({
            "runs": len(group), "changed_after_selection": sum(r["changed_after_selection"] for r in group),
            "overlaps": sum(r["overlaps"] for r in group),
            "mean_harmony": round(sum(r["harmony"] for r in group) / len(group), 4),
            "mean_resolution": round(sum(r["resolution"] for r in group) / len(group), 4)}))
    return int(any(r["changed_after_selection"] or r["overlaps"] for r in rows if r["coherent"]))


if __name__ == "__main__":
    raise SystemExit(main())

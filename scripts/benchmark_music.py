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
import platform
from importlib.metadata import version
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
from benchmark_audio import audio_metrics, compare_reports

STYLES = (("J-Pop Energy", 160), ("Ballade", 80), ("City Pop", 110), ("Rock", 140))
STRUCTURE = ["Verse", "PreChorus", "Chorus", "Verse", "Chorus", "Bridge", "Chorus"]
TEXT = {k: list("きみのこえがきこえるよほしのひかりをおいかけて") for k in STRUCTURE}
EXTRAS = ("best_melody", "melody_pickups", "melody_tensions", "melody_climax", "melody_triplets",
          "melody_character", "section_registers", "key_words", "catchy_chorus")


def measure(style, bpm, seed, coherent, audio_dir=None):
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
    elapsed = round(time.monotonic() - started, 3)
    audio = {}
    if audio_dir is not None:
        import pretty_midi
        import soundfile as sf
        from synth_engine import SAMPLE_RATE, render_notes
        voice = get_style(style).voices.get("melody", {}).get("", "lead")
        rendered = render_notes([pretty_midi.Note(100, n.pitch, n.start * 60 / bpm,
                                                 (n.start + n.dur) * 60 / bpm) for n in notes], voice)
        audio = audio_metrics(rendered, SAMPLE_RATE)
        audio_dir.mkdir(parents=True, exist_ok=True)
        sf.write(audio_dir / f"{style.replace(' ', '_')}-{seed}-{int(coherent)}.wav",
                 rendered.T, SAMPLE_RATE, subtype="FLOAT")
    return {"style": style, "seed": seed, "coherent": coherent, "notes": len(notes),
            "changed_after_selection": changed,
            "overlaps": sum(a.start + a.dur > b.start + 1e-6 for a, b in zip(ordered, ordered[1:])),
            **harmony_scores(notes, plan), "seconds": elapsed, **audio}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audio-dir", type=Path, help="Write deterministic synth melody previews (not full mixes)")
    parser.add_argument("--baseline", type=Path, help="Include per-case numeric deltas against a saved report")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds muss mindestens 1 sein")
    rows = [measure(style, bpm, seed, coherent, args.audio_dir) for style, bpm in STYLES
            for seed in range(args.seeds) for coherent in (False, True)]
    report = {"schema_version": 1, "suite": {"styles": STYLES, "structure": STRUCTURE,
              "text": TEXT, "extras": EXTRAS, "key": "A", "mode": "minor", "spice": 0.5,
              "audio": "synth-melody-float32-v2" if args.audio_dir else None},
              "environment": {"python": platform.python_version(), "platform": platform.platform(),
                              **{p: version(p) for p in ("numpy", "scipy", "pretty_midi")}},
              "seed_count": args.seeds, "rows": rows}
    # Normalize tuples to their JSON representation before comparing to a saved report.
    report = json.loads(json.dumps(report))
    if args.baseline:
        try:
            report["comparison"] = compare_reports(report, json.loads(args.baseline.read_text(encoding="utf-8")))
        except (ValueError, KeyError, OSError) as exc:
            parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
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

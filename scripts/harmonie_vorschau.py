"""Zwei Synth-Melodien mit und ohne Akkordwechsel-Vorausschau blind vergleichen."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import benchmark_music
import hoervergleich
import musicality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stil", choices=[style for style, _ in benchmark_music.STYLES])
    parser.add_argument("ausgabe", type=Path, help="Noch nicht vorhandener Ausgabeordner")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.seed < 0 or args.ausgabe.exists():
        parser.error("Seed muss nichtnegativ und der Ausgabeordner neu sein.")
    bpm = dict(benchmark_music.STYLES)[args.stil]
    before, after = args.ausgabe / "vorher", args.ausgabe / "nachher"
    with patch.object(musicality, "_crossing_cost", lambda pitch, pieces: 0.0):
        old = benchmark_music.measure(args.stil, bpm, args.seed, True, before)
    new = benchmark_music.measure(args.stil, bpm, args.seed, True, after)
    name = f"{args.stil.replace(' ', '_')}-{args.seed}-1.wav"
    hoervergleich.prepare(before / name, after / name, args.ausgabe / "duell")
    (args.ausgabe / "messwerte.json").write_text(
        json.dumps({"vorher": old, "nachher": new}, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8")
    print(f"Hörvergleich erstellt: {args.ausgabe / 'duell'}")


if __name__ == "__main__":
    main()

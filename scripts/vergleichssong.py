"""Einen reproduzierbaren Vergleichssong mit lokaler NEUTRINO-Stimme erzeugen."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vocaloid_generator"))
STYLES = {"J-Pop Energy": 160, "Ballade": 80, "City Pop": 110, "Rock": 140}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stil", choices=STYLES)
    parser.add_argument("ausgabe", type=Path, help="Noch nicht vorhandener Ausgabeordner")
    parser.add_argument("--stimme", default="MERROW")
    parser.add_argument("--ohne-bogen", action="store_true", help="Melodiebogen-Bewertung für einen A/B-Vergleich ausschalten")
    args = parser.parse_args()
    output = args.ausgabe.resolve()
    neutrino = ROOT / "NEUTRINO-windows-v3.1" / "NEUTRINO"
    if output.exists():
        parser.error("Der Ausgabeordner existiert bereits.")
    if not (neutrino / "model" / args.stimme).is_dir():
        parser.error("Die gewählte NEUTRINO-Stimme ist nicht installiert.")
    with tempfile.TemporaryDirectory(prefix="vloid-vergleich-") as scratch:
        # Keine App-Daten, Verlaufseinträge oder Nutzermotive verändern.
        os.environ["VLOID_DATEN"] = scratch
        import pipeline
        import vocal_check
        import melody_score
        from settings import SongSettings
        if args.ohne_bogen:
            melody_score.WEIGHTS["arc"] = 0.0
        output.mkdir(parents=True, exist_ok=False)
        settings = SongSettings(style=args.stil, bpm=STYLES[args.stil], seed=0, key="A", scale="minor",
                                active_sections=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
                                section_bars={"Intro": 4, "Verse": 4, "Chorus": 4, "Outro": 4},
                                vocal_engine="NEUTRINO", singer=args.stimme, neutrino_pfad=str(neutrino),
                                output_ordner=str(output), taste_learning=False, learned_motifs=False,
                                hearing_check=False, polish=False, ai_accompaniment=False, section_style=False,
                                vocal_takes=1, final_choir=False, vocal_versions=False, reuse_steps=False,
                                local_cache=False)
        (output / "vergleich-einstellungen.json").write_text(
            json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "vergleich-methode.json").write_text(
            json.dumps({"melodiebogen": not args.ohne_bogen, "datenordner": "isoliert"}, indent=2),
            encoding="utf-8")
        result = pipeline.generate_song(settings, seed=0, keep_history=False,
                                        progress=lambda fraction, msg: print(f"{fraction:.0%}: {msg}", flush=True))
        info = vocal_check.read(str(output)) or {}
        if info.get("engine") != "NEUTRINO":
            raise RuntimeError(f"NEUTRINO hat nicht gesungen: {info.get('engine', 'unbekannt')}")
        print(f"Fertig: {result.mix_wav}")


if __name__ == "__main__":
    main()

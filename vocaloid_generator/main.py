# main.py – Erzeugt einen kompletten Song ohne Oberfläche.
# Nutzt dieselben Einstellungen wie die App; einzelne Werte lassen sich per Option überschreiben.
import argparse
import logging
import sys

from pipeline import generate_song
from settings import KEYS, SongSettings

log = logging.getLogger("vocaloid")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Vocaloid Song Generator: erzeugt MIDI-Spuren, Gesang und eine fertige MP3.")
    p.add_argument("--settings", help="Einstellungsdatei (Standard: die Einstellungen der App)")
    p.add_argument("--seed", type=int, help="gleicher Seed = gleicher Song")
    p.add_argument("--bpm", type=int)
    p.add_argument("--style", help="Preset-Stil, z. B. 'J-Pop Energy', 'Rock', 'Kawaii Chiptune'")
    p.add_argument("--key", choices=KEYS)
    p.add_argument("--scale", choices=["minor", "major", "dorian", "phrygian"])
    p.add_argument("--output", help="Ausgabeordner")
    p.add_argument("-v", "--verbose", action="store_true", help="alle Details ausgeben")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    log.setLevel(logging.INFO)

    settings = SongSettings.load(args.settings)
    overrides = {
        "seed": args.seed, "bpm": args.bpm, "style": args.style,
        "key": args.key, "scale": args.scale, "output_ordner": args.output,
    }
    settings = settings.with_updates(**{k: v for k, v in overrides.items() if v is not None})

    log.info("=== Vocaloid Song Generator ===")
    log.info("Stil: %s | BPM: %d | Tonart: %s %s", settings.style, settings.bpm, settings.key, settings.scale)
    log.info("Struktur: %s", " → ".join(settings.active_sections))

    try:
        result = generate_song(settings, progress=lambda f, msg: log.info("[%3d%%] %s", round(f * 100), msg))
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    log.info("Fertig! Seed %d", result.seed)
    log.info("Song: %s", result.mp3 or result.mix_wav)
    return 0


if __name__ == "__main__":
    sys.exit(main())

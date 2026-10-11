# main.py – Erzeugt einen kompletten Song ohne Oberfläche.
# Nutzt dieselben Einstellungen wie die App; einzelne Werte lassen sich per Option überschreiben.
import argparse
import logging
import sys

import history
from pipeline import from_references, generate_song, generate_variants
from settings import KEYS, REROLLABLE, ReferenceTrack, SongSettings

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
    p.add_argument("--stimme", metavar="NAME", help="NEUTRINO-Stimme, z. B. MERROW")
    p.add_argument("--duett", metavar="NAME", help="zweite NEUTRINO-Stimme fürs Duett ('' = kein Duett)")
    p.add_argument("--engine", choices=["NEUTRINO", "VOICEVOX", "Vorschau"], help="wer singt")
    p.add_argument("--voicevox-stimme", type=int, metavar="ID", help="VOICEVOX-Singstimme (Stil-ID)")
    p.add_argument("--fassungen", type=int, choices=[1, 2, 3], help="NEUTRINO singt so oft, die sauberste zählt")
    p.add_argument("--vibrato", type=float, metavar="X", help="0 = gerade Töne, 1 = wie gesungen, 2 = doppelt")
    p.add_argument("--uebergaenge", type=float, metavar="X",
                   help="Übergänge zwischen Tönen: 0 = springen, 1 = wie gesungen, 2 = doppelt so lang")
    p.add_argument("--ohne-atmer", action="store_true", help="kein Einatmen vor den Phrasen")
    p.add_argument("--ohne-echo", action="store_true", help="kein Echo auf dem letzten Wort")
    p.add_argument("--ohne-chor", action="store_true", help="kein Chor im letzten Refrain")
    p.add_argument("--vorbild", action="append", metavar="DATEI",
                   help="Vorbild-Song (mehrfach möglich); ersetzt die Vorbilder aus den Einstellungen")
    p.add_argument("--vom-vorbild", action="store_true",
                   help="Tempo, Tonart und Stil der Vorbilder übernehmen (soweit in den Einstellungen erlaubt)")
    p.add_argument("--lautheit", type=float, metavar="LUFS", help="Ziel-Lautheit des Masters, z. B. -14 für YouTube")
    p.add_argument("--verlauf", action="store_true", help="die letzten Songs auflisten und beenden")
    p.add_argument("--aus-verlauf", type=int, metavar="NR",
                   help="Einstellungen und Seed eines Songs aus dem Verlauf nehmen (1 = der neueste)")
    p.add_argument("--neu", action="append", choices=REROLLABLE, metavar="TEIL",
                   help="nur diesen Teil neu würfeln, der Rest bleibt (mehrfach möglich): " + ", ".join(REROLLABLE)
                   + ". Ohne --seed und --aus-verlauf gilt der letzte Song.")
    p.add_argument("--varianten", type=int, default=1, metavar="N",
                   help="N Songs am Stück erzeugen; mit --neu N Fassungen der gewählten Teile")
    p.add_argument("--zip", metavar="DATEI", help="den Song mit allen Spuren als ZIP für eine DAW exportieren")
    p.add_argument("-v", "--verbose", action="store_true", help="alle Details ausgeben")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    log.setLevel(logging.INFO)

    settings = SongSettings.load(args.settings)
    overrides = {"output_ordner": args.output}
    settings = settings.with_updates(**{k: v for k, v in overrides.items() if v is not None})

    if args.verlauf:
        return _list_history(settings)
    if args.aus_verlauf or (args.neu and args.seed is None):
        settings = _from_history(settings, args.aus_verlauf or 1)
        if settings is None:
            return 1

    if args.vorbild:
        settings = settings.with_updates(reference_tracks=[ReferenceTrack(path=p).model_dump() for p in args.vorbild])
    if args.vom_vorbild:
        settings = from_references(settings)
    overrides = {"seed": args.seed, "bpm": args.bpm, "style": args.style, "key": args.key, "scale": args.scale,
                 "singer": args.stimme, "duet_singer": args.duett, "master_lufs": args.lautheit,
                 "vocal_engine": args.engine, "voicevox_singer": args.voicevox_stimme, "vocal_takes": args.fassungen,
                 "vibrato": args.vibrato, "glide": args.uebergaenge,
                 "breaths": False if args.ohne_atmer else None, "echo_throws": False if args.ohne_echo else None,
                 "final_choir": False if args.ohne_chor else None}
    settings = settings.with_updates(**{k: v for k, v in overrides.items() if v is not None})
    parts = tuple(args.neu or ())

    log.info("=== Vocaloid Song Generator ===")
    log.info("Stil: %s | BPM: %d | Tonart: %s %s", settings.style, settings.bpm, settings.key, settings.scale)
    log.info("Struktur: %s", " → ".join(settings.active_sections))

    def progress(f, msg):
        log.info("[%3d%%] %s", round(f * 100), msg)

    try:
        if args.varianten > 1 or parts:
            results = generate_variants(settings, args.varianten, parts, progress=progress)
        else:
            results = [generate_song(settings, progress=progress)]
    except (RuntimeError, ValueError) as e:
        log.error("%s", e)
        return 1

    for result in results:
        log.info("Fertig! Seed %d: %s", result.seed, result.history or result.audio)
    if args.zip:
        from exporter import exportiere_projekt
        log.info("ZIP: %s", exportiere_projekt(results[-1], args.zip))
    return 0


def _list_history(settings: SongSettings) -> int:
    found = history.entries(settings.output_dir())
    if not found:
        log.info("Der Verlauf ist leer.")
    for nr, entry in enumerate(found, 1):
        log.info("%2d. %s%s", nr, "★ " if entry.favorite else "", entry.title)
    return 0


def _from_history(settings: SongSettings, nr: int):
    found = history.entries(settings.output_dir())
    if not 1 <= nr <= len(found):
        log.error("Im Verlauf gibt es keinen Song Nr. %d (vorhanden: %d).", nr, len(found))
        return None
    entry = found[nr - 1]
    log.info("Aus dem Verlauf: %s", entry.title)
    return entry.restore(settings)


if __name__ == "__main__":
    sys.exit(main())

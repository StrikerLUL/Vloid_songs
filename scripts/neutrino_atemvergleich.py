"""Kurze NEUTRINO-Testphrase vor und nach der Atemzeichenkorrektur rendern."""
import argparse
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vocaloid_generator"))

import neutrino_score
from lyrics import Mora, syllables
from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, stimmlage


def old_bind(notes, breaths):
    """Vorherige Atemzeichenregel für einen nachvollziehbaren Vergleich."""
    out, sung = [], 0.0
    for note in notes:
        previous = out[-1] if out else None
        if note.pitch is None:
            if note.beats <= neutrino_score.LEGATO_BIS + 1e-9 and previous is not None and previous.pitch is not None:
                previous.beats += note.beats
                sung += note.beats
                if breaths and sung >= neutrino_score.BREATH_AFTER_BEATS:
                    previous.breath, sung = True, 0.0
                continue
            out.append(note)
            sung = 0.0
            continue
        out.append(note)
        sung += note.beats
        if breaths and sung >= neutrino_score.MAX_PHRASE_BEATS and note.beats >= neutrino_score.LONG_NOTE_BEATS:
            note.breath, sung = True, 0.0
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("neutrino", type=Path)
    parser.add_argument("ausgabe", type=Path, help="Bestehender leerer Ausgabeordner")
    parser.add_argument("--stimme", default="MERROW")
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--wortgrenze", action="store_true", help="Atemstelle innerhalb eines markierten Worts vergleichen")
    parser.add_argument("--echtes-wort", action="store_true", help="Wortgrenzen mit einer japanischen Testzeile vergleichen")
    args = parser.parse_args()
    if not args.ausgabe.is_dir() or any(args.ausgabe.iterdir()):
        parser.error("Bitte einen vorhandenen, leeren Ausgabeordner verwenden.")
    model = args.neutrino / "model" / args.stimme
    if not model.is_dir():
        parser.error("Stimmenmodell nicht gefunden.")
    if args.echtes_wort:
        # きみのこえがとどく ありがとう ね: die kurze Pause liegt zwischen あ und り.
        melody = [(64, 1.0)] * 10 + [(None, 0.25)] + [(65, 1.0)] * 4 + [(None, 0.25), (67, 1.0)]
        lyrics = syllables("きみのこえがとどく ありがとう ね", True, True)
        if len(lyrics) != 15:
            parser.error("Die Testzeile hat in dieser Umgebung nicht die erwarteten 15 Moren.")
    elif args.wortgrenze:
        melody = [(64, 1.0)] * 8 + [(None, 0.25), (65, 1.0), (None, 0.25), (67, 1.0)]
        lyrics = [Mora("ら", word_start=i == 0) for i in range(8)] + [Mora("あ"), Mora("ら", word_start=True)]
    else:
        melody = [(64, 1.0)] * 8 + [(None, 0.25), (65, 1.0), (67, 1.0)]
        lyrics = ["ら"] * 7 + ["か", Mora("あ", melisma=True), "ら"]
    shift = stimmlage(args.stimme)[2]
    for name, binding in (("vorher", old_bind), ("nachher", neutrino_score._bind_short_rests)):
        xml = args.ausgabe / f"{name}.xml"
        with patch.object(neutrino_score, "_bind_short_rests", binding):
            erstelle_musicxml(melody, lyrics, args.bpm, str(xml), shift, neutrino_score.ScoreOptions())
        neutrino_synthese(str(xml), str(args.ausgabe / f"{name}.wav"), str(args.neutrino), str(model))
    print(f"Vergleich fertig: {args.stimme}, {args.bpm} BPM, {args.ausgabe}")


if __name__ == "__main__":
    main()

"""Zwei vorhandene WAV-Fassungen lautheitsangepasst und blind zum Hören vorbereiten."""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf


def prepare(before: Path, after: Path, output: Path, seed: int | None = None):
    """Neue Dateien erstellen; das gemeinsame Pegellimit erhält den Lautheitsabgleich."""
    if output.exists():
        raise ValueError("Der Ausgabeordner existiert bereits; bitte einen neuen wählen.")
    recordings = []
    for path in (before, after):
        audio, rate = sf.read(path, dtype="float64", always_2d=True)
        if not audio.size or not np.isfinite(audio).all():
            raise ValueError(f"Leere oder ungültige Audiodatei: {path}")
        try:
            loudness = float(pyloudnorm.Meter(rate).integrated_loudness(audio))
        except ValueError as exc:
            raise ValueError(f"Datei für die Lautheitsmessung ungeeignet: {path}") from exc
        if not math.isfinite(loudness):
            raise ValueError(f"Keine messbare Lautheit: {path}")
        recordings.append((audio, rate, loudness))
    if recordings[0][1] != recordings[1][1] or recordings[0][0].shape != recordings[1][0].shape:
        raise ValueError("Beide Dateien müssen gleiche Samplerate, Kanäle und Länge haben.")
    target = min(item[2] for item in recordings)
    normalized = [audio * 10 ** ((target - level) / 20) for audio, _, level in recordings]
    peak = max(float(np.max(np.abs(audio))) for audio in normalized)
    if peak > 0.98:
        normalized = [audio * (0.98 / peak) for audio in normalized]
        target += 20 * math.log10(0.98 / peak)
    order = [0, 1]
    (random.Random(seed) if seed is not None else random.SystemRandom()).shuffle(order)
    output.mkdir(parents=True, exist_ok=False)
    for name, index in zip(("A", "B"), order):
        sf.write(output / f"{name}.wav", normalized[index], recordings[index][1], subtype="FLOAT")
    source = (before, after)
    key = {name: {"fassung": ("vorher", "nachher")[index], "datei": str(source[index].resolve()),
                  "sha256": hashlib.sha256(source[index].read_bytes()).hexdigest()}
           for name, index in zip(("A", "B"), order)}
    (output / "aufloesung.json").write_text(json.dumps({"zuordnung": key, "ziel_lufs": target},
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "hoerprotokoll.md").write_text(
        "# Hörprotokoll\n\nErst A und B hören, danach aufloesung.json öffnen.\n\n"
        "Stil / Seed / Text: \n\nStimme / Engine / Instrumente / Einstellungen: \n\n"
        "Änderung zwischen den Fassungen: \n\nAbhörgerät / Datum: \n\n"
        "| Bereich | A, B oder gleich? | Beobachtung / Stelle |\n| --- | --- | --- |\n"
        + "".join(f"| {category} | | |\n" for category in
                  ("Gesang", "Melodie", "Harmonie", "Arrangement", "Mix", "Gesamteindruck"))
        + "\nNach Auflösung: Welche Fassung bevorzugst du und warum? \n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vorher", type=Path)
    parser.add_argument("nachher", type=Path)
    parser.add_argument("ausgabe", type=Path, help="Noch nicht existierender Ausgabeordner")
    parser.add_argument("--seed", type=int, help="Optionale reproduzierbare Zuordnung A/B")
    args = parser.parse_args()
    try:
        level = prepare(args.vorher, args.nachher, args.ausgabe, args.seed)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Hörvergleich erstellt: {args.ausgabe} (gemeinsames Ziel {level:.1f} LUFS)")
    print("A.wav und B.wav hören; erst danach aufloesung.json öffnen.")


if __name__ == "__main__":
    main()

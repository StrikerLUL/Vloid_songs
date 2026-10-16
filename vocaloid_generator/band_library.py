# band_library.py – Flügel, E-Bass und E-Gitarre aus echten Aufnahmen (v6 Nr. 3)
#
# setup_band.py lädt drei frei nutzbare Instrumente nach tools/samples/Band: den Salamander-Flügel (Yamaha C5, von
# Alexander Holm, CC BY 3.0), den Growlybass und die Emily-Gitarre (beide von Karoryfer, CC0; die Gitarre direkt ins
# Pult gespielt). Flügel, E-Bass und saubere E-Gitarre spielen dann aus ihnen statt aus dem SoundFont, Slides im Bass
# inklusive. Verzerrte Gitarren schicken die Emily-Gitarre in den Verstärker (guitar_amp). Fehlt ein Instrument,
# spielt es weiter aus dem SoundFont. Gespielt wird mit dem Sampler aus sfz.py, wie die Orchester-Aufnahmen.
import logging
import os
from typing import Optional

import numpy as np
import pretty_midi

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "samples", "Band")
PIANO, BASS, GUITAR = "Klavier.sfz", "Bass.sfz", "Gitarre.sfz"
NAMES = {PIANO: "Flügel (Salamander)", BASS: "E-Bass (Growlybass)", GUITAR: "E-Gitarre (Emily)"}
# General-MIDI-Programm → Instrument: Flügel, heller Flügel; Finger- und Plektrum-Bass; Jazz- und saubere E-Gitarre
PROGRAMS = {0: PIANO, 1: PIANO, 33: BASS, 34: BASS, 26: GUITAR, 27: GUITAR}
BEND_RANGE = 2.0        # Halbtöne bei vollem Pitch-Bend (General MIDI, wie orchestrator._slides rechnet)
# so laut wie dasselbe Instrument aus dem mitgelieferten SoundFont bei gleichem Anschlag (mit tinysoundfont gemessen);
# zählt, wo Aufnahmen und SoundFont in einer Spur zusammen spielen (der Mixer bringt jede Spur auf ihren Pegel)
LEVEL_DB = {PIANO: 7.0, BASS: 17.0, GUITAR: 8.0}


def path(name: str) -> str:
    return os.path.join(FOLDER, name)


def files() -> list:
    return [PIANO, BASS, GUITAR]


def installed() -> list:
    """Die vorhandenen Instrumente (setup_band.py schreibt jede SFZ-Datei erst, wenn alle Aufnahmen da sind)."""
    return [f for f in files() if os.path.isfile(path(f))]


def covers(inst: pretty_midi.Instrument) -> bool:
    """Spielt dieses Instrument aus den Aufnahmen?"""
    name = PROGRAMS.get(inst.program)
    return not inst.is_drum and bool(inst.notes) and name is not None and os.path.isfile(path(name))


def render(inst: pretty_midi.Instrument, sample_rate: int = 44100) -> Optional[np.ndarray]:
    """Die Töne von inst aus den Aufnahmen, Rückgabe (2, Samples); None, wenn der Sampler nicht spielen kann."""
    import sample_library
    import sfz
    name = PROGRAMS[inst.program]
    try:
        instrument = sfz.load(path(name))
    except (OSError, ValueError) as e:
        log.warning("%s lässt sich nicht laden (%s), %s spielt aus dem SoundFont", name, e, inst.name or "Spur")
        return None
    bends = [(b.time, b.pitch / 8192 * BEND_RANGE) for b in inst.pitch_bends]
    notes = [sample_library._into_range(n, instrument) for n in inst.notes]
    audio = sfz.render(instrument, notes, sample_rate, inst.program, bends=bends or None)
    level = sample_library._level(path(name), os.path.getmtime(path(name))) * 10 ** (LEVEL_DB[name] / 20)
    audio *= np.float32(level)
    pan = next((cc.value for cc in inst.control_changes if cc.number == 10), None)
    if pan is not None:
        audio = sfz.balance(audio, (pan - 64) / 63)
    return audio


def status() -> str:
    """Eine Zeile für die Oberfläche: welche Band-Instrumente aus Aufnahmen spielen."""
    have = installed()
    if not have:
        return "Flügel, Bass und Gitarre aus Aufnahmen fehlen: einmal uv run setup_band.py ausführen"
    return "Aus Aufnahmen: " + ", ".join(NAMES[f] for f in have)

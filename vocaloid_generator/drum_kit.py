# drum_kit.py – ein echtes Schlagzeug aus Aufnahmen (DRS Kit von DrumGizmo, CC BY 4.0)
#
# setup_drums.py lädt die Aufnahmen nach tools/drums/DRSKit und mischt jeden Schlag aus seinen Mikrofonen
# (Nahmikrofone, Overheads, Raum) zu Stereo. Akustische Schlagzeug-Spuren spielen dann daraus statt aus dem SoundFont:
# jede Trommel mit mehreren Anschlag-Schichten und wechselnden Aufnahmen, so klingt kein Schlag wie der vorige.
# Trommeln und Becken klingen aus, bis derselbe Klang zum übernächsten Mal kommt; ein offenes Hi-Hat verstummt, sobald
# das Hi-Hat wieder zugeht. Was das Kit nicht hat (Clap, Tamburin, Cowbell), spielt weiter der SoundFont.
import os
from dataclasses import dataclass

import numpy as np
import pretty_midi

import config

FOLDER = os.path.join(config.REPO_ROOT, "tools", "drums", "DRSKit")
SFZ_NAME = "DRSKit.sfz"
SAMPLE_RATE = 44100
ACOUSTIC_KITS = (0, 8, 16, 32)  # General-MIDI-Kits Standard, Room, Power, Jazz; elektronische bleiben beim SoundFont
RING_HITS = 2                   # ein Klang klingt, bis er zum übernächsten Mal kommt (zwei Stimmen pro Trommel)
LONGEST = 8.0                   # länger klingt kein Schlag (die Aufnahmen enden meist vorher)
GAIN = 0.5                      # so laut wie das Kit des SoundFonts bei gleichem Anschlag


@dataclass(frozen=True)
class Piece:
    name: str                   # Name im DRS Kit (Ordner der Aufnahmen)
    key: int                    # Ton in der SFZ-Datei
    close: tuple = ()           # Nahmikrofone: (Name, Panorama -1 links … 1 rechts, Pegel); Becken haben keine
    gain: float = 0.0           # dB lauter als im Raum gehört (Rim und Hi-Hat sitzen im Pop weiter vorn)


# Overheads und Raum hört man bei jedem Schlag
ROOM = (("OHL", -1.0), ("OHR", 1.0), ("AmbL", -1.0), ("AmbR", 1.0))
HAT_MIC = (("Hihat", -0.4, 0.5),)
RIDE_MIC = (("Ride", 0.4, 0.5),)
PIECES = (
    Piece("Kdrum_with_contact", 36, (("Kdrum_front", 0.0, 1.0), ("Kdrum_back", 0.0, 1.0))),
    Piece("Snare", 38, (("Snare_top", 0.0, 1.0), ("Snare_bottom", 0.0, 1.0))),
    Piece("Snare_rim", 37, (("Snare_top", 0.0, 1.0),), gain=8.0),
    Piece("Tom1", 48, (("Tom1", -0.2, 1.0),)),
    Piece("Tom2", 45, (("Tom2", 0.2, 1.0),)),
    Piece("Tom3", 41, (("Tom3", 0.6, 1.0),)),
    Piece("Hihat_closed", 42, HAT_MIC, gain=4.0),
    Piece("Hihat_foot", 44, HAT_MIC, gain=4.0),
    Piece("Hihat_open", 46, HAT_MIC, gain=4.0),
    Piece("Ride_tip", 51, RIDE_MIC),
    Piece("Ride_shank_bell", 53, RIDE_MIC),
    Piece("Crash_left_shank", 49, gain=3.0),
    Piece("Crash_right_shank", 57, gain=3.0),
)
# General MIDI → Ton im Kit; drei Toms für sechs, Splash und China auf die Crashes
GM = {35: 36, 36: 36, 37: 37, 38: 38, 40: 38, 50: 48, 48: 48, 47: 45, 45: 45, 43: 41, 41: 41,
      42: 42, 44: 44, 46: 46, 51: 51, 59: 51, 53: 53, 49: 49, 55: 49, 52: 57, 57: 57}
HATS = (42, 44, 46)
OPEN_HAT = 46


def path() -> str:
    return os.path.join(FOLDER, SFZ_NAME)


def installed() -> bool:
    """setup_drums.py schreibt die SFZ-Datei erst, wenn die Aufnahmen gemischt sind."""
    return os.path.isfile(path())


def complete() -> bool:
    """Alle Trommeln und Becken da (für Einrichten und Systemcheck)."""
    return installed() and {p.key for p in PIECES} <= keys()


def keys() -> set:
    """Die Töne, die das Kit spielen kann."""
    if not installed():
        return set()
    import sfz
    try:
        return {r.lokey for r in sfz.load(path()).regions}
    except (OSError, ValueError):
        return set()


def covers(inst: pretty_midi.Instrument) -> bool:
    return inst.is_drum and inst.program in ACOUSTIC_KITS and bool(inst.notes)


def render(midi: pretty_midi.PrettyMIDI, sample_rate: int = SAMPLE_RATE) -> tuple:
    """
    Spielt die akustischen Schlagzeug-Spuren mit dem Kit. Rückgabe: (Stereo-Audio (2, Samples) oder None, die
    Spuren mit allem, was das Kit nicht spielt); die übrigen spielt danach der SoundFont.
    """
    import sfz
    playable = keys()
    if not playable:
        return None, list(midi.instruments)
    instrument = sfz.load(path())
    pieces, rest = [], []
    for inst in midi.instruments:
        if not covers(inst):
            rest.append(inst)
            continue
        mine = [n for n in inst.notes if GM.get(n.pitch) in playable]
        other = [n for n in inst.notes if GM.get(n.pitch) not in playable]
        if mine:
            audio = sfz.render(instrument, shaped(mine), sample_rate, retrigger=False)
            pan = next((cc.value for cc in inst.control_changes if cc.number == 10), 64)
            pieces.append(sfz.balance(audio, (pan - 64) / 63) if pan != 64 else audio)
        if other:
            leftover = pretty_midi.Instrument(program=inst.program, is_drum=True, name=inst.name)
            leftover.notes, leftover.control_changes = other, list(inst.control_changes)
            rest.append(leftover)
    if not pieces:
        return None, rest
    out = np.zeros((2, max(p.shape[1] for p in pieces)), dtype=np.float32)
    for p in pieces:
        out[:, :p.shape[1]] += p
    return out * np.float32(GAIN), rest


def shaped(notes: list) -> list:
    """
    Die Töne auf den Tönen des Kits, jeder so lang, wie er klingen darf: bis derselbe Klang zum übernächsten Mal
    kommt, ein offenes Hi-Hat nur bis zum nächsten Hi-Hat-Schlag.
    """
    moved = [pretty_midi.Note(n.velocity, GM[n.pitch], n.start, n.start) for n in notes]
    moved.sort(key=lambda n: (n.start, n.pitch))
    starts = {}
    for n in moved:
        starts.setdefault(n.pitch, []).append(n.start)
    hats = sorted(n.start for n in moved if n.pitch in HATS)
    seen = {}
    for n in moved:
        k = seen.get(n.pitch, 0)
        seen[n.pitch] = k + 1
        own = starts[n.pitch]
        end = own[k + RING_HITS] if k + RING_HITS < len(own) else n.start + LONGEST
        if n.pitch == OPEN_HAT:
            end = min(end, next((t for t in hats if t > n.start + 1e-4), end))
        n.end = min(end, n.start + LONGEST)
    return moved


def status() -> str:
    """Eine Zeile für die Oberfläche: ob das echte Schlagzeug da ist."""
    if not installed():
        return "Echtes Schlagzeug fehlt: unter Hilfe › Einrichten laden (etwa 130 MB)"
    have = len({p.key for p in PIECES} & keys())
    return f"Echtes Schlagzeug (DRS Kit): {have} von {len(PIECES)} Trommeln und Becken da"

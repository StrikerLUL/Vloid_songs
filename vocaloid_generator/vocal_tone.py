# vocal_tone.py – Kette pro Stimme und Stil (Gesang 1.1, D5)
#
# Bis 1.0 bekam jeder Gesang dieselbe Kette: Hochpass, −2 dB bei 250 Hz, +3 dB bei 3,5 kHz, Glanz ab 10 kHz, zwei
# Kompressoren, leichte Sättigung. Helle Stimmen werden davon spitz, tiefe bleiben dumpf, und eine Ballade bekommt
# dieselbe Sättigung wie ein Rocksong. Hier steht, was sich je Stimmlage und Stil ändert; der Rest der Kette bleibt.
from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class Tone:
    highpass: float = 100.0         # Hz
    mud_hz: float = 250.0           # Mitten, die dumpf machen
    mud_db: float = -2.0
    presence_hz: float = 3500.0     # Verständlichkeit
    presence_db: float = 3.0
    air_db: float = 2.5             # Glanz ab 10 kHz
    ratio: float = 6.0              # erster, schneller Kompressor
    drive_db: float = 6.0           # Sättigung (nur mit der Studio-Kette)
    drive_mix: float = 0.3

    def describe(self) -> str:
        return (f"Hochpass {self.highpass:.0f} Hz, {self.mud_db:+.1f} dB bei {self.mud_hz:.0f} Hz, "
                f"{self.presence_db:+.1f} dB bei {self.presence_hz / 1000:g} kHz, Glanz {self.air_db:+.1f} dB, "
                f"Kompressor {self.ratio:g}:1, Sättigung {self.drive_mix:.0%}")


STANDARD = Tone()                    # die Kette bis 1.0

# Stimmlage nach dem höchsten Ton, den die Stimme singt (vocal_synthesizer.STIMMEN)
VOICES = {
    "hell": Tone(highpass=120.0, mud_db=-1.5, presence_db=2.0, air_db=1.5),        # MERROW, KIRITAN, ITAKO …
    "mittel": STANDARD,                                                            # REINA, SEVEN, SOMA
    "tief": Tone(highpass=70.0, mud_hz=300.0, mud_db=-3.0, presence_hz=3000.0, presence_db=3.5, air_db=3.0),
}
BRIGHT_FROM, DEEP_UNTIL = 74, 71     # höchster gesungener Ton (MIDI): ab hier hell, bis hier tief

# Was der Stil dazu ändert: Werte, die zur Stimmlage addiert werden; ratio, drive_db und drive_mix ersetzen
STYLES = {
    "Ballade": {"presence_db": -1.0, "air_db": -0.5, "ratio": 4.0, "drive_db": 4.0, "drive_mix": 0.15},
    "Rock": {"presence_db": 0.5, "drive_db": 9.0, "drive_mix": 0.45},
    "Dark Vocaloid": {"mud_db": -0.5, "drive_db": 8.0, "drive_mix": 0.4},
    "Lo-Fi": {"air_db": -1.5, "drive_mix": 0.35},
    "City Pop": {"mud_db": 0.5, "presence_db": -0.5, "ratio": 4.0},
    "Future Bass": {"air_db": 1.0},
    "Kawaii Chiptune": {"air_db": 1.0},
    "Drum and Bass": {"presence_db": 0.5},
}
ADDED = ("mud_db", "presence_db", "air_db")


def voice_kind(singer: Optional[str]) -> str:
    """hell, mittel oder tief; ohne bekannte NEUTRINO-Stimme mittel."""
    from vocal_synthesizer import STIMMEN
    found = STIMMEN.get((singer or "").upper())
    if found is None:
        return "mittel"
    top = found[1]
    return "hell" if top >= BRIGHT_FROM else "tief" if top <= DEEP_UNTIL else "mittel"


def for_song(singer: Optional[str], style: str) -> Tone:
    """Die Kette für diese Stimme (None: unbekannt, z. B. VOICEVOX) in diesem Stil."""
    tone = VOICES[voice_kind(singer)]
    changes = {}
    for name, value in STYLES.get(style, {}).items():
        changes[name] = getattr(tone, name) + value if name in ADDED else value
    return replace(tone, **changes)

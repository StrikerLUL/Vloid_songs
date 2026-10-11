# sound_library.py – Bessere Klänge für einzelne Instrumente aus zusätzlichen SoundFonts
#
# setup_soundfonts.py lädt sie nach tools/soundfonts. Jedes General-MIDI-Programm, für das hier ein Klang
# steht, spielt dann aus dieser Datei statt aus dem Haupt-SoundFont (GeneralUser GS). Fehlt eine Datei,
# bleibt alles wie bisher. SF3-Dateien (mit Ogg Vorbis gepackt) spielt nur FluidSynth richtig.
import os
from dataclasses import dataclass, field
from typing import Optional

import config

FOLDER = os.path.join(config.REPO_ROOT, "tools", "soundfonts")

MS_BASIC = "MS Basic.sf3"                                         # MuseScore 4, MIT
FM_PIANO = "FM-Piano1 20190916.sf2"                               # FreePats, CC0
CLEAN_GUITAR = "EGuitarFSBS-clean bridge small 20260807.sf2"      # FreePats, CC0
DIST_GUITAR = "EGuitarFSBS-dist2 bridge 20220911.sf2"             # FreePats, CC0
ROCK_KIT = "Red_Zeppelin_4_LV2.sf2"                               # AVL Drumkits, CC-BY-SA 3.0
POP_KIT = "Black_Pearl_4_LV2.sf2"                                 # AVL Drumkits, CC-BY-SA 3.0

# Die AVL-Kits haben nur zwei Toms; auf 43, 47, 48 und 50 liegen andere Klänge (Rand, Hi-Hat-Wisch, Abstoppen)
AVL_NOTES = {50: 45, 48: 45, 47: 45, 43: 41}


@dataclass(frozen=True)
class Sound:
    file: str
    preset: int = 0
    bank: int = 0
    low: int = 0                   # tiefster und höchster gesampelter Ton; Töne außerhalb wandern um Oktaven
    high: int = 127
    notes: dict = field(default_factory=dict)   # Schlagzeug: General-MIDI-Note → Note im Kit
    own_pan: bool = False          # der SoundFont schwächt MIDI-Panorama ab: der Renderer verteilt selbst

    @property
    def path(self) -> str:
        return os.path.join(FOLDER, self.file)

    def pitch(self, pitch: int) -> int:
        pitch = self.notes.get(pitch, pitch)
        while pitch < self.low and pitch + 12 <= 127:
            pitch += 12
        while pitch > self.high and pitch - 12 >= 0:
            pitch -= 12
        return pitch


def _ms(preset: int) -> Sound:
    return Sound(MS_BASIC, preset)


# General-MIDI-Programm → Klang
PROGRAMS = {
    0: _ms(0), 1: _ms(1),                                           # Flügel
    4: _ms(4),                                                      # Tine-E-Piano (Rhodes)
    5: Sound(FM_PIANO, 0, low=27, high=98),                         # FM-E-Piano (DX7), der City-Pop-Klang
    27: Sound(CLEAN_GUITAR, low=35, high=86),                       # cleane E-Gitarre
    29: Sound(DIST_GUITAR, low=35, high=86, own_pan=True),          # verzerrte E-Gitarren
    30: Sound(DIST_GUITAR, low=35, high=86, own_pan=True),
    40: _ms(40), 41: _ms(41), 42: _ms(42), 43: _ms(43),             # Geige, Bratsche, Cello, Kontrabass
    44: _ms(44), 45: _ms(45), 46: _ms(46), 47: _ms(47),             # Tremolo, Pizzicato, Harfe, Pauken
    48: _ms(48), 49: _ms(49),                                       # Streicher
    56: _ms(56), 57: _ms(57), 60: _ms(60), 61: _ms(61),             # Trompete, Posaune, Hörner, Bläsersatz
    68: _ms(68), 71: _ms(71), 73: _ms(73),                          # Oboe, Klarinette, Flöte
}
# Drum-Kit (Preset in Bank 128 des Haupt-SoundFonts) → Klang; elektronische Kits bleiben
KITS = {
    0: Sound(POP_KIT, notes=AVL_NOTES),       # Standard
    8: Sound(POP_KIT, notes=AVL_NOTES),       # Room
    16: Sound(ROCK_KIT, notes=AVL_NOTES),     # Power
}


def find(program: int, is_drum: bool = False, sf3: bool = True) -> Optional[Sound]:
    """Der bessere Klang für ein Programm, wenn seine Datei da ist (sf3=False: nur SF2-Dateien)."""
    sound = (KITS if is_drum else PROGRAMS).get(program)
    if sound is None or (not sf3 and sound.file.lower().endswith(".sf3")):
        return None
    return sound if os.path.isfile(sound.path) else None


def installed() -> list:
    """Dateinamen der vorhandenen zusätzlichen SoundFonts."""
    files = {s.file for s in list(PROGRAMS.values()) + list(KITS.values())}
    return sorted(f for f in files if os.path.isfile(os.path.join(FOLDER, f)))


def status() -> str:
    """Eine Zeile für die Oberfläche: welche zusätzlichen SoundFonts da sind."""
    have = installed()
    total = len({s.file for s in list(PROGRAMS.values()) + list(KITS.values())})
    if not have:
        return "Zusätzliche SoundFonts fehlen: einmal uv run setup_soundfonts.py ausführen"
    return f"Zusätzliche SoundFonts: {len(have)} von {total} da"

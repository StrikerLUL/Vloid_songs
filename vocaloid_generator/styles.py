# styles.py – Klangprofile der Stile: Instrumente, Spielweisen pro Sektion, Akkordfolgen, Mix
from dataclasses import dataclass, field

# ── Akkordfolgen ─────────────────────────────────────────────────────────────────
# Takte durch "|" getrennt, zwei Akkorde in einem Takt teilen sich den Takt.
# Dur-Folgen beziehen sich auf I = Grundton, Moll-Folgen auf i = Grundton.
PROGRESSIONS = {
    "major": {
        "Verse": [
            "I | V/3 | vi | iii | IV | I/3 | ii | V",       # Kanon
            "I | vi | IV | V",
            "vi | IV | V | I",
            "I | iii | IV | V",
            "I | V | vi | IV",
            "IV | V | iii | vi",
        ],
        "PreChorus": [
            "IV | V | iii | vi",
            "ii | iii | IV | V",
            "vi | iii | IV | V",
            "IV | iii | ii | V",
        ],
        "Chorus": [
            "IVmaj7 | V7 | iii7 | vi",                        # Royal Road, die J-Pop-Akkordfolge
            "IV | V | iii | vi | ii | V | I | I",
            "I | V | vi | IV",
            "vi | IV | V | I",
            "I | V/3 | vi | I/5 | IV | I/3 | ii | V",
        ],
        "Bridge": [
            "vi | IV | I | V",
            "ii | iii | IV | V",
            "IV | iv | I | vi",
            "vi | V | IV | V",
        ],
    },
    "minor": {
        "Verse": [
            "i | bVI | bVII | i",
            "i | bVII | bVI | bVII",
            "i | iv | bVII | bIII",
            "i | bVI | bIII | bVII",
            "i | i | bVI | bVII",
        ],
        "PreChorus": [
            "iv | v | bVI | bVII",
            "bVI | bVII | bVI | bVII",
            "bVI | bVII | bIII | bVI",
            "iv | bVII | bIII | bVI",
        ],
        "Chorus": [
            "bVImaj7 | bVII | v7 | i",                       # Royal Road in Moll
            "i | bVI | bIII | bVII",
            "bVI | bVII | i | i",
            "bVI | bVII | v | i | bVI | bVII | V | i",
            "i | bVII | bVI | V",
        ],
        "Bridge": [
            "bVI | bVII | bIII | bVI",
            "iv | i | bVII | bIII",
            "bVI | bIII | bVII | i",
        ],
    },
}
# Stile mit eigener Harmonik ersetzen einzelne Listen
STYLE_PROGRESSIONS = {
    "City Pop": {
        "major": {
            "Verse": ["IVmaj7 | iii7 | ii7 | Imaj7", "Imaj7 | vi7 | ii7 | V7"],
            "PreChorus": ["ii7 | iii7 | IVmaj7 | V7sus4"],
            "Chorus": ["IVmaj7 | III7 | vi7 | v7 I7", "IVmaj7 | V7 | iii7 | vi7"],
            "Bridge": ["ii7 | V7 | Imaj7 | vi7"],
        },
        "minor": {
            "Verse": ["i7 | iv7 | bVII7 | bIIImaj7"],
            "Chorus": ["bVImaj7 | bVII7 | v7 | i7", "iv7 | bVII7 | bIIImaj7 | bVImaj7"],
        },
    },
}

# Abschluss-Takte: Vor dem Refrain steht die Dominante, der Refrain endet auf der Tonika
CADENCES = {
    "major": {"to_chorus": "V", "end": ("IV V", "I")},
    "minor": {"to_chorus": "V", "end": ("bVI bVII", "i")},
}

# ── Energie pro Sektion (0 = still, 1 = volle Band) ──────────────────────────────
SECTION_ENERGY = {
    "Intro": 0.75, "Build-up": 0.6, "Verse": 0.45, "PreChorus": 0.65,
    "Chorus": 0.9, "Bridge": 0.4, "Drop": 0.7, "Outro": 0.6,
}

INSTRUMENT_PARTS = ("piano", "bass", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "perc", "melody")

# Klänge für neue Instrumente, falls ein Stil keine eigenen nennt (General MIDI)
DEFAULT_PROGRAMS = {"bells": 9, "choir": 52, "counter": 73, "perc": 0}


@dataclass(frozen=True)
class StyleProfile:
    name: str
    programs: dict                 # Instrument → General-MIDI-Programm des SoundFonts
    drum_kit: int                  # Preset in Bank 128
    parts: dict                    # Sektion → {Instrument: Spielweise}; fehlt ein Instrument, schweigt es
    grooves: dict                  # Sektion → Drum-Groove
    mix: dict                      # Instrument → Ziel-Lautheit in LUFS (vor dem Mastering)
    reverb: dict                   # Instrument → Hall-Anteil
    chord_color: str = "triad"     # triad | seventh
    key_changes: tuple = (0, 1, 1, 2)   # Auswahl: um wie viele Halbtöne der letzte Refrain steigt
    breakdown_chance: float = 0.4       # letzter Refrain beginnt leise, nur mit parts["breakdown"]
    bridge_breakdown_chance: float = 0.3
    halftime_chance: float = 0.3        # zweite Strophe beginnt im Halftime
    melisma: float = 1.0                # wie oft Phrasen mit einem Melisma enden (1 = normal)
    vocal_center: int = 67         # mittlere Gesangslage (MIDI)
    double_time_melody: bool = False
    swing: float = 0.0
    halftime_below_bpm: int = 0    # unter diesem Tempo: Sechzehntel-Gefühl statt Achtel
    voices: dict = field(default_factory=dict)   # Instrument → {Unterspur: eigene Synth-Stimme}
    fx: str = "full"               # Übergänge: full (Riser, Impact), soft (nur Becken-Swell), none

    def part(self, section: str, instrument: str, occurrence: int = 1, last: bool = False, feel: str = ""):
        """
        Spielweise in einer Sektion. "Verse:2" ergänzt ab dem zweiten Vorkommen, "Chorus:last" im
        letzten Vorkommen; None nimmt ein Instrument dort heraus. Im Breakdown spielt nur "breakdown".
        """
        if feel == "breakdown":
            return self.parts.get("breakdown", {}).get(instrument)
        parts = dict(self.parts.get(section, self.parts.get("Verse", {})))
        if occurrence >= 2:
            parts.update(self.parts.get(f"{section}:2", {}))
        if last:
            parts.update(self.parts.get(f"{section}:last", {}))
        return parts.get(instrument)

    def program(self, instrument: str) -> int:
        return self.programs.get(instrument, DEFAULT_PROGRAMS.get(instrument, 0))

    def groove(self, section: str) -> str:
        return self.grooves.get(section, self.grooves.get("Verse", "verse"))


_MIX_POP = {"drums": -17.0, "bass": -19.5, "piano": -22.0, "guitar": -23.0, "strings": -24.5,
            "synth": -24.0, "brass": -24.0, "melody": -21.0, "vocals": -17.0,
            "bells": -28.0, "choir": -27.0, "counter": -24.5, "perc": -28.5, "fx": -27.0}
_REVERB_POP = {"drums": 0.06, "bass": 0.0, "piano": 0.16, "guitar": 0.12, "strings": 0.28,
               "synth": 0.2, "brass": 0.15, "melody": 0.2, "vocals": 0.18,
               "bells": 0.35, "choir": 0.4, "counter": 0.24, "perc": 0.08, "fx": 0.3}
_SYNTHS = {"synth": {"": "pluck", "saw": "supersaw", "pad": "pad"}}

STYLES = {
    "J-Pop Energy": StyleProfile(
        name="J-Pop Energy",
        programs={"piano": 0, "bass": 33, "guitar": 29, "strings": 48, "synth": 81, "brass": 61, "melody": 81,
                  "bells": 9, "choir": 52, "counter": 48},
        drum_kit=0,
        parts={
            "Intro":       {"piano": "eighths", "bass": "driving", "guitar": "strummed", "synth": "arp", "melody": "hook",
                            "bells": "sparkle", "perc": "shaker"},
            "Build-up":    {"piano": "stabs", "bass": "driving", "strings": "build", "synth": "riser", "perc": "shaker"},
            "Verse":       {"piano": "arpeggio", "bass": "sync", "guitar": "palm_mute"},
            "Verse:2":     {"counter": "answer", "synth": "pluck", "perc": "shaker"},
            "PreChorus":   {"piano": "stabs", "bass": "driving", "guitar": "strummed", "strings": "legato", "synth": "pluck",
                            "choir": "oohs", "perc": "shaker"},
            "Chorus":      {"piano": "eighths", "bass": "driving", "guitar": "strummed", "strings": "legato",
                            "synth": "arp+supersaw", "bells": "sparkle", "counter": "answer", "perc": "claps"},
            "Chorus:last": {"choir": "aahs", "bells": "hook_octave", "perc": "claps+shaker"},
            "Bridge":      {"piano": "arpeggio", "bass": "root", "strings": "legato", "synth": "pad", "choir": "oohs",
                            "bells": "music_box"},
            "Drop":        {"bass": "wobble", "synth": "arp+supersaw", "perc": "claps"},
            "Outro":       {"piano": "eighths", "bass": "driving", "guitar": "strummed", "strings": "legato", "melody": "hook",
                            "synth": "supersaw", "bells": "sparkle"},
            "breakdown":   {"piano": "arpeggio", "strings": "legato", "synth": "pad", "bells": "music_box"},
        },
        grooves={"Intro": "pop_chorus", "Build-up": "build", "Verse": "pop_verse", "PreChorus": "pop_pre",
                 "Chorus": "pop_chorus", "Bridge": "halftime", "Drop": "four_floor", "Outro": "pop_chorus"},
        mix=_MIX_POP, reverb=_REVERB_POP,
        voices={**_SYNTHS, "melody": {"": "lead"}}, breakdown_chance=0.5,
    ),
    "Dark Vocaloid": StyleProfile(
        name="Dark Vocaloid",
        programs={"piano": 0, "bass": 34, "guitar": 30, "strings": 48, "synth": 81, "brass": 61, "melody": 30,
                  "bells": 10, "choir": 52, "counter": 40},
        drum_kit=16,
        parts={
            "Intro":       {"piano": "arpeggio16", "bass": "driving", "guitar": "power_chords", "strings": "staccato",
                            "melody": "hook", "choir": "aahs"},
            "Build-up":    {"piano": "arpeggio16", "bass": "driving", "guitar": "palm_mute", "strings": "build"},
            "Verse":       {"piano": "arpeggio16", "bass": "sync", "guitar": "palm_mute"},
            "Verse:2":     {"counter": "answer"},
            "PreChorus":   {"piano": "stabs", "bass": "driving", "guitar": "palm_mute", "strings": "staccato", "synth": "pad",
                            "choir": "oohs"},
            "Chorus":      {"piano": "arpeggio16", "bass": "driving", "guitar": "power_chords", "strings": "legato",
                            "synth": "arp+supersaw", "choir": "aahs", "counter": "answer"},
            "Chorus:last": {"bells": "hook_octave"},
            "Bridge":      {"piano": "arpeggio", "bass": "root", "strings": "legato", "synth": "pad", "choir": "oohs",
                            "bells": "music_box", "counter": "solo"},
            "Drop":        {"bass": "driving", "guitar": "palm_mute", "counter": "solo"},
            "Outro":       {"piano": "arpeggio16", "bass": "driving", "guitar": "power_chords", "strings": "legato",
                            "melody": "hook", "choir": "aahs"},
            "breakdown":   {"piano": "arpeggio", "strings": "legato", "choir": "oohs"},
        },
        grooves={"Intro": "rock_chorus", "Build-up": "build", "Verse": "rock_verse", "PreChorus": "pop_pre",
                 "Chorus": "double_kick", "Bridge": "halftime", "Drop": "rock_chorus", "Outro": "rock_chorus"},
        mix={**_MIX_POP, "guitar": -22.0, "piano": -22.5}, reverb=_REVERB_POP,
        vocal_center=66, voices=_SYNTHS, key_changes=(0, 1, 1), halftime_chance=0.4,
    ),
    "Kawaii Chiptune": StyleProfile(
        name="Kawaii Chiptune",
        programs={"piano": 8, "bass": 38, "guitar": 27, "strings": 50, "synth": 80, "brass": 62, "melody": 80,
                  "bells": 9, "choir": 54, "counter": 80},
        drum_kit=25,
        parts={
            "Intro":       {"piano": "stabs", "bass": "wobble", "synth": "arp", "melody": "hook", "bells": "sparkle16"},
            "Build-up":    {"bass": "sub_pulse", "synth": "riser", "strings": "build"},
            "Verse":       {"piano": "stabs", "bass": "sub_pulse", "synth": "pluck"},
            "Verse:2":     {"counter": "answer", "perc": "shaker"},
            "PreChorus":   {"piano": "stabs", "bass": "sub_pulse", "synth": "arp", "strings": "legato", "perc": "shaker"},
            "Chorus":      {"piano": "eighths", "bass": "wobble", "synth": "arp+supersaw", "strings": "legato",
                            "brass": "stabs", "bells": "sparkle16", "counter": "answer"},
            "Chorus:last": {"bells": "hook_octave", "choir": "aahs"},
            "Bridge":      {"piano": "arpeggio", "bass": "root", "synth": "pad", "bells": "music_box"},
            "Drop":        {"bass": "wobble", "synth": "arp+supersaw", "counter": "solo"},
            "Outro":       {"piano": "stabs", "bass": "wobble", "synth": "arp", "melody": "hook", "bells": "sparkle16"},
            "breakdown":   {"piano": "arpeggio", "synth": "pad", "bells": "music_box"},
        },
        grooves={"Intro": "four_floor", "Build-up": "build", "Verse": "edm_verse", "PreChorus": "build",
                 "Chorus": "four_floor", "Bridge": "halftime", "Drop": "four_floor", "Outro": "four_floor"},
        mix={**_MIX_POP, "synth": -22.5, "piano": -24.0}, reverb=_REVERB_POP,
        vocal_center=69, key_changes=(1, 2), breakdown_chance=0.3, halftime_chance=0.2, melisma=0.4,
        voices={"synth": {"": "chip", "saw": "supersaw", "pad": "pad"}, "melody": {"": "chip"}, "counter": {"": "chip"}},
    ),
    "Rock": StyleProfile(
        name="Rock",
        programs={"piano": 0, "bass": 34, "guitar": 30, "strings": 48, "synth": 89, "brass": 61, "melody": 29,
                  "counter": 29},
        drum_kit=16,
        parts={
            "Intro":       {"bass": "driving", "guitar": "power_chords", "melody": "hook"},
            "Build-up":    {"bass": "driving", "guitar": "palm_mute"},
            "Verse":       {"bass": "driving", "guitar": "palm_mute"},
            "Verse:2":     {"counter": "answer"},
            "PreChorus":   {"bass": "driving", "guitar": "strummed"},
            "Chorus":      {"bass": "driving", "guitar": "power_chords"},
            "Chorus:last": {"counter": "answer"},
            "Bridge":      {"bass": "root", "guitar": "chill_riff", "counter": "solo"},
            "Drop":        {"bass": "driving", "guitar": "palm_mute", "counter": "solo"},
            "Outro":       {"bass": "driving", "guitar": "power_chords", "melody": "hook"},
            "breakdown":   {"bass": "root", "guitar": "chill_riff"},
        },
        grooves={"Intro": "rock_chorus", "Build-up": "build", "Verse": "rock_verse", "PreChorus": "pop_pre",
                 "Chorus": "rock_chorus", "Bridge": "halftime", "Drop": "rock_chorus", "Outro": "rock_chorus"},
        mix={**_MIX_POP, "guitar": -20.5, "counter": -23.0}, reverb={**_REVERB_POP, "guitar": 0.08},
        key_changes=(0, 0, 2), breakdown_chance=0.3, bridge_breakdown_chance=0.2, halftime_chance=0.4, fx="soft",
        melisma=0.7,
    ),
    "Ballade": StyleProfile(
        name="Ballade",
        programs={"piano": 0, "bass": 33, "guitar": 25, "strings": 49, "synth": 89, "brass": 60, "melody": 73,
                  "bells": 8, "choir": 52, "counter": 42},
        drum_kit=8,
        parts={
            "Intro":       {"piano": "ballad_arp", "strings": "legato", "melody": "hook", "bells": "music_box"},
            "Build-up":    {"piano": "ballad_arp", "strings": "build", "bass": "root"},
            "Verse":       {"piano": "ballad_arp", "bass": "root"},
            "Verse:2":     {"counter": "guide", "synth": "pad", "strings": "pizzicato"},
            "PreChorus":   {"piano": "ballad_arp", "bass": "root", "strings": "legato+harp", "choir": "oohs"},
            "Chorus":      {"piano": "chords", "bass": "root", "strings": "legato", "guitar": "chill_riff", "synth": "pad",
                            "choir": "aahs", "bells": "accents", "counter": "guide", "perc": "shaker"},
            "Chorus:2":    {"brass": "horns"},
            "Chorus:last": {"bells": "hook_octave", "strings": "legato+timpani"},
            "Bridge":      {"piano": "ballad_arp", "strings": "legato+harp+timpani", "synth": "pad", "choir": "oohs",
                            "counter": "guide", "brass": "horns"},
            "Drop":        {"piano": "ballad_arp"},
            "Outro":       {"piano": "ballad_arp", "strings": "legato+harp", "melody": "hook", "bells": "music_box"},
            "breakdown":   {"piano": "ballad_arp", "strings": "legato"},
        },
        grooves={"Intro": None, "Build-up": "ballad", "Verse": "ballad_light", "PreChorus": "ballad",
                 "Chorus": "ballad", "Bridge": None, "Drop": None, "Outro": None},
        mix={**_MIX_POP, "piano": -19.5, "drums": -20.0, "strings": -22.0, "counter": -24.0},
        reverb={**_REVERB_POP, "piano": 0.24},
        chord_color="add9", halftime_below_bpm=200, voices={"synth": {"pad": "pad"}}, fx="soft",
        key_changes=(1, 2, 2), breakdown_chance=0.6, bridge_breakdown_chance=0.0, halftime_chance=0.0, melisma=1.6,
    ),
    "City Pop": StyleProfile(
        name="City Pop",
        programs={"piano": 5, "bass": 33, "guitar": 27, "strings": 49, "synth": 89, "brass": 61, "melody": 65,
                  "bells": 11, "choir": 53, "counter": 66},
        drum_kit=0,
        parts={
            "Intro":       {"piano": "jazz_ch", "bass": "octaves", "guitar": "cutting", "brass": "stabs", "melody": "hook",
                            "perc": "congas"},
            "Build-up":    {"piano": "jazz_ch", "bass": "sync", "guitar": "cutting", "strings": "build"},
            "Verse":       {"piano": "jazz_ch", "bass": "sync", "guitar": "cutting", "perc": "shaker"},
            "Verse:2":     {"counter": "answer"},
            "PreChorus":   {"piano": "jazz_ch", "bass": "sync", "guitar": "cutting", "strings": "legato", "perc": "shaker"},
            "Chorus":      {"piano": "jazz_ch", "bass": "octaves", "guitar": "cutting", "strings": "legato", "brass": "stabs",
                            "bells": "accents", "counter": "answer", "perc": "congas"},
            "Chorus:last": {"choir": "oohs", "perc": "congas+shaker"},
            "Bridge":      {"piano": "jazz_ch", "bass": "lazy", "strings": "legato", "synth": "pad", "bells": "accents",
                            "counter": "solo"},
            "Drop":        {"bass": "octaves", "guitar": "cutting", "counter": "solo", "perc": "congas"},
            "Outro":       {"piano": "jazz_ch", "bass": "octaves", "guitar": "cutting", "brass": "stabs", "melody": "hook",
                            "perc": "congas"},
            "breakdown":   {"piano": "jazz_ch", "bass": "lazy", "synth": "pad"},
        },
        grooves={"Intro": "citypop", "Build-up": "pop_pre", "Verse": "citypop", "PreChorus": "citypop",
                 "Chorus": "citypop", "Bridge": "halftime", "Drop": "citypop", "Outro": "citypop"},
        mix={**_MIX_POP, "piano": -21.0, "brass": -22.5}, reverb=_REVERB_POP,
        chord_color="seventh", vocal_center=66, voices={"synth": {"pad": "pad"}}, fx="soft",
        key_changes=(0, 1, 2), breakdown_chance=0.3,
    ),
}
# Genre-Namen aus älteren Einstellungen und der Kommandozeile
STYLE_ALIASES = {"J-Pop": "J-Pop Energy", "EDM": "Kawaii Chiptune", "Lo-Fi": "City Pop", "Rock": "Rock"}
DEFAULT_STYLE = "J-Pop Energy"


def get_style(name: str) -> StyleProfile:
    name = STYLE_ALIASES.get(name, name)
    return STYLES.get(name, STYLES[DEFAULT_STYLE])


def progressions_for(style: str, mode_class: str, section: str) -> list:
    """Akkordfolgen für eine Sektion; Stile mit eigener Harmonik haben Vorrang."""
    own = STYLE_PROGRESSIONS.get(style, {}).get(mode_class, {}).get(section)
    if own:
        return own
    bank = PROGRESSIONS[mode_class]
    return bank.get(section) or bank["Chorus" if section in ("Intro", "Outro", "Drop") else "Verse"]

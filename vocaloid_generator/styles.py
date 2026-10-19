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

STYLE_PROGRESSIONS["Lo-Fi"] = {
    "major": {
        "Verse": ["IVmaj7 | iii7 | ii7 | Imaj7", "ii7 | V7 | Imaj7 | vi7", "Imaj7 | vi7 | ii7 | V7"],
        "PreChorus": ["ii7 | iii7 | IVmaj7 | V7sus4"],
        "Chorus": ["IVmaj7 | V7 | iii7 | vi7", "ii7 | V7 | iii7 | vi7", "IVmaj7 | iii7 | vi7 | ii7 V7"],
        "Bridge": ["vi7 | ii7 | V7 | Imaj7"],
    },
    "minor": {
        "Verse": ["i7 | iv7 | bVII7 | bIIImaj7", "i7 | bVImaj7 | iv7 | v7"],
        "Chorus": ["bVImaj7 | v7 | i7 | i7", "iv7 | v7 | bVImaj7 | bVII7"],
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
    "Chorus": 0.9, "Bridge": 0.4, "Drop": 0.7, "Solo": 0.85, "Outro": 0.6, "Rap": 0.6, "Interlude": 0.75,
}

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
    swing: float = 0.0
    halftime_below_bpm: int = 0    # unter diesem Tempo: Sechzehntel-Gefühl statt Achtel
    voices: dict = field(default_factory=dict)   # Instrument → {Unterspur: eigene Synth-Stimme}
    fx: str = "full"               # Übergänge: full (Riser, Impact), soft (nur Becken-Swell), none
    drum_machine: str = ""         # "808" oder "909": Schlagzeug aus der Drum-Machine statt aus dem SoundFont
    sidechain: float = 0.25        # so weit ducken Bass und Synths unter der Bassdrum (Pumpen)
    texture: str = ""              # "lofi": Knistern, leiernde Bandmaschine und gedämpfte Höhen auf der Band

    def part(self, section: str, instrument: str, occurrence: int = 1, last: bool = False, feel: str = ""):
        """
        Spielweise in einer Sektion. "Verse:2" ergänzt ab dem zweiten Vorkommen, "Chorus:last" im
        letzten Vorkommen; None nimmt ein Instrument dort heraus. Im Breakdown spielt nur "breakdown".
        """
        if feel == "breakdown":
            return self.parts.get("breakdown", {}).get(instrument)
        if section == "Interlude" and section not in self.parts:
            section = "Intro"                 # Zwischenspiel: die Band spielt wie im Intro
        if section == "Solo" and "Solo" not in self.parts:
            # Solo: die Band spielt wie im Refrain, die Lead-Stimme improvisiert über die Hook
            parts = {**self.parts.get("Chorus", {}), "melody": "solo", "counter": None}
            return parts.get(instrument)
        parts = dict(self.parts.get(section, self.parts.get("Verse", {})))
        if occurrence >= 2:
            parts.update(self.parts.get(f"{section}:2", {}))
        if last:
            parts.update(self.parts.get(f"{section}:last", {}))
        return parts.get(instrument)

    def program(self, instrument: str) -> int:
        return self.programs.get(instrument, DEFAULT_PROGRAMS.get(instrument, 0))

    def groove(self, section: str) -> str:
        if section == "Solo" and section not in self.grooves:
            section = "Chorus"
        if section == "Interlude" and section not in self.grooves:
            section = "Intro"
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
                  "bells": 9, "choir": 52, "counter": 48, "solo": 29},
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
                  "bells": 10, "choir": 52, "counter": 40, "solo": 30},
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
                  "bells": 9, "choir": 54, "counter": 80, "solo": 80},
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
        voices={"synth": {"": "chip", "saw": "supersaw", "pad": "pad"}, "melody": {"": "chip", "solo": "chip"},
                "counter": {"": "chip"}},
        sidechain=0.45,
    ),
    "Rock": StyleProfile(
        name="Rock",
        programs={"piano": 0, "bass": 34, "guitar": 30, "strings": 48, "synth": 89, "brass": 61, "melody": 29,
                  "counter": 29, "solo": 29},
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
                  "bells": 8, "choir": 52, "counter": 42, "solo": 40},
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
                  "bells": 11, "choir": 53, "counter": 66, "solo": 66},
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
    "Future Bass": StyleProfile(
        name="Future Bass",
        programs={"piano": 0, "bass": 38, "guitar": 27, "strings": 49, "synth": 81, "brass": 61, "melody": 81,
                  "bells": 9, "choir": 54, "counter": 81, "solo": 81},
        drum_kit=25,
        parts={
            "Intro":       {"synth": "fb_chords", "melody": "hook", "bells": "sparkle"},
            "Build-up":    {"synth": "riser+pad", "strings": "build", "perc": "claps"},
            "Verse":       {"synth": "pluck", "bass": "root", "piano": "chords"},
            "Verse:2":     {"counter": "answer", "bells": "accents"},
            "PreChorus":   {"synth": "pad+pluck", "bass": "root", "strings": "build", "choir": "oohs"},
            "Chorus":      {"synth": "fb_chords", "bass": "sync", "bells": "sparkle", "counter": "answer",
                            "choir": "aahs", "perc": "claps"},
            "Chorus:last": {"bells": "hook_octave"},
            "Bridge":      {"synth": "pad", "piano": "chords", "bells": "music_box"},
            "Drop":        {"synth": "fb_chords", "bass": "sync", "counter": "solo", "perc": "claps"},
            "Outro":       {"synth": "fb_chords", "bass": "root", "melody": "hook", "bells": "sparkle"},
            "breakdown":   {"synth": "pad", "bells": "music_box"},
        },
        grooves={"Intro": "fb_chorus", "Build-up": "build", "Verse": "fb_verse", "PreChorus": "fb_verse",
                 "Chorus": "fb_chorus", "Bridge": "halftime", "Drop": "fb_chorus", "Outro": "fb_chorus"},
        mix={**_MIX_POP, "synth": -21.5, "bass": -19.0, "piano": -24.0}, reverb={**_REVERB_POP, "synth": 0.24},
        chord_color="add9", vocal_center=68, melisma=0.8, key_changes=(0, 0, 1), breakdown_chance=0.5,
        halftime_chance=0.0, drum_machine="808", sidechain=0.55,
        voices={"synth": {"": "pluck", "saw": "fb_chord", "pad": "pad"}, "bass": {"": "sub"},
                "melody": {"": "lead", "solo": "lead"}},
    ),
    "Drum and Bass": StyleProfile(
        name="Drum and Bass",
        programs={"piano": 4, "bass": 38, "guitar": 27, "strings": 49, "synth": 89, "brass": 61, "melody": 81,
                  "bells": 11, "choir": 52, "counter": 73, "solo": 81},
        drum_kit=8,
        parts={
            "Intro":       {"piano": "arpeggio", "synth": "pad", "melody": "hook", "bells": "accents"},
            "Build-up":    {"synth": "riser+pad", "strings": "build", "bass": "root"},
            "Verse":       {"piano": "arpeggio", "bass": "rolling", "synth": "pad"},
            "Verse:2":     {"counter": "answer", "perc": "shaker"},
            "PreChorus":   {"piano": "arpeggio16", "bass": "rolling", "strings": "legato", "synth": "pad"},
            "Chorus":      {"piano": "stabs", "bass": "rolling", "strings": "legato", "synth": "pad+arp",
                            "counter": "answer", "bells": "accents", "choir": "aahs"},
            "Chorus:last": {"bells": "hook_octave"},
            "Bridge":      {"piano": "arpeggio", "bass": "root", "strings": "legato", "synth": "pad"},
            "Drop":        {"bass": "rolling", "synth": "arp", "counter": "solo"},
            "Outro":       {"piano": "arpeggio", "bass": "rolling", "synth": "pad", "melody": "hook"},
            "breakdown":   {"piano": "arpeggio", "synth": "pad", "strings": "legato"},
        },
        grooves={"Intro": "dnb_verse", "Build-up": "build", "Verse": "dnb_verse", "PreChorus": "dnb_verse",
                 "Chorus": "dnb", "Bridge": "halftime", "Drop": "dnb", "Outro": "dnb"},
        mix={**_MIX_POP, "drums": -16.0, "bass": -19.0, "piano": -23.0}, reverb=_REVERB_POP,
        chord_color="seventh", key_changes=(0, 0, 1), breakdown_chance=0.5, halftime_chance=0.0, sidechain=0.3,
        voices={"bass": {"": "reese"}, "synth": {"": "pluck", "pad": "pad"}, "melody": {"solo": "lead"}},
    ),
    "Lo-Fi": StyleProfile(
        name="Lo-Fi",
        programs={"piano": 4, "bass": 33, "guitar": 26, "strings": 49, "synth": 89, "brass": 65, "melody": 11,
                  "bells": 11, "choir": 52, "counter": 73, "solo": 65},
        drum_kit=0,
        parts={
            "Intro":       {"piano": "jazz_ch", "melody": "hook"},
            "Build-up":    {"piano": "jazz_ch", "bass": "lazy"},
            "Verse":       {"piano": "jazz_ch", "bass": "lazy"},
            "Verse:2":     {"guitar": "chill_riff", "counter": "guide"},
            "PreChorus":   {"piano": "jazz_ch", "bass": "lazy", "synth": "pad"},
            "Chorus":      {"piano": "jazz_ch", "bass": "lazy", "guitar": "chill_riff", "synth": "pad",
                            "bells": "accents", "counter": "answer"},
            "Chorus:last": {"strings": "legato"},
            "Bridge":      {"piano": "ballad_arp", "bass": "root", "synth": "pad", "counter": "solo"},
            "Drop":        {"piano": "jazz_ch", "bass": "lazy", "counter": "solo"},
            "Outro":       {"piano": "jazz_ch", "bass": "lazy", "melody": "hook"},
            "breakdown":   {"piano": "jazz_ch", "synth": "pad"},
        },
        grooves={"Intro": "lofi_light", "Build-up": "lofi_light", "Verse": "lofi", "PreChorus": "lofi",
                 "Chorus": "lofi", "Bridge": "lofi_light", "Drop": "lofi", "Outro": "lofi_light"},
        mix={**_MIX_POP, "piano": -20.5, "drums": -18.0, "guitar": -24.0},
        reverb={**_REVERB_POP, "piano": 0.2, "drums": 0.1},
        chord_color="seventh", vocal_center=65, melisma=0.8, swing=0.45, halftime_below_bpm=110, fx="soft",
        key_changes=(0,), breakdown_chance=0.2, bridge_breakdown_chance=0.2, halftime_chance=0.0, sidechain=0.15,
        texture="lofi", voices={"synth": {"pad": "pad"}},
    ),
    "Idol-Pop": StyleProfile(
        name="Idol-Pop",
        programs={"piano": 0, "bass": 33, "guitar": 27, "strings": 48, "synth": 81, "brass": 61, "melody": 81,
                  "bells": 9, "choir": 52, "counter": 61, "solo": 29},
        drum_kit=0,
        parts={
            "Intro":       {"piano": "eighths", "bass": "octaves", "guitar": "cutting", "brass": "stabs", "synth": "arp",
                            "melody": "hook", "bells": "sparkle", "perc": "claps"},
            "Build-up":    {"bass": "driving", "strings": "build", "synth": "riser", "perc": "claps"},
            "Verse":       {"piano": "stabs", "bass": "sync", "guitar": "cutting"},
            "Verse:2":     {"counter": "answer", "perc": "tambourine"},
            "PreChorus":   {"piano": "eighths", "bass": "driving", "guitar": "strummed", "strings": "build",
                            "synth": "pluck", "perc": "claps"},
            "Chorus":      {"piano": "eighths", "bass": "driving", "guitar": "strummed", "strings": "legato",
                            "brass": "stabs", "synth": "arp+supersaw", "bells": "sparkle", "counter": "answer",
                            "perc": "claps+tambourine"},
            "Chorus:last": {"bells": "hook_octave", "choir": "aahs"},
            "Bridge":      {"piano": "arpeggio", "bass": "root", "strings": "legato", "synth": "pad",
                            "bells": "music_box"},
            "Drop":        {"bass": "octaves", "guitar": "cutting", "brass": "stabs", "synth": "arp", "perc": "claps"},
            "Outro":       {"piano": "eighths", "bass": "octaves", "guitar": "cutting", "brass": "stabs",
                            "melody": "hook", "bells": "sparkle", "perc": "claps"},
            "breakdown":   {"piano": "arpeggio", "strings": "legato", "bells": "music_box"},
        },
        grooves={"Intro": "four_floor", "Build-up": "build", "Verse": "idol_verse", "PreChorus": "pop_pre",
                 "Chorus": "four_floor", "Bridge": "halftime", "Drop": "four_floor", "Outro": "four_floor"},
        mix={**_MIX_POP, "brass": -22.5, "guitar": -23.5}, reverb=_REVERB_POP,
        vocal_center=69, melisma=0.5, key_changes=(1, 2, 2), breakdown_chance=0.5, halftime_chance=0.2,
        voices={**_SYNTHS, "melody": {"": "lead"}},
    ),
}
# Genre-Namen aus älteren Einstellungen und der Kommandozeile
STYLE_ALIASES = {"J-Pop": "J-Pop Energy", "EDM": "Kawaii Chiptune", "Rock": "Rock"}
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

# style_dna.py – Was jeden Stil unverwechselbar macht (1.4.0)
#
# Bis 1.3 teilten sich die Stile fast alles außer den Instrumenten: dieselben Akkordfolgen (nur City Pop und Lo-Fi
# hatten eigene), dieselben Schlusskadenzen, dieselben Regeln für die Melodie, dieselbe Bewertung der besten Melodie,
# denselben Hall und dasselbe Delay. Darum klang ein Rock-Song wie ein Idol-Song mit Gitarren. Hier steht je Stil:
# - Akkorde: eigene Folgen für Strophe, Pre-Chorus, Refrain und Bridge, mit eigener Geschwindigkeit der Wechsel
#   (Dark Vocaloid zwei Akkorde im Takt, Lo-Fi zwei Takte auf einem) und eigenen Kadenzen (Rock bVI-bVII-I,
#   City Pop ii-V-I, Dark Vocaloid iv-V7-i).
# - Melodie-Charakter: wie dicht gesungen wird, welche Rhythmen (auf dem Schlag, synkopiert, lang, abgehackt),
#   welche Sprünge typisch sind, wie oft ein Ton wiederholt wird, wie weit die Melodie ausholt und wie die Töne
#   enden (Kawaii und Idol kurz und abgesetzt, Ballade gebunden). Dazu, was die Bewertung der besten Melodie im Stil
#   für gut hält.
# - Arrangement: was im Stil spielt und was nicht (Rock ohne Glockenspiel, Ballade ohne Synth, Lo-Fi ohne Streicher).
# - Klangbild: Raum, Delay, Klangfarbe des Masters, Breite und Sättigung je Stil.
from dataclasses import dataclass, field
from typing import Optional

# ── Akkorde ─────────────────────────────────────────────────────────────────────
# Wie styles.PROGRESSIONS: Takte durch "|", zwei Akkorde in einem Takt teilen sich den Takt.
PROGRESSIONS = {
    "J-Pop Energy": {
        "major": {
            "Verse": ["I | V/3 | vi | iii | IV | I/3 | ii | V", "vi | IV | V | I", "IV | V | iii | vi",
                      "I | iii | IV | V"],
            "PreChorus": ["IV | V | iii | vi", "ii7 | iii7 | IV | V", "IV | iii | ii | V"],
            "Chorus": ["IVmaj7 | V7 | iii7 | vi", "IV | V | III7 | vi", "IVmaj7 | V | iii7 vi | ii7 V",
                       "vi | IV | V | I"],
            "Bridge": ["vi | IV | I | V", "IV | iv | I | vi", "bVI | bVII | I | I"],
        },
        "minor": {
            "Verse": ["i | bVI | bVII | i", "i | bVII | bVI | V", "i | iv | bVII | bIII"],
            "PreChorus": ["iv | v | bVI | bVII", "bVI | bVII | bIII | bVI"],
            "Chorus": ["bVImaj7 | bVII | v7 | i", "bVI | bVII | i | i", "i | bVI | bIII | bVII",
                       "bVImaj7 | bVII7 | V7 | i"],
            "Bridge": ["bVI | bVII | bIII | bVI", "iv | i | bVII | bIII"],
        },
    },
    "Dark Vocaloid": {
        "minor": {
            # langsam in der Strophe (zwei Takte Moll), phrygisches bII, absteigender Bass (Lamento)
            "Verse": ["i | i | bVI | bVII", "i | bII | i | bII", "i | i7/7 | bVI | V", "i | iv | i | V7"],
            "PreChorus": ["bVI | bVII | bIII | V", "iv | V | bVI | bVII", "bII | bVII | bVI | V"],
            # schnell im Refrain: zwei Akkorde im Takt, wie im Vocaloid-Rock
            "Chorus": ["i bVI | bVII i | iv bVI | V V", "bVI bVII | i | bVI bVII | V7", "i | bVI | bIII | bVII"],
            "Bridge": ["bII | i | bII | V", "iim7b5 | V7 | i | bVI", "iv | bVI | iv | V"],
        },
        "major": {
            "Verse": ["vi | iii | IV | V", "vi | IV | I | V"],
            "PreChorus": ["IV | V | iii | vi"],
            "Chorus": ["vi | IV | V | III7", "IV | V | iii | vi"],
            "Bridge": ["iv | I | iv | V", "bVI | bVII | I | I"],
        },
    },
    "Kawaii Chiptune": {
        "major": {
            "Verse": ["I | V | vi | IV", "I | IV | V | I", "I | iii | IV | V", "I | IV | V | vi"],
            "PreChorus": ["IV | V | iii | vi", "IV | V | IV | V", "ii | V | iii | vi"],
            "Chorus": ["I V | vi IV | I V | IV V", "IV | V | III7 | vi", "I | V/3 | vi | IV",
                       "IV V | iii vi | ii V | I I"],
            "Bridge": ["vi | IV | ii | V", "IV | V | vi | vi"],
        },
        "minor": {
            "Verse": ["i | bVII | bVI | bVII", "i | bIII | bVII | iv"],
            "Chorus": ["bVI | bVII | bIII | bVI", "bIII | bVII | iv | i", "bVI bVII | i i | bVI bVII | i i"],
        },
    },
    "Rock": {
        "major": {
            # mixolydisches bVII und der Mario-Schluss bVI-bVII-I
            "Verse": ["I | bVII | IV | I", "I | I | bVII | IV", "vi | IV | I | V", "I | V | IV | IV"],
            "PreChorus": ["IV | V | IV | V", "vi | V | IV | V", "bVI | bVII | V | V"],
            "Chorus": ["I | V | vi | IV", "I | bVII | IV | V", "IV | I | V | vi", "bVI | bVII | I | I"],
            "Bridge": ["vi | V | IV | V", "bVI | bVII | IV | V", "IV | IV | V | V"],
        },
        "minor": {
            "Verse": ["i | i | bVII | bVII", "i | bVII | bVI | bVII", "i | bIII | bVII | iv"],
            "PreChorus": ["bVI | bVII | bVI | bVII", "iv | bVI | bVII | bVII"],
            "Chorus": ["i | bVI | bIII | bVII", "bVI | bVII | i | i", "i | bVII | bVI | V"],
            "Bridge": ["bVI | bVII | V | V", "iv | iv | bVI | bVII"],
        },
    },
    "Ballade": {
        "major": {
            # absteigender Bass (Kanon), sus4 vor der Dominante, die Moll-Subdominante für den Kloß im Hals
            "Verse": ["I | V/3 | vi | I/5 | IV | I/3 | iv | V", "Iadd9 | iii | IV | V", "I | IV/3 | V | I/3"],
            "PreChorus": ["IV | iii7 | ii7 | Vsus4 V", "ii7 | I/3 | IV | Vsus4 V"],
            "Chorus": ["IVmaj7 | V | iii7 | vi | ii7 | V | Iadd9 | Iadd9", "I | V/3 | vi | I/5 | IV | I/3 | ii | V",
                       "IV | V | iii | vi | IV | iv | I | I"],
            "Bridge": ["vi | iii | IV | I/3", "ii7 | iii7 | IVmaj7 | Vsus4 V", "bVI | bVII | I | I"],
        },
        "minor": {
            "Verse": ["i | i7/7 | bVImaj7 | V", "i | bVII | bVI | iv | i | iv | V | V"],
            "PreChorus": ["iv | bVII | bIIImaj7 | V"],
            "Chorus": ["bVImaj7 | bVII | bIIImaj7 | bVImaj7 | iv7 | V | i | i", "bVI | bVII | i | i"],
            "Bridge": ["bVI | bIII | bVII | i", "iv | i/3 | bVI | V"],
        },
    },
    "City Pop": {
        "major": {
            "Verse": ["IVmaj7 | iii7 | ii7 | Imaj7", "Imaj7 | vi7 | ii7 | V7", "IVmaj7 | III7 | vi7 | v7 I7"],
            "PreChorus": ["ii7 | iii7 | IVmaj7 | V7sus4", "ii7 | V7 | iii7 | VI7"],
            "Chorus": ["IVmaj7 | III7 | vi7 | v7 I7", "IVmaj7 | V7 | iii7 | vi7", "ii7 | V7 | Imaj7 | VI7"],
            "Bridge": ["ii7 | V7 | Imaj7 | vi7", "bVImaj7 | bVII7 | Imaj7 | Imaj7"],
        },
        "minor": {
            "Verse": ["i7 | iv7 | bVII7 | bIIImaj7", "i9 | iv9 | i9 | iv9"],
            "PreChorus": ["bVImaj7 | v7 | iv7 | V7"],
            "Chorus": ["bVImaj7 | bVII7 | v7 | i7", "iv7 | bVII7 | bIIImaj7 | bVImaj7", "bVImaj7 | V7 | i7 | i7"],
            "Bridge": ["iv7 | bVII7 | bIIImaj7 | V7"],
        },
    },
    "Future Bass": {
        "major": {
            "Verse": ["IVmaj7 | V | vi | vi", "vi | IV | I | V", "I | V | vi | IV"],
            "PreChorus": ["IV | V | vi | vi", "ii7 | IV | V | V"],
            "Chorus": ["IVmaj7 | V | iii7 | vi", "IVmaj9 | V | vi9 | vi9", "vi | IV | I | V"],
            "Bridge": ["IVmaj7 | IVmaj7 | V | V", "vi | V | IV | IV"],
        },
        "minor": {
            "Verse": ["bVImaj7 | bVII | i | i", "i | bVI | bIII | bVII"],
            "Chorus": ["bVImaj7 | bVII | v7 | i", "iv7 | bVII | bIIImaj7 | bVImaj7", "bVI | bVII | i | i"],
            "Bridge": ["bVImaj7 | bVImaj7 | bVII | bVII"],
        },
    },
    "Drum and Bass": {
        "minor": {
            # Liquid: dorisches IV7, lange Moll-Neunen
            "Verse": ["i7 | iv7 | i7 | iv7", "i9 | bVImaj7 | bVII | i9", "i7 | IV7 | i7 | IV7"],
            "PreChorus": ["bVImaj7 | bVII7 | bVImaj7 | bVII7", "iv7 | v7 | bVImaj7 | bVII"],
            "Chorus": ["bVImaj7 | bVII | i7 | i7", "i7 | bVImaj7 | bIIImaj7 | bVII", "iv9 | bVII7 | bIIImaj7 | bVImaj7"],
            "Bridge": ["bVImaj7 | bVImaj7 | bVII | bVII", "iv7 | v7 | bVImaj7 | bVII"],
        },
        "major": {
            "Verse": ["Imaj7 | iii7 | vi7 | IVmaj7", "vi7 | IVmaj7 | Imaj7 | V"],
            "Chorus": ["IVmaj7 | V7 | iii7 | vi7", "vi7 | IVmaj7 | ii7 | V7"],
            "Bridge": ["IVmaj7 | IVmaj7 | V | V"],
        },
    },
    "Lo-Fi": {
        "major": {
            # zwei Takte auf einem Akkord und Zwei-Akkord-Vamps, wie geloopt
            "Verse": ["IVmaj7 | iii7 | ii7 | Imaj7", "Imaj7 | IVmaj7 | Imaj7 | IVmaj7", "IVmaj7 | IVmaj7 | iii7 | vi7",
                      "ii7 | V7 | Imaj7 | vi7"],
            "PreChorus": ["ii7 | iii7 | IVmaj7 | V7sus4"],
            "Chorus": ["IVmaj7 | V7 | iii7 | vi7", "ii7 | V7 | Imaj7 | IVmaj7", "IVmaj7 | iii7 | vi7 | ii7 V7"],
            "Bridge": ["vi7 | ii7 | V7 | Imaj7", "IVmaj7 | IVmaj7 | iii7 | iii7"],
        },
        "minor": {
            "Verse": ["i7 | iv7 | bVII7 | bIIImaj7", "i9 | iv9 | i9 | iv9", "i7 | bVImaj7 | iv7 | v7"],
            "Chorus": ["bVImaj7 | v7 | i7 | i7", "iv7 | v7 | bVImaj7 | bVII7", "i9 | iv9 | bVImaj7 | V7"],
        },
    },
    "Idol-Pop": {
        "major": {
            "Verse": ["I | V | vi | iii | IV | I | IV | V", "I | IV | V | I", "I V | vi IV | ii V | I I"],
            "PreChorus": ["IV | V | iii | vi | ii | iii | IV | V", "IV | V | III7 | vi"],
            "Chorus": ["IV | V | iii | vi | ii | V | I | I", "I | V/3 | vi | I/5 | IV | I/3 | II7 | V",
                       "IV V | iii vi | ii V | I I"],
            "Bridge": ["vi | V | IV | V", "bVI | bVII | I | I"],
        },
        "minor": {
            "Verse": ["i | bVII | bVI | bVII", "i | bVI | bVII | i"],
            "Chorus": ["bVI | bVII | i | i", "bVI | bVII | V | i"],
        },
    },
    # 1.5.0: Wafuu-Rock in Moll mit bVI-bVII-i und dem „Senbonzakura“-Gang, Electro-Swing mit Jazz-Wendungen,
    # Hyperpop hell und mit großen Sprüngen zwischen den Stufen
    "Wafuu-Rock": {
        "minor": {
            "Verse": ["i | bVII | bVI | bVII", "i | iv | bVII | bIII", "i | bVI | bVII | i", "i | i | iv | v"],
            "PreChorus": ["bVI | bVII | bIII | bVI", "iv | v | bVI | bVII", "bVI | bVII | V | V"],
            "Chorus": ["bVI | bVII | v | i", "bVImaj7 | bVII | v7 | i", "i | bVII | bVI | bVII i",
                       "bVI | bVII | i | i"],
            "Bridge": ["iv | i | bVII | bIII", "bVI | bIII | bVII | V"],
        },
        "major": {
            "Verse": ["vi | IV | V | vi", "I | V | vi | iii"],
            "PreChorus": ["IV | V | iii | vi"],
            "Chorus": ["IV | V | iii | vi", "IVmaj7 | V | iii7 | vi"],
            "Bridge": ["vi | IV | I | V"],
        },
    },
    "Electro-Swing": {
        "minor": {
            "Verse": ["i | i | iv | V7", "i | bVI7 | V7 | i", "i7 | iv7 | V7 | i7"],
            "PreChorus": ["iv7 | i | bVI7 | V7", "iv | iv | V7 | V7"],
            "Chorus": ["i | iv | V7 | i", "i | bVI7 | V7 | i", "iv7 | V7 | i7 | VI7"],
            "Bridge": ["bVImaj7 | V7 | i | i", "iv7 | bVII7 | bIIImaj7 | V7"],
        },
        "major": {
            "Verse": ["I | VI7 | ii7 | V7", "Imaj7 | vi7 | ii7 | V7", "I | I7 | IV | iv"],
            "PreChorus": ["ii7 | V7 | iii7 | VI7", "IV | iv | I | V7"],
            "Chorus": ["I | VI7 | II7 | V7", "Imaj7 | VI7 | ii7 | V7", "IV | iv | I | VI7"],
            "Bridge": ["III7 | VI7 | II7 | V7"],
        },
    },
    "Hyperpop": {
        "major": {
            "Verse": ["I | V | vi | IV", "vi | IV | I | V", "I | iii | vi | IV"],
            "PreChorus": ["IV | V | vi | vi", "IV | IV | V | V"],
            "Chorus": ["I | V | vi | IV", "IV | V | vi | I", "I V | vi IV | I V | IV V"],
            "Bridge": ["vi | IV | ii | V", "bVI | bVII | I | I"],
        },
        "minor": {
            "Verse": ["i | bVI | bIII | bVII", "i | bVII | bVI | bVII"],
            "Chorus": ["bVI | bVII | i | i", "i | bVI | bIII | bVII"],
            "Bridge": ["bVI | bIII | bVII | V"],
        },
    },
}

# Schluss des Refrains und Akkord vor dem Refrain je Stil (wie styles.CADENCES)
CADENCES = {
    "Dark Vocaloid": {"minor": {"to_chorus": "V7", "end": ("iv V7", "i")},
                      "major": {"to_chorus": "V", "end": ("iv V", "I")}},
    "J-Pop Energy": {"major": {"to_chorus": "IV V", "end": ("IV V", "I")},
                     "minor": {"to_chorus": "bVI bVII", "end": ("bVI bVII", "i")}},
    "Kawaii Chiptune": {"major": {"to_chorus": "V7", "end": ("IV V7", "I")},
                        "minor": {"to_chorus": "V7", "end": ("iv V7", "i")}},
    "Rock": {"major": {"to_chorus": "V", "end": ("bVI bVII", "I")},
             "minor": {"to_chorus": "bVII", "end": ("bVI bVII", "i")}},
    "Ballade": {"major": {"to_chorus": "Vsus4 V", "end": ("IV V7sus4", "I")},
                "minor": {"to_chorus": "Vsus4 V", "end": ("iv V7", "i")}},
    "City Pop": {"major": {"to_chorus": "V7sus4", "end": ("ii7 V7", "Imaj7")},
                 "minor": {"to_chorus": "V7", "end": ("iim7b5 V7", "i7")}},
    "Future Bass": {"major": {"to_chorus": "V", "end": ("IVmaj7 V", "Iadd9")},
                    "minor": {"to_chorus": "bVII", "end": ("bVImaj7 bVII", "i")}},
    "Drum and Bass": {"minor": {"to_chorus": "bVII", "end": ("bVImaj7 bVII", "i7")},
                      "major": {"to_chorus": "V7", "end": ("IVmaj7 V7", "Imaj7")}},
    "Lo-Fi": {"major": {"to_chorus": "ii7 V7", "end": ("ii7 V7", "Imaj7")},
              "minor": {"to_chorus": "V7", "end": ("iim7b5 V7", "i9")}},
    "Idol-Pop": {"major": {"to_chorus": "V7", "end": ("ii V7", "I")},
                 "minor": {"to_chorus": "V7", "end": ("iv V7", "i")}},
    "Wafuu-Rock": {"minor": {"to_chorus": "bVI bVII", "end": ("bVI bVII", "i")},
                   "major": {"to_chorus": "IV V", "end": ("IV V", "vi")}},
    "Electro-Swing": {"minor": {"to_chorus": "V7", "end": ("iim7b5 V7", "i")},
                      "major": {"to_chorus": "V7", "end": ("ii7 V7", "I")}},
    "Hyperpop": {"major": {"to_chorus": "IV V", "end": ("IV V", "I")},
                 "minor": {"to_chorus": "bVII", "end": ("bVI bVII", "i")}},
}


# 1.5.0 (C1): J-Pop Energy als Anison-Band ohne die „Royal Road“ IV–V–iii–vi, die bis 1.4 auch Idol-Pop spielte:
# Komuro-Folge vi–IV–V–I, I–V–vi–IV, IV–V–vi und vor dem Refrain der Anlauf bVI–bVII
SPLIT_PROGRESSIONS = {
    "J-Pop Energy": {
        "major": {
            "Verse": ["vi | IV | V | I", "vi | V | IV | V", "I | V | vi | IV", "I | V/3 | vi | V"],
            "PreChorus": ["IV | V | vi | vi", "ii | iii | IV | V", "IV | IV | V | V", "bVI | bVII | V | V"],
            "Chorus": ["vi | IV | V | I", "I | V | vi | IV", "IV | V | vi | I", "vi | IV | V | V"],
            "Bridge": ["vi | V | IV | V", "bVI | bVII | I | I", "ii | V | vi | vi"],
        },
        "minor": {
            "Verse": ["i | bVI | bVII | i", "i | bVII | bVI | bVII", "i | i | bVI | bVII"],
            "PreChorus": ["bVI | bVII | V | V", "iv | bVI | bVII | bVII"],
            "Chorus": ["i | bVI | bIII | bVII", "bVI | bVII | i | i", "i | bVII | bVI | V", "i | bVI | bVII | i"],
            "Bridge": ["bVI | bVII | V | V", "iv | bVI | bVII | bVII"],
        },
    },
}
SPLIT_CADENCES = {
    "J-Pop Energy": {"major": {"to_chorus": "bVI bVII", "end": ("bVI bVII", "I")},
                     "minor": {"to_chorus": "V", "end": ("bVI bVII", "i")}},
}


def progressions(style: str, mode_class: str, section: str, split: bool = False) -> Optional[list]:
    """Die eigenen Akkordfolgen des Stils für eine Sektion (Intro, Outro und Drop wie der Refrain), sonst None.
    split: J-Pop Energy als Anison-Band (SPLIT_PROGRESSIONS)."""
    bank = ((split and SPLIT_PROGRESSIONS.get(style)) or PROGRESSIONS.get(style, {})).get(mode_class, {})
    return bank.get(section) or bank.get("Chorus" if section in ("Intro", "Outro", "Drop") else "Verse") or None


def cadences(style: str, mode_class: str, split: bool = False) -> Optional[dict]:
    """Die eigene Kadenz des Stils ({"to_chorus", "end"}), sonst None."""
    return ((split and SPLIT_CADENCES.get(style)) or CADENCES.get(style, {})).get(mode_class)


# ── Melodie-Charakter ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MelodyCharacter:
    density: float = 1.0           # mal melody_writer.SYLLABLES_PER_SECOND
    rhythm: str = "even"           # even | syncopated | laid_back | driving | long (rhythm_fit)
    rhythm_pull: float = 1.5       # wie stark die Rhythmen des Stils bevorzugt werden (0 = gar nicht)
    step_cost: float = 1.0         # mal den Kosten von Schritten (1 bis 2 Halbtöne)
    leap_cost: float = 1.0         # mal den Kosten von Sprüngen (ab 3 Halbtönen)
    favorite_leaps: tuple = ()     # diese Intervalle (Halbtöne) sind im Stil typisch und kosten wenig
    repeat_bonus: float = 0.0      # schnelle Tonwiederholungen werden so viel billiger
    contour: float = 1.0           # wie weit Phrasen und Gesten ausholen
    staccato: float = 0.0          # so viele Achtel (mitten in der Phrase) werden kurz und abgesetzt gesungen
    gestures: dict = field(default_factory=dict)   # Sektionsart → Gewichte der Gesten (melody_writer.GESTURES)
    score: dict = field(default_factory=dict)      # was die Bewertung der besten Melodie im Stil anders sieht
    # 1.5.0: Stufen (Halbtöne über dem Grundton), die die Melodie meidet: {"major": …, "minor": …}; Wafuu-Rock
    # singt so in der japanischen Fünftonleiter (Yonanuki: ohne vierte und siebte Stufe, in Moll ohne zweite und sechste)
    avoid: dict = field(default_factory=dict)


# Die Rhythmen, die jeder Stil zusätzlich kennt (Einsätze in Sechzehnteln, wie melody_writer.BODY_RHYTHMS)
EXTRA_RHYTHMS = {
    "syncopated": {2: [(0, 6), (3, 10)], 3: [(0, 3, 10), (0, 6, 10), (3, 6, 12)], 4: [(0, 3, 6, 10), (0, 3, 8, 11),
                   (2, 6, 10, 14)], 5: [(0, 3, 6, 10, 12), (0, 2, 6, 10, 14)], 6: [(0, 3, 6, 8, 11, 14)]},
    "laid_back": {2: [(2, 10), (2, 8)], 3: [(2, 6, 12), (2, 8, 11)], 4: [(2, 6, 10, 12), (2, 5, 8, 12)],
                  5: [(2, 4, 6, 10, 12), (2, 5, 8, 10, 14)]},
    "driving": {4: [(0, 2, 4, 6)], 6: [(0, 2, 4, 6, 8, 10)], 7: [(0, 2, 4, 6, 8, 10, 12)],
                8: [(0, 2, 4, 6, 8, 10, 12, 14)], 9: [(0, 2, 4, 6, 7, 8, 10, 12, 14)],
                10: [(0, 2, 3, 4, 6, 8, 10, 11, 12, 14)]},
    "long": {2: [(0, 8)], 3: [(0, 8, 12), (0, 4, 8)], 4: [(0, 4, 8, 12)]},
    "even": {3: [(0, 4, 8)], 4: [(0, 4, 8, 12), (0, 2, 4, 8)], 5: [(0, 2, 4, 8, 12)], 6: [(0, 2, 4, 8, 10, 12)]},
}

CHARACTERS = {
    "J-Pop Energy": MelodyCharacter(density=1.05, rhythm="syncopated", rhythm_pull=0.8, leap_cost=0.9,
                                    favorite_leaps=(5,), contour=1.1),
    # schnelle, dichte Vocaloid-Strophen, dramatische Sexten, weit ausholend
    "Dark Vocaloid": MelodyCharacter(density=1.2, rhythm="driving", rhythm_pull=1.5, leap_cost=0.85,
                                     favorite_leaps=(7, 8), repeat_bonus=0.3, contour=1.3, staccato=0.15,
                                     score={"leaps": (0.15, 0.38), "range": {"Chorus": (10, 15), "Verse": (7, 12)}}),
    # hüpfend: Terzen und Quarten, viele Tonwiederholungen, kurz und abgesetzt
    "Kawaii Chiptune": MelodyCharacter(density=1.15, rhythm="even", rhythm_pull=2.0, step_cost=1.1, leap_cost=0.8,
                                       favorite_leaps=(3, 4, 5), repeat_bonus=0.5, contour=1.0, staccato=0.55,
                                       gestures={"Chorus": {"neighbor": 3, "leap_fall": 2, "arch": 1},
                                                 "Verse": {"neighbor": 3, "rise": 1, "fall": 1}},
                                       score={"repeats": (0.15, 0.42), "leaps": (0.15, 0.38)}),
    # gerufen: Quarten und Quinten, Tonwiederholungen, Synkopen
    "Rock": MelodyCharacter(density=0.95, rhythm="syncopated", rhythm_pull=1.5, leap_cost=0.9,
                            favorite_leaps=(5, 7), repeat_bonus=0.4, contour=1.2, staccato=0.1,
                            score={"repeats": (0.1, 0.36)}),
    # gebunden und schrittweise, lange Töne, weite Bögen
    "Ballade": MelodyCharacter(density=0.75, rhythm="long", rhythm_pull=2.0, step_cost=0.7, leap_cost=1.3,
                               favorite_leaps=(7,), contour=1.3,
                               gestures={"Chorus": {"arch": 3, "leap_fall": 1, "fall": 1},
                                         "Verse": {"arch": 2, "rise": 2, "fall": 1}},
                               score={"steps": (0.55, 0.85), "leaps": (0.05, 0.22), "range": {"Chorus": (10, 14)}}),
    # zurückgelehnt: Einsätze nach dem Schlag, Terzen wie im Jazz
    "City Pop": MelodyCharacter(density=0.95, rhythm="laid_back", rhythm_pull=1.5, leap_cost=0.9,
                                favorite_leaps=(3, 4), contour=0.9, staccato=0.1,
                                score={"leaps": (0.12, 0.32)}),
    # zerhackt: Synkopen mit Luft, Quarten und Oktaven
    "Future Bass": MelodyCharacter(density=0.85, rhythm="syncopated", rhythm_pull=1.8, leap_cost=0.85,
                                   favorite_leaps=(5, 7, 12), contour=1.1, staccato=0.3),
    # lange Töne über dem schnellen Schlagzeug (halbes Tempo im Gesang)
    "Drum and Bass": MelodyCharacter(density=0.7, rhythm="long", rhythm_pull=2.0, step_cost=0.8,
                                     favorite_leaps=(5,), contour=1.2,
                                     score={"steps": (0.5, 0.82)}),
    # eng, tief und gemütlich, viel auf einem Ton
    "Lo-Fi": MelodyCharacter(density=0.75, rhythm="laid_back", rhythm_pull=1.8, step_cost=0.8, leap_cost=1.3,
                             repeat_bonus=0.3, contour=0.6,
                             score={"range": {"Chorus": (6, 10), "Verse": (4, 8), "PreChorus": (5, 9),
                                              "Bridge": (5, 9)}, "repeats": (0.1, 0.38)}),
    # zum Mitklatschen: auf dem Schlag, kurze Töne, eingängige Wiederholung
    "Idol-Pop": MelodyCharacter(density=1.1, rhythm="even", rhythm_pull=1.5, favorite_leaps=(5,), repeat_bonus=0.3,
                                contour=1.1, staccato=0.35,
                                score={"repeats": (0.1, 0.36), "motif_weight": 1.6}),
}
# 1.5.0
CHARACTERS.update({
    # Fünftonleiter, weite Bögen mit Quarten und Quinten, lange Töne am Phrasenende
    "Wafuu-Rock": MelodyCharacter(density=1.0, rhythm="driving", rhythm_pull=1.2, leap_cost=0.85,
                                  favorite_leaps=(5, 7), contour=1.25, staccato=0.05,
                                  avoid={"major": (5, 11), "minor": (2, 8)},
                                  gestures={"Chorus": {"arch": 3, "leap_fall": 2, "fall": 1}},
                                  score={"range": {"Chorus": (10, 15)}}),
    # Swing: synkopiert und abgehackt wie eine Bläser-Phrase, Terzen und Sexten
    "Electro-Swing": MelodyCharacter(density=1.0, rhythm="syncopated", rhythm_pull=1.8, leap_cost=0.9,
                                     favorite_leaps=(3, 4, 9), repeat_bonus=0.3, contour=1.0, staccato=0.35,
                                     score={"repeats": (0.1, 0.38)}),
    # alles zu viel: dicht, hoch, Oktavsprünge, kurz abgesetzt
    "Hyperpop": MelodyCharacter(density=1.2, rhythm="even", rhythm_pull=1.4, step_cost=1.1, leap_cost=0.75,
                                favorite_leaps=(5, 7, 12), repeat_bonus=0.4, contour=1.35, staccato=0.45,
                                score={"leaps": (0.18, 0.42), "range": {"Chorus": (11, 16)}}),
})
NEUTRAL = MelodyCharacter()


def character(style: str) -> MelodyCharacter:
    return CHARACTERS.get(style, NEUTRAL)


def rhythm_fit(onsets: tuple, rhythm: str, bar_steps: int = 16) -> float:
    """Wie gut ein Takt-Rhythmus zum Rhythmus des Stils passt, etwa -1 bis 1."""
    if not onsets:
        return 0.0
    n = len(onsets)
    on_beat = sum(1 for s in onsets if s % 4 == 0) / n
    off_eighth = sum(1 for s in onsets if s % 4 == 2) / n
    sixteenth = sum(1 for s in onsets if s % 2 == 1) / n
    gaps = [b - a for a, b in zip(onsets, onsets[1:])] + [bar_steps - onsets[-1]]
    even = 1.0 - (max(gaps) - min(gaps)) / bar_steps
    if rhythm == "even":
        return on_beat + 0.5 * off_eighth - 1.5 * sixteenth
    if rhythm == "syncopated":
        return 0.8 * sixteenth + 0.6 * off_eighth - 0.4 * on_beat + 0.3 * (onsets[0] != 0)
    if rhythm == "laid_back":
        return 1.0 * (onsets[0] != 0) + 0.6 * off_eighth + 0.3 * sixteenth - 0.5 * on_beat
    if rhythm == "driving":
        return even + 0.3 * (onsets[0] == 0) - 0.4 * sixteenth
    if rhythm == "long":
        return min(gaps) / 4 + 0.5 * even - sixteenth
    return 0.0


# ── Arrangement ─────────────────────────────────────────────────────────────────
# Was im Stil zusätzlich oder nicht spielt: {Sektion: {Instrument: Spielweise oder None}}, über StyleProfile.parts
ARRANGEMENT = {
    "J-Pop Energy": {
        "Verse:2": {"counter": None, "guitar": "strummed"},
        "Bridge": {"synth": None, "bells": None, "choir": None, "piano": "ballad_arp"},
    },
    "Dark Vocaloid": {
        "Verse": {"strings": "staccato"},
        "Chorus:last": {"bells": None, "choir": "aahs"},
        "Bridge": {"bells": None, "synth": None, "piano": "arpeggio16"},
        "Drop": {"piano": "arpeggio16", "strings": "staccato"},
        "breakdown": {"piano": "arpeggio16", "choir": "oohs", "strings": None},
    },
    "Kawaii Chiptune": {
        "PreChorus": {"strings": None, "bells": "sparkle16"},
        "Chorus": {"strings": None, "brass": None, "bells": "sparkle16", "counter": "answer"},
        "Chorus:last": {"choir": None},
        "Bridge": {"bells": "sparkle16"},
        "Build-up": {"strings": None},
    },
    # Rock: Pre-Chorus abgedämpft, damit der Refrain mit Powerchords aufgeht; die zweite Strophe spielt ein Riff
    # ohne Gegenstimme, in der Bridge das Gitarrensolo über Powerchords
    "Rock": {
        "PreChorus": {"guitar": "palm_mute"},
        "Verse:2": {"counter": None, "guitar": "chill_riff"},
        "Bridge": {"guitar": "power_chords", "bass": "driving"},
    },
    "Ballade": {
        "Chorus": {"guitar": None, "synth": None, "perc": None, "bells": None},
        "Chorus:2": {"brass": None},
        "Verse:2": {"synth": None},
        "Bridge": {"synth": None, "brass": None, "choir": None},
    },
    "City Pop": {
        "Chorus": {"bells": None, "choir": None},
        "Chorus:last": {"choir": None, "brass": "stabs"},
        "Verse:2": {"perc": "congas", "brass": "stabs"},
        "Bridge": {"bells": None},
    },
    "Future Bass": {
        "Chorus": {"choir": None, "counter": None},
        "PreChorus": {"choir": None},
        "Verse:2": {"bells": None},
    },
    "Drum and Bass": {
        "Chorus": {"choir": None, "bells": None, "counter": None},
        "Verse:2": {"counter": None},
        "Bridge": {"strings": "legato", "piano": None},
    },
    "Lo-Fi": {
        "Chorus": {"bells": None},
        "Chorus:last": {"strings": None},
        "Bridge": {"counter": "guide"},
    },
    "Idol-Pop": {
        "Bridge": {"synth": None},
        "Verse:2": {"perc": "claps+tambourine"},
    },
    "Wafuu-Rock": {
        "Verse:2": {"perc": "taiko"},
        "Bridge": {"guitar": None, "perc": None},
    },
    "Electro-Swing": {
        "Chorus:2": {"strings": "pizzicato"},
    },
    "Hyperpop": {
        "Bridge": {"guitar": None, "counter": None},
    },
}


def arranged(parts: dict, style: str) -> dict:
    """parts eines StyleProfile mit dem Arrangement des Stils: Instrumente kommen dazu oder fallen weg (None)."""
    changes = ARRANGEMENT.get(style)
    if not changes:
        return parts
    out = {section: dict(p) for section, p in parts.items()}
    for section, insts in changes.items():
        # eine Sektion, die der Stil nicht eigens besetzt, spielt wie die Strophe (StyleProfile.part)
        whole = ":" not in section and section != "breakdown"
        target = out.setdefault(section, dict(parts.get("Verse", {})) if whole else {})
        for inst, pattern in insts.items():
            target[inst] = pattern            # None nimmt es auch dann heraus, wenn „Verse:2“ es sonst ergänzt
    return out


# ── J-Pop Energy und Idol-Pop getrennt (1.5.0, C1) ──────────────────────────────
# Bis 1.4 lagen die beiden in der Messung am nächsten beieinander. Mit dem Schalter ist J-Pop Energy die Anison-Band:
# Gitarrenriff in der Strophe, Powerchords in Intro, Refrain und Outro, die Hook auf der Lead-Gitarre, Rock-Grooves,
# kein Klavier außer in der Bridge, keine Glitzer-Glocken und eigene Akkorde (SPLIT_PROGRESSIONS). Idol-Pop bleibt
# Tanz-Pop mit Royal Road und Four-on-the-floor, jetzt mit Disco-Oktaven im Bass, Synth-Bläsern und Rufen wie aus
# dem Publikum („Hai! Hai!“) vor dem Refrain.
SPLIT_PARTS = {
    "J-Pop Energy": {
        "Intro": {"guitar": "power_chords", "piano": None, "bells": None},
        "Verse": {"guitar": "riff", "piano": None},
        "Verse:2": {"guitar": "riff"},
        "PreChorus": {"guitar": "palm_mute", "piano": None, "choir": None},
        "Chorus": {"guitar": "power_chords", "piano": None, "bells": None, "synth": "supersaw"},
        "Outro": {"guitar": "power_chords", "piano": None, "bells": None},
        "Bridge": {"guitar": "chill_riff"},
    },
    "Idol-Pop": {
        "PreChorus": {"choir": "calls"},
        "Chorus": {"bass": "octaves"},                  # Disco-Oktaven zum Four-on-the-floor
        "Chorus:last": {"choir": "aahs+calls"},
    },
}
SPLIT_GROOVES = {
    "J-Pop Energy": {"Intro": "rock_chorus", "Verse": "rock_verse", "Chorus": "rock_chorus", "Outro": "rock_chorus"},
}
SPLIT_PROGRAMS = {"J-Pop Energy": {"melody": 30}, "Idol-Pop": {"brass": 62}}    # Lead-Gitarre, Synth-Bläser
SPLIT_WITHOUT_VOICES = {"J-Pop Energy": ("melody",)}  # die Hook spielt die Gitarre, nicht der Synth-Lead


def split(profile):
    """Das StyleProfile mit der Trennung von J-Pop Energy und Idol-Pop; andere Stile bleiben, wie sie sind."""
    from dataclasses import replace
    name = profile.name
    if name not in SPLIT_PARTS:
        return profile
    parts = {section: dict(p) for section, p in profile.parts.items()}
    for section, insts in SPLIT_PARTS[name].items():
        parts.setdefault(section, {}).update(insts)      # None nimmt ein Instrument heraus (StyleProfile.part)
    voices = {inst: v for inst, v in profile.voices.items() if inst not in SPLIT_WITHOUT_VOICES.get(name, ())}
    return replace(profile, parts=parts, grooves={**profile.grooves, **SPLIT_GROOVES.get(name, {})},
                   programs={**profile.programs, **SPLIT_PROGRAMS.get(name, {})}, voices=voices)


# ── Zwei Stile mischen (1.5.0, C4) ──────────────────────────────────────────────
# Etwa 70 % Rock und 30 % Kawaii Chiptune: ein Teil der Instrumente spielt mit Klang und Spielweisen des zweiten
# Stils, ein Teil der Sektionen mit seinem Groove, und ein Teil der Akkordfolgen kommt aus ihm (song_plan.build_plan).
# Wie viele, entscheidet der Anteil; welche, der Seed des Songs. Gesang, Melodie und Klangbild bleiben beim ersten Stil.
BLEND_PARTS = ("piano", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "melody", "bass", "perc")


def blend(profile, other, share: float, seed: str):
    """profile mit share Anteil von other (beides StyleProfile). Rückgabe: (StyleProfile, [Instrumente aus other],
    [Sektionen mit dem Groove von other])."""
    import random
    from dataclasses import replace
    rng = random.Random(f"{seed}:blend:{other.name}")
    # Kandidaten: was der zweite Stil im Refrain spielt; mindestens ein Instrument kommt immer aus ihm
    played = [inst for inst in BLEND_PARTS if other.parts.get("Chorus", {}).get(inst)]
    count = max(1, round(share * len(BLEND_PARTS)))
    taken = sorted(rng.sample(played, min(count, len(played))), key=BLEND_PARTS.index)
    parts = {section: dict(p) for section, p in profile.parts.items()}
    for section in set(parts) | set(other.parts):
        target = parts.setdefault(section, {} if ":" in section or section == "breakdown"
                                  else dict(profile.parts.get("Verse", {})))
        theirs = other.parts.get(section)
        if theirs is None and ":" not in section and section != "breakdown":
            theirs = other.parts.get("Verse", {})          # eine Sektion ohne eigene Besetzung spielt wie die Strophe
        for inst in taken:
            if theirs is not None and inst in theirs:
                target[inst] = theirs[inst]
            elif ":" in section:
                target.pop(inst, None)                     # die Ergänzung des ersten Stils gilt nicht mehr
            else:
                target[inst] = None
    programs = {**profile.programs, **{inst: other.programs[inst] for inst in taken if inst in other.programs}}
    voices = {inst: v for inst, v in profile.voices.items() if inst not in taken}
    voices.update({inst: dict(other.voices[inst]) for inst in taken if inst in other.voices})
    grooves = dict(profile.grooves)
    moved = [section for section in sorted(set(profile.grooves) | set(other.grooves))
             if other.grooves.get(section) and rng.random() < share]
    for section in moved:
        grooves[section] = other.grooves[section]
    return replace(profile, parts=parts, programs=programs, voices=voices, grooves=grooves), taken, moved


# ── Klangbild ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Sound:
    room: float = 0.78             # Größe des gemeinsamen Halls (Pedalboard Reverb room_size)
    damping: float = 0.45          # mehr = dunklerer Hall
    hall_lowpass: float = 9000.0
    predelay: float = 0.0          # Sekunden, bevor der Hall einsetzt
    hall_gain: float = 1.0         # so viel lauter oder leiser als bisher
    delay_beats: float = 0.75      # Gesangs-Delay: punktierte Achtel, Achtel (0.5), Viertel (1.0)
    delay_feedback: float = 0.3
    delay_lowpass: float = 6000.0
    low_db: float = 0.0            # Klangfarbe des Masters: Tiefen (Shelf bei 110 Hz)
    mid_db: float = 0.0            # Mitten (Glocke bei mid_hz)
    mid_hz: float = 1500.0
    high_db: float = 0.0           # Höhen (Shelf bei 9 kHz)
    width: float = 1.0             # Stereobreite der Band (Seiten-Anteil)
    drive: float = 0.0             # Sättigung der Band (0 bis 1)
    describe_as: str = ""

    def describe(self) -> str:
        return (f"{self.describe_as}: Raum {self.room:.2f}, Delay {self.delay_beats:g} Schläge, Tiefen "
                f"{self.low_db:+.1f} dB, Mitten {self.mid_db:+.1f} dB, Höhen {self.high_db:+.1f} dB, Breite "
                f"{self.width:.0%}, Sättigung {self.drive:.0%}")


STYLE_SOUNDS = {
    "J-Pop Energy": Sound(room=0.7, damping=0.45, delay_beats=0.75, low_db=0.5, mid_db=1.0, mid_hz=1500.0,
                          high_db=0.5, width=1.05, drive=0.25, describe_as="Band mit Biss"),
    "Dark Vocaloid": Sound(room=0.86, damping=0.6, hall_lowpass=7000.0, predelay=0.02, delay_beats=0.75,
                           delay_feedback=0.38, delay_lowpass=4500.0, low_db=1.5, mid_db=-1.0, mid_hz=900.0,
                           high_db=-0.5, width=1.15, drive=0.25, describe_as="dunkel und groß"),
    "Kawaii Chiptune": Sound(room=0.45, damping=0.2, hall_lowpass=12000.0, hall_gain=0.7, delay_beats=0.5,
                             delay_feedback=0.25, delay_lowpass=9000.0, high_db=2.0, mid_db=0.5, mid_hz=2500.0,
                             width=1.2, describe_as="glitzernd und eng"),
    "Rock": Sound(room=0.4, damping=0.5, hall_lowpass=8000.0, hall_gain=0.7, delay_beats=0.5, delay_feedback=0.2,
                  low_db=0.5, mid_db=1.5, mid_hz=1800.0, width=0.95, drive=0.35, describe_as="trocken und nach vorn"),
    "Ballade": Sound(room=0.92, damping=0.35, hall_lowpass=10000.0, predelay=0.04, hall_gain=1.35,
                     delay_beats=1.0, delay_feedback=0.35, delay_lowpass=5000.0, low_db=0.5, high_db=0.5,
                     width=1.15, describe_as="weit und weich"),
    "City Pop": Sound(room=0.6, damping=0.3, hall_lowpass=11000.0, predelay=0.015, delay_beats=0.75,
                      delay_feedback=0.25, low_db=1.0, mid_db=-0.5, mid_hz=500.0, high_db=1.5, width=1.1, drive=0.1,
                      describe_as="glänzend wie die 80er"),
    "Future Bass": Sound(room=0.85, damping=0.25, hall_lowpass=12000.0, predelay=0.02, hall_gain=1.15,
                         delay_beats=0.75, delay_feedback=0.4, delay_lowpass=8000.0, low_db=2.0, high_db=1.5,
                         width=1.3, describe_as="riesig und breit"),
    "Drum and Bass": Sound(room=0.55, damping=0.5, hall_gain=0.8, delay_beats=0.5, delay_feedback=0.3,
                           delay_lowpass=7000.0, low_db=2.0, mid_db=-1.0, mid_hz=600.0, high_db=1.5, width=1.15,
                           describe_as="tiefer Sub, klare Höhen"),
    "Lo-Fi": Sound(room=0.35, damping=0.75, hall_lowpass=5500.0, hall_gain=0.8, delay_beats=1.0,
                   delay_feedback=0.35, delay_lowpass=3500.0, low_db=1.0, mid_db=0.5, mid_hz=400.0, high_db=-2.0,
                   width=0.85, drive=0.3, describe_as="klein, warm und dumpf"),
    "Idol-Pop": Sound(room=0.72, damping=0.25, hall_lowpass=12000.0, predelay=0.015, delay_beats=0.5,
                      delay_feedback=0.25, delay_lowpass=8000.0, low_db=1.0, mid_db=-0.5, mid_hz=700.0, high_db=2.0,
                      width=1.25, describe_as="poliert und strahlend"),
    "Wafuu-Rock": Sound(room=0.66, damping=0.45, hall_lowpass=9000.0, predelay=0.02, delay_beats=0.75,
                        delay_feedback=0.3, low_db=1.0, mid_db=1.0, mid_hz=2200.0, high_db=0.5, width=1.1, drive=0.35,
                        describe_as="Halle eines Schreins, Gitarren vorn"),
    "Electro-Swing": Sound(room=0.5, damping=0.5, hall_lowpass=8500.0, predelay=0.01, hall_gain=0.85,
                           delay_beats=0.5, delay_feedback=0.25, delay_lowpass=5000.0, low_db=2.0, mid_db=1.0,
                           mid_hz=1000.0, high_db=-0.5, width=0.95, drive=0.25, describe_as="Shellack-Mitten, Club-Bass"),
    "Hyperpop": Sound(room=0.6, damping=0.2, hall_lowpass=13000.0, hall_gain=0.8, delay_beats=0.5,
                      delay_feedback=0.35, delay_lowpass=10000.0, low_db=2.5, mid_db=0.5, mid_hz=3000.0, high_db=2.5,
                      width=1.35, drive=0.45, describe_as="zu laut, zu hell, zu breit (Absicht)"),
}

SOUNDS = STYLE_SOUNDS            # die Tests schalten es hier ab (conftest.py)


def sound(style: str) -> Optional[Sound]:
    return SOUNDS.get(style)

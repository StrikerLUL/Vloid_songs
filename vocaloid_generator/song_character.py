# song_character.py – Jeder Song bekommt ein eigenes Gesicht (1.4.0)
#
# Zwei Songs im selben Stil hatten bis 1.3 dieselben Klänge, dieselben Grooves und dieselben Spielweisen; nur die Töne
# waren andere. Jetzt würfelt jeder Song aus seinem Seed, innerhalb dessen, was zum Stil passt: den Klang von Klavier,
# Gitarre, Lead, Glocken und Gegenstimme, die eigenen Synth-Stimmen, den Groove von Strophe und Refrain, die
# Spielweise von Bass, Klavier und Gitarre, wie das Intro beginnt (volle Band, leise, Schlagzeug und Bass, nur die
# Hook) und wie der Song endet (Schlussakkord klingt aus, harter Stopp, wird leiser). Was gewürfelt wurde, steht im
# Protokoll („Charakter: …“).
import logging
import random
from dataclasses import dataclass, field, replace

log = logging.getLogger(__name__)

# Klänge (General MIDI), die im Stil passen; der erste ist der des Stils
PROGRAMS = {
    # J-Pop Energy ist die Anison-Band (verzerrte Gitarren, Streicher), Idol-Pop der Tanz-Pop (cleane Gitarre, Bläser)
    "J-Pop Energy": {"piano": [0, 1], "guitar": [29, 30], "bells": [9, 10], "counter": [48, 40, 73],
                     "brass": [61, 62]},
    "Dark Vocaloid": {"piano": [0, 6, 1], "guitar": [30, 29], "melody": [30, 29, 40, 6], "bells": [10, 14, 8],
                      "counter": [40, 42, 71], "strings": [48, 49]},
    "Kawaii Chiptune": {"piano": [8, 11, 4], "bells": [9, 8, 13], "brass": [62, 61]},
    "Rock": {"guitar": [30, 29], "melody": [29, 30], "counter": [29, 30]},
    "Ballade": {"piano": [0, 1], "guitar": [25, 24], "melody": [73, 71, 68, 40, 0], "bells": [8, 10, 11],
                "counter": [42, 40, 73, 71], "strings": [49, 48]},
    "City Pop": {"piano": [5, 4, 2], "guitar": [27, 28], "melody": [65, 66, 56, 11], "bells": [11, 8],
                 "counter": [66, 65, 56, 11], "brass": [61, 56, 62]},
    "Future Bass": {"piano": [0, 4], "bells": [9, 8, 10]},
    "Drum and Bass": {"piano": [4, 5, 0], "melody": [81, 11, 89], "counter": [73, 11, 4], "bells": [11, 9]},
    "Lo-Fi": {"piano": [4, 0, 5], "guitar": [26, 24, 27], "melody": [11, 4, 26, 73], "counter": [73, 65, 26],
              "bells": [11, 10]},
    "Idol-Pop": {"piano": [1, 4, 5], "guitar": [27, 28], "bells": [9, 8, 13], "counter": [61, 56, 62],
                 "brass": [61, 62]},
}
# Eigene Synth-Stimmen (synth_engine.VOICES) je Unterspur: {Instrument: {Unterspur: [Stimmen]}}
VOICES = {
    "J-Pop Energy": {"synth": {"": ["pluck", "chip"], "saw": ["supersaw", "fb_chord"]},
                     "melody": {"": ["lead", "pluck", "chip"]}},
    "Kawaii Chiptune": {"synth": {"saw": ["supersaw", "fb_chord"]}},
    "Future Bass": {"synth": {"": ["pluck", "chip"], "saw": ["fb_chord", "supersaw"]}, "bass": {"": ["sub", "reese"]},
                    "melody": {"": ["lead", "pluck"]}},
    "Drum and Bass": {"bass": {"": ["reese", "sub"]}, "synth": {"": ["pluck", "chip"]}},
    "Idol-Pop": {"synth": {"": ["pluck", "chip"], "saw": ["supersaw", "fb_chord"]}, "melody": {"": ["lead", "chip"]}},
}
# Grooves (drums.GROOVES), die im Stil passen: {Sektion: [Grooves]}
GROOVES = {
    "J-Pop Energy": {"Verse": ["pop_verse", "rock_verse", "tom_verse"],
                     "Chorus": ["pop_chorus", "rock_chorus", "two_beat"]},
    "Dark Vocaloid": {"Verse": ["rock_verse", "pop_verse", "tom_verse"],
                      "Chorus": ["double_kick", "rock_chorus", "four_floor"]},
    "Kawaii Chiptune": {"Verse": ["edm_verse", "idol_verse", "pop_verse"],
                        "Chorus": ["four_floor", "pop_chorus", "disco"]},
    "Rock": {"Verse": ["rock_verse", "tom_verse", "pop_verse"], "Chorus": ["rock_chorus", "two_beat", "double_kick"]},
    "Ballade": {"Verse": ["ballad_light", "lofi_light"], "Chorus": ["ballad", "halftime"]},
    "City Pop": {"Verse": ["citypop", "disco"], "Chorus": ["citypop", "disco", "pop_chorus"]},
    "Future Bass": {"Verse": ["fb_verse", "halftime"], "Chorus": ["fb_chorus", "four_floor"]},
    "Drum and Bass": {"Verse": ["dnb_verse", "halftime"]},
    "Lo-Fi": {"Verse": ["lofi", "lofi_light"]},
    "Idol-Pop": {"Verse": ["idol_verse", "edm_verse"], "Chorus": ["four_floor", "disco"]},
}
# Spielweisen (parts.PARTS): {Sektion: {Instrument: [Spielweisen]}}; nur wo der Stil das Instrument schon spielt
PATTERNS = {
    "J-Pop Energy": {"Verse": {"bass": ["sync", "driving", "octaves"], "piano": ["arpeggio", "stabs", "chords"],
                               "guitar": ["palm_mute", "cutting", "chill_riff"]},
                     "Chorus": {"bass": ["driving", "octaves", "sync"], "piano": ["eighths", "chords", "stabs"],
                                "guitar": ["strummed", "power_chords"]}},
    "Dark Vocaloid": {"Verse": {"bass": ["sync", "driving"], "piano": ["arpeggio16", "arpeggio", "stabs"],
                                "guitar": ["palm_mute", "chill_riff"]},
                      "Chorus": {"bass": ["driving", "octaves"], "piano": ["arpeggio16", "chords"]}},
    "Kawaii Chiptune": {"Verse": {"bass": ["sub_pulse", "octaves", "sync"], "piano": ["stabs", "eighths", "arpeggio"]},
                        "Chorus": {"bass": ["wobble", "octaves", "sub_pulse"], "piano": ["eighths", "stabs"]}},
    "Rock": {"Verse": {"bass": ["driving", "sync", "root"], "guitar": ["palm_mute", "chill_riff", "strummed"]},
             "Chorus": {"bass": ["driving", "octaves"], "guitar": ["power_chords", "strummed"]}},
    "Ballade": {"Verse": {"piano": ["ballad_arp", "arpeggio", "chords"]},
                "Chorus": {"piano": ["chords", "ballad_arp"]}},
    "City Pop": {"Verse": {"bass": ["sync", "octaves", "lazy"], "guitar": ["cutting", "chill_riff"]},
                 "Chorus": {"bass": ["octaves", "sync"]}},
    "Future Bass": {"Verse": {"bass": ["root", "sync"], "piano": ["chords", "arpeggio"]},
                    "Chorus": {"bass": ["sync", "root"]}},
    "Drum and Bass": {"Verse": {"piano": ["arpeggio", "chords", "jazz_ch"]}},
    "Lo-Fi": {"Verse": {"bass": ["lazy", "root"], "piano": ["jazz_ch", "ballad_arp"]}},
    "Idol-Pop": {"Verse": {"bass": ["sync", "octaves", "driving"], "piano": ["stabs", "eighths", "arpeggio"],
                           "guitar": ["cutting", "palm_mute", "strummed"]},
                 "Chorus": {"bass": ["driving", "octaves"], "piano": ["eighths", "stabs", "chords"],
                            "guitar": ["strummed", "cutting"]}},
}
# Wie das Intro beginnt und wie der Song endet, mit Gewichten je Stil
INTROS = ("full", "quiet", "drums", "hook")
ENDINGS = ("ring", "stop", "fade")
INTRO_WEIGHTS = {"Ballade": (1, 4, 0, 2), "Lo-Fi": (2, 3, 1, 1), "Rock": (3, 0, 3, 1), "Drum and Bass": (2, 2, 2, 1),
                 "Dark Vocaloid": (3, 2, 2, 2), "City Pop": (3, 1, 2, 1)}
ENDING_WEIGHTS = {"Ballade": (4, 0, 2), "Lo-Fi": (2, 0, 3), "Rock": (2, 3, 0), "Dark Vocaloid": (2, 3, 1),
                  "Idol-Pop": (2, 3, 1), "Kawaii Chiptune": (2, 3, 1), "City Pop": (2, 1, 3)}
DEFAULT_INTRO, DEFAULT_ENDING = (3, 1, 1, 2), (3, 2, 1)
INTRO_NAMES = {"full": "volle Band", "quiet": "leise", "drums": "Schlagzeug und Bass", "hook": "nur die Hook"}
ENDING_NAMES = {"ring": "Schlussakkord klingt aus", "stop": "harter Stopp", "fade": "wird leiser"}
# Für das Protokoll: die Namen der Klänge (General MIDI) und Instrumente
SOUND_NAMES = {0: "Flügel", 1: "helles Klavier", 2: "E-Flügel", 4: "Rhodes", 5: "FM-Piano", 6: "Cembalo",
               8: "Celesta", 9: "Glockenspiel", 10: "Spieluhr", 11: "Vibraphon", 13: "Xylophon", 14: "Röhrenglocken",
               24: "Nylongitarre", 25: "Westerngitarre", 26: "Jazzgitarre", 27: "cleane E-Gitarre",
               28: "gedämpfte E-Gitarre", 29: "Overdrive-Gitarre", 30: "Distortion-Gitarre", 40: "Violine",
               42: "Cello", 48: "Streicher", 49: "weiche Streicher", 56: "Trompete", 61: "Bläsersatz",
               62: "Synth-Bläser", 65: "Altsax", 66: "Tenorsax", 68: "Oboe", 71: "Klarinette", 73: "Flöte",
               81: "Saw-Lead", 89: "warme Fläche"}
PART_NAMES = {"piano": "Klavier", "guitar": "Gitarre", "melody": "Lead", "bells": "Glocken", "counter": "Gegenstimme",
              "brass": "Bläser", "strings": "Streicher", "synth": "Synth", "bass": "Bass"}
SECTION_NAMES = {"Verse": "Strophe", "Chorus": "Refrain"}
FADE_TO = 0.35            # so leise (Anteil der Anschlagstärke) spielt die Band am Ende eines leiser werdenden Outros
STOP_BEATS = 0.6          # so lange klingt der Schlussakkord bei einem harten Stopp


@dataclass(frozen=True)
class Character:
    programs: dict = field(default_factory=dict)     # Instrument → Klang
    voices: dict = field(default_factory=dict)       # Instrument → {Unterspur: Synth-Stimme}, alle des Songs
    grooves: dict = field(default_factory=dict)      # Sektion → Groove
    patterns: dict = field(default_factory=dict)     # Sektion → {Instrument: Spielweise}
    intro: str = "full"
    ending: str = "ring"

    def describe(self) -> str:
        def part(inst: str) -> str:
            return PART_NAMES.get(inst, inst)

        def section(sec: str) -> str:
            return SECTION_NAMES.get(sec, sec)
        bits = [f"{part(inst)} {SOUND_NAMES.get(program, f'Klang {program}')}"
                for inst, program in sorted(self.programs.items())]
        bits += [f"{part(inst)}{f' ({layer})' if layer else ''} {voice}" for inst, layers in sorted(self.voices.items())
                 for layer, voice in sorted(layers.items())]
        bits += [f"Groove {section(sec)} {groove}" for sec, groove in sorted(self.grooves.items())]
        bits += [f"{part(inst)} {section(sec)} {pattern}" for sec, insts in sorted(self.patterns.items())
                 for inst, pattern in sorted(insts.items())]
        bits += [f"Intro {INTRO_NAMES[self.intro]}", f"Schluss {ENDING_NAMES[self.ending]}"]
        return ", ".join(bits)


def choose(style: str, seed: str) -> Character:
    """Der Charakter eines Songs in diesem Stil; derselbe Seed gibt denselben Charakter."""
    rng = random.Random(f"{seed}:{style}")
    programs = {inst: rng.choice(pool) for inst, pool in sorted(PROGRAMS.get(style, {}).items())}
    voices = {inst: {layer: rng.choice(pool) for layer, pool in sorted(layers.items())}
              for inst, layers in sorted(VOICES.get(style, {}).items())}
    grooves = {sec: rng.choice(pool) for sec, pool in sorted(GROOVES.get(style, {}).items())}
    patterns = {sec: {inst: rng.choice(pool) for inst, pool in sorted(insts.items())}
                for sec, insts in sorted(PATTERNS.get(style, {}).items())}
    intro = rng.choices(INTROS, INTRO_WEIGHTS.get(style, DEFAULT_INTRO))[0]
    ending = rng.choices(ENDINGS, ENDING_WEIGHTS.get(style, DEFAULT_ENDING))[0]
    return Character(programs, voices, grooves, patterns, intro, ending)


def apply(profile, character: Character):
    """Das StyleProfile des Songs mit seinem Charakter: Klänge, Synth-Stimmen, Grooves, Spielweisen und Intro."""
    programs = {**profile.programs, **character.programs}
    voices = {inst: dict(layers) for inst, layers in profile.voices.items()}
    for inst, layers in character.voices.items():
        voices.setdefault(inst, {}).update(layers)
    grooves = dict(profile.grooves)
    for sec, groove in character.grooves.items():
        grooves[sec] = groove
        if sec == "Chorus" and profile.grooves.get("Outro") == profile.grooves.get("Chorus"):
            grooves["Outro"] = groove             # das Outro spielt wie der Refrain
    parts = {sec: dict(p) for sec, p in profile.parts.items()}
    for sec, insts in character.patterns.items():
        for inst, pattern in insts.items():
            if parts.get(sec, {}).get(inst):        # nur, was der Stil dort schon spielt
                parts[sec][inst] = pattern
    parts["Intro"], grooves["Intro"] = _intro(profile, parts, grooves, character.intro)
    return replace(profile, programs=programs, voices=voices, grooves=grooves, parts=parts)


def _intro(profile, parts: dict, grooves: dict, intro: str) -> tuple:
    """(Spielweisen, Groove) des Intros."""
    full, groove = dict(parts.get("Intro", {})), grooves.get("Intro")
    lead = {"melody": full["melody"]} if full.get("melody") else {"melody": "hook"}
    if intro == "quiet":
        quiet = {inst: p for inst, p in parts.get("breakdown", {}).items() if inst not in ("bells", "choir")}
        return {**(quiet or {"piano": "arpeggio"}), **lead}, None
    if intro == "drums":
        bass = full.get("bass") or parts.get("Verse", {}).get("bass") or "root"
        kept = {inst: p for inst, p in full.items() if inst in ("perc", "guitar")}
        return {"bass": bass, **kept, **lead}, groove or grooves.get("Verse")
    if intro == "hook":
        bed = parts.get("Bridge", {}).get("synth") == "pad" or "pad" in str(profile.parts.get("breakdown", {}))
        return {**({"synth": "pad"} if bed else {"strings": "legato"}), **lead}, None
    return full, groove


def finish(plan, events: dict, character: Character, drum_tracks: tuple) -> str:
    """Der Schluss des Songs nach dem Charakter (nach orchestrator._final_chord). Rückgabe: was geändert wurde, leer
    wenn nichts."""
    last = plan.sections[-1]
    if last.kind not in ("Outro", "Chorus") or character.ending == "ring":
        return ""
    downbeat = last.end - last.bar_beats
    if character.ending == "stop":
        for inst, evs in events.items():
            for e in evs:
                if abs(e.start - downbeat) <= 0.02 and inst not in drum_tracks:
                    e.dur = min(e.dur, STOP_BEATS)
        return "harter Stopp"
    span = max(last.end - last.start, 1.0)
    for inst, evs in events.items():
        for e in evs:
            if e.start >= last.start:
                share = 1.0 - (1.0 - FADE_TO) * min(1.0, (e.start - last.start) / span)
                e.vel = max(1, int(round(e.vel * share)))
    return "wird leiser"

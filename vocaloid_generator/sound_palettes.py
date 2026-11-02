"""Kuratiert zusammenpassende Besetzungen. Jedes Set wird als Ganzes gewählt."""
from copy import deepcopy


def _set(name, programs, voices=None):
    return {"name": name, "programs": programs, "voices": voices or {}}


PALETTES = {
    "J-Pop Energy": [_set("Anison-Band", {"piano": 0, "guitar": 29, "strings": 48, "counter": 40, "bells": 9},
                          {"synth": {"": "pluck", "saw": "supersaw"}}),
                     _set("Helle Rockband", {"piano": 1, "guitar": 30, "strings": 49, "counter": 48, "bells": 10},
                          {"synth": {"": "pluck", "saw": "supersaw"}})],
    "Rock": [_set("Warme Rockband", {"piano": 0, "guitar": 29, "melody": 29, "counter": 29}),
             _set("Dichte Rockband", {"piano": 1, "guitar": 30, "melody": 30, "counter": 30})],
    "Dark Vocaloid": [_set("Dunkle Streicherband", {"piano": 0, "guitar": 30, "melody": 40, "strings": 48,
                                                 "counter": 42, "bells": 14}),
                      _set("Dunkles Klavier", {"piano": 0, "guitar": 29, "melody": 0, "strings": 49,
                                              "counter": 40, "bells": 10})],
    "Ballade": [_set("Klavier und Cello", {"piano": 0, "guitar": 24, "strings": 49, "counter": 42,
                                          "melody": 40, "bells": 8}),
                _set("Akustische Ballade", {"piano": 0, "guitar": 25, "strings": 49, "counter": 73,
                                           "melody": 73, "bells": 11})],
    "City Pop": [_set("Rhodes und Saxofon", {"piano": 4, "guitar": 27, "melody": 66, "counter": 65,
                                            "brass": 61, "bells": 11}),
                 _set("FM und Funkgitarre", {"piano": 5, "guitar": 28, "melody": 65, "counter": 66,
                                            "brass": 56, "bells": 11})],
    "Lo-Fi": [_set("Weiches Rhodes", {"piano": 4, "guitar": 26, "counter": 73, "melody": 11, "bells": 11}),
              _set("Staubiges Klavier", {"piano": 0, "guitar": 24, "counter": 71, "melody": 4, "bells": 10})],
    "Kawaii Chiptune": [_set("Spieluhr und Chip", {"piano": 8, "bells": 10, "brass": 62},
                            {"synth": {"": "chip", "saw": "supersaw"}, "melody": {"": "chip"}})],
    "Future Bass": [_set("Warme Future-Bass-Flächen", {"piano": 0, "bells": 9},
                         {"bass": {"": "sub"}, "synth": {"": "pluck", "saw": "fb_chord"},
                          "melody": {"": "lead"}})],
    "Drum and Bass": [_set("Liquid", {"piano": 4, "melody": 89, "counter": 73, "bells": 11},
                           {"bass": {"": "reese"}, "synth": {"": "pluck"}})],
    "Idol-Pop": [_set("Heller Dance-Pop", {"piano": 5, "guitar": 27, "bells": 9, "brass": 62, "counter": 61},
                      {"synth": {"": "pluck", "saw": "supersaw"}, "melody": {"": "lead"}})],
    "Wafuu-Rock": [_set("Koto und Shakuhachi", {"piano": 107, "guitar": 29, "melody": 77,
                                              "counter": 106, "bells": 107}),
                   _set("Harfe und Flöte", {"piano": 46, "guitar": 29, "melody": 73,
                                            "counter": 107, "bells": 108})],
    "Electro-Swing": [_set("Swing-Quartett", {"piano": 0, "melody": 59, "counter": 66, "brass": 61}),
                      _set("Swing mit Klarinette", {"piano": 0, "melody": 71, "counter": 65, "brass": 56})],
    "Hyperpop": [_set("Gläserner Hyperpop", {"piano": 8, "guitar": 30, "bells": 9},
                      {"bass": {"": "reese"}, "synth": {"": "chip", "saw": "supersaw"},
                       "melody": {"": "chip"}})],
}


def choose(style, rng, taste=None):
    from geschmack import pick
    options = PALETTES.get(style, [])
    return deepcopy(pick(rng, options, taste, lambda s: ("palette", style, s["name"]))) if options else None

# qualitaet.py – Qualität und Länge für die einfache Ansicht (1.6.0)
#
# In der einfachen Ansicht gibt es statt 130 Schaltern drei Stufen. Eine Stufe schaltet nur ab, was sie langsamer
# machen würde, und schaltet nie etwas ein, das du (oder das Hör-Duell) ausgeschaltet hast; nur „Beste“ lässt NEUTRINO
# zweimal singen. Die Schalter selbst bleiben unverändert: In der Profi-Ansicht gilt wieder genau, was dort steht.
from typing import Optional

PRESETS = {
    "Schnell": {"best_melody": False, "amp_models": False, "hearing_check": False, "polish": False,
                "ai_backgrounds": False, "ai_accompaniment": False, "ai_melody": False, "vocal_takes": 1,
                "group_vocals": 0},
    "Gut": {"polish": False, "ai_accompaniment": False, "ai_melody": False, "vocal_takes": 1},
    "Beste": {"vocal_takes": 2},
}
DESCRIPTIONS = {
    "Schnell": "ohne die langsamen Teile: keine Suche nach der besten Melodie, Gitarren ohne Verstärker-Modell, "
               "kein Hör-Check",
    "Gut": "alles, was an ist, NEUTRINO singt einmal, ohne Klang-Veredler und KI-Versuche",
    "Beste": "alles, was an ist, NEUTRINO singt zweimal und aus jeder Phrase zählt die sauberste Fassung",
}
LENGTHS = {
    "Kurz": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "Chorus", "Outro"],
    "Normal": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"],
    "Lang": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "PreChorus", "Chorus",
             "Chorus", "Outro"],
}


def overrides(settings, quality: Optional[str] = None) -> dict:
    """Was die Stufe an den Einstellungen ändert: Schalter nur aus, Fassungen wie die Stufe sagt."""
    preset = PRESETS[quality or settings.quality]
    out = {}
    for field, value in preset.items():
        current = getattr(settings, field)
        if isinstance(current, bool):
            new = current and value
        elif field == "vocal_takes" and value > 1:
            new = max(current, value)
        else:
            new = min(current, value)
        if new != current:
            out[field] = new
    return out


def apply(settings, quality: Optional[str] = None):
    """Die Einstellungen für einen Lauf in dieser Stufe."""
    found = overrides(settings, quality)
    return settings.with_updates(**found) if found else settings


def length_of(sections: list) -> str:
    """Welche Länge ein Ablauf ist; „“, wenn er eigen ist."""
    return next((name for name, order in LENGTHS.items() if list(sections) == order), "")

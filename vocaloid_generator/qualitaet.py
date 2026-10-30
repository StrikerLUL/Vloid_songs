# qualitaet.py – Die Qualitätsstufen der einfachen Ansicht (1.6.0)
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
    "Gut": "alles, was an ist, die Stimme singt einmal, ohne Klang-Veredler und KI-Versuche",
    "Beste": "alles, was an ist, die Stimme singt zweimal und aus jeder Phrase zählt die sauberste Fassung",
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

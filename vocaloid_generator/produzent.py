# produzent.py – Dein Produzentenstil (1.5.0, C2)
#
# Ein Profil, das über alle Songs gleich bleibt, auch über das Album über Nacht (Tab Band › Dein Produzentenstil):
# - Name: steht im Abspann des Videos, in der YouTube-Beschreibung und als Künstler der MP3 („Name feat. MERROW“).
# - Producer-Tag: vier Töne am Anfang jedes Songs, die aus deinem Namen entstehen. Sie klingen in jedem Song gleich
#   (in dessen Tonart), wie die kurzen Erkennungsmelodien vor den Songs bekannter Produzenten.
# - Erkennungsklang: der Klang des Tags und der Glocken in jedem Song (Glockenspiel, Spieluhr, Vibraphon …); ohne
#   Auswahl entsteht er aus dem Namen.
# - Akkordwendung: deine typische Folge, die der Refrain in zwei von drei Songs spielt (Royal Road, Komuro, Kanon …).
# - Lieblingsstimme: singt in jedem Stil, für den im Stimmen-Casting keine eigene gemerkt ist (casting.favorite).
# Ohne Namen und ohne Auswahl ändert sich nichts.
import hashlib
import random
from dataclasses import dataclass
from typing import Optional

from theory import SCALES, is_minor

# Erkennungsklänge (General MIDI)
SOUNDS = {"Glockenspiel": 9, "Spieluhr": 10, "Celesta": 8, "Vibraphon": 11, "Marimba": 12, "Xylophon": 13,
          "Röhrenglocken": 14, "Kalimba": 108}
# Typische Akkordwendungen für den Refrain, in Dur und Moll
TURNS = {
    "Royal Road (IV–V–iii–vi)": {"major": "IVmaj7 | V7 | iii7 | vi", "minor": "bVImaj7 | bVII | v7 | i"},
    "Komuro (vi–IV–V–I)": {"major": "vi | IV | V | I", "minor": "i | bVI | bVII | bIII"},
    "Kanon (I–V–vi–iii–IV–I–IV–V)": {"major": "I | V | vi | iii | IV | I | IV | V",
                                     "minor": "i | v | bVI | bIII | iv | i | iv | V"},
    "Marusa (IVmaj7–III7–vi7–I7)": {"major": "IVmaj7 | III7 | vi7 | I7", "minor": "bVImaj7 | V7 | i7 | i7"},
    "Anlauf bVI–bVII–I": {"major": "IV | V | bVI bVII | I", "minor": "iv | v | bVI bVII | i"},
    "Just the Two of Us (IVmaj7–III7–vi7–v7 I7)": {"major": "IVmaj7 | III7 | vi7 | v7 I7",
                                                   "minor": "bVImaj7 | V7 | i7 | iv7"},
}
TURN_CHANCE = 2 / 3             # so oft spielt der Refrain die Wendung
# Rhythmen des Tags (Einsätze in Schlägen); der letzte Ton klingt einen Schlag
TAG_RHYTHMS = ((0.0, 0.5, 1.0, 1.5), (0.0, 0.25, 0.5, 1.0), (0.0, 0.75, 1.5, 2.0), (0.0, 0.5, 0.75, 1.0),
               (0.0, 0.25, 0.75, 1.5))
TAG_STEPS = (0, 2, 4, 7)        # Stufen der Tonleiter (Grundton, Terz, Quinte, Oktave), aus denen der Tag besteht
TAG_LOW = 72                    # der Grundton des Tags liegt in der Oktave darüber
TAG_VELOCITY = 92


@dataclass(frozen=True)
class Profile:
    name: str = ""
    sound: int = 0              # Erkennungsklang (General MIDI), 0 = keiner
    turn: str = ""              # Name aus TURNS
    tag: bool = False           # Producer-Tag am Anfang (nur mit Namen)

    def __bool__(self) -> bool:
        return bool(self.sound or self.turn or self.tag)


def _seed(name: str) -> int:
    return int(hashlib.sha1(name.strip().lower().encode("utf-8")).hexdigest()[:8], 16)


def profile(settings) -> Optional[Profile]:
    """Das Profil aus den Einstellungen; None, wenn es aus ist oder nichts darin steht."""
    if not settings.producer_profile:
        return None
    name = settings.producer_name.strip()
    sound = SOUNDS.get(settings.producer_sound, 0)
    if not sound and name:
        sound = list(SOUNDS.values())[_seed(name) % len(SOUNDS)]
    found = Profile(name=name, sound=sound, turn=settings.producer_turn if settings.producer_turn in TURNS else "",
                    tag=bool(name) and settings.producer_tag)
    return found or None


def name(settings) -> str:
    """Der Produzentenname für Abspann, Beschreibung und MP3; leer, wenn keiner gilt."""
    return settings.producer_name.strip() if settings is not None and settings.producer_profile else ""


def turn(found: Optional[Profile], mode: str, seed: str) -> str:
    """Die Akkordfolge des Refrains aus der Wendung, oder leer (in einem von drei Songs, oder ohne Wendung)."""
    if not found or not found.turn or random.Random(f"{seed}:producer-turn").random() >= TURN_CHANCE:
        return ""
    return TURNS[found.turn]["minor" if is_minor(mode) else "major"]


def motif(name: str) -> list:
    """[(Einsatz in Schlägen, Stufe in TAG_STEPS, Länge)]: der Tag, immer derselbe für denselben Namen."""
    rng = random.Random(_seed(name))
    rhythm = rng.choice(TAG_RHYTHMS)
    steps = [rng.choice(TAG_STEPS[:3])]
    for _ in range(2):
        steps.append(rng.choice([s for s in TAG_STEPS if s != steps[-1]]))
    steps.append(rng.choice([0, 7]))                  # er endet auf dem Grundton oder eine Oktave darüber
    if steps[-1] == steps[-2]:
        steps[-1] = 7 if steps[-1] == 0 else 0
    return [(at, step, 1.0 if k == 3 else min(0.45, rhythm[k + 1] - at)) for k, (at, step) in
            enumerate(zip(rhythm, steps))]


def tag_notes(found: Optional[Profile], tonic: int, mode: str) -> list:
    """[(Einsatz, Tonhöhe, Länge, Anschlag)] des Tags in der Tonart des Songs; leer ohne Tag."""
    if not found or not found.tag:
        return []
    scale = SCALES.get(mode, SCALES["minor"])
    base = TAG_LOW + (tonic - TAG_LOW) % 12
    return [(at, base + (12 if step >= 7 else scale[step]), length, TAG_VELOCITY)
            for at, step, length in motif(found.name)]

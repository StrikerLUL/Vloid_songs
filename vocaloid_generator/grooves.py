# grooves.py – Grooves und Fills von echten Schlagzeugern (Groove MIDI Dataset von Google Magenta, CC BY 4.0)
#
# setup_grooves.py lädt die Aufnahmen (MIDI von einem E-Drum-Set, gespielt von Profis zum Metronom) und legt die
# brauchbaren Takte in tools/grooves/grooves.json ab: Phrasen aus vier aufeinanderfolgenden Takten und Fills. Die
# Grooves der Stile Pop, Rock, Ballade, City Pop und Idol-Pop spielen dann statt der eingebauten Muster eine solche
# Phrase, mit dem Timing und der Dynamik des Schlagzeugers; ruhige Teile nehmen lockere Phrasen, Refrains dichte.
# Am Ende eines Teils spielt ein echter Fill. Jeder Groove eines Songs bleibt bei einer Phrase, wie bei einem
# Schlagzeuger, der seinen Strophen-Groove hat. Build-ups, Wirbel und elektronische Stile bleiben eingebaut.
import functools
import json
import logging
import os
import random
from typing import Optional

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "grooves")
LIBRARY = "grooves.json"
# eingebauter Groove → Stilrichtungen im Groove MIDI Dataset, die ihn ersetzen dürfen (die erste zählt am meisten)
FAMILIES = {
    "pop_verse": ("pop", "rock", "soul"), "pop_pre": ("pop", "rock", "funk"), "pop_chorus": ("rock", "pop", "punk"),
    "rock_verse": ("rock", "punk"), "rock_chorus": ("rock", "punk"), "ballad": ("soul", "pop", "rock"),
    "ballad_light": ("soul", "pop"), "citypop": ("funk", "soul", "pop"), "idol_verse": ("pop", "rock", "punk"),
    "halftime": ("rock", "hiphop", "pop"),
}
EXTRAS = (39, 54)               # Clap und Tamburin der eingebauten Grooves spielen weiter mit
TEMPO_RANGE = (0.8, 1.25)       # Phrasen aus diesem Tempo-Verhältnis klingen natürlich (sonst: alle)
FEEL = 0.6                      # so viel vom Timing des Schlagzeugers bleibt (1 = alles, 0 = genau im Raster)
PICK_SPREAD = 0.15              # wie weit die Wahl um die passende Dichte streut (Anteil aller Phrasen)
FILL_EVERY = 8                  # in langen Teilen alle so viele Takte ein Fill


def path() -> str:
    return os.path.join(FOLDER, LIBRARY)


def installed() -> bool:
    return os.path.isfile(path())


@functools.lru_cache(maxsize=2)
def _read(file: str, mtime: float) -> dict:
    with open(file, encoding="utf-8") as f:
        return json.load(f)


def load() -> Optional[dict]:
    """Die Sammlung aus setup_grooves.py; None, wenn sie fehlt oder kaputt ist."""
    if not installed():
        return None
    try:
        data = _read(path(), os.path.getmtime(path()))
    except (OSError, ValueError) as e:
        log.warning("Grooves lassen sich nicht lesen (%s), es spielen die eingebauten", e)
        return None
    return data if data.get("phrases") else None


def status() -> str:
    data = load()
    if data is None:
        return "Echte Grooves fehlen: unter Hilfe › Einrichten laden (etwa 3 MB)"
    return f"Echte Grooves: {len(data['phrases'])} Phrasen und {len(data.get('fills', []))} Fills"


def _density(phrase: dict) -> float:
    return sum(len(bar) for bar in phrase["bars"]) / len(phrase["bars"])


class Drummer:
    """Ein Schlagzeuger für einen Song: pro Groove eine Phrase und eine Auswahl an Fills."""

    def __init__(self, data: dict, bpm: float, seed: int):
        self.data, self.bpm, self.seed = data, bpm, seed
        self.phrases = {}

    def _fitting(self, items: list, groove: str) -> list:
        styles = FAMILIES.get(groove, ())
        found = [p for p in items if p["style"] in styles]
        tempo = [p for p in found if TEMPO_RANGE[0] <= p["bpm"] / self.bpm <= TEMPO_RANGE[1]]
        return tempo or found

    def plays(self, groove: str) -> bool:
        return bool(self._fitting(self.data["phrases"], groove))

    def phrase(self, groove: str, energy: float) -> dict:
        """Die Phrase für diesen Groove: lockerer bei wenig Energie, dichter bei viel; einmal gewählt, bleibt sie."""
        if groove not in self.phrases:
            found = sorted(self._fitting(self.data["phrases"], groove), key=_density)
            rng = random.Random(f"{self.seed}:{groove}")
            at = energy * (len(found) - 1) + rng.uniform(-PICK_SPREAD, PICK_SPREAD) * len(found)
            self.phrases[groove] = found[max(0, min(len(found) - 1, round(at)))]
        return self.phrases[groove]

    def bar(self, groove: str, energy: float, number: int) -> list:
        """Takt number der Phrase (sie wiederholt sich), als [(Schlag im Takt, Ton, Anschlag)]."""
        bars = self.phrase(groove, energy)["bars"]
        return _played(bars[number % len(bars)], energy)

    def fill(self, groove: str, energy: float, rng: random.Random) -> Optional[list]:
        fills = self._fitting(self.data.get("fills", []), groove)
        if not fills:
            return None
        return _played(rng.choice(fills)["hits"], energy)


def _played(hits: list, energy: float) -> list:
    """Timing etwas näher ans Raster, Anschlag passend zur Energie des Teils."""
    scale = 0.7 + 0.45 * energy
    out = []
    for pos, pitch, vel in hits:
        grid = round(pos * 4) / 4
        out.append((max(0.0, grid + (pos - grid) * FEEL), int(pitch), max(1, min(127, round(vel * scale)))))
    return out


def for_song(bpm: float, seed: int) -> Optional[Drummer]:
    data = load()
    return Drummer(data, bpm, seed) if data else None

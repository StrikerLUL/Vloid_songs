# ritardando.py – Ritardando am Ende (v6 Nr. 16)
#
# Eine Ballade wird in den letzten Takten langsamer und lässt den Schlussakkord lange ausklingen (Fermate), wie eine
# Band, die gemeinsam ausatmet. Nur wenn der Song instrumental endet (Outro): der Gesang bleibt im Tempo, NEUTRINO
# singt nur ein Tempo. Die Noten bleiben im Raster; langsamer werden ihre Zeiten in Sekunden und die MIDI-Dateien
# bekommen dazu die Tempowechsel.
import math
from typing import Callable, Optional

STYLES = {"Ballade": 2}          # Stil: so viele Takte vor dem Schlussakkord wird es langsamer
END_TEMPO = 0.65                 # im Schlussakkord: so viel vom Tempo
FERMATA = 1.5                    # der Schlussakkord klingt so viel länger


def window(plan, style_name: str) -> Optional[tuple]:
    """(Anfang, Schlussakkord) des Ritardandos in Schlägen; None in anderen Stilen und wenn am Ende gesungen wird."""
    bars = STYLES.get(style_name, 0)
    if not bars or not plan.sections:
        return None
    last = plan.sections[-1]
    if last.has_vocals:
        return None
    final = last.end - last.bar_beats             # dort setzt der Schlussakkord ein (orchestrator._final_chord)
    start = max(last.start, final - bars * last.bar_beats)
    return (start, final) if final - start > 1e-6 else None


def step(quarters_per_beat: float) -> float:
    """Das Tempo ändert sich jede Achtel."""
    return 0.5 / quarters_per_beat


def factor(beat: float, rit: tuple, quarters_per_beat: float = 1.0) -> float:
    """Tempo an dieser Stelle im Verhältnis zum Songtempo; je Achtel gleich, damit MIDI und Audio übereinstimmen."""
    start, end = rit
    if beat < start:
        return 1.0
    if beat >= end - 1e-9:
        return END_TEMPO
    size = step(quarters_per_beat)
    middle = start + (math.floor((beat - start) / size + 1e-9) + 0.5) * size
    return 1.0 - (1.0 - END_TEMPO) * (middle - start) / (end - start)


def warp(rit: Optional[tuple], quarters_per_beat: float = 1.0) -> Optional[Callable[[float], float]]:
    """Schlag → Schlag im Songtempo (so viel Zeit vergeht bis dahin); None ohne Ritardando."""
    if rit is None:
        return None
    start, end = rit
    size = step(quarters_per_beat)

    def at(beat: float) -> float:
        if beat <= start:
            return beat
        out, b = start, start
        while b < min(beat, end) - 1e-12:
            nxt = min(b + size, beat, end)
            out += (nxt - b) / factor(b, rit, quarters_per_beat)
            b = nxt
        if beat > end:
            out += (beat - end) / END_TEMPO
        return out
    return at


def tempo_points(rit: tuple, bpm: float, quarters_per_beat: float) -> list:
    """[(Schlag, BPM in Vierteln)] der Tempowechsel für die MIDI-Dateien."""
    start, end = rit
    size = step(quarters_per_beat)
    count = int(round((end - start) / size))
    points = [(start + k * size, bpm * quarters_per_beat * factor(start + k * size, rit, quarters_per_beat))
              for k in range(count)]
    return points + [(end, bpm * quarters_per_beat * END_TEMPO)]

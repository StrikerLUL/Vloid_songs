# riff.py – Ein eigenes Riff für Intro, Zwischenspiel und Outro (1.3.0, I1)
#
# Bis 1.2 spielt das Intro die Refrain-Melodie nach. Jetzt komponiert die App für jeden Song eine eigene Figur aus
# zwei Takten: einen Rhythmus mit Synkopen und eine Linie in Tonleiterstufen, deren betonte Töne Akkordtöne sind.
# Die Lead-Stimme spielt sie im Intro, im Zwischenspiel nach dem ersten Refrain und im Outro; über anderen Akkorden
# rückt die Figur um so viele Stufen, dass ihre betonten Töne wieder passen (Sequenz), am Ende eines Teils hält sie
# den letzten Ton. Im letzten Refrain läuft sie in der zweiten Hälfte leise eine Oktave höher mit.
import random
from dataclasses import dataclass
from typing import Optional

from parts import Ev, _vel
from song_plan import BEATS_PER_BAR, Section, SongPlan
from theory import scale_pcs

FIGURE_STEPS = 32                 # zwei Takte in Sechzehnteln
# Einsätze der Figur in Sechzehnteln; der zweite Takt antwortet dem ersten und endet mit einem langen Ton
RHYTHMS = {
    "drive": ((0, 3, 6, 8, 10, 12, 14, 16, 19, 22, 24), (0, 2, 3, 6, 8, 11, 14, 16, 18, 19, 22, 24),
              (0, 2, 4, 6, 7, 8, 10, 12, 14, 16, 18, 20, 22, 23, 24)),
    "calm": ((0, 3, 6, 10, 12, 16, 19, 22, 26), (0, 4, 6, 8, 12, 16, 20, 22, 24)),
}
CALM_STYLES = ("Ballade", "Lo-Fi", "City Pop")
END_STEP = 30                     # der letzte Ton der Figur endet hier (eine Achtel Luft)
# Bewegung von Ton zu Ton in Tonleiterstufen und wie oft
MOVES = ((1, 30), (-1, 30), (2, 10), (-2, 12), (0, 10), (3, 3), (-3, 4))
LOWEST, HIGHEST = -4, 5          # Stufen um den Grundton: die Figur bleibt in gut einer Oktave
SHIFTS = (0, 1, -1, 2, -2, 3, -3)
RANGE_BELOW, RANGE_ABOVE = 5, 10  # Halbtöne um die Mitte der Lead-Stimme
QUIET, OCTAVE = 0.45, 12          # im letzten Refrain: so leise und so viel höher


@dataclass
class Riff:
    figure: list                  # [(Sechzehntel, Länge in Sechzehnteln, Stufe ab dem Grundton, betont)]
    center: int                   # mittlere Lage (MIDI)


def _ladder(sec: Section, center: int) -> list:
    pcs = set(scale_pcs(sec.tonic, sec.mode))
    return [p for p in range(center - 2 * RANGE_ABOVE, center + 2 * RANGE_ABOVE + 1) if p % 12 in pcs]


def _home(ladder: list, sec: Section, center: int) -> int:
    """Index des Grundtons, der der Mitte am nächsten liegt."""
    return min((i for i, p in enumerate(ladder) if p % 12 == sec.tonic), key=lambda i: abs(ladder[i] - center))


def compose(plan: SongPlan, rng: random.Random, skip_beat: Optional[int] = None) -> Optional[Riff]:
    """Die Figur des Songs, auf den Akkorden des Intros (oder des ersten Refrains). skip_beat: im 3/4-Takt fällt
    dieser Schlag jedes Vierer-Takts heraus (meter.py), dort setzt die Figur nicht ein."""
    sec = next((s for s in plan.sections if s.kind in ("Intro", "Interlude", "Outro", "Chorus")), None)
    if sec is None:
        return None
    center = plan.style.vocal_center + 5
    rhythms = RHYTHMS["calm" if plan.style.name in CALM_STYLES else "drive"]
    onsets = [s for s in rng.choice(rhythms) if skip_beat is None or (s % 16) // 4 != skip_beat]
    ladder = _ladder(sec, center)
    home = _home(ladder, sec, center)
    moves, weights = zip(*MOVES)
    figure, degree = [], None
    for i, step in enumerate(onsets):
        nxt = onsets[i + 1] if i + 1 < len(onsets) else END_STEP
        dur = max(1, nxt - step)
        strong = step % 8 == 0 or dur >= 3 or i == len(onsets) - 1
        chord = sec.chord_at(sec.start + step / 4)
        if degree is None:
            degree = 0
        elif step >= 16 and step - 16 in [s for s, *_ in figure[:3]]:
            degree = next(d for s, _, d, _ in figure if s == step - 16)      # der zweite Takt antwortet dem ersten
        elif i == len(onsets) - 1:
            degree = (degree + rng.choice((0, 0, 2))) // 2      # der lange Schlusston kehrt zur Mitte zurück
        else:
            degree += rng.choices(moves, weights)[0]
        degree = max(LOWEST, min(HIGHEST, degree))
        if strong:
            degree = _snap(ladder, home, degree, chord.pcs)
        figure.append((step, dur, degree, strong))
    return Riff(figure=figure, center=center)


def _snap(ladder: list, home: int, degree: int, pcs) -> int:
    """Die nächste Stufe, deren Ton im Akkord liegt."""
    for d in (0, -1, 1, -2, 2, -3, 3):
        i = home + degree + d
        if 0 <= i < len(ladder) and ladder[i] % 12 in pcs:
            return degree + d
    return degree


def play(riff: Riff, sec: Section, start: Optional[float] = None, accent: float = 0.85, octave: int = 0,
         final: bool = False) -> list:
    """Die Figur in jedem Zwei-Takt-Abschnitt der Sektion ab start, auf deren Akkorde verschoben. Im letzten Abschnitt
    hält sie den letzten Ton bis zum Ende des Teils; final (Ende des Songs): sie endet auf der Eins des letzten Takts
    mit einem Akkordton, der bis zum Schluss klingt."""
    begin = sec.start if start is None else start
    ladder = _ladder(sec, riff.center)
    home = _home(ladder, sec, riff.center)
    span = FIGURE_STEPS / 4
    out = []
    t = begin
    while t + span <= sec.end + 1e-6:
        last = t + 2 * span > sec.end + 1e-6
        shift = _best_shift(riff, sec, ladder, home, t)
        figure = riff.figure
        if last and final:
            figure = [f for f in figure if f[0] < 16]
        for k, (step, dur, degree, strong) in enumerate(figure):
            i = max(0, min(len(ladder) - 1, home + degree + shift))
            pitch = ladder[i]
            when = t + step / 4
            chord = sec.chord_at(when)
            if strong and pitch % 12 not in chord.pcs:
                pitch = min((p for p in ladder if p % 12 in chord.pcs), key=lambda p: (abs(p - pitch), p))
            length = dur / 4 * 0.9
            if last and not final and k == len(figure) - 1:
                length = max(length, sec.end - when - 0.5)
            out.append(Ev(when, length, pitch + octave, _vel(sec, accent if strong else accent * 0.85)))
        if last and final and out:
            when = t + span / 2
            chord = sec.chord_at(when)
            pitch = min((p for p in ladder if p % 12 in chord.pcs), key=lambda p: (abs(p + octave - out[-1].pitch), p))
            out.append(Ev(when, sec.end - when, pitch + octave, _vel(sec, accent)))
        t += span
    return out


def _best_shift(riff: Riff, sec: Section, ladder: list, home: int, t: float) -> int:
    """So viele Stufen rückt die Figur, damit möglichst viele betonte Töne im Akkord liegen (bei Gleichstand: wenig)."""
    def misses(shift: int) -> int:
        count = 0
        for step, _, degree, strong in riff.figure:
            i = home + degree + shift
            if not 0 <= i < len(ladder):
                return 99
            if strong and ladder[i] % 12 not in sec.chord_at(t + step / 4).pcs:
                count += 1
        return count
    return min(SHIFTS, key=lambda s: (misses(s), abs(s)))


def last_chorus(riff: Riff, sec: Section) -> list:
    """Im letzten Refrain: die zweite Hälfte leise eine Oktave höher, unter dem Gesang kaum zu hören, aber zu spüren."""
    half = sec.start + (sec.bars // 2) * BEATS_PER_BAR
    return play(riff, sec, start=half, accent=QUIET, octave=OCTAVE)


def with_interlude(structure: list) -> list:
    """Der Ablauf mit einem Zwischenspiel nach dem ersten Refrain, wenn danach eine Strophe oder der Rap kommt und
    der Ablauf noch keins hat."""
    if "Interlude" in structure:
        return list(structure)
    for i, kind in enumerate(structure[:-1]):
        if kind == "Chorus":
            if structure[i + 1] in ("Verse", "Rap"):
                return structure[:i + 1] + ["Interlude"] + structure[i + 1:]
            break
    return list(structure)

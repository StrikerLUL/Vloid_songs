# melody_score.py – Punkte für eine Gesangsmelodie (1.3.0, M1)
#
# Der Melodie-Schreiber würfelt, und nicht jeder Wurf ist gleich eingängig. Mit „Beste Melodie suchen“ schreibt er
# CANDIDATES Fassungen jeder Sektionsart, und diese Punkte wählen die beste: ein Umfang, der weder eintönig noch zu
# weit ist, ein klarer Höhepunkt auf einem langen oder betonten Ton, Schritte und Sprünge gemischt, wenige
# Tonwiederholungen am Stück, Takte, deren Motiv wiederkommt, Sprünge, nach denen die Melodie zurückgeht, lange Töne
# nur auf Silben, die man halten kann, und ein Refrain, der höher hinausgeht als die Strophe.
import logging
from typing import Optional

log = logging.getLogger(__name__)

CANDIDATES = 30
PHRASE_GAP = 1.0             # Schläge Pause, ab denen eine neue Phrase beginnt
# Umfang (Halbtöne vom tiefsten zum höchsten Ton), der sich gut anhört
IDEAL_RANGE = {"Chorus": (9, 13), "Verse": (6, 10), "PreChorus": (7, 11), "Bridge": (7, 12)}
# Anteile der Bewegungen von Ton zu Ton: Schritte (1–2 Halbtöne), Sprünge (ab 3) und Tonwiederholungen
STEP_SHARE = (0.45, 0.75)
LEAP_SHARE = (0.1, 0.3)
REPEAT_SHARE = (0.05, 0.3)
LONG_RUN = 4                 # so viele gleiche Töne nacheinander sind schon eintönig
BIG_LEAP = 5                 # nach einem Sprung ab einer Quarte soll die Melodie zurückgehen
HOLD_BEATS = 1.0             # ab dieser Länge muss die Silbe ein Vokal sein, den man halten kann
UNHELD = ("ん", "っ")
HIGH_SHARE = 0.25            # so viel der Zeit darf die Stimme ganz oben (die oberen zwei Halbtöne) singen
WEIGHTS = {"range": 1.0, "peak": 1.0, "moves": 1.5, "runs": 0.8, "motif": 1.0, "text": 1.0, "recovery": 0.6,
           "contrast": 1.0, "high": 0.6}


def score(notes: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
          bar_beats: float = 4, targets: Optional[dict] = None) -> float:
    """
    Punkte einer Sektion (MelNotes), mehr ist besser. below: die schon geschriebenen Töne der Sektionen vor dem
    Refrain (der Refrain soll höher hinaus), top: höchster Ton der Stimme, bar_beats: Schläge pro Takt.
    targets: was im Stil anders gut ist (1.4.0, style_dna.MelodyCharacter.score): "steps", "leaps", "repeats" als
    (von, bis), "range" als {Sektionsart: (von, bis)}, "motif_weight" als Gewicht der Motive.
    """
    weights = dict(WEIGHTS)
    if targets and "motif_weight" in targets:
        weights["motif"] = targets["motif_weight"]
    return sum(weights[name] * value for name, value in parts(notes, kind, below, top, bar_beats, targets).items())


def parts(notes: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
          bar_beats: float = 4, targets: Optional[dict] = None) -> dict:
    """Die einzelnen Punkte (jeweils etwa -1 bis 1), zum Nachsehen und für die Tests."""
    sung = sorted((n for n in notes if not getattr(n.syllable, "melisma", False)), key=lambda n: n.start)
    if len(sung) < 2:
        return {name: 0.0 for name in WEIGHTS}
    pitches = [n.pitch for n in sung]
    moves = [b.pitch - a.pitch for a, b in zip(sung, sung[1:]) if b.start - a.start - a.dur < PHRASE_GAP]
    return {
        "range": _range(pitches, kind, (targets or {}).get("range")),
        "peak": _peak(sung),
        "moves": _moves(moves, targets),
        "runs": _runs(sung),
        "motif": _motif(sung, bar_beats),
        "text": _text(notes),
        "recovery": _recovery(moves),
        "contrast": _contrast(sung, kind, below),
        "high": _high(sung, top),
    }


def _range(pitches: list, kind: str, own: Optional[dict] = None) -> float:
    lo, hi = (own or {}).get(kind) or IDEAL_RANGE.get(kind, (7, 11))
    span = max(pitches) - min(pitches)
    return 1.0 - 0.25 * max(lo - span, span - hi, 0)


def _peak(sung: list) -> float:
    """Ein klarer Höhepunkt: der höchste Ton kommt selten und mindestens einmal lang oder betont."""
    top = max(n.pitch for n in sung)
    tops = [n for n in sung if n.pitch == top]
    held = any(n.strong or n.dur >= 0.75 for n in tops)
    return (0.6 if held else -0.4) + 0.4 * (len(tops) <= 3) - 0.15 * max(len(tops) - 4, 0)


def _share_penalty(share: float, bounds: tuple) -> float:
    lo, hi = bounds
    return max(lo - share, share - hi, 0.0) * 4


def _moves(moves: list, targets: Optional[dict] = None) -> float:
    if not moves:
        return 0.0
    targets = targets or {}
    n = len(moves)
    steps = sum(1 for m in moves if 1 <= abs(m) <= 2) / n
    leaps = sum(1 for m in moves if abs(m) >= 3) / n
    repeats = sum(1 for m in moves if m == 0) / n
    return 1.0 - _share_penalty(steps, targets.get("steps", STEP_SHARE)) - \
        _share_penalty(leaps, targets.get("leaps", LEAP_SHARE)) - \
        _share_penalty(repeats, targets.get("repeats", REPEAT_SHARE))


def _runs(sung: list) -> float:
    """Minus für jede Strecke aus LONG_RUN oder mehr gleichen Tönen."""
    penalty, run = 0.0, 1
    for a, b in zip(sung, sung[1:]):
        run = run + 1 if b.pitch == a.pitch else 1
        if run >= LONG_RUN:
            penalty += 0.3
    return 1.0 - penalty


def _motif(sung: list, bar_beats: float) -> float:
    """Wie viele Takte ein Motiv singen, das in einem anderen Takt wiederkommt (Intervalle und Rhythmus)."""
    bars = {}
    for n in sung:
        bars.setdefault(int(n.start // bar_beats), []).append(n)
    shapes = []
    for notes in bars.values():
        if len(notes) < 3:
            continue
        shapes.append((tuple(round(n.start % bar_beats, 2) for n in notes),
                       tuple(b.pitch - a.pitch for a, b in zip(notes, notes[1:]))))
    if len(shapes) < 2:
        return 0.0
    repeated = sum(1 for s in shapes if shapes.count(s) > 1) / len(shapes)
    return min(repeated, 0.6) / 0.6


def _text(notes: list) -> float:
    """Lange Töne auf ん oder っ lassen sich nicht schön halten."""
    bad = sum(1 for n in notes if str(n.syllable or "") in UNHELD and n.dur >= HOLD_BEATS)
    return 1.0 - 0.5 * bad


def _recovery(moves: list) -> float:
    """Nach einem großen Sprung geht eine gute Melodie in die Gegenrichtung zurück."""
    jumps = [(a, b) for a, b in zip(moves, moves[1:]) if abs(a) >= BIG_LEAP]
    if not jumps:
        return 0.5
    return 1.0 - 0.3 * sum(1 for a, b in jumps if a * b > 0)


def _contrast(sung: list, kind: str, below: Optional[list]) -> float:
    """Der Refrain liegt höher als die Teile davor: sein höchster Ton und seine Mitte."""
    if kind != "Chorus" or not below:
        return 0.0
    mine = [n.pitch for n in sung]
    theirs = [n.pitch for n in below]
    peak = 1.0 if max(mine) > max(theirs) else -0.5 if max(mine) < max(theirs) else 0.0
    mean = sum(mine) / len(mine) - sum(theirs) / len(theirs)
    return peak + (0.5 if mean >= 1.0 else -0.3 if mean < 0 else 0.0)


def _high(sung: list, top: Optional[int]) -> float:
    """Ganz oben singt die Stimme nur kurz: zu lange dort strengt an und klingt gepresst."""
    if top is None:
        return 0.0
    total = sum(n.dur for n in sung) or 1.0
    high = sum(n.dur for n in sung if n.pitch >= top - 1) / total
    return -max(high - HIGH_SHARE, 0.0) * 4


def pick(candidates: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
         bar_beats: float = 4, targets: Optional[dict] = None) -> tuple:
    """Die beste Fassung: (Index, Punkte, Schnitt aller Fassungen). candidates: Listen von MelNotes."""
    scores = [score(c, kind, below, top, bar_beats, targets) for c in candidates]
    best = max(range(len(scores)), key=lambda i: (scores[i], -i))
    return best, scores[best], sum(scores) / len(scores)

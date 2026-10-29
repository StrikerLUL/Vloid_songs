# melody_writer.py – Gesangsmelodie aus Phrasen, Motiven und einem festen Refrain-Hook
#
# Jede Sektion besteht aus Phrasen von 2 oder 4 Takten. Takte innerhalb einer Sektion teilen sich
# einen Rhythmus (Motiv), betonte Töne sind Akkordtöne, dazwischen bewegt sich die Melodie in
# Tonleiterschritten. Der Refrain wiederholt seine erste Phrase (Hook), wiederkehrende Sektionen
# singen dieselbe Melodie. Wo der Text es verrät, folgt die Melodie dem Tonhöhenakzent der Wörter, und
# manche Phrasen enden mit einem Melisma: die letzte Silbe gleitet auf einen zweiten Ton.
import logging
import math
import random
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Optional

from lyrics import Mora, for_occurrence, vowel
from meter import END_RHYTHMS_34, RHYTHMS_34
from song_plan import BEATS_PER_BAR, VOCAL_RANGE, Section, SongPlan
from theory import Chord, scale_pcs

log = logging.getLogger(__name__)

STEPS_PER_BEAT = 4
BAR_STEPS = STEPS_PER_BEAT * BEATS_PER_BAR
VOCAL_LO, VOCAL_HI = VOCAL_RANGE   # Standardlage; ein Song kann eine engere haben (plan.vocal_range)

# Einsätze in Sechzehnteln innerhalb eines Takts, nach Anzahl der Silben im Takt
BODY_RHYTHMS = {
    1: [(0,), (2,)],
    2: [(0, 8), (0, 6), (2, 8), (0, 10)],
    3: [(0, 6, 12), (0, 4, 8), (0, 2, 8), (2, 6, 10), (0, 8, 10), (0, 3, 8)],
    4: [(0, 4, 8, 12), (0, 2, 4, 8), (0, 3, 6, 10), (0, 4, 6, 10), (2, 4, 8, 12), (0, 2, 6, 10)],
    5: [(0, 2, 4, 8, 12), (0, 2, 6, 8, 12), (0, 3, 6, 8, 12), (0, 4, 6, 10, 12), (0, 2, 4, 6, 10)],
    6: [(0, 2, 4, 6, 8, 12), (0, 2, 4, 8, 10, 12), (0, 2, 6, 8, 10, 14), (0, 3, 6, 8, 10, 12)],
    7: [(0, 2, 4, 6, 8, 10, 12), (0, 2, 3, 6, 8, 10, 12), (0, 2, 4, 6, 8, 11, 14)],
    8: [(0, 2, 4, 6, 8, 10, 12, 14), (0, 2, 3, 4, 6, 8, 10, 12), (0, 1, 2, 4, 6, 8, 10, 12)],
}
# Letzter Takt einer Phrase: wenige Töne, dann ein langer Schlusston und Luft zum Atmen
END_RHYTHMS = {
    1: [(0,)],
    2: [(0, 4), (0, 6), (2, 6)],
    3: [(0, 2, 4), (0, 2, 6), (0, 4, 6)],
    4: [(0, 2, 4, 6), (0, 2, 4, 8), (0, 1, 2, 4)],
    5: [(0, 2, 4, 6, 8), (0, 1, 2, 4, 6)],
    6: [(0, 1, 2, 3, 4, 6), (0, 2, 3, 4, 6, 8)],
}
END_RELEASE = 12                  # der Schlusston endet hier, danach wird geatmet
MAX_PER_BAR = 12

# Kosten eines Intervalls in Halbtönen: Schritte sind billig, große Sprünge teuer
INTERVAL_COST = [0.9, 0.0, 0.1, 0.6, 0.8, 1.3, 4.0, 1.8, 3.0, 3.2, 5.0, 6.0, 3.5, 8.0]

# Rollen der Phrasen und ihre Kontur (Abweichung von der Mittellage über die Phrase)
ROLE_SEQUENCES = {
    "Chorus":    ["H", "H2", "H", "END"],
    "Verse":     ["A", "A2", "B", "C"],
    "PreChorus": ["P", "P2", "P", "PUP"],
    "Bridge":    ["A", "A2", "B", "OPEN"],
    "Rap":       ["R", "R2", "R", "R2"],
}
CONTOURS = {
    "A":    lambda t: 3.0 * math.sin(math.pi * t) - 1.0,
    "A2":   lambda t: 3.0 * math.sin(math.pi * t) - 1.0,
    "B":    lambda t: -1.0 + 5.0 * t,
    "C":    lambda t: 2.0 - 4.0 * t,
    "OPEN": lambda t: 1.0 + 2.0 * math.sin(math.pi * t),
    "H":    lambda t: 3.0 + 1.5 * math.sin(2 * math.pi * t) - 2.0 * t,
    "H2":   lambda t: 3.0 + 1.5 * math.sin(2 * math.pi * t) - 2.0 * t,
    "END":  lambda t: 4.0 - 5.0 * t,
    "P":    lambda t: -2.0 + 4.0 * t,
    "P2":   lambda t: -1.0 + 4.0 * t,
    "PUP":  lambda t: 1.0 + 5.0 * t,
    "R":    lambda t: 0.0,
    "R2":   lambda t: 0.0,
}
KIND_OFFSET = {"Verse": -3, "PreChorus": -1, "Chorus": 2, "Bridge": -2, "Rap": -4}

# Gesten pro Takt: Abweichung der Töne eines Takts von der Phrasenkontur (k = Töne im Takt)
def _span(k: int) -> list:
    return [i / (k - 1) for i in range(k)] if k > 1 else [0.0]


GESTURES = {
    "leap_fall": lambda k: [4.0 - 6.0 * x for x in _span(k)],
    "rise":      lambda k: [-2.0 + 4.0 * x for x in _span(k)],
    "fall":      lambda k: [2.0 - 4.0 * x for x in _span(k)],
    "arch":      lambda k: [3.0 * math.sin(math.pi * x) for x in _span(k)],
    "valley":    lambda k: [1.0 - 3.0 * math.sin(math.pi * x) for x in _span(k)],
    "neighbor":  lambda k: [(0.0, 1.0, 0.0, -1.0)[i % 4] for i in range(k)],
}
GESTURE_WEIGHTS = {
    "Chorus":    {"leap_fall": 3, "arch": 2, "fall": 1, "neighbor": 1},
    "Verse":     {"rise": 2, "fall": 2, "neighbor": 1, "valley": 1, "arch": 1},
    "PreChorus": {"rise": 3, "arch": 1, "neighbor": 1},
    "Bridge":    {"arch": 2, "valley": 1, "fall": 1},
}
GESTURE_DEPTH = {"Chorus": 1.0, "Verse": 0.7, "PreChorus": 0.8, "Bridge": 0.8, "Rap": 0.2}
# Singbare Silben pro Sekunde, an denen sich die Dichte orientiert
SYLLABLES_PER_SECOND = {"Verse": 3.3, "PreChorus": 3.5, "Chorus": 3.6, "Bridge": 3.0, "Rap": 5.0, "Spoken": 5.0}
SINGING_SHARE = 0.75
# Steigt der Akzent im Wort (tief → hoch), soll die Melodie nicht fallen, und umgekehrt
ACCENT_COST = 1.5
# ん und っ springen nicht, sie hängen am Ton davor
SPECIAL_MORAE = ("ん", "っ")
# Anteil der Phrasen, deren langer Schlusston ein Melisma bekommt (mal melisma des Stils)
MELISMA_SHARE = {"Chorus": 0.35, "Verse": 0.2, "PreChorus": 0.25, "Bridge": 0.45, "Rap": 0.0}
MELISMA_MIN_STEPS = 6
LEARNED_SHARE = 0.5     # so oft singt ein Takt einen aus MIDI-Dateien gelernten Rhythmus (motifs.py), wenn es einen gibt
# M2 (1.3.0): Auftakte und vorgezogene Töne. Eine Phrase beginnt mit 1 bis 3 Silben vor dem Taktstrich (Sechzehntel
# vor der Eins), und ein Ton auf der Eins kommt manchmal eine Sechzehntel früher, über den Taktstrich gebunden.
PICKUPS = {1: [(-2,), (-1,)], 2: [(-2, -1), (-3, -2)], 3: [(-3, -2, -1)]}
PICKUP_SIZES = ((1, 0.45), (2, 0.4), (3, 0.15))
PICKUP_SHARE = {"Chorus": 0.6, "PreChorus": 0.6, "Verse": 0.5, "Bridge": 0.5}
PUSH_SHARE = {"Chorus": 0.3, "PreChorus": 0.3, "Verse": 0.2, "Bridge": 0.2}
PUSH_STEPS = 1          # so viele Sechzehntel früher
# M3: Vorhalte (ein Ton über dem Akkordton auf der betonten Zeit, der sich auf demselben Vokal löst) und lange
# Refrain-Töne auf der None oder der großen Septime
APPOGGIATURA_SHARE = {"Chorus": 0.15, "PreChorus": 0.12, "Verse": 0.1, "Bridge": 0.15}
APPOGGIATURA_MIN_BEATS = 1.0
COLOR_SHARE = {"Chorus": 0.35, "Bridge": 0.2}
COLOR_MIN_BEATS = 1.5
MAJOR_QUALITIES = ("maj", "maj7", "add9", "maj9", "6")
# M5: drei Silben in einem Schlag als Achteltriole, zwei Achtel als punktierte Achtel und Sechzehntel; so oft je
# Schlag, der dafür passt (City Pop, Ballade und Lo-Fi mehr)
TRIPLET_SHARE = {"City Pop": 0.3, "Ballade": 0.3, "Lo-Fi": 0.25}
DOTTED_SHARE = {"City Pop": 0.25, "Ballade": 0.25, "Lo-Fi": 0.2}
FIGURE_SHARE = 0.1
# M4: der höchste Ton des Songs kommt einmal, am Ende des letzten Refrains; so viele Halbtöne darf er über der
# geschriebenen Stimmlage liegen
CLIMAX_ABOVE = 2


@dataclass
class MelNote:
    start: float                  # Schlag ab Songanfang
    dur: float
    pitch: int
    syllable: Optional[str] = None
    strong: bool = False
    pushed: bool = False          # M2: kommt eine Sechzehntel vor dem Takt, gemeint ist der Akkord danach
    tension: bool = False         # M3: ein gewollter Spannungston (Vorhalt, None), kein Fehler im Akkord


def heard_at(note: MelNote) -> float:
    """Der Schlag, dessen Akkord ein Ton meint: bei einem vorgezogenen Ton der nach dem Taktstrich."""
    return note.start + PUSH_STEPS / STEPS_PER_BEAT if getattr(note, "pushed", False) else note.start


@dataclass
class _Slot:
    step: int                     # Sechzehntel ab Phrasenanfang
    dur: int
    strong: bool
    last: bool


def roles_for(kind: str, n_phrases: int) -> list:
    seq = ROLE_SEQUENCES.get(kind, ROLE_SEQUENCES["Verse"])
    if n_phrases <= 1:
        return [seq[-1]]
    if n_phrases <= len(seq):
        return seq[:n_phrases - 1] + [seq[-1]]
    body = [seq[i % (len(seq) - 1)] for i in range(n_phrases - 1)]
    return body + [seq[-1]]


def phrase_bars_for(bars: int, bpm: float, bar_beats: float = BEATS_PER_BAR) -> int:
    bar_seconds = bar_beats * 60.0 / bpm
    if bars % 4 == 0 and bar_seconds * 4 <= 8.5:
        return 4
    if bars % 2 == 0:
        return 2
    return bars


def max_syllables(bars: int, bar_steps: int = BAR_STEPS) -> int:
    return bars * _per_bar(bar_steps)


def _per_bar(bar_steps: int) -> int:
    """So viele Silben passen höchstens in einen Takt: 12 im 4/4-Takt, 9 im 3/4-Takt."""
    return MAX_PER_BAR * bar_steps // BAR_STEPS


def _local_scale(tonic: int, mode: str, chord: Chord) -> set:
    """Tonleiter, in der leiterfremde Akkordtöne (z. B. die Terz der Dominante in Moll) ihre Nachbarn ersetzen."""
    pcs = set(scale_pcs(tonic, mode))
    for pc in chord.pcs:
        if pc not in pcs:
            pcs -= {(pc - 1) % 12, (pc + 1) % 12}
            pcs.add(pc)
    return pcs


class SectionMelodyWriter:
    def __init__(self, plan: SongPlan, section: Section, rng: random.Random, motifs=None, extras=()):
        """motifs: zusätzliche Rhythmen und Gesten (motifs.Motifs); None = nur die eingebauten.
        extras: eingeschaltete Neuerungen aus 1.3.0 (pipeline.COMPOSITION_EXTRAS), z. B. "melody_pickups"."""
        self.plan = plan
        self.sec = section
        self.rng = rng
        self.extra = motifs
        self.extras = extras
        # die Sektion „Sprechen“ bekommt den Rhythmus des Raps (gesprochen wird sie frei, spoken.py)
        self.kind = "Rap" if section.kind == "Spoken" else section.kind if section.kind in ROLE_SEQUENCES else "Verse"
        lo, hi = plan.vocal_range
        center = plan.style.vocal_center + KIND_OFFSET.get(self.kind, 0)
        self.center = max(lo + 7, min(hi - 8, center))
        self.lo = max(lo, self.center - 7)
        self.hi = min(hi, self.center + 8)
        self.motifs = {}
        self.gestures = {}
        self.melisma = {}
        self.pushes = {}
        self.tensions = {}
        self.figures = {}
        # Sechzehntel pro Takt: 16, im 3/4-Takt 12 (dort schreibt der Writer im fertigen Takt, meter.py)
        self.bar_steps = int(round(section.bar_beats * STEPS_PER_BEAT))
        self.waltz = self.bar_steps == 12
        self.body = RHYTHMS_34 if self.waltz else BODY_RHYTHMS
        self.ends = END_RHYTHMS_34 if self.waltz else END_RHYTHMS
        self.strong_steps = (0,) if self.waltz else (0, 8)
        self.release = self.bar_steps - 4         # der Schlusston endet einen Schlag vor dem Taktende
        self.own_rhythms = bool(motifs) and self.bar_steps == BAR_STEPS   # gelernte Rhythmen sind 4/4
        # 1.4.0: der Melodie-Charakter des Stils (style_dna.py); None = wie bis 1.3
        self.char = None
        if "melody_character" in extras and self.kind not in ("Rap",):
            import style_dna
            self.char = style_dna.character(plan.style.name)
        self.costs = INTERVAL_COST if self.char is None else _interval_costs(self.char)
        self.avoid = ()
        if self.char is not None and self.char.avoid:
            major = (self.sec.tonic + 4) % 12 in scale_pcs(self.sec.tonic, self.sec.mode)
            self.avoid = self.char.avoid.get("major" if major else "minor", ())
        self.detached = {}

    # ── Silben verteilen ─────────────────────────────────────────────────────────
    def allocate(self, syllables: list) -> tuple:
        """Silben auf Phrasen verteilen. Kurze Texte werden wiederholt, damit die Sektion nicht leer klingt."""
        bars = self.sec.bars
        pb = phrase_bars_for(bars, self.plan.bpm, self.sec.bar_beats)
        n_phrases = max(bars // pb, 1)
        syllables = list(syllables) or ["ら"]
        seconds = bars * self.sec.bar_beats * self.plan.seconds_per_beat
        comfortable = SYLLABLES_PER_SECOND.get(self.kind, 3.3) * seconds * SINGING_SHARE
        if self.char is not None:
            comfortable *= self.char.density
        reps = max(1, round(comfortable / len(syllables)))
        while reps > 1 and len(syllables) * reps > max_syllables(bars, self.bar_steps):
            reps -= 1
        stream = (syllables * reps)[:max_syllables(bars, self.bar_steps)]
        if reps > 1 and n_phrases % reps == 0:
            per_pass = n_phrases // reps
            chunks = []
            for r in range(reps):
                chunks.extend(_split_even(syllables, per_pass))
        else:
            chunks = _split_even(stream, n_phrases)
        return pb, chunks

    # ── Rhythmus ─────────────────────────────────────────────────────────────────
    def _motif(self, count: int, variant: int = 0) -> tuple:
        """Rhythmus eines Takts mit count Silben. variant 1 ist ein zweites Motiv für jeden zweiten Takt."""
        if count == 0:
            return ()
        key = (count, variant)
        if key in self.motifs:
            return self.motifs[key]
        for other in (count - 1, count + 1):
            if (other, variant) in self.motifs and other > 0:
                self.motifs[key] = _derive(self.motifs[(other, variant)], count, self.bar_steps)
                return self.motifs[key]
        if count in self.body:
            options = list(self.body[count])
            if self.own_rhythms:
                options += self.extra.body.get(count, [])
                learned = self.extra.learned.get(count, [])
                if learned and self.rng.random() < LEARNED_SHARE:
                    options = list(learned)
            if self.char is not None and not self.waltz:
                import style_dna
                options += style_dna.EXTRA_RHYTHMS.get(self.char.rhythm, {}).get(count, [])
            first = self.motifs.get((count, 0))
            if variant and first in options and len(set(options)) > 1:
                options = [o for o in options if o != first]
            motif = self.rng.choice(options) if self.char is None else self._styled_choice(options)
        else:
            eighths = set(range(0, self.bar_steps, 2))
            extra = [s for s in (3, 11, 7, 15, 1, 9, 5, 13) if s < self.bar_steps][:count - len(eighths)]
            motif = tuple(sorted(eighths | set(extra)))[:count]
        self.motifs[key] = motif
        return motif

    def _styled_choice(self, options: list) -> tuple:
        """Ein Rhythmus, gewichtet nach dem Rhythmus des Stils (style_dna.rhythm_fit)."""
        import style_dna
        weights = [math.exp(self.char.rhythm_pull * style_dna.rhythm_fit(o, self.char.rhythm, self.bar_steps))
                   for o in options]
        return self.rng.choices(options, weights)[0]

    def _end_rhythm(self, count: int, role: str) -> tuple:
        key = ("end", role, count)
        if key not in self.motifs:
            options = self.ends.get(min(count, 6))
            if self.own_rhythms:
                options = options + self.extra.end.get(min(count, 6), [])
            self.motifs[key] = self.rng.choice(options) if count <= 6 else self._motif(count)
        return self.motifs[key]

    def phrase_rhythm(self, n: int, phrase_bars: int, role: str, pickup: tuple = ()) -> list:
        """Einsätze und Längen (in Sechzehnteln) für n Silben in einer Phrase. pickup: Einsätze vor der Eins (negativ,
        M2) für die ersten Silben."""
        n -= len(pickup)
        if phrase_bars == 1:
            counts, end = [], n
        else:
            body = phrase_bars - 1
            end = 1 if n <= body + 1 else max(1, min(6, round(n / phrase_bars * 0.6)))
            rest = n - end
            while rest > body * _per_bar(self.bar_steps) and end < 6:
                end += 1
                rest -= 1
            base, extra = divmod(rest, body)
            order = list(range(1, body)) + [0]
            counts = [base] * body
            for i in order[:extra]:
                counts[i] += 1
        onsets = []
        for b, c in enumerate(counts):
            variant = b % 2 if len(counts) > 2 else 0
            onsets.extend(b * self.bar_steps + s for s in self._motif(c, variant))
        last_bar = len(counts) * self.bar_steps
        onsets.extend(last_bar + s for s in self._end_rhythm(end, role))
        onsets = list(pickup) + onsets
        phrase_end = last_bar + self.release
        if onsets and onsets[-1] >= phrase_end - 1:
            phrase_end = min(last_bar + self.bar_steps, onsets[-1] + 2)
        slots = []
        for i, step in enumerate(onsets):
            nxt = onsets[i + 1] if i + 1 < len(onsets) else phrase_end
            in_bar = step % self.bar_steps
            dur = max(1, nxt - step)
            strong = in_bar in self.strong_steps or dur >= 4 or i == len(onsets) - 1
            slots.append(_Slot(step, dur, strong, i == len(onsets) - 1))
        return slots

    # ── Tonhöhen ─────────────────────────────────────────────────────────────────
    def _gesture(self, role: str, bar: int) -> str:
        key = (role.rstrip("2"), bar)
        if key not in self.gestures:
            weights = GESTURE_WEIGHTS.get(self.kind, GESTURE_WEIGHTS["Verse"])
            if self.char is not None and self.kind in self.char.gestures:
                weights = self.char.gestures[self.kind]
            if self.extra:
                weights = {**weights, **self.extra.weights(self.kind)}
            names = list(weights)
            self.gestures[key] = self.rng.choices(names, [weights[n] for n in names])[0]
        return self.gestures[key]

    def _gesture_offsets(self, slots: list, role: str) -> list:
        by_bar = {}
        for i, s in enumerate(slots):
            by_bar.setdefault(s.step // self.bar_steps, []).append(i)
        depth = GESTURE_DEPTH.get(self.kind, 0.8)
        offsets = [0.0] * len(slots)
        for bar, idxs in by_bar.items():
            name = self._gesture(role, bar)
            shape = GESTURES[name](len(idxs)) if name in GESTURES else self.extra.gesture(name, len(idxs))
            for i, off in zip(idxs, shape):
                offsets[i] = off * depth
        return offsets

    def _chord_at_step(self, phrase_start: float, step: int) -> Chord:
        return self.sec.chord_at(phrase_start + step / STEPS_PER_BEAT)

    def _candidates(self, chord: Chord, strong: bool) -> list:
        pcs = set(chord.pcs) if strong else _local_scale(self.sec.tonic, self.sec.mode, chord)
        return [p for p in range(self.lo, self.hi + 1) if p % 12 in pcs]

    def _choose(self, slot: _Slot, chord: Chord, target: float, prev: Optional[int], prev_move: int,
                history: list, ending_pcs: Optional[set] = None, accent: int = 0, special: bool = False) -> int:
        """accent: +1, wenn die Silbe im Wort höher gesprochen wird als die davor, -1 wenn tiefer."""
        cands = self._candidates(chord, slot.strong)
        if ending_pcs:
            preferred = [p for p in cands if p % 12 in ending_pcs]
            cands = preferred or cands
        scale = _local_scale(self.sec.tonic, self.sec.mode, chord)
        best, best_cost = None, float("inf")
        for p in cands:
            cost = abs(p - target) * 0.35
            if prev is not None:
                d = abs(p - prev)
                cost += self.costs[min(d, len(self.costs) - 1)]
                if d == 0:
                    cost += -0.6 if slot.dur <= 1 else 0.6   # schnelle Tonwiederholungen sind typisch, lange nicht
                    if self.char is not None and slot.dur <= 1:
                        cost -= self.char.repeat_bonus
                if abs(prev_move) >= 5 and (p - prev) * prev_move > 0:
                    cost += 2.0           # nach einem Sprung in die Gegenrichtung
                if d == 0 and len(history) >= 2 and history[-1] == history[-2] == p:
                    cost += 3.0
                if accent and (p - prev) * accent < 0:
                    cost += ACCENT_COST
                if special and d > 2:
                    cost += 1.5
            if p % 12 not in chord.pcs:
                cost += 0.25
                if slot.dur >= 4:
                    cost += 2.5
            if p % 12 not in scale:
                cost += 5.0
            if self.avoid and (p - self.sec.tonic) % 12 in self.avoid:
                cost += AVOID_COST
            cost += self.rng.random() * 0.7
            if cost < best_cost:
                best, best_cost = p, cost
        return best if best is not None else int(round(target))

    def _ending_pcs(self, role: str, chord: Chord) -> set:
        if role in ("END", "C") and self.sec.tonic in chord.pcs:
            return {self.sec.tonic}
        if role in ("H", "A", "P"):
            return set(chord.triad_pcs[1:])        # offen: Terz oder Quinte
        if role in ("H2", "A2", "P2"):
            return {chord.root}                    # die Antwort landet auf dem Grundton
        return set(chord.triad_pcs)

    def phrase_pitches(self, slots: list, phrase_start: float, role: str, prev: Optional[int],
                       reference: Optional[list] = None, words: Optional[list] = None) -> list:
        """Tonhöhen für alle Einsätze. Mit reference werden Takte übernommen, deren Rhythmus gleich ist.
        words: die Silben der Phrase; ihr Tonhöhenakzent lenkt die Richtung der Melodie."""
        accents = accent_moves(words or [])
        accents += [0] * (len(slots) - len(accents))
        special = [str(w) in SPECIAL_MORAE for w in (words or [])] + [False] * len(slots)
        total = max(slots[-1].step + slots[-1].dur, 1)
        contour = CONTOURS.get(role, CONTOURS["A"])
        out, history, prev_move = [], [], 0
        ref_by_step = {s.step: p for s, p in reference} if reference else {}
        gesture = self._gesture_offsets(slots, role)
        last_bar_start = (slots[-1].step // self.bar_steps) * self.bar_steps
        for i, slot in enumerate(slots):
            chord = self._chord_at_step(phrase_start, slot.step)
            if self.char is None:
                target = self.center + contour(slot.step / total) + gesture[i]
            else:
                target = self.center + self.char.contour * (contour(slot.step / total) + gesture[i])
            ref = ref_by_step.get(slot.step)
            in_last_bar = slot.step >= last_bar_start and len(slots) > 1
            if ref is not None and not (in_last_bar and role in ("H2", "A2", "P2")):
                pitch = ref
                if slot.strong and pitch % 12 not in chord.pcs:
                    pitch = self._choose(slot, chord, ref, prev, prev_move, history)
            else:
                ending = self._ending_pcs(role, chord) if slot.last else None
                if ref is not None:
                    target = (target + ref) / 2 - 1
                pitch = self._choose(slot, chord, target, prev, prev_move, history, ending, accents[i], special[i])
            if prev is not None:
                prev_move = pitch - prev
            out.append(pitch)
            history.append(pitch)
            prev = pitch
        return out

    def sequence_bars(self, slots: list, pitches: list, phrase_start: float) -> list:
        """Hook-Technik: weitere Takte wiederholen das Motiv des ersten Takts, verschoben auf den neuen Akkord."""
        bars = {}
        for i, s in enumerate(slots):
            bars.setdefault(s.step // self.bar_steps, []).append(i)
        first = bars.get(0, [])
        if not first:
            return pitches
        motif_steps = [slots[i].step for i in first]
        out = list(pitches)
        scale = sorted(p for p in range(self.lo - 12, self.hi + 13) if p % 12 in scale_pcs(self.sec.tonic, self.sec.mode))
        for b, idxs in bars.items():
            if b == 0 or b == max(bars):
                continue
            steps = [slots[i].step - b * self.bar_steps for i in idxs]
            if steps != motif_steps:
                continue
            chord = self._chord_at_step(phrase_start, b * self.bar_steps)
            best = None
            for shift in (0, 1, -1, 2, -2, 3, -3, 4, -4):
                moved = [_scale_shift(scale, out[i], shift) for i in first]
                if None in moved or min(moved) < self.lo or max(moved) > self.hi:
                    continue
                strong_ok = all(m % 12 in chord.pcs for m, i in zip(moved, first) if slots[i].strong)
                if strong_ok:
                    best = moved
                    break
            if best:
                for i, p in zip(idxs, best):
                    out[i] = p
        return out

    # ── Ganze Sektion ────────────────────────────────────────────────────────────
    def write(self, syllables: list) -> list:
        pb, chunks = self.allocate(syllables)
        roles = roles_for(self.kind, len(chunks))
        notes, prev = [], None
        written = {}
        for ph, (chunk, role) in enumerate(zip(chunks, roles)):
            phrase_start = self.sec.start + ph * pb * self.sec.bar_beats
            slots = self.phrase_rhythm(len(chunk), pb, role, self._pickup(ph, role, len(chunk), notes, phrase_start))
            slots = self._figures(slots, role)
            base_role = role.rstrip("2")
            reference = written.get(base_role)
            same_rhythm = reference and [s.step for s, _ in reference] == [s.step for s in slots]
            if role in ("H", "A", "P") and reference and same_rhythm:
                pitches = [p for _, p in reference]       # die Phrase kehrt genau wieder
            else:
                pitches = self.phrase_pitches(slots, phrase_start, role, prev,
                                              reference if same_rhythm else None, chunk)
                if role == "H":
                    pitches = self.sequence_bars(slots, pitches, phrase_start)
            written.setdefault(role, list(zip(slots, pitches)))
            phrase = [MelNote(start=phrase_start + float(slot.step) / STEPS_PER_BEAT,
                              dur=float(slot.dur) / STEPS_PER_BEAT, pitch=pitch, syllable=syl, strong=slot.strong)
                      for slot, pitch, syl in zip(slots, pitches, chunk)]
            self._push(slots, phrase, role)
            self._detach(slots, phrase, role)
            for slot, group in zip(slots, self._tension(slots, phrase, role)):
                if len(group) > 1:
                    notes += group
                else:
                    notes += self._melisma(group[0], role) if slot.last and slot.dur >= MELISMA_MIN_STEPS else group
            prev = pitches[-1] if pitches else prev
        return notes

    # ── Auftakte und vorgezogene Töne (M2) ───────────────────────────────────────
    def _grooves(self) -> bool:
        return "melody_pickups" in self.extras and not self.waltz and self.kind != "Rap"

    def _pickup(self, ph: int, role: str, n: int, notes: list, phrase_start: float) -> tuple:
        """Einsätze vor der Eins für die ersten Silben der Phrase, oder (). Nie in der ersten Phrase der Sektion und
        nie in Phrasen, die wörtlich wiederkehren (H, A, P), damit die Hook gleich bleibt."""
        if not self._grooves() or ph == 0 or role in ("H", "A", "P") or not notes:
            return ()
        if self.rng.random() >= PICKUP_SHARE.get(self.kind, 0.3):
            return ()
        room = (phrase_start - notes[-1].start - notes[-1].dur) * STEPS_PER_BEAT - 1   # eine Sechzehntel zum Atmen
        sizes, weights = zip(*PICKUP_SIZES)
        k = min(self.rng.choices(sizes, weights)[0], n - 2)
        while k > 0:
            options = [p for p in PICKUPS[k] if -p[0] <= room]
            if options:
                return self.rng.choice(options)
            k -= 1
        return ()

    def _push(self, slots: list, phrase: list, role: str) -> None:
        """Töne auf der Eins kommen eine Sechzehntel früher, der Ton davor wird so viel kürzer (Synkope über den
        Taktstrich). Gleiche Stellen gleicher Phrasen werden gleich vorgezogen."""
        if not self._grooves():
            return
        share = PUSH_SHARE.get(self.kind, 0.2)
        early = PUSH_STEPS / STEPS_PER_BEAT
        for i in range(1, len(slots)):
            slot, before = slots[i], slots[i - 1]
            if slot.step <= 0 or slot.step % self.bar_steps or before.step + before.dur != slot.step or before.dur < 2:
                continue
            key = (role.rstrip("2"), slot.step)
            if key not in self.pushes:
                self.pushes[key] = self.rng.random() < share
            if self.pushes[key]:
                note, prev = phrase[i], phrase[i - 1]
                note.start -= early
                note.dur += early
                note.pushed = True
                prev.dur -= early

    # ── Abgesetzte Töne (1.4.0, Melodie-Charakter) ───────────────────────────────
    def _detach(self, slots: list, phrase: list, role: str) -> None:
        """Achtel mitten in der Phrase werden zur Sechzehntel mit Sechzehntelpause danach (Kawaii, Idol: kurz und
        abgesetzt). Gleiche Stellen gleicher Phrasen entscheiden gleich, damit die Hook gleich bleibt."""
        if self.char is None or self.char.staccato <= 0:
            return
        for i in range(len(slots) - 1):
            slot, note = slots[i], phrase[i]
            if slot.dur != 2 or slots[i + 1].step != slot.step + 2 or str(note.syllable) in SPECIAL_MORAE \
                    or getattr(note, "pushed", False) or getattr(phrase[i + 1], "pushed", False):
                continue
            key = (role.rstrip("2"), slot.step)
            if key not in self.detached:
                self.detached[key] = self.rng.random() < self.char.staccato
            if self.detached[key]:
                note.dur = 1.0 / STEPS_PER_BEAT

    # ── Triolen und punktierte Rhythmen (M5) ─────────────────────────────────────
    def _figures(self, slots: list, role: str) -> list:
        """Schläge mit drei Einsätzen werden zur Achteltriole, Schläge mit zwei Achteln punktiert. Gleiche Stellen
        gleicher Phrasen entscheiden gleich (die Hook bleibt), nur im 4/4-Takt."""
        if "melody_triplets" not in self.extras or self.waltz or self.kind == "Rap" or not slots:
            return slots
        style = self.plan.style.name
        out = list(slots)
        beats = int(max(s.step + s.dur for s in slots) // STEPS_PER_BEAT)
        for b in range(beats):
            begin, end = b * STEPS_PER_BEAT, (b + 1) * STEPS_PER_BEAT
            idx = [i for i, s in enumerate(out) if begin <= s.step < end]
            if not idx or out[idx[0]].step != begin:
                continue
            last = out[idx[-1]]
            reach = last.step + last.dur
            if len(idx) == 3 and reach >= end:
                key, share = (role.rstrip("2"), b, 3), TRIPLET_SHARE.get(style, FIGURE_SHARE)
                third = Fraction(STEPS_PER_BEAT, 3)
                if self._figure(key, share):
                    for k, i in enumerate(idx):
                        start = begin + k * third
                        out[i] = _Slot(start, third if k < 2 else reach - start, out[i].strong, out[i].last)
            elif len(idx) == 2 and out[idx[1]].step == begin + 2 and out[idx[0]].dur == 2 and reach >= end:
                key, share = (role.rstrip("2"), b, 2), DOTTED_SHARE.get(style, FIGURE_SHARE)
                if self._figure(key, share):
                    first, second = out[idx[0]], out[idx[1]]
                    out[idx[0]] = _Slot(first.step, 3, first.strong, first.last)
                    out[idx[1]] = _Slot(begin + 3, reach - begin - 3, second.strong, second.last)
        return out

    def _figure(self, key: tuple, share: float) -> bool:
        if key not in self.figures:
            self.figures[key] = self.rng.random() < share
        return self.figures[key]

    # ── Vorhalte und Spannungstöne (M3) ──────────────────────────────────────────
    def _tension(self, slots: list, phrase: list, role: str) -> list:
        """[[Töne] je Einsatz]: ein Ton allein oder ein Vorhalt mit seiner Auflösung. Gleiche Stellen gleicher Phrasen
        entscheiden gleich, damit die Hook gleich bleibt."""
        if "melody_tensions" not in self.extras or self.kind == "Rap":
            return [[n] for n in phrase]
        out = []
        for i, (slot, note) in enumerate(zip(slots, phrase)):
            key = (role.rstrip("2"), slot.step)
            if key not in self.tensions:
                roll = self.rng.random()
                if roll < APPOGGIATURA_SHARE.get(self.kind, 0.0):
                    self.tensions[key] = "lean"
                elif roll < APPOGGIATURA_SHARE.get(self.kind, 0.0) + COLOR_SHARE.get(self.kind, 0.0):
                    self.tensions[key] = "color"
                else:
                    self.tensions[key] = ""
            choice = self.tensions[key]
            final = slot.last and role in ("END", "C")
            if choice == "lean" and i > 0 and slot.strong:
                out.append(self._lean(note))
            elif choice == "color" and not final and note.dur >= COLOR_MIN_BEATS:
                self._color(note)
                out.append([note])
            else:
                out.append([note])
        return out

    def _lean(self, note: MelNote) -> list:
        """Vorhalt: die erste Hälfte einen Schritt über dem Akkordton, dann auf demselben Vokal hinunter."""
        sung = vowel(note.syllable or "")
        if note.dur < APPOGGIATURA_MIN_BEATS or sung is None or str(note.syllable) in SPECIAL_MORAE:
            return [note]
        chord = self.sec.chord_at(heard_at(note))
        scale = _local_scale(self.sec.tonic, self.sec.mode, chord)
        upper = next((p for p in (note.pitch + 1, note.pitch + 2) if p % 12 in scale), None)
        if upper is None or upper % 12 in chord.pcs or upper > self.hi or note.pitch % 12 not in chord.pcs:
            return [note]
        first = max(0.5, math.floor(note.dur) / 2)
        return [replace(note, dur=first, pitch=upper, tension=True),
                MelNote(note.start + first, note.dur - first, note.pitch, Mora(sung, melisma=True), False)]

    def _color(self, note: MelNote) -> None:
        """Ein langer Ton rückt auf die None oder (in Dur-Akkorden) die große Septime, wenn sie nah liegt."""
        chord = self.sec.chord_at(heard_at(note))
        scale = _local_scale(self.sec.tonic, self.sec.mode, chord)
        colors = {(chord.root + 2) % 12}
        if chord.quality in MAJOR_QUALITIES:
            colors.add((chord.root + 11) % 12)
        near = [p for p in range(note.pitch - 2, note.pitch + 3)
                if p % 12 in colors and p % 12 in scale and self.lo <= p <= self.hi and p != note.pitch]
        if near:
            note.pitch = min(near, key=lambda p: (abs(p - note.pitch), p))
            note.tension = True

    def _melisma(self, note: MelNote, role: str) -> list:
        """Der lange Schlusston gleitet auf den nächsten Akkordton darunter (oder darüber), auf demselben Vokal."""
        if role not in self.melisma:
            share = MELISMA_SHARE.get(self.kind, 0.2) * self.plan.style.melisma
            self.melisma[role] = self.rng.random() < share
        sung = vowel(note.syllable or "")
        if not self.melisma[role] or sung is None:
            return [note]
        first = max(0.5, round(note.dur * 0.6 * 2) / 2)
        second_start = note.start + first
        chord = self.sec.chord_at(second_start)
        below = [p for p in range(note.pitch - 5, note.pitch) if p % 12 in chord.pcs and p >= self.lo]
        above = [p for p in range(note.pitch + 1, note.pitch + 5) if p % 12 in chord.pcs and p <= self.hi]
        target = max(below) if below else min(above) if above else None
        if target is None:
            return [note]
        return [replace(note, dur=first),
                MelNote(second_start, note.dur - first, target, Mora(sung, melisma=True), False)]


FAVORITE_SHARE = 0.4      # so viel kostet ein typischer Sprung des Stils im Vergleich zu sonst
AVOID_COST = 2.0          # so viel kostet eine Stufe, die der Stil meidet (style_dna.MelodyCharacter.avoid)


def _interval_costs(char) -> list:
    """INTERVAL_COST für einen Melodie-Charakter: Schritte und Sprünge teurer oder billiger, typische Sprünge billig."""
    out = []
    for d, cost in enumerate(INTERVAL_COST):
        if 1 <= d <= 2:
            cost *= char.step_cost
        elif d >= 3:
            cost *= char.leap_cost
        if d in char.favorite_leaps:
            cost *= FAVORITE_SHARE
        out.append(cost)
    return out


def accent_moves(words: list) -> list:
    """Pro Silbe: +1, wenn sie im selben Wort höher gesprochen wird als die davor, -1 wenn tiefer, sonst 0."""
    out = []
    for i, w in enumerate(words):
        before = words[i - 1] if i else None
        a, b = getattr(before, "tone", None), getattr(w, "tone", None)
        if a and b and a != b and not getattr(w, "word_start", False):
            out.append(1 if b == "H" else -1)
        else:
            out.append(0)
    return out


def _split_even(items: list, parts: int) -> list:
    parts = max(parts, 1)
    base, extra = divmod(len(items), parts)
    out, i = [], 0
    for p in range(parts):
        size = base + (1 if p < extra else 0)
        out.append(items[i:i + size])
        i += size
    return [c for c in out if c] or [items]


def _derive(motif: tuple, count: int, bar_steps: int = BAR_STEPS) -> tuple:
    """Motiv mit einer Silbe mehr oder weniger, so ähnlich wie möglich."""
    onsets = list(motif)
    while len(onsets) < count:
        bounds = onsets + [bar_steps]
        gaps = [(bounds[i + 1] - bounds[i], i) for i in range(len(onsets))]
        size, i = max(gaps)
        if size < 2:
            break
        half = size // 2
        new = onsets[i] + (half if half % 2 == 0 or size < 4 else half - 1)
        onsets.insert(i + 1, new)
    while len(onsets) > count:
        bounds = onsets + [bar_steps]
        gaps = [(bounds[i + 1] - bounds[i], i) for i in range(1, len(onsets))]
        _, i = min(gaps) if gaps else (0, 0)
        onsets.pop(i if i else len(onsets) - 1)
    return tuple(onsets)


def _scale_shift(scale: list, pitch: int, steps: int) -> Optional[int]:
    if pitch not in scale:
        pitch = min(scale, key=lambda p: abs(p - pitch))
    i = scale.index(pitch) + steps
    return scale[i] if 0 <= i < len(scale) else None


# ── Ganzer Song ──────────────────────────────────────────────────────────────────
def write_vocal_melody(plan: SongPlan, lyrics: dict, rng: random.Random, rerolls: Optional[dict] = None,
                       imported: Optional[dict] = None, motifs=None, singable: bool = False, extras=()) -> list:
    """
    Melodie für alle Sektionen mit Gesang. Jede Sektionsart wird einmal komponiert; spätere Vorkommen
    singen dieselbe Melodie (im Schlussrefrain höher, wenn der Song die Tonart wechselt). Hat ein späteres Vorkommen
    einen eigenen Text (lyrics["Verse#2"], aus „[Verse 2]“), singt es ihn auf dieselbe Melodie (fit_text).
    Jede Sektionsart würfelt für sich; rerolls {Sektionsart: Zufall} schreibt nur ihre Melodie neu.
    imported {Sektionsart: Melodie aus melody_import.load}: dort singt die eigene Melodie, Ton für Ton.
    motifs: zusätzliche Rhythmen und Gesten (motifs.Motifs), None = nur die eingebauten.
    singable: die komponierten Töne danach auf Singbarkeit prüfen (make_singable).
    extras: eingeschaltete Neuerungen aus 1.3.0; "best_melody" schreibt jede Sektionsart mehrmals und nimmt die
    Fassung mit den meisten Punkten (melody_score.py).
    """
    seed = rng.getrandbits(64)
    rerolls, imported = rerolls or {}, imported or {}
    written = {}
    notes = []
    for sec in plan.sections:
        if not sec.has_vocals:
            continue
        if sec.kind not in written:
            if imported.get(sec.kind):
                from melody_import import fit
                sec_notes = fit(imported[sec.kind], plan, sec, lyrics.get(sec.kind, []))
            else:
                kind_rng = rerolls.get(sec.kind) or random.Random(f"{seed}:{sec.kind}")
                words = lyrics.get(sec.kind, [])
                if "best_melody" in extras and sec.kind not in ("Rap", "Spoken"):
                    before = [n for kind, (_, ns) in written.items() if kind in ("Verse", "PreChorus") for n in ns]
                    sec_notes = _best_of(plan, sec, kind_rng, motifs, words, extras, before)
                else:
                    sec_notes = SectionMelodyWriter(plan, sec, kind_rng, motifs, extras).write(words)
                if sec.kind in ("Rap", "Spoken"):
                    _chant(sec_notes)
            written[sec.kind] = (sec, sec_notes)
        else:
            first, first_notes = written[sec.kind]
            shift = (sec.tonic - first.tonic + 6) % 12 - 6
            sec_notes = [replace(n, start=n.start - first.start + sec.start, pitch=n.pitch + shift) for n in first_notes]
            own = for_occurrence(lyrics, sec.kind, sec.occurrence)
            if own:
                sec_notes = fit_text(sec_notes, own)
                log.info("%s %d singt seinen eigenen Text (%d Silben)", sec.kind, sec.occurrence, len(own))
        notes.extend(sec_notes)
    composed = [n for n in notes if not imported.get(plan.section_at(n.start).kind)]
    if "melody_climax" in extras:
        _plan_climax(plan, notes, composed)
    _fit_to_chords(plan, composed)
    if singable:
        make_singable(plan, composed)
    return notes


def _best_of(plan: SongPlan, sec: Section, rng: random.Random, motifs, words: list, extras, before: list) -> list:
    """M1: die Sektion melody_score.CANDIDATES-mal schreiben, die Fassung mit den meisten Punkten gewinnt.
    before: Töne der Strophe und des Pre-Chorus, über die der Refrain hinausgehen soll."""
    import melody_score
    base = rng.getrandbits(64)
    candidates = [SectionMelodyWriter(plan, sec, random.Random(f"{base}:{i}"), motifs, extras).write(words)
                  for i in range(melody_score.CANDIDATES)]
    targets = None
    if "melody_character" in extras:
        import style_dna
        targets = style_dna.character(plan.style.name).score or None
    best, points, mean = melody_score.pick(candidates, sec.kind, before, plan.vocal_range[1], sec.bar_beats, targets)
    log.info("Beste Melodie: %s aus %d Fassungen, %.1f Punkte (Schnitt %.1f)", sec.kind, len(candidates), points, mean)
    return candidates[best]


def _plan_climax(plan: SongPlan, notes: list, composed: list) -> None:
    """M4: die Schlusszeile des letzten Refrains endet oben, auf dem höchsten Ton des ganzen Songs, und nur dort
    (ein Akkordton; reicht die Stimmlage nicht darüber, rücken die anderen Töne so hoch einen Schritt tiefer).
    Strophe, Pre-Chorus und Bridge bleiben unter dem Spitzenton der Refrain-Hook."""
    choruses = [sec for sec in plan.sections if sec.kind == "Chorus" and sec.has_vocals]
    mine = set(id(n) for n in composed)
    if not choruses:
        return
    first, last = choruses[0], choruses[-1]
    ending = sorted((n for n in notes if last.start <= n.start < last.end and id(n) in mine), key=lambda n: n.start)
    if not ending:
        return
    held = [n for n in ending if not _held(n)]
    final = held[-1] if held else ending[-1]
    tail = [n for n in ending if n.start >= final.start]
    rest = [n for n in notes if n.start < final.start or n.start >= last.end]
    top = max((n.pitch for n in rest), default=final.pitch)
    chord = plan.chord_at(heard_at(final))
    hi = plan.vocal_range[1] + CLIMAX_ABOVE
    climax = next((p for p in range(top + 1, top + 6) if p % 12 in chord.pcs and p <= hi), None) or \
        next((p for p in range(min(top, hi), top - 5, -1) if p % 12 in chord.pcs), None)
    if climax is None or climax < final.pitch:
        log.info("Höhepunkt: kein Akkordton nahe %d, der Schluss bleibt", top)
        return
    for n in tail:
        n.pitch = climax
    lowered = sum(_below(plan, n, climax) for n in rest if n.pitch >= climax and id(n) in mine)
    hook = [n.pitch for n in notes if first.start <= n.start < first.end and n.start < final.start]
    peak = max(hook) if hook else climax
    lowered += sum(_below(plan, n, peak) for n in notes if id(n) in mine and n.pitch >= peak
                   and plan.section_at(n.start).kind in ("Verse", "PreChorus", "Bridge"))
    log.info("Höhepunkt: der letzte Refrain endet auf %d (sonst höchstens %d), %d Töne tiefer", climax,
             max((n.pitch for n in rest), default=climax), lowered)


def _below(plan: SongPlan, n: MelNote, ceiling: int) -> int:
    """Der Ton rückt unter ceiling, auf den nächsten Akkordton (lang oder betont) oder Ton der Tonleiter. 1 = gerückt."""
    scale, chord = _scale_at(plan, n)
    pcs = chord.pcs if n.strong or n.dur >= 1 else scale
    below = [p for p in range(ceiling - 7, ceiling) if p % 12 in pcs]
    if not below:
        return 0
    n.pitch = max(below)
    return 1


RAP_RANGE = 2           # Halbtöne um die Mitte: ein Rap ohne Sprechstimme klingt wie ein Sprechgesang


def _chant(notes: list) -> None:
    """Der Rap-Teil fast auf einem Ton (rap.py spricht ihn; singt ihn die Engine, klingt er wie ein Sprechgesang)."""
    if not notes:
        return
    center = sorted(n.pitch for n in notes)[len(notes) // 2]
    for n in notes:
        n.pitch = center + max(-RAP_RANGE, min(RAP_RANGE, round((n.pitch - center) * 0.35)))


# ── Eigener Text für eine wiederholte Sektion (v6, Nr. 1) ───────────────────────
# Die Melodie bleibt, der Rhythmus passt sich an: mehr Silben teilen die längsten Töne, weniger Silben lassen kurze
# Töne direkt nach einem anderen auf dem Vokal davor weiterklingen (Melisma) oder binden sie an ihn.
MIN_SPLIT = 0.5             # Schläge: kürzere Töne werden nicht mehr geteilt (zwei Sechzehntel)
SPLIT_GRID = 0.25


def _held(note: MelNote) -> bool:
    return bool(getattr(note.syllable, "melisma", False))


def fit_text(notes: list, syllables: list) -> list:
    """
    Die Töne einer wiederholten Sektion mit einem eigenen Text. notes: die Töne des ersten Vorkommens (an die Stelle
    dieses Vorkommens verschoben), syllables: der neue Text. Ist er viel kürzer als der alte, wird er wie beim ersten
    Vorkommen wiederholt. Rückgabe: neue Töne mit den neuen Silben; Tonhöhen und Phrasen bleiben.
    """
    out = [[replace(n), not _held(n)] for n in sorted(notes, key=lambda n: n.start)]
    words = [w for w in syllables if w]
    if not out or not words:
        return [n for n, _ in out]
    slots = sum(1 for _, sung in out if sung)
    stream = words * max(1, round(slots / len(words)))
    # mehr Silben als Töne: erst Melismen zu eigenen Silben, dann die längsten Töne teilen
    while sum(1 for _, sung in out if sung) < len(stream):
        held = next((item for item in out if not item[1]), None)
        if held:
            held[1] = True
            continue
        longest = max(out, key=lambda item: (item[0].dur, -item[0].start))
        note = longest[0]
        if note.dur < MIN_SPLIT:
            break
        first = max(SPLIT_GRID, round(note.dur / 2 / SPLIT_GRID) * SPLIT_GRID)
        rest = MelNote(note.start + first, note.dur - first, note.pitch, None, False)
        note.dur = first
        out.insert(out.index(longest) + 1, [rest, True])
    # weniger Silben als Töne: kurze, unbetonte Töne direkt nach einem anderen klingen auf dessen Silbe weiter
    surplus = sum(1 for _, sung in out if sung) - len(stream)
    if surplus > 0:
        candidates = [i for i in range(1, len(out)) if out[i][1]
                      and abs(out[i - 1][0].start + out[i - 1][0].dur - out[i][0].start) < 1e-6]
        candidates.sort(key=lambda i: (out[i][0].strong, out[i][0].dur, out[i][0].start))
        for i in candidates[:surplus]:
            out[i][1] = False
        surplus -= min(surplus, len(candidates))
        while surplus > 0:                       # sonst die kürzesten Töne weglassen (eine Pause mehr)
            shortest = min((item for item in out if item[1]), key=lambda item: (item[0].dur, -item[0].start))
            out.remove(shortest)
            surplus -= 1
    fitted, words = [], iter(stream)
    for note, sung in out:
        if sung:
            note.syllable = next(words, None)
        elif fitted and fitted[-1].pitch == note.pitch and \
                abs(fitted[-1].start + fitted[-1].dur - note.start) < 1e-6:
            fitted[-1].dur += note.dur            # gleicher Ton: einfach länger halten
            continue
        else:
            sound = vowel(str(fitted[-1].syllable or "")) if fitted else None
            if sound is None:                     # nach っ oder vor dem ersten Ton: ein Ton weniger
                if fitted and abs(fitted[-1].start + fitted[-1].dur - note.start) < 1e-6:
                    fitted[-1].dur += note.dur
                continue
            note.syllable = Mora(sound, melisma=True)
            note.strong = False
        fitted.append(note)
    left = sum(1 for _ in words)
    if left:
        log.warning("Eigener Text: %d Silben passen nicht mehr auf die Melodie und fallen weg", left)
    return fitted


# ── Singbarkeit (Gesang 1.1, A5) ────────────────────────────────────────────────
# Laut NEUTRINO-FAQ klingen extreme Sprünge und Melodien ohne Pause unnatürlich. Die Prüfung ändert nur
# einzelne Töne: Tonhöhen von Sprüngen und Spitzen, und am Ende langer Strecken wird der letzte Ton kürzer.
MAX_SHORT_LEAP = 7          # Halbtöne: weiter springt die Stimme nur auf einen Ton ab einer Achtel
SHORT_NOTE = 0.5            # Schläge: kürzer ist eine kurze Silbe
LEAP_GAP = 1.0              # nach so viel Pause darf die Stimme neu ansetzen, wo sie will
SIXTEENTH = 0.25
PEAK_GAP = 0.5              # Pause in Schlägen, an der eine Phrase für die Spitzen-Prüfung endet
LONG_PHRASE_SECONDS = 8.0   # so lange singt die Stimme höchstens ohne Atempause
BREATH_SECONDS = 0.25       # so lang ist die Atempause danach mindestens


def make_singable(plan: SongPlan, notes: list) -> dict:
    """
    Prüft die Melodie so, wie eine Sängerin sie singen müsste, und ändert die Töne an Ort und Stelle:
    keine Sprünge über eine Quinte auf eine kurze Silbe, der höchste Ton einer Phrase nicht nur auf einer
    Sechzehntel, und nach spätestens LONG_PHRASE_SECONDS Gesang eine Atempause.
    Rückgabe: {"leaps": …, "peaks": …, "breaths": …}, wie viele Stellen geändert wurden.
    """
    ordered = sorted(notes, key=lambda n: n.start)
    done = {"leaps": _soften_leaps(plan, ordered), "peaks": _hold_peaks(plan, ordered),
            "breaths": _breathe(plan, ordered)}
    if any(done.values()):
        log.info("Singbarkeit: %d Sprünge kleiner, %d Spitzen nicht mehr auf Sechzehnteln, %d Atempausen",
                 done["leaps"], done["peaks"], done["breaths"])
    return done


def _scale_at(plan: SongPlan, n: MelNote) -> tuple:
    sec = plan.section_at(n.start)
    chord = plan.chord_at(heard_at(n))
    return _local_scale(sec.tonic, sec.mode, chord), chord


def _soften_leaps(plan: SongPlan, ordered: list) -> int:
    lo, hi = plan.vocal_range
    changed = 0
    for prev, n in zip(ordered, ordered[1:]):
        if (n.start - prev.start - prev.dur >= LEAP_GAP or n.dur >= SHORT_NOTE
                or abs(n.pitch - prev.pitch) <= MAX_SHORT_LEAP):
            continue
        scale, chord = _scale_at(plan, n)
        candidates = [p for p in range(prev.pitch - MAX_SHORT_LEAP, prev.pitch + MAX_SHORT_LEAP + 1)
                      if p % 12 in scale and lo <= p <= hi + 1]
        if candidates:
            n.pitch = min(candidates, key=lambda p: (abs(p - n.pitch), n.strong and p % 12 not in chord.pcs, p))
            changed += 1
    return changed


def _phrases(ordered: list, gap: float) -> list:
    out, current = [], []
    for n in ordered:
        if current and n.start - current[-1].start - current[-1].dur >= gap:
            out.append(current)
            current = []
        current.append(n)
    return out + [current] if current else out


def _hold_peaks(plan: SongPlan, ordered: list) -> int:
    lo = plan.vocal_range[0]
    changed = 0
    for phrase in _phrases(ordered, PEAK_GAP):
        for _ in range(4):
            top = max(n.pitch for n in phrase)
            tops = [n for n in phrase if n.pitch == top]
            if any(n.dur > SIXTEENTH + 1e-6 for n in tops) or all(n.pitch == top for n in phrase):
                break
            for n in tops:
                scale, _ = _scale_at(plan, n)
                below = [p for p in range(top - 1, top - 4, -1) if p % 12 in scale and p >= lo]
                if not below:
                    return changed
                n.pitch = below[0]
            changed += 1
    return changed


def _breathe(plan: SongPlan, ordered: list) -> int:
    beat = 60.0 / plan.bpm
    breath = max(SIXTEENTH, math.ceil(BREATH_SECONDS / beat / SIXTEENTH) * SIXTEENTH)
    changed = 0
    run_start = ordered[0].start if ordered else 0.0
    for n, nxt in zip(ordered, ordered[1:]):
        gap = nxt.start - n.start - n.dur
        if gap >= breath - 1e-6:
            run_start = nxt.start
            continue
        if (n.start + n.dur - run_start) * beat < LONG_PHRASE_SECONDS or getattr(nxt.syllable, "melisma", False):
            continue
        shorter = nxt.start - breath - n.start
        if shorter >= SIXTEENTH - 1e-6:
            n.dur = shorter
            run_start = nxt.start
            changed += 1
    return changed


def _fit_to_chords(plan: SongPlan, notes: list) -> None:
    """Sicherheitsnetz: lange oder betonte Töne, die nicht zum Akkord passen (z. B. vor dem Tonartwechsel), rücken auf den nächsten Akkordton."""
    for n in notes:
        chord = plan.chord_at(heard_at(n))
        sec = plan.section_at(n.start)
        if n.tension or n.pitch % 12 in _local_scale(sec.tonic, sec.mode, chord) and \
                not (n.strong and n.dur >= 1 and n.pitch % 12 not in chord.pcs):
            continue
        lo, hi = plan.vocal_range
        candidates = [p for p in range(n.pitch - 3, n.pitch + 4) if p % 12 in chord.pcs and lo <= p <= hi + 1]
        if candidates:
            n.pitch = min(candidates, key=lambda p: (abs(p - n.pitch), p))


PHRASE_END_GAP = 1.0     # Schläge Pause, ab denen ein Ton eine Phrase beendet
END_NOTES = 2            # so viele Töne am Phrasenende singt die Harmonie „nur auf Phrasenenden“


def harmony_line(plan: SongPlan, notes: list, kinds: tuple = ("Chorus",), modes: Optional[dict] = None) -> list:
    """
    Zweite Stimme für den Refrain: die Terz über der Melodie aus der Tonleiter; auf langen Tönen ein
    Akkordton. Passt sie nicht mehr in die Stimmlage, singt sie darunter. Im Breakdown schweigt sie.
    modes: {Start der Sektion: Art}; "above" (Terz darüber, Standard), "below" (Terz darunter, wenn sie in die
    Stimmlage passt) oder "ends" (Terz darüber nur auf den letzten Tönen jeder Phrase).
    """
    lo, hi = plan.vocal_range
    ordered = sorted(notes, key=lambda n: n.start)
    ends = set()
    for k, n in enumerate(ordered):
        if k + 1 == len(ordered) or ordered[k + 1].start - (n.start + n.dur) >= PHRASE_END_GAP:
            ends.update(id(m) for m in ordered[max(0, k - END_NOTES + 1):k + 1])
    out = []
    for n in notes:
        sec = plan.section_at(n.start)
        if sec.kind not in kinds or (sec.feel == "breakdown" and n.start < sec.resume):
            continue    # im leisen Teil singt die Stimme allein
        mode = (modes or {}).get(sec.start, "above")
        if mode == "ends" and id(n) not in ends:
            continue
        chord = sec.chord_at(heard_at(n))
        scale = sorted(set(scale_pcs(sec.tonic, sec.mode)) | set(chord.pcs))
        ladder = [p for p in range(n.pitch - 12, n.pitch + 13) if p % 12 in scale]
        i = ladder.index(n.pitch) if n.pitch in ladder else min(range(len(ladder)), key=lambda j: abs(ladder[j] - n.pitch))
        above, below = ladder[min(i + 2, len(ladder) - 1)], ladder[max(i - 2, 0)]
        if n.dur >= 1.0:
            above = next((p for p in range(n.pitch + 3, n.pitch + 8) if p % 12 in chord.pcs), above)
            below = next((p for p in range(n.pitch - 3, n.pitch - 10, -1) if p % 12 in chord.pcs), below)
        pitch = above if above <= hi + 2 else below
        if mode == "below" and below >= lo - 2:
            pitch = below
        out.append(MelNote(n.start, n.dur, max(pitch, lo - 2), n.syllable, n.strong))
    return out


def duet_voice(sec: Section) -> int:
    """Wer im Duett singt: 0 = erste Stimme, 1 = zweite. Strophen und Pre-Chorus wechseln sich ab, die Bridge
    gehört der zweiten Stimme, im Refrain singt die erste die Melodie und die zweite die zweite Stimme."""
    if sec.kind == "Chorus":
        return 0
    if sec.kind == "Bridge":
        return 1
    return (sec.occurrence - 1) % 2


def split_for_duet(plan: SongPlan, data: list, syllables: list) -> tuple:
    """Melodie (wie melody_data) in die Teile beider Stimmen: was die andere singt, wird Pause.
    Rückgabe: ((Daten, Silben) der ersten Stimme, (Daten, Silben) der zweiten)."""
    parts = [([], []), ([], [])]
    t, i = 0.0, 0
    for pitch, dur in data:
        if pitch is not None:
            who = duet_voice(plan.section_at(t + 1e-6))
            for k, (d, s) in enumerate(parts):
                d.append((pitch, dur) if k == who else (None, dur))
                if k == who:
                    s.append(syllables[i] if i < len(syllables) else "ら")
            i += 1
        else:
            for d, _ in parts:
                d.append((None, dur))
        t += dur
    return tuple((_merge_rests(d), s) for d, s in parts)


def group_turns(plan: SongPlan, count: int) -> dict:
    """G5: wer in einer Gruppe singt, je Sektion (Nummer der Sektion → Stimme, None = alle). Die Refrains singen alle
    zusammen, jede Strophe, Bridge und jeder Rap kommt reihum an die nächste Stimme, der Pre-Chorus bleibt bei der
    Stimme der Strophe davor."""
    out, turn = {}, -1
    for sec in plan.sections:
        if not sec.has_vocals:
            continue
        if sec.kind == "Chorus":
            out[sec.index] = None
            continue
        if sec.kind != "PreChorus" or turn < 0:
            turn += 1
        out[sec.index] = turn % count
    return out


def split_for_group(plan: SongPlan, data: list, syllables: list, count: int) -> list:
    """Melodie (wie melody_data) in die Teile der Stimmen einer Gruppe (group_turns): was die anderen allein singen,
    wird Pause. Rückgabe: [(Daten, Silben)] je Stimme."""
    turns = group_turns(plan, count)
    parts = [([], []) for _ in range(count)]
    t, i = 0.0, 0
    for pitch, dur in data:
        if pitch is not None:
            who = turns.get(plan.section_at(t + 1e-6).index)
            for k, (d, s) in enumerate(parts):
                mine = who is None or who == k
                d.append((pitch, dur) if mine else (None, dur))
                if mine:
                    s.append(syllables[i] if i < len(syllables) else "ら")
            i += 1
        else:
            for d, _ in parts:
                d.append((None, dur))
        t += dur
    return [(_merge_rests(d), s) for d, s in parts]


def _merge_rests(data: list) -> list:
    out = []
    for pitch, dur in data:
        if pitch is None and out and out[-1][0] is None:
            out[-1] = (None, round(out[-1][1] + dur, 4))
        else:
            out.append((pitch, dur))
    return out


def melody_data(notes: list) -> tuple:
    """(Tonhöhe, Dauer in Vierteln)-Liste mit None für Pausen, ab Songanfang, und die Silben dazu."""
    data, syllables, t = [], [], 0.0
    for n in sorted(notes, key=lambda n: n.start):
        if n.start > t + 1e-6:
            data.append((None, round(n.start - t, 4)))
        data.append((n.pitch, round(n.dur, 4)))
        syllables.append(n.syllable or "ら")
        t = n.start + n.dur
    return data, syllables


def required_bars(n_syllables: int, bar_steps: int = BAR_STEPS) -> int:
    """Takte (Zweierpotenz), die eine Sektion mindestens braucht, damit n Silben singbar hineinpassen."""
    bars = 1
    while n_syllables > max_syllables(bars, bar_steps):
        bars *= 2
    return bars

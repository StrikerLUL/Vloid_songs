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
from dataclasses import dataclass
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
SYLLABLES_PER_SECOND = {"Verse": 3.3, "PreChorus": 3.5, "Chorus": 3.6, "Bridge": 3.0, "Rap": 5.0}
SINGING_SHARE = 0.75
# Steigt der Akzent im Wort (tief → hoch), soll die Melodie nicht fallen, und umgekehrt
ACCENT_COST = 1.5
# ん und っ springen nicht, sie hängen am Ton davor
SPECIAL_MORAE = ("ん", "っ")
# Anteil der Phrasen, deren langer Schlusston ein Melisma bekommt (mal melisma des Stils)
MELISMA_SHARE = {"Chorus": 0.35, "Verse": 0.2, "PreChorus": 0.25, "Bridge": 0.45, "Rap": 0.0}
MELISMA_MIN_STEPS = 6
LEARNED_SHARE = 0.5     # so oft singt ein Takt einen aus MIDI-Dateien gelernten Rhythmus (motifs.py), wenn es einen gibt


@dataclass
class MelNote:
    start: float                  # Schlag ab Songanfang
    dur: float
    pitch: int
    syllable: Optional[str] = None
    strong: bool = False


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
    def __init__(self, plan: SongPlan, section: Section, rng: random.Random, motifs=None):
        """motifs: zusätzliche Rhythmen und Gesten (motifs.Motifs); None = nur die eingebauten."""
        self.plan = plan
        self.sec = section
        self.rng = rng
        self.extra = motifs
        self.kind = section.kind if section.kind in ROLE_SEQUENCES else "Verse"
        lo, hi = plan.vocal_range
        center = plan.style.vocal_center + KIND_OFFSET.get(self.kind, 0)
        self.center = max(lo + 7, min(hi - 8, center))
        self.lo = max(lo, self.center - 7)
        self.hi = min(hi, self.center + 8)
        self.motifs = {}
        self.gestures = {}
        self.melisma = {}
        # Sechzehntel pro Takt: 16, im 3/4-Takt 12 (dort schreibt der Writer im fertigen Takt, meter.py)
        self.bar_steps = int(round(section.bar_beats * STEPS_PER_BEAT))
        self.waltz = self.bar_steps == 12
        self.body = RHYTHMS_34 if self.waltz else BODY_RHYTHMS
        self.ends = END_RHYTHMS_34 if self.waltz else END_RHYTHMS
        self.strong_steps = (0,) if self.waltz else (0, 8)
        self.release = self.bar_steps - 4         # der Schlusston endet einen Schlag vor dem Taktende
        self.own_rhythms = bool(motifs) and self.bar_steps == BAR_STEPS   # gelernte Rhythmen sind 4/4

    # ── Silben verteilen ─────────────────────────────────────────────────────────
    def allocate(self, syllables: list) -> tuple:
        """Silben auf Phrasen verteilen. Kurze Texte werden wiederholt, damit die Sektion nicht leer klingt."""
        bars = self.sec.bars
        pb = phrase_bars_for(bars, self.plan.bpm, self.sec.bar_beats)
        n_phrases = max(bars // pb, 1)
        syllables = list(syllables) or ["ら"]
        seconds = bars * self.sec.bar_beats * self.plan.seconds_per_beat
        comfortable = SYLLABLES_PER_SECOND.get(self.kind, 3.3) * seconds * SINGING_SHARE
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
            first = self.motifs.get((count, 0))
            if variant and first in options and len(set(options)) > 1:
                options = [o for o in options if o != first]
            motif = self.rng.choice(options)
        else:
            eighths = set(range(0, self.bar_steps, 2))
            extra = [s for s in (3, 11, 7, 15, 1, 9, 5, 13) if s < self.bar_steps][:count - len(eighths)]
            motif = tuple(sorted(eighths | set(extra)))[:count]
        self.motifs[key] = motif
        return motif

    def _end_rhythm(self, count: int, role: str) -> tuple:
        key = ("end", role, count)
        if key not in self.motifs:
            options = self.ends.get(min(count, 6))
            if self.own_rhythms:
                options = options + self.extra.end.get(min(count, 6), [])
            self.motifs[key] = self.rng.choice(options) if count <= 6 else self._motif(count)
        return self.motifs[key]

    def phrase_rhythm(self, n: int, phrase_bars: int, role: str) -> list:
        """Einsätze und Längen (in Sechzehnteln) für n Silben in einer Phrase."""
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
                cost += INTERVAL_COST[min(d, len(INTERVAL_COST) - 1)]
                if d == 0:
                    cost += -0.6 if slot.dur <= 1 else 0.6   # schnelle Tonwiederholungen sind typisch, lange nicht
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
            target = self.center + contour(slot.step / total) + gesture[i]
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
            slots = self.phrase_rhythm(len(chunk), pb, role)
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
            for slot, pitch, syl in zip(slots, pitches, chunk):
                note = MelNote(start=phrase_start + slot.step / STEPS_PER_BEAT, dur=slot.dur / STEPS_PER_BEAT,
                               pitch=pitch, syllable=syl, strong=slot.strong)
                notes += self._melisma(note, role) if slot.last and slot.dur >= MELISMA_MIN_STEPS else [note]
            prev = pitches[-1] if pitches else prev
        return notes

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
        return [MelNote(note.start, first, note.pitch, note.syllable, note.strong),
                MelNote(second_start, note.dur - first, target, Mora(sung, melisma=True), False)]


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
                       imported: Optional[dict] = None, motifs=None, singable: bool = False) -> list:
    """
    Melodie für alle Sektionen mit Gesang. Jede Sektionsart wird einmal komponiert; spätere Vorkommen
    singen dieselbe Melodie (im Schlussrefrain höher, wenn der Song die Tonart wechselt). Hat ein späteres Vorkommen
    einen eigenen Text (lyrics["Verse#2"], aus „[Verse 2]“), singt es ihn auf dieselbe Melodie (fit_text).
    Jede Sektionsart würfelt für sich; rerolls {Sektionsart: Zufall} schreibt nur ihre Melodie neu.
    imported {Sektionsart: Melodie aus melody_import.load}: dort singt die eigene Melodie, Ton für Ton.
    motifs: zusätzliche Rhythmen und Gesten (motifs.Motifs), None = nur die eingebauten.
    singable: die komponierten Töne danach auf Singbarkeit prüfen (make_singable).
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
                sec_notes = SectionMelodyWriter(plan, sec, kind_rng, motifs).write(lyrics.get(sec.kind, []))
                if sec.kind == "Rap":
                    _chant(sec_notes)
            written[sec.kind] = (sec, sec_notes)
        else:
            first, first_notes = written[sec.kind]
            shift = (sec.tonic - first.tonic + 6) % 12 - 6
            sec_notes = [MelNote(n.start - first.start + sec.start, n.dur, n.pitch + shift, n.syllable, n.strong)
                         for n in first_notes]
            own = for_occurrence(lyrics, sec.kind, sec.occurrence)
            if own:
                sec_notes = fit_text(sec_notes, own)
                log.info("%s %d singt seinen eigenen Text (%d Silben)", sec.kind, sec.occurrence, len(own))
        notes.extend(sec_notes)
    composed = [n for n in notes if not imported.get(plan.section_at(n.start).kind)]
    _fit_to_chords(plan, composed)
    if singable:
        make_singable(plan, composed)
    return notes


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
    out = [[MelNote(n.start, n.dur, n.pitch, n.syllable, n.strong), not _held(n)] for n in sorted(notes, key=lambda n: n.start)]
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
    chord = plan.chord_at(n.start)
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
        chord = plan.chord_at(n.start)
        sec = plan.section_at(n.start)
        if n.pitch % 12 in _local_scale(sec.tonic, sec.mode, chord) and not (n.strong and n.dur >= 1 and n.pitch % 12 not in chord.pcs):
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
        chord = sec.chord_at(n.start)
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

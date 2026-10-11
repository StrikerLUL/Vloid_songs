# melody_writer.py – Gesangsmelodie aus Phrasen, Motiven und einem festen Refrain-Hook
#
# Jede Sektion besteht aus Phrasen von 2 oder 4 Takten. Takte innerhalb einer Sektion teilen sich
# einen Rhythmus (Motiv), betonte Töne sind Akkordtöne, dazwischen bewegt sich die Melodie in
# Tonleiterschritten. Der Refrain wiederholt seine erste Phrase (Hook), wiederkehrende Sektionen
# singen dieselbe Melodie. Wo der Text es verrät, folgt die Melodie dem Tonhöhenakzent der Wörter, und
# manche Phrasen enden mit einem Melisma: die letzte Silbe gleitet auf einen zweiten Ton.
import math
import random
from dataclasses import dataclass
from typing import Optional

from lyrics import Mora, vowel
from song_plan import BEATS_PER_BAR, VOCAL_RANGE, Section, SongPlan
from theory import Chord, scale_pcs

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
}
KIND_OFFSET = {"Verse": -3, "PreChorus": -1, "Chorus": 2, "Bridge": -2}

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
GESTURE_DEPTH = {"Chorus": 1.0, "Verse": 0.7, "PreChorus": 0.8, "Bridge": 0.8}
# Singbare Silben pro Sekunde, an denen sich die Dichte orientiert
SYLLABLES_PER_SECOND = {"Verse": 3.3, "PreChorus": 3.5, "Chorus": 3.6, "Bridge": 3.0}
SINGING_SHARE = 0.75
# Steigt der Akzent im Wort (tief → hoch), soll die Melodie nicht fallen, und umgekehrt
ACCENT_COST = 1.5
# ん und っ springen nicht, sie hängen am Ton davor
SPECIAL_MORAE = ("ん", "っ")
# Anteil der Phrasen, deren langer Schlusston ein Melisma bekommt (mal melisma des Stils)
MELISMA_SHARE = {"Chorus": 0.35, "Verse": 0.2, "PreChorus": 0.25, "Bridge": 0.45}
MELISMA_MIN_STEPS = 6


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


def phrase_bars_for(bars: int, bpm: float) -> int:
    bar_seconds = BEATS_PER_BAR * 60.0 / bpm
    if bars % 4 == 0 and bar_seconds * 4 <= 8.5:
        return 4
    if bars % 2 == 0:
        return 2
    return bars


def max_syllables(bars: int) -> int:
    return bars * MAX_PER_BAR


def _local_scale(tonic: int, mode: str, chord: Chord) -> set:
    """Tonleiter, in der leiterfremde Akkordtöne (z. B. die Terz der Dominante in Moll) ihre Nachbarn ersetzen."""
    pcs = set(scale_pcs(tonic, mode))
    for pc in chord.pcs:
        if pc not in pcs:
            pcs -= {(pc - 1) % 12, (pc + 1) % 12}
            pcs.add(pc)
    return pcs


class SectionMelodyWriter:
    def __init__(self, plan: SongPlan, section: Section, rng: random.Random):
        self.plan = plan
        self.sec = section
        self.rng = rng
        self.kind = section.kind if section.kind in ROLE_SEQUENCES else "Verse"
        lo, hi = plan.vocal_range
        center = plan.style.vocal_center + KIND_OFFSET.get(self.kind, 0)
        self.center = max(lo + 7, min(hi - 8, center))
        self.lo = max(lo, self.center - 7)
        self.hi = min(hi, self.center + 8)
        self.motifs = {}
        self.gestures = {}
        self.melisma = {}

    # ── Silben verteilen ─────────────────────────────────────────────────────────
    def allocate(self, syllables: list) -> tuple:
        """Silben auf Phrasen verteilen. Kurze Texte werden wiederholt, damit die Sektion nicht leer klingt."""
        bars = self.sec.bars
        pb = phrase_bars_for(bars, self.plan.bpm)
        n_phrases = max(bars // pb, 1)
        syllables = list(syllables) or ["ら"]
        seconds = bars * BEATS_PER_BAR * self.plan.seconds_per_beat
        comfortable = SYLLABLES_PER_SECOND.get(self.kind, 3.3) * seconds * SINGING_SHARE
        reps = max(1, round(comfortable / len(syllables)))
        while reps > 1 and len(syllables) * reps > max_syllables(bars):
            reps -= 1
        stream = (syllables * reps)[:max_syllables(bars)]
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
                self.motifs[key] = _derive(self.motifs[(other, variant)], count)
                return self.motifs[key]
        if count in BODY_RHYTHMS:
            options = list(BODY_RHYTHMS[count])
            first = self.motifs.get((count, 0))
            if variant and first in options and len(options) > 1:
                options.remove(first)
            motif = self.rng.choice(options)
        else:
            extra = [3, 11, 7, 15, 1, 9, 5, 13][:count - 8]
            motif = tuple(sorted(set(range(0, 16, 2)) | set(extra)))[:count]
        self.motifs[key] = motif
        return motif

    def _end_rhythm(self, count: int, role: str) -> tuple:
        key = ("end", role, count)
        if key not in self.motifs:
            options = END_RHYTHMS.get(min(count, 6))
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
            while rest > body * MAX_PER_BAR and end < 6:
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
            onsets.extend(b * BAR_STEPS + s for s in self._motif(c, variant))
        last_bar = len(counts) * BAR_STEPS
        onsets.extend(last_bar + s for s in self._end_rhythm(end, role))
        phrase_end = last_bar + END_RELEASE
        if onsets and onsets[-1] >= phrase_end - 1:
            phrase_end = min(last_bar + BAR_STEPS, onsets[-1] + 2)
        slots = []
        for i, step in enumerate(onsets):
            nxt = onsets[i + 1] if i + 1 < len(onsets) else phrase_end
            in_bar = step % BAR_STEPS
            dur = max(1, nxt - step)
            strong = in_bar in (0, 8) or dur >= 4 or i == len(onsets) - 1
            slots.append(_Slot(step, dur, strong, i == len(onsets) - 1))
        return slots

    # ── Tonhöhen ─────────────────────────────────────────────────────────────────
    def _gesture(self, role: str, bar: int) -> str:
        key = (role.rstrip("2"), bar)
        if key not in self.gestures:
            weights = GESTURE_WEIGHTS.get(self.kind, GESTURE_WEIGHTS["Verse"])
            names = list(weights)
            self.gestures[key] = self.rng.choices(names, [weights[n] for n in names])[0]
        return self.gestures[key]

    def _gesture_offsets(self, slots: list, role: str) -> list:
        by_bar = {}
        for i, s in enumerate(slots):
            by_bar.setdefault(s.step // BAR_STEPS, []).append(i)
        depth = GESTURE_DEPTH.get(self.kind, 0.8)
        offsets = [0.0] * len(slots)
        for bar, idxs in by_bar.items():
            shape = GESTURES[self._gesture(role, bar)](len(idxs))
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
        last_bar_start = (slots[-1].step // BAR_STEPS) * BAR_STEPS
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
            bars.setdefault(s.step // BAR_STEPS, []).append(i)
        first = bars.get(0, [])
        if not first:
            return pitches
        motif_steps = [slots[i].step for i in first]
        out = list(pitches)
        scale = sorted(p for p in range(self.lo - 12, self.hi + 13) if p % 12 in scale_pcs(self.sec.tonic, self.sec.mode))
        for b, idxs in bars.items():
            if b == 0 or b == max(bars):
                continue
            steps = [slots[i].step - b * BAR_STEPS for i in idxs]
            if steps != motif_steps:
                continue
            chord = self._chord_at_step(phrase_start, b * BAR_STEPS)
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
            phrase_start = self.sec.start + ph * pb * BEATS_PER_BAR
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


def _derive(motif: tuple, count: int) -> tuple:
    """Motiv mit einer Silbe mehr oder weniger, so ähnlich wie möglich."""
    onsets = list(motif)
    while len(onsets) < count:
        bounds = onsets + [BAR_STEPS]
        gaps = [(bounds[i + 1] - bounds[i], i) for i in range(len(onsets))]
        size, i = max(gaps)
        if size < 2:
            break
        half = size // 2
        new = onsets[i] + (half if half % 2 == 0 or size < 4 else half - 1)
        onsets.insert(i + 1, new)
    while len(onsets) > count:
        bounds = onsets + [BAR_STEPS]
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
                       imported: Optional[dict] = None) -> list:
    """
    Melodie für alle Sektionen mit Gesang. Jede Sektionsart wird einmal komponiert; spätere Vorkommen
    singen dieselbe Melodie (im Schlussrefrain höher, wenn der Song die Tonart wechselt).
    Jede Sektionsart würfelt für sich; rerolls {Sektionsart: Zufall} schreibt nur ihre Melodie neu.
    imported {Sektionsart: Melodie aus melody_import.load}: dort singt die eigene Melodie, Ton für Ton.
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
                sec_notes = SectionMelodyWriter(plan, sec, kind_rng).write(lyrics.get(sec.kind, []))
            written[sec.kind] = (sec, sec_notes)
        else:
            first, first_notes = written[sec.kind]
            shift = (sec.tonic - first.tonic + 6) % 12 - 6
            sec_notes = [MelNote(n.start - first.start + sec.start, n.dur, n.pitch + shift, n.syllable, n.strong)
                         for n in first_notes]
        notes.extend(sec_notes)
    _fit_to_chords(plan, [n for n in notes if not imported.get(plan.section_at(n.start).kind)])
    return notes


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


def harmony_line(plan: SongPlan, notes: list, kinds: tuple = ("Chorus",)) -> list:
    """
    Zweite Stimme für den Refrain: die Terz über der Melodie aus der Tonleiter; auf langen Tönen ein
    Akkordton. Passt sie nicht mehr in die Stimmlage, singt sie darunter. Im Breakdown schweigt sie.
    """
    lo, hi = plan.vocal_range
    out = []
    for n in notes:
        sec = plan.section_at(n.start)
        if sec.kind not in kinds or (sec.feel == "breakdown" and n.start < sec.resume):
            continue    # im leisen Teil singt die Stimme allein
        chord = sec.chord_at(n.start)
        scale = sorted(set(scale_pcs(sec.tonic, sec.mode)) | set(chord.pcs))
        ladder = [p for p in range(n.pitch - 12, n.pitch + 13) if p % 12 in scale]
        i = ladder.index(n.pitch) if n.pitch in ladder else min(range(len(ladder)), key=lambda j: abs(ladder[j] - n.pitch))
        above, below = ladder[min(i + 2, len(ladder) - 1)], ladder[max(i - 2, 0)]
        if n.dur >= 1.0:
            above = next((p for p in range(n.pitch + 3, n.pitch + 8) if p % 12 in chord.pcs), above)
            below = next((p for p in range(n.pitch - 3, n.pitch - 10, -1) if p % 12 in chord.pcs), below)
        pitch = above if above <= hi + 2 else below
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


def required_bars(n_syllables: int) -> int:
    """Takte (Zweierpotenz), die eine Sektion mindestens braucht, damit n Silben singbar hineinpassen."""
    bars = 1
    while n_syllables > max_syllables(bars):
        bars *= 2
    return bars

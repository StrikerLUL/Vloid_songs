# meter.py – 3/4- und 6/8-Takt (v6 Nr. 17)
#
# Komponiert wird immer in Vierer-Takten: Akkorde, Gesangsmelodie, Band und Schlagzeug kennen nur sie. Erst am Ende
# rückt time() jeden Ton an seinen Platz im gewählten Takt:
#   3/4: aus jedem Vierer-Takt fällt der dritte Schlag heraus, der vierte wird zum dritten. Aus Bassdrum auf 1,
#        Snare auf 2 und 4 wird so das Bum-Tschak-Tschak des Walzers. Schlagzeug-Muster mit der Snare auf der Drei
#        (Halftime) verlieren stattdessen den zweiten Schlag. Die Gesangsmelodie hat eigene Rhythmen, die den
#        herausfallenden Schlag nie benutzen (RHYTHMS_34), so geht keine Silbe verloren.
#   6/8: jeder Schlag wird zur punktierten Viertel, seine Achtel und Sechzehntel zu Triolen-Achteln: aus Bassdrum
#        auf 1, Snare auf 2 wird der typische 6/8-Groove, aus geraden Achteln ein wiegendes Lang-Kurz. Ein Vierer-Takt
#        sind zwei 6/8-Takte; das Tempo zählt dann die punktierten Viertel (zwei pro Takt).
# Mit 4/4 bleibt alles, wie es war.
import math
from dataclasses import dataclass, replace
from typing import Optional

COMPOSE_BEATS = 4               # so viele Schläge hat ein Takt beim Komponieren
EARLY = 0.0625                  # ein Ton so knapp vor einem Schlag gehört zu diesem Schlag (echte Schlagzeuger)
METERS = ("4/4", "3/4", "6/8")


@dataclass(frozen=True)
class Meter:
    name: str
    bar_beats: float            # Schläge pro Kompositionstakt nach dem Umrechnen (3/4: 3; 6/8: 4 punktierte Viertel)
    bars_per_bar: int           # so viele Takte dieses Takts stecken in einem Kompositionstakt (6/8: 2)
    numerator: int
    denominator: int
    quarters_per_beat: float    # Viertel pro Schlag: 1, im 6/8-Takt 1,5 (punktierte Viertel)
    drop: Optional[int] = None  # 3/4: dieser Schlag (0-basiert) fällt aus jedem Vierer-Takt heraus

    @property
    def plain(self) -> bool:
        return self.name == "4/4"

    @property
    def compound(self) -> bool:
        return self.name == "6/8"

    # ── Zeit ────────────────────────────────────────────────────────────────────────
    def time(self, beat: float, drop: Optional[int] = None) -> float:
        """Kompositionsschlag → Schlag im Takt (für Enden und Grenzen: stetig, der ausfallende Schlag wird zum Punkt)."""
        drop = self.drop if drop is None else drop
        if self.compound:
            whole = math.floor(beat + 1e-9)
            frac = beat - whole
            return whole + (frac * 4 / 3 if frac < 0.5 else 2 / 3 + (frac - 0.5) * 2 / 3)
        if drop is None:
            return beat
        bar = math.floor(beat / COMPOSE_BEATS + 1e-9)
        pos = beat - bar * COMPOSE_BEATS
        pos = pos if pos < drop else drop if pos < drop + 1 else pos - 1
        return bar * self.bar_beats + pos

    def onset(self, beat: float, drop: Optional[int] = None) -> Optional[float]:
        """Wie time(), aber für Anschläge: None, wenn der Ton auf den ausfallenden Schlag fällt. Ein Ton knapp vor
        einem Schlag (EARLY) zählt zu diesem Schlag."""
        drop = self.drop if drop is None else drop
        if self.compound or drop is None:
            return self.time(beat)
        bar = math.floor((beat + EARLY) / COMPOSE_BEATS)
        pos = beat - bar * COMPOSE_BEATS
        if drop - EARLY <= pos < drop + 1 - EARLY:
            return None
        if drop + 1 - EARLY <= pos < drop + 1:
            return bar * self.bar_beats + drop + (pos - drop - 1)
        return self.time(beat, drop)

    def compose_time(self, beat: float) -> float:
        """Umkehrung von time(): Schlag im Takt → Kompositionsschlag."""
        if self.compound:
            whole = math.floor(beat + 1e-9)
            frac = beat - whole
            return whole + (frac * 3 / 4 if frac < 2 / 3 else 0.5 + (frac - 2 / 3) * 3 / 2)
        if self.drop is None:
            return beat
        bar = math.floor(beat / self.bar_beats + 1e-9)
        pos = beat - bar * self.bar_beats
        return bar * COMPOSE_BEATS + (pos if pos < self.drop else pos + 1)

    def events(self, evs: list, drop: Optional[int] = None) -> list:
        """Ereignisse (start, dur in Schlägen, z. B. parts.Ev) an ihren Platz im Takt; was auf den ausfallenden Schlag
        fällt, fehlt danach."""
        if self.plain:
            return evs
        out = []
        for e in evs:
            start = self.onset(e.start, drop)
            if start is None:
                continue
            end = self.time(e.start + e.dur, drop)
            out.append(replace(e, start=start, dur=max(end - start, min(e.dur, 0.05))))
        return out

    @property
    def native(self) -> bool:
        """Schreibt melody_writer die Gesangsmelodie gleich im Takt (3/4) statt in Vierer-Takten?"""
        return self.drop is not None

    def vocal(self, melody: list) -> list:
        """Die Gesangsmelodie (melody_writer.MelNote), wie sie geschrieben wurde, an ihrem Platz im Takt."""
        if not self.compound:
            return melody
        out = []
        for n in melody:
            start = self.time(n.start)
            out.append(replace(n, start=start, dur=max(self.time(n.start + n.dur) - start, 0.05)))
        return out

    def band_vocal(self, melody: list) -> list:
        """Die Gesangsmelodie in Kompositionsschlägen, wie Band und Lead sie hören (im 3/4-Takt zurückgerechnet)."""
        if not self.native:
            return melody
        out = []
        for n in melody:
            start = self.compose_time(n.start)
            out.append(replace(n, start=start, dur=max(self.compose_time(n.start + n.dur) - start, 0.05)))
        return out

    def imported(self, melody: list) -> list:
        """Eine eigene Melodie (melody_import.load, in Vierteln) in den Schlägen, in denen sie geschrieben wird: im
        6/8-Takt sind drei Achtel ein Schlag, sie wird in Kompositionsschlägen geschrieben."""
        if not self.compound:
            return melody
        out = []
        for start, dur, pitch in melody:
            begin = self.compose_time(start / self.quarters_per_beat)
            out.append((begin, self.compose_time((start + dur) / self.quarters_per_beat) - begin, pitch))
        return out

    # ── Von Hand geänderte Töne ─────────────────────────────────────────────────────
    # Schlüssel und Längen (SongSettings.melody_edits und melody_lengths) zählen in den Schlägen, in denen die Melodie
    # geschrieben wird: im 6/8-Takt in Kompositionsschlägen, sonst im Takt.
    def edit_key(self, beat: float) -> str:
        """Schlüssel des Tons, der auf Schlag beat (im Takt) beginnt."""
        from settings import edit_key
        return edit_key(self.compose_time(beat) if self.compound else beat)

    def edit_length(self, start: float, end: float) -> float:
        """Länge eines Tons von start bis end (Schläge im Takt), wie melody_lengths sie speichert."""
        if not self.compound:
            return end - start
        return self.compose_time(end) - self.compose_time(start)

    def edited_end(self, start: float, length: float) -> float:
        """Ende (Schlag im Takt) eines Tons, der auf start beginnt und length lang ist (melody_lengths)."""
        if not self.compound:
            return start + length
        return self.time(self.compose_time(start) + length)

    # ── Bauplan ─────────────────────────────────────────────────────────────────────
    def plan(self, plan):
        """Der Bauplan mit Sektionen und Akkorden an ihren Plätzen im Takt (für Gesang, Mix und Video)."""
        if self.plain:
            return plan
        import copy
        real = copy.deepcopy(plan)
        real.meter = self.name
        for sec in real.sections:
            sec.start = self.time(sec.start)
            sec.bar_beats = self.bar_beats
            if sec.resume is not None:
                sec.resume = self.time(sec.resume)
            for slot in sec.chords:
                end = self.time(slot.start + slot.dur)
                slot.start = self.time(slot.start)
                slot.dur = end - slot.start
            sec.chords = [slot for slot in sec.chords if slot.dur > 1e-6]
        return real


FOUR = Meter("4/4", 4, 1, 4, 4, 1.0)
THREE = Meter("3/4", 3, 1, 3, 4, 1.0, drop=2)
SIX = Meter("6/8", 4, 2, 6, 8, 1.5)
_ALL = {m.name: m for m in (FOUR, THREE, SIX)}


def get(name: Optional[str]) -> Meter:
    return _ALL.get(name or "4/4", FOUR)


def drum_drop(pattern: dict) -> int:
    """Welcher Schlag im 3/4-Takt herausfällt: der zweite, wenn die Snare (oder der Clap) nur auf der Drei liegt
    (Halftime), sonst der dritte."""
    backbeat = {step for inst, hits in pattern.items() if inst in (38, 39) for step, _ in hits}
    return 1 if 8 in backbeat and 4 not in backbeat and 12 not in backbeat else 2


# ── Rhythmen der Gesangsmelodie im 3/4-Takt ─────────────────────────────────────────
# Einsätze in Sechzehnteln eines 3/4-Takts (0, 4, 8 sind die Schläge), nach Anzahl der Silben im Takt
RHYTHMS_34 = {
    1: [(0,), (2,)],
    2: [(0, 4), (0, 8), (0, 6), (4, 8)],
    3: [(0, 4, 8), (0, 2, 4), (0, 6, 8), (0, 4, 6), (2, 4, 8)],
    4: [(0, 2, 4, 8), (0, 4, 6, 8), (0, 2, 6, 8), (0, 4, 8, 10), (0, 3, 4, 8)],
    5: [(0, 2, 4, 6, 8), (0, 2, 4, 8, 10), (0, 4, 6, 8, 10), (0, 3, 4, 6, 8)],
    6: [(0, 2, 4, 6, 8, 10), (0, 1, 2, 4, 6, 8), (0, 2, 3, 4, 6, 8)],
    7: [(0, 2, 4, 5, 6, 8, 10), (0, 1, 2, 4, 6, 8, 10)],
    8: [(0, 1, 2, 4, 5, 6, 8, 10), (0, 2, 3, 4, 6, 7, 8, 10)],
}
# letzter Takt einer Phrase: alles vor der Drei, dort endet der Schlusston
END_RHYTHMS_34 = {
    1: [(0,)],
    2: [(0, 4), (0, 2)],
    3: [(0, 2, 4), (0, 4, 6), (0, 1, 2)],
    4: [(0, 2, 4, 6), (0, 1, 2, 4)],
    5: [(0, 1, 2, 4, 6), (0, 2, 3, 4, 6)],
    6: [(0, 1, 2, 3, 4, 6), (0, 1, 2, 4, 5, 6)],
}

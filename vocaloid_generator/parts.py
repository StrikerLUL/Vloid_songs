# parts.py – Begleitung: Klavier, Bass, Gitarre, Streicher, Synth, Bläser und die Lead-Hook
#
# Jede Spielweise bekommt eine Sektion und liefert Ereignisse in Schlägen. Akkorde kommen aus dem
# Bauplan, Griffe werden mit Stimmführung verbunden (ctx merkt sich den letzten Griff pro Instrument).
import math
import random
from dataclasses import dataclass

from song_plan import BEATS_PER_BAR, Section, SongPlan
from theory import Chord, nearest_pitch, pitches_in_range, scale_pcs, voice_chord

# Unterspuren mit eigenem Klang (General-MIDI-Programm)
LAYER_PROGRAMS = {"pad": 89, "pizz": 45, "saw": 81, "oohs": 53}


@dataclass
class Ev:
    start: float      # Schlag ab Songanfang
    dur: float
    pitch: int
    vel: int
    layer: str = ""


def _vel(sec: Section, accent: float = 1.0) -> int:
    return max(1, min(127, int((40 + 70 * sec.energy) * accent)))


def _bars(sec: Section):
    for b in range(sec.bars):
        yield b, sec.start + b * BEATS_PER_BAR


def _chord_for(sec: Section, t: float) -> Chord:
    """Akkord für einen Anschlag; die letzte Achtel vor einem Akkordwechsel nimmt den neuen Akkord vorweg."""
    for i, slot in enumerate(sec.chords):
        if slot.start <= t < slot.start + slot.dur:
            offbeat = abs(t - round(t)) > 1e-6
            if offbeat and slot.start + slot.dur - t <= 0.5 + 1e-6 and i + 1 < len(sec.chords):
                return sec.chords[i + 1].chord
            return slot.chord
    return sec.chords[-1].chord


def _pattern_hits(sec: Section, steps: list, length: float = None):
    """(Zeit, Akzent, Dauer) für ein Takt-Muster aus (Sechzehntel, Akzent)-Paaren."""
    for _, bar_start in _bars(sec):
        for i, (step, accent) in enumerate(steps):
            nxt = steps[i + 1][0] if i + 1 < len(steps) else 16
            dur = length if length is not None else (nxt - step) / 4
            yield bar_start + step / 4, accent, dur


def _bass_pitch(pc: int, prev: int = None, lo: int = 28, hi: int = 43) -> int:
    options = pitches_in_range([pc], lo, hi)
    ref = prev if prev is not None else 36
    return min(options, key=lambda p: (abs(p - ref), p))


def _voicing(ctx: dict, key: str, chord: Chord, lo: int, hi: int, n: int, ext: bool = True) -> list:
    v = voice_chord(chord, lo, hi, n, ctx.get(key), include_extensions=ext)
    ctx[key] = v
    return v


# ── Klavier ──────────────────────────────────────────────────────────────────────
def piano(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern == "chords":
        for slot in sec.chords:
            v = _voicing(ctx, "piano", slot.chord, 55, 76, 4)
            hits = [slot.start] + ([slot.start + 2] if slot.dur >= 4 else [])
            for h in hits:
                length = min(2.0, slot.start + slot.dur - h)
                out += [Ev(h, length * 0.95, p, _vel(sec, 0.85)) for p in v]
            root = _bass_pitch(slot.chord.bass_pc, None, 36, 47)
            out += [Ev(slot.start, slot.dur * 0.95, root, _vel(sec, 0.8)), Ev(slot.start, slot.dur * 0.95, root + 12, _vel(sec, 0.7))]
    elif pattern in ("eighths", "stabs"):
        steps = ([(s, (1.0, 0.7, 0.85, 0.7)[s // 2 % 4]) for s in range(0, 16, 2)] if pattern == "eighths"
                 else [(0, 1.0), (3, 0.8), (6, 0.85), (10, 0.85), (12, 0.9)])
        length = 0.42 if pattern == "eighths" else 0.3
        for t, accent, _ in _pattern_hits(sec, steps, length):
            chord = _chord_for(sec, t)
            v = _voicing(ctx, "piano", chord, 60, 79, 3, ext=False)
            top = [v[-1] - 12] if pattern == "eighths" and sec.energy >= 0.8 else []
            out += [Ev(t, length, p, _vel(sec, 0.8 * accent)) for p in v + top]
        for slot in sec.chords:
            root = _bass_pitch(slot.chord.bass_pc, None, 36, 47)
            for beat in range(int(slot.dur)):
                out += [Ev(slot.start + beat, 0.9, root, _vel(sec, 0.7)), Ev(slot.start + beat, 0.9, root + 12, _vel(sec, 0.6))]
    elif pattern in ("arpeggio", "arpeggio16"):
        step = 0.5 if pattern == "arpeggio" else 0.25
        order = [0, 1, 2, 3, 4, 3, 2, 1]
        for slot in sec.chords:
            tones = pitches_in_range(slot.chord.pcs, 57, 86)
            v = _voicing(ctx, "piano", slot.chord, 57, 72, 3, ext=False)
            start = tones.index(min(tones, key=lambda p: abs(p - v[0])))
            ladder = tones[start:start + 5] or tones[-5:]
            t, i = slot.start, 0
            while t < slot.start + slot.dur - 1e-6:
                p = ladder[order[i % len(order)] % len(ladder)]
                accent = 1.0 if abs(t - round(t)) < 1e-6 else 0.75
                out.append(Ev(t, step * 1.6, p, _vel(sec, 0.75 * accent)))
                t += step
                i += 1
            root = _bass_pitch(slot.chord.bass_pc, None, 36, 47)
            for h in range(0, int(slot.dur), 2):
                out.append(Ev(slot.start + h, min(2, slot.dur - h) * 0.95, root, _vel(sec, 0.75)))
                out.append(Ev(slot.start + h, min(2, slot.dur - h) * 0.95, root + 12, _vel(sec, 0.65)))
    elif pattern == "ballad_arp":
        for slot in sec.chords:
            root = _bass_pitch(slot.chord.bass_pc, None, 36, 47)
            third = 3 if slot.chord.is_minor else 4
            figure = [0, 7, 12, 12 + third, 19, 12 + third, 12, 7]
            t, i = slot.start, 0
            while t < slot.start + slot.dur - 1e-6:
                out.append(Ev(t, 1.2, root + figure[i % 8], _vel(sec, 0.7 if i % 2 else 0.8)))
                t += 0.5
                i += 1
            v = _voicing(ctx, "piano", slot.chord, 64, 81, 3)
            out += [Ev(slot.start, slot.dur * 0.98, p, _vel(sec, 0.6)) for p in v]
    elif pattern == "jazz_ch":
        comp = [(0.0, 1.25, 1.0), (1.5, 0.5, 0.75), (2.5, 1.0, 0.9), (3.5, 0.5, 0.8)]
        for _, bar_start in _bars(sec):
            for off, length, accent in comp:
                t = bar_start + off
                chord = _chord_for(sec, t)
                # Griff ohne Grundton (den spielt der Bass), dafür mit der None
                pcs = [pc for pc in chord.pcs if pc != chord.root][:3] + [(chord.root + 2) % 12]
                center = ctx.get("piano_center", 66)
                v = sorted(set(nearest_pitch(pc, round(center)) for pc in pcs))
                ctx["piano_center"] = (sum(v) / len(v) + 66) / 2
                out += [Ev(t, length, p, _vel(sec, 0.75 * accent)) for p in v]
    return out


# ── Bass ─────────────────────────────────────────────────────────────────────────
def bass(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    prev = ctx.get("bass")

    def note(t, length, chord, accent=1.0, octave=0, fifth=False):
        nonlocal prev
        pc = chord.fifth_pc if fifth else chord.bass_pc
        p = _bass_pitch(pc, prev)
        if not fifth:
            prev = p
        out.append(Ev(t, length, p + octave, _vel(sec, 0.9 * accent)))

    if pattern == "root":
        for slot in sec.chords:
            for h in range(0, max(int(slot.dur), 1), 2):
                note(slot.start + h, min(2, slot.dur - h) * 0.95, slot.chord, 0.95, fifth=(h == 2 and slot.dur >= 4))
    elif pattern == "driving":
        for i, slot in enumerate(sec.chords):
            nxt = sec.chords[i + 1].chord if i + 1 < len(sec.chords) else None
            n8 = int(slot.dur * 2)
            for k in range(n8):
                t = slot.start + k * 0.5
                accent = 1.0 if k % 2 == 0 else 0.8
                if k == n8 - 1 and nxt and nxt.bass_pc != slot.chord.bass_pc and rng.random() < 0.6:
                    target = _bass_pitch(nxt.bass_pc, prev)
                    approach = target - 1 if target > prev else target + 1
                    out.append(Ev(t, 0.45, approach, _vel(sec, 0.8)))
                else:
                    note(t, 0.45, slot.chord, accent)
    elif pattern == "sync":
        steps = [(0, 1.0), (3, 0.75), (6, 0.85), (8, 0.95), (11, 0.75), (14, 0.85)]
        for t, accent, dur in _pattern_hits(sec, steps):
            note(t, dur * 0.9, _chord_for(sec, t), accent, octave=12 if abs((t % 4) - 2.75) < 1e-6 else 0)
    elif pattern in ("octaves", "wobble"):
        step = 0.5 if pattern == "octaves" else 0.25
        k = 0
        for _, bar_start in _bars(sec):
            t = bar_start
            while t < bar_start + 4 - 1e-6:
                chord = _chord_for(sec, t)
                up = (k % 2 == 1) if pattern == "octaves" else (k % 4 == 2)
                note(t, step * 0.8, chord, 1.0 if k % 2 == 0 else 0.8, octave=12 if up else 0)
                t += step
                k += 1
    elif pattern == "sub_pulse":
        steps = [(0, 1.0), (2, 0.8), (6, 0.8), (10, 0.8), (14, 0.8)]
        for t, accent, _ in _pattern_hits(sec, steps):
            note(t, 0.4, _chord_for(sec, t), accent)
    elif pattern == "lazy":
        for t, accent, dur in _pattern_hits(sec, [(0, 1.0), (6, 0.7), (10, 0.85)]):
            note(t, dur * 0.85, _chord_for(sec, t), accent, fifth=abs((t % 4) - 2.5) < 1e-6)
    ctx["bass"] = prev
    return out


# ── Gitarre ──────────────────────────────────────────────────────────────────────
def _guitar_shape(chord: Chord) -> list:
    root = _bass_pitch(chord.root, None, 40, 51)
    third = 3 if chord.is_minor else 4
    if chord.quality in ("sus4", "7sus4"):
        third = 5
    elif chord.quality == "sus2":
        third = 2
    shape = [root, root + 7, root + 12, root + 12 + third, root + 19, root + 24]
    if chord.quality in ("7", "m7", "maj7"):
        shape[5] = root + 12 + chord.intervals[3]
    return shape


def guitar(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    spb = plan.seconds_per_beat
    strum_gap = 0.007 / spb    # 7 ms zwischen den Saiten, in Schlägen
    if pattern == "strummed":
        steps = [(0, "D", 1.0), (4, "D", 0.8), (6, "U", 0.7), (10, "U", 0.7), (12, "D", 0.9), (14, "U", 0.7)]
        for _, bar_start in _bars(sec):
            for i, (step, direction, accent) in enumerate(steps):
                t = bar_start + step / 4
                nxt = steps[i + 1][0] if i + 1 < len(steps) else 16
                length = (nxt - step) / 4 * 0.9
                shape = _guitar_shape(_chord_for(sec, t))
                strings = shape if direction == "D" else list(reversed(shape[2:]))
                for k, p in enumerate(strings):
                    out.append(Ev(t + k * strum_gap, length, p, _vel(sec, 0.72 * accent)))
    elif pattern == "palm_mute":
        for _, bar_start in _bars(sec):
            for k in range(8):
                t = bar_start + k * 0.5
                shape = _guitar_shape(_chord_for(sec, t))
                notes = shape[:3] if sec.energy >= 0.7 else shape[:2]
                accent = 1.0 if k % 2 == 0 else 0.8
                out += [Ev(t, 0.28, p, _vel(sec, 0.78 * accent)) for p in notes]
    elif pattern == "power_chords":
        hits = [(0.0, 1.9, 1.0), (2.0, 1.4, 0.9), (3.5, 0.45, 0.85)]
        for _, bar_start in _bars(sec):
            for off, length, accent in hits:
                t = bar_start + off
                shape = _guitar_shape(_chord_for(sec, t))
                out += [Ev(t + k * strum_gap, length, p, _vel(sec, 0.8 * accent)) for k, p in enumerate(shape[:3])]
    elif pattern == "chill_riff":
        order = [0, 2, 1, 3, 2, 4, 3, 5]
        for _, bar_start in _bars(sec):
            for k in range(8):
                t = bar_start + k * 0.5
                shape = _guitar_shape(_chord_for(sec, t))
                out.append(Ev(t, 0.9, shape[order[k]], _vel(sec, 0.62 if k % 2 else 0.7)))
    elif pattern == "cutting":
        for _, bar_start in _bars(sec):
            for k in range(8):
                t = bar_start + k * 0.5
                chord = _chord_for(sec, t)
                v = _voicing(ctx, "guitar", chord, 62, 77, 3, ext=False)
                accent = 1.0 if k % 2 else 0.55
                out += [Ev(t + j * strum_gap, 0.14, p, _vel(sec, 0.7 * accent)) for j, p in enumerate(v)]
    return out


# ── Streicher ────────────────────────────────────────────────────────────────────
def strings(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern == "legato":
        for slot in sec.chords:
            v = _voicing(ctx, "strings", slot.chord, 55, 81, 4)
            out += [Ev(slot.start, slot.dur, p, _vel(sec, 0.72)) for p in v]
            if sec.energy >= 0.6:
                out.append(Ev(slot.start, slot.dur, _bass_pitch(slot.chord.bass_pc, None, 43, 54), _vel(sec, 0.65)))
    elif pattern == "build":
        total = sec.beats
        for slot in sec.chords:
            v = _voicing(ctx, "strings", slot.chord, 60, 81, 3, ext=False)
            step = 0.25 if slot.start - sec.start >= total - 8 else 0.5
            t = slot.start
            while t < slot.start + slot.dur - 1e-6:
                progress = (t - sec.start) / total
                out += [Ev(t, step * 0.8, p, _vel(sec, 0.45 + 0.55 * progress)) for p in v]
                t += step
    elif pattern == "pizzicato":
        for _, bar_start in _bars(sec):
            for k in range(4):
                t = bar_start + k
                v = _voicing(ctx, "strings", _chord_for(sec, t), 55, 79, 3, ext=False)
                out.append(Ev(t, 0.3, v[k % 3], _vel(sec, 0.8), layer="pizz"))
    elif pattern == "staccato":
        for _, bar_start in _bars(sec):
            for k in range(8):
                t = bar_start + k * 0.5
                v = _voicing(ctx, "strings", _chord_for(sec, t), 55, 79, 3, ext=False)
                out += [Ev(t, 0.25, p, _vel(sec, 0.75 if k % 2 == 0 else 0.6)) for p in v]
    return out


# ── Synth ────────────────────────────────────────────────────────────────────────
def synth(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern == "pad":
        for slot in sec.chords:
            v = _voicing(ctx, "pad", slot.chord, 55, 79, 4)
            out += [Ev(slot.start, slot.dur, p, _vel(sec, 0.7), layer="pad") for p in v]
    elif pattern in ("arp", "riser"):
        order = [0, 1, 2, 3, 1, 2, 3, 4]
        k = 0
        for slot in sec.chords:
            tones = pitches_in_range(slot.chord.triad_pcs, 64, 91)
            t = slot.start
            while t < slot.start + slot.dur - 1e-6:
                if pattern == "arp":
                    p = tones[order[k % 8] % len(tones)]
                    accent = 1.0 if k % 2 == 0 else 0.7
                else:
                    progress = (t - sec.start) / sec.beats
                    p = tones[min(int(progress * len(tones)) + k % 3, len(tones) - 1)]
                    accent = 0.4 + 0.6 * progress
                out.append(Ev(t, 0.2, p, _vel(sec, 0.7 * accent)))
                t += 0.25
                k += 1
    elif pattern in ("pluck", "staccato_pluck"):
        steps = [(2, 1.0), (6, 0.9), (10, 1.0), (14, 0.9)] if pattern == "pluck" else \
                [(2, 1.0), (3, 0.6), (6, 0.9), (7, 0.6), (10, 1.0), (11, 0.6), (14, 0.9), (15, 0.6)]
        for t, accent, _ in _pattern_hits(sec, steps, 0.2):
            v = _voicing(ctx, "synth", _chord_for(sec, t), 64, 84, 3, ext=False)
            out += [Ev(t, 0.2, p, _vel(sec, 0.7 * accent)) for p in v]
    elif pattern == "wide_saw":
        for slot in sec.chords:
            v = _voicing(ctx, "synth", slot.chord, 60, 84, 4)
            out += [Ev(slot.start, slot.dur * 0.98, p, _vel(sec, 0.65)) for p in v]
    elif pattern == "supersaw":
        # breite Akkordfläche im Refrain, oben mit der Oktave des Spitzentons
        for slot in sec.chords:
            v = _voicing(ctx, "saw", slot.chord, 60, 79, 4)
            out += [Ev(slot.start, slot.dur * 0.98, p, _vel(sec, 0.6), layer="saw") for p in v + [v[-1] + 12]]
    return out


# ── Bläser ───────────────────────────────────────────────────────────────────────
def brass(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern == "stabs":
        figures = ([(0.0, 0.45, 1.0), (1.5, 0.4, 0.85), (2.5, 0.9, 0.95)], [(0.0, 1.9, 0.9), (3.5, 0.45, 0.9)])
        for b, bar_start in _bars(sec):
            for off, length, accent in figures[b % 2]:
                t = bar_start + off
                v = _voicing(ctx, "brass", _chord_for(sec, t), 58, 79, 3, ext=False)
                out += [Ev(t, length, p, _vel(sec, 0.78 * accent)) for p in v]
    elif pattern == "accents":
        for b, bar_start in _bars(sec):
            if b % 4 == 0:
                v = _voicing(ctx, "brass", _chord_for(sec, bar_start), 58, 79, 3, ext=False)
                out += [Ev(bar_start, 1.0, p, _vel(sec, 0.85)) for p in v]
    return out


# ── Glocken: Glockenspiel, Celesta, Spieluhr oder Vibraphon über der Band ───────
def bells(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern in ("sparkle", "sparkle16"):
        step = 0.5 if pattern == "sparkle" else 0.25
        order = [0, 2, 1, 3, 2, 4, 3, 1]
        k = 0
        for slot in sec.chords:
            tones = pitches_in_range(slot.chord.triad_pcs, 76, 96)
            t = slot.start
            while t < slot.start + slot.dur - 1e-6:
                accent = 1.0 if abs(t - round(t)) < 1e-6 else 0.7
                out.append(Ev(t, step * 1.5, tones[order[k % 8] % len(tones)], _vel(sec, 0.6 * accent)))
                t += step
                k += 1
    elif pattern == "hook_octave":
        # verdoppelt die Gesangsmelodie eine Oktave höher, wie das Glockenspiel im Schlussrefrain
        for n in _vocal_in(sec, ctx):
            p = n.pitch + 12
            while p < 74:
                p += 12
            out.append(Ev(n.start, min(n.dur, 1.5), p, _vel(sec, 0.7)))
    elif pattern == "accents":
        for slot in sec.chords:
            tones = pitches_in_range(slot.chord.triad_pcs, 76, 93)
            out += [Ev(slot.start, 2.0, p, _vel(sec, 0.6)) for p in tones[-2:]]
    elif pattern == "music_box":
        figure = [0, 2, 1, 3]
        for slot in sec.chords:
            tones = pitches_in_range(slot.chord.triad_pcs, 72, 91)
            for i in range(int(slot.dur)):
                out.append(Ev(slot.start + i, 1.4, tones[figure[i % 4] % len(tones)], _vel(sec, 0.62)))
    return out


# ── Chor: Aahs und Oohs als Fläche ───────────────────────────────────────────────
def choir(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    if pattern in ("aahs", "oohs"):
        layer, accent = ("", 0.62) if pattern == "aahs" else ("oohs", 0.55)
        for slot in sec.chords:
            v = _voicing(ctx, "choir", slot.chord, 57, 76, 4, ext=False)
            out += [Ev(slot.start, slot.dur, p, _vel(sec, accent), layer=layer) for p in v]
    return out


# ── Gegenstimme: antwortet in den Gesangspausen, Leitton-Linie oder Solo ─────────
HELD_NOTE, HELD_NOTE_LANDING = 1.5, 0.5   # ab dieser Länge (Schläge) darf die Gegenstimme nach der Landung einsetzen
def _vocal_in(sec: Section, ctx: dict) -> list:
    return [n for n in ctx.get("vocal", []) if sec.start <= n.start < sec.end]


def _ladder(sec: Section, chord: Chord, lo: int, hi: int) -> list:
    """Töne, die über chord gut klingen: Akkordtöne und Leitertöne ohne Halbton-Reibung mit dem Akkord."""
    scale = set(scale_pcs(sec.tonic, sec.mode))
    foreign = set(chord.pcs) - scale                 # z. B. das Gis im E-Dur-Akkord von a-Moll
    pcs = {pc for pc in scale if (pc - 1) % 12 not in chord.pcs and (pc + 1) % 12 not in foreign}
    pcs |= set(chord.pcs)
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def _fit(p: int, ladder: list, direction: int) -> int:
    """p, oder der nächste Ton der Leiter in Laufrichtung, falls p dort nicht vorkommt."""
    if p in ladder:
        return p
    return min(ladder, key=lambda q: (abs(q - p), -direction * (q - p)))


def _gaps(sec: Section, vocal: list, min_len: float) -> list:
    """
    Stellen, an denen eine Gegenstimme antworten kann: Pausen im Gesang und lange Schlusstöne, sobald
    der Gesang auf ihnen angekommen ist. Mindestens min_len Schläge lang.
    """
    edges, t = [], sec.start
    for n in sorted(vocal, key=lambda n: n.start):
        if n.start - t >= min_len:
            edges.append((t, n.start))
        busy = n.start + (HELD_NOTE_LANDING if n.dur >= HELD_NOTE else n.dur)
        t = max(t, busy)
    if sec.end - t >= min_len:
        edges.append((t, sec.end))
    return edges


ANSWER_RHYTHMS = ([0.25, 0.25, 0.5], [0.5, 0.5], [0.25, 0.25, 0.25, 0.25], [0.5, 0.5, 1.0],
                  [0.25, 0.25, 0.5, 1.0], [0.5, 0.25, 0.25, 0.5, 1.0], [0.75, 0.25, 1.0], [0.25, 0.25, 0.25, 0.25, 1.0])


def counter(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    vocal = _vocal_in(sec, ctx)
    center = plan.style.vocal_center
    if pattern == "solo" and vocal:
        pattern = "answer"          # ein Solo nur, wenn niemand singt
    if pattern == "answer":
        prev = ctx.get("counter", center + 5)
        for lo, hi in _gaps(sec, vocal, 1.25):
            start = math.ceil(lo * 4 - 1e-6) / 4
            room = hi - 0.25 - start
            fitting = [r for r in ANSWER_RHYTHMS if sum(r) <= room]
            if not fitting:
                continue
            longest = max(sum(r) for r in fitting)
            rhythm = rng.choice([r for r in fitting if sum(r) >= longest - 1.0])
            end_chord = sec.chord_at(start + sum(rhythm) - rhythm[-1])
            ladder = _ladder(sec, end_chord, center - 3, center + 14)
            target = min((p for p in ladder if p % 12 in end_chord.triad_pcs), key=lambda p: abs(p - prev))
            steps = len(rhythm) - 1
            direction = 1 if rng.random() < 0.5 else -1
            i_target = ladder.index(target)
            i = max(0, min(len(ladder) - 1, i_target - direction * steps))
            t = start
            for k, d in enumerate(rhythm):
                if k == len(rhythm) - 1:
                    p = target
                else:
                    # Durchgangstöne laufen auf das Ziel zu, passen aber zum Akkord, der gerade klingt
                    p = ladder[max(0, min(len(ladder) - 1, i + direction * k))]
                    p = _fit(p, _ladder(sec, sec.chord_at(t), center - 3, center + 14), direction)
                out.append(Ev(t, d * 0.92, p, _vel(sec, 0.78 if k == 0 else 0.7)))
                t += d
            prev = target
        ctx["counter"] = prev
    elif pattern == "guide":
        # Terzen und Septimen der Akkorde, schrittweise verbunden, unter dem Gesang
        prev = ctx.get("guide", center - 7)
        for slot in sec.chords:
            guide = [slot.chord.pcs[1]] + ([slot.chord.pcs[3]] if len(slot.chord.pcs) > 3 else [slot.chord.fifth_pc])
            halves = [slot.dur] if slot.dur < 4 else [slot.dur / 2, slot.dur / 2]
            t = slot.start
            for h, length in enumerate(halves):
                options = pitches_in_range([guide[h % len(guide)]], center - 14, center - 1)
                p = min(options, key=lambda q: (abs(q - prev), q))
                out.append(Ev(t, length * 0.97, p, _vel(sec, 0.66)))
                prev, t = p, t + length
        ctx["guide"] = prev
    elif pattern == "solo":
        rhythms = ([0.5] * 8, [0.25] * 4 + [0.5] * 6, [1.0, 0.5, 0.5, 0.25, 0.25, 0.5, 1.0], [0.75, 0.25] * 4)
        prev = ctx.get("counter", center + 5)
        for b, bar_start in _bars(sec):
            last_bar = b == sec.bars - 1
            rhythm = [4.0] if last_bar else rng.choice(rhythms)
            t, direction = bar_start, rng.choice((-1, 1))
            for k, d in enumerate(rhythm):
                chord = sec.chord_at(t)
                ladder = _ladder(sec, chord, center - 3, center + 17)
                if k == 0 or abs(t - round(t)) < 1e-6 and int(round(t)) % 2 == 0:
                    p = min((q for q in ladder if q % 12 in chord.triad_pcs), key=lambda q: abs(q - prev))
                else:
                    i = min(range(len(ladder)), key=lambda j: abs(ladder[j] - prev))
                    if not 0 <= i + direction < len(ladder):
                        direction = -direction
                    p = ladder[i + direction]
                out.append(Ev(t, d * 0.9, p, _vel(sec, 0.8 if k == 0 else 0.7)))
                prev, t = p, t + d
        ctx["counter"] = prev
    return out


# ── Percussion: Shaker, Claps, Tamburin, Congas, Cowbell ─────────────────────────
SHAKER, CLAPS, TAMB, COWBELL, CONGA_MUTE, CONGA_OPEN, CONGA_LOW = 82, 39, 54, 56, 62, 63, 64
PERC_PATTERNS = {
    "shaker": [(s, SHAKER, 0.62 if s % 4 == 2 else 0.42 if s % 2 == 0 else 0.3) for s in range(16)],
    "claps": [(4, CLAPS, 0.85), (12, CLAPS, 0.85)],
    "tambourine": [(s, TAMB, 0.7 if s in (4, 12) else 0.45) for s in range(0, 16, 2)],
    "congas": [(0, CONGA_LOW, 0.8), (3, CONGA_OPEN, 0.65), (6, CONGA_MUTE, 0.55), (8, CONGA_LOW, 0.7),
               (10, CONGA_OPEN, 0.7), (11, CONGA_OPEN, 0.5), (14, CONGA_MUTE, 0.55)],
    "cowbell": [(s, COWBELL, 0.6 if s % 8 == 0 else 0.45) for s in range(0, 16, 4)],
}


def perc(pattern: str, sec: Section, plan: SongPlan, rng: random.Random, ctx: dict) -> list:
    out = []
    steps = PERC_PATTERNS.get(pattern, [])
    for _, bar_start in _bars(sec):
        for step, pitch, accent in steps:
            out.append(Ev(bar_start + step / 4, 0.2, pitch, _vel(sec, accent)))
    return out


# ── Lead: spielt den Refrain-Hook im Intro und Outro ─────────────────────────────
def lead_hook(sec: Section, plan: SongPlan, vocal_notes: list) -> list:
    chorus = next((s for s in plan.sections if s.kind == "Chorus" and s.has_vocals), None)
    if chorus is None:
        return []
    shift = (sec.tonic - chorus.tonic + 6) % 12 - 6
    chorus_notes = [n for n in vocal_notes if chorus.start <= n.start < chorus.end]
    if not chorus_notes:
        return []
    half = min(sec.bars, chorus.bars) * BEATS_PER_BAR / 2
    if sec.kind == "Outro" and chorus.bars * BEATS_PER_BAR > 2 * half:
        windows = [(0.0, half, 0.0), (chorus.beats - half, chorus.beats, half)]
    else:
        windows = [(0.0, 2 * half, 0.0)]
    out = []
    for lo, hi, target in windows:
        for n in chorus_notes:
            rel = n.start - chorus.start
            if lo <= rel < hi:
                out.append(Ev(sec.start + target + rel - lo, n.dur * 0.95, n.pitch + shift, _vel(sec, 0.85)))
    return out


PARTS = {"piano": piano, "bass": bass, "guitar": guitar, "strings": strings, "synth": synth, "brass": brass,
         "bells": bells, "choir": choir, "counter": counter, "perc": perc}

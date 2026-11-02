"""Musikalischer Zusammenhang: vollständige Notendauern, Phrasen und gelernte Vorlieben.

Alle Zeiten sind Schläge. Keine Audio-Engine und kein Zufall: dieselbe Partitur wird immer gleich geprüft.
"""
import math
from dataclasses import replace

from theory import scale_pcs


def local_scale(section, chord) -> set:
    pcs = set(scale_pcs(section.tonic, section.mode))
    for pc in chord.pcs:
        if pc not in pcs:
            pcs -= {(pc - 1) % 12, (pc + 1) % 12}
            pcs.add(pc)
    return pcs


def slices(plan, note):
    """Jeder tatsächlich klingende Akkord unter einer Note, einschließlich Sektionsgrenzen."""
    end = note.start + note.dur
    for section in plan.sections:
        if section.end <= note.start or section.start >= end:
            continue
        for slot in section.chords:
            start, stop = max(note.start, slot.start), min(end, slot.start + slot.dur)
            if stop > start + 1e-7:
                # Ein vorgezogener Einsatz meint den Akkord auf der nächsten Eins.
                if getattr(note, "pushed", False) and stop <= note.start + 0.25 + 1e-7:
                    yield start, stop, section, plan.chord_at(note.start + 0.25)
                else:
                    yield start, stop, section, slot.chord


def tone_cost(pitch, section, chord) -> float:
    pc = pitch % 12
    if pc in chord.pcs:
        return 0.0
    if pc not in local_scale(section, chord):
        return 2.0
    # Diatonische Durchgänge sind leichter als chromatische Reibungen. Eine Sekunde zum Bass bleibt hörbar.
    return 0.8 if (pc - chord.bass_pc) % 12 in (1, 11) else 0.3


def intentional(note, chord, following=None) -> bool:
    if not getattr(note, "tension", False):
        return False
    degree = (note.pitch - chord.root) % 12
    color = degree in (2, 11) and chord.quality in ("maj", "maj7", "add9", "maj9", "6")
    resolved = following is not None and abs(following.pitch - note.pitch) <= 2 \
        and following.pitch % 12 in chord.pcs \
        and following.start - (note.start + note.dur) < 0.26
    return color or resolved


def harmony_scores(notes, plan) -> dict:
    ordered = sorted(notes, key=lambda n: n.start)
    total = sum(n.dur for n in ordered) or 1.0
    cost, unresolved = 0.0, 0.0
    for i, note in enumerate(ordered):
        following = ordered[i + 1] if i + 1 < len(ordered) else None
        for start, end, sec, chord in slices(plan, note):
            value = tone_cost(note.pitch, sec, chord)
            if intentional(note, chord, following):
                value *= 0.15
            elif note.dur >= 1 and note.pitch % 12 not in chord.pcs:
                value += 0.4
            cost += (end - start) * value
        if getattr(note, "tension", False) and not intentional(note, plan.chord_at(note.start), following):
            unresolved += note.dur
    return {"harmony": 1.0 - cost / total, "resolution": 1.0 - unresolved / total}


def fit_harmony(plan, notes) -> list:
    """Ungewollte lange Reibungen korrigieren; gebundene Vokale erhalten den Text beim Akkordwechsel."""
    from lyrics import Mora
    ordered = sorted(notes, key=lambda n: n.start)
    out = []
    lo, hi = plan.vocal_range
    for i, note in enumerate(ordered):
        following = ordered[i + 1] if i + 1 < len(ordered) else None
        pieces = list(slices(plan, note))
        if not pieces:
            out.append(note)
            continue
        # Erst teilen, wenn die Fortsetzung außerhalb der lokalen Skala liegt oder lange instabil klingt.
        changes = [j for j, (a, b, sec, chord) in enumerate(pieces)
                   if not intentional(note, chord, following)
                   and (tone_cost(note.pitch, sec, chord) >= 1.8
                        or (b - a >= 0.75 and note.pitch % 12 not in chord.pcs))]
        if not changes:
            out.append(note)
            continue
        current = note
        for j, (a, b, sec, chord) in enumerate(pieces):
            pitch = note.pitch
            if j in changes:
                options = [p for p in range(max(lo, pitch - 5), min(hi, pitch + 5) + 1) if p % 12 in chord.pcs]
                if options:
                    previous = out[-1].pitch if out else pitch
                    pitch = min(options, key=lambda p: (abs(p - pitch) + 0.15 * abs(p - previous), p))
            if j == 0:
                current = replace(note, start=a, dur=b - a, pitch=pitch,
                                  tension=getattr(note, "tension", False) and pitch == note.pitch)
                out.append(current)
            elif pitch == current.pitch:
                current.dur += b - a
            else:
                syllable = Mora(str(note.syllable or "ら"), melisma=True)
                current = replace(note, start=a, dur=b - a, pitch=pitch, syllable=syllable,
                                  strong=False, pushed=False, tension=False)
                out.append(current)
    return out


def split_text(items, count) -> list:
    """Phrasengrenzen an Zeilen und Wörtern; keine künstlichen Textwiederholungen."""
    items = list(items)
    if not items:
        return [[]]
    count = max(1, min(count, len(items)))
    explicit = [i for i in range(1, len(items)) if getattr(items[i], "line_start", False)]
    words = [i for i in range(1, len(items)) if getattr(items[i], "word_start", False)]
    # Ohne Wortanalyse (z. B. einzelne Kana) ist jede Silbengrenze eine mögliche Grenze.
    boundaries = sorted(set(explicit + words)) or list(range(1, len(items)))
    cuts, previous = [], 0
    for p in range(1, count):
        available = [i for i in boundaries if previous < i < len(items)]
        if not available:
            break
        target = len(items) * p / count
        cut = min(available, key=lambda i: (abs(i - target) - (1.5 if i in explicit else 0), i))
        cuts.append(cut)
        previous = cut
    return [items[a:b] for a, b in zip([0] + cuts, cuts + [len(items)]) if b > a]


def phrase_path(writer, slots, phrase_start, role, previous, reference, words) -> list:
    """Begrenzte Suche über ganze Phrasen statt einer unwiderruflichen lokalen Tonwahl."""
    from melody_writer import CONTOURS, STEPS_PER_BEAT, accent_moves
    total = max(slots[-1].step + slots[-1].dur, 1)
    offsets = writer._gesture_offsets(slots, role)
    contour = CONTOURS.get(role, CONTOURS["A"])
    accents = accent_moves(words or []) + [0] * len(slots)
    refs = {s.step: p for s, p in reference} if reference else {}
    end_chord = writer._chord_at_step(phrase_start, slots[-1].step)
    end_pcs = writer._ending_pcs(role, end_chord)
    goals = [p for p in range(writer.lo, writer.hi + 1) if p % 12 in end_pcs]
    beams = [(0.0, [], previous, 0)]
    for i, slot in enumerate(slots):
        chord = writer._chord_at_step(phrase_start, slot.step)
        options = writer._candidates(chord, slot.strong)
        if slot.last:
            options = [p for p in options if p % 12 in end_pcs] or options
        target = writer.center + (contour(slot.step / total) + offsets[i]) * \
            (writer.char.contour if writer.char else 1.0)
        expanded = []
        for cost, path, prev, move in beams:
            for pitch in options:
                value = abs(pitch - target) * 0.28
                if prev is not None:
                    delta = pitch - prev
                    value += writer.costs[min(abs(delta), len(writer.costs) - 1)]
                    if delta == 0:
                        value += 0.4 + (1.2 if len(path) > 1 and path[-2] == pitch else 0)
                    if abs(move) >= 5 and delta * move > 0:
                        value += 1.5
                    if accents[i] and delta * accents[i] < 0:
                        value += 1.0
                else:
                    delta = 0
                if slot.step in refs:
                    value += abs(pitch - refs[slot.step]) * 0.4
                if goals:
                    remaining = max(1, len(slots) - i - 1)
                    value += max(0, min(abs(pitch - g) for g in goals) - 2 * remaining) * 0.7
                if pitch % 12 not in chord.pcs:
                    value += 0.15
                expanded.append((cost + value, path + [pitch], pitch, delta))
        # Verschiedene Endzustände erhalten, damit die Suche nicht zwölf Kopien desselben Pfads behält.
        unique = {}
        for beam in sorted(expanded, key=lambda b: (b[0], b[1])):
            key = (beam[2], beam[3], tuple(beam[1][-3:]))
            unique.setdefault(key, beam)
            if len(unique) == 12:
                break
        beams = list(unique.values())
        if not beams:
            return []
    return min(beams, key=lambda b: (b[0], b[1]))[1]


def melody_features(notes) -> dict:
    """Transpositionsunabhängige, grobe Merkmale für persönliche Vorlieben."""
    sung = sorted((n for n in notes if not getattr(n.syllable, "melisma", False)), key=lambda n: n.start)
    if len(sung) < 2:
        return {}
    moves = [b.pitch - a.pitch for a, b in zip(sung, sung[1:])]
    duration = max(n.start + n.dur for n in sung) - sung[0].start
    contour = sum(moves[:max(1, len(moves) // 2)])
    return {"density": min(7, round(len(sung) / max(duration, 1) * 2)),
            "range": (max(n.pitch for n in sung) - min(n.pitch for n in sung)) // 3,
            "steps": round(sum(1 <= abs(m) <= 2 for m in moves) / len(moves) * 4),
            "repeats": round(sum(m == 0 for m in moves) / len(moves) * 4),
            "rhythm": ",".join(str(min(8, round(n.dur * 4))) for n in sung[:8]),
            "opening": ",".join(str(max(-7, min(7, m))) for m in moves[:4]),
            "contour": (contour > 0) - (contour < 0)}


def preference(notes, kind, taste) -> float:
    if taste is None:
        return 0.0
    features = melody_features(notes)
    if not features:
        return 0.0
    return sum(math.log(taste.weight(("melody", kind, key, value))) for key, value in features.items()) / len(features)


def final_variation(plan, section, notes, before, finish=None) -> list:
    """Ein höherer langer Zielton ist ein Kandidat, keine Pflicht für den letzten Ton des Songs."""
    import melody_score
    if not notes:
        return notes
    candidate = [replace(n) for n in notes]
    last_phrase = section.end - min(4, section.bars) * section.bar_beats
    eligible = [n for n in candidate if n.start >= last_phrase and n.dur >= 0.75
                and not getattr(n.syllable, "melisma", False)]
    if not eligible:
        return notes
    target = max(eligible, key=lambda n: (n.dur, n.strong, -n.start))
    chord = plan.chord_at(target.start)
    higher = [p for p in range(target.pitch + 1, min(plan.vocal_range[1], target.pitch + 3) + 1)
              if p % 12 in chord.pcs]
    if not higher:
        return notes
    target.pitch = higher[0]
    if finish is not None:
        candidate = finish(candidate)
    def value(found):
        return melody_score.score(found, "Chorus", before, plan.vocal_range[1], section.bar_beats,
                                  extras=("catchy_chorus",), plan=plan)
    return candidate if value(candidate) > value(notes) + 0.05 else notes

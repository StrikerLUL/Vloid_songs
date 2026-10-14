# backing_vocals.py – Begleitstimmen wie in Produktionen, von NEUTRINO gesungen
#
#   Harmonien mit Abwechslung (C5): der erste Refrain singt die Terz nur auf den Phrasenenden, mittlere Refrains die
#       Terz darunter, der letzte die volle Terz darüber; passt die ganze Melodie eine Oktave höher oder tiefer in die
#       Stimmlage, singt im letzten Refrain zusätzlich die Oktave mit. Die Doppelung links und rechts singt
#       pipeline._sing_harmony.
#   Gesungene Flächen (C4): drei Stimmen singen im Refrain die Akkordtöne auf „う“ (im letzten Refrain „あ“) statt
#       des Keyboard-Chors.
#   Ad-libs (C3): im letzten Refrain kurze Rufe (いぇー, おー) und Echo-Antworten (die letzten Silben der Zeile davor)
#       in den Lücken des Gesangs.
# Alles als melody_data (Tonhöhe oder None, Dauer in Schlägen) ab Songanfang, mit den Silben dazu.
from lyrics import Mora
from melody_writer import MelNote, harmony_line, melody_data

PAD_VOICES = 3
PAD_SYLLABLE = "う"
FINAL_PAD_SYLLABLE = "あ"
PAD_RANGE = 10               # Halbtöne über dem tiefsten Ton der Stimme, in denen die Flächen liegen
ADLIB_GAP = 1.0              # Schläge Lücke im Gesang, ab der ein Ad-lib hineinpasst
ADLIB_OVERLAP = 0.5          # so weit darf ein Ad-lib in die nächste Zeile hineinklingen (leiser, zur Seite)
MAX_ADLIBS = 4
CALLS = (("いぇ", "え"), ("お", "お"), ("あ", "あ"))     # Ruf: Silbe, dann ihr Vokal gehalten einen Ton tiefer


def notes_of(melody_data_: list, silben: list) -> list:
    """melody_data und Silben zurück in MelNotes."""
    out, t, i = [], 0.0, 0
    for pitch, dur in melody_data_:
        if pitch is not None:
            out.append(MelNote(t, dur, int(pitch), silben[i] if i < len(silben) else "ら"))
            i += 1
        t += dur
    return out


def choruses(plan) -> list:
    return [sec for sec in plan.sections if sec.kind == "Chorus" and sec.has_vocals]


def harmony_modes(plan) -> dict:
    """Art der Harmonie je Refrain: erster nur Phrasenenden, mittlere Terz darunter, letzter Terz darüber."""
    found = choruses(plan)
    modes = {}
    for k, sec in enumerate(found):
        modes[sec.start] = "above" if k == len(found) - 1 else ("ends" if k == 0 else "below")
    return modes


def octave(plan, notes: list) -> list:
    """Die Melodie des letzten Refrains eine Oktave höher oder tiefer, wenn sie ganz in die Stimmlage passt."""
    found = choruses(plan)
    if not found:
        return []
    sec = found[-1]
    mine = [n for n in notes if sec.start <= n.start < sec.end]
    if not mine:
        return []
    lo, hi = plan.vocal_range
    for step in (12, -12):
        if all(lo - 3 <= n.pitch + step <= hi + 3 for n in mine):
            return [MelNote(n.start, n.dur, n.pitch + step, n.syllable, n.strong) for n in mine]
    return []


def pads(plan) -> list:
    """Drei Linien mit den Akkordtönen der Refrains, jede ein [MelNote]."""
    from theory import voice_chord
    found = choruses(plan)
    lo = plan.vocal_range[0]
    lines = [[] for _ in range(PAD_VOICES)]
    for k, sec in enumerate(found):
        syllable = FINAL_PAD_SYLLABLE if k == len(found) - 1 and len(found) > 1 else PAD_SYLLABLE
        start = sec.resume if sec.feel == "breakdown" and sec.resume is not None else sec.start
        previous = None
        for slot in sec.chords:
            a, b = max(slot.start, start), min(slot.start + slot.dur, sec.end)
            if b - a < 0.5:
                continue
            previous = voice_chord(slot.chord, lo, lo + PAD_RANGE, PAD_VOICES, previous, include_extensions=False)
            for line, pitch in zip(lines, sorted(previous)):
                line.append(MelNote(a, b - a, pitch, syllable))
    return lines


def adlibs(plan, notes: list) -> list:
    """Rufe und Echo-Antworten in den Lücken des letzten Refrains, abwechselnd."""
    found = choruses(plan)
    if not found:
        return []
    sec = found[-1]
    lo, hi = plan.vocal_range
    mine = sorted((n for n in notes if sec.start <= n.start < sec.end), key=lambda n: n.start)
    out, made = [], 0
    for k, (n, nxt) in enumerate(zip(mine, mine[1:] + [None])):
        gap_start = n.start + n.dur
        gap_end = nxt.start if nxt is not None else sec.end
        if gap_end - gap_start < ADLIB_GAP or made >= MAX_ADLIBS:
            continue
        chord = sec.chord_at(gap_start)
        made += 1
        room = gap_end - gap_start + ADLIB_OVERLAP
        if made % 2 == 1:
            phrase = [m for m in mine[:k + 1] if m.start >= n.start - 4.0][-2:]
            t = gap_start + 0.25
            for m in phrase:
                dur = min(m.dur, (room - 0.25) / len(phrase), 0.75)
                out.append(MelNote(t, dur, m.pitch, m.syllable))
                t += dur
        else:
            first, held = CALLS[(made // 2 - 1) % len(CALLS)]
            top = max((p for p in range(hi - 4, hi + 1) if p % 12 in chord.pcs), default=hi - 2)
            low = max((p for p in range(top - 5, top - 1) if p % 12 in chord.pcs), default=top - 2)
            out.append(MelNote(gap_start, 0.5, top, first))
            out.append(MelNote(gap_start + 0.5, min(1.0, room - 0.5), low, Mora(held, melisma=True)))
    for n in out:
        n.dur = min(n.dur, plan.total_beats - n.start)
    return [n for n in out if n.dur > 0.1 and lo - 3 <= n.pitch]


def add(tracks: dict, settings) -> None:
    """Die Begleitstimmen zu den Spuren eines komponierten Songs: harmony_data/-silben (mit Abwechslung),
    octave_data/-silben, pads [(Daten, Silben)] und adlib_data/-silben, jeweils nur mit ihrem Schalter."""
    plan = tracks.get("plan")
    if plan is None or not tracks.get("melody_data"):
        return
    notes = notes_of(tracks["melody_data"], tracks.get("silben", []))
    if getattr(settings, "harmony_variety", False):
        tracks["harmony_data"], tracks["harmony_silben"] = melody_data(harmony_line(plan, notes,
                                                                                     modes=harmony_modes(plan)))
        tracks["octave_data"], tracks["octave_silben"] = melody_data(octave(plan, notes))
    if getattr(settings, "sung_pads", False):
        tracks["pads"] = [melody_data(line) for line in pads(plan) if line]
    if getattr(settings, "adlibs", False):
        tracks["adlib_data"], tracks["adlib_silben"] = melody_data(adlibs(plan, notes))

"""Gemeinsames rhythmisches Fundament und Platz für die führende Stimme."""
from collections import defaultdict


def rhythm(section, drums) -> dict:
    """Die tatsächlich gespielten Kicks, einschließlich des Timings echter Grooves."""
    kicks = sorted({round(e.start, 6): e.vel for e in drums
                    if e.pitch in (35, 36) and section.start <= e.start < section.end}.items())
    return {"kicks": kicks, "anchors": [s.start for s in section.chords]}


def bass_line(pattern, section, plan, context) -> list:
    from parts import Ev, _bass_pitch, _vel
    shared = context["rhythm"]
    kicks = dict(shared["kicks"])
    times = set(shared["anchors"]) | set(kicks)
    if pattern in ("driving", "octaves", "wobble") and section.energy >= 0.65:
        for t in list(times):
            if t + 0.5 < section.end:
                times.add(round(t + 0.5, 6))
    if pattern in ("root", "lazy"):
        times = set(shared["anchors"]) | {t for t, v in kicks.items() if v >= 75}
    times = sorted(t for t in times if section.start <= t < section.end)
    out, prev = [], context.get("bass")
    for i, t in enumerate(times):
        chord = section.chord_at(t)
        pitch = _bass_pitch(chord.bass_pc, prev)
        end = times[i + 1] if i + 1 < len(times) else section.end
        # Kein alter Bassgrundton bleibt unter einem neuen Akkord liegen.
        end = min(end, next((s.start for s in section.chords if s.start > t + 1e-6), end))
        if end - t < 0.05:
            continue
        octave = 12 if pattern == "octaves" and i % 2 else 0
        accent = 1.0 if any(abs(t - k) < 0.02 for k in kicks) else 0.75
        out.append(Ev(t, min(1.9, end - t) * 0.9, pitch + octave, _vel(section, accent * 0.9)))
        prev = pitch
    context["bass"] = prev
    return out


def _overlap(event, notes):
    return [n for n in notes if n.start < event.start + event.dur and event.start < n.start + n.dur]


def arrange(plan, events, vocal) -> dict:
    """Hauptbegleitung, Hintergrund und Antworten erhalten unterschiedliche Rollen und ein Dichtebudget."""
    rocks = ("Rock", "J-Pop Energy", "Dark Vocaloid", "Wafuu-Rock")
    primary = "guitar" if plan.style.name in rocks else "piano"
    trimmed, removed, clashes = 0, 0, 0
    for sec in plan.sections:
        sung = [n for n in vocal if sec.start <= n.start < sec.end]
        if not sung:
            continue
        active = [key for key in (primary, "piano", "guitar", "synth", "brass")
                  if any(sec.start <= e.start < sec.end for e in events.get(key, []))]
        active = list(dict.fromkeys(active))
        allowed = set(active[:2 if sec.kind == "Chorus" and sec.energy >= 0.8 else 1])
        for key in ("piano", "guitar", "synth", "brass", "counter", "bells", "strings", "choir", "melody"):
            kept = []
            for event in events.get(key, []):
                if not sec.start <= event.start < sec.end:
                    kept.append(event)
                    continue
                sounding = _overlap(event, sung)
                if not sounding:
                    kept.append(event)
                    continue
                decoration = key in ("counter", "bells", "melody") or event.layer in ("hook", "gliss")
                moving = key in ("piano", "guitar", "synth", "brass") and event.dur < 1.25
                collision = any(abs(event.pitch - n.pitch) in (1, 2) and
                                min(event.start + event.dur, n.start + n.dur) - max(event.start, n.start) >= 0.25
                                for n in sounding)
                if decoration or (moving and key not in allowed) or collision:
                    # Antworten dürfen bis zum nächsten Gesangseinsatz klingen.
                    next_vocal = min((n.start for n in sounding if n.start > event.start), default=event.start)
                    if next_vocal - event.start >= 0.25:
                        event.dur = min(event.dur, next_vocal - event.start - 0.05)
                        kept.append(event)
                        trimmed += 1
                    else:
                        removed += 1
                    clashes += int(collision)
                else:
                    if key in ("strings", "choir"):
                        event.vel = max(1, round(event.vel * 0.72))
                    kept.append(event)
            events[key] = kept
    return {"removed": removed, "trimmed": trimmed, "clashes_avoided": clashes}


def score(events, vocal) -> float:
    """Zeitgewichtete enge Reibungen der Begleitung zur Hauptstimme; 1 ist konfliktfrei."""
    bins = defaultdict(list)
    for n in vocal:
        for beat in range(int(n.start), int(n.start + n.dur) + 1):
            bins[beat].append(n)
    conflict, total = 0.0, 0.0
    for key, notes in events.items():
        if key in ("drums", "perc", "fx"):
            continue
        for e in notes:
            total += e.dur
            seen = set()
            for beat in range(int(e.start), int(e.start + e.dur) + 1):
                for n in bins.get(beat, ()):
                    if id(n) in seen:
                        continue
                    seen.add(id(n))
                    if abs(e.pitch - n.pitch) in (1, 2):
                        conflict += max(0.0, min(e.start + e.dur, n.start + n.dur) - max(e.start, n.start))
    return max(0.0, 1.0 - conflict / max(total, 1.0))

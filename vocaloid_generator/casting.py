# casting.py – Stimmen-Casting: der Refrain-Hook, gesungen von jeder installierten NEUTRINO-Stimme
#
# Jede Stimme singt die ersten Takte des Refrains in ihrer eigenen Lage (die Melodie passt sich ihrem Tonumfang an,
# wie im ganzen Song), über Akkorden und Bass aus der Refrain-Vorschau. So hört man in einer Minute, welche Stimme
# zu einem Stil passt, statt zehn Songs zu machen. Die Lieblingsstimme je Stil merkt sich die App (style_singers).
import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

log = logging.getLogger(__name__)

CAST_FOLDER = "Casting"
VOCAL_PEAK = 0.8             # Gesang gegen die Begleitung in der Vorschau
BACKING = 0.35


@dataclass
class Audition:
    singer: str
    wav: str


def singers(neutrino_dir: str) -> list:
    """Die installierten NEUTRINO-Stimmen."""
    from vocal_synthesizer import installed_singers
    return [n for n in installed_singers(neutrino_dir) if os.path.isdir(os.path.join(neutrino_dir, "model", n))]


def cast(settings, progress: Optional[Callable] = None) -> list:
    """Jede installierte Stimme singt den Refrain-Hook. Rückgabe: [Audition] in der Reihenfolge der Stimmen.
    Wirft ValueError ohne NEUTRINO-Stimme oder ohne Sektion mit Gesang."""
    import cancel
    import neutrino_score
    import pipeline
    import singing
    import voice_fx
    from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, stimmlage
    report = progress or (lambda fraction, message: None)
    neutrino_dir = settings.neutrino_dir()
    names = singers(neutrino_dir)
    if not names:
        raise ValueError("Keine NEUTRINO-Stimme gefunden. Unter Einrichten lässt sich NEUTRINO mit Stimmen einrichten.")
    kind = pipeline.hook_kind(settings)
    if settings.seed is None:
        settings = settings.with_updates(seed=pipeline.new_seed())
    folder = os.path.join(settings.output_dir(), CAST_FOLDER)
    found = []
    for i, singer in enumerate(names):
        cancel.check()
        report(i / len(names), f"Stimmen-Casting: {singer} ({i + 1}/{len(names)})...")
        target = os.path.join(folder, singer)
        os.makedirs(target, exist_ok=True)
        s = settings.with_updates(singer=singer, output_ordner=target)
        tracks, _ = pipeline.compose(s)
        sec = next(sec for sec in tracks["plan"].sections if sec.kind == kind)
        start, end = sec.start, min(sec.end, sec.start + pipeline.HOOK_BARS * sec.bar_beats)
        data, silben = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], start, end)
        if not data:
            continue
        xml = erstelle_musicxml(data, silben, s.bpm, os.path.join(target, "hook.xml"), stimmlage(singer)[2],
                                neutrino_score.options(s))
        vocal = os.path.join(target, "gesang.wav")
        try:
            neutrino_synthese(xml, vocal, neutrino_dir, os.path.join(neutrino_dir, "model", singer),
                              style_shift=singing._chorus_shift(s))
        except Exception as e:  # noqa: BLE001 – eine Stimme, die nicht singt, fehlt eben im Casting
            log.warning("Stimmen-Casting: %s singt nicht: %s", singer, e)
            continue
        backing = os.path.join(target, "begleitung.wav")
        pipeline._hook_preview(tracks, kind, backing, lead=False)
        wav = os.path.join(folder, f"{singer}.wav")
        _mix(vocal, backing, wav)
        found.append(Audition(singer, wav))
    report(1.0, "Fertig")
    if not found:
        raise ValueError("Keine Stimme hat gesungen; das Protokoll sagt, warum.")
    return found


def _mix(vocal: str, backing: str, out: str) -> None:
    import soundfile as sf
    from scipy.signal import resample_poly
    v, vr = sf.read(vocal, dtype="float32", always_2d=True)
    b, br = sf.read(backing, dtype="float32", always_2d=True)
    v = v.mean(axis=1)
    if vr != br:
        v = resample_poly(v, br, vr).astype(np.float32)
    length = max(len(v), len(b))
    mix = np.zeros((length, 2), dtype=np.float32)
    mix[:len(b)] += b[:, :2] if b.shape[1] > 1 else np.repeat(b, 2, axis=1)
    mix *= BACKING / (float(np.max(np.abs(mix))) or 1.0)
    mix[:len(v)] += (v * (VOCAL_PEAK / (float(np.max(np.abs(v))) or 1.0)))[:, None]
    sf.write(out, mix * (0.95 / max(1.0, float(np.max(np.abs(mix))))), br)


def remember(settings, singer: str) -> None:
    """singer als Lieblingsstimme für den Stil von settings merken (in settings, die App speichert sie)."""
    settings.style_singers = {**settings.style_singers, settings.style: singer}


def favorite(settings):
    """Die Einstellungen mit der Lieblingsstimme des Stils, wenn eine gemerkt und installiert ist."""
    singer = settings.style_singers.get(settings.style) if settings.style_singer else None
    if not singer or singer == settings.singer:
        return settings
    if not os.path.isdir(os.path.join(settings.neutrino_dir(), "model", singer)):
        return settings
    log.info("Lieblingsstimme für %s: %s", settings.style, singer)
    return settings.with_updates(singer=singer)

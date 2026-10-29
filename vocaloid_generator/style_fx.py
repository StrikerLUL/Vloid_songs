# style_fx.py – Stil-Effekte auf dem Gesang (Gesang 1.1, D7)
#
# Typische Vocaloid- und EDM-Momente, je nach Stil: die erste Zeile klingt wie durchs Telefon, vor dem Refrain stottert
# die Stimme (Stutter-Edit), im Future-Bass-Refrain rastet die Tonhöhe hart auf den Noten ein (wie Auto-Tune mit
# schnellster Einstellung), und eine Formant-Verschiebung macht die Stimme kindlicher oder dunkler, ohne die Tonhöhe zu
# ändern. Alles ist Studio-Bearbeitung der fertigen Aufnahme, wie sie die NEUTRINO-FAQ selbst nennt; keine Stimme wird
# in eine andere umgewandelt.
import logging
from typing import Optional

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

# Welcher Stil welche Effekte bekommt; formant: Faktor für die Formanten (über 1 heller und kindlicher)
STYLES = {
    "Future Bass": {"telephone": True, "stutter": True, "hard_tune": True},
    "Drum and Bass": {"telephone": True, "stutter": True},
    "Dark Vocaloid": {"telephone": True, "formant": 0.95},
    "Kawaii Chiptune": {"stutter": True, "hard_tune": True, "formant": 1.08},
    "J-Pop Energy": {"stutter": True},
    "Idol-Pop": {"formant": 1.04},
    "Lo-Fi": {"telephone": True},
}
TELEPHONE_BAND = (300.0, 3400.0)     # Hz, wie eine Telefonleitung
STUTTER_REPEATS = 4                  # so oft wiederholt sich die Silbe im letzten Schlag vor dem Refrain
FADE = 0.004                         # Sekunden Blende an jedem Schnitt, damit nichts knackt
# 1.4.0 sanfte Nachbearbeitung: eine Formant-Verschiebung rechnet die ganze Spur mit dem Vocoder neu und raut die Stimme
# auf; so kleine Verschiebungen (Idol ×1,04, Dark ×0,95) hört man kaum, die Rauheit schon. Sie fallen dann weg.
FORMANT_MIN_SHIFT = 0.06


def effects_for(style: str, settings) -> dict:
    """Die Effekte für diesen Stil, soweit ihr Schalter an ist."""
    wanted = STYLES.get(style, {})
    switches = {"telephone": settings.telephone_fx, "stutter": settings.stutter_fx,
                "hard_tune": settings.hard_tune, "formant": settings.formant_fx}
    chosen = {name: value for name, value in wanted.items() if switches.get(name)}
    if "formant" in chosen and getattr(settings, "gentle_reshape", False) and \
            abs(chosen["formant"] - 1.0) < FORMANT_MIN_SHIFT:
        del chosen["formant"]
    return chosen


def apply(path: str, notes: list, sections: list, bpm: float, effects: dict) -> list:
    """Die Effekte auf die Gesangsspur path. notes: voice_fx.timeline (Sekunden, gesungene Tonhöhe); sections:
    [(Start, Ende in Sekunden, Art)]. Rückgabe: was gemacht wurde, für das Protokoll."""
    import voice_fx
    done = []
    if not effects or not notes:
        return done
    if effects.get("hard_tune"):
        chorus = [n for n in notes if _kind_at(sections, n.start) == "Chorus"]
        if chorus and hard_tune(path, chorus):
            done.append("harter Tune im Refrain")
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    if effects.get("telephone"):
        first = voice_fx.phrases(notes)[0]
        audio = telephone(audio, rate, first[0].start - 0.05, first[-1].end + 0.2)
        done.append("Telefon in der ersten Zeile")
    if effects.get("stutter"):
        count = 0
        for start, _, kind in sections:
            if kind == "Chorus" and start > notes[0].start + 1.0:
                count += stutter(audio, rate, notes, start, 60.0 / bpm)
        if count:
            done.append(f"Stutter vor {count} Refrain{'s' if count > 1 else ''}")
    sf.write(path, audio, rate, subtype="FLOAT")
    if effects.get("formant") and formant(path, effects["formant"]):
        done.append(f"Formanten ×{effects['formant']:.2f}")
    return done


def _kind_at(sections: list, t: float) -> Optional[str]:
    return next((kind for start, end, kind in sections if start - 1e-6 <= t < end), None)


def _ramp(n: int, rate: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, max(1, min(n, int(FADE * rate))), dtype=np.float32)


def telephone(audio: np.ndarray, rate: int, start: float, end: float) -> np.ndarray:
    """Zwischen start und end (Sekunden) klingt die Stimme wie durchs Telefon: schmales Band, leicht angezerrt,
    genauso laut wie vorher. audio: (Samples, Kanäle)."""
    from scipy.signal import butter, sosfilt
    a, b = max(0, int(start * rate)), min(len(audio), int(end * rate))
    if b - a < int(0.05 * rate):
        return audio
    part = audio[a:b]
    sos = butter(4, TELEPHONE_BAND, "bandpass", fs=rate, output="sos")
    narrow = np.tanh(2.0 * sosfilt(sos, part, axis=0)) / 2.0
    before, after = float(np.sqrt(np.mean(part ** 2))), float(np.sqrt(np.mean(narrow ** 2)))
    if after > 1e-9:
        narrow *= before / after
    mix = np.ones(b - a, dtype=np.float32)
    ramp = _ramp(b - a, rate) if b - a > 0 else np.ones(1, dtype=np.float32)
    n = len(ramp)
    mix[:n], mix[-n:] = ramp, ramp[::-1]
    out = audio.copy()
    out[a:b] = part * (1 - mix[:, None]) + narrow.astype(np.float32) * mix[:, None]
    return out


def stutter(audio: np.ndarray, rate: int, notes: list, drop: float, beat: float) -> int:
    """Im letzten Schlag vor drop (Sekunden) wiederholt sich der Anfang der letzten Silbe davor STUTTER_REPEATS-mal in
    Sechzehnteln, lauter werdend (ändert audio). 1, wenn gestottert wurde, sonst 0."""
    before = [n for n in notes if n.start < drop - beat + 1e-6 and n.end > drop - 4 * beat]
    if not before:
        return 0
    source = before[-1]
    piece = int(beat / 4 * rate)
    a = int(source.start * rate)
    if a + piece > len(audio):
        return 0
    grain = audio[a:a + piece].copy()
    ramp = _ramp(piece, rate)
    grain[:len(ramp)] *= ramp[:, None]
    grain[-len(ramp):] *= ramp[::-1, None]
    start = int((drop - beat) * rate)
    end = min(len(audio), start + STUTTER_REPEATS * piece)
    if start < 0 or end <= start:
        return 0
    audio[start:end] = 0.0
    for k in range(STUTTER_REPEATS):
        at = start + k * piece
        take = min(piece, len(audio) - at)
        if take <= 0:
            break
        audio[at:at + take] += grain[:take] * (0.6 + 0.4 * k / max(1, STUTTER_REPEATS - 1))
    return 1


def hard_tune(path: str, notes: list) -> bool:
    """Die Tonhöhe rastet auf jedem Ton genau auf seiner Note ein, Übergänge in einem Rahmen (PSOLA, ohne
    parselmouth WORLD). Gerechnet wird Phrase für Phrase der notes."""
    import voice_fx

    def snap(f0: np.ndarray, frame: float, phrase: list, offset: float) -> np.ndarray:
        t = offset + np.arange(len(f0)) * frame
        out = f0.copy()
        for n in phrase:
            inside = (t >= n.start) & (t < n.end) & (f0 > 0)
            if not inside.any():
                continue
            sung = 69 + 12 * np.log2(np.median(f0[inside]) / 440.0)
            octave = 12 * round((sung - n.pitch) / 12)       # die Stimme singt eine Oktave tiefer oder höher
            out[inside] = 440.0 * 2 ** ((n.pitch + octave - 69) / 12)
        return out
    return voice_fx.repitch(path, notes, snap)


def formant(path: str, ratio: float) -> bool:
    """Die Formanten um ratio verschieben, die Tonhöhe bleibt (Praat „Change gender“). False ohne parselmouth."""
    try:
        import parselmouth
        from parselmouth.praat import call
    except ImportError:
        log.info("Formant-Verschiebung braucht parselmouth")
        return False
    audio, rate = sf.read(path, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    sound = parselmouth.Sound(mono, sampling_frequency=rate)
    changed = call(sound, "Change gender", 100.0, 1100.0, float(ratio), 0.0, 1.0, 1.0)
    out = changed.values[0][:len(mono)]
    out = np.pad(out, (0, len(mono) - len(out)))
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 0.99:
        out *= 0.99 / peak
    sf.write(path, np.repeat(out[:, None], audio.shape[1], axis=1).astype(np.float32), rate, subtype="FLOAT")
    return True

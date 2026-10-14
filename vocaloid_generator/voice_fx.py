# voice_fx.py – Gesang lebendiger machen: Atmer vor den Phrasen, Echo auf dem letzten Wort, Vibrato und Übergänge
# zwischen den Tönen, jede Phrase aus der saubersten von mehreren Fassungen (Comping), Ausdruck pro Phrase und ein
# Chor im letzten Refrain.
# Alles arbeitet auf fertig gesungenen Spuren und kennt dazu die Noten (in Sekunden ab Songanfang).
import logging
import os
from typing import Callable
from dataclasses import dataclass

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

PHRASE_GAP = 0.25            # ab dieser Pause (Sekunden) beginnt eine neue Phrase
BREATH_MIN, BREATH_MAX = 0.18, 0.5    # Länge eines Atmers in Sekunden
BREATH_LEAD = 0.06           # so lange vor dem ersten Ton der Phrase ist der Atmer vorbei
BREATH_DB = -24.0            # Atmer gegen die lauten Stellen des Gesangs
THROW_ROOM = 2.0             # Schläge Pause nach einem Phrasenende, damit das Echo Platz hat
GLIDE_ZONE = 0.1             # Sekunden vor und nach einem Tonwechsel, in denen die Stimme gleitet
VIBRATO_PERIOD = 0.18        # eine Schwingung eines natürlichen Vibratos (5,5 Hz)
VIBRATO_DEPTH = 0.3          # Halbtöne, die ein zusätzliches Vibrato auf und ab geht
NATURAL_VIBRATO = 0.08       # ab dieser Tiefe (Halbtöne) hat die Stimme selbst ein Vibrato
FRAME = 0.005                # Rahmen der Tonhöhenanalyse mit WORLD und Praat (Sekunden)
# Chor aus der eigenen Stimme: (Verstimmung in Cent, Verzögerung in Sekunden, Panorama) je Sänger
CHOIR_VOICES = ((-14, 0.019, -0.85), (9, 0.027, -0.4), (-7, 0.034, 0.4), (15, 0.042, 0.85))
CHOIR_PAN = 0.6              # gesungene Chorstimmen stehen abwechselnd so weit links und rechts


@dataclass
class SungNote:
    start: float             # Sekunden ab Songanfang
    end: float
    pitch: int               # MIDI, so wie er klingt


def smooth(curve: np.ndarray, n: int) -> np.ndarray:
    """Gleitender Mittelwert über n Werte (schnell auch für ganze Songs)."""
    if n <= 1 or not len(curve):
        return np.asarray(curve, dtype=np.float32)
    total = np.concatenate([[0.0], np.cumsum(curve, dtype=np.float64)])
    idx = np.arange(len(curve))
    lo, hi = np.clip(idx - n // 2, 0, len(curve)), np.clip(idx + n - n // 2, 0, len(curve))
    return ((total[hi] - total[lo]) / (hi - lo)).astype(np.float32)


def timeline(melody_data: list, bpm: float, transpose: int = 0) -> list:
    """Die Noten in Sekunden. Kurze Pausen in einer Phrase werden gebunden, so wie NEUTRINO sie singt."""
    from vocal_synthesizer import _gebunden
    spb = 60.0 / bpm
    notes, t = [], 0.0
    for pitch, dur in _gebunden(melody_data):
        if pitch is not None:
            notes.append(SungNote(t, t + dur * spb, int(pitch) + transpose))
        t += dur * spb
    return notes


def phrases(notes: list, gap: float = PHRASE_GAP) -> list:
    """Die Noten in Phrasen: eine neue beginnt nach einer Pause von mindestens gap Sekunden."""
    out = []
    for n in notes:
        if out and n.start - out[-1][-1].end < gap:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def phrase_kinds(groups: list, sections: list) -> list:
    """Sektionsart je Phrase: die Sektion (Start, Ende in Sekunden, Art), in der die Phrase am längsten liegt.
    Ein Auftakt vor dem Refrain gehört so zur Strophe davor, eine Zeile, die im Refrain weiterläuft, zum Refrain."""
    out = []
    for group in groups:
        a, b = group[0].start, group[-1].end
        best = max(sections, key=lambda s: min(b, s[1]) - max(a, s[0]), default=None)
        out.append(best[2] if best is not None and min(b, best[1]) > max(a, best[0]) else "")
    return out


def only_notes(melody_data: list, silben: list, keep: set) -> tuple:
    """Die Melodie gleich lang, aber nur mit den gesungenen Tönen, deren Nummer (0 = erster Ton) in keep steht; die
    anderen werden Pausen. Rückgabe: (melody_data, Silben der übrigen Töne)."""
    data, syllables, i = [], [], 0
    for pitch, dur in melody_data:
        if pitch is None:
            data.append((None, dur))
            continue
        if i in keep:
            data.append((pitch, dur))
            syllables.append(silben[i] if i < len(silben) else "ら")
        else:
            data.append((None, dur))
        i += 1
    return data, syllables


def same_audio(a: str, b: str, tolerance: float = 1e-3) -> bool:
    """Klingen zwei Fassungen gleich (NEUTRINO singt bei gleichem StyleShift jedes Mal dasselbe)?"""
    x, _ = sf.read(a, dtype="float32", always_2d=True)
    y, _ = sf.read(b, dtype="float32", always_2d=True)
    n = min(len(x), len(y))
    if n == 0 or abs(len(x) - len(y)) > 1:
        return n == 0 and len(x) == len(y)
    return float(np.max(np.abs(x[:n] - y[:n]))) <= tolerance


def excerpt(melody_data: list, silben: list, start: float, end: float) -> tuple:
    """Nur die Noten, die zwischen den Schlägen start und end beginnen, als melody_data ab start, mit ihren Silben."""
    data, syllables, t, pos, i = [], [], 0.0, start, 0
    for pitch, dur in melody_data:
        if pitch is not None:
            if start - 1e-6 <= t < end - 1e-6:
                if t > pos + 1e-6:
                    data.append((None, round(t - pos, 4)))
                data.append((pitch, dur))
                syllables.append(silben[i] if i < len(silben) else "ら")
                pos = t + dur
            i += 1
        t += dur
    return data, syllables


# ── Atmer ──────────────────────────────────────────────────────────────────────
BREATH_FOLDER = "Atmer"       # im Datenordner: eigene Atem-Aufnahmen (WAV, FLAC), z. B. CC0 von Freesound


def breath_samples(rate: int, folder: str = None) -> list:
    """Aufgenommene Atmer aus dem Ordner Atmer: [(Länge in Sekunden, mono, Effektivwert 1)], kürzeste zuerst.
    Stille am Anfang und Ende wird abgeschnitten."""
    import config
    from scipy.signal import resample_poly
    folder = folder or os.path.join(config.DATA_DIR, BREATH_FOLDER)
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".wav", ".flac", ".ogg", ".aiff")))
    except OSError:
        return []
    out = []
    for name in names:
        try:
            data, sr = sf.read(os.path.join(folder, name), dtype="float32", always_2d=True)
        except Exception as e:  # noqa: BLE001 – eine kaputte Datei zählt nicht
            log.warning("Atmer %s nicht lesbar: %s", name, e)
            continue
        mono = data.mean(axis=1)
        if sr != rate:
            mono = resample_poly(mono, rate, sr).astype(np.float32)
        loud = np.flatnonzero(np.abs(mono) > np.abs(mono).max() * 0.02) if len(mono) else []
        if len(loud) < rate * 0.1:
            continue
        mono = mono[loud[0]:loud[-1] + 1]
        out.append((len(mono) / rate, (mono / (np.sqrt(np.mean(mono ** 2)) + 1e-12)).astype(np.float32)))
    return sorted(out, key=lambda x: x[0])


def _recorded_breath(samples: list, n: int, rate: int, rng: np.random.Generator) -> np.ndarray:
    """Ein aufgenommener Atmer mit passender Länge (einer der zwei nächstgelegenen), auf n Samples gebracht:
    zu lang wird vorn gekürzt (das Ende des Einatmens bleibt), zu kurz beginnt später."""
    dur = n / rate
    near = sorted(range(len(samples)), key=lambda k: abs(samples[k][0] - dur))[:2]
    mono = samples[int(rng.choice(near))][1]
    out = np.zeros(n, dtype=np.float32)
    if len(mono) >= n:
        out[:] = mono[len(mono) - n:]
        fade = min(n // 4, int(0.05 * rate))
        out[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    else:
        out[n - len(mono):] = mono
    return out


def add_breaths(path: str, notes: list, seed: int = 0, recorded: bool = True) -> int:
    """Vor jeder Phrase, vor der genug Pause ist, ein hörbares Einatmen in die Gesangsspur mischen.
    Längere Phrasen bekommen einen tieferen Atemzug. Mit recorded und Aufnahmen im Ordner Atmer klingen echte
    Atmer, sonst gefiltertes Rauschen. Rückgabe: Anzahl der Atmer."""
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    level = _sung_level(audio.mean(axis=1), rate)
    if level <= 0:
        return 0
    rng = np.random.default_rng(seed)
    samples = breath_samples(rate) if recorded else []
    track = np.zeros(len(audio), dtype=np.float32)
    count, prev_end = 0, 0.0
    for phrase in phrases(notes):
        onset, length = phrase[0].start, phrase[-1].end - phrase[0].start
        room = onset - prev_end - BREATH_LEAD
        prev_end = phrase[-1].end
        if room < BREATH_MIN:
            continue
        depth = float(np.clip(length / 4.0, 0.4, 1.0))
        dur = float(np.clip(BREATH_MAX * depth, BREATH_MIN, room * 0.8))
        a = int((onset - BREATH_LEAD - dur) * rate)
        n = int(dur * rate)
        if a < 0 or a + n > len(track):
            continue
        gain = level * 10 ** (BREATH_DB / 20) * (0.6 + 0.4 * depth) * rng.uniform(0.85, 1.15)
        track[a:a + n] += (_recorded_breath(samples, n, rate, rng) if samples else breath(n, rate, rng)) * gain
        count += 1
    sf.write(path, audio + track[:, None], rate, subtype="FLOAT")
    return count


def breath(n: int, rate: int, rng: np.random.Generator) -> np.ndarray:
    """Ein Einatmen: Rauschen mit einer Betonung um 1–2 kHz (halb offener Mund), langsam lauter, am Ende kurz ab.
    Effektivwert 1."""
    from scipy.signal import butter, sosfilt
    pad = 2048
    noise = rng.standard_normal(n + pad)
    body = sosfilt(butter(2, [500, 6000], "bandpass", fs=rate, output="sos"), noise)
    formant = rng.uniform(1100, 1800)
    mouth = sosfilt(butter(2, [formant * 0.8, formant * 1.25], "bandpass", fs=rate, output="sos"), noise)
    x = (body + 1.5 * mouth)[pad:]
    t = np.linspace(0.0, 1.0, n)
    env = np.sin(np.pi / 2 * np.clip(t / 0.75, 0, 1)) ** 2 * np.clip((1 - t) / 0.12, 0, 1) ** 1.5
    x *= env
    return (x / (np.sqrt(np.mean(x ** 2)) + 1e-12)).astype(np.float32)


def _sung_level(mono: np.ndarray, rate: int) -> float:
    """Effektivwert der lauten Stellen (90. Perzentil der 50-ms-Fenster, in denen gesungen wird)."""
    hop = max(1, int(0.05 * rate))
    frames = len(mono) // hop
    if frames == 0:
        return 0.0
    rms = np.sqrt(np.mean(mono[:frames * hop].reshape(frames, hop) ** 2, axis=1))
    sung = rms[rms > rms.max() * 10 ** (-40 / 20)] if rms.max() > 0 else rms[:0]
    return float(np.percentile(sung, 90)) if len(sung) else 0.0


# ── Echo auf dem letzten Wort ──────────────────────────────────────────────────
def throw_windows(notes: list, bpm: float, sections: list = (), room: float = 1.0) -> list:
    """
    [(Start, Ende)] der letzten Silbe der Phrasen, die ein Echo bekommen: die letzte Phrase jeder Sektion und im
    Refrain jede zweite. sections: [(Start, Ende in Sekunden, Art)]; ohne sie jede Phrase, nach der mindestens
    THROW_ROOM Schläge Pause sind. Nach der Phrase braucht es room Schläge Pause, sonst geht das Echo unter.
    Ist die letzte Note sehr kurz, gehört die davor mit dazu.
    """
    spb = 60.0 / bpm
    out, groups = [], phrases(notes)
    for k, phrase in enumerate(groups):
        following = groups[k + 1][0].start if k + 1 < len(groups) else float("inf")
        pause = (following - phrase[-1].end) / spb
        if pause < room - 1e-6:
            continue
        sec = next((sec for sec in sections if sec[0] - 1e-6 <= phrase[0].start < sec[1]), None)
        if sec is None:
            wanted = pause >= THROW_ROOM - 1e-6
        else:
            same = [p for p in groups if sec[0] - 1e-6 <= p[0].start < sec[1]]
            pos = next(i for i, p in enumerate(same) if p is phrase)
            wanted = pos == len(same) - 1 or (sec[2] == "Chorus" and pos % 2 == 1)
        if wanted:
            first = phrase[-2] if len(phrase) > 1 and phrase[-1].end - phrase[-1].start < 0.25 else phrase[-1]
            out.append((first.start, phrase[-1].end))
    return out


# ── Vibrato und Übergänge ──────────────────────────────────────────────────────
def shape_pitch(f0: np.ndarray, frame: float, notes: list, vibrato: float = 1.0, glide: float = 1.0,
                offset: float = 0.0) -> np.ndarray:
    """
    Vibrato und Übergänge einer gesungenen Tonhöhenkurve ändern (Hz je Rahmen, 0 = stimmlos).
    vibrato: 0 = gerade Töne, 1 = wie gesungen, 2 = doppelt so tief; lange Töne ohne eigenes Vibrato bekommen
    über 1 eines dazu. glide: 0 = die Töne springen, 1 = wie gesungen, 2 = doppelt so lange Übergänge.
    offset: Zeit des ersten Rahmens ab Songanfang.
    """
    f0 = np.asarray(f0, dtype=np.float64)
    voiced = f0 > 0
    if not voiced.any() or not notes:
        return f0
    idx = np.arange(len(f0))
    t = offset + idx * frame
    midi = np.interp(idx, idx[voiced], 69 + 12 * np.log2(f0[voiced] / 440.0))
    vib, natural = _vibrato(midi, t, notes, frame)
    base = midi - vib
    if abs(glide - 1.0) > 1e-3:
        base = _glides(base, t, notes, glide)
    out = base + _new_vibrato(vib, natural, t, notes, vibrato)
    return np.where(voiced, 440.0 * 2 ** ((out - 69) / 12), 0.0)


def _interior(t: np.ndarray, n: SungNote) -> tuple:
    """Rahmen eines Tons ohne die Übergänge an seinen Rändern."""
    return int(np.searchsorted(t, n.start + GLIDE_ZONE)), int(np.searchsorted(t, n.end - GLIDE_ZONE * 0.6))


def _vibrato(midi: np.ndarray, t: np.ndarray, notes: list, frame: float) -> tuple:
    """Das Vibrato der Stimme (Abweichung vom gleitenden Mittel über eine Schwingung) und je Note,
    ob sie selbst eines singt."""
    from scipy.ndimage import uniform_filter1d
    vib = np.zeros_like(midi)
    natural = []
    width = max(3, int(round(VIBRATO_PERIOD / frame)))
    for n in notes:
        i, j = _interior(t, n)
        if j - i < width:
            natural.append(False)
            continue
        seg = midi[i:j]
        v = seg - uniform_filter1d(seg, width, mode="nearest")
        fade = min(len(v) // 4, max(1, int(0.03 / frame)))
        v[:fade] *= np.linspace(0, 1, fade)
        v[-fade:] *= np.linspace(1, 0, fade)
        vib[i:j] = v
        natural.append(float(np.std(v)) * np.sqrt(2) >= NATURAL_VIBRATO)
    return vib, natural


def _new_vibrato(vib: np.ndarray, natural: list, t: np.ndarray, notes: list, amount: float) -> np.ndarray:
    out = vib * min(amount, 1.0)
    for n, own in zip(notes, natural):
        i, j = _interior(t, n)
        if j <= i:
            continue
        if own:
            out[i:j] = vib[i:j] * amount
        elif amount > 1.0 and n.end - n.start >= 0.35:
            tt = t[i:j] - t[i]
            env = np.clip(tt / 0.2, 0, 1) * np.clip((t[j - 1] - t[i:j]) / 0.05, 0, 1)
            out[i:j] += (amount - 1.0) * VIBRATO_DEPTH * env * np.sin(2 * np.pi / VIBRATO_PERIOD * tt)
    return out


def _glides(base: np.ndarray, t: np.ndarray, notes: list, amount: float) -> np.ndarray:
    """Die Übergänge zwischen gebundenen Tönen zeitlich stauchen (amount < 1) oder dehnen (amount > 1)."""
    out = base.copy()
    for prev, nxt in zip(notes, notes[1:]):
        if nxt.start - prev.end > 0.1:
            continue                          # Pause dazwischen: kein Gleiten
        b = nxt.start
        left = min(GLIDE_ZONE, 0.4 * (prev.end - prev.start))
        right = min(GLIDE_ZONE, 0.4 * (nxt.end - nxt.start))
        reach_left = min(left * max(amount, 1.0), 0.45 * (prev.end - prev.start))
        reach_right = min(right * max(amount, 1.0), 0.45 * (nxt.end - nxt.start))
        zone = (t >= b - reach_left) & (t <= b + reach_right)
        source = b + (t[zone] - b) / max(amount, 1e-3)
        out[zone] = np.interp(np.clip(source, b - left, b + right), t, base)
    return out


def reshape(path: str, notes: list, vibrato: float = 1.0, glide: float = 1.0, psola: bool = True) -> bool:
    """Vibrato und Übergänge einer gesungenen Spur ändern. Gerechnet wird Phrase für Phrase, die Pausen bleiben
    unberührt. psola: mit Praat-PSOLA (parselmouth), das nur die Tonhöhe verschiebt und den Klang der Stimme lässt;
    ohne, oder wenn parselmouth fehlt, baut der WORLD-Vocoder die Phrase neu (klingt eine Spur rauer).
    False, wenn nichts zu tun war."""
    if abs(vibrato - 1.0) < 1e-3 and abs(glide - 1.0) < 1e-3:
        return False

    def curve(f0: np.ndarray, frame: float, phrase: list, offset: float) -> np.ndarray:
        return shape_pitch(f0, frame, phrase, vibrato, glide, offset=offset)
    repitch(path, notes, curve, psola)
    log.info("Vibrato %.1f, Übergänge %.1f (%s)", vibrato, glide, "PSOLA" if psola and psola_available() else "WORLD")
    return True


def repitch(path: str, notes: list, curve: Callable, psola: bool = True) -> bool:
    """Eine neue Tonhöhenkurve für jede Phrase der notes: curve(f0 in Hz je FRAME, FRAME, Phrase, Zeit des ersten
    Rahmens) gibt sie zurück. Mit PSOLA, wenn psola und parselmouth da sind, sonst mit WORLD."""
    method = _psola if psola and psola_available() else _world
    audio, rate = sf.read(path, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    out = mono.copy()
    pad = 0.15
    changed = False
    for phrase in phrases(notes):
        a = max(0, int((phrase[0].start - pad) * rate))
        b = min(len(mono), int((phrase[-1].end + pad) * rate))
        if b - a < int(0.1 * rate):
            continue
        x = np.ascontiguousarray(mono[a:b])
        y = method(x, rate, lambda f0, frame, offset, phrase=phrase: curve(f0, frame, phrase, offset), a / rate)
        if y is None:
            continue
        y = np.pad(y[:len(x)], (0, max(0, len(x) - len(y))))
        fade = min(len(y) // 4, int(0.01 * rate))
        ramp = np.linspace(0, 1, fade)
        y[:fade] = x[:fade] * (1 - ramp) + y[:fade] * ramp
        y[-fade:] = y[-fade:] * ramp[::-1] + x[-fade:] * (1 - ramp[::-1])
        out[a:b] = y
        changed = True
    sf.write(path, np.repeat(out[:, None], audio.shape[1], axis=1).astype(np.float32), rate, subtype="FLOAT")
    return changed


def psola_available() -> bool:
    try:
        import parselmouth  # noqa: F401
        return True
    except ImportError:
        return False


def _f0(x: np.ndarray, rate: int) -> tuple:
    """Tonhöhe je FRAME mit WORLD (DIO und StoneMask): genauer im Vibrato als die Analyse von Praat."""
    import pyworld as pw
    f0, times = pw.dio(x, rate, f0_floor=70.0, f0_ceil=1100.0, frame_period=FRAME * 1000)
    return pw.stonemask(x, f0, times, rate), times


def _world(x: np.ndarray, rate: int, curve: Callable, offset: float):
    """curve(f0, FRAME, Zeit des ersten Rahmens) → neue Tonhöhe; WORLD baut die Phrase damit neu."""
    import pyworld as pw
    f0, times = _f0(x, rate)
    if not np.any(f0 > 0):
        return None
    sp = pw.cheaptrick(x, f0, times, rate)
    ap = pw.d4c(x, f0, times, rate)
    return pw.synthesize(curve(f0, FRAME, offset), sp, ap, rate, frame_period=FRAME * 1000)


def _psola(x: np.ndarray, rate: int, curve: Callable, offset: float):
    """Die neue Tonhöhenkurve als PitchTier in eine Praat-Manipulation, dann Overlap-Add (PSOLA). Gemessen wird die
    Tonhöhe mit WORLD, neu gerechnet nicht: die Stimme behält ihren Klang."""
    import parselmouth
    from parselmouth.praat import call
    f0, times = _f0(x, rate)
    if not np.any(f0 > 0):
        return None
    new = curve(f0, FRAME, offset)
    sound = parselmouth.Sound(x, sampling_frequency=rate)
    manipulation = call(sound, "To Manipulation", 0.01, 70.0, 1100.0)
    tier = call("Create PitchTier", "neu", sound.xmin, sound.xmax)
    for t, hz in zip(times, new):
        if hz > 0:
            call(tier, "Add point", float(t), float(hz))
    call([manipulation, tier], "Replace pitch tier")
    return call(manipulation, "Get resynthesis (overlap-add)").values[0]


# ── Swing (A6) ─────────────────────────────────────────────────────────────────
def swung(notes: list, bpm: float) -> list:
    """Die Töne, die auf einer zweiten Sechzehntel beginnen: diese verschiebt der Swing der Band."""
    spb = 60.0 / bpm
    out = []
    for n in notes:
        sixteenth = n.start / spb * 4
        if abs(sixteenth - round(sixteenth)) < 1e-3 and round(sixteenth) % 2 == 1:
            out.append(n)
    return out


def swing(path: str, notes: list, bpm: float, shift_beats: float) -> int:
    """Der Gesang swingt wie die Band (orchestrator._to_notes): jeder Ton auf einer zweiten Sechzehntel setzt
    shift_beats später ein. Die Sechzehntel davor wird dafür etwas gedehnt, die danach gestaucht (Praat-PSOLA mit
    DurationTier); Tonhöhe, Klang und Gesamtlänge bleiben. Gerechnet wird nur in Phrasen mit solchen Tönen.
    Rückgabe: Zahl der verschobenen Töne (0 ohne parselmouth)."""
    if shift_beats <= 0 or not psola_available():
        return 0
    import parselmouth
    from parselmouth.praat import call
    q = 60.0 / bpm / 4                                  # eine Sechzehntel in Sekunden
    d = min(shift_beats * 60.0 / bpm, q * 0.5)
    audio, rate = sf.read(path, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    out = mono.copy()
    pad = q + 0.05
    moved = 0
    for phrase in phrases(notes):
        onsets = [n.start for n in swung(phrase, bpm)]
        a = max(0, int((phrase[0].start - pad) * rate))
        b = min(len(mono), int((phrase[-1].end + pad) * rate))
        onsets = [s - a / rate for s in onsets if s - q > a / rate and s + q < b / rate]
        if not onsets:
            continue
        x = np.ascontiguousarray(mono[a:b])
        sound = parselmouth.Sound(x, sampling_frequency=rate)
        manipulation = call(sound, "To Manipulation", 0.01, 70.0, 1100.0)
        tier = call("Create DurationTier", "swing", sound.xmin, sound.xmax)
        eps = min(0.002, q / 10)
        for s in onsets:
            for t, factor in ((s - q, 1.0), (s - q + eps, (q + d) / q), (s - eps, (q + d) / q),
                              (s + eps, (q - d) / q), (s + q - eps, (q - d) / q), (s + q, 1.0)):
                call(tier, "Add point", float(t), float(factor))
        call([manipulation, tier], "Replace duration tier")
        y = call(manipulation, "Get resynthesis (overlap-add)").values[0]
        y = np.pad(y[:len(x)], (0, max(0, len(x) - len(y))))
        fade = min(len(y) // 4, int(0.01 * rate))
        ramp = np.linspace(0, 1, fade)
        y[:fade] = x[:fade] * (1 - ramp) + y[:fade] * ramp
        y[-fade:] = y[-fade:] * ramp[::-1] + x[-fade:] * (1 - ramp[::-1])
        out[a:b] = y
        moved += len(onsets)
    if moved:
        sf.write(path, np.repeat(out[:, None], audio.shape[1], axis=1).astype(np.float32), rate, subtype="FLOAT")
    return moved


# ── Fassungen ──────────────────────────────────────────────────────────────────
def take_shifts(style_shift: int, takes: int) -> list:
    """StyleShift je Fassung: die gewählte zuerst, dann eine Stufe heller und eine dunkler."""
    shifts = []
    for s in (style_shift, style_shift + 1, style_shift - 1):
        s = int(np.clip(s, -6, 6))
        if s not in shifts:
            shifts.append(s)
    return shifts[:max(1, takes)]


def _pitch_track(path: str) -> tuple:
    """(Tonhöhe in Hz je 10 ms, Zeiten, übersteuert je Zeit, Audio, Rate) einer Fassung."""
    import pyworld as pw
    from scipy.signal import resample_poly
    audio, rate = sf.read(path, dtype="float64", always_2d=True)
    x = np.ascontiguousarray(resample_poly(audio.mean(axis=1), 16000, rate))
    f0, times = pw.dio(x, 16000, f0_floor=70.0, f0_ceil=1100.0, frame_period=10.0)
    f0 = pw.stonemask(x, f0, times, 16000)
    hop = rate // 100
    peaks = np.abs(audio).max(axis=1)
    clipped = np.array([np.mean(peaks[i * hop:(i + 1) * hop] >= 0.999) if i * hop < len(peaks) else 0.0
                        for i in range(len(times))])
    return f0, times, clipped, audio, rate


# Grobe Fehler (Fassungen ohne Farbsprung): bis zu dieser Abweichung (Cent) ist ein Ton nicht falsch, sondern gesungen
GROSS_CENTS = 50.0
CRACK_CENTS = 300.0          # ein Sprung der Tonhöhe von einem Rahmen zum nächsten mitten im Ton: ein Kiekser
CRACK_COST = 300.0           # so viel Cent kostet jeder Kiekser
SILENT_SCORE = 500.0         # ab diesem Fehler singt eine Fassung die Phrase nicht (z. B. eine andere Sektion)


def _note_errors(f0: np.ndarray, times: np.ndarray, notes: list, tolerance: float = 0.0) -> list:
    """[(Fehler mal Dauer, Dauer)] je Note: mittlere Abweichung in Cent, Aussetzer zählen wie 600 Cent.
    tolerance: Abweichungen bis zu so vielen Cent zählen nicht; dann kosten auch Kiekser (Sprünge mitten im Ton)."""
    out = []
    for n in notes:
        dur = n.end - n.start
        sel = f0[(times >= n.start + 0.2 * dur) & (times < n.end - 0.2 * dur)] if dur >= 0.12 else []
        if not len(sel):
            out.append((0.0, 0.0))
            continue
        sung = sel[sel > 0]
        target = 440.0 * 2 ** ((n.pitch - 69) / 12)
        cents = float(np.median(np.abs(1200 * np.log2(sung / target)))) if len(sung) else 600.0
        cents = max(0.0, cents - tolerance) if len(sung) else cents
        if tolerance and len(sung) > 1:
            cents += CRACK_COST * int(np.sum(np.abs(np.diff(1200 * np.log2(sung))) > CRACK_CENTS))
        out.append(((min(cents, 600.0) + 600.0 * (1 - len(sung) / len(sel))) * dur, dur))
    return out


def pitch_error(path: str, notes: list, tolerance: float = 0.0) -> float:
    """Wie weit eine Fassung danebenliegt (kleiner ist besser): mittlere Abweichung von den Noten in Cent,
    Aussetzer (stumm, wo gesungen werden soll) zählen wie 600 Cent, übersteuerte Stellen kosten extra.
    tolerance: siehe _note_errors (grobe Fehler statt jeder Abweichung)."""
    f0, times, clipped, _, _ = _pitch_track(path)
    errors = _note_errors(f0, times, notes, tolerance)
    weight = sum(d for _, d in errors)
    return (sum(e for e, _ in errors) / weight if weight else 600.0) + float(np.mean(clipped)) * 1e4


# ── Comping: jede Phrase aus der saubersten Fassung ──────────────────────────────
COMP_FADE = 0.03             # Überblendung an den Schnitten (Sekunden), mitten in der Pause zwischen zwei Phrasen


def phrase_errors(track: tuple, notes: list, groups: list, tolerance: float = 0.0) -> list:
    """Fehler je Phrase (wie pitch_error, nur über die Noten der Phrase und ihre Zeit)."""
    f0, times, clipped = track[:3]
    errors = _note_errors(f0, times, notes, tolerance)
    index = {id(n): i for i, n in enumerate(notes)}
    out = []
    for group in groups:
        mine = [errors[index[id(n)]] for n in group]
        weight = sum(d for _, d in mine)
        inside = (times >= group[0].start) & (times < group[-1].end)
        clip = float(np.mean(clipped[inside])) if inside.any() else 0.0
        out.append((sum(e for e, _ in mine) / weight if weight else 600.0) + clip * 1e4)
    return out


def _cut_points(groups: list) -> list:
    """Schnittstellen zwischen den Phrasen: die Mitte der Pause dazwischen (Sekunden)."""
    return [(a[-1].end + b[0].start) / 2 for a, b in zip(groups, groups[1:])]


def _segment_masks(choice: list, cuts: list, takes: int, length: int, rate: int,
                   keep: np.ndarray = None) -> np.ndarray:
    """Gewicht jeder Fassung über die Zeit: 1 in ihren Phrasen, weich überblendet; keep blendet Stellen aus."""
    masks = np.zeros((takes, length), dtype=np.float32)
    bounds = [0] + [int(c * rate) for c in cuts] + [length]
    for k, (a, b) in zip(choice, zip(bounds, bounds[1:])):
        if k is not None:
            masks[k, a:b] = 1.0
    if keep is not None:
        masks *= keep[None]
    return np.stack([smooth(m, int(COMP_FADE * rate)) for m in masks])


def comp(takes: list, notes: list, out_path: str, double_path: str = None, double_windows: list = (),
         tolerance: float = 0.0, forced: dict = None) -> list:
    """
    Setzt die Hauptstimme Phrase für Phrase aus der saubersten Fassung zusammen und schreibt sie nach out_path.
    double_path: dort landet in den double_windows (Sekunden, z. B. die Refrains) die zweitbeste Fassung jeder Phrase,
    eine echte Doppelung statt einer Kopie; eine Fassung, die die Phrase gar nicht singt, doppelt nicht.
    tolerance: grobe Fehler statt jeder Abweichung (siehe _note_errors). forced: {Phrase: Fassung}, die feststehen
    (von Hand neu gesungen); sie bekommen keine Doppelung. Rückgabe: die Fassung je Phrase.
    """
    groups = phrases(notes)
    tracks = [_pitch_track(t) for t in takes]
    rate = tracks[0][4]
    length = max(len(tr[3]) for tr in tracks)
    audio = np.zeros((len(takes), length, tracks[0][3].shape[1]), dtype=np.float32)
    for k, tr in enumerate(tracks):
        if tr[4] != rate:
            raise ValueError("Die Fassungen haben verschiedene Abtastraten")
        audio[k, :len(tr[3])] = tr[3]
    scores = np.array([phrase_errors(tr, notes, groups, tolerance) for tr in tracks])      # [Fassung, Phrase]
    order = np.argsort(scores, axis=0, kind="stable")
    forced = forced or {}
    choice = [forced.get(p, int(order[0, p])) for p in range(len(groups))]
    cuts = _cut_points(groups)
    masks = _segment_masks(choice, cuts, len(takes), length, rate)
    sf.write(out_path, np.einsum("kt,ktc->tc", masks, audio), rate, subtype="FLOAT")
    if double_path and len(takes) > 1 and double_windows:
        keep = np.zeros(length, dtype=np.float32)
        for start, end in double_windows:
            keep[max(0, int(start * rate)):min(length, int(end * rate))] = 1.0
        second = [int(order[1, p]) if scores[order[1, p], p] < SILENT_SCORE and p not in forced else None
                  for p in range(len(groups))]
        masks = _segment_masks(second, cuts, len(takes), length, rate, keep)
        double = np.einsum("kt,ktc->tc", masks, audio)
        if np.max(np.abs(double)) > 1e-4:
            sf.write(double_path, double, rate, subtype="FLOAT")
    return choice


# ── Ausdruck pro Phrase ────────────────────────────────────────────────────────
# Grundpegel des Gesangs je Sektion (dB): Strophen etwas zurück, Refrains nach vorn
SECTION_LEVEL_DB = {"Intro": -1.0, "Verse": -1.5, "PreChorus": -0.5, "Chorus": 1.0, "Bridge": -1.0,
                    "Build-up": 0.0, "Drop": 1.0, "Outro": -1.5}
RISE_DB = 2.0                # zum höchsten Ton einer Phrase hin wird sie so viel lauter
END_DB = -3.0                # der letzte Ton einer Phrase klingt so viel leiser aus
BRIGHT = 0.5                 # lauter klingt heller: Anteil der Höhen über 2,5 kHz, der mit dem Pegel mitgeht


def expression_curve(notes: list, sections: list, length: int, rate: int, amount: float = 1.0) -> np.ndarray:
    """Pegel über die Zeit in dB: Grundpegel der Sektion, Anstieg zum Höhepunkt der Phrase, weiches Ende."""
    points_t, points_db = [0.0], [0.0]

    def level(t: float) -> float:
        kind = next((k for start, end, k in sections if start <= t < end), "")
        return SECTION_LEVEL_DB.get(kind, 0.0)

    for group in phrases(notes):
        base = level(group[0].start)
        top = max(range(len(group)), key=lambda i: (group[i].pitch, i))
        peak = group[top]
        last = group[-1]
        fade_start = last.start + 0.4 * (last.end - last.start)
        shape = [(group[0].start - 0.05, base - 1.0), (group[0].start, base - 1.0),
                 ((peak.start + peak.end) / 2, base + RISE_DB)]
        if top == len(group) - 1:       # der Höhepunkt ist der letzte Ton: er bleibt oben und klingt dann aus
            shape += [(fade_start, base + RISE_DB)]
        else:
            shape += [(fade_start, base)]
        shape += [(last.end, base + END_DB), (last.end + 0.05, base)]
        for t, db in shape:
            if t > points_t[-1]:
                points_t.append(t)
                points_db.append(db)
    curve = np.interp(np.arange(length) / rate, points_t, points_db).astype(np.float32)
    return smooth(curve, int(0.02 * rate)) * float(amount)


def express(path: str, notes: list, sections: list, amount: float = 1.0) -> bool:
    """
    Ausdruck pro Phrase auf eine fertige Gesangsspur: sections [(Start, Ende in Sekunden, Sektionsart)].
    Lauter klingt dabei auch heller, wie bei einer echten Stimme. False, wenn es nichts zu tun gab.
    """
    from scipy.signal import butter, sosfilt
    if not notes:
        return False
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    db = expression_curve(notes, sections, len(audio), rate, amount)
    gain = 10 ** (db / 20)
    highs = sosfilt(butter(2, 2500, "highpass", fs=rate, output="sos"), audio, axis=0)
    shaped = audio * gain[:, None] + highs * ((gain - 1) * BRIGHT)[:, None]
    sf.write(path, shaped.astype(np.float32), rate, subtype="FLOAT")
    return True


# ── Lautstärke pro Silbe (C2) ──────────────────────────────────────────────────
ACCENT_DB = 1.5              # betonte Silbe (Wortakzent oder starke Zählzeit) lauter
BOTH_DB = 2.5                # Wortakzent auf der starken Zählzeit
PICKUP_DB = -1.5             # kurze Silbe direkt vor einem Hochton leiser (Anlauf)
ONSET_DB = -6.0              # weicher Einsatz am Phrasenanfang: so leise beginnt der erste Ton
ONSET_SECONDS = 0.06
SYLLABLE_FADE = 0.02         # Sekunden Übergang zwischen den Silben


def syllable_gains(melody_data: list, silben: list, bpm: float) -> list:
    """[(Start, Ende in Sekunden, dB)] je gesungenem Ton: wie stark die Silbe betont wird."""
    from vocal_synthesizer import _gebunden
    spb = 60.0 / bpm
    sung, t, i = [], 0.0, 0
    for pitch, dur in _gebunden(melody_data):
        if pitch is not None:
            syl = silben[i] if i < len(silben) else ""
            sung.append((t, dur, int(pitch), syl))
            i += 1
        t += dur
    out = []
    for k, (beat, dur, pitch, syl) in enumerate(sung):
        strong = abs(beat % 2.0) < 1e-6 or abs(beat % 2.0 - 2.0) < 1e-6        # Schlag 1 und 3
        accent = getattr(syl, "tone", None) == "H" and getattr(syl, "word_start", False) or (
            getattr(syl, "tone", None) == "H" and k > 0 and getattr(sung[k - 1][3], "tone", None) == "L")
        held = getattr(syl, "melisma", False)
        db = BOTH_DB if strong and accent else (ACCENT_DB if strong or accent else 0.0)
        nxt = sung[k + 1] if k + 1 < len(sung) else None
        if nxt is not None and dur <= 0.5 and nxt[2] >= pitch + 3 and abs(nxt[0] - beat - dur) < 1e-6:
            db = PICKUP_DB
        if held:
            db = out[-1][2] if out else 0.0                     # ein gehaltener Vokal bleibt, wie er war
        out.append((beat * spb, (beat + dur) * spb, db))
    return out


def syllable_curve(gains: list, notes: list, length: int, rate: int) -> np.ndarray:
    """Pegel über die Zeit in dB aus syllable_gains, um den Mittelwert verschoben, mit weichem Phrasenanfang."""
    curve = np.zeros(length, dtype=np.float32)
    for start, end, db in gains:
        curve[int(start * rate):int(end * rate)] = db
    sung = np.zeros(length, dtype=bool)
    for start, end, _ in gains:
        sung[int(start * rate):int(end * rate)] = True
    if sung.any():
        curve[sung] -= float(np.mean(curve[sung]))
    curve = smooth(curve, int(SYLLABLE_FADE * rate))
    ramp = int(ONSET_SECONDS * rate)
    for group in phrases(notes):
        a = int(group[0].start * rate)
        n = min(ramp, length - a)
        if n > 0:
            curve[a:a + n] += np.linspace(ONSET_DB, 0.0, n, dtype=np.float32)
    return curve


def syllable_dynamics(path: str, melody_data: list, silben: list, bpm: float) -> bool:
    """Lautstärke pro Silbe auf eine fertige Gesangsspur. False, wenn es nichts zu tun gab."""
    gains = syllable_gains(melody_data, silben, bpm)
    if not gains:
        return False
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    db = syllable_curve(gains, timeline(melody_data, bpm), len(audio), rate)
    sf.write(path, (audio * (10 ** (db / 20))[:, None]).astype(np.float32), rate, subtype="FLOAT")
    return True


# ── Chor im letzten Refrain ────────────────────────────────────────────────────
def choir_from_lead(lead_path: str, out_path: str, window: tuple) -> bool:
    """Ohne weitere Stimmen: vier leicht verstimmte, verschieden späte und sich langsam bewegende Kopien der
    Hauptstimme, breit verteilt, nur im Fenster (Sekunden)."""
    from pedalboard import Chorus, PitchShift
    audio, rate = sf.read(lead_path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    a, b = max(0, int(window[0] * rate)), min(len(mono), int(window[1] * rate))
    if b - a < rate // 2:
        return False
    tail = int(0.5 * rate)
    seg = mono[a:min(len(mono), b + tail)].copy()
    fade = int(0.05 * rate)
    seg[:fade] *= np.linspace(0, 1, fade)
    seg[b - a:] *= np.linspace(1, 0, len(seg) - (b - a))
    out = np.zeros((len(mono), 2), dtype=np.float32)
    for k, (cents, delay, pan) in enumerate(CHOIR_VOICES):
        copy = PitchShift(semitones=cents / 100)(seg[None], rate)
        copy = Chorus(rate_hz=0.25 + 0.15 * k, depth=0.2, centre_delay_ms=delay * 1000, feedback=0.0,
                      mix=1.0)(copy, rate)[0]
        _place(out, copy * 0.5, a, pan)
    sf.write(out_path, out, rate, subtype="FLOAT")
    return True


def write_choir(out_path: str, voices: list, rate: int, offset: float, length: int = 0) -> None:
    """Gesungene Chorstimmen (Mono, ab offset Sekunden) abwechselnd links und rechts in eine Spur."""
    start = int(offset * rate)
    total = max(length, start + max(len(v) for v in voices))
    out = np.zeros((total, 2), dtype=np.float32)
    for k, voice in enumerate(voices):
        delay = int(0.012 * k * rate)
        _place(out, np.asarray(voice, dtype=np.float32), start + delay, CHOIR_PAN if k % 2 else -CHOIR_PAN)
    sf.write(out_path, out, rate, subtype="FLOAT")


def _place(out: np.ndarray, mono: np.ndarray, start: int, pan: float) -> None:
    end = min(len(out), start + len(mono))
    if end <= start:
        return
    angle = (pan + 1) * np.pi / 4
    out[start:end, 0] += mono[:end - start] * np.cos(angle) * np.sqrt(2)
    out[start:end, 1] += mono[:end - start] * np.sin(angle) * np.sqrt(2)

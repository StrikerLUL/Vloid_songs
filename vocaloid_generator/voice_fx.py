# voice_fx.py – Gesang lebendiger machen: Atmer vor den Phrasen, Echo auf dem letzten Wort, Vibrato und Übergänge
# zwischen den Tönen, jede Phrase aus der saubersten von mehreren Fassungen (Comping), Ausdruck pro Phrase und ein
# Chor im letzten Refrain.
# Alles arbeitet auf fertig gesungenen Spuren und kennt dazu die Noten (in Sekunden ab Songanfang).
import logging
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
FRAME = 0.005                # Rahmen der Tonhöhenanalyse mit WORLD (Sekunden)
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
def add_breaths(path: str, notes: list, seed: int = 0) -> int:
    """Vor jeder Phrase, vor der genug Pause ist, ein hörbares Einatmen in die Gesangsspur mischen.
    Längere Phrasen bekommen einen tieferen Atemzug. Rückgabe: Anzahl der Atmer."""
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    level = _sung_level(audio.mean(axis=1), rate)
    if level <= 0:
        return 0
    rng = np.random.default_rng(seed)
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
        track[a:a + n] += breath(n, rate, rng) * gain
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


def reshape(path: str, notes: list, vibrato: float = 1.0, glide: float = 1.0) -> bool:
    """Vibrato und Übergänge einer gesungenen Spur mit dem WORLD-Vocoder ändern. Gerechnet wird Phrase für Phrase,
    die Pausen bleiben unberührt. False, wenn nichts zu tun war."""
    if abs(vibrato - 1.0) < 1e-3 and abs(glide - 1.0) < 1e-3:
        return False
    import pyworld as pw
    audio, rate = sf.read(path, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    out = mono.copy()
    pad = 0.15
    for phrase in phrases(notes):
        a = max(0, int((phrase[0].start - pad) * rate))
        b = min(len(mono), int((phrase[-1].end + pad) * rate))
        if b - a < int(0.1 * rate):
            continue
        x = np.ascontiguousarray(mono[a:b])
        f0, times = pw.dio(x, rate, f0_floor=70.0, f0_ceil=1100.0, frame_period=FRAME * 1000)
        f0 = pw.stonemask(x, f0, times, rate)
        if not np.any(f0 > 0):
            continue
        sp = pw.cheaptrick(x, f0, times, rate)
        ap = pw.d4c(x, f0, times, rate)
        new = shape_pitch(f0, FRAME, phrase, vibrato, glide, offset=a / rate)
        y = pw.synthesize(new, sp, ap, rate, frame_period=FRAME * 1000)[:len(x)]
        y = np.pad(y, (0, len(x) - len(y)))
        fade = min(len(y) // 4, int(0.01 * rate))
        ramp = np.linspace(0, 1, fade)
        y[:fade] = x[:fade] * (1 - ramp) + y[:fade] * ramp
        y[-fade:] = y[-fade:] * ramp[::-1] + x[-fade:] * (1 - ramp[::-1])
        out[a:b] = y
    sf.write(path, np.repeat(out[:, None], audio.shape[1], axis=1).astype(np.float32), rate, subtype="FLOAT")
    log.info("Vibrato %.1f, Übergänge %.1f", vibrato, glide)
    return True


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


def _note_errors(f0: np.ndarray, times: np.ndarray, notes: list) -> list:
    """[(Fehler mal Dauer, Dauer)] je Note: mittlere Abweichung in Cent, Aussetzer zählen wie 600 Cent."""
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
        out.append(((min(cents, 600.0) + 600.0 * (1 - len(sung) / len(sel))) * dur, dur))
    return out


def pitch_error(path: str, notes: list) -> float:
    """Wie weit eine Fassung danebenliegt (kleiner ist besser): mittlere Abweichung von den Noten in Cent,
    Aussetzer (stumm, wo gesungen werden soll) zählen wie 600 Cent, übersteuerte Stellen kosten extra."""
    f0, times, clipped, _, _ = _pitch_track(path)
    errors = _note_errors(f0, times, notes)
    weight = sum(d for _, d in errors)
    return (sum(e for e, _ in errors) / weight if weight else 600.0) + float(np.mean(clipped)) * 1e4


# ── Comping: jede Phrase aus der saubersten Fassung ──────────────────────────────
COMP_FADE = 0.03             # Überblendung an den Schnitten (Sekunden), mitten in der Pause zwischen zwei Phrasen


def phrase_errors(track: tuple, notes: list, groups: list) -> list:
    """Fehler je Phrase (wie pitch_error, nur über die Noten der Phrase und ihre Zeit)."""
    f0, times, clipped = track[:3]
    errors = _note_errors(f0, times, notes)
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


def comp(takes: list, notes: list, out_path: str, double_path: str = None, double_windows: list = ()) -> list:
    """
    Setzt die Hauptstimme Phrase für Phrase aus der saubersten Fassung zusammen und schreibt sie nach out_path.
    double_path: dort landet in den double_windows (Sekunden, z. B. die Refrains) die zweitbeste Fassung jeder Phrase,
    eine echte Doppelung statt einer Kopie. Rückgabe: die gewählte Fassung (Index in takes) je Phrase.
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
    scores = np.array([phrase_errors(tr, notes, groups) for tr in tracks])      # [Fassung, Phrase]
    order = np.argsort(scores, axis=0, kind="stable")
    choice = [int(order[0, p]) for p in range(len(groups))]
    cuts = _cut_points(groups)
    masks = _segment_masks(choice, cuts, len(takes), length, rate)
    sf.write(out_path, np.einsum("kt,ktc->tc", masks, audio), rate, subtype="FLOAT")
    if double_path and len(takes) > 1 and double_windows:
        keep = np.zeros(length, dtype=np.float32)
        for start, end in double_windows:
            keep[max(0, int(start * rate)):min(length, int(end * rate))] = 1.0
        second = [int(order[1, p]) for p in range(len(groups))]
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

# spoken.py – Sektion „Sprechen“ (1.3.0, G7)
#
# Eine Zeile unter [Sprechen] im Liedtext spricht die VOICEVOX-Sprechstimme frei, nicht im Takt wie beim Rap: so, wie
# man einen Satz sagt, mit der Satzmelodie von VOICEVOX. Sie beginnt kurz nach dem Anfang der Sektion und wird nur
# schneller, wenn sie sonst nicht in die Sektion passt. Dazu klingt sie nach Hall (wie aus einem großen Raum), Telefon
# (schmal, leicht verzerrt) oder trocken. Die Gesangs-Engine singt diese Zeile nie; läuft VOICEVOX nicht, fällt sie
# weg. Die Band spielt darunter leise wie im Breakdown, das Schlagzeug schweigt (styles.py).
import json
import logging
from typing import Optional

import numpy as np

import rap

log = logging.getLogger(__name__)

KIND = "Spoken"
SOUNDS = ("Hall", "Telefon", "trocken")
START = 0.5                 # Schläge nach dem Anfang der Sektion, bis gesprochen wird
ROOM = 1.0                  # Schläge vor dem Ende der Sektion, die frei bleiben
MAX_SPEED = 1.6             # schneller spricht die Stimme nicht, auch wenn die Zeile dann überhängt
HALL_SECONDS, HALL_WET = 1.6, 0.4
PHONE_BAND = (400.0, 3400.0)


def windows(plan) -> list:
    """[(Anfang, Ende)] der Sektionen „Sprechen“ in Schlägen."""
    if plan is None:
        return []
    return [(sec.start, sec.end) for sec in plan.sections if sec.kind == KIND and sec.has_vocals]


MIN_LINE = 4                # Moren: so lang ist eine Zeile mindestens, die die Melodie wiederholt hat


def once(text: str) -> str:
    """Füllt die Melodie die Sektion, indem sie die Zeile wiederholt, wird sie nur einmal gesprochen."""
    for period in range(MIN_LINE, len(text) // 2 + 1):
        if (text[:period] * (len(text) // period + 1)).startswith(text):
            return text[:period]
    return text


def lines(melody_data: list, silben: list, spans: list) -> list:
    """Der Text je Sektion „Sprechen“ als Kana (Silben auf gehaltenen Vokalen fallen weg): [(Anfang, Ende, Text)]."""
    out = []
    for start, end in spans:
        text = "".join(rap._kana(syllable) for _, _, syllable in rap.notes(melody_data, silben, [(start, end)]))
        if text.strip("ら"):
            out.append((start, end, once(text)))
    return out


def speed_for(natural: float, available: float) -> float:
    """So viel schneller spricht die Stimme, damit die Zeile in die Sektion passt (1 = wie sie spricht)."""
    if available <= 0 or natural <= available:
        return 1.0
    return min(MAX_SPEED, natural / available)


def _length(query: dict) -> float:
    moras = [m for phrase in query["accent_phrases"] for m in phrase["moras"] + ([phrase["pause_mora"]]
                                                                                  if phrase.get("pause_mora") else [])]
    return sum((m.get("consonant_length") or 0.0) + (m.get("vowel_length") or 0.0) for m in moras)


def sound(audio: np.ndarray, rate: int, kind: str, seed: int = 0) -> np.ndarray:
    """Hall: lange Fahne aus abklingendem Rauschen dazu; Telefon: nur die Mitten, leicht verzerrt; sonst trocken."""
    from scipy.signal import butter, fftconvolve, sosfilt
    if kind == "Telefon":
        sos = butter(4, PHONE_BAND, btype="bandpass", fs=rate, output="sos")
        x = sosfilt(sos, audio)
        peak = float(np.max(np.abs(x))) or 1.0
        return (np.tanh(2.5 * x / peak) * peak / np.tanh(2.5)).astype(np.float32)
    if kind == "Hall":
        rng = np.random.default_rng(seed)
        n = int(HALL_SECONDS * rate)
        tail = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)       # -60 dB nach HALL_SECONDS
        tail = sosfilt(butter(2, 5000.0, fs=rate, output="sos"), tail)
        tail /= np.sqrt(np.sum(tail ** 2)) or 1.0
        wet = fftconvolve(audio, tail)[:len(audio) + n]
        dry = np.pad(audio, (0, len(wet) - len(audio)))
        return (dry * (1 - HALL_WET) + wet * HALL_WET * 1.4).astype(np.float32)
    return audio.astype(np.float32)


def render(melody_data: list, silben: list, bpm: float, spans: list, url: str, speaker: int, rate: int,
           length: int, kind: str = "Hall", seed: int = 0) -> Optional[np.ndarray]:
    """Alle Zeilen der Sektionen „Sprechen“, frei gesprochen und an ihrem Platz: mono, length Samples."""
    import io

    import soundfile as sf

    import voicevox
    found = lines(melody_data, silben, spans)
    if not found:
        return None
    spb = 60.0 / bpm
    out = np.zeros(length, dtype=np.float32)
    for start, end, text in found:
        query = json.loads(voicevox._request(url, "/audio_query", {"text": text, "speaker": speaker}, {}, 30.0))
        speed = speed_for(_length(query), (end - start - START - ROOM) * spb)
        query.update(speedScale=speed, intonationScale=rap.INTONATION, prePhonemeLength=0.05, postPhonemeLength=0.2,
                     outputSamplingRate=rate, outputStereo=False)
        data = voicevox._request(url, "/synthesis", {"speaker": speaker}, query, 120.0)
        audio, got = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        if got != rate:
            from scipy.signal import resample_poly
            audio = resample_poly(audio, rate, got).astype(np.float32)
        audio = sound(audio, rate, kind, seed)
        begin = int(round((start + START) * spb * rate))
        if begin + len(audio) > len(out):
            out = np.concatenate([out, np.zeros(begin + len(audio) - len(out), dtype=np.float32)])
        out[begin:begin + len(audio)] += audio
        log.info("Gesprochen bei Schlag %g: „%s“ (%s%s)", start, text, kind,
                 f", {speed:.2f}× so schnell" if speed > 1.0 else "")
    return out

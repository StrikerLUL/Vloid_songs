# vocal_chops.py – Vocal Chops im Drop (v6 Nr. 14)
#
# Wie in Future Bass und EDM-J-Pop: kurze Schnipsel der eigenen Hauptstimme, ausgeschnitten und auf die Akkordtöne
# umgestimmt, spielen im Drop (im Future Bass auch im Intro) einen Riff. Nur schneiden und umstimmen wie ein Sampler
# (schneller oder langsamer abgespielt, dadurch heller oder dunkler), keine KI. Aus dem fertigen Gesang (vocals.wav)
# und den Noten der Melodie, daher nach dem Singen.
import logging
import os
from typing import Optional

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

FILE = "chops.wav"
# Stile mit Chops und die Sektionen ohne Gesang, in denen sie spielen
CHOP_STYLES = {"Future Bass": ("Drop", "Intro"), "J-Pop Energy": ("Drop",), "Kawaii Chiptune": ("Drop",),
               "Idol-Pop": ("Drop",), "Drum and Bass": ("Drop",), "Dark Vocaloid": ("Drop",)}
# Riff je Takt: (Schlag, Länge in Schlägen); der letzte Takt einer Sektion endet mit einem Stottern
PATTERN = ((0.0, 0.5), (0.75, 0.5), (1.5, 0.5), (2.0, 0.25), (2.5, 0.5), (3.25, 0.25), (3.5, 0.5))
STUTTER = ((0.0, 0.5), (0.75, 0.5), (1.5, 0.5), (2.0, 0.25), (2.5, 0.25), (3.0, 0.25), (3.25, 0.25), (3.5, 0.25),
           (3.75, 0.25))
PATTERN_68 = ((0.0, 1 / 3), (2 / 3, 1 / 3), (1.0, 2 / 3), (5 / 3, 1 / 3))      # zwei punktierte Viertel pro Takt
CONTOUR = (2, 1, 2, 3, 2, 1, 0, 1, 2)    # welcher Akkordton (von unten) die Töne eines Takts spielen
SNIPPETS = 3                             # so viele verschiedene Silben
MIN_NOTE = 0.18                          # Sekunden: kürzere Töne geben keinen Schnipsel her
SKIP = 0.04                              # Sekunden am Anfang des Tons (Konsonant) überspringen
MAX_SNIPPET = 0.4
ATTACK, RELEASE = 0.003, 0.02
PANS = (-0.3, 0.3)


def sections(plan) -> list:
    """Die Sektionen, in denen Chops spielen; leer in Stilen ohne Chops."""
    kinds = CHOP_STYLES.get(plan.style.name, ())
    return [sec for sec in plan.sections if sec.kind in kinds and not sec.has_vocals]


def hits(plan, sec) -> list:
    """[(Anfang, Länge in Schlägen, Nummer im Takt)] des Riffs in einer Sektion."""
    out = []
    bars = int(round((sec.end - sec.start) / sec.bar_beats))
    for bar in range(bars):
        if plan.meter == "6/8":
            pattern = PATTERN_68
        else:
            pattern = STUTTER if bar == bars - 1 and bars > 1 else PATTERN
            pattern = [(t, d) for t, d in pattern if t < sec.bar_beats - 1e-6]
        start = sec.start + bar * sec.bar_beats
        out += [(start + t, min(d, sec.end - start - t), k) for k, (t, d) in enumerate(pattern)]
    return out


def pitch(plan, beat: float, k: int, center: int) -> int:
    """Der Ton des k-ten Schlags im Takt: ein Akkordton um center, nach CONTOUR auf und ab."""
    pcs = plan.chord_at(beat).pcs
    tones = [p for p in range(center - 5, center + 8) if p % 12 in pcs][:4] or [center]
    return tones[CONTOUR[k % len(CONTOUR)] % len(tones)]


def snippets(audio: np.ndarray, rate: int, melody_data: list, silben: list, bpm: float, plan) -> list:
    """[(Mono-Audio, Tonhöhe)]: die Vokale der längsten Töne aus den Refrains, je Silbe einer."""
    spb = 60.0 / bpm
    notes, t, i = [], 0.0, 0
    for note, dur in melody_data:
        if note is not None:
            if dur * spb >= MIN_NOTE:
                notes.append((t, dur, int(note), str(silben[i]) if i < len(silben) else ""))
            i += 1
        t += dur
    chorus = [n for n in notes if plan.section_at(n[0]).kind == "Chorus"] or notes
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    out, used = [], set()
    for start, dur, note, syllable in sorted(chorus, key=lambda n: -n[1]):
        a = int((start * spb + SKIP) * rate)
        b = min(int((start * spb + min(dur * spb, SKIP + MAX_SNIPPET)) * rate), len(audio))
        piece = audio[a:b]
        if len(piece) < MIN_NOTE / 2 * rate or np.sqrt(np.mean(piece ** 2)) < 0.05 * max(peak, 1e-6):
            continue
        if syllable in used:
            continue
        used.add(syllable)
        out.append((piece.astype(np.float32), note))
        if len(out) == SNIPPETS:
            break
    return out


def repitch(piece: np.ndarray, semitones: float) -> np.ndarray:
    """Schneller (höher) oder langsamer (tiefer) abspielen wie ein Sampler."""
    ratio = 2.0 ** (semitones / 12.0)
    positions = np.arange(0.0, len(piece) - 1, ratio)
    return np.interp(positions, np.arange(len(piece)), piece).astype(np.float32)


def _shaped(piece: np.ndarray, length: int, rate: int) -> np.ndarray:
    piece = piece[:length].copy()
    attack, release = min(int(ATTACK * rate), len(piece)), min(int(RELEASE * rate), len(piece))
    if attack:
        piece[:attack] *= np.linspace(0, 1, attack, dtype=np.float32)
    if release:
        piece[-release:] *= np.linspace(1, 0, release, dtype=np.float32)
    return piece


def render(plan, melody_data: list, silben: list, bpm: float, vocals_wav: str, out_path: str) -> Optional[str]:
    """Die Chops aller Sektionen als Stereo-Spur so lang wie der Gesang; None ohne Chops."""
    found = sections(plan)
    if not found or not os.path.isfile(vocals_wav):
        return None
    audio, rate = sf.read(vocals_wav, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    pieces = snippets(mono, rate, melody_data, silben, bpm, plan)
    if not pieces:
        log.info("Keine Vocal Chops: kein Ton im Gesang lang genug")
        return None
    center = int(np.median([p for _, p in pieces]))
    spb = 60.0 / bpm
    length = max(len(mono), int(max(sec.end for sec in found) * spb * rate) + rate)
    out = np.zeros((length, 2), dtype=np.float32)
    count = 0
    for sec in found:
        for beat, dur, k in hits(plan, sec):
            piece, source = pieces[k % len(pieces)]
            shift = pitch(plan, beat, k, center) - source
            while abs(shift) > 12:                          # höchstens eine Oktave umstimmen
                shift -= 12 * np.sign(shift)
            sound = _shaped(repitch(piece, shift), int(dur * spb * rate * 0.95), rate)
            at = int(beat * spb * rate)
            end = min(at + len(sound), length)
            angle = (PANS[k % 2] + 1) * np.pi / 4
            out[at:end, 0] += sound[:end - at] * np.cos(angle) * np.sqrt(2)
            out[at:end, 1] += sound[:end - at] * np.sin(angle) * np.sqrt(2)
            count += 1
    sf.write(out_path, out, rate, subtype="FLOAT")
    log.info("Vocal Chops: %d Töne aus %d Silben in %s", count, len(pieces),
             ", ".join(sec.kind for sec in found))
    return out_path

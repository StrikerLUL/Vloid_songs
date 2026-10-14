# sfz.py – ein kleiner Sampler für Instrumente im SFZ-Format (z. B. VSCO 2 Community Edition)
#
# Eine SFZ-Datei ist Text: sie sagt, welche Aufnahme (WAV) für welchen Ton und welche Anschlagstärke spielt.
# Dieser Sampler kann, was Orchester-Bibliotheken wie VSCO 2 brauchen: Tonbereiche und Anschlag-Schichten,
# Wechsel zwischen mehreren Aufnahmen desselben Tons (seq_length/seq_position, lorand/hirand), Lautstärke,
# Stimmung, Panorama und eine Hüllkurve (Einschwingen, Halten, Abklingen, Ausklingen). Töne zwischen zwei
# Aufnahmen stimmt er aus der nächsten Aufnahme hoch oder herunter (kubische Interpolation). Umschalt-Töne
# (sw_*) und Loslass-Aufnahmen (trigger=release) spielt er nicht.
import functools
import logging
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CACHE_BYTES = 400 * 2**20       # so viel Speicher dürfen geladene Aufnahmen belegen
MIN_FADE = 0.005                # kürzestes Ein- und Ausblenden in Sekunden, gegen Knackser
END_FADE = 0.03                 # Ausblenden, wenn ein Ton länger ist als seine Aufnahme
SKIP_FADE = 0.015               # Einblenden, wenn der Anfang einer Aufnahme übersprungen ist
CHOKE_FADE = 0.03               # spielt derselbe Ton neu, klingt der alte so schnell aus (wie eine neu gestrichene Saite)
RELEASE_DB = -60.0              # so leise ist ein Ton nach seiner Ausklingzeit (ampeg_release)
SILENCE_DB = -40.0              # leiser als das (unter dem lautesten Moment) gilt der Anfang einer Aufnahme als Stille
SWELL_DB = -10.0                # ab hier ist ein langsam einsetzender Ton „da“
MAX_RELEASE = 4.0               # längeres Ausklingen kürzen (Harfe und Pauken haben 12 s), sonst wird es sehr langsam
NOTE_NAMES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_TOKEN = re.compile(r"<(\w+)>|(\w+)=")
_LEVELS = ("control", "global", "master", "group")


@dataclass(frozen=True)
class Region:
    """Eine Aufnahme und wann und wie sie spielt."""
    sample: str                 # Pfad der WAV-Datei
    lokey: int = 0
    hikey: int = 127
    keycenter: int = 60         # Ton der Aufnahme
    lovel: int = 0
    hivel: int = 127
    volume: float = 0.0         # dB
    tune: float = 0.0           # Cent
    transpose: int = 0          # Halbtöne
    keytrack: float = 100.0     # Cent pro Halbton Abstand zum keycenter
    veltrack: float = 100.0     # Prozent: wie stark der Anschlag die Lautstärke bestimmt
    pan: float = 0.0            # -100 links … 100 rechts
    offset: int = 0             # erstes gespieltes Sample der Aufnahme
    attack: float = 0.0         # Sekunden
    hold: float = 0.0
    decay: float = 0.0
    sustain: float = 100.0      # Prozent
    release: float = 0.0
    seq_length: int = 1
    seq_position: int = 1
    lorand: float = 0.0
    hirand: float = 1.0

    def key_distance(self, pitch: int) -> int:
        return max(self.lokey - pitch, pitch - self.hikey, 0)

    def vel_distance(self, velocity: int) -> int:
        return max(self.lovel - velocity, velocity - self.hivel, 0)


def note_number(value: str) -> int:
    """MIDI-Ton aus einer Zahl oder einem Namen wie c4 (= 60), f#3 oder eb5."""
    value = value.strip().lower()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    m = re.fullmatch(r"([a-g])([#b]?)(-?\d+)", value)
    if not m:
        raise ValueError(f"kein Ton: {value}")
    name, sign, octave = m.groups()
    return NOTE_NAMES[name] + {"#": 1, "b": -1, "": 0}[sign] + (int(octave) + 1) * 12


def parse(path: str) -> list:
    """Alle spielbaren Regionen einer SFZ-Datei, mit den geerbten Angaben aus <global>, <master> und <group>."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = re.sub(r"//[^\n]*", "", f.read())
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    levels = {name: {} for name in _LEVELS}
    current, region, raw = None, None, []
    tokens = list(_TOKEN.finditer(text))
    for k, m in enumerate(tokens):
        header, opcode = m.groups()
        if header:
            if region is not None:
                raw.append(region)
            region = None
            if header == "region":
                region = {**levels["control"], **levels["global"], **levels["master"], **levels["group"]}
                current = None
            elif header in levels:
                # ein neuer Kopf ersetzt seine Angaben und die der Ebenen darunter
                for name in ("control",) if header == "control" else _LEVELS[_LEVELS.index(header):]:
                    levels[name] = {}
                current = header
            else:
                current = "ignored"     # <curve>, <effect>, <midi> … braucht dieser Sampler nicht
            continue
        end = tokens[k + 1].start() if k + 1 < len(tokens) else len(text)
        value = text[m.end():end].strip()
        if region is not None:
            region[opcode] = value
        elif current in levels:
            levels[current][opcode] = value
    if region is not None:
        raw.append(region)
    folder = os.path.dirname(os.path.abspath(path))
    regions = []
    for opcodes in raw:
        try:
            r = _region(opcodes, folder)
        except ValueError as e:
            log.debug("%s: Region übersprungen (%s)", os.path.basename(path), e)
            continue
        if r is not None:
            regions.append(r)
    return regions


def _region(o: dict, folder: str):
    if "sample" not in o or o.get("trigger", "attack") != "attack" or any(k.startswith("sw_") for k in o):
        return None
    sample = (o.get("default_path", "") + o["sample"]).replace("\\", "/")
    lokey, hikey = note_number(o.get("lokey", "0")), note_number(o.get("hikey", "127"))
    center = o.get("pitch_keycenter", "60")
    keycenter = note_number(center) if center != "sample" else 60
    if "key" in o:
        lokey = hikey = keycenter = note_number(o["key"])
    return Region(
        sample=os.path.normpath(os.path.join(folder, sample)),
        lokey=lokey, hikey=hikey, keycenter=keycenter,
        lovel=int(o.get("lovel", 0)), hivel=int(o.get("hivel", 127)),
        volume=float(o.get("volume", 0)), tune=float(o.get("tune", 0)), transpose=int(o.get("transpose", 0)),
        keytrack=float(o.get("pitch_keytrack", 100)), veltrack=float(o.get("amp_veltrack", 100)),
        pan=float(o.get("pan", 0)), offset=int(o.get("offset", 0)),
        attack=float(o.get("ampeg_attack", 0)), hold=float(o.get("ampeg_hold", 0)),
        decay=float(o.get("ampeg_decay", 0)), sustain=float(o.get("ampeg_sustain", 100)),
        release=float(o.get("ampeg_release", 0)),
        seq_length=max(int(o.get("seq_length", 1)), 1), seq_position=int(o.get("seq_position", 1)),
        lorand=float(o.get("lorand", 0)), hirand=float(o.get("hirand", 1)),
    )


class Instrument:
    """Eine geladene SFZ-Datei."""

    def __init__(self, path: str):
        self.path = path
        self.regions = parse(path)
        if not self.regions:
            raise ValueError(f"{os.path.basename(path)} hat keine spielbaren Regionen")
        self.low = min(r.lokey for r in self.regions)
        self.high = max(r.hikey for r in self.regions)

    def samples(self) -> list:
        """Die Aufnahmen, die diese Datei braucht."""
        return sorted({r.sample for r in self.regions})

    def pick(self, pitch: int, velocity: int, turn: int = 0, chance: float = 0.0) -> list:
        """
        Die Regionen, die einen Ton spielen. Trifft keine Region den Ton oder Anschlag genau, nimmt er die nächsten.
        turn: wie oft dieser Ton schon gespielt hat (für seq_position), chance: Zufallszahl in [0, 1) (lorand/hirand).
        """
        nearest = min(r.key_distance(pitch) for r in self.regions)
        found = [r for r in self.regions if r.key_distance(pitch) == nearest]
        nearest = min(r.vel_distance(velocity) for r in found)
        found = [r for r in found if r.vel_distance(velocity) == nearest]
        found = [r for r in found if (turn % r.seq_length) + 1 == r.seq_position] or found
        return [r for r in found if r.lorand <= chance < r.hirand] or found


@functools.lru_cache(maxsize=64)
def _instrument(path: str, mtime: float) -> Instrument:
    return Instrument(path)


def load(path: str) -> Instrument:
    """Die SFZ-Datei path, einmal gelesen und dann aus dem Speicher."""
    return _instrument(os.path.abspath(path), os.path.getmtime(path))


# ── Aufnahmen ───────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Recording:
    data: np.ndarray        # int16, (Frames, Kanäle)
    rate: int
    sound: int              # erstes Frame, in dem etwas zu hören ist (Stille davor überspringt der Sampler)
    swell: int              # erstes Frame, in dem der Ton fast voll da ist (-10 dB)


_cache: OrderedDict = OrderedDict()
_cache_bytes = 0
_lock = threading.Lock()


def _sample(path: str):
    """Die Aufnahme path, einmal geladen und dann aus dem Speicher; None, wenn sie fehlt oder kaputt ist."""
    global _cache_bytes
    with _lock:
        if path in _cache:
            _cache.move_to_end(path)
            return _cache[path]
    try:
        data, rate = sf.read(path, dtype="int16", always_2d=True)
        recording = Recording(data, rate, *_onsets(data, rate)) if len(data) >= 4 else None
    except (RuntimeError, OSError) as e:        # soundfile: LibsndfileError ist ein RuntimeError
        log.warning("Aufnahme fehlt oder ist kaputt: %s (%s)", path, e)
        recording = None
    with _lock:
        _cache[path] = recording
        _cache_bytes += 0 if recording is None else recording.data.nbytes
        while _cache_bytes > CACHE_BYTES and len(_cache) > 1:
            _, old = _cache.popitem(last=False)
            _cache_bytes -= 0 if old is None else old.data.nbytes
    return recording


def _onsets(data: np.ndarray, rate: int) -> tuple:
    """(erstes hörbares Frame, erstes Frame bei -10 dB der 20-ms-Lautstärke) in den ersten drei Sekunden."""
    head = np.abs(data[:3 * rate].astype(np.float32)).max(axis=1)
    peak = float(head.max())
    if peak <= 0:
        return 0, 0
    sound = int(np.argmax(head > peak * 10 ** (SILENCE_DB / 20)))
    window = max(rate // 50, 1)
    frames = head[:len(head) // window * window].reshape(-1, window)
    if not len(frames):
        return sound, sound
    level = np.sqrt(np.mean(np.square(frames), axis=1))
    swell = int(np.argmax(level >= level.max() * 10 ** (SWELL_DB / 20))) * window
    return sound, max(swell, sound)


# ── Spielen ─────────────────────────────────────────────────────────────────────────

def render(instrument: Instrument, notes: list, sample_rate: int = SAMPLE_RATE, seed: int = 0,
           swell: float = None, retrigger: bool = True) -> np.ndarray:
    """
    Spielt notes (mit start, end, pitch, velocity, z. B. pretty_midi.Note) und gibt float32 der Form (2, Samples)
    zurück. seed macht die Auswahl zwischen gleichwertigen Aufnahmen wiederholbar. Stille am Anfang einer Aufnahme
    überspringt der Sampler, damit jeder Ton auf dem Schlag kommt. swell: braucht eine Aufnahme länger als so viele
    Sekunden, bis sie fast laut ist (langsam einsetzende Streicher), beginnt sie entsprechend später; None = nie.
    retrigger: ein neuer Ton gleicher Höhe beendet den alten; aus (Schlagzeug), wenn die Tonlängen das schon regeln.
    """
    notes = sorted(notes, key=lambda n: (n.start, n.pitch))
    if not notes:
        return np.zeros((2, 0), dtype=np.float32)
    rng = np.random.default_rng(seed)
    out = np.zeros((2, int((max(n.end for n in notes) + MAX_RELEASE) * sample_rate) + 2), dtype=np.float32)
    used, turns = 0, {}
    for n, again in zip(notes, _next_same_pitch(notes)):
        turn = turns.get(n.pitch, 0)
        turns[n.pitch] = turn + 1
        start = int(round(n.start * sample_rate))
        until = None if again is None or not retrigger else again - n.start + CHOKE_FADE
        for region in instrument.pick(n.pitch, n.velocity, turn, float(rng.random())):
            audio = _voice(region, n.pitch, n.velocity, n.end - n.start, sample_rate, until, swell)
            if audio is not None:
                audio = audio[:, :out.shape[1] - start]
                out[:, start:start + audio.shape[1]] += audio
                used = max(used, start + audio.shape[1])
    return out[:, :used]


def _next_same_pitch(notes: list) -> list:
    """Für jeden Ton der Beginn des nächsten Tons gleicher Höhe (None, wenn keiner mehr kommt)."""
    following, seen = [None] * len(notes), {}
    for k in range(len(notes) - 1, -1, -1):
        following[k] = seen.get(notes[k].pitch)
        seen[notes[k].pitch] = notes[k].start
    return following


def _voice(r: Region, pitch: int, velocity: int, duration: float, rate: int, until: float = None,
           swell: float = None):
    """
    Ein Ton aus einer Aufnahme: umgestimmt, mit Hüllkurve, Lautstärke und Panorama. (2, Samples) oder None.
    until: spätestens nach so vielen Sekunden ist der Ton aus (weil derselbe Ton neu anschlägt).
    """
    rec = _sample(r.sample)
    if rec is None:
        return None
    semitones = (pitch - r.keycenter) * r.keytrack / 100 + r.transpose + r.tune / 100
    step = 2 ** (semitones / 12) * rec.rate / rate
    first = r.offset
    if not first:       # ohne eigenen Startpunkt: Stille davor und, wenn gewünscht, ein zu langes Anschwellen weglassen
        first = max(rec.sound - int(MIN_FADE * rec.rate), 0)
        if swell is not None:
            first = max(first, rec.swell - int(swell * rec.rate))
    release = min(max(r.release, MIN_FADE), MAX_RELEASE)
    available = int((len(rec.data) - 3 - first) / step)
    full = int((max(duration, 0.0) + release) * rate)
    n = min(available, full, full if until is None else int(until * rate))
    if n <= 0:
        return None
    audio = _cubic(rec.data, first + step * np.arange(n))
    # abgeschnitten (Aufnahme zu Ende, derselbe Ton schlägt neu an): etwas länger ausblenden
    end_fade = MIN_FADE if n == full else END_FADE if n == available else CHOKE_FADE
    attack = max(r.attack, MIN_FADE if first <= rec.sound else SKIP_FADE)
    vel = 1 - min(max(r.veltrack, 0.0), 100.0) / 100 * (1 - (velocity / 127) ** 2)
    audio *= _envelope(r, n, duration, attack, release, rate, end_fade) * np.float32(10 ** (r.volume / 20) * vel)
    if audio.shape[0] == 1:
        audio = np.vstack([audio, audio])
    return balance(audio[:2], r.pan / 100) if r.pan else audio[:2]


def _cubic(data: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Catmull-Rom-Interpolation von data (Frames, Kanäle, int16) an den Stellen pos; Rückgabe (Kanäle, len(pos))."""
    i = pos.astype(np.int64)
    f = (pos - i).astype(np.float32)[:, None]
    x0, x1, x2, x3 = (data[k].astype(np.float32) for k in (np.maximum(i - 1, 0), i, i + 1, i + 2))
    y = x1 + 0.5 * f * (x2 - x0 + f * (2 * x0 - 5 * x1 + 4 * x2 - x3 + f * (3 * (x1 - x2) + x3 - x0)))
    return (y * np.float32(1 / 32768)).T


def _envelope(r: Region, n: int, duration: float, attack: float, release: float, rate: int,
              end_fade: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / rate
    level = np.minimum(t / attack, 1.0)
    if r.sustain < 100:
        falling = np.clip((t - attack - r.hold) / max(r.decay, MIN_FADE), 0, 1)
        level = np.where(t >= attack + r.hold, 1 - (1 - r.sustain / 100) * falling, level)
    off = int(max(duration, 0.0) * rate)
    if off < n:
        start = level[off - 1] if off > 0 else 0.0
        level[off:] = start * 10 ** (RELEASE_DB / 20 * (t[off:] - t[off]) / release)
    fade = min(n, max(int(end_fade * rate), 1))
    level[n - fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return level.astype(np.float32)


def balance(audio: np.ndarray, pan: float) -> np.ndarray:
    """Stereo-Balance mit gleicher Leistung: pan -1 links … 1 rechts, 0 lässt alles, wie es ist."""
    angle = (max(-1.0, min(1.0, pan)) + 1) * np.pi / 4
    gains = np.array([[np.cos(angle)], [np.sin(angle)]], dtype=np.float32) * np.float32(np.sqrt(2))
    return audio * gains

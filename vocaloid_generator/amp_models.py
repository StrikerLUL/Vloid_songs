# amp_models.py – echte Verstärker als Modell: Neural Amp Modeler (1.3.0, I9)
#
# Der Neural Amp Modeler (NAM, Steven Atkinson, MIT-Lizenz) lernt aus Aufnahmen, wie ein echter Verstärker klingt.
# Ein Modell (.nam) ist eine Datei mit einem kleinen WaveNet: zwei Stapel aus zehn gedehnten Faltungen. Hier rechnet
# numpy dasselbe wie NAM (nam/models/wavenet.py), Block für Block, ohne PyTorch. Ist ein Modell eingerichtet
# (setup_nam.py lädt zwei frei nutzbare, GPL-3, aus der Sammlung der NAM-Gemeinschaft), spielen verzerrte E-Gitarren
# durch den Verstärker aus dem Modell statt durch den eingebauten Verzerrer; die Box (eingebaut oder eigene
# Impulsantwort) kommt wie bisher dahinter, denn die Modelle sind Verstärker ohne Box.
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "nam")
MODEL_RATE = 48000              # in dieser Abtastrate sind die Modelle gelernt (NAM ohne Angabe: 48 kHz)
BLOCK = 1 << 15                 # so viele Samples auf einmal, damit der Speicher klein bleibt
SILENT = 1e-6                   # leiser ist Stille (-120 dB)


@dataclass(frozen=True)
class Amp:
    file: str
    sha256: str
    name: str                   # so heißt der Verstärker in Protokoll und Anleitung
    author: str


# General MIDI 29 (Overdrive-Gitarre) und 30 (Distortion-Gitarre): je ein Verstärker
AMPS = {
    29: Amp("Tim R JCM2000 Crunch.nam", "d687c5829ae246a36d573d705bd296e8c26be48385f2948edf2db67f2ba67e87",
            "Marshall JCM2000 (Crunch)", "Tim R"),
    30: Amp("Helga B 6505+ Red ch - NoBoost.nam", "f389f5fcd4675cb7d8ec5134bea4d080fe12cac57839545a8f226f8f8797379b",
            "Peavey 6505+ (Red Channel)", "Helga Behrens"),
}


def path(program: int) -> str:
    return os.path.join(FOLDER, AMPS[program].file)


def covers(program: int) -> bool:
    return program in AMPS and os.path.isfile(path(program))


def installed() -> bool:
    return all(covers(p) for p in AMPS)


# ── WaveNet ─────────────────────────────────────────────────────────────────────
@dataclass
class _Layer:
    dilation: int
    conv: list                  # je Abgriff der Faltung (Kanäle, Kanäle)
    conv_bias: np.ndarray
    mixer: np.ndarray           # (Kanäle, Bedingung)
    out: np.ndarray             # 1×1-Faltung (Kanäle, Kanäle)
    out_bias: np.ndarray


@dataclass
class _Array:
    rechannel: np.ndarray       # (Kanäle, Eingang)
    layers: list
    head: np.ndarray            # (Kopf, Kanäle)
    head_bias: Optional[np.ndarray]
    kernel: int
    gated: bool

    @property
    def reach(self) -> int:
        return (self.kernel - 1) * sum(layer.dilation for layer in self.layers)


class WaveNet:
    """Ein NAM-Modell der Architektur WaveNet aus einer .nam-Datei (JSON: config, weights)."""

    def __init__(self, data: dict):
        if data.get("architecture") != "WaveNet":
            raise ValueError(f"nur WaveNet-Modelle, nicht {data.get('architecture')}")
        weights = np.asarray(data["weights"], dtype=np.float32)
        pos = 0

        def take(*shape):
            nonlocal pos
            n = int(np.prod(shape))
            if pos + n > len(weights):
                raise ValueError("zu wenige Gewichte im Modell")
            block = weights[pos:pos + n].reshape(shape)
            pos += n
            return block
        cfg = data["config"]
        self.arrays = []
        for spec in cfg["layers"]:
            ch, k, cond = spec["channels"], spec["kernel_size"], spec["condition_size"]
            mid = 2 * ch if spec.get("gated") else ch
            rechannel = take(ch, spec["input_size"])
            layers = []
            for d in spec["dilations"]:
                conv = take(mid, ch, k)
                layers.append(_Layer(d, [np.ascontiguousarray(conv[:, :, j]) for j in range(k)], take(mid)[:, None],
                                     take(mid, cond), take(ch, ch), take(ch)[:, None]))
            head = take(spec["head_size"], ch)
            bias = take(spec["head_size"]) if spec.get("head_bias") else None
            if spec.get("activation", "Tanh") != "Tanh":
                raise ValueError(f"Aktivierung {spec.get('activation')} wird nicht unterstützt")
            self.arrays.append(_Array(rechannel, layers, head, bias, k, bool(spec.get("gated"))))
        if cfg.get("head") is not None:
            raise ValueError("WaveNet mit eigenem Kopf wird nicht unterstützt")
        self.head_scale = float(weights[pos]) if pos < len(weights) else float(cfg.get("head_scale", 1.0))
        if pos + 1 != len(weights):
            raise ValueError("die Gewichte passen nicht zur Beschreibung des Modells")
        self.reach = sum(a.reach for a in self.arrays)       # so viele Samples Vorlauf braucht ein Ausgabe-Sample

    def _forward(self, x: np.ndarray) -> np.ndarray:
        """x: (Samples,) mit reach Samples Vorlauf; Rückgabe: (Samples - reach,), wie NAM ohne Polsterung."""
        cond = x[None, :]
        y, head = cond, None
        for array in self.arrays:
            length = y.shape[1] - array.reach
            y = _mul(array.rechannel, y)
            term = None
            for layer in array.layers:
                d, k = layer.dilation, array.kernel
                n = y.shape[1] - (k - 1) * d
                z = _mul(layer.mixer, cond[:, -n:])
                z += layer.conv_bias
                for j, w in enumerate(layer.conv):        # gedehnte Faltung: ein Abgriff alle d Samples
                    z += w @ y[:, j * d:j * d + n]
                if array.gated:
                    half = z.shape[0] // 2
                    act = np.tanh(z[:half]) / (1.0 + np.exp(-z[half:]))
                else:
                    act = np.tanh(z, out=z)
                res = layer.out @ act
                res += y[:, -n:]
                res += layer.out_bias
                y = res
                piece = act[:, -length:]
                term = piece if term is None else term[:, -length:] + piece
            head_in = term if head is None else head[:, -length:] + term
            head = array.head @ head_in + (array.head_bias[:, None] if array.head_bias is not None else 0.0)
        return self.head_scale * head[0]

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        """Ein ganzes Signal (mono, MODEL_RATE): vorne mit Stille gepolstert, blockweise, gleich lang zurück. Wo das
        Modell seit reach Samples nur Stille hört, gibt es immer denselben Wert aus; dort rechnet es nicht (eine
        Gitarren-Spur schweigt oft lange)."""
        audio = np.asarray(audio, np.float32)
        x = np.concatenate([np.zeros(self.reach, np.float32), audio])
        heard = np.concatenate([[0], np.cumsum(np.abs(x) > SILENT)])
        busy = (heard[self.reach + 1:] - heard[:-self.reach - 1]) > 0       # Ausgabe n hört x[n] bis x[n + reach]
        out = np.full(len(audio), self._forward(np.zeros(self.reach + 1, np.float32))[0], np.float32)
        edges = np.flatnonzero(np.diff(np.concatenate([[0], busy.astype(np.int8), [0]])))
        for first, last in zip(edges[::2], edges[1::2]):
            for start in range(first, last, BLOCK):
                end = min(last, start + BLOCK)
                out[start:end] = self._forward(x[start:end + self.reach])
        return out


def _mul(weights: np.ndarray, x: np.ndarray) -> np.ndarray:
    """weights @ x; bei einem Eingangskanal als Produkt, das ist zehnmal schneller als BLAS mit innerer Länge 1."""
    return weights * x if weights.shape[1] == 1 else weights @ x


@lru_cache(maxsize=4)
def model(file: str) -> WaveNet:
    with open(file, encoding="utf-8") as f:
        return WaveNet(json.load(f))


def play(audio: np.ndarray, program: int, rate: int) -> Optional[np.ndarray]:
    """Mono-Signal (1, Samples) oder (Samples,) durch den Verstärker für dieses Programm; gleiche Form und Rate.
    None ohne Modell oder bei einem Fehler (dann spielt der eingebaute Verzerrer)."""
    from scipy.signal import resample_poly
    if not covers(program):
        return None
    try:
        net = model(path(program))
        mono = np.asarray(audio, np.float32).reshape(-1)
        up = resample_poly(mono, MODEL_RATE, rate).astype(np.float32) if rate != MODEL_RATE else mono
        wet = net(up)
        back = resample_poly(wet, rate, MODEL_RATE).astype(np.float32) if rate != MODEL_RATE else wet
    except (OSError, ValueError, KeyError, MemoryError) as e:
        log.warning("Verstärker-Modell %s nicht gespielt (%s), nehme den eingebauten Verzerrer", AMPS[program].file, e)
        return None
    back = np.pad(back[:len(mono)], (0, max(0, len(mono) - len(back))))
    if not np.all(np.isfinite(back)):
        log.warning("Verstärker-Modell %s lieferte Unsinn, nehme den eingebauten Verzerrer", AMPS[program].file)
        return None
    log.info("Gitarre über %s (NAM-Modell von %s)", AMPS[program].name, AMPS[program].author)
    return back.reshape(np.shape(audio))

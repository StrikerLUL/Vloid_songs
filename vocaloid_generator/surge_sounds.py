# surge_sounds.py – Werks-Klänge von Surge XT statt der eigenen Synths (1.3.0, I8)
#
# Ist Surge XT eingerichtet (setup_surge.py, kostenlos, GPL-3), spielen die Unterspuren, die sonst eine eigene Stimme
# aus synth_engine spielen, einen passenden Klang aus Surge XT: Supersaw, Pluck, Chip-Lead, Future-Bass-Akkorde und
# Reese-Bass. Die Klänge sind .fxp-Dateien aus den Werks- und Gast-Klängen von Surge XT. Im Zustand des VST3 (ein
# JUCE-Block, von JUCE in eigenem Base64 verpackt) steckt genau der Inhalt einer .fxp; so lädt die App den Klang ohne
# Fenster. Jeder Klang wird so laut wie die eigene Stimme, die er ersetzt: die Spur bleibt im Mix, wie sie war. Fehlt
# Surge XT oder geht etwas schief, spielt die eigene Stimme.
import logging
import os
import re
import struct
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "surge")
PLUGIN = "Surge XT.vst3"
DATA = "SurgeXTData"            # neben dem VST3 findet Surge XT seine Klänge (wie in der portablen Ausgabe)
WARM_SECONDS = 0.3              # Surge lädt einen Klang im ersten Audio-Block; Töne darin gingen verloren
TAIL_SECONDS = 2.5
_PRIVATE = b"JUCEPrivateData"
_LOCK = threading.Lock()        # ein Plugin für alle Spuren: immer nur eine spielt


@dataclass(frozen=True)
class Sound:
    file: str                   # Pfad unter resources/data im Quellcode von Surge XT
    sha256: str
    transpose: int = 0          # Halbtöne, damit der Klang in der Lage der eigenen Stimme spielt
    poly: bool = False          # ein einstimmiger Klang spielt mehrstimmig (Akkorde)


SOUNDS = {
    "supersaw": Sound("patches_3rdparty/Luna/Leads/96 Osc Supersaw.fxp",
                      "4cca59981f136beb34142f5f11fa38ee0c5ecb95d2bed8d78e99b817a755a36a"),
    "pluck": Sound("patches_3rdparty/Vincent Zauhar/Plucks/Super Pluck.fxp",
                   "c80a5278982fe1a73cf8616d592f7b769bb6c0c2e16c00183ef2653aee85c681"),
    "chip": Sound("patches_3rdparty/Luna/Leads/Gameboy.fxp",
                  "5ebf62de7cf4753c32e22fb5fde04b6655581fac4db15d92d7104298ffc10b7b", poly=True),
    "fb_chord": Sound("patches_factory/Polysynths/Japanese Unison.fxp",
                      "4cdb5553fb932e0e7aef4fa85dee9eda9141cfd567003e16ac707682eede1337"),
    "reese": Sound("patches_3rdparty/Vospi/Basses/Primitive Reese.fxp",
                   "f1d68358e1de5d388619b21edcd72200b64685d48bbbf3b70f99e96e04e8694e", transpose=12),
}


def plugin_path() -> str:
    """Surge XT aus setup_surge.py, sonst ein installiertes (vst_sounds.find_surge); sonst ""."""
    import vst_sounds
    own = os.path.join(FOLDER, PLUGIN)
    return own if os.path.exists(own) else vst_sounds.find_surge()


def patch_path(voice: str) -> str:
    return os.path.join(FOLDER, DATA, *SOUNDS[voice].file.split("/"))


def covers(voice: str) -> bool:
    """Spielt Surge XT diese eigene Stimme?"""
    return voice in SOUNDS and os.path.isfile(patch_path(voice)) and bool(plugin_path())


def installed() -> bool:
    return bool(plugin_path()) and all(os.path.isfile(patch_path(v)) for v in SOUNDS)


def polyphonic(fxp: bytes) -> bytes:
    """Die .fxp mit Spielweise „Poly“: der XML-Teil hinter dem Kopf ("sub3", Länge, sechs Wavetable-Längen) ändert
    sich, seine Länge wird angepasst."""
    head = 60
    if fxp[head:head + 4] != b"sub3":
        return fxp
    size = struct.unpack("<I", fxp[head + 4:head + 8])[0]
    start = head + 32
    xml = fxp[start:start + size]
    poly = re.sub(rb'(<a_polymode type="0" value=")\d+(")', rb"\g<1>0\g<2>", xml)
    return fxp[:head + 4] + struct.pack("<I", len(poly)) + fxp[head + 8:start] + poly + fxp[start + size:]


def with_patch(state: bytes, fxp: bytes) -> bytes:
    """Der Zustand des Plugins (raw_state) mit dem Klang aus einer .fxp. Innen steht der Klang ohne den 60 Bytes
    langen Kopf der .fxp, dahinter der JUCE-Block (Länge, JUCEPrivateData), der bleibt."""
    from airwindows import juce_decode, juce_encode
    outer = re.search(rb"<IComponent>(.*?)</IComponent>", state)
    if outer is None or state[:4] != b"VC2!":
        raise ValueError("unbekannter Zustand von Surge XT")
    inner = juce_decode(outer.group(1).decode("ascii"))
    if not inner.endswith(_PRIVATE):
        raise ValueError("unbekannter Zustand von Surge XT")
    block = struct.unpack("<q", inner[-len(_PRIVATE) - 8:-len(_PRIVATE)])[0]
    private = inner[-(len(_PRIVATE) + 8 + block):]
    packed = juce_encode(fxp[60:] + private).encode("ascii")
    body = state[8:outer.start(1)] + packed + state[outer.end(1):]
    size = struct.unpack("<I", state[4:8])[0] + len(packed) - len(outer.group(1))
    return b"VC2!" + struct.pack("<I", size) + body


@lru_cache(maxsize=1)
def _plugin(path: str):
    from pedalboard import load_plugin
    return load_plugin(path)        # einmal laden (dauert Sekunden), die Spuren rendern nacheinander


def load(plugin, voice: str, rate: int) -> None:
    """Den Klang einer Stimme ins Plugin laden und kurz Stille spielen, bis Surge ihn übernommen hat."""
    sound = SOUNDS[voice]
    with open(patch_path(voice), "rb") as f:
        fxp = f.read()
    plugin.raw_state = with_patch(plugin.raw_state, polyphonic(fxp) if sound.poly else fxp)
    warm(plugin, rate)


def warm(plugin, rate: int) -> None:
    plugin([], duration=WARM_SECONDS, sample_rate=rate, num_channels=2)


def render(notes: list, voice: str, rate: int, path: str = "") -> Optional[np.ndarray]:
    """Die Noten (pretty_midi.Note) mit dem Surge-Klang der Stimme, so laut wie die eigene Stimme: (2, Samples).
    None ohne Surge XT oder bei einem Fehler."""
    import mido

    from synth_engine import render_notes
    path = path or plugin_path()
    if not notes or not path or voice not in SOUNDS or not os.path.isfile(patch_path(voice)):
        return None
    shift = SOUNDS[voice].transpose
    messages = []
    for n in notes:
        pitch = int(np.clip(n.pitch + shift, 0, 127))
        messages.append(mido.Message("note_on", note=pitch, velocity=n.velocity, time=n.start))
        messages.append(mido.Message("note_off", note=pitch, velocity=0, time=n.end))
    messages.sort(key=lambda m: (m.time, m.type == "note_on"))
    end = max(n.end for n in notes)
    try:
        with _LOCK:
            plugin = _plugin(path)
            load(plugin, voice, rate)
            audio = np.asarray(plugin(messages, duration=end + TAIL_SECONDS, sample_rate=rate, num_channels=2),
                               dtype=np.float32)
    except Exception as e:  # noqa: BLE001 – ein kaputtes Plugin darf den Song nicht anhalten
        log.warning("Surge XT konnte %s nicht spielen (%s), nimmt die eigene Stimme", voice, e)
        return None
    audio = np.vstack([audio, audio]) if audio.ndim == 1 or audio.shape[0] == 1 else audio[:2]
    level = float(np.sqrt(np.mean(audio ** 2)))
    if not np.isfinite(level) or level < 1e-6:
        log.warning("Surge XT blieb bei %s stumm, nimmt die eigene Stimme", voice)
        return None
    own = render_notes(notes, voice)
    audio *= float(np.sqrt(np.mean(own ** 2))) / level
    log.info("Surge XT spielt %s (%s)", voice, os.path.basename(SOUNDS[voice].file)[:-4])
    return audio

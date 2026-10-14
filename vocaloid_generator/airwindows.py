# airwindows.py – Effekte aus Airwindows Consolidated (Gesang 1.1, D6)
#
# Airwindows Consolidated (Chris Johnson und Paul Walker, frei) bündelt fast 400 Airwindows-Effekte in einem VST3.
# pedalboard lädt es wie Surge XT. Welcher Effekt läuft, steht nicht in einem Parameter, sondern im Zustand des
# Plugins (XML, von JUCE in eigenem Base64 verpackt): currentProcessorName und die Regler awp_0 bis awp_9 (0 bis 1).
# Die App nutzt zwei Klassiker: ToTape9 als Bandsättigung auf dem Gesang und Console7 (Channel auf jeder Spur,
# Buss auf der Summe) als analoges Mischpult. setup_airwindows.py lädt das Plugin nach tools\airwindows.
import logging
import os
import re
import struct
from typing import Optional

import numpy as np

import config

log = logging.getLogger(__name__)

PLUGIN = "Airwindows Consolidated.vst3"
FOLDER = os.path.join(config.REPO_ROOT, "tools", "airwindows")

# (Effekt, Regler awp_0 …) mit den Grundwerten von Airwindows; ToTape9 ohne Flattern (der Gesang soll nicht leiern)
TAPE = ("ToTape9", (0.5, 0.5, 0.5, 0.0, 0.5, 0.5, 0.5, 0.5, 0.5))
CONSOLE_CHANNEL = ("Console7Channel", (0.772,))
CONSOLE_BUSS = ("Console7Buss", (0.772,))

_TABLE = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"


def system_folders() -> tuple:
    """Wo der Installer von Airwindows (oder eine DAW) VST3-Plugins hinlegt."""
    common = os.environ.get("COMMONPROGRAMFILES", r"C:\Program Files\Common Files")
    return (os.path.join(common, "VST3"), os.path.join(os.path.expanduser("~"), ".vst3"), "/usr/lib/vst3",
            "/Library/Audio/Plug-Ins/VST3")


def find() -> str:
    """Pfad zum Plugin: aus setup_airwindows.py oder dort, wo der Installer es hinlegt; sonst ""."""
    for folder in (FOLDER,) + system_folders():
        path = os.path.join(folder, PLUGIN)
        if os.path.exists(path):
            return path
    return ""


def available() -> bool:
    return bool(find())


# ── JUCE-Zustand ───────────────────────────────────────────────────────────────
def juce_decode(text: str) -> bytes:
    """MemoryBlock::fromBase64Encoding von JUCE: "Länge." und 6 Bit je Zeichen, das niedrigste zuerst."""
    size, _, data = text.partition(".")
    out = bytearray(int(size))
    pos = 0
    for ch in data:
        value = _TABLE.index(ch)
        for bit in range(6):
            if value >> bit & 1:
                byte, shift = divmod(pos + bit, 8)
                if byte < len(out):
                    out[byte] |= 1 << shift
        pos += 6
    return bytes(out)


def juce_encode(data: bytes) -> str:
    bits = len(data) * 8
    chars = []
    for pos in range(0, bits, 6):
        value = 0
        for bit in range(6):
            p = pos + bit
            if p < bits and data[p // 8] >> (p % 8) & 1:
                value |= 1 << bit
        chars.append(_TABLE[value])
    return f"{len(data)}." + "".join(chars)


def with_processor(state: bytes, name: str, values: tuple) -> bytes:
    """Der Zustand des Plugins (raw_state) mit einem anderen Effekt und seinen Reglern."""
    outer = re.search(rb"<IComponent>(.*?)</IComponent>", state)
    if outer is None:
        raise ValueError("unbekannter Zustand von Airwindows Consolidated")
    inner = juce_decode(outer.group(1).decode("ascii"))
    if inner[:4] != b"VC2!":
        raise ValueError("unbekannter Zustand von Airwindows Consolidated")
    end = inner.index(b"\x00", 8)
    xml = inner[8:end].decode("utf-8")
    xml = re.sub(r'currentProcessorName="[^"]*"', f'currentProcessorName="{name}"', xml)
    for k in range(10):
        xml = re.sub(rf'awp_{k}="[^"]*"', f'awp_{k}="{values[k] if k < len(values) else 0.0}"', xml)
    body = xml.encode("utf-8") + b"\x00"
    packed = b"VC2!" + struct.pack("<I", len(body)) + body + inner[end + 1:]
    return state[:outer.start(1)] + juce_encode(packed).encode("ascii") + state[outer.end(1):]


def effect(spec: tuple, path: Optional[str] = None):
    """Ein Airwindows-Effekt (spec: (Name, Regler)) als pedalboard-Plugin; wirft, wenn es fehlt."""
    from pedalboard import load_plugin
    plugin = load_plugin(path or find())
    plugin.raw_state = with_processor(plugin.raw_state, *spec)
    return plugin


def tape_for(drive_mix: float) -> tuple:
    """ToTape9 mit mehr oder weniger Eingang, passend zur Sättigung der Gesangskette (vocal_tone.Tone.drive_mix)."""
    name, values = TAPE
    drive = float(np.clip(0.5 + (drive_mix - 0.3) * 0.5, 0.4, 0.65))
    return name, (drive,) + values[1:]

# test_airwindows.py – Effekte aus Airwindows Consolidated (D6): Zustand des Plugins, Einrichten und Mix
import io
import os
import zipfile

import numpy as np
import pytest
import soundfile as sf

import airwindows
import config
import einrichten
import main
import mixer
from settings import SongSettings

RATE = mixer.SAMPLE_RATE
REAL = os.path.join(config.REPO_ROOT, "tools", "airwindows")


def fake_state(xml: str) -> bytes:
    body = xml.encode() + b"\x00"
    inner = b"VC2!" + len(body).to_bytes(4, "little") + body + b"\x00" * 17 + b"JUCEPrivateData"
    return (b'VC2!\x00\x00\x00\x00<?xml version="1.0"?> <VST3PluginState><IComponent>' +
            airwindows.juce_encode(inner).encode() + b"</IComponent></VST3PluginState>\x00")


def test_juce_base64_goes_there_and_back():
    data = bytes(np.random.default_rng(0).integers(0, 256, 301, dtype=np.uint8))
    assert airwindows.juce_decode(airwindows.juce_encode(data)) == data


def test_the_state_names_the_effect_and_its_controls():
    xml = ('<awconsolidated streamingVersion="8524" currentProcessorName="Galactic" awp_0="0.5" awp_1="0.5" '
           'awp_2="0.5" awp_3="1.0" awp_4="1.0" awp_5="0.0" awp_6="0.0" awp_7="0.0" awp_8="0.0" awp_9="0.0" '
           'inlev="0.5" outlev="0.5" monoBehaviour="0"/>')
    new = airwindows.with_processor(fake_state(xml), *airwindows.TAPE)
    inner = airwindows.juce_decode(new.split(b"<IComponent>")[1].split(b"</IComponent>")[0].decode())
    text = inner[8:inner.index(b"\x00", 8)].decode()
    assert int.from_bytes(inner[4:8], "little") == len(text) + 1
    assert 'currentProcessorName="ToTape9"' in text and 'awp_3="0.0"' in text and 'awp_8="0.5"' in text
    assert 'awp_9="0.0"' in text and 'inlev="0.5"' in text and inner.endswith(b"JUCEPrivateData")
    with pytest.raises(ValueError):
        airwindows.with_processor(b"kein Zustand", *airwindows.TAPE)


def test_more_saturation_drives_the_tape_harder():
    assert airwindows.tape_for(0.45)[1][0] > airwindows.tape_for(0.3)[1][0] == 0.5 > airwindows.tape_for(0.15)[1][0]


# ── Einrichten ─────────────────────────────────────────────────────────────────
SUMS = """dfd3  artifacts/dawplugin-windows-x64/AirwindowsConsolidated-2026-10-11-8a67b80-Windows.zip
7beb  artifacts/dawplugin-windows-x64/AirwindowsConsolidated-2026-10-11-8a67b80-Windows-64bit-setup.exe
5e56  artifacts/dawplugin-windows-juce7/AirwindowsConsolidated-2026-10-11-8a67b80-Windows-windows7.zip
9144  artifacts/build-docker-linux/AirwindowsConsolidated-2026-10-11-8a67b80-Linux.zip
"""


def setup_module_():
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_airwindows",
                                                  os.path.join(config.REPO_ROOT, "setup_airwindows.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_picks_this_weeks_build_and_unpacks_only_the_plugin(tmp_path):
    setup = setup_module_()
    assert setup.choose(SUMS, "Windows") == ("AirwindowsConsolidated-2026-10-11-8a67b80-Windows.zip", "dfd3")
    assert setup.choose(SUMS, "Linux")[0].endswith("-Linux.zip") and setup.choose(SUMS, "Darwin") == (None, None)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Airwindows Consolidated.vst3/Contents/x86_64-win/Airwindows Consolidated.vst3", b"dll")
        z.writestr("Airwindows Consolidated.vst3/Contents/Resources/moduleinfo.json", b"{}")
        z.writestr("Airwindows Consolidated.exe", b"exe")
        z.writestr("LICENSE.gpl3", b"GPL")
        z.writestr("Airwindows Consolidated.vst3/../../boese.txt", b"x")
    target = tmp_path / "ziel"
    assert setup.unpack(buffer.getvalue(), str(target)) == 3
    assert not (tmp_path / "boese.txt").exists()                               # nichts außerhalb des Zielordners
    tmp_path = target
    assert (tmp_path / "Airwindows Consolidated.vst3" / "Contents" / "x86_64-win" / "Airwindows Consolidated.vst3").exists()
    assert not (tmp_path / "Airwindows Consolidated.exe").exists() and (tmp_path / "LICENSE.gpl3").exists()
    assert einrichten.find("airwindows").script == "setup_airwindows.py"


# ── im Mix ─────────────────────────────────────────────────────────────────────
def tracks(tmp_path):
    t = np.arange(2 * RATE) / RATE
    vocal, band = str(tmp_path / "vocals.wav"), str(tmp_path / "piano.wav")
    sf.write(vocal, 0.2 * np.sin(2 * np.pi * 330 * t), RATE)
    sf.write(band, 0.2 * np.sin(2 * np.pi * 220 * t), RATE)
    return [vocal, band]


def test_the_mix_uses_tape_and_console_when_airwindows_is_there(tmp_path, monkeypatch):
    used = []

    def effect(spec, path=None):
        def run(audio, rate):
            used.append(spec[0])
            return audio * 0.5
        return run
    monkeypatch.setattr(airwindows, "available", lambda: True)
    monkeypatch.setattr(airwindows, "effect", effect)
    out = str(tmp_path / "mix.wav")
    mixer.mische_spuren(tracks(tmp_path), output_pfad=out, vocal_chain=True, airwindows=True)
    assert sorted(set(used)) == ["Console7Buss", "Console7Channel", "ToTape9"]
    assert used.count("Console7Channel") == 2 and used.count("Console7Buss") == 1
    used.clear()
    mixer.mische_spuren(tracks(tmp_path), output_pfad=out, vocal_chain=True)
    assert used == []


def test_a_broken_plugin_leaves_the_mix_as_before(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(airwindows, "available", lambda: True)
    monkeypatch.setattr(airwindows, "effect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaputt")))
    out = str(tmp_path / "mix.wav")
    with caplog.at_level("WARNING", logger="mixer"):
        mixer.mische_spuren(tracks(tmp_path), output_pfad=out, vocal_chain=True, airwindows=True)
    assert os.path.exists(out) and "Airwindows nicht geladen" in caplog.text


def test_airwindows_has_a_switch():
    assert SongSettings().airwindows and main.parse_args(["--ohne-airwindows"]).ohne_airwindows


@pytest.mark.skipif(not os.path.isdir(os.path.join(REAL, airwindows.PLUGIN)), reason="setup_airwindows.py nicht gelaufen")
def test_the_real_plugin_saturates_softly(monkeypatch):
    monkeypatch.setattr(airwindows, "FOLDER", REAL)
    t = np.arange(RATE) / RATE
    x = np.stack([0.3 * np.sin(2 * np.pi * 220 * t)] * 2).astype(np.float32)
    tape = airwindows.effect(airwindows.TAPE)(x, RATE)
    spectrum = np.abs(np.fft.rfft(tape[0, RATE // 2:]))
    f = np.fft.rfftfreq(RATE // 2, 1 / RATE)
    h1, h3 = (spectrum[np.argmin(np.abs(f - hz))] for hz in (220, 660))
    assert -70 < 20 * np.log10(h3 / h1) < -30                                   # leise Obertöne, kein Zerren
    assert abs(20 * np.log10(np.sqrt(np.mean(tape[:, RATE // 2:] ** 2)) / np.sqrt(np.mean(x ** 2)))) < 2.0
    both = airwindows.effect(airwindows.CONSOLE_BUSS)(airwindows.effect(airwindows.CONSOLE_CHANNEL)(x, RATE), RATE)
    assert abs(20 * np.log10(np.sqrt(np.mean(both ** 2)) / np.sqrt(np.mean(x ** 2)))) < 3.0

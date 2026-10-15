# fehlerbericht.py – Ein ZIP mit allem, was man zur Fehlersuche braucht, ohne Songs
#
# Darin: die Protokolldateien, die Einstellungen, das letzte Ergebnis von „System prüfen“ und eine Beschreibung des
# Rechners (Windows, Python, Bibliotheken, Grafikkarte, freier Platz, was eingerichtet ist). Keine Audiodateien.
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from typing import Optional

import applog
import config
from version import VERSION

log = logging.getLogger(__name__)

PACKAGES = ("nicegui", "numpy", "scipy", "librosa", "pedalboard", "pyfluidsynth", "tinysoundfont", "pretty_midi",
            "music21", "matchering", "pydub", "pyworld", "pyttsx3", "pywebview", "soundfile", "jaconv",
            "praat-parselmouth", "alkana", "e2k", "onnxruntime")
FOLDER = "Fehlerberichte"


def gpu() -> str:
    """Name und Speicher der NVIDIA-Grafikkarte, sonst eine kurze Begründung."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return "keine NVIDIA-Grafikkarte gefunden (nvidia-smi fehlt)"
    try:
        done = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"nvidia-smi ging nicht: {e}"
    return done.stdout.strip() or done.stderr.strip() or "nvidia-smi ohne Ausgabe"


def free_space(folder: str) -> str:
    try:
        usage = shutil.disk_usage(folder if os.path.isdir(folder) else os.path.dirname(folder) or ".")
    except OSError as e:
        return f"unbekannt ({e})"
    return f"{usage.free / 1e9:.1f} GB frei von {usage.total / 1e9:.0f} GB"


def packages() -> list:
    from importlib import metadata
    found = []
    for name in PACKAGES:
        try:
            found.append(f"{name} {metadata.version(name)}")
        except metadata.PackageNotFoundError:
            found.append(f"{name} fehlt")
    return found


def system_info(settings=None) -> str:
    lines = [
        f"Vloid Songs {VERSION}",
        f"Erstellt: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"System: {platform.platform()} ({platform.machine()})",
        f"Python: {sys.version.split()[0]} ({sys.executable})",
        f"Programmordner: {config.REPO_ROOT}",
        f"Datenordner: {config.DATA_DIR}",
        f"Speicher Datenordner: {free_space(config.DATA_DIR)}",
        f"Speicher Programmordner: {free_space(config.REPO_ROOT)}",
        f"Grafikkarte: {gpu()}",
        f"ffmpeg: {shutil.which('ffmpeg') or 'fehlt'}",
    ]
    try:
        import einrichten
        lines.append("")
        lines.append("Eingerichtet:")
        lines += [f"  {line}" for line in einrichten.status_lines(settings)]
    except Exception as e:  # noqa: BLE001 – der Bericht entsteht auch, wenn hier etwas fehlt
        lines.append(f"Einrichtung nicht lesbar: {e}")
    lines.append("")
    lines.append("Bibliotheken:")
    lines += [f"  {p}" for p in packages()]
    return "\n".join(lines) + "\n"


def save(target: Optional[str] = None, settings=None) -> str:
    """Schreibt das ZIP (Standard: Fehlerberichte\\fehlerbericht_<Zeit>.zip im Datenordner) und gibt den Pfad zurück."""
    target = target or os.path.join(config.DATA_DIR, FOLDER, f"fehlerbericht_{datetime.now():%Y%m%d-%H%M%S}.zip")
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.txt", system_info(settings))
        for path in applog.files():
            z.write(path, os.path.join("protokoll", os.path.basename(path)))
        if settings is not None:
            z.writestr("Einstellungen.json", json.dumps(settings.model_dump(), indent=2, ensure_ascii=False))
        import settings as settings_module
        if os.path.exists(settings_module.SETTINGS_PATH):
            z.write(settings_module.SETTINGS_PATH, "Einstellungen_gespeichert.json")
        import systemcheck
        if os.path.exists(systemcheck.result_path()):
            z.write(systemcheck.result_path(), "systemcheck.json")
        for extra in _tool_logs():
            z.write(extra, os.path.join("werkzeuge", os.path.basename(os.path.dirname(extra)) + "_" +
                                        os.path.basename(extra)))
    log.info("Fehlerbericht gespeichert: %s", target)
    return target


def _tool_logs() -> list:
    """Was ACE-Step und die Einrichtung zuletzt ausgegeben haben."""
    import polish
    found = [os.path.join(polish.FOLDER, polish.LOG_FILE)]
    import einrichten
    found.append(einrichten.log_path())
    return [p for p in found if os.path.exists(p)]

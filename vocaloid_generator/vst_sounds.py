# vst_sounds.py – Klänge aus einem VST3-Instrument (z. B. Surge XT, kostenlos) pro Spur auswählen und speichern.
#
# Zum Auswählen öffnet sich das Fenster des Instruments in einem eigenen Prozess, denn das Fenster braucht den
# Hauptthread eines Programms, und den hat schon die App. Man sucht dort einen Klang aus und schließt das Fenster;
# der Zustand des Instruments wird als Text in den Einstellungen gespeichert und beim Rendern wieder geladen.
import base64
import logging
import os
import subprocess
import sys
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

PARTS = ("synth", "melody", "bass", "counter")     # Spuren, die einen eigenen VST-Klang bekommen können
CHOOSE_TIMEOUT = 3600.0                              # so lange darf das Fenster offen bleiben


def _surge_candidates() -> tuple:
    home = os.path.expanduser("~")
    common = os.environ.get("COMMONPROGRAMFILES", r"C:\Program Files\Common Files")
    return (
        os.path.join(common, "VST3", "Surge Synth Team", "Surge XT.vst3"),
        os.path.join(common, "VST3", "Surge XT.vst3"),
        "/Library/Audio/Plug-Ins/VST3/Surge XT.vst3",
        os.path.join(home, "Library", "Audio", "Plug-Ins", "VST3", "Surge XT.vst3"),
        os.path.join(home, ".vst3", "Surge XT.vst3"),
        "/usr/lib/vst3/Surge XT.vst3",
        "/usr/local/lib/vst3/Surge XT.vst3",
    )


def find_surge() -> str:
    """Pfad zu Surge XT (VST3), wenn es an einem der üblichen Orte installiert ist, sonst ""."""
    return next((p for p in _surge_candidates() if os.path.exists(p)), "")


def encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def apply(plugin, state: str) -> None:
    """Lädt einen gespeicherten Klang ins Instrument."""
    plugin.raw_state = base64.b64decode(state)


def choose(plugin_path: str, state: str = "", timeout: float = CHOOSE_TIMEOUT) -> Optional[str]:
    """
    Öffnet das Fenster des Instruments mit dem bisherigen Klang state und wartet, bis es geschlossen wird.
    Rückgabe: der gewählte Klang, None wenn das Fenster nicht aufging.
    """
    with tempfile.TemporaryDirectory() as folder:
        before, after = os.path.join(folder, "vorher.txt"), os.path.join(folder, "klang.txt")
        with open(before, "w", encoding="ascii") as f:
            f.write(state)
        try:
            done = subprocess.run([sys.executable, os.path.abspath(__file__), plugin_path, before, after],
                                  timeout=timeout, capture_output=True, text=True, errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            log.warning("Fenster von %s: %s", os.path.basename(plugin_path), e)
            return None
        if done.returncode != 0 or not os.path.exists(after):
            log.warning("Das Fenster von %s ging nicht auf: %s", os.path.basename(plugin_path), done.stderr[-500:])
            return None
        with open(after, encoding="ascii") as f:
            return f.read().strip() or None


def _editor(plugin_path: str, before: str, after: str) -> None:
    """Läuft im eigenen Prozess: Instrument laden, Fenster zeigen, nach dem Schließen den Klang speichern."""
    from pedalboard import load_plugin
    plugin = load_plugin(plugin_path)
    with open(before, encoding="ascii") as f:
        state = f.read().strip()
    if state:
        apply(plugin, state)
    plugin.show_editor()
    with open(after, "w", encoding="ascii") as f:
        f.write(encode(plugin.raw_state))


if __name__ == "__main__":
    _editor(*sys.argv[1:4])

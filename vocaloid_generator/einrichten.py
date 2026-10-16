# einrichten.py – Was die App zusätzlich laden kann, ob es da ist, und das Einrichten aus der App heraus
#
# Jeder Baustein ist ein Setup-Skript im Programmordner (setup_samples.py usw.), das auch allein auf der
# Kommandozeile läuft. Der Einrichten-Assistent der App startet die gewählten nacheinander und zeigt ihre Ausgabe;
# alles landet zusätzlich in Protokolle\einrichten.log. Ein abgebrochenes Skript macht beim nächsten Mal dort weiter.
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import cancel
import config

log = logging.getLogger(__name__)

DONE_FILE = "einrichtung.json"
LOG_NAME = "einrichten.log"


def _fluidsynth() -> bool:
    from renderer import engine_name
    return engine_name() == "FluidSynth"


def _soundfonts() -> bool:
    import sound_library
    return bool(sound_library.installed())


def _samples() -> bool:
    import sample_library
    return len(sample_library.installed()) == len(sample_library.files())


def _band() -> bool:
    import band_library
    return len(band_library.installed()) == len(band_library.files())


def _drums() -> bool:
    import drum_kit
    return drum_kit.complete()


def _grooves() -> bool:
    import grooves
    return grooves.load() is not None


def _airwindows() -> bool:
    import airwindows
    return airwindows.available()


def _rating() -> bool:
    import rating
    return rating.complete()        # fehlt der Umgebung ein Paket, bietet der Assistent sie wieder an


def _demucs() -> bool:
    import separation
    return separation.available()


def _accompaniment() -> bool:
    import accompaniment
    return accompaniment.available()


def _ace_step() -> bool:
    import polish
    return polish.available()


@dataclass(frozen=True)
class Component:
    key: str
    name: str
    what: str                       # was es bringt, ein Satz
    size: str                       # Platz und Download
    script: str                     # Setup-Skript im Programmordner
    installed: Callable[[], bool]
    args: tuple = ()
    recommended: bool = True        # im Assistenten vorausgewählt
    gpu: bool = False               # braucht eine NVIDIA-Grafikkarte
    windows_only: bool = False
    extra: dict = field(default_factory=dict)


COMPONENTS = (
    Component("fluidsynth", "FluidSynth", "Instrumente aus dem SoundFont klingen so, wie er gebaut ist",
              "etwa 20 MB", "setup_fluidsynth.py", _fluidsynth, windows_only=True),
    Component("soundfonts", "Bessere Klänge", "Flügel, Streicher, Bläser, E-Gitarren und Schlagzeuge aus besseren "
              "SoundFonts", "etwa 250 MB Download, 550 MB Platz", "setup_soundfonts.py", _soundfonts),
    Component("samples", "Orchester aus echten Aufnahmen", "Streicher, Bläser, Harfe, Pauken und Stabspiele aus "
              "VSCO 2", "etwa 1,2 GB", "setup_samples.py", _samples),
    Component("band", "Flügel, Bass und Gitarre aus Aufnahmen", "Salamander-Flügel, ein E-Bass und eine direkt "
              "eingespielte E-Gitarre statt der SoundFont-Klänge", "etwa 550 MB", "setup_band.py", _band),
    Component("drums", "Echtes Schlagzeug", "Bassdrum, Snare, Toms, Hi-Hat und Becken aus dem DRS Kit, im Studio "
              "aufgenommen", "etwa 130 MB Download, 50 MB Platz", "setup_drums.py", _drums),
    Component("grooves", "Echte Grooves", "Schlagzeug-Phrasen und Fills von zehn Profi-Schlagzeugern (Groove MIDI "
              "Dataset)", "etwa 3 MB", "setup_grooves.py", _grooves),
    Component("airwindows", "Airwindows-Effekte", "Bandsättigung für den Gesang und ein analoges Mischpult aus "
              "Airwindows Consolidated", "etwa 15 MB", "setup_airwindows.py", _airwindows),
    Component("rating", "Automatische Bewertung", "Bei mehreren Fassungen hört ein Modell zu und lädt die beste",
              "etwa 3 GB", "setup_bewertung.py", _rating),
    Component("demucs", "Mix wie die Vorbilder", "Demucs zerlegt deine Vorbild-Songs; Gesang, Schlagzeug, Bass und "
              "Rest werden dann einzeln so gemischt wie dort", "etwa 3 GB", "setup_demucs.py", _demucs,
              recommended=False),
    Component("begleitung", "KI-Begleitung (Versuch)", "Der Anticipatory Music Transformer schreibt Klavier, Gitarre, "
              "Streicher und Synths zu deiner Melodie; einschalten unter Pfade", "etwa 4 GB, mit NVIDIA-Grafikkarte "
              "deutlich schneller", "setup_begleitung.py", _accompaniment, recommended=False),
    Component("ace_step", "Klang-Veredler ACE-Step (Versuch)", "Eine zweite Fassung jedes Songs mit neu "
              "eingespielter Band", "etwa 20 GB, braucht eine NVIDIA-Grafikkarte", "setup_ace_step.py", _ace_step,
              recommended=False, gpu=True),
)


def register(component: Component) -> None:
    """Weitere Bausteine melden sich hier an (Tests, Erweiterungen)."""
    global COMPONENTS
    COMPONENTS = tuple(c for c in COMPONENTS if c.key != component.key) + (component,)


def components() -> list:
    return [c for c in COMPONENTS if not c.windows_only or os.name == "nt"]


def find(key: str) -> Optional[Component]:
    return next((c for c in COMPONENTS if c.key == key), None)


def is_installed(component: Component) -> bool:
    try:
        return bool(component.installed())
    except Exception as e:  # noqa: BLE001 – eine kaputte Prüfung heißt: nicht eingerichtet
        log.debug("Prüfung von %s fehlgeschlagen: %s", component.key, e)
        return False


def missing() -> list:
    return [c for c in components() if not is_installed(c)]


def status_lines(settings=None) -> list:
    """Für Fehlerbericht und Systemcheck: eine Zeile pro Baustein, dazu NEUTRINO und VOICEVOX."""
    lines = []
    if settings is not None:
        from vocal_synthesizer import neutrino_info
        lines.append(neutrino_info(settings.neutrino_dir()))
    for c in components():
        lines.append(f"{'✓' if is_installed(c) else '–'} {c.name}")
    return lines


# ── Assistent abgeschlossen? ────────────────────────────────────────────────────
def done_path() -> str:
    return os.path.join(config.DATA_DIR, DONE_FILE)


def wizard_done() -> bool:
    try:
        with open(done_path(), encoding="utf-8") as f:
            return bool(json.load(f).get("fertig"))
    except (OSError, ValueError):
        return False


def mark_wizard_done(done: bool = True) -> None:
    os.makedirs(os.path.dirname(done_path()), exist_ok=True)
    with open(done_path(), "w", encoding="utf-8") as f:
        json.dump({"fertig": done, "am": datetime.now().isoformat(timespec="seconds")}, f)


# ── Einrichten ──────────────────────────────────────────────────────────────────
def log_path() -> str:
    return os.path.join(config.LOG_DIR, LOG_NAME)


def environment() -> dict:
    """
    Die Skripte finden uv auch, wenn es nur neben der App liegt (Installer) und nicht im PATH. Bringt die Setup.exe
    Python mit, nimmt uv nur dieses (wie in „Vloid Songs starten.bat“), z. B. für uv sync bei ACE-Step, und lädt ein
    Paket nach dem anderen (mehrere große gleichzeitig bleiben auf manchen PCs stehen, z. B. PyTorch).
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    bundled = os.path.join(config.REPO_ROOT, "uv")
    if os.path.isdir(bundled):
        env["PATH"] = bundled + os.pathsep + env.get("PATH", "")
    if os.path.isfile(config.BUNDLED_PYTHON):
        env.update(UV_PYTHON=config.BUNDLED_PYTHON, UV_PYTHON_DOWNLOADS="never",
                   UV_PYTHON_INSTALL_DIR=os.path.join(bundled, "python"), UV_CONCURRENT_DOWNLOADS="1")
    return env


def install(keys: list, say: Callable[[str], None] = print,
            progress: Optional[Callable[[float, str], None]] = None) -> dict:
    """
    Richtet die Bausteine keys nacheinander ein. say bekommt jede Zeile der Ausgabe. Rückgabe {key: geklappt}.
    Ein Abbruch (cancel.request) beendet das laufende Skript; was fertig ist, bleibt.
    """
    report = progress or (lambda fraction, message: None)
    chosen = [c for c in components() if c.key in keys]
    results = {}
    os.makedirs(os.path.dirname(log_path()), exist_ok=True)
    with open(log_path(), "a", encoding="utf-8") as logfile:
        def line(text: str) -> None:
            logfile.write(text + "\n")
            logfile.flush()
            say(text)

        for i, c in enumerate(chosen):
            report(i / max(len(chosen), 1), f"{c.name} ({i + 1} von {len(chosen)})")
            line(f"── {c.name} ── {datetime.now():%H:%M:%S}")
            script = os.path.join(config.REPO_ROOT, c.script)
            if not os.path.isfile(script):
                line(f"{c.script} fehlt im Programmordner")
                results[c.key] = False
                continue
            try:
                code = cancel.stream([sys.executable, "-u", script, *c.args], line, cwd=config.REPO_ROOT,
                                     env=environment(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as e:
                line(f"Konnte {c.script} nicht starten: {e}")
                code = 1
            results[c.key] = code == 0
            line(f"{c.name}: {'fertig' if code == 0 else 'nicht geklappt, noch einmal starten macht dort weiter'}")
    report(1.0, "Fertig")
    _refresh_caches()
    return results


def _refresh_caches() -> None:
    """Nach dem Einrichten sieht die App neue Bausteine sofort, ohne Neustart."""
    try:
        import renderer
        renderer._fluidsynth.cache_clear()
    except Exception:  # noqa: BLE001
        pass


def free_gb(folder: str = None) -> float:
    folder = folder or config.REPO_ROOT
    while folder and not os.path.exists(folder):
        folder = os.path.dirname(folder)
    try:
        return shutil.disk_usage(folder or ".").free / 1e9
    except OSError:
        return 0.0

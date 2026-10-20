# updates.py – Neue Versionen finden und holen, und „Was ist neu“ nach einem Update
#
# Neue Versionen liegen als Release auf GitHub (mit Setup.exe). Ist die App ein git-Klon, holt „Update holen“ die
# neue Version mit git pull; sonst lädt es die Setup.exe und startet sie, die App schließt sich dafür. Die
# Abfrage geht höchstens einmal am Tag raus und lässt sich in den Einstellungen abschalten.
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

import config
from version import REPO, VERSION

log = logging.getLogger(__name__)

API = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_FILE = "update.json"
SEEN_FILE = "zuletzt_gesehen.txt"
CHECK_EVERY = 24 * 3600
CHANGELOG = os.path.join(config.REPO_ROOT, "CHANGELOG.md")


@dataclass
class Release:
    version: str
    notes: str
    setup_url: str          # Download der Setup.exe ("" wenn keine dabei ist)
    page: str


def parse_version(text: str) -> tuple:
    """"v1.2.3" → (1, 2, 3); Unlesbares zählt als (0,)."""
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in numbers[:3]) or (0,)


def newer(candidate: str, current: str = VERSION) -> bool:
    return parse_version(candidate) > parse_version(current)


def _cache_path() -> str:
    return os.path.join(config.DATA_DIR, CACHE_FILE)


def latest(force: bool = False, timeout: float = 5.0) -> Optional[Release]:
    """Das neueste Release auf GitHub; zwischengespeichert für einen Tag. None ohne Internet oder ohne Release."""
    cached = _read_cache()
    if cached and not force and time.time() - cached.get("zeit", 0) < CHECK_EVERY:
        return _release(cached.get("release"))
    try:
        request = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": f"VloidSongs/{VERSION}"})
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            data = json.load(answer)
    except (OSError, ValueError) as e:
        log.info("Update-Suche ging nicht: %s", e)
        return _release(cached.get("release")) if cached else None
    setup = next((a.get("browser_download_url", "") for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), "")
    found = {"version": data.get("tag_name", ""), "notes": data.get("body") or "", "setup_url": setup,
             "page": data.get("html_url", f"https://github.com/{REPO}/releases")}
    _write_cache({"zeit": time.time(), "release": found})
    return _release(found)


def _release(data) -> Optional[Release]:
    if not isinstance(data, dict) or not data.get("version"):
        return None
    return Release(data["version"], data.get("notes", ""), data.get("setup_url", ""), data.get("page", ""))


def _read_cache() -> dict:
    try:
        with open(_cache_path(), encoding="utf-8") as f:
            found = json.load(f)
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(data: dict) -> None:
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(_cache_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def available(force: bool = False) -> Optional[Release]:
    """Das neuere Release, wenn es eins gibt."""
    found = latest(force)
    return found if found and newer(found.version) else None


# ── holen ──────────────────────────────────────────────────────────────────────
def is_git_checkout() -> bool:
    return os.path.isdir(os.path.join(config.REPO_ROOT, ".git")) and shutil.which("git") is not None


def pull(say: Callable[[str], None] = print) -> bool:
    """git pull im Programmordner; die neuen Bibliotheken holt uv beim nächsten Start."""
    import cancel
    code = cancel.stream(["git", "-C", config.REPO_ROOT, "pull", "--ff-only"], say,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return code == 0


def download_setup(release: Release, say: Callable[[str], None] = print) -> Optional[str]:
    """Lädt die Setup.exe des Releases in einen temporären Ordner; Pfad oder None."""
    if not release.setup_url:
        say("Das Release hat keine Setup.exe.")
        return None
    target = os.path.join(tempfile.mkdtemp(prefix="vloid-update-"), f"VloidSongs-Setup-{release.version}.exe")
    try:
        with urllib.request.urlopen(release.setup_url, timeout=60) as answer, open(target, "wb") as f:
            length = answer.headers.get("Content-Length")
            shutil.copyfileobj(answer, f, 1 << 20)
        # reißt die Verbindung mittendrin ab, endet der Download ohne Fehler, nur zu kurz: so eine Setup.exe nie starten
        if length is not None and os.path.getsize(target) != int(length):
            raise OSError("Verbindung mittendrin abgebrochen")
    except OSError as e:
        say(f"Download fehlgeschlagen: {e}")
        shutil.rmtree(os.path.dirname(target), ignore_errors=True)
        return None
    say(f"Geladen: {target}")
    return target


def run_setup(path: str) -> None:
    """Startet die Setup.exe ohne Fragen; sie schließt die App und startet sie danach wieder."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/NEUSTART=1"],
                     creationflags=flags, close_fds=True)


# ── Was ist neu ────────────────────────────────────────────────────────────────
def changes(version: str = VERSION, path: str = CHANGELOG) -> str:
    """Der Abschnitt dieser Version aus CHANGELOG.md ("" wenn es keinen gibt)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    sections = re.split(r"(?m)^## ", text)
    for section in sections[1:]:
        head, _, body = section.partition("\n")
        if parse_version(head) == parse_version(version):
            return body.strip()
    return ""


def unseen_changes() -> str:
    """Die Neuerungen dieser Version, wenn sie seit dem Update noch nicht gezeigt wurden (einmal pro Version)."""
    seen_path = os.path.join(config.DATA_DIR, SEEN_FILE)
    try:
        with open(seen_path, encoding="utf-8") as f:
            seen = f.read().strip()
    except OSError:
        seen = ""
    if seen == VERSION:
        return ""
    import settings
    known_user = bool(seen) or os.path.exists(settings.SETTINGS_PATH)    # wer schon Einstellungen hat, hatte eine
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(seen_path, "w", encoding="utf-8") as f:
            f.write(VERSION)
    except OSError:
        return ""
    return changes() if known_user else ""      # beim allerersten Start gibt es kein „neu“

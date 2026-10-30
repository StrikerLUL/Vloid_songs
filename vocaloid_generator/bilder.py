# bilder.py – KI-Hintergründe fürs Musikvideo, ein Bild pro Sektion (1.5.0 V13)
#
# Ein Bildmodell (LCM Dreamshaper v7, MIT-Lizenz) malt für jede Sektionsart des Songs eine Landschaft ohne Menschen
# und ohne Schrift: die Szene des Stils (Bühne, Fenster bei Nacht, Schrein …), die Stimmung der Sektion (Strophe
# ruhig, Refrain hell und weit) und was im Text vorkommt (雨 → Regen, 星 → Sternenhimmel). Es läuft wie die Bewertung
# in einer eigenen Umgebung (tools/bilder, einmal uv run setup_bilder.py), mit NVIDIA-Grafikkarte in Sekunden, sonst
# auf dem Prozessor in etwa einer halben Minute pro Bild. Die Bilder liegen im Songordner unter bilder\ und werden
# beim nächsten Video desselben Songs (gleicher Seed, gleicher Prompt) wiederverwendet; ein neuer Song im selben
# Ausgabeordner bekommt eigene Bilder. Fehlt die Umgebung, malt video_szenen.py die Szene wie ohne.
import json
import logging
import os
import re
import subprocess
import sys
from typing import Optional

import cancel
import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "bilder")
WORKER = os.path.join(config.BASE_DIR, "bilder_worker.py")
MODEL = "SimianLuo/LCM_Dreamshaper_v7"
MARKER = "BILDER "
SONG_FOLDER = "bilder"
PROMPTS_FILE = "prompts.json"
LOG_FILE = "letzter_lauf.log"
SIZE = (640, 360)               # 16:9, das Video vergrößert; im Hintergrund unter dem Text reicht das
STEPS = 4
TIMEOUT = 3600                  # beim ersten Mal lädt das Modell etwa 4 GB

# Stil → was zu sehen ist (Englisch, so versteht es das Modell)
STYLE_PROMPTS = {
    "J-Pop Energy": "anime city skyline at golden hour, vivid colors, lens flare, summer clouds",
    "Dark Vocaloid": "dark neon alley at night, cyberpunk, red and teal lights, wet ground",
    "Kawaii Chiptune": "pastel pixel art dreamland, candy clouds, cute, 8-bit",
    "Rock": "empty concert stage with spotlights and smoke, amplifiers",
    "Ballade": "quiet window at night, city lights bokeh, melancholic, soft light",
    "City Pop": "1980s japanese city pop illustration, seaside highway, palm trees, retro sunset",
    "Future Bass": "colorful abstract sky, glowing clouds, floating crystals, dreamy",
    "Drum and Bass": "futuristic tunnel with neon lights, speed, dark",
    "Lo-Fi": "cozy anime bedroom at night, desk lamp, window with city view, lofi",
    "Idol-Pop": "empty idol concert stage with pastel lights, ribbons and confetti",
    "Wafuu-Rock": "traditional japanese shrine with torii gate, red moon, ukiyo-e colors",
    "Electro-Swing": "1920s art deco ballroom, golden ornaments, jazz age poster",
    "Hyperpop": "glossy chrome y2k shapes, bubbles, pink and blue, surreal",
}
DEFAULT_PROMPT = "dreamy anime landscape, soft gradient sky"
# Sektion → Stimmung
MOODS = {
    "Intro": "establishing shot, calm, early light",
    "Verse": "calm, soft light, muted colors",
    "PreChorus": "rising tension, dramatic sky",
    "Chorus": "wide shot, vivid and bright, glowing",
    "Bridge": "different mood, twilight, dreamy",
    "Interlude": "quiet, empty, gentle light",
    "Outro": "fading light, peaceful, distant",
    "Drop": "explosive light, intense colors",
    "Solo": "dramatic light beams",
    "Rap": "close-up details, strong contrast",
    "Spoken": "close-up details, still",
    "Breakdown": "sparse, dim, mysterious",
}
# Motiv aus dem Text (textmotive.py) → was dazukommt
MOTIFS = {
    "rain": "rain", "snow": "snowfall", "petals": "cherry blossom petals falling", "stars": "starry sky",
    "moon": "full moon", "night": "night", "sun": "warm sunlight", "sea": "ocean waves", "fire": "embers and flames",
    "tears": "raindrops on glass", "hearts": "soft pink glow", "chat": "glowing phone screens", "game": "arcade lights",
    "city": "city streets", "wind": "wind with flying leaves", "music": "floating music notes",
}
SUFFIX = "scenery, background art, anime style, highly detailed, no humans, no text"


def model_folder() -> str:
    return os.path.join(FOLDER, "huggingface")


def environment() -> dict:
    return {**os.environ, **config.hf_environment(model_folder()), "PYTHONIOENCODING": "utf-8"}


def python() -> str:
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def status() -> str:
    if not available():
        return "KI-Bilder fürs Video fehlen: einmal uv run setup_bilder.py ausführen"
    return "KI-Bilder fürs Video (LCM Dreamshaper) sind eingerichtet"


def problem() -> str:
    return f"Das Bildmodell lief nicht (Ausgabe in {os.path.join(FOLDER, LOG_FILE)})"


def prompts(style: str, kinds: list, section_motifs: dict, song_motifs: list) -> dict:
    """{Sektionsart: Prompt}. section_motifs {Sektionsart: Motive in ihrem Text}; song_motifs: die häufigsten im
    ganzen Song (höchstens zwei kommen in jedes Bild, damit der Song zusammenpasst)."""
    scene = STYLE_PROMPTS.get(style, DEFAULT_PROMPT)
    out = {}
    for kind in kinds:
        main = list(song_motifs[:2])
        found = main + [m for m in sorted(section_motifs.get(kind, ())) if m not in main]
        extra = ", ".join(MOTIFS[m] for m in found[:4] if m in MOTIFS)
        out[kind] = ", ".join(p for p in (scene, MOODS.get(kind, ""), extra, SUFFIX) if p)
    return out


def song_prompts(result) -> dict:
    """Die Prompts eines fertigen Songs aus Songkarte und Liedtext."""
    import karaoke
    import songkarte
    import textmotive
    found = songkarte.load(os.path.join(result.output_dir, songkarte.FILE))
    if found is None or not found.sections:
        return {}
    lines = karaoke.load(os.path.join(result.output_dir, karaoke.FILE))
    kinds = list(dict.fromkeys(s.kind for s in found.sections))
    per_kind = {}
    for line in lines:
        sec = found.section_at(line["start"])
        if sec is not None:
            per_kind.setdefault(sec.kind, set()).update(textmotive.find(line.get("text") or ""))
    total = textmotive.song_motifs(lines)
    return prompts(result.settings.style if result.settings else "", kinds, per_kind,
                   [m for m, _ in total.most_common()])


def for_song(result, progress=None) -> dict:
    """{Sektionsart: PNG} für das Video; {} ohne Umgebung oder wenn das Modell nicht lief."""
    if not available():
        return {}
    wanted = song_prompts(result)
    if not wanted:
        return {}
    folder = os.path.join(result.output_dir, SONG_FOLDER)
    return paint(wanted, folder, result.seed, progress)


def _name(kind: str) -> str:
    return re.sub(r"[^\w-]", "_", kind) + ".png"


def paint(wanted: dict, folder: str, seed: int, progress=None) -> dict:
    """Malt die Bilder, die in folder noch fehlen oder deren Prompt oder Seed sich geändert hat. Alle Songs teilen sich
    den Ausgabeordner: ohne den Seed bekäme ein neuer Song im selben Stil die Bilder des vorigen."""
    os.makedirs(folder, exist_ok=True)
    known_path = os.path.join(folder, PROMPTS_FILE)
    try:
        with open(known_path, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    painted = {kind: f"{int(seed)}|{prompt}" for kind, prompt in wanted.items()}
    jobs = []
    for i, (kind, prompt) in enumerate(wanted.items()):
        path = os.path.join(folder, _name(kind))
        if known.get(kind) != painted[kind] or not os.path.exists(path):
            jobs.append({"path": path, "prompt": prompt, "seed": int(seed) * 31 + i})
    if jobs:
        if progress:
            progress(0.03, f"Video: male {len(jobs)} Bilder...")
        if not _run(jobs, folder):
            return {}
        with open(known_path, "w", encoding="utf-8") as f:
            json.dump({**known, **painted}, f, ensure_ascii=False, indent=1)
    return {kind: os.path.join(folder, _name(kind)) for kind in wanted
            if os.path.exists(os.path.join(folder, _name(kind)))}


def _run(jobs: list, folder: str) -> bool:
    request = os.path.join(folder, "auftrag.json")
    with open(request, "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "width": SIZE[0], "height": SIZE[1], "steps": STEPS, "jobs": jobs}, f)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    config.hf_without_links(model_folder())
    try:
        done = cancel.run([python(), WORKER, request], capture_output=True, timeout=TIMEOUT, env=environment(),
                          encoding="utf-8", errors="replace", creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("KI-Bilder fehlgeschlagen: %s", e)
        return False
    finally:
        try:
            os.remove(request)
        except OSError:
            pass
    try:
        os.makedirs(FOLDER, exist_ok=True)
        with open(os.path.join(FOLDER, LOG_FILE), "w", encoding="utf-8") as f:
            f.write((done.stdout or "") + "\n" + (done.stderr or ""))
    except OSError:
        pass
    line = next((ln for ln in reversed((done.stdout or "").splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        log.warning("KI-Bilder fehlgeschlagen: %s", (done.stderr or done.stdout or "").strip()[-800:])
        return False
    log.info("KI-Bilder: %s", line[len(MARKER):])
    return True


def probe(folder: str) -> Optional[str]:
    """Ein Probebild (Systemcheck, Einrichten); None, wenn das Modell nicht lief."""
    found = paint({"Probe": prompts("Ballade", ["Chorus"], {}, ["stars"])["Chorus"]}, folder, 7)
    return found.get("Probe")

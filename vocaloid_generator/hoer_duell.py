# hoer_duell.py – Hör-Duell (1.6.0): dieselbe Stelle zweimal, einmal mit und einmal ohne eine Funktion, blind
#
# Fast alle Schalter der App stehen auf „an“, weil sie beim Bauen besser klangen, nicht weil du sie gehört hast. Das
# Duell fragt dein Ohr: Der Refrain deines Songs (gleicher Seed, gleiche Stimme, gleicher Text) entsteht zweimal,
# einmal mit und einmal ohne eine Funktion. Welche Fassung A und welche B ist, wird ausgelost, beide klingen gleich
# laut. Du sagst „A besser“, „B besser“ oder „gleich“, und am Ende übernimmt die App die Gewinner als deine
# Einstellungen. Bei „gleich“ geht die Funktion aus (das spart Zeit beim Erzeugen), und die Oberfläche kann den
# Schalter ausblenden (settings.tidy_switches). Klingen beide Fassungen gleich, weil die Funktion in diesem Stil nichts
# tut oder ihr Baustein fehlt, überspringt das Duell sie, ohne etwas zu ändern.
#
# Beide Fassungen entstehen im selben Ordner: Gesang und Spuren, die sich nicht ändern, nimmt der zweite Lauf aus
# dem Zwischenspeicher (singing.TAKE_CACHE, <spur>.wav.key), so singt NEUTRINO bei Klang- und Mix-Duellen nur einmal.
# Die Ergebnisse liegen in hoer_duell.json im Datenordner und kommen in den Fehlerbericht.
import json
import logging
import os
import random
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import numpy as np
import soundfile as sf

import config

log = logging.getLogger(__name__)

FILE = "hoer_duell.json"
FOLDER = "Hoer-Duell"           # im Ausgabeordner
GROUPS = {"stimme": "Stimme", "melodie": "Melodie", "klang": "Klang", "mix": "Mix"}
CHOICES = {"a": "A besser", "b": "B besser", "gleich": "gleich"}
SAME_DB = -60.0                 # Unterschied der beiden Fassungen unter diesem Pegel (zum Signal) = kein Unterschied
EDGE_SECONDS = 0.01             # weiches Ein- und Ausblenden der Ausschnitte


@dataclass(frozen=True)
class Candidate:
    field: str                  # Einstellung in SongSettings
    label: str                  # wie der Schalter in der App heißt
    group: str                  # Schlüssel aus GROUPS
    off: object = False         # Wert „ohne“; „mit“ ist der aktuelle Wert, oder der Standard, wenn er gerade aus ist
    sections: tuple = ("Chorus",)
    hint: str = ""              # worauf man achten kann


CANDIDATES = (
    # Stimme
    Candidate("soft_vocal_chain", "Weichere Gesangskette", "stimme", hint="runder, weniger spitz"),
    Candidate("gentle_reshape", "Sanfte Nachbearbeitung", "stimme", hint="natürlicher, weniger künstlich"),
    Candidate("psola_reshape", "Vibrato mit PSOLA statt WORLD", "stimme", hint="Klangfarbe der Stimme"),
    Candidate("vocal_tone", "Klangfarbe je Stimme und Stil", "stimme", hint="hell oder warm"),
    Candidate("airwindows", "Airwindows-Bandmaschine", "stimme", hint="Wärme, Glanz"),
    Candidate("resonance_tamer", "Härte zähmen", "stimme", hint="schrille Stellen"),
    Candidate("intonation", "Tonhöhe glätten", "stimme", off=0.0, hint="gerade oder schiefe Töne"),
    Candidate("ornaments", "Verzierungen", "stimme", off=0.0, hint="von unten in den Ton, Fall am Ende"),
    Candidate("note_swells", "Lange Töne leben", "stimme", hint="gehaltene Töne"),
    Candidate("living_double", "Lebendige Doppelung", "stimme", hint="Breite des Refrains"),
    Candidate("harmonies", "Zweite Stimme im Refrain", "stimme"),
    Candidate("sung_pads", "Gesungene Flächen", "stimme", hint="„uu“ und „aa“ im Hintergrund"),
    Candidate("final_choir", "Chor im letzten Refrain", "stimme"),
    Candidate("adlibs", "Rufe und Echo-Antworten", "stimme"),
    Candidate("breaths", "Hörbare Atmer", "stimme"),
    Candidate("formant_fx", "Formanten je Stil", "stimme", hint="kindlicher oder dunkler"),
    # Melodie
    Candidate("melody_character", "Melodie je Stil", "melodie", hint="was eingängiger ist"),
    Candidate("style_chords", "Akkorde je Stil", "melodie"),
    Candidate("chord_spice", "Akkord-Würze", "melodie", off=0.0, hint="bunter oder schlichter"),
    Candidate("melody_pickups", "Auftakte und vorgezogene Töne", "melodie"),
    Candidate("melody_tensions", "Spannungstöne", "melodie"),
    Candidate("melody_triplets", "Triolen", "melodie"),
    Candidate("key_words", "Kernwort hoch oder lang", "melodie"),
    Candidate("best_melody", "Beste Melodie suchen", "melodie", hint="dauert länger"),
    # Klang
    Candidate("style_sound", "Klangbild je Stil", "klang", hint="Raum, Breite"),
    Candidate("song_character", "Eigene Klänge je Song", "klang"),
    Candidate("surge_sounds", "Surge-XT-Klänge", "klang"),
    Candidate("amp_models", "Echte Verstärker", "klang", hint="verzerrte Gitarren, dauert länger"),
    Candidate("band_groove", "Band im Groove", "klang"),
    Candidate("lively_bass", "Bass mit Ghost-Notes", "klang"),
    Candidate("bass_runs", "Bass-Läufe", "klang"),
    Candidate("band_runs", "Läufe von Klavier und Streichern", "klang"),
    Candidate("kime", "Gemeinsame Akzente und Stopps", "klang"),
    Candidate("anison_grooves", "Anison-Grooves", "klang", hint="schnelle Stile"),
    # Mix
    Candidate("mix_punch", "Druck", "mix"),
    Candidate("mix_movement", "Bewegung im Mix", "mix", sections=("PreChorus", "Chorus"), hint="Anlauf zum Refrain"),
    Candidate("vocal_unmask", "Band macht Platz für den Gesang", "mix"),
    Candidate("vocal_ride", "Gesang gleich weit über der Band", "mix"),
    Candidate("convolution_reverb", "Gesangsplatte (Hall)", "mix"),
    Candidate("ducked_delay", "Leiseres Echo beim Singen", "mix"),
)
BY_FIELD = {c.field: c for c in CANDIDATES}


@dataclass
class Duel:
    candidate: Candidate
    a: str                      # WAV-Pfade, gleich laut
    b: str
    a_is_on: bool               # True: A ist die Fassung mit der Funktion
    on: object
    identical: bool = False


# ── was gegeneinander antritt ─────────────────────────────────────────────────────────
def _default(field: str):
    from settings import SongSettings
    return SongSettings.model_fields[field].default


def on_value(settings, candidate: Candidate):
    """Der Wert „mit“: der aktuelle, oder der Standard, wenn der Schalter gerade aus (auf dem Wert „ohne“) steht."""
    current = getattr(settings, candidate.field)
    return _default(candidate.field) if current == candidate.off else current


def plan(settings, groups=None, limit: int = 0) -> list:
    """Die Duelle für diese Bereiche (None = alle), in der Reihenfolge von CANDIDATES. limit > 0: höchstens so viele;
    dann kommen zuerst die, über die du noch nicht entschieden hast."""
    wanted = [c for c in CANDIDATES if (not groups or c.group in groups) and on_value(settings, c) != c.off]
    if limit > 0:
        done = {e["field"] for e in load()}
        wanted = sorted(wanted, key=lambda c: c.field in done)[:limit]
        wanted = [c for c in CANDIDATES if c in wanted]
    return wanted


def clip_settings(settings, candidate: Candidate, folder: str):
    """Nur der Ausschnitt: die Sektionen des Duells, ohne Verlauf, Veredler, Hör-Check, Fassungen und Tag."""
    s = settings.with_updates(active_sections=list(candidate.sections), output_ordner=folder, draft=False,
                              polish=False, hearing_check=False, vocal_versions=False, id3_tags=False,
                              producer_tag=False, ai_accompaniment=False, reuse_steps=True, vocal_takes=1,
                              ref_stems=False)
    if not s.channels["vocals"].enabled and not s.channels["melody"].enabled:
        s.channels["melody"].enabled = True
    return s


# ── ein Duell vorbereiten ───────────────────────────────────────────────────────────
def _read(path: str) -> tuple:
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    return audio, rate


def _loudness(audio: np.ndarray, rate: int) -> float:
    import pyloudnorm
    try:
        return float(pyloudnorm.Meter(rate).integrated_loudness(audio.astype(np.float64)))
    except ValueError:          # kürzer als ein Messblock
        return float("-inf")


def same(a: np.ndarray, b: np.ndarray) -> bool:
    """Kein hörbarer Unterschied: die Differenz liegt mehr als 60 dB unter dem Signal (oder beide sind still)."""
    n = min(len(a), len(b))
    if n == 0 or abs(len(a) - len(b)) > 0.05 * max(len(a), len(b)):
        return n == 0 and len(a) == len(b)
    signal = float(np.sqrt(np.mean(np.square(a[:n], dtype=np.float64))))
    diff = float(np.sqrt(np.mean(np.square(a[:n] - b[:n], dtype=np.float64))))
    if signal == 0.0:
        return diff == 0.0
    return diff == 0.0 or 20 * np.log10(diff / signal) < SAME_DB


def _match(audio: np.ndarray, rate: int, target: float) -> np.ndarray:
    """Auf dieselbe Lautheit bringen (lauter klingt sonst besser), ohne zu übersteuern, mit weichen Rändern."""
    level = _loudness(audio, rate)
    out = audio.copy()
    if np.isfinite(level) and np.isfinite(target):
        out *= 10 ** ((target - level) / 20)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0.98:
        out *= 0.98 / peak
    edge = min(int(EDGE_SECONDS * rate), len(out) // 2)
    if edge:
        ramp = np.linspace(0.0, 1.0, edge, dtype=np.float32)[:, None]
        out[:edge] *= ramp
        out[-edge:] *= ramp[::-1]
    return out


def render(settings, folder: str, seed: int, progress: Optional[Callable] = None) -> str:
    """Den Ausschnitt mischen; Rückgabe: final_mix.wav im Ordner. Ohne Verlauf (keep_history=False)."""
    import pipeline
    result = pipeline.generate_song(settings, progress=progress, seed=seed, keep_history=False)
    return result.mix_wav


def prepare(settings, candidate: Candidate, folder: str, seed: int, number: int = 1,
            progress: Optional[Callable] = None, rng: Optional[random.Random] = None) -> Duel:
    """Beide Fassungen erzeugen, gleich laut machen und auslosen, welche A ist."""
    report = progress or (lambda fraction, message: None)
    run_folder = os.path.join(folder, "lauf")
    os.makedirs(run_folder, exist_ok=True)       # sonst gilt der Ordner als unerreichbar (settings.output_dir)
    base = clip_settings(settings, candidate, run_folder)
    on = on_value(settings, candidate)
    paths = {}
    for i, (side, value) in enumerate((("mit", on), ("ohne", candidate.off))):
        step = (lambda f, m, i=i: report((i + f) / 2, f"Duell {number}: {candidate.label} {'mit' if i == 0 else 'ohne'}"
                                         f" ({m})"))
        mix = render(base.with_updates(**{candidate.field: value}), base.output_dir(), seed, step)
        paths[side] = os.path.join(folder, f"{number:02d}_{side}.wav")
        shutil.copyfile(mix, paths[side])
    with_audio, rate = _read(paths["mit"])
    without, _ = _read(paths["ohne"])
    identical = bool(same(with_audio, without))
    target = (_loudness(with_audio, rate) + _loudness(without, rate)) / 2
    a_is_on = (rng or random).random() < 0.5
    out = {}
    for name, (audio, side) in {"a": (with_audio, "mit") if a_is_on else (without, "ohne"),
                                "b": (without, "ohne") if a_is_on else (with_audio, "mit")}.items():
        out[name] = os.path.join(folder, f"{number:02d}_{name.upper()}.wav")
        sf.write(out[name], _match(audio, rate, target), rate)
    for side in paths.values():
        os.remove(side)
    report(1.0, f"Duell {number} bereit")
    return Duel(candidate, out["a"], out["b"], a_is_on, on, identical)


# ── Ergebnisse ────────────────────────────────────────────────────────────────────────
def path() -> str:
    return os.path.join(config.DATA_DIR, FILE)


def load() -> list:
    """Alle Entscheidungen, älteste zuerst: [{field, label, group, choice ("mit"/"ohne"/"gleich"), auto, …}]."""
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    entries = data.get("entries", []) if isinstance(data, dict) else []
    return [e for e in entries if isinstance(e, dict) and e.get("field") in BY_FIELD
            and e.get("choice") in ("mit", "ohne", "gleich")]


def _save(entries: list) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "entries": entries}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path())


def verdict(duel: Duel, choice: str) -> str:
    """„A besser“/„B besser“/„gleich“ → mit, ohne oder gleich."""
    if choice == "gleich" or duel.identical:
        return "gleich"
    if choice not in ("a", "b"):
        raise ValueError(f"Unbekannte Wahl: {choice}")
    return "mit" if (choice == "a") == duel.a_is_on else "ohne"


def record(duel: Duel, choice: str, settings) -> dict:
    """Eine Entscheidung merken (hoer_duell.json) und zurückgeben."""
    c = duel.candidate
    entry = {"field": c.field, "label": c.label, "group": c.group, "choice": verdict(duel, choice),
             "auto": duel.identical, "on": duel.on, "style": settings.style, "singer": settings.singer,
             "date": datetime.now().isoformat(timespec="seconds")}
    _save(load() + [entry])
    log.info("Hör-Duell %s: %s%s", c.label, entry["choice"], " (kein Unterschied)" if duel.identical else "")
    return entry


def latest(entries: Optional[list] = None) -> dict:
    """Je Einstellung die letzte Entscheidung, die du gehört hast. Duelle ohne jeden Unterschied zählen nicht: die
    Funktion tut im Stil des Duells nichts (Verstärker in der Ballade) oder ihr Baustein fehlt noch (Surge XT)."""
    found = {}
    for e in entries if entries is not None else load():
        if not e.get("auto"):
            found[e["field"]] = e
    return found


def changes(settings, entries: Optional[list] = None) -> dict:
    """Was die Duelle an den Einstellungen ändern: {Feld: neuer Wert}. „mit“ = der Wert, der antrat; „ohne“ und
    „gleich“ = der Wert „ohne“ (gleich klingt, wird nicht gerechnet)."""
    out = {}
    for field, e in latest(entries).items():
        c = BY_FIELD[field]
        value = e.get("on", on_value(settings, c)) if e["choice"] == "mit" else c.off
        if getattr(settings, field) != value:
            out[field] = value
    return out


def apply(settings, entries: Optional[list] = None):
    """Die Einstellungen mit den Gewinnern der Duelle."""
    found = changes(settings, entries)
    return settings.with_updates(**found) if found else settings


def inaudible(entries: Optional[list] = None) -> set:
    """Felder, deren letztes Duell „gleich“ ergab: die Oberfläche blendet ihre Schalter aus (tidy_switches)."""
    return {field for field, e in latest(entries).items() if e["choice"] == "gleich"}


def summary(entries: Optional[list] = None) -> str:
    found = latest(entries)
    if not found:
        return "Noch kein Hör-Duell."
    count = {k: sum(1 for e in found.values() if e["choice"] == k) for k in ("mit", "ohne", "gleich")}
    return (f"{len(found)} Funktionen verglichen: {count['mit']} klingen mit besser, {count['ohne']} ohne, "
            f"{count['gleich']} machen keinen hörbaren Unterschied")


def forget() -> None:
    """Alle Duelle vergessen (die Schalter bleiben, wie sie sind)."""
    try:
        os.remove(path())
    except OSError:
        pass

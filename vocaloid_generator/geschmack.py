# geschmack.py – Geschmack lernen (1.5.0, C3)
#
# Im Verlauf gibt es neben dem Stern einen Daumen für Klang, Melodie, Stimme und Groove. Die App merkt sich, was in
# den Songs vorkam, die du so bewertet hast (history.py speichert dazu den Charakter jedes Songs), und würfelt
# danach öfter, was dir gefallen hat, und seltener, was nicht:
# - Klang: die Klänge und Synth-Stimmen des Charakters (song_character.py)
# - Groove: Grooves und Spielweisen je Sektion, wie das Intro beginnt und wie der Song endet
# - Melodie: die Akkordfolgen je Sektion (song_plan.build_plan), auf denen die Melodie entsteht
# - Stimme: die NEUTRINO-Stimme; ist für einen Stil keine gemerkt, singt die mit den meisten Daumen hoch
#   (casting.favorite)
# Nichts wird ausgeschlossen: ein Daumen runter macht etwas nur seltener.
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

ASPECTS = {"klang": "Klang", "melodie": "Melodie", "stimme": "Stimme", "groove": "Groove"}
ARCHIVE = "geschmack.json"      # im Verlaufsordner: die Daumen der Songs, die schon aus dem Verlauf gefallen sind
STEP = 0.75                     # so viel mehr Gewicht pro Daumen hoch (1 = so oft wie ohne Geschmack)
LOWEST, HIGHEST = 0.25, 4.0


@dataclass
class Taste:
    scores: dict = field(default_factory=dict)       # Schlüssel (Tupel) → Summe der Daumen
    singers: dict = field(default_factory=dict)      # Stil → {Stimme: Summe der Daumen}

    def __bool__(self) -> bool:
        return bool(self.scores or self.singers)

    def weight(self, key: tuple) -> float:
        return min(HIGHEST, max(LOWEST, 1.0 + STEP * self.scores.get(key, 0)))

    def weights(self, keys: list) -> Optional[list]:
        """Gewichte für eine Auswahl; None, wenn der Geschmack zu keiner etwas weiß (dann würfelt es wie bisher)."""
        if not any(key in self.scores for key in keys):
            return None
        return [self.weight(key) for key in keys]

    def singer(self, style: str) -> str:
        """Die Stimme mit den meisten Daumen hoch für den Stil (sonst über alle Stile); leer, wenn keine vorn liegt."""
        for pool in (self.singers.get(style, {}), _summed(self.singers)):
            best = max(pool.items(), key=lambda kv: (kv[1], kv[0]), default=("", 0))
            if best[1] > 0:
                return best[0]
        return ""

    def describe(self) -> str:
        liked = sum(1 for v in self.scores.values() if v > 0)
        disliked = sum(1 for v in self.scores.values() if v < 0)
        return f"{liked} Vorlieben, {disliked} Abneigungen"


def _summed(singers: dict) -> dict:
    out = {}
    for pool in singers.values():
        for name, score in pool.items():
            out[name] = out.get(name, 0) + score
    return out


# ── Was ein Song gewürfelt hat ──────────────────────────────────────────────────────
def song_keys(character: dict) -> dict:
    """{Aspekt: [Schlüssel]} aus dem Charakter, den history.py mit dem Song gespeichert hat."""
    keys = {"klang": [], "groove": [], "melodie": []}
    for inst, program in (character.get("programs") or {}).items():
        keys["klang"].append(("program", inst, program))
    for inst, layers in (character.get("voices") or {}).items():
        for layer, voice in layers.items():
            keys["klang"].append(("voice", inst, layer, voice))
    for sec, groove in (character.get("grooves") or {}).items():
        keys["groove"].append(("groove", sec, groove))
    for sec, insts in (character.get("patterns") or {}).items():
        for inst, pattern in insts.items():
            keys["groove"].append(("pattern", sec, inst, pattern))
    for what in ("intro", "ending"):
        if character.get(what):
            keys["groove"].append((what, character[what]))
    for bank, progression in (character.get("chords") or {}).items():
        keys["melodie"].append(("chords", bank, progression))
    return keys


def learn(entries: list, taste: Optional[Taste] = None) -> Taste:
    """Der Geschmack aus den Daumen im Verlauf (history.Entry mit thumbs und character), zu taste dazu."""
    taste = taste or Taste()
    for entry in entries:
        thumbs = entry.thumbs or {}
        if not thumbs:
            continue
        keys = song_keys(entry.character or {})
        for aspect, found in keys.items():
            vote = thumbs.get(aspect, 0)
            for key in found if vote else ():
                taste.scores[key] = taste.scores.get(key, 0) + vote
        vote = thumbs.get("stimme", 0)
        singer = entry.settings.singer if entry.settings.vocal_engine == "NEUTRINO" else ""
        if vote and singer:
            pool = taste.singers.setdefault(entry.settings.style, {})
            pool[singer] = pool.get(singer, 0) + vote
    return taste


def load(settings) -> Optional[Taste]:
    """Der Geschmack aus dem Verlauf im Ausgabeordner; None, wenn er aus ist oder es noch keine Daumen gibt."""
    if not settings.taste_learning:
        return None
    import history
    try:
        taste = learn(history.entries(settings.output_dir()), _archived(settings.output_dir()))
    except OSError as e:
        log.warning("Geschmack nicht gelesen: %s", e)
        return None
    if taste:
        log.info("Geschmack aus dem Verlauf: %s", taste.describe())
    return taste or None


def _archive_path(output_dir: str) -> str:
    import history
    return os.path.join(history.folder(output_dir), ARCHIVE)


def _archived(output_dir: str) -> Taste:
    """Die Daumen der Songs, die schon aus dem Verlauf gefallen sind."""
    try:
        with open(_archive_path(output_dir), encoding="utf-8") as f:
            data = json.load(f)
        scores = {tuple(item["key"]): int(item["score"]) for item in data.get("scores", [])}
        return Taste(scores, {style: dict(pool) for style, pool in data.get("singers", {}).items()})
    except (OSError, ValueError, KeyError, TypeError):
        return Taste()


def archive(output_dir: str, entry) -> None:
    """Nimmt die Daumen eines Songs, der aus dem Verlauf fällt, in geschmack.json auf."""
    taste = learn([entry], _archived(output_dir))
    try:
        with open(_archive_path(output_dir), "w", encoding="utf-8") as f:
            json.dump({"scores": [{"key": list(k), "score": v} for k, v in taste.scores.items()],
                       "singers": taste.singers}, f, ensure_ascii=False, indent=1)
    except OSError as e:
        log.warning("Geschmack nicht gespeichert: %s", e)


def snapshot(settings) -> list:
    """Der Geschmack jetzt, zum Speichern in den Einstellungen des Songs ([[Schlüssel], Daumen])."""
    taste = load(settings)
    return [[list(key), score] for key, score in sorted(taste.scores.items(), key=str)] if taste else []


def from_snapshot(found: list) -> Taste:
    return Taste({tuple(key): int(score) for key, score in found})


def pick(rng, pool: list, taste: Optional[Taste], key) -> object:
    """rng.choice(pool), mit Geschmack gewichtet; key(option) ist der Schlüssel einer Option."""
    weights = taste.weights([key(option) for option in pool]) if taste else None
    if weights is None:
        return rng.choice(pool)
    return rng.choices(pool, weights)[0]

# userdata.py – Dein Datenordner: Songs, Einstellungen, Vorlagen, Vorbilder und Motive an einem Ort
#
# Früher lag alles im Programmordner (vocaloid_generator\output, user_settings.json, ...). Jetzt liegt es in
# config.DATA_DIR (Standard Dokumente\Vloid Songs), wo Updates und ein neuer Installer es nie anfassen. migrate()
# zieht beim Start um, was noch an der alten Stelle liegt; import_from() holt alles aus einem anderen Programmordner,
# z. B. dem alten entpackten oder geklonten Ordner, wenn die App jetzt per Setup installiert ist.
import json
import logging
import os
import shutil

import config

log = logging.getLogger(__name__)

# (alter Name im Programmordner, Name im Datenordner)
ITEMS = (
    ("user_settings.json", "Einstellungen.json"),
    ("output", "Songs"),
    ("vorlagen", "Vorlagen"),
    ("vorbilder", "Vorbilder"),
    ("motive", "Motive"),
    ("vorbild_messungen.json", "vorbild_messungen.json"),
)
NEW_NAMES = tuple(new for _, new in ITEMS)
# Was ein alter Programmordner sonst noch Großes mitbringt: NEUTRINO und die geladenen Klänge und Modelle
TOOLS = ("NEUTRINO-windows-v3.1", "tools")


def _merge(source: str, target: str) -> bool:
    """Verschiebt source nach target; liegt dort schon ein Ordner, kommt nur dazu, was fehlt. True, wenn etwas kam."""
    if not os.path.exists(source) or os.path.normcase(os.path.abspath(source)) == \
            os.path.normcase(os.path.abspath(target)):
        return False
    if not os.path.exists(target):
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.move(source, target)
        return True
    if not (os.path.isdir(source) and os.path.isdir(target)):
        return False                # eine Datei am Ziel gewinnt, die alte bleibt liegen
    moved = False
    for name in os.listdir(source):
        moved = _merge(os.path.join(source, name), os.path.join(target, name)) or moved
    try:
        os.rmdir(source)            # nur, wenn er jetzt leer ist
    except OSError:
        pass
    return moved


def _sources(target: str) -> list:
    """[(alter Ort, neuer Ort)]: die alten Namen im Programmordner und die neuen Namen am jeweils anderen Ort."""
    pairs = [(os.path.join(config.BASE_DIR, old), os.path.join(target, new)) for old, new in ITEMS]
    for other in {config.default_data_dir(), config.BASE_DIR}:
        if os.path.normcase(os.path.abspath(other)) != os.path.normcase(os.path.abspath(target)):
            pairs += [(os.path.join(other, new), os.path.join(target, new)) for new in NEW_NAMES]
    return pairs


def migrate(target: str = None) -> list:
    """Zieht Daten von alten Orten in den Datenordner um. Rückgabe: die neuen Pfade, die etwas bekommen haben.
    Wer den Ordner mit VLOID_DATEN selbst festlegt (z. B. die Tests), zieht selbst um."""
    if target is None and os.environ.get(config.DATA_ENV):
        return []
    target = target or config.DATA_DIR
    moved = []
    for source, destination in _sources(target):
        try:
            if _merge(source, destination):
                moved.append(destination)
                log.info("Umgezogen: %s -> %s", source, destination)
        except OSError as e:
            log.warning("Konnte %s nicht nach %s verschieben: %s", source, destination, e)
    if moved:
        fix_paths(os.path.join(target, "Einstellungen.json"), target)
    return moved


def import_from(old_root: str, target: str = None, program_root: str = None) -> list:
    """
    Holt Songs und Einstellungen aus einem anderen Programmordner (alte Namen in old_root\\vocaloid_generator oder
    neue Namen in old_root) in den Datenordner, dazu NEUTRINO und tools (Klänge, Modelle) in diesen Programmordner.
    """
    target = target or config.DATA_DIR
    program_root = program_root or config.REPO_ROOT
    old_root = os.path.abspath(old_root)
    if os.path.basename(old_root).lower() == "vocaloid_generator":
        old_root = os.path.dirname(old_root)
    moved = []
    pairs = [(os.path.join(old_root, "vocaloid_generator", old), os.path.join(target, new)) for old, new in ITEMS]
    pairs += [(os.path.join(old_root, "vocaloid_generator", new), os.path.join(target, new)) for new in NEW_NAMES]
    pairs += [(os.path.join(old_root, name), os.path.join(program_root, name)) for name in TOOLS]
    for source, destination in pairs:
        try:
            if _merge(source, destination):
                moved.append(destination)
                log.info("Übernommen: %s -> %s", source, destination)
        except OSError as e:
            log.warning("Konnte %s nicht übernehmen: %s", source, e)
    if moved:
        fix_paths(os.path.join(target, "Einstellungen.json"), target, old_roots=(old_root,), program_root=program_root)
    return moved


def fix_paths(settings_file: str, target: str, old_roots: tuple = (), program_root: str = None) -> None:
    """
    Pfade in den Einstellungen, die auf die alten Orte zeigen (z. B. eine gesummte Melodie im alten output-Ordner),
    zeigen danach auf den Datenordner, NEUTRINO und tools auf den neuen Programmordner. Ein Ausgabeordner, der der
    alte Standard war, wird wieder leer (= Standard).
    """
    try:
        with open(settings_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    bases = [config.BASE_DIR, config.default_data_dir(), *(os.path.join(r, "vocaloid_generator") for r in old_roots),
             *old_roots]
    renames = [(os.path.join(base, old), os.path.join(target, new)) for base in bases for old, new in ITEMS]
    renames += [(os.path.join(base, new), os.path.join(target, new)) for base in bases for new in NEW_NAMES]
    if program_root:
        renames += [(os.path.join(r, name), os.path.join(program_root, name)) for r in old_roots for name in TOOLS]

    def moved(value: str) -> str:
        norm = os.path.normcase(os.path.abspath(value)) if value else ""
        for old, new in renames:
            prefix = os.path.normcase(os.path.abspath(old))
            if norm == prefix or norm.startswith(prefix + os.sep):
                return new + os.path.abspath(value)[len(os.path.abspath(old)):]
        return value

    changed = False
    for key, value in list(data.items()):
        if isinstance(value, str) and value and (os.sep in value or "/" in value):
            fixed = moved(value)
            if key == "output_ordner" and os.path.normcase(fixed) == os.path.normcase(os.path.join(target, "Songs")):
                fixed = ""
            if fixed != value:
                data[key], changed = fixed, True
    if changed:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def in_program_folder() -> bool:
    """Bleiben die Daten wie früher im Programmordner?"""
    return config.data_choice().lower() == config.PROGRAM_FOLDER


def choose_program_folder(keep_in_program: bool) -> None:
    """Merkt sich die Wahl für den nächsten Start; erst dann zieht die App um."""
    if keep_in_program:
        with open(config.DATA_CHOICE, "w", encoding="utf-8") as f:
            f.write(config.PROGRAM_FOLDER + "\n")
    elif os.path.exists(config.DATA_CHOICE):
        os.remove(config.DATA_CHOICE)


def describe() -> str:
    return f"Deine Daten liegen in {config.DATA_DIR}"

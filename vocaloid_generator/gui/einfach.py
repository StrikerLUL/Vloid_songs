# einfach.py – Die einfache Ansicht (1.6.0): Stil, Stimmung, Stimme, Länge, Qualität, Text und ein Knopf
#
# Alle anderen Einstellungen bleiben, wie sie in der Profi-Ansicht (den Tabs) stehen. Die Qualität gilt nur hier
# (qualitaet.py): Wer in der Profi-Ansicht erzeugt, bekommt genau seine Schalter.
from typing import Callable

from nicegui import ui

import laufzeit
import qualitaet
from gui import labels
from settings import SongSettings
from styles import STYLES

MOODS = {0.0: "ruhig", 0.25: "sanft", 0.5: "normal", 0.75: "kräftig", 1.0: "wild"}


def length_of(sections: list) -> str:
    """Welche Vorlage (Kurz, Standard, Lang wie im Tab Song) ein Ablauf ist; „“, wenn er eigen ist."""
    return next((name for name, order in labels.STRUCTURES.items() if list(sections) == order), "")


def mood_name(value: float) -> str:
    return MOODS[min(MOODS, key=lambda m: abs(m - value))]


def estimate(settings: SongSettings, quality: str) -> str:
    """„zuletzt etwa 4 Min.“ aus früheren Läufen dieser Stufe; leer, solange es keine gibt."""
    seconds = laufzeit.typical(run_kind(settings, quality))
    if seconds is None:
        return ""
    return f"zuletzt etwa {max(1, round(seconds / 60))} Min." if seconds >= 60 else f"zuletzt etwa {seconds:.0f} s"


def run_kind(settings: SongSettings, quality: str) -> str:
    """Die Art des Laufs für die Restzeit: wie laufzeit.kind, dazu die Stufe."""
    return f"{laufzeit.kind(qualitaet.apply(settings, quality), 1, False)}|{quality}"


def simple_panel(s: SongSettings, singers: Callable[[], list], on_generate: Callable, on_duel: Callable,
                 on_build_text: Callable) -> Callable[[], None]:
    """Baut die einfache Ansicht; Rückgabe: refresh() für Stimmen, Länge und Zeitschätzung."""
    from gui.panels import favorite_voice, hint

    def style_changed() -> None:
        from preset_manager import preset_settings
        new = preset_settings(s.style, s)
        if new is not None:            # Tempo, Tonart und Lautstärken wie für den Stil typisch, die Länge bleibt
            s.bpm, s.key, s.scale = new.bpm, new.key, new.scale
            for ch, data in new.channels.items():
                s.channels[ch].volume, s.channels[ch].pan = data.volume, data.pan
        favorite_voice(s)
        refresh()

    def length_changed(value) -> None:
        if value in labels.STRUCTURES:
            s.active_sections = list(labels.STRUCTURES[value])

    with ui.column().classes("w-full gap-3").mark("simple-panel"):
        hint("Hier stellst du nur das Wichtigste ein. Alles andere steht unter „Profi“ oben rechts und bleibt, wie es "
             "dort eingestellt ist.")
        ui.select(list(STYLES), label="Stil").bind_value(s, "style").classes("w-full").mark("simple-style") \
            .on("update:model-value", lambda: ui.timer(0.05, style_changed, once=True))
        with ui.row().classes("w-full items-center no-wrap gap-3"):
            ui.label("Stimmung").classes("w-24")
            ui.label("ruhig").classes("text-caption text-grey-5")
            ui.slider(min=0, max=1, step=0.05).bind_value(s, "mood").classes("col").mark("simple-mood") \
                .tooltip("Ruhig: weicheres Schlagzeug, weniger Fills, schlankere Besetzung. Wild: härter, mehr "
                         "Fills und Becken, alle spielen mit")
            ui.label("wild").classes("text-caption text-grey-5")
        voice = ui.select([s.singer], label="Stimme").bind_value(s, "singer").classes("w-full").mark("simple-singer")
        with ui.row().classes("w-full items-center no-wrap gap-3"):
            ui.label("Länge").classes("w-24")
            length = ui.toggle(list(labels.STRUCTURES), value=length_of(s.active_sections) or None,
                               on_change=lambda e: length_changed(e.value)).props("no-caps dense").mark("simple-length")
        with ui.row().classes("w-full items-center no-wrap gap-3"):
            ui.label("Qualität").classes("w-24")
            ui.toggle(list(qualitaet.PRESETS)).bind_value(s, "quality").props("no-caps dense") \
                .on_value_change(lambda: refresh()).mark("simple-quality")
        quality_hint = ui.label().classes("text-caption text-grey-5").mark("simple-quality-hint")
        with ui.row().classes("w-full items-center no-wrap"):
            ui.label("Text").classes("text-subtitle2")
            ui.space()
            ui.button("Text bauen", icon="edit_note", on_click=lambda: on_build_text()) \
                .props("flat dense no-caps").mark("simple-build-text") \
                .tooltip("Thema und Stimmung wählen: die App setzt einen japanischen Text mit Romaji und Deutsch "
                         "zusammen, ohne KI")
        ui.textarea(placeholder="[Verse]\n…\n[Chorus]\n…").bind_value(s, "lyrics").props("outlined autogrow") \
            .classes("w-full").style("max-height: 16rem; overflow: auto").mark("simple-lyrics")
        with ui.row().classes("w-full items-center gap-2 q-mt-sm"):
            ui.button("Song machen", icon="auto_awesome", on_click=lambda: on_generate()) \
                .props("unelevated size=lg no-caps color=secondary").classes("col").mark("simple-generate")
            ui.button("Hör-Duell", icon="hearing", on_click=lambda: on_duel()).props("outline no-caps") \
                .mark("simple-duel").tooltip("Zwei Fassungen blind vergleichen: die App lernt, was dir gefällt")

    def refresh() -> None:
        names = sorted(set(singers()) | {s.singer})
        voice.set_options(names, value=s.singer)
        length.set_value(length_of(s.active_sections) or None)
        when = estimate(s, s.quality)
        quality_hint.set_text(f"{qualitaet.DESCRIPTIONS[s.quality]}{f' ({when})' if when else ''}")

    refresh()
    return refresh


def switch_names(client) -> dict[str, str]:
    """Feld → Beschriftung aller Schalter dieser Seite (die mit „switch-Feld“ markierten), auch ausgeblendeter."""
    names = {}
    for element in list(client.elements.values()):
        for marker in element._markers:
            text = getattr(element, "text", "")
            if marker.startswith("switch-") and isinstance(text, str) and text:
                names.setdefault(marker[len("switch-"):], text.split(":")[0])
    return names


def _chords(chords: dict) -> str:
    from song_character import SECTION_NAMES
    return ", ".join(f"{SECTION_NAMES.get(kind, kind)} {'–'.join(map(str, steps))}"
                     for kind, steps in chords.items() if steps)


def song_info(host, entry, current: SongSettings, names: dict[str, str]) -> None:
    """„Was steckt in diesem Song?“: Grundwerte, was gewürfelt wurde, welche Schalter an und aus waren und was heute
    anders eingestellt ist."""
    from dataclasses import fields

    from gui.page import describe
    from song_character import Character
    s = entry.settings
    switches = {f: label for f, label in sorted(names.items(), key=lambda x: x[1].lower())
                if isinstance(getattr(s, f, None), bool)}
    on = [label for f, label in switches.items() if getattr(s, f)]
    off = [label for f, label in switches.items() if not getattr(s, f)]
    basics = {"style": "Stil", "bpm": "Tempo", "key": "Tonart", "scale": "Tonleiter", "singer": "Stimme",
              "vocal_engine": "Gesang mit"}
    differs = [f"{label}: damals {getattr(s, f)}, jetzt {getattr(current, f)}"
               for f, label in {**basics, **switches}.items()
               if hasattr(current, f) and getattr(s, f) != getattr(current, f)]
    character = entry.character or {}
    known = {f.name for f in fields(Character)}
    rolled = Character(**{k: v for k, v in character.items() if k in known}).describe() if character else ""
    length = length_of(s.active_sections) or f"{len(s.active_sections)} Teile"
    with host, ui.dialog() as dialog, ui.card().classes("w-[34rem]").mark("song-info"):
        ui.label("Was steckt in diesem Song?").classes("text-h6")
        ui.label(describe(s)).classes("text-body2")
        ui.label(f"Stimme {s.singer} ({s.vocal_engine}) · Länge {length}").classes("text-caption text-grey-5")
        with ui.scroll_area().style("height: 50vh"):
            if rolled:
                ui.label("Gewürfelt").classes("text-subtitle2 q-mt-sm")
                ui.label(rolled).classes("text-caption").mark("song-info-rolled")
            if character.get("chords"):
                ui.label(f"Akkorde: {_chords(character['chords'])}").classes("text-caption")
            ui.label(f"An ({len(on)})").classes("text-subtitle2 q-mt-sm")
            ui.label(", ".join(on) or "–").classes("text-caption").mark("song-info-on")
            ui.label(f"Aus ({len(off)})").classes("text-subtitle2 q-mt-sm")
            ui.label(", ".join(off) or "–").classes("text-caption").mark("song-info-off")
            ui.label("Anders als jetzt").classes("text-subtitle2 q-mt-sm")
            if differs:
                for line in differs:
                    ui.label(line).classes("text-caption").mark("song-info-differs")
            else:
                ui.label("Nichts: der Song entstand mit deinen jetzigen Einstellungen.").classes("text-caption")
        with ui.row().classes("w-full justify-end"):
            ui.button("Schließen", on_click=dialog.close).props("flat").mark("song-info-close")
    dialog.open()

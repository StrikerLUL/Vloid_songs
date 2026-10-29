# textbau.py – Der Dialog zum Text-Baukasten (1.6.0, textbaukasten.py)
from typing import Callable

from nicegui import ui

import textbaukasten
from settings import SongSettings

OWN = "eigenes"


def open_builder(host, settings: SongSettings, on_done: Callable[[], None]) -> None:
    """Thema, Stimmung und Titelwort wählen, zusammensetzen, Zeilen tauschen, übernehmen (ersetzt settings.lyrics)."""
    from gui.panels import hint
    state = {"song": None}

    def words(theme: str) -> dict:
        out = {"": "eins vom Thema"}
        out.update({w.text: f"{textbaukasten.plain(w.text)} – {w.german}" for w in textbaukasten.TITLE_WORDS[theme]})
        out[OWN] = "eigenes Wort …"
        return out

    def theme_changed() -> None:
        word.set_options(words(theme.value), value="")

    def chosen_word():
        if word.value == OWN:
            found = textbaukasten.title_word(own.value or "", own_german.value or "")
            if found is None:
                ui.notify("Das Wort kenne ich nicht: schreib es japanisch (星屑, ほしくず) oder wähle eins aus der Liste",
                          type="warning")
            return found, True
        if word.value:
            return next(w for w in textbaukasten.TITLE_WORDS[theme.value] if w.text == word.value), True
        return None, False

    def compose() -> None:
        hook, wanted = chosen_word()
        if wanted and hook is None:
            return
        song = textbaukasten.build(settings, theme.value, mood.value, hook)
        if not song.parts:
            ui.notify("Im Ablauf ist keine gesungene Sektion (Strophe, Pre-Chorus, Refrain, Bridge)", type="warning")
            return
        state["song"] = song
        result.refresh()
        apply_button.enable()

    def swap(part: int, line: int) -> None:
        textbaukasten.swap(state["song"], part, line)
        result.refresh()

    def take() -> None:
        settings.lyrics = state["song"].text()
        on_done()
        dialog.close()
        ui.notify("Text übernommen: im Tab Text siehst du Silben, Reime und Lesungen pro Zeile", type="positive")

    with host, ui.dialog() as dialog, ui.card().classes("w-[44rem] max-w-full").mark("text-builder"):
        ui.label("Text-Baukasten").classes("text-h6")
        hint("Die App setzt einen japanischen Text aus über 500 von Hand geschriebenen Zeilen zusammen, passend zu "
             "Ablauf und Tempo: so viele Silben, wie in die Phrasen passen, Reime am Zeilenende, das Titelwort am "
             "Anfang und Ende des Refrains, unter jeder Zeile die Übersetzung fürs Video. Ohne KI.")
        with ui.row().classes("w-full items-center gap-3"):
            theme = ui.select(textbaukasten.THEMES, value="liebe", label="Thema",
                              on_change=lambda: theme_changed()).classes("col").mark("text-theme")
            mood = ui.toggle(list(textbaukasten.MOODS), value="bittersüß").props("no-caps dense").mark("text-mood")
        with ui.row().classes("w-full items-center gap-3"):
            word = ui.select(words("liebe"), value="", label="Titelwort").classes("col").mark("text-word")
            own = ui.input("eigenes Wort", placeholder="星屑 oder Feuerwerk").classes("col").mark("text-own-word") \
                .bind_visibility_from(word, "value", value=OWN)
            own_german = ui.input("auf Deutsch (fürs Video)").classes("col").mark("text-own-german") \
                .bind_visibility_from(word, "value", value=OWN)
        ui.button("Zusammensetzen", icon="auto_fix_high", on_click=compose).props("unelevated no-caps color=secondary") \
            .mark("text-build").tooltip("Noch einmal drücken: ein neuer Text mit denselben Wünschen")

        @ui.refreshable
        def result() -> None:
            song = state["song"]
            if song is None:
                return
            ui.label(f"Titelwort: {textbaukasten.plain(song.hook.text)} ({song.hook.kana}) – {song.hook.german}") \
                .classes("text-subtitle2 q-mt-sm").mark("text-hook")
            for problem, sung in textbaukasten.check(song, settings):
                ui.label(f"„{problem.text}“ singt die App als {sung}: im Tab Text eine Lesung wie 君[きみ] angeben") \
                    .classes("text-caption text-orange-5").mark("text-reading")
            with ui.scroll_area().style("height: 45vh"):
                for p, part in enumerate(song.parts):
                    times = f" · {part.shared}× gesungen" if part.shared > 1 else ""
                    ui.label(f"{part.header}{times}").classes("text-caption text-deep-purple-3 q-mt-sm")
                    for i, line in enumerate(part.lines):
                        with ui.row().classes("w-full items-center no-wrap gap-2"):
                            with ui.column().classes("col gap-0"):
                                ui.label(textbaukasten.plain(line.text)).classes("text-body1") \
                                    .mark(f"text-line-{p}-{i}")
                                ui.label(f"{line.romaji} · {line.count} Silben").classes("text-caption text-grey-5")
                                ui.label(line.german).classes("text-caption text-italic")
                            ui.button(icon="autorenew", on_click=lambda _, a=p, b=i: swap(a, b)) \
                                .props("flat round dense").mark(f"text-swap-{p}-{i}").tooltip("andere Zeile")

        result()
        if settings.lyrics.strip():
            ui.label("Übernehmen ersetzt den bisherigen Text.").classes("text-caption text-amber-5")
        with ui.row().classes("w-full justify-end"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat").mark("text-close")
            apply_button = ui.button("Übernehmen", icon="check", on_click=take).props("unelevated") \
                .mark("text-apply")
            apply_button.disable()
    dialog.open()

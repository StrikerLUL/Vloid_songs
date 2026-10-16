# dialogs.py – Fenster des Hilfe-Menüs: Einrichten, System prüfen, Fehlerbericht, Updates, Was ist neu, Credits
import logging
import os
import queue
from collections.abc import Awaitable, Callable

from nicegui import app, run, ui

import cancel
import config
import einrichten
import fehlerbericht
import speicher
import systemcheck
import updates
import userdata
from gui import media
from settings import SongSettings
from version import VERSION

log = logging.getLogger(__name__)

PickFn = Callable[..., Awaitable[str | None]]
ICONS = {True: ("check_circle", "positive"), False: ("cancel", "negative"), None: ("remove_circle_outline", "grey")}


class Lines:
    """Zeilen aus einem Hintergrund-Thread, die ein Timer in ein ui.log schiebt."""

    def __init__(self, view) -> None:
        self.view = view
        self.queue: queue.Queue = queue.Queue()
        ui.timer(0.2, self.flush)

    def __call__(self, line: str) -> None:
        self.queue.put(line)

    def flush(self) -> None:
        while not self.queue.empty():
            self.view.push(self.queue.get_nowait())


def _title(text: str) -> None:
    ui.label(text).classes("text-h6")


def _hint(text: str) -> None:
    ui.label(text).classes("text-caption text-grey-5")


# ── Einrichten ──────────────────────────────────────────────────────────────────
def setup_wizard(s: SongSettings, pick: PickFn, on_change: Callable[[], None]) -> ui.dialog:
    """Der Einrichten-Assistent: was die App zusätzlich laden kann, mit Platzbedarf und Fortschritt."""
    state = {"running": False}
    sizes: dict = {}            # Baustein → Bytes auf der Festplatte (speicher.components), kommt im Hintergrund
    with ui.dialog().props("persistent") as dialog, ui.card().classes("w-[720px] max-w-full bg-grey-9"):
        _title("Einrichten")
        _hint("Hier lädt die App, was sie zusätzlich nutzen kann. Alles ist freiwillig; was fehlt, lässt sich jederzeit "
              "über Hilfe › Einrichten nachholen. Ein abgebrochener Download macht beim nächsten Mal dort weiter.")
        ui.label(f"Frei auf dem Laufwerk der App: {einrichten.free_gb():.0f} GB").classes("text-caption") \
            .mark("wizard-free")

        ui.label("Deine Daten").classes("text-subtitle1 q-mt-sm")
        ui.label(userdata.describe()).classes("text-body2").mark("wizard-data")
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            old = ui.input("Alter Programmordner (z. B. der entpackte Vloid_songs-Ordner)").classes("col") \
                .props("dense stack-label clearable").mark("wizard-old-folder")

            async def choose_old() -> None:
                path = await pick(folder=True)
                if path:
                    old.value = path
            if pick.available:
                ui.button(icon="folder_open", on_click=choose_old).props("flat round dense")

            async def take_over() -> None:
                if not old.value or not os.path.isdir(old.value):
                    ui.notify("Den alten Ordner gibt es nicht.", type="warning")
                    return
                moved = await run.io_bound(userdata.import_from, old.value)
                ui.notify(f"Übernommen: {len(moved)} Ordner und Dateien" if moved else
                          "Dort lag nichts, was hier noch fehlt.", type="positive" if moved else "info")
                if moved:
                    on_change()
                    show()
            ui.button("Übernehmen", icon="move_down", on_click=take_over).props("flat dense no-caps") \
                .mark("wizard-import")
        _hint("Holt Songs, Einstellungen, Vorlagen, Vorbilder, Motive, NEUTRINO und geladene Klänge aus einem alten "
              "Ordner hierher, damit nichts doppelt geladen werden muss.")

        ui.label("NEUTRINO").classes("text-subtitle1 q-mt-sm")
        neutrino_status = ui.label().classes("text-body2").mark("wizard-neutrino")
        neutrino_hint = ui.label().classes("text-caption text-warning").mark("wizard-neutrino-hint")
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            ui.input("NEUTRINO-Ordner (darin liegen bin und model)").bind_value(s, "neutrino_pfad") \
                .classes("col").props("dense stack-label clearable").on("blur", lambda: show())

            async def choose_neutrino() -> None:
                path = await pick(folder=True)
                if path:
                    s.neutrino_pfad = path
                    show()
            if pick.available:
                ui.button(icon="folder_open", on_click=choose_neutrino).props("flat round dense")
        with ui.row().classes("items-center gap-2"):
            ui.link("NEUTRINO herunterladen (studio-neutrino.com)", "https://studio-neutrino.com", new_tab=True) \
                .classes("text-caption")
            ui.button("Stimmen-Ordner öffnen", icon="folder",
                      on_click=lambda: media.open_folder(os.path.join(s.neutrino_dir(), "model"))) \
                .props("flat dense no-caps")
        _hint("NEUTRINO darf die App nicht selbst laden (Lizenz). Lade es von der Seite oben, entpack es und wähl den "
              "Ordner. Weitere Stimmen kommen als Ordner in model.")

        ui.label("Klänge und Modelle").classes("text-subtitle1 q-mt-sm")
        rows = ui.column().classes("w-full gap-1")
        checks: dict = {}
        progress = ui.linear_progress(value=0, show_value=False).props("rounded color=secondary").classes("q-mt-sm")
        step = ui.label("").classes("text-caption").mark("wizard-step")
        output = ui.log(max_lines=300).classes("w-full h-40 text-xs")
        lines = Lines(output)

        ui.label("Speicherplatz").classes("text-subtitle1 q-mt-sm")
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            songs_label = ui.label("Songs: …").classes("text-body2 col").mark("wizard-songs")
            ui.button("Projekte löschen (Songs bleiben)", icon="delete_sweep", on_click=lambda: drop_projects()) \
                .props("flat dense no-caps").mark("wizard-drop-projects")
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            caches_label = ui.label("Zwischenspeicher: …").classes("text-body2 col").mark("wizard-caches")
            ui.button("Aufräumen", icon="cleaning_services", on_click=lambda: clear_caches()) \
                .props("flat dense no-caps").mark("wizard-clear")
        _hint("Projekte sind der aufgehobene Gesang zum Wieder-Öffnen aus dem Verlauf; Favoriten und benannte Songs "
              "behalten ihres. Zwischenspeicher sind Messungen der Vorbilder, alte Protokolle und Fehlerberichte, die "
              "beim nächsten Mal neu entstehen. Eingerichtete Klänge und Modelle lassen sich oben mit „Entfernen“ "
              "löschen und jederzeit neu einrichten.")
        with ui.row().classes("w-full items-center gap-2 q-mt-sm"):
            ui.switch("Beim Start zeigen, bis „Fertig“ gedrückt ist").bind_value(s, "setup_wizard").props("dense") \
                .mark("wizard-show")
            ui.space()
            start = ui.button("Ausgewählte einrichten", icon="download", on_click=lambda: install()) \
                .props("unelevated no-caps color=secondary").mark("wizard-install")
            stop = ui.button("Abbrechen", icon="stop", on_click=cancel.request).props("flat no-caps") \
                .mark("wizard-stop")
            later = ui.button("Später", on_click=dialog.close).props("flat no-caps").mark("wizard-later")
            ui.button("Fertig", icon="check", on_click=lambda: finish()).props("flat no-caps").mark("wizard-done")

    def show() -> None:
        from vocal_synthesizer import neutrino_hinweis, neutrino_info
        neutrino_status.set_text(neutrino_info(s.neutrino_dir()))
        neutrino_hint.set_text(neutrino_hinweis(s.neutrino_dir()))
        neutrino_hint.set_visibility(bool(neutrino_hint.text))
        rows.clear()
        checks.clear()
        with rows:
            for c in einrichten.components():
                have = einrichten.is_installed(c)
                with ui.row().classes("w-full items-start no-wrap gap-2"):
                    if have:
                        ui.icon("check_circle", color="positive").classes("q-mt-xs").mark(f"wizard-have-{c.key}")
                    else:
                        checks[c.key] = ui.checkbox(value=c.recommended).props("dense").mark(f"wizard-{c.key}")
                    with ui.column().classes("gap-0 col"):
                        size = speicher.describe(sizes[c.key]) + " belegt" if have and c.key in sizes else c.size
                        ui.label(f"{c.name} · {size}").classes("text-body2")
                        ui.label(c.what + (" (schon da)" if have else "")).classes("text-caption text-grey-5")
                    if have and c.key in sizes:
                        ui.button("Entfernen", icon="delete", on_click=lambda _, c=c: remove(c)) \
                            .props("flat dense no-caps color=grey").mark(f"wizard-remove-{c.key}")
        start.set_enabled(bool(checks) and not state["running"])
        stop.set_visibility(state["running"])
        later.set_enabled(not state["running"])

    async def install() -> None:
        keys = [k for k, box in checks.items() if box.value]
        if not keys:
            ui.notify("Nichts ausgewählt.", type="info")
            return
        state["running"] = True
        cancel.reset()
        show()

        def report(fraction: float, message: str) -> None:
            progress.set_value(fraction)
            step.set_text(message)
        try:
            results = await run.io_bound(einrichten.install, keys, lines, report)
        except cancel.Cancelled:
            results = None
            ui.notify("Einrichten abgebrochen. Beim nächsten Mal geht es dort weiter.", type="warning")
        finally:
            state["running"] = False
            cancel.reset()
        if results:
            failed = [einrichten.find(k).name for k, ok in results.items() if not ok]
            ui.notify("Alles eingerichtet." if not failed else f"Nicht geklappt: {', '.join(failed)} (Ausgabe "
                      "unten, noch einmal starten hilft oft)", type="positive" if not failed else "warning",
                      multi_line=True)
        on_change()
        show()

    def finish() -> None:
        einrichten.mark_wizard_done()
        dialog.close()

    async def measure() -> None:
        """Wie viel Platz Bausteine, Songs und Zwischenspeicher belegen (im Hintergrund, das Zählen dauert)."""
        found = await run.io_bound(speicher.components)
        sizes.clear()
        sizes.update({u.key: u.bytes for u in found})
        total, projects, count = await run.io_bound(speicher.songs, s.output_dir())
        caches = await run.io_bound(lambda: sum(speicher.size(p) for p in speicher.caches()))
        songs_label.set_text(f"Songs: {speicher.describe(total)}, davon {count} aufgehobene Projekte: "
                             f"{speicher.describe(projects)}")
        caches_label.set_text(f"Zwischenspeicher: {speicher.describe(caches)}")
        show()

    async def remove(c) -> None:
        answer = await _confirm(f"{c.name} entfernen?", f"Gibt {speicher.describe(sizes.get(c.key))} frei. Neu "
                                "einrichten geht jederzeit hier im Assistenten.")
        if not answer:
            return
        try:
            freed = await run.io_bound(speicher.remove, c.key)
        except (ValueError, OSError) as e:
            ui.notify(str(e), type="warning", multi_line=True)
            return
        ui.notify(f"{c.name} entfernt: {speicher.describe(freed)} frei", type="positive")
        on_change()
        await measure()

    async def drop_projects() -> None:
        answer = await _confirm("Projekte löschen?", "Die Songs bleiben im Verlauf, nur ihr aufgehobener Gesang geht. "
                                "Wieder-Öffnen singt sie dann neu. Favoriten und benannte Songs behalten ihr Projekt.")
        if answer:
            freed = await run.io_bound(speicher.drop_projects, s.output_dir())
            ui.notify(f"Projekte gelöscht: {speicher.describe(freed)} frei", type="positive")
            await measure()

    async def clear_caches() -> None:
        freed = await run.io_bound(speicher.clear_caches)
        ui.notify(f"Aufgeräumt: {speicher.describe(freed)} frei", type="positive")
        await measure()

    show()
    with dialog:
        ui.timer(0.1, measure, once=True)
    return dialog


async def _confirm(question: str, detail: str) -> bool:
    with ui.dialog() as ask, ui.card():
        ui.label(question).classes("text-h6")
        ui.label(detail).classes("text-body2")
        with ui.row().classes("w-full justify-end"):
            ui.button("Abbrechen", on_click=lambda: ask.submit(False)).props("flat no-caps")
            ui.button("Ja", on_click=lambda: ask.submit(True)).props("unelevated no-caps color=negative") \
                .mark("confirm-yes")
    answer = await ask
    ask.delete()
    return bool(answer)


# ── System prüfen ─────────────────────────────────────────────────────────────
def system_check(s: SongSettings) -> ui.dialog:
    state = {"busy": False}
    with ui.dialog() as dialog, ui.card().classes("w-[720px] max-w-full bg-grey-9"):
        _title("System prüfen")
        _hint("Jeder Baustein macht etwas Kleines echt: einen Takt Klavier, zwei Töne mit NEUTRINO, einen Probeton "
              "bewerten, zum Schluss einen kurzen ganzen Song. Grau heißt: nicht eingerichtet.")
        summary = ui.label("").classes("text-subtitle1").mark("check-summary")
        rows = ui.column().classes("w-full gap-1")
        progress = ui.linear_progress(value=0, show_value=False).props("rounded color=secondary")
        with ui.row().classes("w-full items-center gap-2"):
            check_button = ui.button("Prüfen", icon="fact_check", on_click=lambda: check(False)) \
                .props("unelevated no-caps color=secondary").mark("check-run")
            thorough = ui.button("Gründlich (mit ACE-Step und KI-Begleitung)", icon="speed",
                                 on_click=lambda: check(True)).props("outline no-caps").mark("check-thorough")
            ui.space()
            ui.button("Fehlerbericht speichern", icon="bug_report", on_click=lambda: save_report(s)) \
                .props("flat no-caps")
            ui.button("Schließen", on_click=dialog.close).props("flat no-caps")

    def show(found) -> None:
        rows.clear()
        if not found:
            summary.set_text("Noch nicht geprüft.")
            return
        when, results = found
        summary.set_text(f"{systemcheck.summary(results)} (geprüft {when:%d.%m. %H:%M})")
        with rows:
            for r in results:
                icon, color = ICONS[r.ok]
                with ui.row().classes("w-full items-start no-wrap gap-2"):
                    ui.icon(icon, color=color).classes("q-mt-xs").mark(f"check-{r.key}")
                    with ui.column().classes("gap-0 col"):
                        ui.label(f"{r.name}" + (f"  ({r.seconds:.0f} s)" if r.seconds >= 1 else "")) \
                            .classes("text-body2")
                        ui.label(r.message).classes("text-caption text-grey-5")

    def enable(on: bool) -> None:
        for button in (check_button, thorough):
            button.set_enabled(on)

    def watch() -> None:
        """Eine Prüfung gibt es nur einmal: Jedes offene Fenster zeigt die laufende und sperrt die Knöpfe."""
        if not dialog.value:
            return
        busy = systemcheck.running()
        enable(not busy)
        if busy:
            fraction, step = systemcheck.current_step()
            progress.set_value(fraction)
            summary.set_text(step or "Prüfung läuft...")
        elif state["busy"]:
            progress.set_value(1.0)
            show(systemcheck.load())
        state["busy"] = busy

    async def check(deep: bool) -> None:
        if systemcheck.running():
            ui.notify("Die Prüfung läuft schon, das Ergebnis erscheint gleich hier.", type="info")
            return
        cancel.reset()
        enable(False)
        try:
            await run.io_bound(systemcheck.run_all, s.model_copy(deep=True), None, deep)
        except systemcheck.Busy:
            ui.notify("Die Prüfung läuft schon, das Ergebnis erscheint gleich hier.", type="info")
            return
        except cancel.Cancelled:
            ui.notify("Prüfung abgebrochen.", type="warning")
        else:
            progress.set_value(1.0)
        enable(not systemcheck.running())
        show(systemcheck.load())

    show(systemcheck.load())
    with dialog:
        ui.timer(0.3, watch)
    return dialog


async def save_report(s: SongSettings) -> None:
    try:
        path = await run.io_bound(fehlerbericht.save, None, s.model_copy(deep=True))
    except OSError as e:
        ui.notify(f"Fehlerbericht nicht gespeichert: {e}", type="negative")
        return
    ui.notify(f"Fehlerbericht gespeichert: {path}. Schick die ZIP-Datei mit, wenn du einen Fehler meldest.",
              type="positive", multi_line=True)
    media.open_folder(os.path.dirname(path))
    ui.download.file(path)


# ── Updates ────────────────────────────────────────────────────────────────────
def update_dialog(found: updates.Release | None = None) -> ui.dialog:
    with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full bg-grey-9"):
        _title("Update")
        info = ui.label(f"Deine Version: {VERSION}").classes("text-body2").mark("update-info")
        notes = ui.markdown("").classes("w-full")
        output = ui.log(max_lines=100).classes("w-full h-28 text-xs")
        output.set_visibility(False)
        lines = Lines(output)
        with ui.row().classes("w-full gap-2"):
            search = ui.button("Nach Update suchen", icon="refresh", on_click=lambda: look(True)) \
                .props("outline no-caps").mark("update-search")
            get = ui.button("Update holen", icon="system_update", on_click=lambda: fetch()) \
                .props("unelevated no-caps color=secondary").mark("update-get")
            ui.space()
            ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
    state = {"release": found}

    def show() -> None:
        release = state["release"]
        if release and updates.newer(release.version):
            info.set_text(f"Neue Version {release.version} (deine: {VERSION})")
            notes.set_content(release.notes[:3000])
        else:
            info.set_text(f"Deine Version {VERSION} ist die neueste." if release else
                          f"Deine Version: {VERSION}. Keine Verbindung zu GitHub oder noch kein Release.")
            notes.set_content("")
        get.set_visibility(bool(release and updates.newer(release.version)))

    async def look(force: bool) -> None:
        search.set_enabled(False)
        state["release"] = await run.io_bound(updates.latest, force)
        search.set_enabled(True)
        show()

    async def fetch() -> None:
        release = state["release"]
        output.set_visibility(True)
        get.set_enabled(False)
        if updates.is_git_checkout():
            ok = await run.io_bound(updates.pull, lines)
            ui.notify("Update geholt. Starte die App neu, dann richtet uv die neuen Bibliotheken ein." if ok else
                      "git pull ging nicht (Ausgabe oben).", type="positive" if ok else "warning", multi_line=True)
            get.set_enabled(True)
            return
        path = await run.io_bound(updates.download_setup, release, lines)
        if not path:
            get.set_enabled(True)
            return
        ui.notify("Das Update startet; die App schließt sich und kommt danach wieder.", type="positive")
        updates.run_setup(path)
        ui.timer(2.0, app.shutdown, once=True)

    show()
    if found is None:
        ui.timer(0.1, lambda: look(False), once=True)
    return dialog


def whats_new(text: str, version: str = VERSION) -> ui.dialog:
    with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full bg-grey-9"):
        _title(f"Neu in Version {version}")
        with ui.scroll_area().classes("w-full").style("height: 60vh"):
            ui.markdown(text or "Für diese Version ist nichts notiert.").mark("whats-new")
        ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
    return dialog


def markdown_page(title: str, path: str) -> ui.dialog:
    """Ein Text aus dem Programmordner (Anleitung, Credits) in einem Fenster."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = f"{os.path.basename(path)} fehlt im Programmordner."
    with ui.dialog() as dialog, ui.card().classes("w-[860px] max-w-full bg-grey-9"):
        _title(title)
        with ui.scroll_area().classes("w-full").style("height: 70vh"):
            ui.markdown(text).mark(f"page-{os.path.basename(path)}")
        ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
    return dialog


# ── Hilfe-Menü ─────────────────────────────────────────────────────────────────
def help_menu(s: SongSettings, pick: PickFn, on_change: Callable[[], None]) -> None:
    host = ui.element("div")        # die Fenster hängen hier, nicht im Menü, das sich beim Klick schließt

    def show(make: Callable[[], ui.dialog]) -> None:
        with host:
            make().open()

    def page(title: str, name: str) -> None:
        show(lambda: markdown_page(title, os.path.join(config.REPO_ROOT, name)))

    with ui.button(icon="help_outline").props("flat round").mark("help-menu").tooltip("Hilfe"):
        with ui.menu():
            ui.menu_item("Erste Schritte", lambda: page("Erste Schritte", "ANLEITUNG.md")).mark("menu-guide")
            ui.menu_item("Fehlerbehebung", lambda: page("Fehlerbehebung", "FEHLERBEHEBUNG.md")).mark("menu-help")
            ui.menu_item("Einrichten", lambda: show(lambda: setup_wizard(s, pick, on_change))).mark("menu-setup")
            ui.menu_item("System prüfen", lambda: show(lambda: system_check(s))).mark("menu-check")
            ui.menu_item("Fehlerbericht speichern", lambda: save_report(s)).mark("menu-report")
            ui.separator()
            ui.menu_item("Datenordner öffnen", lambda: media.open_folder(config.DATA_DIR))
            ui.menu_item("Protokoll öffnen", lambda: media.open_folder(config.LOG_DIR))
            ui.separator()
            ui.menu_item("Nach Update suchen", lambda: show(update_dialog)).mark("menu-update")
            ui.menu_item("Was ist neu", lambda: show(lambda: whats_new(updates.changes()))).mark("menu-news")
            ui.menu_item("Credits und Lizenzen", lambda: page("Credits und Lizenzen", "CREDITS.md")) \
                .mark("menu-credits")
            ui.separator()
            ui.label(f"Vloid Songs {VERSION}").classes("q-px-md q-py-xs text-caption text-grey-6")

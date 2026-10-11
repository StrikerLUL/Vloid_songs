# page.py – Die Hauptseite: Song erzeugen, anhören, Teile neu würfeln, Verlauf und Einstellungen
import logging
import os
import queue
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse
from nicegui import app, run, ui

import history
import pipeline
from gui import labels, media, panels
from gui.components import Karaoke, PianoRoll, WavePlayer, add_style
from settings import ChannelSettings, SongSettings, edit_key

log = logging.getLogger(__name__)

FILE_ROUTE = "/datei"
COUNTS = {1: "1 Fassung", 2: "2 Fassungen", 3: "3 Fassungen", 5: "5 Fassungen"}
# Ordner, aus denen der Player Dateien holen darf (Ausgabeordner, auch frühere)
SERVED_ROOTS: set = set()


@dataclass
class Job:
    """Fortschritt eines laufenden Songs; der Hintergrund-Thread schreibt, die Oberfläche liest."""
    fraction: float = 0.0
    message: str = ""
    started: float = 0.0
    step_start: float = 0.0
    steps: list = field(default_factory=list)       # [[Schritt, Sekunden]]
    running: bool = False

    def start(self) -> None:
        self.fraction, self.message, self.steps, self.running = 0.0, "", [], True
        self.started = self.step_start = time.monotonic()

    def report(self, fraction: float, message: str) -> None:
        now = time.monotonic()
        if self.steps:
            self.steps[-1][1] = now - self.step_start
        if message != self.message:
            self.steps.append([message, 0.0])
            self.step_start = now
        self.fraction, self.message = fraction, message

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started if self.started else 0.0


class Picker:
    """Datei- und Ordnerauswahl über das native Fenster; im Browser gibt es sie nicht."""

    @property
    def available(self) -> bool:
        return app.native.main_window is not None

    async def __call__(self, folder: bool = False, file_types: tuple = ()) -> Optional[str]:
        window = app.native.main_window
        if window is None:
            return None
        import webview
        kind = webview.FileDialog.FOLDER if folder else webview.FileDialog.OPEN
        chosen = await window.create_file_dialog(kind, file_types=tuple(file_types) + ("Alle Dateien (*.*)",))
        return chosen[0] if chosen else None


class LogQueue(logging.Handler):
    """Sammelt Protokollzeilen aus allen Threads; die Oberfläche holt sie im Takt des Timers ab."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: queue.Queue = queue.Queue()
        self.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.put(self.format(record))


def setup_routes() -> None:
    """Liefert Songs und Spuren an den Player, mit Range-Anfragen zum Springen."""
    if any(getattr(r, "path", "") == FILE_ROUTE for r in app.routes):
        return

    @app.get(FILE_ROUTE)
    def serve(pfad: str):
        path = os.path.realpath(pfad)
        allowed = any(os.path.commonpath([root, path]) == root for root in SERVED_ROOTS
                      if os.path.splitdrive(root)[0] == os.path.splitdrive(path)[0])
        if not allowed or not os.path.isfile(path):
            raise HTTPException(status_code=404)
        return FileResponse(path)


def file_url(path: str) -> str:
    """URL für den Player; ändert sich mit jeder neuen Datei, damit der Browser nichts Altes abspielt."""
    SERVED_ROOTS.add(os.path.realpath(os.path.dirname(path)))
    return f"{FILE_ROUTE}?pfad={quote(os.path.realpath(path))}&v={int(os.path.getmtime(path) * 1000)}"


def assign(target: SongSettings, source: SongSettings) -> None:
    """Übernimmt alle Werte in das bestehende Objekt, damit die Bindungen der Oberfläche erhalten bleiben."""
    for name in SongSettings.model_fields:
        if name != "channels":
            setattr(target, name, getattr(source, name))
    for ch, data in source.channels.items():
        for name in ChannelSettings.model_fields:
            setattr(target.channels[ch], name, getattr(data, name))


def build() -> None:
    """Baut die Seite. Jede Seite hat ihre eigenen Einstellungen und ihren eigenen Song."""
    settings = SongSettings.load()
    state = {"result": None, "saved": settings.model_dump(), "compare": {"A": None, "B": None}}
    job = Job()
    picker = Picker()
    logs = LogQueue()
    logging.getLogger().addHandler(logs)
    ui.context.client.on_delete(lambda: logging.getLogger().removeHandler(logs))
    setup_routes()

    ui.dark_mode(True)
    ui.colors(primary="#7e57c2", secondary="#ff4f8b", accent="#ff4f8b")
    add_style()
    ui.page_title("Vocaloid Song Generator")

    # ── Kopfzeile: erzeugen ───────────────────────────────────────────────────────
    with ui.header().classes("items-center gap-4 bg-grey-10 q-px-md"):
        ui.label("🎤 Vocaloid Song Generator").classes("text-h6")
        ui.space()
        count = ui.select(COUNTS, value=1).props("dense outlined dark").classes("w-36").mark("count") \
            .tooltip("Mehrere Fassungen landen im Verlauf; dort hörst du sie an und behältst die beste.")
        generate_button = ui.button("Song erzeugen", icon="auto_awesome", on_click=lambda: generate()) \
            .props("unelevated size=lg color=secondary no-caps").mark("generate")

    with ui.row().classes("w-full no-wrap items-start gap-4 q-pa-md"):
        # ── Links: anhören, neu würfeln, Fortschritt ───────────────────────────────
        with ui.column().classes("gap-4").style("flex: 3; min-width: 0"):
            with ui.card().classes("w-full bg-grey-9"):
                with ui.row().classes("w-full items-center no-wrap"):
                    song_label = ui.label("Noch kein Song. Klick oben auf „Song erzeugen“.") \
                        .classes("text-subtitle1").mark("song-label")
                    ui.space()
                    ui.switch("Mitlesen").bind_value(settings, "show_karaoke").props("dense").mark("switch-karaoke") \
                        .tooltip("Den Liedtext beim Abspielen unter dem Player zeigen")
                    ui.button("Seed festhalten", icon="lock", on_click=lambda: lock_seed()) \
                        .props("flat dense no-caps").mark("lock-seed") \
                        .tooltip("Der Song bleibt, auch wenn du Mix, Gesang oder Text änderst.")
                player = WavePlayer().classes("w-full").mark("player")
                lyrics_view = Karaoke().classes("w-full").mark("karaoke") \
                    .bind_visibility_from(settings, "show_karaoke")
                stem_row = ui.row().classes("gap-1 q-mt-sm")
                compare_row = ui.row().classes("items-center gap-1 q-mt-sm")
            with ui.card().classes("w-full bg-grey-9"):
                with ui.row().classes("w-full items-center gap-1"):
                    ui.label("Noten").classes("text-subtitle1 q-mr-md")
                    legend = ui.row().classes("gap-1")
                    ui.space()
                    ui.switch("Gesang bearbeiten", on_change=lambda e: roll.set_editable(e.value)) \
                        .props("dense").mark("edit-melody") \
                        .tooltip("Töne der Gesangsmelodie nach oben oder unten ziehen, oder anklicken und mit den "
                                 "Pfeiltasten verschieben (mit Umschalt um eine Oktave)")
                roll = PianoRoll().classes("w-full")
                with ui.row().classes("items-center gap-1") as edit_row:
                    edits_label = ui.label().classes("text-caption").mark("edits")
                    resing_button = ui.button("Neu singen", icon="record_voice_over", on_click=lambda: resing()) \
                        .props("unelevated dense no-caps color=secondary").mark("resing")
                    ui.button("Änderungen verwerfen", icon="undo", on_click=lambda: drop_edits()) \
                        .props("flat dense no-caps").mark("drop-edits")
            with ui.card().classes("w-full bg-grey-9"):
                with ui.row().classes("w-full items-center no-wrap"):
                    ui.label("Neu würfeln: nur dieser Teil wird neu, der Rest bleibt").classes("text-subtitle1")
                    ui.space()
                    where = ui.select({"": "im ganzen Song", **{k: f"nur {t}" for k, t in labels.SECTIONS.items()}},
                                      value="").props("dense outlined dark").classes("w-40").mark("reroll-where")
                with ui.row().classes("gap-1"):
                    reroll_buttons = {}
                    for part, text in labels.PARTS.items():
                        button = ui.button(text, icon="casino", on_click=lambda _, p=part: reroll(p)) \
                            .props("outline no-caps dense").mark(f"reroll-{part}")
                        if part in labels.PART_HINTS:
                            button.tooltip(labels.PART_HINTS[part])
                        reroll_buttons[part] = button
                with ui.row().classes("w-full items-center gap-1 q-mt-sm"):
                    hooks_button = ui.button("3 Refrain-Melodien zur Auswahl", icon="queue_music",
                                             on_click=lambda: hooks()).props("outline no-caps dense").mark("hooks") \
                        .tooltip("Drei neue Melodien für den Refrain, kurz zum Anhören; der Rest des Songs bleibt")
                    hook_row = ui.row().classes("items-center gap-1")
                with ui.row().classes("gap-2 q-mt-sm"):
                    zip_button = ui.button("Als ZIP für die DAW", icon="archive", on_click=lambda: export_zip()) \
                        .props("flat no-caps").mark("zip")
                    video_button = ui.button("Lyric-Video (MP4)", icon="movie", on_click=lambda: make_video()) \
                        .props("flat no-caps").mark("video") \
                        .tooltip("Der Song mit dem Text zum Mitlesen als Video, z. B. für YouTube (braucht ffmpeg)")
                    ui.button("Ausgabeordner öffnen", icon="folder",
                              on_click=lambda: media.open_folder(settings.output_dir())).props("flat no-caps")
            with ui.card().classes("w-full bg-grey-9"):
                progress = ui.linear_progress(value=0, show_value=False).props("rounded color=secondary")
                step_label = ui.label("Bereit").classes("text-caption").mark("step")
                steps_box = ui.column().classes("gap-0")
                with ui.expansion("Protokoll", icon="article").classes("w-full"):
                    log_view = ui.log(max_lines=500).classes("w-full h-64 text-xs")

        # ── Rechts: Einstellungen und Verlauf ─────────────────────────────────────
        with ui.card().classes("bg-grey-9").style("flex: 2; min-width: 440px"):
            with ui.tabs().props("dense no-caps align=left").classes("w-full") as tabs:
                for name, icon in (("Song", "music_note"), ("Text", "notes"), ("Band", "piano"),
                                   ("Gesang", "mic"), ("Mix", "tune"), ("Verlauf", "history"),
                                   ("Pfade", "folder")):
                    ui.tab(name, icon=icon).mark(f"tab-{name}")
            with ui.tab_panels(tabs, value="Song").classes("w-full bg-transparent") as panel_box:
                with ui.tab_panel("Song"):
                    panels.song_panel(settings, picker, lambda new: assign(settings, new))
                with ui.tab_panel("Text"):
                    panels.text_panel(settings)
                with ui.tab_panel("Band"):
                    panels.band_panel(settings)
                with ui.tab_panel("Gesang"):
                    singer_select, duet_select = panels.voice_panel(settings, _singers(settings))
                with ui.tab_panel("Mix"):
                    panels.mix_panel(settings)
                with ui.tab_panel("Verlauf"):
                    history_box = ui.column().classes("w-full")
                with ui.tab_panel("Pfade"):
                    paths_status = ui.column().classes("gap-0 q-mb-md")
                    panels.paths_panel(settings, picker, lambda: show_status())

    # ── Song erzeugen ──────────────────────────────────────────────────────────────
    async def reroll(part: str) -> None:
        kind = where.value
        result = state["result"]
        if kind and result is not None and kind not in result.settings.active_sections:
            ui.notify(f"Im Song gibt es keine Sektion {labels.SECTIONS.get(kind, kind)}.", type="warning")
            return
        await generate(f"{part}:{kind}" if kind else part)

    async def generate(part: Optional[str] = None, n: Optional[int] = None, same_song: bool = False) -> None:
        if job.running:
            return
        current = settings.model_copy(deep=True)
        result = state["result"]
        if part is not None or same_song:
            if result is None:
                ui.notify("Erst einen Song erzeugen, dann einzelne Teile neu würfeln.", type="warning")
                return
            current = current.with_updates(seed=result.seed, variations=result.settings.variations)
        elif current.seed is None:
            current = current.with_updates(variations={}, melody_edits={})
        save_settings()
        job.start()
        set_busy(True)
        n = n or int(count.value or 1)
        try:
            if n > 1 or part:
                results = await run.io_bound(pipeline.generate_variants, current, n, (part,) if part else (),
                                             job.report)
            else:
                results = [await run.io_bound(pipeline.generate_song, current, job.report)]
        except Exception as e:  # noqa: BLE001 – jeder Fehler gehört ins Protokoll und auf den Schirm
            log.error("Song fehlgeschlagen: %s", e)
            ui.notify(f"Fehler: {e}", type="negative", multi_line=True)
            results = None
        finally:
            job.running = False
            set_busy(False)
        results = [r for r in results or [] if r is not None]   # None: abgebrochen, weil die App schließt
        if not results:
            return
        state["result"] = results[-1]
        settings.variations = results[-1].settings.variations
        settings.melody_edits = results[-1].settings.melody_edits
        await show_result(results[-1])
        show_history()
        if len(results) > 1:
            panel_box.set_value("Verlauf")
            ui.notify(f"{len(results)} Fassungen im Verlauf: anhören und die beste behalten", type="positive")

    async def hooks() -> None:
        if job.running:
            return
        current = settings.model_copy(deep=True)
        result = state["result"]
        if result is not None:
            current = current.with_updates(seed=result.seed, variations=result.settings.variations)
        job.start()
        set_busy(True)
        try:
            choices = await run.io_bound(pipeline.hook_choices, current, 3, job.report)
        except ValueError as e:
            ui.notify(str(e), type="warning")
            choices = None
        except Exception as e:  # noqa: BLE001 – jeder Fehler gehört ins Protokoll und auf den Schirm
            log.error("Refrain-Melodien fehlgeschlagen: %s", e)
            ui.notify(f"Fehler: {e}", type="negative", multi_line=True)
            choices = None
        finally:
            job.running = False
            set_busy(False)
        if not choices:
            return
        hook_row.clear()
        with hook_row:
            for choice in choices:
                with ui.button_group().props("outline"):
                    ui.button(f"Refrain {choice.number}", icon="play_arrow",
                              on_click=lambda _, c=choice: play(f"Refrain {c.number}", c.preview)) \
                        .props("outline no-caps dense").mark(f"hook-play-{choice.number}")
                    ui.button("nehmen", icon="check", on_click=lambda _, c=choice: take(c)) \
                        .props("outline no-caps dense color=secondary").mark(f"hook-take-{choice.number}")
        await play("Refrain 1", choices[0].preview)

    async def take(choice) -> None:
        """Den ganzen Song mit dieser Refrain-Melodie erzeugen."""
        settings.seed = choice.settings.seed
        settings.variations = choice.settings.variations
        hook_row.clear()
        await generate(n=1)

    # ── Gesang bearbeiten ─────────────────────────────────────────────────────────
    def on_edit(e) -> None:
        result = state["result"]
        if result is None:
            return
        start, pitch = float(e.args["start"]), int(e.args["pitch"])
        settings.melody_edits = {**settings.melody_edits, edit_key(start * result.settings.bpm / 60): pitch}
        roll.move(start, pitch)
        show_edits()

    def show_edits() -> None:
        n = len(settings.melody_edits)
        edits_label.set_text(_edits(n))
        edit_row.set_visibility(n > 0)
        resing_button.set_enabled(n > 0 and not job.running)

    async def resing() -> None:
        """Derselbe Song mit den geänderten Tönen; unveränderte Spuren werden nicht neu gerendert."""
        await generate(n=1, same_song=True)
        show_edits()

    async def drop_edits() -> None:
        settings.melody_edits = {}
        show_edits()
        result = state["result"]
        if result is not None:
            data = await run.io_bound(media.piano_roll, result)
            if data is not None:
                roll.show(data)

    roll.on("edit", on_edit)

    # ── Lyric-Video und Vergleich ─────────────────────────────────────────────────
    async def make_video() -> None:
        result = state["result"]
        if result is None or job.running:
            ui.notify("Erst einen Song erzeugen.", type="warning")
            return
        job.start()
        job.report(0.1, "Baue Lyric-Video...")
        set_busy(True)
        try:
            path = await run.io_bound(pipeline.lyric_video, result)
        except RuntimeError as e:
            ui.notify(str(e), type="warning", multi_line=True)
            path = None
        finally:
            job.report(1.0, "Fertig")
            job.running = False
            set_busy(False)
        if path:
            ui.notify(f"Lyric-Video gespeichert: {path}", type="positive", multi_line=True)
            ui.download.file(path)

    def choose(slot: str, entry) -> None:
        state["compare"][slot] = entry
        show_compare()

    def show_compare() -> None:
        compare_row.clear()
        chosen = state["compare"]
        if not any(chosen.values()):
            return
        with compare_row:
            ui.label("Vergleich:").classes("text-caption q-mr-xs")
            for slot in ("A", "B"):
                entry = chosen[slot]
                if entry is None:
                    ui.label(f"{slot}: im Verlauf wählen").classes("text-caption text-grey-6")
                    continue
                ui.button(f"{slot}: {entry.created:%H:%M} {entry.settings.style}",
                          on_click=lambda _, sl=slot, e=entry: play(f"{sl} · {describe(e.settings)}", e.audio)) \
                    .props("outline dense no-caps").mark(f"compare-{slot}") \
                    .tooltip("Wechselt an derselben Stelle im Song")
            ui.button(icon="close", on_click=lambda: (state["compare"].update(A=None, B=None), show_compare())) \
                .props("flat round dense").mark("compare-close")

    async def show_result(result) -> None:
        song_label.set_text(describe(result.settings))
        lyrics_view.show(await run.io_bound(media.lyrics, result) or [])
        found = media.stems(result)
        stem_row.clear()
        with stem_row:
            if found:
                ui.label("Anhören:").classes("text-caption self-center q-mr-xs")
            for name, path in found.items():
                ui.button(name, on_click=lambda _, n=name, p=path: play(n, p)) \
                    .props("dense no-caps " + ("unelevated" if name == "Mix" else "outline")) \
                    .mark(f"stem-{name}")
        if found:
            await play(*next(iter(found.items())))
        data = await run.io_bound(media.piano_roll, result)
        if data is None:        # die App wird gerade beendet
            return
        roll.show(data)
        show_edits()
        legend.clear()
        with legend:
            for i, track in enumerate(data["tracks"]):
                ui.chip(track["name"], color=track["color"], text_color="black",
                        on_click=lambda e, i=i: toggle_track(e.sender, i)).props("dense clickable")

    async def play(name: str, path: str) -> None:
        if not os.path.exists(path):
            ui.notify("Die Datei gibt es nicht mehr.", type="warning")
            return
        loaded = await run.io_bound(media.peaks, path)
        if loaded is None:      # die App wird gerade beendet
            return
        player.show(file_url(path), name, *loaded)

    def toggle_track(chip, index: int) -> None:
        hidden = set(roll.hidden)
        if index in hidden:
            hidden.discard(index)
        else:
            hidden.add(index)
        chip.classes(toggle="opacity-30")
        roll.set_hidden(list(hidden))

    def lock_seed() -> None:
        result = state["result"]
        if result is None:
            ui.notify("Erst einen Song erzeugen.", type="warning")
            return
        settings.seed = result.seed
        settings.variations = result.settings.variations
        ui.notify(f"Seed {result.seed} festgehalten: „Song erzeugen“ macht jetzt diesen Song mit deinen Änderungen")

    async def export_zip() -> None:
        result = state["result"]
        if result is None:
            ui.notify("Noch kein Song zum Exportieren.", type="warning")
            return
        from exporter import exportiere_projekt
        name = f"song_{result.settings.style.replace(' ', '-')}_{result.seed}.zip"
        target = os.path.join(result.output_dir, "export", name)
        path = await run.io_bound(exportiere_projekt, result, target)
        if path is None:        # die App wird gerade beendet
            return
        ui.notify(f"ZIP gespeichert: {path}", type="positive", multi_line=True)
        ui.download.file(path)

    # ── Fortschritt, Protokoll, Speichern ──────────────────────────────────────────
    def set_busy(busy: bool) -> None:
        for button in (generate_button, zip_button, video_button, hooks_button, *reroll_buttons.values()):
            button.set_enabled(not busy)
        resing_button.set_enabled(not busy and bool(settings.melody_edits))
        show_steps()

    def show_steps() -> None:
        progress.set_value(job.fraction)
        if job.running:
            step_label.set_text(f"{job.message} ({job.elapsed:.0f} s)")
        elif job.steps:
            step_label.set_text(f"Fertig nach {job.elapsed:.0f} s")
        steps_box.clear()
        with steps_box:
            for message, seconds in job.steps[-8:]:
                ui.label(f"{message}  {seconds:.1f} s").classes("text-caption text-grey-5")

    def tick() -> None:
        while not logs.lines.empty():
            log_view.push(logs.lines.get_nowait())
        if job.running:
            show_steps()
        save_settings()

    def save_settings() -> None:
        current = settings.model_dump()
        if current == state["saved"]:
            return
        try:
            settings.save()
            state["saved"] = current
        except OSError as e:
            log.warning("Einstellungen nicht gespeichert: %s", e)

    def show_status() -> None:
        import sound_library
        from renderer import engine_name
        from vocal_synthesizer import neutrino_info
        paths_status.clear()
        with paths_status:
            ui.label(neutrino_info(settings.neutrino_dir())).classes("text-caption").mark("neutrino-info")
            ui.label(f"Instrumente mit {engine_name()}").classes("text-caption")
            ui.label(sound_library.status()).classes("text-caption").mark("sound-library")
        singer_select.set_options(sorted(set(_singers(settings)) | {settings.singer}), value=settings.singer)
        duet_select.set_options(panels.duet_options(_singers(settings), settings), value=settings.duet_singer)
        show_history()

    # ── Verlauf ──────────────────────────────────────────────────────────────────────
    def show_history() -> None:
        entries = history.entries(settings.output_dir())
        history_box.clear()
        with history_box:
            if not entries:
                ui.label("Noch keine Songs im Verlauf.").classes("text-grey-5")
                return
            panels.hint("Die 30 neuesten Songs bleiben, mit Stern markierte immer. "
                        "↺ übernimmt die Einstellungen samt Seed.")
            with ui.scroll_area().classes("w-full").style("height: 60vh"):
                for nr, entry in enumerate(entries, 1):
                    with ui.row().classes("w-full items-center no-wrap gap-1"):
                        ui.button(icon="play_arrow", on_click=lambda _, e=entry: play(describe(e.settings), e.audio)) \
                            .props("flat round dense").mark("history-play")
                        ui.label(f"{entry.created:%d.%m. %H:%M}  {describe(entry.settings)}") \
                            .classes("col text-body2")
                        for slot in ("A", "B"):
                            ui.button(slot, on_click=lambda _, sl=slot, e=entry: choose(sl, e)) \
                                .props("flat dense round size=sm").mark(f"history-{slot}-{nr}") \
                                .tooltip(f"Als {slot} vergleichen: im Player zwischen A und B wechseln")
                        ui.button(icon="star" if entry.favorite else "star_border",
                                  on_click=lambda _, e=entry: favorite(e)).props("flat round dense color=amber") \
                            .mark("history-favorite")
                        ui.button(icon="settings_backup_restore", on_click=lambda _, e=entry: restore(e)) \
                            .props("flat round dense").tooltip("Einstellungen dieses Songs übernehmen") \
                            .mark("history-restore")
                        ui.button(icon="delete", on_click=lambda _, e=entry: remove(e)) \
                            .props("flat round dense color=grey").mark("history-delete")

    def favorite(entry) -> None:
        history.set_favorite(entry, not entry.favorite)
        show_history()

    def restore(entry) -> None:
        assign(settings, entry.restore(settings))
        ui.notify("Einstellungen samt Seed übernommen: „Song erzeugen“ macht diesen Song noch einmal",
                  type="positive")

    def remove(entry) -> None:
        history.delete(entry)
        show_history()

    ui.timer(0.3, tick)
    show_status()
    show_edits()


def describe(s: SongSettings) -> str:
    rerolled = ", ".join(f"{_part_name(p)} {n}×" for p, n in sorted(s.variations.items()))
    return (f"{s.style} · {s.bpm} BPM · {s.key} {labels.SCALES.get(s.scale, s.scale)} · Seed {s.seed}"
            + (f" · neu gewürfelt: {rerolled}" if rerolled else "")
            + (f" · {_edits(len(s.melody_edits))}" if s.melody_edits else ""))


def _edits(n: int) -> str:
    return "1 Ton geändert" if n == 1 else f"{n} Töne geändert"


def _part_name(key: str) -> str:
    """Name zum Anzeigen: melody:Chorus → Melodie (Refrain)."""
    part, _, kind = key.partition(":")
    name = labels.PARTS.get(part, part)
    return f"{name} ({labels.SECTIONS.get(kind, kind)})" if kind else name


def _singers(settings: SongSettings) -> list:
    from vocal_synthesizer import installed_singers
    try:
        return installed_singers(settings.neutrino_dir())
    except Exception:  # noqa: BLE001
        return []

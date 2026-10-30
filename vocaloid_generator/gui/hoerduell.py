# hoerduell.py – Der Dialog zum Hör-Duell (1.6.0): zwei Fassungen blind vergleichen, die Gewinner übernehmen
#
# Während du ein Duell hörst, entsteht im Hintergrund schon das nächste. Wie die Fassungen entstehen und was die
# Entscheidungen ändern, steht in hoer_duell.py.
import asyncio
import logging
import os
from typing import Callable

from nicegui import run, ui

import cancel
import hoer_duell
import pipeline

log = logging.getLogger(__name__)

COUNTS = {5: "5 Duelle (etwa 5 Minuten)", 10: "10 Duelle", 20: "20 Duelle", 0: "alle im Bereich"}
CHOICE_TEXT = {"mit": "klingt mit besser", "ohne": "klingt ohne besser", "gleich": "kein Unterschied"}


def open_duel(host, settings, current: Callable, job, set_busy: Callable, file_url: Callable,
              on_apply: Callable) -> None:
    """current(): die Einstellungen des Songs, der gerade da ist (mit seinem Seed); on_apply(neue Einstellungen)."""
    state = {"stop": False, "choice": None, "entries": []}

    with host, ui.dialog().props("persistent") as dialog, ui.card().classes("w-[34rem]"):
        ui.label("Hör-Duell").classes("text-h6")
        body = ui.column().classes("w-full gap-2")

    def setup() -> None:
        body.clear()
        with body:
            ui.label("Du hörst denselben Refrain zweimal, einmal mit und einmal ohne eine Funktion. Welche A und welche "
                     "B ist, wird ausgelost, beide sind gleich laut. Am Ende übernimmt die App, was dir besser "
                     "gefällt.").classes("text-body2")
            ui.label(hoer_duell.summary()).classes("text-caption text-grey-5").mark("duel-summary")
            groups = ui.select(hoer_duell.GROUPS, value=["stimme", "klang"], multiple=True, label="Bereiche") \
                .props("use-chips").classes("w-full").mark("duel-groups")
            count = ui.select(COUNTS, value=10, label="Wie viele").classes("w-full").mark("duel-count")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                ui.button("Starten", icon="hearing", on_click=lambda: start(list(groups.value or []),
                                                                           int(count.value or 0))) \
                    .props("unelevated no-caps color=secondary").mark("duel-start")

    async def start(groups: list, count: int) -> None:
        if job.running:
            ui.notify("Es läuft schon etwas.", type="warning")
            return
        if job.blocked():
            return
        base = current()
        if base.seed is None:
            base = base.with_updates(seed=pipeline.new_seed())
        candidates = hoer_duell.plan(base, groups or None, count)
        if not candidates:
            ui.notify("In diesen Bereichen gibt es nichts zu vergleichen.", type="warning")
            return
        folder = os.path.join(base.output_dir(), hoer_duell.FOLDER)
        os.makedirs(folder, exist_ok=True)
        state.update(stop=False, entries=[])
        queue: asyncio.Queue = asyncio.Queue()
        job.start()
        set_busy(True)

        async def produce() -> None:
            for number, candidate in enumerate(candidates, 1):
                if state["stop"]:
                    break
                try:
                    duel = await run.io_bound(hoer_duell.prepare, base, candidate, folder, base.seed, number,
                                              job.report)
                except cancel.Cancelled:
                    break
                except Exception as e:  # noqa: BLE001 – ein Duell, das nicht entsteht, fällt aus
                    log.error("Hör-Duell %s fehlgeschlagen: %s", candidate.label, e)
                    continue
                await queue.put(duel)
            await queue.put(None)

        producer = asyncio.create_task(produce())
        try:
            number = 0
            while True:
                waiting(number + 1, len(candidates))
                duel = await queue.get()
                if duel is None:
                    break
                number += 1
                if duel.identical:
                    state["entries"].append(hoer_duell.record(duel, "gleich", base))
                    continue
                choice = await ask(duel, number, len(candidates))
                if choice is None:
                    break
                state["entries"].append(hoer_duell.record(duel, choice, base))
        finally:
            state["stop"] = True
            cancel.request()
            await asyncio.gather(producer, return_exceptions=True)
            cancel.reset()
            job.running = False
            set_busy(False)
        finish(base)

    def waiting(number: int, total: int) -> None:
        body.clear()
        with body:
            ui.label(f"Duell {number} von {total} entsteht …").classes("text-subtitle1").mark("duel-waiting")
            ui.label("Beim ersten singt NEUTRINO den Refrain; danach geht es meist schneller.") \
                .classes("text-caption text-grey-5")
            ui.spinner(size="lg")
            ui.button("Beenden", on_click=stop).props("flat no-caps").mark("duel-stop")

    def stop() -> None:
        state["stop"] = True
        cancel.request()
        future = state.get("choice")
        if future is not None and not future.done():
            future.set_result(None)

    async def ask(duel, number: int, total: int):
        future = asyncio.get_running_loop().create_future()
        state["choice"] = future
        c = duel.candidate
        body.clear()
        with body:
            ui.label(f"Duell {number} von {total}: {c.label}").classes("text-subtitle1").mark("duel-title")
            if c.hint:
                ui.label(f"Achte auf: {c.hint}").classes("text-caption text-grey-5")
            for side, path in (("A", duel.a), ("B", duel.b)):
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    ui.label(side).classes("text-h6 w-6")
                    ui.audio(file_url(path)).classes("col").mark(f"duel-audio-{side}")
            with ui.row().classes("w-full justify-between q-mt-sm"):
                for key, text in hoer_duell.CHOICES.items():
                    ui.button(text, on_click=lambda _, k=key: future.done() or future.set_result(k)) \
                        .props("unelevated no-caps color=secondary" if key != "gleich" else "outline no-caps") \
                        .mark(f"duel-{key}")
            ui.button("Beenden", on_click=stop).props("flat no-caps").mark("duel-stop")
        return await future

    def finish(base) -> None:
        entries = [e for e in state["entries"]]
        changes = hoer_duell.changes(settings)
        body.clear()
        with body:
            ui.label("Ergebnis").classes("text-subtitle1").mark("duel-result")
            if not entries:
                ui.label("Kein Duell entschieden.").classes("text-body2")
            for e in entries:
                text = "in diesem Song ohne Wirkung, übersprungen" if e.get("auto") else CHOICE_TEXT[e["choice"]]
                ui.label(f"{e['label']}: {text}").classes("text-body2")
            if changes:
                ui.label(f"Übernehmen ändert {len(changes)} Einstellungen. Was keinen Unterschied machte, geht aus "
                         "und lässt sich ausblenden (Tab Pfade, „Aufgeräumt“).").classes("text-caption text-grey-5")
            with ui.row().classes("w-full justify-end"):
                ui.button("Schließen", on_click=dialog.close).props("flat no-caps").mark("duel-close")
                if changes:
                    ui.button("Übernehmen", icon="check", on_click=lambda: take()) \
                        .props("unelevated no-caps color=secondary").mark("duel-apply")

    def take() -> None:
        on_apply(hoer_duell.apply(settings))
        ui.notify("Die Gewinner der Duelle sind jetzt deine Einstellungen.", type="positive")
        dialog.close()

    setup()
    dialog.open()

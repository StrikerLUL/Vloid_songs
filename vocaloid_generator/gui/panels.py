# panels.py – Die Einstellungen der App, direkt an SongSettings gebunden
import logging
from collections.abc import Awaitable, Callable

from nicegui import ui

import vorlagen
from gui import labels
from lyrics import _HEADER, syllables
from settings import KEYS, STYLE_OPTIONS, SongSettings
from styles import STYLES

log = logging.getLogger(__name__)

PickFn = Callable[..., Awaitable[str | None]]


def section_title(text: str) -> None:
    ui.label(text).classes("text-subtitle1 text-weight-medium q-mt-sm")


def hint(text: str) -> None:
    ui.label(text).classes("text-caption text-grey-5")


# ── Song ────────────────────────────────────────────────────────────────────────
def song_panel(s: SongSettings, pick: PickFn, apply_template: Callable[[SongSettings], None]) -> None:
    def typical() -> None:
        from preset_manager import preset_settings
        new = preset_settings(s.style, s)
        if new is None:
            ui.notify(f"Für {s.style} gibt es keine typischen Werte.", type="warning")
            return
        apply_template(new)
        ui.notify(f"Typische Werte für {s.style}: {new.bpm} BPM, {new.key} {labels.SCALES.get(new.scale)}")

    with ui.grid(columns=2).classes("w-full gap-x-4"):
        with ui.row().classes("items-end no-wrap"):
            ui.select(list(STYLES), label="Stil").bind_value(s, "style").classes("col").mark("style")
            ui.button(icon="auto_fix_high", on_click=typical).props("flat round dense").mark("typical") \
                .tooltip("Typische Werte für diesen Stil: Tempo, Tonart, Ablauf und Lautstärken")
        ui.select(list(KEYS), label="Tonart").bind_value(s, "key")
        ui.select(labels.SCALES, label="Tonleiter").bind_value(s, "scale")
        ui.number("Tempo (BPM)", min=40, max=260, step=1, precision=0) \
            .bind_value(s, "bpm", forward=lambda v: int(v or 160)).mark("bpm")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Swing").classes("w-24")
        ui.slider(min=0, max=0.5, step=0.01).bind_value(s, "swing").props("label").classes("col")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Humanize").classes("w-24")
        ui.slider(min=0, max=0.1, step=0.005).bind_value(s, "jitter").props("label").classes("col")

    section_title("Seed")
    ui.number("Seed", min=0, step=1, precision=0, placeholder="leer = jedes Mal ein neuer Song") \
        .bind_value(s, "seed", forward=lambda v: None if v is None else int(v)).props("clearable").mark("seed")
    hint("Mit festem Seed bleibt der Song gleich, auch wenn du Mix, Gesang oder Text änderst. "
         "Leer lassen für jedes Mal einen neuen Song.")

    section_title("Ablauf")
    structure_editor(s)

    section_title("Vorbild-Song fürs Mastering")
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input(placeholder="kein Vorbild: normales Mastering").bind_value(s, "reference_track") \
            .classes("col").props("clearable dense").mark("reference")
        pick_button(pick, s, "reference_track", file_types=("Audio (*.wav;*.mp3;*.flac;*.ogg)",))
    hint("Lautheit, Klangfarbe und Stereobreite werden an diesen Song angeglichen (matchering).")

    section_title("Vorlagen")
    templates_editor(s, apply_template)


def structure_editor(s: SongSettings) -> None:
    @ui.refreshable
    def chips() -> None:
        with ui.row().classes("gap-1"):
            for i, name in enumerate(s.active_sections):
                ui.chip(labels.SECTIONS.get(name, name), removable=True, color="deep-purple-4",
                        text_color="white", on_value_change=lambda _, i=i: remove(i)).props("dense") \
                    .mark(f"section-{i}")
        with ui.row().classes("gap-1 items-center"):
            ui.label("Anhängen:").classes("text-caption")
            for name, text in labels.SECTIONS.items():
                ui.button(text, on_click=lambda _, n=name: add(n)).props("flat dense no-caps")
        with ui.row().classes("gap-1 items-center"):
            ui.label("Vorlage:").classes("text-caption")
            for text, parts in labels.STRUCTURES.items():
                ui.button(text, on_click=lambda _, p=parts: set_all(p)).props("outline dense no-caps")

    def remove(i: int) -> None:
        if len(s.active_sections) > 1:
            s.active_sections = s.active_sections[:i] + s.active_sections[i + 1:]
        chips.refresh()

    def add(name: str) -> None:
        s.active_sections = s.active_sections + [name]
        chips.refresh()

    def set_all(parts: list) -> None:
        s.active_sections = list(parts)
        chips.refresh()

    chips()


def templates_editor(s: SongSettings, apply_template: Callable[[SongSettings], None]) -> None:
    with ui.row().classes("w-full items-center no-wrap gap-2"):
        choice = ui.select(vorlagen.names(), label="Vorlage").classes("col").mark("template")
        name = ui.input("Name für neue Vorlage").classes("col").mark("template-name")

    def load() -> None:
        if not choice.value:
            return
        apply_template(vorlagen.apply(choice.value, s))
        ui.notify(f"Vorlage „{choice.value}“ geladen")

    def save() -> None:
        try:
            saved = vorlagen.save(name.value, s)
        except (ValueError, OSError) as e:
            ui.notify(str(e), type="negative")
            return
        choice.set_options(vorlagen.names(), value=saved)
        name.value = ""
        ui.notify(f"Vorlage „{saved}“ gespeichert", type="positive")

    def delete() -> None:
        if choice.value:
            vorlagen.delete(choice.value)
            choice.set_options(vorlagen.names(), value=None)

    with ui.row().classes("gap-2"):
        ui.button("Laden", icon="file_open", on_click=load).props("flat no-caps")
        ui.button("Speichern", icon="save", on_click=save).props("flat no-caps").mark("save-template")
        ui.button("Löschen", icon="delete", on_click=delete).props("flat no-caps color=grey")
    hint("Eine Vorlage merkt sich Stil, Tempo, Tonart, Ablauf, Band, Gesang und Mix, aber nicht den Text.")


# ── Text ────────────────────────────────────────────────────────────────────────
def text_panel(s: SongSettings) -> None:
    hint("Eine Überschrift wie [Verse], [Pre-Chorus], [Chorus] oder [Bridge] pro Abschnitt. Japanisch darf ganz "
         "normal geschrieben werden, auch mit Kanji; 君[きみ] gibt eine Lesung von Hand vor.")

    @ui.refreshable
    def preview() -> None:
        rows, count = [], 0
        for raw in (s.lyrics or "").splitlines():
            line = raw.strip()
            header = _HEADER.match(line)
            if header:
                rows.append(("header", header.group(1)))
            elif line:
                sylls = syllables(line)
                count += len(sylls)
                rows.append(("line", " ".join(sylls)))
        ui.label(f"So wird gesungen: {count} Silben").classes("text-subtitle2").mark("syllables")
        with ui.scroll_area().classes("w-full h-96"):
            for kind, text in rows:
                if kind == "header":
                    ui.label(f"[{text}]").classes("text-caption text-deep-purple-3 q-mt-sm")
                else:
                    ui.label(text).classes("text-body2")

    with ui.row().classes("w-full no-wrap gap-4 items-start"):
        ui.textarea().bind_value(s, "lyrics").props("outlined autogrow input-style=min-height:360px") \
            .classes("col").mark("lyrics").on_value_change(lambda: preview.refresh())
        with ui.column().classes("col"):
            preview()


# ── Band ────────────────────────────────────────────────────────────────────────
BAND = ("melody", "piano", "bass", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "perc",
        "drums", "fx", "vocals")


def band_panel(s: SongSettings) -> None:
    hint("Spielweise „wie der Stil“ nimmt die des gewählten Stils. Lautstärke 0,8 ist der Normalwert.")
    with ui.grid(columns="110px 1fr 70px 1fr 1fr 90px").classes("w-full items-center gap-x-3 gap-y-1"):
        for text in ("Spur", "Spielweise", "an", "Lautstärke", "Panorama", "Mute / Solo"):
            ui.label(text).classes("text-caption text-grey-5")
        for ch in BAND:
            channel = s.channels[ch]
            ui.label(labels.CHANNELS[ch])
            options = STYLE_OPTIONS.get(ch, ())
            if len(options) > 1:
                ui.select({o: labels.PLAYING.get(o, o) for o in options}).bind_value(channel, "style") \
                    .props("dense options-dense").mark(f"style-{ch}")
            else:
                ui.label("—").classes("text-grey-6")
            ui.switch().bind_value(channel, "enabled").props("dense").mark(f"enabled-{ch}")
            ui.slider(min=0, max=1.5, step=0.05).bind_value(channel, "volume").props("label dense")
            ui.slider(min=-1, max=1, step=0.05).bind_value(channel, "pan").props("label dense")
            with ui.row().classes("gap-0 no-wrap"):
                ui.checkbox("M").bind_value(channel, "mute").props("dense")
                ui.checkbox("S").bind_value(channel, "solo").props("dense")
    with ui.row().classes("items-center gap-4 q-mt-md"):
        ui.label("Master").classes("w-24")
        ui.slider(min=0, max=1.5, step=0.05).bind_value(s.channels["master"], "volume").props("label") \
            .classes("w-64")


# ── Gesang ──────────────────────────────────────────────────────────────────────
def voice_panel(s: SongSettings, singers: list) -> ui.select:
    ui.select(labels.ENGINES, label="Gesang mit").bind_value(s, "vocal_engine").classes("w-full")
    options = sorted(set(singers) | {s.singer})
    singer = ui.select(options, label="Stimme").bind_value(s, "singer").classes("w-full").mark("singer")
    hint("Die Stimmen aus dem Ordner model von NEUTRINO. Die Melodie passt sich ihrem Tonumfang an.")
    ui.switch("Zweite Stimme im Refrain").bind_value(s, "harmonies")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("StyleShift").classes("w-28")
        ui.slider(min=-6, max=6, step=1).bind_value(s, "style_shift").props("label markers").classes("col")
    hint("Plus = heller und jünger, minus = dunkler. Braucht NEUTRINO mit StyleShift.")
    section_title("Vorschau-Stimme (wenn NEUTRINO fehlt)")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Hauchigkeit").classes("w-28")
        ui.slider(min=0, max=0.2, step=0.002).bind_value(s, "breathiness").props("label").classes("col")
    ui.switch("Schimmer").bind_value(s, "shimmer")
    return singer


# ── Mix ─────────────────────────────────────────────────────────────────────────
def mix_panel(s: SongSettings) -> None:
    for text, attr, lo, hi, step in (
        ("Kompressor: Schwelle (dB)", "compressor_threshold", -60, 0, 0.5),
        ("Kompressor: Verhältnis", "compressor_ratio", 1, 20, 0.5),
        ("Limiter: Obergrenze (dB)", "limiter_threshold", -20, 0, 0.1),
    ):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-56")
            ui.slider(min=lo, max=hi, step=step).bind_value(s, attr).props("label").classes("col")
    hint("Ist ein Vorbild-Song gewählt, mastert die App nach ihm; sonst auf -12 LUFS mit diesem Limiter.")


# ── Pfade ───────────────────────────────────────────────────────────────────────
def paths_panel(s: SongSettings, pick: PickFn, status: Callable[[], None]) -> None:
    import config
    for text, attr, folder, types, default in (
        ("NEUTRINO-Ordner", "neutrino_pfad", True, (), config.NEUTRINO_PFAD),
        ("SoundFont", "soundfont_pfad", False, ("SoundFont (*.sf2;*.sf3)",), config.SOUNDFONT_PFAD),
        ("Ausgabeordner", "output_ordner", True, (), config.OUTPUT_ORDNER),
        ("VST3-Instrument für Synth und Lead (optional)", "vst_path", False, ("VST3 (*.vst3)",), ""),
    ):
        with ui.row().classes("w-full items-center no-wrap"):
            ui.input(text, placeholder=f"leer = {default}" if default else "leer = keins") \
                .bind_value(s, attr).classes("col").props("dense stack-label").mark(f"path-{attr}") \
                .on("blur", lambda: status())
            pick_button(pick, s, attr, folder=folder, file_types=types, then=status)


def pick_button(pick: PickFn, s: SongSettings, attr: str, folder: bool = False, file_types: tuple = (),
                then: Callable[[], None] = None) -> None:
    async def choose() -> None:
        path = await pick(folder=folder, file_types=file_types)
        if path:
            setattr(s, attr, path)
            if then:
                then()
    button = ui.button("Wählen", icon="folder_open", on_click=choose).props("flat dense no-caps")
    button.set_visibility(pick.available)

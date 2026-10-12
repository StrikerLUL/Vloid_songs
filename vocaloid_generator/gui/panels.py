# panels.py – Die Einstellungen der App, direkt an SongSettings gebunden
import logging
import os
from collections.abc import Awaitable, Callable

from nicegui import run, ui

import vorlagen
from gui import labels
from lyrics import _HEADER, syllables
from settings import KEYS, MASTER_TARGETS, STYLE_OPTIONS, SongSettings
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

    section_title("Eigene Akkorde")
    chords_editor(s)

    section_title("Eigene Melodie")
    melody_editor(s, pick)

    section_title("Motive der Melodie")
    motif_editor(s, pick)

    section_title("Vorbild-Songs")
    reference_editor(s, pick, apply_template)

    section_title("Vorlagen")
    templates_editor(s, apply_template)


BAR_CHOICES = (2, 4, 8, 12, 16, 24, 32)


def structure_editor(s: SongSettings) -> None:
    import config
    dragged = {"from": None}

    @ui.refreshable
    def chips() -> None:
        with ui.row().classes("gap-1"):
            for i, name in enumerate(s.active_sections):
                bars = s.section_bars.get(name, config.SECTION_CONFIG[name]["bars"])
                with ui.chip(f"{labels.SECTIONS.get(name, name)} · {bars}", removable=True, color="deep-purple-4",
                             text_color="white", on_value_change=lambda _, i=i: remove(i)) \
                        .props("dense draggable clickable").mark(f"section-{i}") as chip:
                    with ui.menu().props("auto-close"):
                        ui.label(f"{labels.SECTIONS.get(name, name)}: Takte").classes("q-px-md q-pt-sm text-caption")
                        for choice in BAR_CHOICES:
                            ui.menu_item(f"{choice} Takte" + (" (Standard)" if choice == config.SECTION_CONFIG[name]["bars"]
                                                               else ""),
                                         on_click=lambda _, n=name, b=choice: set_bars(n, b)).mark(f"bars-{name}-{choice}")
                chip.on("dragstart", lambda _, i=i: dragged.update({"from": i}))
                chip.on("dragover", js_handler="(e) => e.preventDefault()")
                chip.on("drop", lambda _, i=i: move(i))
        hint("Ziehen ändert die Reihenfolge, ein Klick die Länge in Takten (gilt für alle Sektionen dieser Art). "
             "Lange Liedtexte machen eine Sektion länger.")
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

    def move(target: int) -> None:
        source, dragged["from"] = dragged["from"], None
        if source is None or source == target or not 0 <= source < len(s.active_sections):
            return
        sections = list(s.active_sections)
        sections.insert(target, sections.pop(source))
        s.active_sections = sections
        chips.refresh()

    def set_bars(kind: str, bars: int) -> None:
        default = config.SECTION_CONFIG[kind]["bars"]
        s.section_bars = {**{k: v for k, v in s.section_bars.items() if k != kind},
                          **({kind: bars} if bars != default else {})}
        chips.refresh()

    def add(name: str) -> None:
        s.active_sections = s.active_sections + [name]
        chips.refresh()

    def set_all(parts: list) -> None:
        s.active_sections = list(parts)
        chips.refresh()

    chips()


CHORD_KINDS = ("Verse", "PreChorus", "Chorus", "Bridge")


def chords_editor(s: SongSettings) -> None:
    from song_plan import check_custom
    hint("Akkordnamen (F G Em Am, C/E, Bbmaj7) oder Stufen (IV V iii vi). Mit | trennst du Takte "
         "(„F | G | Em Am“), sonst ist jeder Akkord ein Takt. Leer = die Akkorde des Stils. "
         "Intro, Outro und Solo spielen die des Refrains.")
    for kind in CHORD_KINDS:
        ui.input(labels.SECTIONS[kind], placeholder="wie der Stil", validation=lambda v: check_custom(v or "") or None) \
            .bind_value(s, "custom_chords", forward=lambda v, k=kind: {**s.custom_chords, k: v or ""},
                        backward=lambda chords, k=kind: chords.get(k, "")) \
            .classes("w-full").props("dense stack-label clearable").mark(f"chords-{kind}")


def melody_editor(s: SongSettings, pick: PickFn) -> None:
    import config
    sung = {k: labels.SECTIONS.get(k, k) for k, cfg in config.SECTION_CONFIG.items() if cfg.get("has_vocals", True)}
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input("MIDI-Datei mit deiner Melodie", placeholder="leer = die Melodie wird komponiert") \
            .bind_value(s, "melody_midi").classes("col").props("dense stack-label clearable").mark("melody-midi")
        pick_button(pick, s, "melody_midi", file_types=("MIDI (*.mid;*.midi)",))
    ui.select(sung, label="Singt in").bind_value(s, "melody_midi_section").classes("w-48").mark("melody-section")
    hint("Die Spur mit den meisten Tönen zählt, auf Sechzehntel gerundet; sie wiederholt sich, bis die Sektion "
         "voll ist, und rückt in die Stimmlage. Schreib sie in der Tonart des Songs.")


def motif_editor(s: SongSettings, pick: PickFn) -> None:
    import motifs

    def folder() -> str:
        return motifs.folder(s)

    def show() -> None:
        info.set_text(motifs.status(s))

    def open_folder() -> None:
        from gui import media
        os.makedirs(folder(), exist_ok=True)
        media.open_folder(folder())

    ui.switch("Mehr eingebaute Rhythmen und Gesten").bind_value(s, "more_motifs").mark("more-motifs") \
        .tooltip("Synkopen wie im J-Pop, Schlüsse mit Vorhalt, Zickzack und Umspielungen")
    ui.switch("Motive aus deinen MIDI-Dateien lernen", on_change=lambda: show()) \
        .bind_value(s, "learned_motifs").mark("learned-motifs") \
        .tooltip("Rhythmen und Bewegungen der Melodien in deinem Motiv-Ordner")
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input("Ordner mit MIDI-Melodien", placeholder=f"leer = {motifs.FOLDER}").bind_value(s, "motif_folder") \
            .classes("col").props("dense stack-label clearable").mark("motif-folder").on("blur", lambda: show())
        ui.button(icon="folder_open", on_click=open_folder).props("flat round dense") \
            .tooltip("Ordner öffnen: MIDI-Dateien mit Melodien hineinlegen, die dir gefallen")
        pick_button(pick, s, "motif_folder", folder=True, then=show)
    info = ui.label("").classes("text-caption").mark("motif-status")
    show()
    hint("Jeder Takt einer Melodie in Gesangslage liefert seinen Rhythmus und seine Bewegung; etwa die Hälfte "
         "der Takte singt dann solche. Neue Dateien ändern auch Songs mit festem Seed.")


REFERENCE_SWITCHES = (
    ("ref_mastering", "Mastering", "Klang und Stereobreite des Masters wie die Vorbilder (matchering); "
                                   "die Lautheit stellst du im Tab Mix ein"),
    ("ref_energy", "Lautstärke-Verlauf", "Strophe und Refrain liegen so weit auseinander wie in den Vorbildern"),
    ("ref_vocal_level", "Gesangslautstärke", "Gesang so laut gegen die Band wie in den Vorbildern (geschätzt)"),
    ("ref_tempo_key", "Tempo und Tonart vorschlagen", "Ein Klick übernimmt Tempo und Tonart der Vorbilder"),
    ("ref_style", "Stil vorschlagen", "Ein Klick übernimmt den Stil, der am besten zu den Vorbildern passt"),
)


def reference_editor(s: SongSettings, pick: PickFn, apply_template: Callable[[SongSettings], None]) -> None:
    """Mehrere Vorbilder mit Gewicht, aus Datei oder Bibliothek, dazu was sie bestimmen dürfen."""
    import reference

    from settings import ReferenceTrack
    found = {"summary": None}

    def folder() -> str:
        return s.reference_folder or reference.LIBRARY

    async def add(path: str) -> None:
        if path and all(r.path != path for r in s.reference_tracks):
            s.reference_tracks = s.reference_tracks + [ReferenceTrack(path=path)]
        rows.refresh()
        await measure()

    async def remove(i: int) -> None:
        s.reference_tracks = s.reference_tracks[:i] + s.reference_tracks[i + 1:]
        rows.refresh()
        await measure()

    async def choose() -> None:
        await add(await pick(file_types=("Audio (*.wav;*.mp3;*.flac;*.ogg;*.m4a)",)))

    async def upload(e) -> None:
        os.makedirs(folder(), exist_ok=True)
        target = os.path.join(folder(), os.path.basename(e.file.name))
        await e.file.save(target)
        await add(target)

    def open_library() -> None:
        from gui import media
        os.makedirs(folder(), exist_ok=True)
        media.open_folder(folder())

    @ui.refreshable
    def rows() -> None:
        for i, ref in enumerate(s.reference_tracks):
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.checkbox().bind_value(ref, "enabled").props("dense").on_value_change(lambda: measure())
                ui.label(os.path.basename(ref.path)).classes("col ellipsis").tooltip(ref.path)
                ui.slider(min=0, max=3, step=0.1).bind_value(ref, "weight").props("label dense") \
                    .classes("w-28").tooltip("Gewicht: wie stark dieses Vorbild zählt") \
                    .on("change", lambda: measure())
                ui.button(icon="close", on_click=lambda _, i=i: remove(i)).props("flat round dense color=grey") \
                    .mark(f"reference-remove-{i}")
        if not s.reference_tracks:
            hint("Kein Vorbild: normales Mastering. Füge einen oder mehrere Lieblingssongs hinzu.")
        library = [f for f in reference.library_files(folder()) if all(r.path != f for r in s.reference_tracks)]
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            ui.select({f: os.path.basename(f) for f in library}, label="Aus der Bibliothek",
                      on_change=lambda e: add(e.value)).classes("col").props("dense").mark("reference-library")
            ui.button(icon="folder_open", on_click=open_library).props("flat round dense") \
                .tooltip(f"Bibliothek öffnen: Songs in diesen Ordner legen ({folder()})")
            if pick.available:
                ui.button("Datei", icon="add", on_click=choose).props("flat dense no-caps").mark("reference-add")
        if not pick.available:
            ui.upload(label="Vorbild hochladen", auto_upload=True, on_upload=upload) \
                .props("dense flat accept=audio/*").classes("w-full")

    @ui.refreshable
    def summary_box() -> None:
        summary = found["summary"]
        if summary is None:
            return
        ui.label(f"Vorbilder: {summary.describe()}").classes("text-body2").mark("reference-summary")
        with ui.row().classes("gap-2"):
            if s.ref_tempo_key:
                ui.button(f"{summary.bpm} BPM, {summary.key} übernehmen", icon="speed",
                          on_click=lambda: take(bpm=summary.bpm, key=summary.key, scale=summary.scale)) \
                    .props("outline dense no-caps").mark("reference-take-tempo")
            if s.ref_style and summary.style != s.style:
                ui.button(f"Stil {summary.style} übernehmen", icon="style",
                          on_click=lambda: take(style=summary.style)) \
                    .props("outline dense no-caps").mark("reference-take-style")

    def take(**values) -> None:
        apply_template(s.with_updates(**values))
        summary_box.refresh()
        ui.notify("Vom Vorbild übernommen: " + ", ".join(str(v) for v in values.values()), type="positive")

    async def measure() -> None:
        if not reference.active(s.reference_tracks):
            found["summary"] = None
            summary_box.refresh()
            return
        refs = [r.model_copy() for r in s.reference_tracks]
        found["summary"] = await run.io_bound(reference.summarize, refs, list(STYLES))
        summary_box.refresh()

    rows()
    with ui.column().classes("w-full gap-0"):
        ui.label("Die Vorbilder bestimmen:").classes("text-caption text-grey-5 q-mt-sm")
        for attr, text, tip in REFERENCE_SWITCHES:
            ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}") \
                .on_value_change(lambda: summary_box.refresh())
    summary_box()
    ui.timer(0.1, measure, once=True)


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
    section_title("Klang")
    ui.switch("Verzerrte E-Gitarren über Verstärker und Box").bind_value(s, "guitar_amp").mark("switch-guitar_amp") \
        .tooltip("Der SoundFont spielt die Gitarre sauber, verzerrt wird danach wie mit einem echten Verstärker, und "
                 "die Box nimmt das Kratzen weg. Eine eigene Box (Impulsantwort) lässt sich unter Pfade wählen.")
    ui.switch("Lo-Fi-Klang: Knistern und alte Bandmaschine").bind_value(s, "lofi_texture") \
        .mark("switch-lofi_texture").tooltip("Nur im Stil Lo-Fi")
    hint("Das Schlagzeug kann oben statt aus dem SoundFont aus einer Drum-Machine kommen (808 oder 909).")
    section_title("Klänge aus dem VST-Instrument")
    vst_editor(s)


def vst_editor(s: SongSettings) -> None:
    """Pro Spur einen Klang im Fenster des VST-Instruments (z. B. Surge XT) aussuchen."""
    import vst_sounds

    async def choose(part: str) -> None:
        ui.notify("Das Fenster des Instruments geht auf. Such einen Klang aus und schließ das Fenster.")
        state = await run.io_bound(vst_sounds.choose, s.vst_path, s.vst_sounds.get(part, ""))
        if state:
            s.vst_sounds = {**s.vst_sounds, part: state}
        else:
            ui.notify("Das Fenster ging nicht auf. Ist unter Pfade ein VST3-Instrument gewählt?", type="warning")

    def forget(part: str) -> None:
        s.vst_sounds = {k: v for k, v in s.vst_sounds.items() if k != part}

    hint("Braucht ein VST3-Instrument unter Pfade, z. B. das kostenlose Surge XT mit echten Supersaws, Reese-Bässen "
         "und Flächen. Ohne gewählten Klang spielt die Spur wie bisher.")
    for part in vst_sounds.PARTS:
        with ui.row().classes("items-center gap-3"):
            ui.label(labels.CHANNELS[part]).classes("w-28")
            ui.label().bind_text_from(s, "vst_sounds", backward=lambda d, p=part: "eigener Klang" if p in d else
                                      "wie der Stil").classes("w-32 text-grey-5").mark(f"vst-status-{part}")
            ui.button("Klang wählen", icon="tune", on_click=lambda p=part: choose(p)) \
                .props("flat dense no-caps").bind_enabled_from(s, "vst_path", backward=bool).mark(f"vst-choose-{part}")
            ui.button("zurück", icon="undo", on_click=lambda p=part: forget(p)).props("flat dense no-caps") \
                .bind_visibility_from(s, "vst_sounds", backward=lambda d, p=part: p in d).mark(f"vst-forget-{part}")


# ── Gesang ──────────────────────────────────────────────────────────────────────
LIVELY_SWITCHES = (
    ("breaths", "Atmer vor den Phrasen", "Vor jeder Zeile ist ein leises Einatmen zu hören"),
    ("echo_throws", "Echo auf dem letzten Wort", "Am Ende jeder Sektion und jeder zweiten Refrain-Zeile hallt das "
                                                 "letzte Wort links und rechts nach"),
    ("final_choir", "Chor im letzten Refrain", "Mit NEUTRINO oder VOICEVOX singen zwei weitere Stimmen mit, "
                                               "sonst wird die eigene Stimme zum Chor vervielfacht"),
)


def voice_panel(s: SongSettings, singers: list) -> tuple:
    """Rückgabe: die Auswahl der Stimme und die der Duett-Stimme, damit die Seite ihre Listen erneuern kann."""
    ui.select(labels.ENGINES, label="Gesang mit").bind_value(s, "vocal_engine").classes("w-full").mark("engine")
    hint("Fehlt die gewählte Engine, singt die andere; fehlen beide, die Vorschau-Stimme.")
    section_title("NEUTRINO")
    options = sorted(set(singers) | {s.singer})
    singer = ui.select(options, label="Stimme").bind_value(s, "singer").classes("w-full").mark("singer")
    hint("Die Stimmen aus dem Ordner model von NEUTRINO. Die Melodie passt sich ihrem Tonumfang an.")
    duet = ui.select(duet_options(singers, s), label="Duett mit").bind_value(s, "duet_singer") \
        .classes("w-full").mark("duet")
    hint("Im Duett wechseln sich die Stimmen in den Strophen ab, die Bridge singt die zweite, im Refrain singt "
         "sie die zweite Stimme. Braucht NEUTRINO.")
    ui.switch("Zweite Stimme im Refrain").bind_value(s, "harmonies")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("StyleShift").classes("w-28")
        ui.slider(min=-6, max=6, step=1).bind_value(s, "style_shift").props("label markers").classes("col")
    hint("Plus = heller und jünger, minus = dunkler. Braucht NEUTRINO mit StyleShift.")
    ui.select({1: "1 (am schnellsten)", 2: "2", 3: "3"}, label="Fassungen").bind_value(s, "vocal_takes") \
        .classes("w-full").mark("vocal-takes")
    hint("NEUTRINO singt den Song so oft, eine Stufe heller und dunkler; in den Song kommt die Fassung, die die Töne "
         "am besten trifft und keine Aussetzer hat. Jede Fassung dauert so lange wie die erste.")
    section_title("VOICEVOX")
    voicevox_editor(s)
    section_title("Lebendiger Gesang")
    for attr, text, tip in LIVELY_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    for text, attr in (("Vibrato", "vibrato"), ("Übergänge", "glide")):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-28")
            ui.slider(min=0, max=2, step=0.1).bind_value(s, attr).props("label markers").classes("col") \
                .mark(f"slider-{attr}")
    hint("1 = wie die Stimme singt. Vibrato 0 = gerade Töne, 2 = doppelt so viel; Übergänge 0 = die Töne springen "
         "(wie Autotune), 2 = die Stimme gleitet doppelt so lange. Bei NEUTRINO wird die Aufnahme dafür neu "
         "berechnet (WORLD), das klingt eine Spur rauer.")
    section_title("Vorschau-Stimme (wenn NEUTRINO und VOICEVOX fehlen)")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Hauchigkeit").classes("w-28")
        ui.slider(min=0, max=0.2, step=0.002).bind_value(s, "breathiness").props("label").classes("col")
    ui.switch("Schimmer").bind_value(s, "shimmer")
    return singer, duet


def voicevox_editor(s: SongSettings) -> None:
    """Singstimme von VOICEVOX; die Liste kommt von der laufenden VOICEVOX-App."""
    import voicevox

    def options(found: dict) -> dict:
        names = {0: "die erste Singstimme", **found}
        if s.voicevox_singer not in names:
            names[s.voicevox_singer] = f"Stimme {s.voicevox_singer}"
        return names

    with ui.row().classes("w-full items-center no-wrap gap-2"):
        select = ui.select(options({}), label="VOICEVOX-Stimme").bind_value(s, "voicevox_singer").classes("col") \
            .mark("voicevox-singer")
        reload_button = ui.button(icon="refresh").props("flat round dense").tooltip("Stimmen neu laden") \
            .mark("voicevox-reload")
    status = ui.label().classes("text-caption text-grey-5").mark("voicevox-status")

    async def load() -> None:
        found = await run.io_bound(voicevox.singers, s.voicevox_url or voicevox.URL)
        select.set_options(options(found), value=s.voicevox_singer)
        status.set_text(f"VOICEVOX läuft, {len(found)} Singstimmen." if found else
                        "VOICEVOX läuft nicht. Kostenlos unter voicevox.hiroshiba.jp; App starten, dann neu laden.")

    reload_button.on_click(load)
    ui.timer(0.2, load, once=True)


def duet_options(singers: list, s: SongSettings) -> dict:
    names = sorted(set(singers) | ({s.duet_singer} if s.duet_singer else set()))
    return {"": "kein Duett", **{n: n for n in names}}


# ── Mix ─────────────────────────────────────────────────────────────────────────
def mix_panel(s: SongSettings) -> None:
    targets = {**MASTER_TARGETS, **({} if s.master_lufs in MASTER_TARGETS else {s.master_lufs: f"{s.master_lufs:g} LUFS"})}
    ui.select(targets, label="Lautheit des Masters").bind_value(s, "master_lufs").classes("w-full") \
        .mark("master-lufs")
    hint("YouTube und Spotify regeln lautere Songs auf -14 LUFS herunter; ein Master auf -14 klingt dort nicht gequetscht.")
    for text, attr, lo, hi, step in (
        ("Kompressor: Schwelle (dB)", "compressor_threshold", -60, 0, 0.5),
        ("Kompressor: Verhältnis", "compressor_ratio", 1, 20, 0.5),
        ("Limiter: Obergrenze (dB)", "limiter_threshold", -20, 0, 0.1),
    ):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-56")
            ui.slider(min=lo, max=hi, step=step).bind_value(s, attr).props("label").classes("col")
    hint("Die Lautheit gilt immer, auch beim Mastering nach Vorbild-Songs; der Limiter hält die Spitzen unten.")
    ui.switch("Bewegung im Mix").bind_value(s, "mix_movement").mark("switch-mix_movement") \
        .tooltip("Anlauf mit Filter vor jedem Refrain, Hall je nach Sektion, breitere Refrains")


# ── Pfade ───────────────────────────────────────────────────────────────────────
def paths_panel(s: SongSettings, pick: PickFn, status: Callable[[], None]) -> None:
    import config
    for text, attr, folder, types, default in (
        ("NEUTRINO-Ordner", "neutrino_pfad", True, (), config.NEUTRINO_PFAD),
        ("SoundFont", "soundfont_pfad", False, ("SoundFont (*.sf2;*.sf3)",), config.SOUNDFONT_PFAD),
        ("Ausgabeordner", "output_ordner", True, (), config.OUTPUT_ORDNER),
        ("VST3-Instrument, z. B. Surge XT (optional)", "vst_path", False, ("VST3 (*.vst3)",), ""),
        ("Impulsantwort der Gitarrenbox (WAV, optional)", "cabinet_ir", False, ("WAV (*.wav)",), "eingebaute Box"),
        ("Bibliothek der Vorbild-Songs", "reference_folder", True, (), _reference_library()),
    ):
        with ui.row().classes("w-full items-center no-wrap"):
            ui.input(text, placeholder=f"leer = {default}" if default else "leer = keins") \
                .bind_value(s, attr).classes("col").props("dense stack-label").mark(f"path-{attr}") \
                .on("blur", lambda: status())
            pick_button(pick, s, attr, folder=folder, file_types=types, then=status)
    import vst_sounds
    surge = vst_sounds.find_surge()
    if surge:
        def use_surge() -> None:
            s.vst_path = surge
            status()
        ui.button("Surge XT gefunden – übernehmen", icon="piano", on_click=use_surge).props("flat dense no-caps") \
            .bind_visibility_from(s, "vst_path", backward=lambda path: not path).mark("use-surge")
    import voicevox
    ui.input("Adresse von VOICEVOX", placeholder=f"leer = {voicevox.URL}").bind_value(s, "voicevox_url") \
        .classes("w-full").props("dense stack-label").mark("path-voicevox_url")
    ui.switch("Bessere Klänge aus den zusätzlichen SoundFonts (setup_soundfonts.py)") \
        .bind_value(s, "sound_library").mark("sound-library-switch") \
        .tooltip("Flügel, Streicher, Bläser, E-Gitarren und echte Schlagzeuge; gilt nur ohne eigenen SoundFont")
    ui.switch("Orchester aus echten Aufnahmen (setup_samples.py)") \
        .bind_value(s, "samples").mark("samples-switch") \
        .tooltip("Streicher, Bläser, Harfe, Pauken und Stabspiele aus VSCO 2; gilt nur ohne eigenen SoundFont")
    ui.switch("Mehrere Fassungen automatisch bewerten (setup_bewertung.py)") \
        .bind_value(s, "auto_rating").mark("rating-switch") \
        .tooltip("Audiobox Aesthetics hört jede Fassung an und gibt ihr eine Note; die beste wird geladen")


def _reference_library() -> str:
    import reference
    return reference.LIBRARY


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

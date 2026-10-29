# panels.py – Die Einstellungen der App, direkt an SongSettings gebunden
import logging
import os
from collections.abc import Awaitable, Callable

from nicegui import run, ui

import vorlagen
from gui import labels
from lyrics import _HEADER, is_translation, options as lyric_options, syllables
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
            ui.select(list(STYLES), label="Stil").bind_value(s, "style").classes("col").mark("style") \
                .on("update:model-value", lambda: ui.timer(0.05, lambda: favorite_voice(s), once=True))
            ui.button(icon="auto_fix_high", on_click=typical).props("flat round dense").mark("typical") \
                .tooltip("Typische Werte für diesen Stil: Tempo, Tonart, Ablauf und Lautstärken")
        ui.select(list(KEYS), label="Tonart").bind_value(s, "key")
        ui.select(labels.SCALES, label="Tonleiter").bind_value(s, "scale")
        ui.number("Tempo (BPM)", min=40, max=260, step=1, precision=0) \
            .bind_value(s, "bpm", forward=lambda v: int(v or 160)).mark("bpm")
        ui.select(labels.METERS, label="Takt").bind_value(s, "meter").mark("meter") \
            .tooltip("3/4: Bum-Tschak-Tschak wie ein Walzer. 6/8: wiegend, das Tempo zählt dann die punktierten Viertel "
                     "(zwei pro Takt, eine Ballade hat etwa 50 bis 70). 4/4 = wie bisher.")
    # 1.5.0 (C4): ein zweiter Stil mit Anteil
    with ui.row().classes("w-full items-center no-wrap gap-4"):
        ui.switch("Mischen mit").bind_value(s, "style_blend").props("dense").mark("switch-style_blend") \
            .tooltip("Ein Teil der Instrumente spielt mit Klang und Spielweise des zweiten Stils, ein Teil der "
                     "Sektionen mit seinem Groove, ein Teil der Akkordfolgen kommt aus ihm, z. B. Rock mit 30 % "
                     "Kawaii Chiptune. Gesang, Melodie und Klangbild bleiben beim ersten Stil")
        ui.select({"": "keinem zweiten Stil", **{n: n for n in STYLES}}).bind_value(s, "blend_style") \
            .props("dense").classes("col").mark("blend-style")
        ui.slider(min=0.1, max=0.5, step=0.05).bind_value(s, "blend_share").props("label dense") \
            .classes("w-32").mark("blend-share").tooltip("Anteil des zweiten Stils")
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

    section_title("Melodie und Akkorde")
    for attr, text, tip in MELODY_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    sliders(s, MELODY_SLIDERS)

    section_title("Eigene Akkorde")
    chords_editor(s)

    section_title("Eigene Melodie")
    melody_editor(s, pick)

    section_title("Motive der Melodie")
    motif_editor(s, pick)

    section_title("Vorbild-Songs")
    reference_editor(s, pick, apply_template)

    section_title("Song-Rezepte")
    recipes_editor(apply_template, s)

    section_title("Vorlagen")
    templates_editor(s, apply_template)


# Gesang 1.3.0 und 1.4.0, jede Neuerung mit Schalter
VOICE_SWITCHES = (
    ("resonance_tamer", "Härte zähmen", "Wie das Plugin soothe2: wenn hohe, laute Töne schrill werden, werden nur die "
                                        "Frequenzen leiser, die gerade herausstechen, und nur so lange. Die Stimme "
                                        "bleibt hell und nah"),
    ("vocal_pocket", "Gesang im Groove", "Im City Pop, Lo-Fi und in der Ballade liegt der Gesang leicht hinter dem "
                                         "Schlag (etwa 20 ms), im Rock und Drum and Bass leicht davor"),
    ("diffsinger_expression", "DiffSinger-Ausdruck", "DiffSinger-Stimmen mit Varianz-Modell singen die Strophe "
                                                     "hauchig und den Refrain kräftig, lange Töne werden zum Ende "
                                                     "hauchiger, hohe Töne gespannter"),
    # 1.4.0
    ("voice_comfort", "Wohlfühlbereich der Stimme", "Liegt das Tempo weit außerhalb dessen, was die NEUTRINO-Stimme "
                                                    "am schönsten singt (MERROW etwa 80 bis 140 BPM), steht im "
                                                    "Protokoll, welche installierte Stimme besser passt. Kennt "
                                                    "NEUTRINO keinen StyleShift (vor 3.2.2), singt es den Song am "
                                                    "Stück statt in Teilen"),
    ("gentle_reshape", "Sanfte Nachbearbeitung", "Vibrato, Übergänge und Verzierungen werden nur dort neu gerechnet, "
                                                 "wo sich die Tonhöhe hörbar ändert; der Rest bleibt, wie NEUTRINO "
                                                 "ihn gesungen hat. Kaum hörbare Formant-Verschiebungen (Idol, Dark) "
                                                 "fallen weg, weil sie die Stimme nur aufrauen"),
    ("soft_vocal_chain", "Weichere Gesangskette", "Der erste Kompressor greift mit höchstens 3:1 und 6 ms sanfter zu, "
                                                  "statt mit 6:1 in 1 ms jeden Einsatz zu quetschen; die Präsenz ist "
                                                  "breiter und sitzt höher, der Glanz bei 12 kHz. Die Stimme klingt "
                                                  "runder und weniger spitz"),
    # 1.5.0
    ("hearing_check", "Hör-Check für den Text", "Nach dem Singen hört eine japanische Spracherkennung ab, ohne den "
                                                "Text zu kennen; Zeilen, die man kaum versteht, stehen unter dem "
                                                "Player und in hoer_check.txt, mit den Lesungen der Wörter. Erst "
                                                "nach Einrichten › Hör-Check"),
)
# (Einstellung, Text, von, bis, Schritt, Erklärung), 0 = aus
VOICE_SLIDERS = (
    ("intonation", "Tonhöhe glätten", 0.0, 1.0, 0.05,
     "Zieht den ruhigen Teil zu weit danebenliegender Töne zur Note, wie eine sanfte Tonhöhenkorrektur; Vibrato und "
     "Übergänge bleiben, wie gesungen. 0 = aus, 1 = genau auf die Note"),
    ("ornaments", "Verzierungen", 0.0, 1.0, 0.05,
     "Shakuri (von unten in den Ton), Fall am Phrasenende und Kobushi (kleiner Schnörkel) auf langen Tönen, je Stil "
     "dosiert: Ballade mehr, Chiptune gar nicht. 0,35 = dezent"),
)
GROUP_CHOICES = {0: "aus", 3: "3 Stimmen", 4: "4 Stimmen"}
SPOKEN_SOUNDS = {"Hall": "mit Hall", "Telefon": "wie am Telefon", "trocken": "trocken"}

# Band 1.3.0 und 1.4.0, jede Neuerung mit Schalter
BAND_SWITCHES = (
    ("kime", "Kime, Stopps und Fills", "Vor manchen Refrains und am Ende spielt die ganze Band dieselben Akzente mit "
                                       "Becken, in Strophen setzt sie manchmal zwei Schläge aus (nur der Gesang), und "
                                       "am Ende von Vier-Takt-Phrasen spielt ein Instrument einen kleinen Lauf. Nur im "
                                       "4/4-Takt"),
    ("band_groove", "Band im Groove", "Bass, Gitarre und Klavier übernehmen die Verschiebungen und Betonungen des "
                                      "Schlagzeugers, wie eine Band, die zusammen spielt (am deutlichsten mit den "
                                      "Grooves echter Schlagzeuger). Nur im 4/4-Takt"),
    ("bass_runs", "Bass-Läufe", "Der Bass läuft zum nächsten Akkord, spielt am Ende jeder Vier-Takt-Phrase einen Fill, "
                                "springt im Refrain in die Oktave und spielt im City Pop funkige Oktaven mit "
                                "abgedämpften Tönen. Nur im 4/4-Takt"),
    ("band_runs", "Läufe", "Klavierläufe in Sechzehnteln, ein Glissando vor dem Refrain, Streicher, die nach oben in "
                           "den Refrain laufen, und im Refrain die Hook vom Klavier in Oktaven. Nur im 4/4-Takt"),
    ("anison_grooves", "Anison-Grooves", "In schnellen Songs (ab 140 BPM: J-Pop Energy, Rock, Idol-Pop, Dark "
                                         "Vocaloid, Kawaii) 2-Beat im Refrain, Disco-Hi-Hats im Pre-Chorus, "
                                         "Tom-Groove in der ersten Strophe, Snare-Wirbel als Anlauf und Becken-Stopps. "
                                         "Nur im 4/4-Takt"),
    ("section_buildup", "Aufbau in der Sektion", "Die erste Strophe beginnt nur mit Klavier oder Gitarre und Gesang, "
                                                 "nach vier Takten kommen Bass und Schlagzeug dazu; die zweite Hälfte "
                                                 "jedes Refrains bekommt eine Schicht mehr"),
    ("surge_sounds", "Surge-Klänge", "Supersaw, Pluck, Chip-Lead, Future-Bass-Akkorde und Reese-Bass spielen Werks-"
                                     "Klänge des kostenlosen Synthesizers Surge XT statt der eigenen Synths, gleich "
                                     "laut. Erst nach Einrichten › Surge XT"),
    ("amp_models", "Verstärker", "Verzerrte E-Gitarren spielen über Modelle echter Verstärker (Neural Amp Modeler): "
                                 "ein Marshall JCM2000 für Overdrive, ein Peavey 6505+ für Distortion, dahinter die "
                                 "Box. Erst nach Einrichten › Gitarren-Verstärker, nur mit „Verzerrte E-Gitarren "
                                 "über Verstärker und Box“"),
    # 1.4.0
    ("style_arrangement", "Arrangement je Stil", "Jeder Stil besetzt seine Sektionen anders: Rock mit abgedämpfter "
                                                 "Gitarre vor dem Refrain und Gitarrensolo über Powerchords in der "
                                                 "Bridge, die Ballade im Refrain "
                                                 "ohne Gitarre und Synth, Dark Vocaloid mit Staccato-Streichern und "
                                                 "Klavier-Arpeggio in der Bridge, Kawaii mit Glitzer-Glocken und "
                                                 "Antwort-Melodie im Refrain, City Pop mit Bläsern und Congas"),
    ("song_character", "Charakter pro Song", "Jeder Song bekommt aus seinem Seed eigene Klänge (z. B. Rhodes statt "
                                             "Klavier, Fingerbass statt Pick), eigene Grooves je Sektion, ein "
                                             "eigenes Intro (leise, nur Schlagzeug, mit der Hook) und einen eigenen "
                                             "Schluss (ausklingen, harter Stopp, ausblenden). Zwei Songs eines Stils "
                                             "klingen so nicht mehr gleich"),
    # 1.5.0
    ("chorus_lift", "Refrains steigern sich", "Der erste Refrain ist schlanker (Antwort-Melodie und Glocken erst ab "
                                              "der Hälfte, keine Oktav-Schicht), der letzte spielt mit allem: Oktave "
                                              "über den ganzen Refrain und ein Becken alle vier Takte"),
    ("jpop_idol_split", "J-Pop und Idol getrennt", "J-Pop Energy wird zur Anison-Band: Gitarrenriff in der Strophe, "
                                                   "Powerchords im Refrain, Rock-Grooves und Akkorde ohne die "
                                                   "„Royal Road“ (vi–IV–V–I, bVI–bVII vor dem Refrain). Idol-Pop "
                                                   "bleibt Tanz-Pop mit Royal Road, jetzt mit Synth-Bläsern und Rufen "
                                                   "wie aus dem Publikum vor dem Refrain"),
    ("taste_learning", "Geschmack lernen", "Gib Songs im Verlauf Daumen für Klang, Melodie, Stimme und Groove: die "
                                           "App würfelt Klänge, Grooves, Spielweisen und Akkordfolgen danach öfter, "
                                           "was dir gefiel, und seltener, was nicht. Ist für einen Stil keine "
                                           "Stimme gemerkt, singt die mit den meisten Daumen hoch"),
)

# Melodie 1.3.0 und 1.4.0, jede Neuerung mit Schalter
MELODY_SWITCHES = (
    ("best_melody", "Beste Melodie suchen", "Jede Sektion wird 30-mal geschrieben; es singt die Fassung mit den meisten "
                                            "Punkten: klarer Höhepunkt, Schritte und Sprünge gemischt, wenige "
                                            "Tonwiederholungen, Motive, die wiederkommen, ein Refrain über der Strophe"),
    ("melody_pickups", "Auftakte und Synkopen", "Manche Phrasen beginnen ein bis drei Silben vor dem Takt, und Töne auf "
                                                "der Eins kommen manchmal eine Sechzehntel früher, wie im J-Pop. Nur im "
                                                "4/4-Takt"),
    ("melody_tensions", "Spannungstöne", "Ab und zu liegt auf der betonten Zeit ein Ton über dem Akkordton, der sich "
                                         "auf demselben Vokal auflöst (Vorhalt), und lange Refrain-Töne landen auf "
                                         "der None oder der großen Septime"),
    ("melody_climax", "Höhepunkt im letzten Refrain", "Strophen bleiben unter dem Spitzenton des Refrains, und die "
                                                      "Schlusszeile des letzten Refrains endet oben, auf dem höchsten "
                                                      "Ton des ganzen Songs"),
    ("melody_triplets", "Triolen", "Drei Silben in einem Schlag werden manchmal zur Achteltriole, zwei Achtel zu "
                                   "punktierter Achtel und Sechzehntel; im City Pop, in der Ballade und im Lo-Fi "
                                   "öfter. NEUTRINO bekommt echte Triolen in den Noten. Nur im 4/4-Takt"),
    ("intro_riff", "Eigenes Intro-Riff", "Die Lead-Stimme spielt im Intro eine eigene Figur aus zwei Takten statt der "
                                         "Refrain-Melodie; sie kommt in einem Zwischenspiel nach dem ersten Refrain "
                                         "und im Outro wieder und läuft im letzten Refrain leise mit"),
    # 1.4.0
    ("style_chords", "Akkorde je Stil", "Jeder Stil hat eigene Akkordfolgen und Kadenzen: Rock bVI–bVII–I, City Pop "
                                        "ii7–V7–Imaj7, Ballade den Kanon mit Bass-Lauf, Dark Vocaloid i–bVI–bVII mit "
                                        "harmonischer Dominante, Lo-Fi kreisende Zweier-Folgen"),
    ("melody_character", "Melodie-Charakter je Stil", "Jeder Stil singt anders: Kawaii dicht, kurz und hüpfend, "
                                                      "Ballade lang, schrittweise und weit gespannt, Rock treibend "
                                                      "mit Quart-Sprüngen, City Pop synkopisch, Lo-Fi flach und "
                                                      "zurückgelehnt. Auch die Punkte von „Beste Melodie suchen“ "
                                                      "richten sich nach dem Stil"),
    # 1.5.0
    ("key_words", "Wichtige Wörter betonen", "„Beste Melodie suchen“ nimmt lieber die Fassung, in der das Kernwort des "
                                             "Refrains (das Wort, das am öftesten wiederkommt) hoch oder lang auf der "
                                             "betonten Zeit liegt und Gefühlswörter wie 好き, 涙, さよなら lange Töne "
                                             "bekommen"),
    ("catchy_chorus", "Ohrwurm-Wertung", "„Beste Melodie suchen“ nimmt im Refrain lieber die Fassung, deren erste "
                                         "Phrase mit kleiner Veränderung wiederkommt und deren Anfangsmotiv "
                                         "zurückkehrt"),
)
# (Einstellung, Text, von, bis, Schritt, Erklärung): Regler der Neuerungen aus 1.3.0, 0 = aus
MELODY_SLIDERS = (
    ("chord_spice", "Akkord-Würze", 0.0, 1.0, 0.05,
     "Wie oft die Akkordfolge gewürzt wird: Zwischendominanten (III7 vor vi), Leihakkorde (iv, bVI bVII), "
     "verminderte Durchgänge, sus4 vor der Dominante, laufender Bass und im Refrain die Marusa-Folge. 0 = nur die "
     "Folgen des Stils"),
)

BAR_CHOICES = (2, 4, 8, 12, 16, 24, 32)


def sliders(s: SongSettings, rows: tuple) -> None:
    """Regler der Neuerungen aus 1.3.0 (0 = aus, 1 = 100 %)."""
    for attr, text, lo, hi, step, tip in rows:
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-28").tooltip(tip)
            ui.slider(min=lo, max=hi, step=step).bind_value(s, attr).props("label").classes("col") \
                .tooltip(tip).mark(f"slider-{attr}")


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
    humming_editor(s, pick)


def humming_editor(s: SongSettings, pick: PickFn) -> None:
    """Eine gesummte Melodie (Aufnahme) wird zur MIDI-Datei, die der Song singt."""
    import humming

    async def hum(path: str) -> None:
        if not path:
            return
        target = humming.target_for(path, s.output_dir())
        count = await run.io_bound(humming.transcribe, path, s.bpm, target)
        if not count:
            ui.notify("In der Aufnahme ist keine Melodie zu hören (oder die Datei ist nicht lesbar). "
                      "Summ deutlich, Ton für Ton (da-da-da).",
                      type="warning", multi_line=True)
            return
        s.melody_midi = target
        ui.notify(f"Gesummte Melodie: {count} Töne, gespeichert als {os.path.basename(target)}", type="positive")

    async def choose() -> None:
        await hum(await pick(file_types=humming.FILE_TYPES))

    async def upload(e) -> None:
        folder = os.path.join(s.output_dir(), "summen")
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, os.path.basename(e.file.name))
        await e.file.save(target)
        await hum(target)

    if pick.available:
        ui.button("Melodie summen (Aufnahme wählen)", icon="mic", on_click=choose) \
            .props("outline dense no-caps").mark("hum-pick")
    else:
        ui.upload(label="Gesummte Melodie hochladen", auto_upload=True, on_upload=upload) \
            .props("dense flat accept=audio/*").classes("w-full").mark("hum-upload")
    hint("Summ oder sing deine Melodie im Tempo des Songs ins Handy, Ton für Ton (da-da-da). Daraus werden Noten "
         "für das Feld oben, auf Sechzehntel gerundet; der erste Ton liegt auf der Eins.")


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
    learned = ui.switch("Motive aus deinen MIDI-Dateien lernen").bind_value(s, "learned_motifs") \
        .mark("learned-motifs").tooltip("Rhythmen und Bewegungen der Melodien in deinem Motiv-Ordner")
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input("Ordner mit MIDI-Melodien", placeholder=f"leer = {motifs.FOLDER}").bind_value(s, "motif_folder") \
            .classes("col").props("dense stack-label clearable").mark("motif-folder").on("blur", lambda: show())
        ui.button(icon="folder_open", on_click=open_folder).props("flat round dense") \
            .tooltip("Ordner öffnen: MIDI-Dateien mit Melodien hineinlegen, die dir gefallen")
        pick_button(pick, s, "motif_folder", folder=True, then=show)
    info = ui.label("").classes("text-caption").mark("motif-status")
    learned.on_value_change(lambda: show())       # erst jetzt: das Binden beim Aufbau ruft es sonst ohne info auf
    show()
    hint("Jeder Takt einer Melodie in Gesangslage liefert seinen Rhythmus und seine Bewegung; etwa die Hälfte "
         "der Takte singt dann solche. Neue Dateien ändern auch Songs mit festem Seed.")


REFERENCE_SWITCHES = (
    ("ref_mastering", "Mastering", "Klang und Stereobreite des Masters wie die Vorbilder (matchering); "
                                   "die Lautheit stellst du im Tab Mix ein"),
    ("ref_energy", "Lautstärke-Verlauf", "Strophe und Refrain liegen so weit auseinander wie in den Vorbildern"),
    ("ref_vocal_level", "Gesangslautstärke", "Gesang so laut gegen die Band wie in den Vorbildern (geschätzt)"),
    ("ref_stems", "Mix pro Instrument", "Gesang, Schlagzeug, Bass und Rest einzeln so laut und so hell wie in den "
                                        "Vorbildern; braucht Demucs (Hilfe › Einrichten), das zerlegt die Vorbilder"),
    ("ref_vocal_curve", "Gesangsklang wie im Vorbild", "Die Klangkurve des Gesangs in Terzbändern wie beim Gesang der "
                                                       "Vorbilder, höchstens 4 dB je Band; braucht Demucs"),
    ("ref_tempo_key", "Tempo und Tonart vorschlagen", "Ein Klick übernimmt Tempo und Tonart der Vorbilder"),
    ("ref_style", "Stil vorschlagen", "Ein Klick übernimmt den Stil, der am besten zu den Vorbildern passt"),
    ("ref_structure", "Ablauf und Akkorde vorschlagen (wie dieser Song)",
     "Ein Klick misst das Vorbild mit dem größten Gewicht ganz durch und übernimmt Ablauf (Intro, Strophe, Refrain …), "
     "Takte und Akkorde als Stufen; alles steht danach in den Feldern und lässt sich ändern"),
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
            if s.ref_structure:
                ui.button("Ablauf und Akkorde übernehmen", icon="view_timeline", on_click=take_structure) \
                    .props("outline dense no-caps").mark("reference-take-structure") \
                    .tooltip("Wie dieser Song: misst das wichtigste Vorbild ganz durch (dauert ein paar Sekunden)")

    def take(**values) -> None:
        apply_template(s.with_updates(**values))
        summary_box.refresh()
        ui.notify("Vom Vorbild übernommen: " + ", ".join(str(v) for v in values.values()), type="positive")

    async def take_structure() -> None:
        import vorbild_ablauf
        refs = [r.model_copy() for r in s.reference_tracks]
        template = await run.io_bound(vorbild_ablauf.for_references, refs)
        if template is None:
            ui.notify("Ablauf des Vorbilds nicht messbar (zu kurz oder keine Schläge erkannt)", type="warning")
            return
        apply_template(s.with_updates(**template.updates(s)))
        summary_box.refresh()
        ui.notify(f"Ablauf vom Vorbild übernommen: {template.describe()}", type="positive", multi_line=True)

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
        import separation
        hint(separation.status())
    summary_box()
    ui.timer(0.1, measure, once=True)


def recipes_editor(apply_template: Callable[[SongSettings], None], s: SongSettings) -> None:
    """Fertige Ausgangspunkte mit Beispieltext (rezepte.py, v6 Nr. 13)."""
    import rezepte
    about = {r.name: r.about for r in rezepte.RECIPES}

    def load() -> None:
        if not choice.value:
            return
        apply_template(rezepte.apply(choice.value, s))
        ui.notify(f"Rezept „{choice.value}“ geladen, jetzt auf „Song erzeugen“ drücken", type="positive")

    with ui.row().classes("w-full items-center no-wrap gap-2"):
        choice = ui.select(rezepte.names(), label="Rezept").classes("col").mark("recipe")
        ui.button("Rezept laden", icon="restaurant_menu", on_click=load).props("flat no-caps").mark("load-recipe")
    ui.label().classes("text-caption").bind_text_from(choice, "value", backward=lambda v: about.get(v, "")) \
        .mark("recipe-about")
    hint("Ein Rezept bringt Stil, Tempo, Tonart, Takt, Ablauf und einen passenden Beispieltext mit (ersetzt deinen "
         "Text). Es entsteht ein neuer Song; Stimme, Pfade und Mix bleiben.")


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
def text_panel(s: SongSettings) -> Callable[[], None]:
    """Gibt zurück, wie sich die Vorschau neu zeichnet (nach Tempo, Takt oder Ablauf auf einem anderen Reiter)."""
    hint("Eine Überschrift wie [Verse], [Pre-Chorus], [Chorus] oder [Bridge] pro Abschnitt. Japanisch darf ganz "
         "normal geschrieben werden, auch mit Kanji; 君[きみ] gibt eine Lesung von Hand vor. [Verse 2] oder "
         "[Chorus 3] gibt einer Wiederholung ihren eigenen Text auf dieselbe Melodie.")
    ui.switch("Eigener Text für [Verse 2], [Chorus 3] …").bind_value(s, "numbered_lyrics").props("dense") \
        .mark("switch-numbered_lyrics") \
        .tooltip("Aus: jede Wiederholung singt wieder den Text der ersten Strophe oder des ersten Refrains (wie bis "
                 "1.1), Überschriften mit Nummer werden übergangen.")
    ui.switch("Romaji japanisch singen (kimi no koe → きみ の こえ)").bind_value(s, "romaji").props("dense") \
        .mark("switch-romaji").on_value_change(lambda: preview.refresh()) \
        .tooltip("Eine Zeile ganz in Romaji wird japanisch gesungen; ist ein englisches Wort darin (love, baby), bleibt "
                 "die Zeile, wie sie ist. Neben japanischer Schrift wird jedes Romaji-Wort umgewandelt.")

    ui.switch("Partikel erkennen (きみは → きみわ, 一回 → いっかい)").bind_value(s, "smart_readings") \
        .props("dense").mark("switch-smart_readings").on_value_change(lambda: preview.refresh()) \
        .tooltip("は, へ und を werden auch in reinen Kana wie Partikel gesungen (わ, え, お), Zahl und Zählwort wie "
                 "gesprochen (一回 いっかい, 三本 さんぼん). Eigene Lesungen gehören in Lesungen.txt im Datenordner, "
                 "eine pro Zeile wie „明日=あした“; eine leere Datei ändert nichts.")
    def open_readings() -> None:
        import readings
        from gui import media
        media.open_folder(readings.ensure_file())

    ui.button("Eigene Lesungen (Lesungen.txt)", icon="edit_note", on_click=open_readings) \
        .props("flat dense no-caps").mark("open-readings")
    ui.switch("Text-Helfer: Silben gegen Platz, Reime und Lesungen pro Zeile").bind_value(s, "lyric_hints") \
        .props("dense").mark("switch-lyric_hints").on_value_change(lambda: preview.refresh()) \
        .tooltip("Neben jeder Zeile: wie viele Silben sie hat und wie viele bequem in ihre Phrase passen (rot = zu "
                 "viele), auf welchem Vokal sie endet (gleicher Buchstabe = Reim) und wie Kanji gelesen werden. "
                 "Rechnet mit Tempo, Takt und Takten der Sektion.")

    @ui.refreshable
    def preview() -> None:
        if s.lyric_hints:
            helped()
            return
        rows, count = [], 0
        for raw in (s.lyrics or "").splitlines():
            line = raw.strip()
            header = _HEADER.match(line)
            if header:
                rows.append(("header", header.group(1)))
            elif line and not is_translation(line):
                sylls = syllables(line, **lyric_options(s))
                count += len(sylls)
                rows.append(("line", " ".join(sylls)))
        ui.label(f"So wird gesungen: {count} Silben").classes("text-subtitle2").mark("syllables")
        with ui.scroll_area().classes("w-full h-96"):
            for kind, text in rows:
                if kind == "header":
                    ui.label(f"[{text}]").classes("text-caption text-deep-purple-3 q-mt-sm")
                else:
                    ui.label(text).classes("text-body2")

    def helped() -> None:
        import lyric_helper
        sections = lyric_helper.check(s)
        count = sum(line.count for sec in sections for line in sec.lines)
        ui.label(f"So wird gesungen: {count} Silben").classes("text-subtitle2").mark("syllables")
        with ui.scroll_area().classes("w-full h-96"):
            for sec in sections:
                if sec.name:
                    about = f" · {sec.bars} Takte, {sec.phrases} Phrasen" if sec.phrases else ""
                    ui.label(f"[{sec.name}]{about}").classes("text-caption text-deep-purple-3 q-mt-sm")
                if sec.note():
                    ui.label(sec.note()).classes("text-caption text-amber-5").mark("lyric-note")
                for line in sec.lines:
                    with ui.row().classes("w-full no-wrap items-baseline gap-2"):
                        ui.label(line.letter or " ").classes("text-caption text-grey-5 w-4") \
                            .tooltip(f"endet auf {line.rhyme}: gleicher Buchstabe = Reim" if line.rhyme else "")
                        ui.label(" ".join(str(x) for x in line.sung)).classes("text-body2 col")
                    color = {"zu viel": "text-red-5", "schnell": "text-orange-5"}.get(line.status, "text-grey-5")
                    ui.label(line.describe()).classes(f"text-caption q-ml-lg {color}").mark("line-hint")
                    if line.changes:
                        ui.label("gelesen: " + ", ".join(f"{a} → {b}" for a, b in line.changes)) \
                            .classes("text-caption q-ml-lg text-teal-4").mark("line-reading")
                    if line.unread:
                        ui.label("Kanji ohne Lesung: schreib sie in Kana oder mit Lesung wie 君[きみ]") \
                            .classes("text-caption q-ml-lg text-red-5").mark("line-unread")

    with ui.row().classes("w-full no-wrap gap-4 items-start"):
        ui.textarea().bind_value(s, "lyrics").props("outlined autogrow input-style=min-height:360px") \
            .classes("col").mark("lyrics").on_value_change(lambda: preview.refresh())
        with ui.column().classes("col"):
            preview()
    return preview.refresh


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
    section_title("Lebendige Band")
    ui.switch("Bass mit Ghost-Notes und Slides").bind_value(s, "lively_bass").mark("switch-lively_bass") \
        .tooltip("Leise, kurze Töne vor manchen Schlägen und Gleiten in große Sprünge und laute Teile, wie bei "
                 "einem Bassisten (Spielweisen Grundton, synkopiert, entspannt und rollend)")
    ui.switch("Gitarre schlägt je nach Teil anders an").bind_value(s, "guitar_strums") \
        .mark("switch-guitar_strums") \
        .tooltip("Ruhige Teile in Vierteln, Refrains in Sechzehnteln mit abgedämpften Anschlägen; runter klingen die "
                 "tiefen Saiten, hoch die hohen (Spielweise geschlagen)")
    for attr, text, tip in BAND_SWITCHES:
        ui.switch(text).bind_value(s, attr).tooltip(tip).mark(f"switch-{attr}")
    ui.switch("Vocal Chops im Drop").bind_value(s, "vocal_chops").mark("switch-vocal_chops") \
        .tooltip("Kurze Schnipsel der Hauptstimme, umgestimmt auf die Akkorde, spielen im Drop einen Riff (im Future "
                 "Bass auch im Intro). Nur in Stilen mit Drop, nicht in Ballade, Rock, City Pop und Lo-Fi")
    ui.switch("Ballade: langsamer zum Schluss").bind_value(s, "ritardando").mark("switch-ritardando") \
        .tooltip("In den letzten zwei Takten vor dem Schlussakkord wird die Band langsamer (Ritardando), der "
                 "Schlussakkord klingt länger aus. Nur im Stil Ballade und wenn der Song mit einem Outro endet")
    hint("Echtes Schlagzeug und Grooves echter Schlagzeuger schaltest du unter Pfade ein oder aus, sobald sie "
         "eingerichtet sind.")
    producer_editor(s)
    section_title("Klänge aus dem VST-Instrument")
    vst_editor(s)


def producer_editor(s: SongSettings) -> None:
    """1.5.0 (C2): das Produzenten-Profil, das über alle Songs gleich bleibt."""
    import produzent
    section_title("Dein Produzentenstil")
    ui.switch("Produzenten-Profil").bind_value(s, "producer_profile").mark("switch-producer_profile") \
        .tooltip("Name, Producer-Tag, Erkennungsklang, Akkordwendung und Lieblingsstimme gelten für jeden Song, "
                 "auch im Album über Nacht. Ohne Namen und Auswahl ändert sich nichts")
    ui.input("Dein Produzentenname").bind_value(s, "producer_name").props("dense clearable").classes("w-full") \
        .mark("producer-name")
    hint("Steht im Abspann des Videos, in der YouTube-Beschreibung und als Künstler der MP3 („Name feat. MERROW“).")
    ui.switch("Producer-Tag am Anfang").bind_value(s, "producer_tag").props("dense").mark("switch-producer_tag") \
        .tooltip("Vier Töne aus deinem Namen am Anfang jedes Songs, im Erkennungsklang: in jedem Song dieselbe "
                 "Melodie, nur in dessen Tonart. Nur mit Namen")
    ui.select({"": "aus dem Namen", **{n: n for n in produzent.SOUNDS}}, label="Erkennungsklang") \
        .bind_value(s, "producer_sound").classes("w-full").mark("producer-sound") \
        .tooltip("Klang des Tags und der Glocken in jedem Song")
    ui.select({"": "keine", **{n: n for n in produzent.TURNS}}, label="Typische Akkordwendung im Refrain") \
        .bind_value(s, "producer_turn").classes("w-full").mark("producer-turn") \
        .tooltip("Der Refrain spielt sie in zwei von drei Songs, mit dem Schluss des Stils")
    hint("Die Lieblingsstimme für alle Stile wählst du im Tab Gesang.")


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


def favorite_voice(s: SongSettings) -> None:
    """Nach einem Wechsel des Stils: die Lieblingsstimme aus dem Stimmen-Casting wählen, wenn eine gemerkt ist."""
    import casting
    chosen = casting.favorite(s).singer
    if chosen != s.singer:
        s.singer = chosen
        ui.notify(f"Lieblingsstimme für {s.style}: {chosen}")


# ── Gesang ──────────────────────────────────────────────────────────────────────
LIVELY_SWITCHES = (
    ("breaths", "Atmer vor den Phrasen", "Vor jeder Zeile ist ein leises Einatmen zu hören"),
    ("recorded_breaths", "Echte Atmer", "Liegen Atem-Aufnahmen (WAV, z. B. CC0 von Freesound) im Datenordner unter "
                                        "Atmer, atmet die Stimme mit ihnen, passend zur Länge der Zeile"),
    ("echo_throws", "Echo auf dem letzten Wort", "Am Ende jeder Sektion und jeder zweiten Refrain-Zeile hallt das "
                                                 "letzte Wort links und rechts nach"),
    ("final_choir", "Chor im letzten Refrain", "Mit NEUTRINO oder VOICEVOX singen zwei weitere Stimmen mit, "
                                               "sonst wird die eigene Stimme zum Chor vervielfacht"),
    ("phrase_expression", "Ausdruck pro Phrase", "Jede Zeile wird zu ihrem höchsten Ton hin lauter und heller und "
                                                 "klingt am Ende weicher aus; Strophen leiser als Refrains"),
    ("syllable_dynamics", "Lautstärke pro Silbe", "Betonte Silben (Wortakzent, Schlag 1 und 3) etwas lauter, kurze "
                                                  "Silben vor einem Hochton leiser, jede Zeile setzt weich ein"),
    ("vocal_unmask", "Band macht dem Gesang Platz", "Wie das Plugin Trackspacer: die Band wird genau in den "
                                                    "Frequenzen bis zu 3 dB leiser, in denen der Gesang gerade laut "
                                                    "ist. Der Gesang ist verständlich, ohne lauter zu werden."),
    ("vocal_ride", "Gesang reitet auf der Band", "Alle 50 ms wird gemessen, wie weit der Gesang über der Band steht; "
                                                 "wo er untergeht oder heraussticht, wird er bis zu 4 dB nachgeführt"),
    ("convolution_reverb", "Platte aus Impulsantwort", "Der Hall des Gesangs aus einer Impulsantwort statt eines "
                                                         "Algorithmus, mit Pre-Delay im Tempo. Eigene Impulsantworten "
                                                         "(WAV) kommen in den Datenordner unter Hall: „platte“ im Namen "
                                                         "für den Gesang, „raum“ für die Band."),
    ("ducked_delay", "Delay weicht dem Gesang", "Das Echo auf dem Gesang ist leiser, solange gesungen wird, und "
                                                "klingt in den Pausen voll nach; die Wörter verschwimmen nicht"),
    ("vocal_chain", "Studio-Gesangskette", "Leichte Bandsättigung, Hall und Delay je Sektion (Strophe trockener, "
                                           "Refrain und Bridge weiter) und im Refrain eine echte Doppelung aus der "
                                           "zweiten Fassung"),
    ("vocal_tone", "Kette pro Stimme und Stil", "EQ, Kompressor und Sättigung passen zur Stimme und zum Stil: helle "
                                                "Stimmen weniger spitz, tiefe klarer, Ballade weicher, Rock mit mehr "
                                                "Sättigung"),
    ("airwindows", "Airwindows-Effekte", "Mit Airwindows Consolidated (Hilfe › Einrichten): Bandsättigung ToTape9 auf "
                                         "dem Gesang und das Mischpult Console7 auf jeder Spur und der Summe"),
    # 1.5.0
    ("text_expression", "Ausdruck aus dem Text", "Zeilen mit leisen Gefühlswörtern (涙, ごめん, さよなら) singt die "
                                                 "Stimme etwas leiser und dunkler, Zeilen mit lauten (叫べ, 走れ, "
                                                 "もっと) kräftiger und heller"),
    ("note_swells", "Lange Töne leben", "Gehaltene Töne mitten in einer Zeile schwellen leicht an, wie ein Sänger "
                                        "sie hält"),
    ("living_double", "Lebendige Doppelung", "Ohne zweite Fassung wandert der Abstand der Doppelung im Refrain "
                                             "langsam, wie bei einem zweimal eingesungenen Take, statt fest zu "
                                             "bleiben"),
)

# Stil-Effekte auf dem Gesang (style_fx.py), jeweils nur in den Stilen, zu denen sie gehören
STYLE_FX_SWITCHES = (
    ("telephone_fx", "Telefon in der ersten Zeile", "Die erste Zeile klingt wie durchs Telefon (Future Bass, Drum and "
                                                    "Bass, Dark Vocaloid, Lo-Fi)"),
    ("stutter_fx", "Stutter vor dem Refrain", "Im letzten Schlag vor dem Refrain stottert die Stimme in Sechzehnteln "
                                              "(Future Bass, Drum and Bass, Kawaii, J-Pop Energy)"),
    ("hard_tune", "Harter Tune im Refrain", "Die Tonhöhe rastet hart auf den Noten ein, wie Auto-Tune auf schnellster "
                                            "Stufe (Future Bass, Kawaii)"),
    ("formant_fx", "Formanten verschieben", "Kindlicher bei Kawaii und Idol-Pop, dunkler bei Dark Vocaloid; die "
                                            "Tonhöhe bleibt"),
    ("vocal_swing", "Gesang swingt mit", "Swingt die Band (Lo-Fi oder Swing-Regler ab 0,2), setzen die Töne auf der "
                                         "zweiten Sechzehntel genauso viel später ein; Tonhöhe und Klang bleiben"),
)

# Begleitstimmen wie in Produktionen (backing_vocals.py), von NEUTRINO gesungen
BACKING_SWITCHES = (
    ("harmony_variety", "Harmonie je Refrain anders", "Erster Refrain: Terz nur auf den Phrasenenden, mittlere: Terz "
                                                      "darunter, letzter: Terz darüber und, wenn sie in die Stimmlage "
                                                      "passt, die Oktave"),
    ("harmony_double", "Harmonie gedoppelt", "Die zweite Stimme singt zweimal, eine Fassung links, eine rechts"),
    ("sung_pads", "Gesungene Flächen", "Drei Stimmen singen im Refrain die Akkordtöne auf う (im letzten auf あ) statt "
                                       "des Keyboard-Chors; NEUTRINO singt dafür etwas länger"),
    ("adlibs", "Ad-libs im letzten Refrain", "Kurze Rufe (いぇー, おー) und Echo-Antworten in den Lücken des Gesangs"),
    ("idol_calls", "Idol-Rufe", "Mehrere Stimmen rufen „はい！はい！“ (Rock: „おい！“) auf den Gegenschlägen, an denen "
                                "die Hauptstimme Pause hat, und „ふっふー“ vor dem Refrain. Im Idol-Pop und Kawaii in "
                                "jedem Refrain, in J-Pop Energy und Rock im letzten"),
)

# Noten, die NEUTRINO gut singen kann (neutrino_score.py) und Englisch im Liedtext
SCORE_SWITCHES = (
    ("long_vowel_mark", "Haltezeichen ー für lange Vokale", "Lang gezogene Vokale und Melismen bekommen für NEUTRINO "
                                                            "das Haltezeichen ー statt einer neuen Silbe"),
    ("breath_marks", "Atemzeichen in langen Zeilen", "Nach spätestens zwei Takten Gesang atmet die Stimme an der "
                                                     "nächsten kleinen Pause; NEUTRINO braucht dann weniger Speicher"),
    ("fast_diphthongs", "Schnelle Stellen flüssig", "Zwei sehr schnelle Töne mit Doppelvokal (か + い) singt NEUTRINO "
                                                    "auf einem Ton, wie es seine Anleitung empfiehlt"),
    ("english_kana", "Englisch als Katakana", "Englische Wörter im Text werden so gesungen, wie man sie in J-Pop singt "
                                              "(love → ラブ). NEUTRINO kann kein Englisch."),
    ("singable_melody", "Singbare Melodie", "Keine Sprünge über eine Quinte auf kurzen Silben, der höchste Ton nicht "
                                            "nur eine Sechzehntel lang, nach spätestens 8 Sekunden eine Atempause. "
                                            "Gilt nicht für eine eigene Melodie."),
)


def voice_panel(s: SongSettings, singers: list, pick: PickFn | None = None) -> tuple:
    """Rückgabe: die Auswahl der Stimme, der Duett- und der Support-Stimme, damit die Seite ihre Listen erneuern
    kann."""
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
    support = ui.select(support_options(singers, s), label="Support-Stimme (Versuch)") \
        .bind_value(s, "support_singer").classes("w-full").mark("support")
    hint("Eine zweite Stimme läuft als Support-Modell mit und gibt der Hauptstimme eine andere Färbung, z. B. MERROW "
         "mit SOMA. NEUTRINO nennt das selbst experimentell; braucht Run_support_model.bat (ab NEUTRINO 3).")
    ui.select(GROUP_CHOICES, label="Gruppe").bind_value(s, "group_vocals").classes("w-full").mark("group-vocals")
    hint("Drei oder vier installierte NEUTRINO-Stimmen singen den Refrain zusammen (links, Mitte, rechts) und die "
         "Strophen reihum, wie eine Idol-Gruppe. Mit weniger als drei Stimmen singt die gewählte allein.")
    ui.switch("Zweite Stimme im Refrain").bind_value(s, "harmonies")
    ui.switch("Lieblingsstimme je Stil").bind_value(s, "style_singer").props("dense").mark("switch-style_singer") \
        .tooltip("Beim Wechsel des Stils wählt die App die Stimme, die du im Stimmen-Casting für ihn gemerkt hast")
    ui.select({"": "keine", **{n: n for n in sorted(set(singers) | ({s.producer_singer} - {""}))}},
              label="Lieblingsstimme für alle Stile (Produzenten-Profil)").bind_value(s, "producer_singer") \
        .classes("w-full").mark("producer-singer") \
        .tooltip("Beim Wechsel des Stils singt sie, wenn für den Stil keine eigene Stimme gemerkt ist")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("StyleShift").classes("w-28")
        ui.slider(min=-6, max=6, step=1).bind_value(s, "style_shift").props("label markers").classes("col")
    hint("Plus = heller und jünger, minus = dunkler. Braucht NEUTRINO mit StyleShift.")
    ui.select({1: "1 (am schnellsten)", 2: "2", 3: "3"}, label="Fassungen").bind_value(s, "vocal_takes") \
        .classes("w-full").mark("vocal-takes")
    hint("NEUTRINO singt den Song so oft, eine Stufe heller und dunkler. Jede Fassung dauert so lange wie die erste.")
    ui.switch("Jede Phrase aus der saubersten Fassung (Comping)").bind_value(s, "vocal_comping").props("dense") \
        .mark("switch-vocal_comping") \
        .tooltip("Wie im Studio: jede Zeile kommt aus der Fassung, die ihre Töne am besten trifft. Aus ist es die "
                 "sauberste ganze Fassung. Die zweitbeste Fassung doppelt den Refrain (mit der Studio-Gesangskette).")
    ui.switch("Fassungen ohne Farbsprung").bind_value(s, "even_takes").props("dense").mark("switch-even_takes") \
        .tooltip("Alle Fassungen singen mit demselben StyleShift, und eine Phrase wechselt die Fassung nur bei groben "
                 "Fehlern (falscher Ton, Kiekser), nicht wegen schöner Schleifer. Singt NEUTRINO jedes Mal dasselbe, "
                 "merkt die App das und singt die weiteren Fassungen eine Stufe heller und dunkler.")
    section_title("Strophe ruhig, Refrain kräftig")
    ui.switch("StyleShift pro Sektion").bind_value(s, "section_style").props("dense").mark("switch-section_style") \
        .tooltip("NEUTRINO singt die Strophen tiefer und ruhiger, die Refrains heller und kräftiger. Jede Sektion "
                 "wird einzeln gesungen und in den Pausen zusammengesetzt; das dauert etwas länger.")
    for text, attr in (("Strophe", "verse_style_shift"), ("Refrain", "chorus_style_shift")):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-28")
            ui.slider(min=-3, max=3, step=1).bind_value(s, attr).props("label markers").classes("col") \
                .bind_enabled_from(s, "section_style").mark(f"slider-{attr}")
    hint("Zum StyleShift oben dazu: minus = dunkler und ruhiger, plus = heller und kräftiger. Zweite Stimme und Chor "
         "singen wie der Refrain. Die NEUTRINO-Ausgabe mit Tuning-Tool (.ex) kennt keinen StyleShift.")
    section_title("Begleitstimmen (NEUTRINO)")
    for attr, text, tip in BACKING_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    section_title("Stil-Effekte")
    for attr, text, tip in STYLE_FX_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    section_title("Noten für NEUTRINO")
    for attr, text, tip in SCORE_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    section_title("Eigene Gesangsspur")
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input("WAV statt der Hauptstimme", placeholder="leer = die Engine singt") \
            .bind_value(s, "own_vocal").classes("col").props("dense stack-label clearable").mark("own-vocal")
        if pick is not None:
            pick_button(pick, s, "own_vocal", file_types=("WAV (*.wav)",))
    ui.switch("An den Noten ausrichten").bind_value(s, "own_vocal_align").props("dense").mark("switch-own_vocal_align")
    hint("Für Feinarbeit im NEUTRINO-Tuning-Tool, in VoiSona oder für eine eigene Aufnahme: „Noten für Tuning-Tools“ "
         "exportieren, dort bearbeiten, die WAV hier wählen. Sie ersetzt die Hauptstimme und wird gemischt wie der "
         "eigene Gesang; der Vorlauftakt fällt beim Ausrichten weg. Die Begleitstimmen singt weiter die Engine.")
    section_title("DiffSinger (Versuch)")
    with ui.row().classes("w-full items-center no-wrap"):
        ui.input("Stimme (Ordner mit dsconfig.yaml)", placeholder="leer = die erste aus OpenUtau") \
            .bind_value(s, "diffsinger_voice").classes("col").props("dense stack-label clearable").mark("diffsinger")
        if pick is not None:
            pick_button(pick, s, "diffsinger_voice", folder=True)
    hint("DiffSinger-Stimmen für OpenUtau (Ordner Singers, Vocoder unter Dependencies) singen ohne OpenUtau: die App "
         "rechnet ihre Modelle selbst, wie OpenUtau. Ein Versuch: Konsonanten und Tonhöhe setzt die App nach festen "
         "Regeln. Jede Stimme hat eigene Nutzungsregeln.")
    section_title("VOICEVOX")
    voicevox_editor(s)
    ui.switch("VOICEVOX singt laut und leise selbst").bind_value(s, "voicevox_dynamics").props("dense") \
        .mark("switch-voicevox_dynamics") \
        .tooltip("Betonte Silben und der Weg zum Höhepunkt einer Zeile gehen als Lautstärke in den Gesang ein, statt "
                 "danach lauter und leiser gedreht zu werden. Leiser klingt dann auch weicher.")
    section_title("Rap und Sprechen")
    rap_editor(s)
    section_title("Gesang wie produziert")
    for attr, text, tip in VOICE_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    import hoercheck
    hint(hoercheck.status())
    sliders(s, VOICE_SLIDERS)
    section_title("Lebendiger Gesang")
    for attr, text, tip in LIVELY_SWITCHES:
        ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
    for text, attr in (("Vibrato", "vibrato"), ("Übergänge", "glide")):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(text).classes("w-28")
            ui.slider(min=0, max=2, step=0.1).bind_value(s, attr).props("label markers").classes("col") \
                .mark(f"slider-{attr}")
    ui.switch("Mit PSOLA statt WORLD").bind_value(s, "psola_reshape").props("dense").mark("switch-psola_reshape") \
        .tooltip("Praat-PSOLA verschiebt nur die Tonhöhe und lässt den Klang der Stimme, wie er ist. Aus: der "
                 "WORLD-Vocoder baut jede Phrase neu, das klingt eine Spur rauer.")
    hint("1 = wie die Stimme singt. Vibrato 0 = gerade Töne, 2 = doppelt so viel; Übergänge 0 = die Töne springen "
         "(wie Autotune), 2 = die Stimme gleitet doppelt so lange. Bei NEUTRINO wird die Aufnahme dafür Phrase für "
         "Phrase umgerechnet, bei 1 und 1 bleibt sie unberührt.")
    section_title("Vorschau-Stimme (wenn NEUTRINO und VOICEVOX fehlen)")
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Hauchigkeit").classes("w-28")
        ui.slider(min=0, max=0.2, step=0.002).bind_value(s, "breathiness").props("label").classes("col")
    ui.switch("Schimmer").bind_value(s, "shimmer")
    return singer, duet, support


def rap_editor(s: SongSettings) -> None:
    """Sprechstimme für die Sektion „Rap“ (rap.py); die Liste kommt von der laufenden VOICEVOX-App."""
    import voicevox

    def options(found: dict) -> dict:
        names = {0: "die erste Sprechstimme", **found}
        if s.rap_speaker not in names:
            names[s.rap_speaker] = f"Stimme {s.rap_speaker}"
        return names

    ui.switch("Rap von der VOICEVOX-Sprechstimme").bind_value(s, "rap_voice").props("dense") \
        .mark("switch-rap_voice")
    with ui.row().classes("w-full items-center no-wrap gap-2"):
        select = ui.select(options({}), label="Sprechstimme").bind_value(s, "rap_speaker").classes("col") \
            .mark("rap-speaker")
        reload_button = ui.button(icon="refresh").props("flat round dense").tooltip("Stimmen neu laden")
    hint("Eine Sektion „Rap“ (Ablauf und [Rap] im Liedtext) spricht VOICEVOX im Takt, wie der Rap in „Idol“; NEUTRINO "
         "kann nicht rappen. Dafür muss die VOICEVOX-App laufen, auch wenn NEUTRINO singt. Ohne VOICEVOX oder mit dem "
         "Schalter aus singt die Gesangsstimme den Rap fast auf einem Ton.")
    ui.select(SPOKEN_SOUNDS, label="Sprechen klingt").bind_value(s, "spoken_sound").classes("w-full") \
        .mark("spoken-sound")
    hint("Eine Sektion „Sprechen“ (Ablauf und [Sprechen] im Liedtext) spricht dieselbe Stimme frei, nicht im Takt, "
         "während die Band leise spielt. Ohne VOICEVOX fällt die Zeile weg.")

    async def load() -> None:
        found = await run.io_bound(voicevox.talkers, s.voicevox_url or voicevox.URL)
        if found is None:       # die App wird gerade beendet
            return
        select.set_options(options(found), value=s.rap_speaker)

    reload_button.on_click(load)
    ui.timer(0.3, load, once=True)


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
        if found is None:       # die App wird gerade beendet
            return
        select.set_options(options(found), value=s.voicevox_singer)
        status.set_text(f"VOICEVOX läuft, {len(found)} Singstimmen." if found else
                        "VOICEVOX läuft nicht. Kostenlos unter voicevox.hiroshiba.jp; App starten, dann neu laden.")

    reload_button.on_click(load)
    ui.timer(0.2, load, once=True)


def duet_options(singers: list, s: SongSettings) -> dict:
    names = sorted(set(singers) | ({s.duet_singer} if s.duet_singer else set()))
    return {"": "kein Duett", **{n: n for n in names}}


def support_options(singers: list, s: SongSettings) -> dict:
    names = sorted(set(singers) | ({s.support_singer} if s.support_singer else set()))
    return {"": "aus", **{n: n for n in names}}


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
    ui.switch("Klangbild je Stil").bind_value(s, "style_sound").mark("switch-style_sound") \
        .tooltip("Jeder Stil hat seinen eigenen Raum und Klang: Ballade großer, weicher Hall, Lo-Fi kleiner dumpfer "
                 "Raum mit warmer Sättigung, Rock kurzer Raum mit Biss in den Mitten, Future Bass riesig und breit, "
                 "City Pop glänzend wie die 80er, Dark Vocaloid dunkel mit langem Delay")
    ui.switch("Druck (Parallel-, Bus- und Mehrband-Kompression)").bind_value(s, "mix_punch") \
        .mark("switch-mix_punch") \
        .tooltip("Eine stark komprimierte Kopie des Schlagzeugs läuft leise mit, ein Bus-Kompressor hält die Band "
                 "zusammen, und im Master werden Bässe, Mitten und Höhen einzeln verdichtet: der Song klingt dichter "
                 "und druckvoller, ohne lauter zu werden")
    ui.switch("Spitzen auch zwischen den Samples begrenzen (-1 dBTP)").bind_value(s, "true_peak") \
        .mark("switch-true_peak") \
        .tooltip("MP3 und Streaming heben Spitzen zwischen den Samples sonst über 0 dB; das kann knacksen. "
                 "YouTube und Spotify empfehlen -1 dBTP.")
    ui.switch("Off-Vocal und A-cappella dazu (ohne Gesang / nur Gesang)").bind_value(s, "vocal_versions") \
        .mark("switch-vocal_versions") \
        .tooltip("Zwei weitere MP3s neben dem Song, so laut wie im Song: zum Mitsingen, für Cover und Remixe. "
                 "Im Player unter den Spuren.")
    ui.switch("Titel, Liedtext und Titelbild in die MP3 schreiben").bind_value(s, "id3_tags") \
        .mark("switch-id3_tags") \
        .tooltip("Handy, Auto und Musik-Apps zeigen den Song dann mit Namen, Stil, Tempo, Text und Cover.")
    with ui.column().classes("w-full gap-1").bind_visibility_from(s, "polish"):
        ui.label("Klang-Veredler (ACE-Step, Versuch)").classes("text-subtitle2 q-mt-sm")
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Wie stark verändern").classes("w-56")
            ui.slider(min=0.1, max=0.9, step=0.05).bind_value(s, "polish_strength").props("label").classes("col") \
                .mark("polish-strength")
        ui.input("Klangbeschreibung auf Englisch", placeholder="leer = passend zum Stil") \
            .bind_value(s, "polish_caption").classes("w-full").props("dense stack-label").mark("polish-caption")
        hint("ACE-Step spielt die Band neu ein, Takt, Akkorde und Melodie bleiben, der Gesang wird nicht verändert. "
             "Das Ergebnis ist eine zweite Fassung neben dem normalen Song („Veredelt“ im Player).")


# ── Video (1.5.0) ───────────────────────────────────────────────────────────────
VIDEO_SWITCHES = (
    ("video_kanji", "Text mit Kanji, Wort für Wort eingefärbt",
     "Wie du ihn geschrieben hast. Aus: in Hiragana Silbe für Silbe wie gesungen."),
    ("video_romaji", "Romaji unter der Zeile", "Die gesungenen Silben in lateinischen Buchstaben: ame no machi o"),
    ("video_german", "Deine Übersetzung unter der Zeile",
     "Schreib im Text-Tab unter eine Zeile eine mit „>“ davor, z. B. „> Durch die Stadt im Regen“. Sie wird nicht "
     "gesungen."),
    ("video_chords", "Akkord unten links, mit dem nächsten", "Wechselt genau mit dem Akkord im Song"),
    ("video_melody_line", "Gesangsmelodie als Notenlinie", "Die Töne ziehen durchs Bild, der gerade gesungene leuchtet"),
    ("video_spectrum", "Spektrum des Songs", "Balken, Kreis oder Pegel je nach Szene, aus dem fertigen Mix"),
    ("video_words", "Bilder aus dem Text",
     "Regen bei 雨, Schnee bei 雪, Sterne bei 星, Blüten bei 桜, eine Chat-Blase bei 既読 … nur was im Text steht"),
    ("video_titles", "Titelkarte am Anfang, Abspann am Ende",
     "Der Titel, solange das Intro ohne Text läuft; im Outro Stimme und Musik"),
    ("video_hud", "Ablaufleiste mit den Sektionen", "Oben rechts: wo im Song du gerade bist, Refrains hervorgehoben"),
    ("youtube_chapters", "Kapitel in der YouTube-Beschreibung", "0:00 Intro, 0:15 Strophe 1, 0:59 Refrain 1 …"),
)


def video_panel(s: SongSettings, pick: PickFn) -> None:
    import bilder
    import video_szenen
    ui.switch("Musikvideo: das Bild folgt dem Song").bind_value(s, "music_video").mark("switch-music_video") \
        .tooltip("Szene passend zum Stil; Strophe ruhig, Refrain hell und voll, Bewegung auf Kick und Snare, Akkorde, "
                 "Melodie und Spektrum. Aus: das Lyric-Video wie bis 1.4.")
    with ui.column().classes("w-full gap-1").bind_visibility_from(s, "music_video"):
        with ui.grid(columns=2).classes("w-full gap-x-4"):
            ui.select(video_szenen.CHOICES, label="Szene").bind_value(s, "video_scene").mark("video-scene") \
                .tooltip("Wie der Stil oder eine andere Szene; „Textkunst“ ist alles aus Zeichen wie ein altes Spiel, "
                         "der Zeichenregen besteht aus deinem eigenen Text")
            ui.select({"Stil": "wie der Stil", "ruhig": "ruhig und elegant", "lebhaft": "viel Bewegung"},
                      label="Bewegung").bind_value(s, "video_motion").mark("video-motion") \
                .tooltip("Ruhig: sanftes Wiegen statt Zoom und Wackeln. Blitze gibt es nie öfter als dreimal pro "
                         "Sekunde und nie grell.")
        for attr, text, tip in VIDEO_SWITCHES:
            ui.switch(text).bind_value(s, attr).props("dense").tooltip(tip).mark(f"switch-{attr}")
        ui.switch("KI-Bild pro Sektion (setup_bilder.py)").bind_value(s, "ai_backgrounds").props("dense") \
            .mark("switch-ai_backgrounds") \
            .tooltip("Ein gemaltes Bild für jede Sektion passend zu Stil und Text; nur wenn unter Hilfe › Einrichten "
                     "„KI-Bilder fürs Video“ eingerichtet ist, sonst die gezeichnete Szene")
        hint(bilder.status())
        section_title("Eigene Figur (optional)")
        for text, attr in (("Figur, Mund zu (PNG mit durchsichtigem Hintergrund)", "video_figure"),
                           ("Dieselbe Figur mit offenem Mund (optional)", "video_figure_open")):
            with ui.row().classes("w-full items-center no-wrap"):
                ui.input(text, placeholder="leer = keine Figur").bind_value(s, attr).classes("col") \
                    .props("dense stack-label").mark(f"path-{attr}")
                pick_button(pick, s, attr, file_types=("Bild (*.png)",))
        hint("Die Figur steht rechts, hüpft im Takt und öffnet den Mund, solange gesungen wird.")
    hint("Hintergrundbild und Farben des Lyric-Videos ohne Musikvideo stellst du unter Pfade ein.")


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
        ("Hintergrundbild des Lyric-Videos (optional)", "video_background", False,
         ("Bild (*.png;*.jpg;*.jpeg)",), "Farbverlauf des Stils"),
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
    ui.switch("Lyric-Video in den Farben des Stils").bind_value(s, "video_colors").mark("switch-video_colors") \
        .tooltip("Farbverlauf wie beim YouTube-Titelbild, Text und Wellenform in den Farben des Stils. Aus: dunkel "
                 "mit pinkem Text wie bis 1.1. Ein eigenes Hintergrundbild (oben) gilt immer.")
    import voicevox
    ui.input("Adresse von VOICEVOX", placeholder=f"leer = {voicevox.URL}").bind_value(s, "voicevox_url") \
        .classes("w-full").props("dense stack-label").mark("path-voicevox_url")
    ui.switch("Bessere Klänge aus den zusätzlichen SoundFonts (setup_soundfonts.py)") \
        .bind_value(s, "sound_library").mark("sound-library-switch") \
        .tooltip("Flügel, Streicher, Bläser, E-Gitarren und echte Schlagzeuge; gilt nur ohne eigenen SoundFont")
    ui.switch("Orchester aus echten Aufnahmen (setup_samples.py)") \
        .bind_value(s, "samples").mark("samples-switch") \
        .tooltip("Streicher, Bläser, Harfe, Pauken und Stabspiele aus VSCO 2; gilt nur ohne eigenen SoundFont")
    ui.switch("Flügel, E-Bass und E-Gitarre aus echten Aufnahmen (setup_band.py)") \
        .bind_value(s, "band_samples").mark("band-samples-switch") \
        .tooltip("Salamander-Flügel, Growlybass und Emily-Gitarre; verzerrte Gitarren spielen die Emily-Gitarre "
                 "in den Verstärker. Gilt nur ohne eigenen SoundFont")
    ui.switch("Echtes Schlagzeug aus Aufnahmen (setup_drums.py, DRS Kit)") \
        .bind_value(s, "real_drums").mark("real-drums-switch") \
        .tooltip("Bassdrum, Snare, Toms, Hi-Hat und Becken aus einem im Studio aufgenommenen Schlagzeug; "
                 "gilt für akustische Kits ohne eigenen SoundFont, 808 und 909 bleiben Drum-Machines")
    ui.switch("Grooves und Fills echter Schlagzeuger (setup_grooves.py)") \
        .bind_value(s, "real_grooves").mark("real-grooves-switch") \
        .tooltip("Pop, Rock, Ballade, City Pop und Idol-Pop spielen Phrasen und Fills aus dem Groove MIDI Dataset, "
                 "mit dem Timing echter Schlagzeuger; Stile mit Swing und elektronische bleiben eingebaut")
    ui.switch("Mehrere Fassungen automatisch bewerten (setup_bewertung.py)") \
        .bind_value(s, "auto_rating").mark("rating-switch") \
        .tooltip("Audiobox Aesthetics hört jede Fassung an und gibt ihr eine Note; die beste wird geladen")
    ui.switch("Klang der Band mit ACE-Step veredeln (setup_ace_step.py, Versuch)") \
        .bind_value(s, "polish").mark("polish-switch").on_value_change(lambda: status()) \
        .tooltip("Zweite Fassung jedes Songs mit neu eingespielter Band; braucht eine NVIDIA-Grafikkarte")
    ui.switch("Begleitung vom KI-Modell schreiben lassen (setup_begleitung.py, Versuch)") \
        .bind_value(s, "ai_accompaniment").mark("accompaniment-switch") \
        .tooltip("Der Anticipatory Music Transformer schreibt Klavier, Gitarre, Streicher, Synths und Bläser passend zu "
                 "Melodie, Bass und Schlagzeug; ohne NVIDIA-Grafikkarte dauert ein Song lange")
    ui.switch("KI-Melodie im Refrain vorschlagen lassen (setup_begleitung.py, Versuch)") \
        .bind_value(s, "ai_melody").mark("switch-ai_melody") \
        .tooltip("Dasselbe Modell schreibt zu Akkorden, Bass und Schlagzeug vier Refrain-Melodien; die App passt sie an "
                 "Silben und Stimmlage an und bewertet sie wie „Beste Melodie suchen“. Singt eine besser als die "
                 "komponierte, singen alle Refrains sie. Braucht die eingerichtete KI-Begleitung")
    app_settings(s)


def app_settings(s: SongSettings) -> None:
    """Schalter für die App selbst: Wiederverwenden, Protokoll, Updates, Assistent, Verlauf, Datenordner."""
    import userdata
    section_title("App")
    ui.switch("Fertige Schritte wiederverwenden (Gesang, Spuren, Weitermachen nach Absturz)") \
        .bind_value(s, "reuse_steps").mark("reuse-switch") \
        .tooltip("Singt NEUTRINO nicht neu, wenn sich am Gesang nichts geändert hat, und bietet nach einem Absturz an, "
                 "den Song fertig zu machen")
    ui.switch("Protokoll in eine Datei schreiben (für Fehlerberichte)").bind_value(s, "log_file") \
        .mark("log-switch").tooltip("Protokolle\\vloid_songs.log im Datenordner; gilt ab dem nächsten Start")
    ui.switch("Nach Updates suchen (einmal am Tag) und nach einem Update zeigen, was neu ist").bind_value(s, "update_check").mark("update-switch")
    ui.switch("Einrichten-Assistent beim Start zeigen, bis er fertig ist").bind_value(s, "setup_wizard") \
        .mark("wizard-switch")
    ui.switch("Tastenkürzel: Leertaste spielt, Strg+Enter erzeugt, Strg+Z nimmt eine Notenänderung zurück") \
        .bind_value(s, "shortcuts").mark("switch-shortcuts") \
        .tooltip("Gilt nicht, während du in ein Feld schreibst")
    ui.switch("Melden, wenn der Song fertig ist").bind_value(s, "done_notice").mark("switch-done_notice") \
        .tooltip("Eine Windows-Benachrichtigung unten rechts, wenn ein Song, mehrere Fassungen oder ein Album "
                 "fertig sind (nur nach Läufen ab 20 Sekunden). So kannst du in der Zeit etwas anderes machen.")
    ui.number("So viele Songs behält der Verlauf (0 = alle)", min=0, max=1000, step=5, precision=0) \
        .bind_value(s, "history_keep", forward=lambda v: int(v or 0)).classes("w-80").mark("history-keep") \
        .tooltip("Ältere fallen heraus; Favoriten, Songs mit Namen und Album-Songs bleiben immer")
    ui.switch("Gesang jedes Songs aufheben, zum Wieder-Öffnen aus dem Verlauf").bind_value(s, "keep_projects") \
        .mark("switch-keep_projects") \
        .tooltip("Etwa 20 bis 60 MB pro Song (FLAC). Ein wieder geöffneter Song singt nicht neu: Band und Mix "
                 "entstehen frisch, danach lässt er sich weiter bearbeiten.")
    ui.label(userdata.describe()).classes("text-caption").mark("data-folder")
    ui.switch("Daten im Programmordner lassen statt in Dokumente (gilt ab dem nächsten Start)",
              value=userdata.in_program_folder(), on_change=lambda e: userdata.choose_program_folder(e.value)) \
        .mark("program-folder-switch") \
        .tooltip("Für einen Ordner auf dem USB-Stick. Beim nächsten Start zieht die App deine Songs und Einstellungen um.")


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

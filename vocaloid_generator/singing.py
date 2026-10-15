# singing.py – Der Gesang eines Songs: welche Engine singt (NEUTRINO, VOICEVOX, DiffSinger, sonst die Vorschau-Stimme),
# Fassungen, Comping, Begleitstimmen, Duett, Chor, und was danach mit der Hauptstimme passiert (Ausdruck, Atmer,
# Stil-Effekte, Swing). Bleibt alles, was den Gesang bestimmt, gleich, wird nicht neu gesungen (vocals.key).
# pipeline.py ruft _synthesize_vocals() auf.
import logging
import os
from typing import NamedTuple, Optional

import numpy as np

import config
import neutrino_score
from config import remove_file
from settings import SongSettings
from song_plan import chorus_windows, final_chorus, sections_in_seconds

log = logging.getLogger(__name__)


# Begleitstimmen, die nur NEUTRINO singt (backing_vocals.py): Oktave im letzten Refrain, Flächen, Ad-libs
EXTRA_VOCALS = ("vocals_harmony_2.wav", "vocals_flaechen.wav", "vocals_adlibs.wav")
VOCAL_FILES = ("vocals.wav", "vocals_duett_1.wav", "vocals_duett_2.wav", "vocals_harmony.wav", "vocals_chor.wav",
               "vocals_double.wav") + EXTRA_VOCALS
# Welche Engine singt, wenn die gewählte fehlt; ganz zuletzt die lokale Vorschau-Stimme
ENGINE_ORDER = {"NEUTRINO": ("NEUTRINO", "VOICEVOX"), "VOICEVOX": ("VOICEVOX", "NEUTRINO"),
                "DiffSinger": ("DiffSinger", "NEUTRINO", "VOICEVOX"), "Vorschau": ()}
# A6: ab diesem Swing (Stil plus Regler) swingt der Gesang mit; Lo-Fi ja, der Grundwert 0,12 allein nicht
VOCAL_SWING_FROM = 0.2
# Welche Gesangsspur nach welchen Noten swingt
VOCAL_SWING_LINES = {"melody_data": ("vocals.wav", "vocals_double.wav", "vocals_duett_1.wav", "vocals_duett_2.wav",
                                     "vocals_chor.wav"),
                     "harmony_data": ("vocals_harmony.wav",), "octave_data": ("vocals_harmony_2.wav",)}


# Was den Gesang bestimmt: ändert sich nichts davon, bleibt der gesungene Gesang (z. B. beim Neu-Würfeln des Basses)
VOCAL_KEY = "vocals.key"
# Die gesungenen Noten aller Stimmen in den Spuren (orchestrate_song)
NOTE_KEYS = ("melody_data", "silben", "harmony_data", "harmony_silben", "octave_data", "octave_silben", "pads",
             "adlib_data", "adlib_silben")
VOCAL_CODE = ("singing.py", "vocal_synthesizer.py", "voice_fx.py", "voicevox.py", "neutrino_score.py", "diffsinger.py")
VOCAL_FIELDS = ("bpm", "seed", "singer", "vocal_engine", "harmonies", "duet_singer", "support_singer", "style_shift", "vocal_takes",
                "vibrato", "glide", "breaths", "final_choir", "voicevox_url", "voicevox_singer", "voicevox_dynamics", "diffsinger_voice",
                "neutrino_pfad",
                "vocal_comping", "phrase_expression", "long_vowel_mark", "breath_marks", "fast_diphthongs",
                "english_kana", "section_style", "verse_style_shift", "chorus_style_shift", "even_takes",
                "harmony_variety", "harmony_double", "sung_pads", "adlibs", "syllable_dynamics",
                "recorded_breaths", "psola_reshape", "own_vocal", "own_vocal_align", "phrase_fixes", "style",
                "telephone_fx", "stutter_fx", "hard_tune", "formant_fx", "vocal_swing", "breathiness", "shimmer")


def _vocal_key(settings: SongSettings, tracks: dict) -> str:
    import hashlib
    import json

    from vocal_synthesizer import neutrino_info
    digest = hashlib.sha1()
    for name in VOCAL_CODE:
        try:
            with open(os.path.join(config.BASE_DIR, name), "rb") as f:
                digest.update(f.read())
        except OSError:
            digest.update(name.encode())
    plan = tracks.get("plan")
    data = {name: getattr(settings, name) for name in VOCAL_FIELDS}
    data["notes"] = [tracks.get(k) for k in NOTE_KEYS]
    data["sections"] = [(sec.kind, sec.start, sec.end) for sec in plan.sections] if plan else []
    data["neutrino"] = neutrino_info(settings.neutrino_dir())
    data["swing"] = _swing_amount(settings)
    if settings.own_vocal and os.path.isfile(settings.own_vocal):
        data["own_vocal_file"] = (os.path.getmtime(settings.own_vocal), os.path.getsize(settings.own_vocal))
    digest.update(json.dumps(data, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _sung_before(out: str, key: str) -> bool:
    import json
    try:
        with open(os.path.join(out, VOCAL_KEY), encoding="utf-8") as f:
            found = json.load(f)
    except (OSError, ValueError):
        return False
    files = found.get("files") or []
    return found.get("key") == key and "vocals.wav" in files and all(os.path.exists(os.path.join(out, n)) for n in files)


def _remember_vocals(out: str, key: str) -> None:
    import json
    files = [name for name in VOCAL_FILES if os.path.exists(os.path.join(out, name))]
    try:
        with open(os.path.join(out, VOCAL_KEY), "w", encoding="utf-8") as f:
            json.dump({"key": key, "files": files}, f)
    except OSError as e:
        log.debug("Fingerabdruck des Gesangs nicht gespeichert: %s", e)


def _synthesize_vocals(settings: SongSettings, tracks: dict, out: str) -> Optional[str]:
    vocals_wav = os.path.join(out, "vocals.wav")
    melody_data = tracks.get("melody_data", [])
    silben = tracks.get("silben", [])
    key = _vocal_key(settings, tracks) if settings.reuse_steps and settings.channels["vocals"].enabled else None
    if key and _sung_before(out, key):
        log.info("Gesang unverändert, nicht neu gesungen")
        return vocals_wav
    import vocal_check
    for name in VOCAL_FILES + (VOCAL_KEY, vocal_check.SUNG_FILE):
        remove_file(os.path.join(out, name))
    if not settings.channels["vocals"].enabled:
        log.info("Gesang ist ausgeschaltet.")
        return None
    if not melody_data or not silben:
        log.warning("Keine Melodie oder keine Silben vorhanden, überspringe den Gesang.")
        return None

    from vocal_synthesizer import erstelle_musicxml, stimmlage
    _, _, transpose = stimmlage(settings.singer)
    xml = erstelle_musicxml(melody_data, silben, settings.bpm, os.path.join(out, "vocals.xml"), transpose,
                            neutrino_score.options(settings))

    import own_vocal
    own = own_vocal.available(settings.own_vocal)
    if settings.own_vocal and not own:
        log.warning("Eigene Gesangsspur nicht gefunden: %s. Die Engine singt.", settings.own_vocal)
    engines = {"NEUTRINO": _sing_neutrino, "VOICEVOX": _sing_voicevox, "DiffSinger": _sing_diffsinger}
    sung = False
    engine = "Vorschau"
    _takes_used.clear()
    for name in ENGINE_ORDER.get(settings.vocal_engine, ENGINE_ORDER["NEUTRINO"]):
        try:
            voice = engines[name](settings, tracks, out, vocals_wav, xml, lead=not own)
            sung, engine = True, name
            if name == "NEUTRINO":
                _prune_takes(out)
            if not own:
                vocal_check.record(out, settings, name, voice or "")
            break
        except Exception as e:  # noqa: BLE001 – dann singt die nächste Engine
            log.warning("%s nicht verfügbar: %s", name, e)
            for leftover in VOCAL_FILES:
                remove_file(os.path.join(out, leftover))
    if own:
        return _place_own_vocal(settings, tracks, out, vocals_wav, key if sung else None)
    if not sung:
        if settings.vocal_engine != "Vorschau":
            log.warning("Weder NEUTRINO noch VOICEVOX singen, nutze die lokale Vorschau-Stimme.")
        if not _sing_preview(settings, tracks, vocals_wav):
            return None
        vocal_check.record(out, settings, "Vorschau")
    _liven(settings, tracks, out, vocals_wav, sung_dynamics=engine == "VOICEVOX" and _voicevox_dynamics(settings))
    _style_effects(settings, tracks, vocals_wav)
    _vocal_swing(settings, tracks, out)
    if sung and key:
        _remember_vocals(out, key)     # die Vorschau-Stimme nicht: fehlte NEUTRINO nur kurz, singt es beim nächsten Mal
    return vocals_wav


def _place_own_vocal(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, key: Optional[str]) -> str:
    """Die eigene Gesangsspur (E1) als Hauptstimme; die Begleitstimmen hat die Engine schon gesungen, soweit es eine
    gab. Die Spur bleibt, wie sie ist: kein Ausdruck, keine Atmer, nur der Chor im letzten Refrain kann aus ihr
    entstehen."""
    import own_vocal
    import vocal_check
    import voice_fx
    remove_file(os.path.join(out, "vocals_double.wav"))          # die Doppelung wäre die Engine, nicht die eigene Spur
    notes = voice_fx.timeline(tracks["melody_data"], settings.bpm)
    own_vocal.place(settings.own_vocal, notes, settings.bpm, vocals_wav, settings.own_vocal_align)
    vocal_check.record(out, settings, "Eigene Spur", os.path.basename(settings.own_vocal))
    choir = os.path.join(out, "vocals_chor.wav")
    window = final_chorus(tracks.get("plan"))
    if settings.final_choir and window and not os.path.exists(choir):
        spb = 60.0 / settings.bpm
        try:
            voice_fx.choir_from_lead(vocals_wav, choir, (window[0] * spb, window[1] * spb))
        except Exception as e:  # noqa: BLE001
            log.warning("Chor im letzten Refrain fehlgeschlagen: %s", e)
    if key:
        _remember_vocals(out, key)
    return vocals_wav


def _sing_preview(settings: SongSettings, tracks: dict, vocals_wav: str) -> bool:
    from vocal_synthesizer import generiere_lokale_vocals
    try:
        generiere_lokale_vocals(
            tracks["melody_data"], tracks["silben"], settings.bpm, vocals_wav,
            breathiness=settings.breathiness, shimmer=settings.shimmer, vibrato=settings.vibrato,
            glide=settings.glide,
        )
    except Exception as e:  # noqa: BLE001
        log.error("Lokale Stimme fehlgeschlagen, der Song entsteht ohne Gesang: %s", e)
        return False
    return os.path.exists(vocals_wav)


def _liven(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, sung_dynamics: bool = False) -> None:
    """Was jede Engine bekommt: Chor im letzten Refrain (aus der eigenen Stimme, wenn die Engine keinen gesungen
    hat), Ausdruck pro Phrase und Atmer vor den Phrasen. sung_dynamics: die Engine hat Lautstärke pro Silbe und
    Ausdruck pro Phrase schon selbst gesungen (VOICEVOX, F2)."""
    import voice_fx
    if sung_dynamics:
        log.info("VOICEVOX singt die Lautstärke pro Silbe und den Ausdruck pro Phrase selbst")
    elif settings.syllable_dynamics and voice_fx.syllable_dynamics(vocals_wav, tracks["melody_data"],
                                                                   tracks["silben"], settings.bpm):
        log.info("Lautstärke pro Silbe: betonte Silben lauter, weicher Einsatz am Phrasenanfang")
    if settings.phrase_expression and tracks.get("plan") is not None and not sung_dynamics:
        notes = voice_fx.timeline(tracks["melody_data"], settings.bpm)
        if voice_fx.express(vocals_wav, notes, sections_in_seconds(tracks["plan"])):
            log.info("Ausdruck pro Phrase: zum Höhepunkt lauter, am Ende weicher")
    choir = os.path.join(out, "vocals_chor.wav")
    window = final_chorus(tracks.get("plan"))
    if settings.final_choir and window and not os.path.exists(choir):
        spb = 60.0 / settings.bpm
        try:
            if voice_fx.choir_from_lead(vocals_wav, choir, (window[0] * spb, window[1] * spb)):
                log.info("Chor im letzten Refrain aus der eigenen Stimme")
        except Exception as e:  # noqa: BLE001
            log.warning("Chor im letzten Refrain fehlgeschlagen: %s", e)
    if settings.breaths:
        count = voice_fx.add_breaths(vocals_wav, voice_fx.timeline(tracks["melody_data"], settings.bpm),
                                     seed=settings.seed or 0, recorded=settings.recorded_breaths)
        log.info("%d Atmer vor den Phrasen%s", count,
                 " (aufgenommen)" if settings.recorded_breaths and voice_fx.breath_samples(48000) else "")


def _style_effects(settings: SongSettings, tracks: dict, vocals_wav: str) -> None:
    """Stil-Effekte (style_fx.py) auf die Hauptstimme: Telefon, Stutter, harter Tune, Formanten."""
    import style_fx
    import voice_fx
    effects = style_fx.effects_for(settings.style, settings)
    if not effects or tracks.get("plan") is None:
        return
    try:
        done = style_fx.apply(vocals_wav, voice_fx.timeline(tracks["melody_data"], settings.bpm),
                              sections_in_seconds(tracks["plan"]), settings.bpm, effects)
    except Exception as e:  # noqa: BLE001 – ein Effekt ist kein Grund, den Gesang aufzugeben
        log.warning("Stil-Effekte übersprungen: %s", e)
        return
    if done:
        log.info("Stil-Effekte (%s): %s", settings.style, ", ".join(done))


def _swing_amount(settings: SongSettings) -> float:
    """Wie stark die Band swingt (wie in orchestrate_song); unter VOCAL_SWING_FROM bleibt der Gesang gerade."""
    from styles import get_style
    amount = min(1.0, get_style(settings.style).swing + settings.swing)
    return round(amount, 4) if settings.vocal_swing and amount >= VOCAL_SWING_FROM else 0.0


def _vocal_swing(settings: SongSettings, tracks: dict, out: str) -> None:
    """A6: der Gesang swingt mit der Band. Jede Spur nach ihren eigenen Noten; Flächen und Adlibs bleiben."""
    amount = _swing_amount(settings)
    if not amount:
        return
    import voice_fx
    from orchestrator import SWING_MAX
    shift = amount * SWING_MAX * 0.5
    moved = 0
    for line, files in VOCAL_SWING_LINES.items():
        notes = voice_fx.timeline(tracks.get(line) or [], settings.bpm)
        if not voice_fx.swung(notes, settings.bpm):
            continue
        for name in files:
            path = os.path.join(out, name)
            if os.path.exists(path):
                try:
                    moved += voice_fx.swing(path, notes, settings.bpm, shift)
                except Exception as e:  # noqa: BLE001 – dann bleibt diese Spur gerade
                    log.warning("Swing im Gesang übersprungen (%s): %s", name, e)
    if moved:
        log.info("Gesang swingt mit: %d Töne um %.0f ms später", moved, shift * 60000 / settings.bpm)


# ── NEUTRINO ────────────────────────────────────────────────────────────────────
def _sing_neutrino(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, xml: str, lead: bool = True) -> str:
    """Rückgabe: wer gesungen hat (die Stimme, im Duett beide). lead=False: nur die Begleitstimmen, die Hauptstimme
    kommt aus einer eigenen Spur (E1)."""
    from vocal_synthesizer import neutrino_hinweis, neutrino_info, stimmlage
    if not xml:
        raise RuntimeError("ohne music21 gibt es keine Noten für NEUTRINO")
    neutrino_dir = settings.neutrino_dir()
    duet = _duet_partner(settings, neutrino_dir) if lead else None
    voice = settings.singer + (f" und {duet}" if duet else "")
    log.info("%s; singe mit %s", neutrino_info(neutrino_dir), voice)
    if neutrino_hinweis(neutrino_dir):
        log.warning(neutrino_hinweis(neutrino_dir))
    if duet:
        _sing_duet(settings, tracks, out, neutrino_dir, duet, vocals_wav)
    elif lead:
        plan = tracks.get("plan")
        _neutrino_lead(settings, tracks["melody_data"], xml, vocals_wav, neutrino_dir, settings.singer,
                       chorus_windows(plan), tracks["silben"], sections_in_seconds(plan) if plan else ())
    harmony_wav = os.path.join(out, "vocals_harmony.wav")
    if (settings.harmonies or duet) and tracks.get("harmony_data"):
        # im Duett singt die zweite Stimme die zweite Stimme im Refrain
        singer = duet or settings.singer
        _sing_harmony(settings, tracks, out, neutrino_dir, os.path.join(neutrino_dir, "model", singer),
                      stimmlage(singer)[2], harmony_wav)
    if settings.final_choir:
        _neutrino_choir(settings, tracks, out, neutrino_dir, duet)
    _neutrino_backing(settings, tracks, out, neutrino_dir, duet)
    return voice


def _neutrino_lead(settings: SongSettings, data: list, xml: str, wav: str, neutrino_dir: str, singer: str,
                   double_windows: list = (), silben: Optional[list] = None, sections: list = ()) -> None:
    """Eine Hauptstimme mit NEUTRINO, danach Vibrato und Übergänge.
    StyleShift pro Sektion (sections: [(Start, Ende in Sekunden, Art)], braucht silben): jede Gruppe von Phrasen mit
    demselben StyleShift singt NEUTRINO aus einer eigenen MusicXML, in der die anderen Töne Pausen sind; geschnitten
    wird in den Pausen wie beim Comping. Bei mehreren Fassungen kommt jede Phrase aus der saubersten (Comping, ohne:
    die sauberste ganze Fassung je Gruppe); in den double_windows (Sekunden) wird aus den zweitbesten Phrasen eine
    echte Doppelung (vocals_double.wav)."""
    import voice_fx
    from vocal_synthesizer import erstelle_musicxml, stimmlage
    transpose = stimmlage(singer)[2]
    model_dir = os.path.join(neutrino_dir, "model", singer)
    notes = voice_fx.timeline(data, settings.bpm, transpose)
    shifts = _phrase_shifts(settings, notes, sections if silben is not None else ())
    fixes = _phrase_fixes(settings, notes, singer) if silben is not None else []
    fixed = set().union(*(keep for _, _, keep in fixes)) if fixes else set()
    groups = {}                                       # StyleShift → Nummern der Töne, die damit gesungen werden
    for i, shift in enumerate(shifts):
        groups.setdefault(shift, set()).add(i)
    everything = set(range(len(notes)))
    parts = [_Part(settings.style_shift if not groups else next(iter(groups)), xml, everything - fixed, model_dir)]
    if len(groups) > 1:
        parts = []
        for k, (shift, keep) in enumerate(sorted(groups.items())):
            part_data, part_silben = voice_fx.only_notes(data, silben, keep)
            part_xml = erstelle_musicxml(part_data, part_silben, settings.bpm, wav[:-4] + f"_stil_{k + 1}.xml",
                                         transpose, neutrino_score.options(settings))
            parts.append(_Part(shift, part_xml, keep - fixed, model_dir))     # die MusicXML bleibt, wie sie war
    for k, (shift, other, keep) in enumerate(fixes):
        part_data, part_silben = voice_fx.only_notes(data, silben, keep)
        part_xml = erstelle_musicxml(part_data, part_silben, settings.bpm, wav[:-4] + f"_phrase_{k + 1}.xml",
                                     stimmlage(other)[2], neutrino_score.options(settings))
        parts.append(_Part(shift, part_xml, keep, os.path.join(neutrino_dir, "model", other), True))
    try:
        takes = _sing_takes(settings, parts, wav, neutrino_dir)
        _choose_takes(settings, takes, parts, notes, wav, singer, double_windows)
    finally:
        for part in parts:
            if part.xml != xml:
                remove_file(part.xml)
    double = os.path.join(os.path.dirname(wav), "vocals_double.wav")
    if os.path.exists(double):
        voice_fx.reshape(double, notes, settings.vibrato, settings.glide, settings.psola_reshape)
    voice_fx.reshape(wav, notes, settings.vibrato, settings.glide, settings.psola_reshape)


class _Part(NamedTuple):
    """Was NEUTRINO für eine Hauptstimme aus einer MusicXML singt: keep sind die Töne, die aus ihr kommen.
    fixed: eine von Hand neu gesungene Phrase (E3); ihre Töne kommen immer aus dieser Aufnahme."""
    shift: int
    xml: str
    keep: set
    model_dir: str
    fixed: bool = False


def _phrase_fixes(settings: SongSettings, notes: list, singer: str) -> list:
    """[(StyleShift, Stimme, Nummern der Töne)] der Phrasen, die von Hand neu gesungen werden (settings.phrase_fixes:
    {Schlag einer Note der Phrase: {"style_shift", "singer"}}). Eine fehlende Stimme singt als singer."""
    import voice_fx
    if not settings.phrase_fixes or not notes:
        return []
    spb = 60.0 / settings.bpm
    index = {id(n): i for i, n in enumerate(notes)}
    groups = voice_fx.phrases(notes)
    out, seen = [], set()
    for key, fix in sorted(settings.phrase_fixes.items(), key=lambda kv: float(kv[0])):
        t = float(key) * spb
        group = next((g for g in groups if g[0].start - 0.05 <= t <= g[-1].end + 0.05), None)
        if group is None or id(group[0]) in seen:
            continue
        seen.add(id(group[0]))
        other = fix.get("singer") or singer
        if not os.path.isdir(os.path.join(settings.neutrino_dir(), "model", other)):
            log.warning("Stimme %s für die Phrase bei %.1f s fehlt, dort singt %s", other, group[0].start, singer)
            other = singer
        shift = int(np.clip(fix.get("style_shift", settings.style_shift), -6, 6))
        out.append((shift, other, {index[id(n)] for n in group}))
        log.info("Phrase bei %.1f s neu gesungen: %s, StyleShift %+d", group[0].start, other, shift)
    return out


def _phrase_shifts(settings: SongSettings, notes: list, sections: list) -> list:
    """StyleShift je Ton: der gewählte, mit StyleShift pro Sektion plus der Versatz der Sektion seiner Phrase."""
    import voice_fx
    base = settings.style_shift
    if not settings.section_style or not sections:
        return [base] * len(notes)
    offsets = {"Verse": settings.verse_style_shift, "Chorus": settings.chorus_style_shift}
    groups = voice_fx.phrases(notes)
    out, used = [], {}
    for group, kind in zip(groups, voice_fx.phrase_kinds(groups, sections)):
        shift = int(np.clip(base + offsets.get(kind, 0), -6, 6))
        used[kind or "ohne Sektion"] = shift
        out += [shift] * len(group)
    if len(set(out)) > 1:
        log.info("StyleShift pro Sektion: %s", ", ".join(f"{kind} {shift:+d}" for kind, shift in used.items()))
    return out


def _sing_takes(settings: SongSettings, parts: list, wav: str, neutrino_dir: str) -> list:
    """Alle Fassungen aller Gruppen (_Part) singen. Fassungen ohne Farbsprung (even_takes) singen mit demselben
    StyleShift; singt NEUTRINO dabei jedes Mal dasselbe (beim ersten Mal geprüft und gemerkt), eine Stufe heller und
    dunkler. Eine neu gesungene Phrase singt nur einmal. Rückgabe: [(Gruppe, StyleShift, WAV)]."""
    import voice_fx
    from vocal_synthesizer import LETZTER_LAUF
    count = max(1, settings.vocal_takes)
    even = settings.even_takes and count > 1
    repeats = _neutrino_repeats(neutrino_dir) if even else None
    takes, warned = [], False
    for p, part in enumerate(parts):
        shift, part_xml, model_dir = part.shift, part.xml, part.model_dir
        plan = [shift] * count if even and repeats is not True else voice_fx.take_shifts(shift, count)
        if part.fixed:
            plan = [shift]
        k = 0
        while k < len(plan):
            take = wav if len(parts) == 1 and count == 1 else wav[:-4] + f"_fassung_{p + 1}_{k + 1}.wav"
            slot = "phrase" if part.fixed else f"{os.path.basename(wav)}#{k + 1}"
            LETZTER_LAUF["styleshift"] = None
            try:
                _neutrino(settings, part_xml, take, neutrino_dir, model_dir, plan[k], slot)
            except Exception as e:  # noqa: BLE001 – eine misslungene Fassung ist kein Grund aufzuhören
                if k == 0:
                    raise
                log.warning("Fassung %d nicht gesungen: %s", k + 1, e)
                k += 1
                continue
            if LETZTER_LAUF.get("styleshift") is False and not warned:
                warned = True
                log.warning("Diese NEUTRINO-Ausgabe nimmt keinen StyleShift an (z. B. die mit Tuning-Tool): "
                            "Strophe und Refrain klingen gleich, der Rest läuft wie gewohnt")
            if even and repeats is None and k == 1 and plan[1] == plan[0]:
                repeats = voice_fx.same_audio(takes[-1][2], take)
                _remember_repeats(neutrino_dir, repeats)
                if repeats:
                    log.info("NEUTRINO singt bei gleichem StyleShift jedes Mal dasselbe; die weiteren Fassungen "
                             "singen eine Stufe heller und dunkler")
                    remove_file(take)
                    plan = plan[:1] + voice_fx.take_shifts(shift, count)[1:]
                    continue
            takes.append((p, plan[k], take))
            k += 1
    return takes


def _choose_takes(settings: SongSettings, takes: list, parts: list, notes: list, wav: str, singer: str,
                  double_windows: list) -> None:
    """Aus den Fassungen die Hauptstimme nach wav schreiben und die Fassungen löschen."""
    import voice_fx
    if len(takes) == 1:
        if takes[0][2] != wav:
            os.replace(takes[0][2], wav)
        return
    tolerance = voice_fx.GROSS_CENTS if settings.even_takes else 0.0
    double = os.path.join(os.path.dirname(wav), "vocals_double.wav")
    groups = voice_fx.phrases(notes)
    first = {}                                     # Nummer eines Tons → seine Phrase
    for g, group in enumerate(groups):
        first.update({id(n): g for n in group})

    def forced(chosen: list) -> dict:
        """{Phrase: Fassung} für die von Hand neu gesungenen Phrasen; chosen: die Fassungen, aus denen geschnitten wird."""
        out = {}
        for k, (p, _, _) in enumerate(chosen):
            if parts[p].fixed:
                out.update({first[id(notes[i])]: k for i in parts[p].keep})
        return out
    try:
        if settings.vocal_comping:
            choice = voice_fx.comp([t for _, _, t in takes], notes, wav, double, double_windows, tolerance,
                                   forced(takes))
            counts = {}
            for k in choice:
                counts[k] = counts.get(k, 0) + 1
            log.info("%s: Phrasen aus den saubersten Fassungen (%s)", singer,
                     ", ".join(f"StyleShift {takes[k][1]:+d}: {c}×" for k, c in sorted(counts.items())))
            return
        best = []                                   # die sauberste ganze Fassung je Gruppe
        for p, part in enumerate(parts):
            mine = [t for t in takes if t[0] == p]
            if not mine:
                continue
            group_notes = [n for i, n in enumerate(notes) if i in part.keep] or notes
            scores = [voice_fx.pitch_error(t[2], group_notes, tolerance) for t in mine]
            k = int(np.argmin(scores))
            best.append(mine[k])
            if not part.fixed:
                log.info("%s: Fassung %d klingt am saubersten (StyleShift %+d)", singer, k + 1, mine[k][1])
        if len(best) == 1:
            os.replace(best[0][2], wav)
        else:
            voice_fx.comp([t for _, _, t in best], notes, wav, forced=forced(best))
    finally:
        for _, _, take in takes:
            if take != wav:
                remove_file(take)


# Was NEUTRINO beim letzten Lauf gesungen hat (im Song-Ordner, FLAC): dieselben Noten mit derselben Stimme und demselben
# StyleShift werden nicht noch einmal gesungen. So singt NEUTRINO für eine neu gesungene Phrase (E3) nur sie.
TAKE_CACHE = "_gesungen"
_takes_used: set = set()


def _neutrino(settings: SongSettings, xml: str, wav: str, neutrino_dir: str, model_dir: str, shift: int,
              slot: Optional[str] = None) -> None:
    """NEUTRINO singt xml nach wav, oder die Aufnahme kommt aus TAKE_CACHE. slot: welche Aufnahme das ist (z. B.
    die zweite Fassung der Hauptstimme); Standard der Dateiname von wav."""
    import soundfile as sf

    import vocal_synthesizer
    cached = None
    support = _support_model(settings, neutrino_dir, model_dir)
    slot = (slot or os.path.basename(wav)) + (f"|{support}" if support else "")
    key = _take_key(xml, neutrino_dir, model_dir, shift, slot) if settings.reuse_steps else None
    if key:
        cached = os.path.join(os.path.dirname(wav), TAKE_CACHE, key + ".flac")
        if os.path.exists(cached):
            try:
                audio, rate = sf.read(cached, dtype="float32")
                sf.write(wav, audio, rate, subtype="FLOAT")
                _takes_used.add(os.path.abspath(cached))
                return
            except Exception as e:  # noqa: BLE001 – dann eben neu singen
                log.debug("Gesungene Aufnahme %s nicht lesbar: %s", cached, e)
    vocal_synthesizer.neutrino_synthese(xml, wav, neutrino_dir, model_dir, style_shift=shift,
                                        **({"support_pfad": support} if support else {}))
    if cached:
        try:
            os.makedirs(os.path.dirname(cached), exist_ok=True)
            audio, rate = sf.read(wav, dtype="float32")
            sf.write(cached, audio, rate, format="FLAC", subtype="PCM_24")
            _takes_used.add(os.path.abspath(cached))
        except Exception as e:  # noqa: BLE001
            log.debug("Aufnahme nicht zwischengespeichert: %s", e)


def _support_model(settings: SongSettings, neutrino_dir: str, model_dir: str) -> Optional[str]:
    """B5: Ordner der Support-Stimme, wenn eine gewählt ist und NEUTRINO mit der Hauptstimme singt (nicht im Duett
    mit der zweiten Stimme); None sonst."""
    name = (settings.support_singer or "").strip()
    if not name or name.upper() == settings.singer.upper():
        return None
    if os.path.basename(os.path.normpath(model_dir)).upper() != settings.singer.upper():
        return None
    path = os.path.join(neutrino_dir, "model", name)
    if not os.path.isdir(path):
        if name not in _support_missing:
            _support_missing.add(name)
            log.warning("Support-Stimme %s nicht gefunden (Ordner model von NEUTRINO), singt ohne", name)
        return None
    return path


_support_missing: set = set()


def _take_key(xml: str, neutrino_dir: str, model_dir: str, shift: int, slot: str) -> Optional[str]:
    """Schlüssel einer Aufnahme; None, wenn die MusicXML nicht lesbar ist (dann wird nichts gemerkt)."""
    import hashlib
    import re
    try:
        with open(xml, encoding="utf-8") as f:
            text = f.read()
    except (OSError, ValueError):
        return None
    text = re.sub(r"<encoding-date>.*?</encoding-date>", "", text)
    text = re.sub(r'id="[^"]*"', 'id=""', text)              # music21 vergibt jedes Mal neue Kennungen
    digest = hashlib.sha1(text.encode("utf-8"))
    digest.update(f"|{shift}|{os.path.abspath(model_dir)}|{_neutrino_id(neutrino_dir)}|{slot}".encode("utf-8"))
    return digest.hexdigest()


def _prune_takes(out: str) -> None:
    """Aus TAKE_CACHE fliegt, was dieser Lauf nicht gebraucht hat."""
    folder = os.path.join(out, TAKE_CACHE)
    if not os.path.isdir(folder):
        return
    for name in os.listdir(folder):
        path = os.path.abspath(os.path.join(folder, name))
        if path not in _takes_used:
            remove_file(path)
    if not os.listdir(folder):
        os.rmdir(folder)


NEUTRINO_NOTES = "neutrino.json"     # im Datenordner: was über die installierte NEUTRINO-Ausgabe bekannt ist


def _neutrino_id(neutrino_dir: str) -> str:
    exe = os.path.join(neutrino_dir, "bin", "NEUTRINO.exe")
    try:
        return f"{os.path.abspath(neutrino_dir)}|{os.path.getsize(exe)}|{int(os.path.getmtime(exe))}"
    except OSError:
        return os.path.abspath(neutrino_dir)


def _neutrino_repeats(neutrino_dir: str) -> Optional[bool]:
    """Singt diese NEUTRINO-Ausgabe bei gleichem StyleShift jedes Mal dasselbe? None = noch nicht geprüft."""
    import json
    try:
        with open(os.path.join(config.DATA_DIR, NEUTRINO_NOTES), encoding="utf-8") as f:
            return json.load(f).get("repeats", {}).get(_neutrino_id(neutrino_dir))
    except (OSError, ValueError, AttributeError):
        return None


def _remember_repeats(neutrino_dir: str, repeats: bool) -> None:
    import json
    path = os.path.join(config.DATA_DIR, NEUTRINO_NOTES)
    try:
        with open(path, encoding="utf-8") as f:
            notes = json.load(f)
    except (OSError, ValueError):
        notes = {}
    notes.setdefault("repeats", {})[_neutrino_id(neutrino_dir)] = bool(repeats)
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=1)
    except OSError as e:
        log.debug("%s nicht gespeichert: %s", NEUTRINO_NOTES, e)


def _chorus_shift(settings: SongSettings) -> int:
    """StyleShift für alles, was nur im Refrain singt (zweite Stimme, Chor)."""
    shift = settings.style_shift + (settings.chorus_style_shift if settings.section_style else 0)
    return int(np.clip(shift, -6, 6))


def _neutrino_choir(settings: SongSettings, tracks: dict, out: str, neutrino_dir: str, duet: Optional[str]) -> None:
    """Im letzten Refrain singen zwei weitere Stimmen die Melodie mit (andere installierte Stimmen, sonst dieselbe
    heller und dunkler)."""
    import soundfile as sf
    import voice_fx
    from vocal_synthesizer import erstelle_musicxml, installed_singers, stimmlage
    window = final_chorus(tracks.get("plan"))
    if window is None:
        return
    data, silben = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], *window)
    if not data:
        return
    singers = [n for n in installed_singers(neutrino_dir) if n != settings.singer
               and os.path.isdir(os.path.join(neutrino_dir, "model", n))]
    singers.sort(key=lambda n: n != duet)
    shift = _chorus_shift(settings)
    voices = [(n, shift) for n in singers[:2]] or [(settings.singer, max(-6, shift - 2)), (settings.singer, min(6, shift + 2))]
    sung, rate = [], 48000
    for k, (singer, shift) in enumerate(voices):
        xml = os.path.join(out, f"vocals_chor_{k + 1}.xml")
        wav = os.path.join(out, f"vocals_chor_{k + 1}.wav")
        try:
            erstelle_musicxml(data, silben, settings.bpm, xml, stimmlage(singer)[2], neutrino_score.options(settings))
            _neutrino(settings, xml, wav, neutrino_dir, os.path.join(neutrino_dir, "model", singer), shift)
            audio, rate = sf.read(wav, dtype="float32", always_2d=True)
            sung.append(audio.mean(axis=1))
        except Exception as e:  # noqa: BLE001
            log.warning("Chorstimme %s fehlgeschlagen: %s", singer, e)
        finally:
            remove_file(wav)
            remove_file(xml)
    if sung:
        voice_fx.write_choir(os.path.join(out, "vocals_chor.wav"), sung, rate, window[0] * 60.0 / settings.bpm)
        log.info("Chor im letzten Refrain: %s", ", ".join(f"{n} ({s:+d})" for n, s in voices))


# ── VOICEVOX ────────────────────────────────────────────────────────────────────
# ── DiffSinger (F1, Versuch) ────────────────────────────────────────────────────
def _sing_diffsinger(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, xml: str = "",
                     lead: bool = True) -> str:
    """Hauptstimme und zweite Stimme im Refrain mit einer DiffSinger-Stimme für OpenUtau (diffsinger.py)."""
    import diffsinger
    if not diffsinger.available():
        raise RuntimeError("DiffSinger braucht onnxruntime")
    folder = diffsinger.find(settings.diffsinger_voice)
    if not folder:
        raise FileNotFoundError("keine DiffSinger-Stimme gefunden (OpenUtau, Ordner Singers)")
    name = os.path.basename(os.path.normpath(folder))
    log.info("Singe mit DiffSinger: %s", name)
    if lead:
        diffsinger.sing(tracks["melody_data"], tracks["silben"], settings.bpm, vocals_wav, folder,
                        vibrato=settings.vibrato, glide=settings.glide)
    if settings.harmonies and tracks.get("harmony_data"):
        try:
            diffsinger.sing(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                            os.path.join(out, "vocals_harmony.wav"), folder, vibrato=settings.vibrato,
                            glide=settings.glide)
            log.info("Zweite Stimme im Refrain gesungen.")
        except Exception as e:  # noqa: BLE001
            log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)
    return name


def _voicevox_dynamics(settings: SongSettings) -> bool:
    """F2: singt VOICEVOX die Lautstärke pro Silbe und den Ausdruck pro Phrase selbst?"""
    return settings.voicevox_dynamics and (settings.syllable_dynamics or settings.phrase_expression)


def _voicevox_volume(settings: SongSettings, tracks: dict):
    """Die Lautstärke je Rahmen für VOICEVOX (F2), oder None."""
    if not _voicevox_dynamics(settings):
        return None
    import voice_fx
    sections = sections_in_seconds(tracks["plan"]) if settings.phrase_expression and tracks.get("plan") else []

    def volume(loud, frame, offset):
        times = offset + np.arange(len(loud)) * frame
        db = voice_fx.dynamics_db(tracks["melody_data"], tracks["silben"], settings.bpm, sections, times,
                                  syllables=settings.syllable_dynamics, expression=bool(sections))
        return loud * 10 ** (db / 20)
    return volume


def _sing_voicevox(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, xml: str = "",
                   lead: bool = True) -> str:
    import voice_fx
    import voicevox
    url = settings.voicevox_url or voicevox.URL
    singer, name = voicevox.pick_singer(url, settings.voicevox_singer)
    log.info("Singe mit VOICEVOX: %s", name)
    notes = voice_fx.timeline(tracks["melody_data"], settings.bpm)
    shape = None
    if abs(settings.vibrato - 1.0) > 1e-3 or abs(settings.glide - 1.0) > 1e-3:
        def shape(f0, frame, offset):
            return voice_fx.shape_pitch(f0, frame, notes, settings.vibrato, settings.glide, offset)
    if lead:
        voicevox.sing(tracks["melody_data"], tracks["silben"], settings.bpm, vocals_wav, url, singer, pitch=shape,
                      volume=_voicevox_volume(settings, tracks))
    if settings.harmonies and tracks.get("harmony_data"):
        try:
            voicevox.sing(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                          os.path.join(out, "vocals_harmony.wav"), url, singer)
            log.info("Zweite Stimme im Refrain gesungen.")
        except Exception as e:  # noqa: BLE001
            log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)
    window = final_chorus(tracks.get("plan"))
    if settings.final_choir and window:
        _voicevox_choir(settings, tracks, out, url, singer, window)
    return name


def _voicevox_choir(settings: SongSettings, tracks: dict, out: str, url: str, singer: int, window: tuple) -> None:
    import soundfile as sf
    import voice_fx
    import voicevox
    data, silben = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], *window)
    voices, rate = [], 24000
    for k, other in enumerate(voicevox.others(url, singer)):
        wav = os.path.join(out, f"vocals_chor_{k + 1}.wav")
        try:
            voicevox.sing(data, silben, settings.bpm, wav, url, other)
            audio, rate = sf.read(wav, dtype="float32", always_2d=True)
            voices.append(audio.mean(axis=1))
        except Exception as e:  # noqa: BLE001
            log.warning("Chorstimme fehlgeschlagen: %s", e)
        finally:
            remove_file(wav)
    if voices:
        voice_fx.write_choir(os.path.join(out, "vocals_chor.wav"), voices, rate, window[0] * 60.0 / settings.bpm)
        log.info("Chor im letzten Refrain mit %d weiteren VOICEVOX-Stimmen", len(voices))


def _duet_partner(settings: SongSettings, neutrino_dir: str) -> Optional[str]:
    """Die zweite Stimme fürs Duett, wenn sie gewählt und installiert ist."""
    partner = settings.duet_singer
    if not partner or partner == settings.singer:
        return None
    if not os.path.isdir(os.path.join(neutrino_dir, "model", partner)):
        log.warning("Duett-Stimme %s fehlt im NEUTRINO-Ordner, %s singt allein", partner, settings.singer)
        return None
    return partner


DUET_PAN = 0.2       # die beiden Stimmen stehen leicht links und rechts


def _sing_duet(settings: SongSettings, tracks: dict, out: str, neutrino_dir: str, partner: str, vocals_wav: str) -> None:
    """Beide Stimmen singen ihre Teile (melody_writer.duet_voice); zusammen ergeben sie vocals.wav."""
    import soundfile as sf
    from melody_writer import split_for_duet
    from vocal_synthesizer import erstelle_musicxml, stimmlage
    parts = split_for_duet(tracks["plan"], tracks["melody_data"], tracks["silben"])
    audio, rate = [], None
    for k, (singer, (data, silben)) in enumerate(zip((settings.singer, partner), parts)):
        wav = os.path.join(out, f"vocals_duett_{k + 1}.wav")
        xml = erstelle_musicxml(data, silben, settings.bpm, os.path.join(out, f"vocals_duett_{k + 1}.xml"),
                                stimmlage(singer)[2], neutrino_score.options(settings))
        _neutrino_lead(settings, data, xml, wav, neutrino_dir, singer, (), silben, sections_in_seconds(tracks["plan"]))
        data_k, rate = sf.read(wav, dtype="float32", always_2d=True)
        mono = data_k.mean(axis=1)
        angle = (1 + (-DUET_PAN if k == 0 else DUET_PAN)) * np.pi / 4
        audio.append(np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1) * np.sqrt(2))
    length = max(len(a) for a in audio)
    mix = sum(np.pad(a, ((0, length - len(a)), (0, 0))) for a in audio)
    sf.write(vocals_wav, mix, rate, subtype="FLOAT")
    log.info("Duett: %s und %s", settings.singer, partner)


HARMONY_PAN = 0.6       # die gedoppelte Harmonie: eine Fassung links, eine rechts
PAD_PANS = (-0.6, 0.0, 0.6)


def _sing_harmony(settings, tracks, out, neutrino_dir, model_dir, transpose, harmony_wav) -> None:
    """Zweite Stimme im Refrain, mit NEUTRINO gesungen; mit harmony_double zweimal, links und rechts."""
    from vocal_synthesizer import erstelle_musicxml
    xml = erstelle_musicxml(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                            os.path.join(out, "vocals_harmony.xml"), transpose, neutrino_score.options(settings))
    shift = _chorus_shift(settings)
    try:
        _neutrino(settings, xml, harmony_wav, neutrino_dir, model_dir, shift)
        log.info("Zweite Stimme im Refrain gesungen.")
    except Exception as e:
        log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)
        return
    if not settings.harmony_double:
        return
    second = harmony_wav[:-4] + "_2b.wav"
    # singt NEUTRINO bei gleichem StyleShift jedes Mal dasselbe, klingt die zweite Fassung eine Stufe heller
    other = shift if _neutrino_repeats(neutrino_dir) is False else (shift + 1 if shift < 6 else shift - 1)
    try:
        _neutrino(settings, xml, second, neutrino_dir, model_dir, other)
        _stereo([harmony_wav, second], (-HARMONY_PAN, HARMONY_PAN), harmony_wav)
        log.info("Zweite Stimme gedoppelt, links und rechts")
    except Exception as e:  # noqa: BLE001 – dann eben ungedoppelt
        log.warning("Doppelung der zweiten Stimme fehlgeschlagen: %s", e)
    finally:
        remove_file(second)


def _stereo(paths: list, pans: tuple, out: str) -> None:
    """Mono-Fassungen nebeneinander im Panorama zu einer Stereo-Datei."""
    import soundfile as sf
    voices, rate = [], 48000
    for path in paths:
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
        voices.append(audio.mean(axis=1))
    length = max(len(v) for v in voices)
    mix = np.zeros((length, 2), dtype=np.float32)
    for mono, pan in zip(voices, pans):
        angle = (pan + 1) * np.pi / 4
        mix[:len(mono), 0] += mono * np.cos(angle)
        mix[:len(mono), 1] += mono * np.sin(angle)
    sf.write(out, mix * np.float32(np.sqrt(2) / len(voices) ** 0.5), rate, subtype="FLOAT")


def _neutrino_backing(settings: SongSettings, tracks: dict, out: str, neutrino_dir: str, duet: Optional[str]) -> None:
    """Begleitstimmen aus backing_vocals: Oktave im letzten Refrain, gesungene Flächen, Ad-libs."""
    singer = duet or settings.singer
    shift = _chorus_shift(settings)
    if settings.harmonies and tracks.get("octave_data"):
        if _sing_line(settings, tracks["octave_data"], tracks["octave_silben"], out, "vocals_harmony_2", neutrino_dir,
                      singer, shift):
            log.info("Im letzten Refrain singt die Oktave mit")
    lines = tracks.get("pads") or []
    if settings.sung_pads and lines:
        sung = [p for k, (data, silben) in enumerate(lines)
                if (p := _sing_line(settings, data, silben, out, f"vocals_flaechen_{k + 1}", neutrino_dir,
                                    settings.singer, max(-6, shift - 1)))]
        if sung:
            _stereo(sung, PAD_PANS if len(sung) == len(PAD_PANS) else tuple(np.linspace(-0.4, 0.4, len(sung))),
                    os.path.join(out, "vocals_flaechen.wav"))
            log.info("Gesungene Flächen im Refrain (%d Stimmen) statt des Keyboard-Chors", len(sung))
        for path in sung:
            remove_file(path)
    if settings.adlibs and tracks.get("adlib_data"):
        if _sing_line(settings, tracks["adlib_data"], tracks["adlib_silben"], out, "vocals_adlibs", neutrino_dir,
                      singer, min(6, shift + 1)):
            log.info("Ad-libs im letzten Refrain")


def _sing_line(settings: SongSettings, data: list, silben: list, out: str, name: str, neutrino_dir: str,
               singer: str, shift: int) -> Optional[str]:
    """Eine Begleitstimme mit NEUTRINO nach out/name.wav; None, wenn es nicht klappt."""
    from vocal_synthesizer import erstelle_musicxml, stimmlage
    if not any(p is not None for p, _ in data):
        return None
    xml = os.path.join(out, name + ".xml")
    wav = os.path.join(out, name + ".wav")
    try:
        erstelle_musicxml(data, silben, settings.bpm, xml, stimmlage(singer)[2], neutrino_score.options(settings))
        _neutrino(settings, xml, wav, neutrino_dir, os.path.join(neutrino_dir, "model", singer), shift)
        return wav
    except Exception as e:  # noqa: BLE001 – eine Begleitstimme ist kein Grund, den Song aufzugeben
        log.warning("%s nicht gesungen: %s", name, e)
        remove_file(wav)
        return None
    finally:
        remove_file(xml)

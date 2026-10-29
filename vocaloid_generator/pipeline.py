# pipeline.py – Der komplette Ablauf von den Einstellungen bis zur fertigen MP3.
# Kommandozeile (main.py) und Oberfläche (gui/page.py) rufen beide nur generate_song() auf. Den Gesang macht singing.py,
# die Instrumente rendering.py, die Angaben zum Mischen mixdown.py.
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

import cancel
import config
import mixdown
import rendering
import singing
from config import remove_file
from lyrics import options as lyric_options, parse_lyrics, shared_only
from orchestrator import orchestrate_song
from settings import DEFAULT_JITTER, INSTRUMENTS, SongSettings

log = logging.getLogger(__name__)

# Preset-Stile der App auf die Genres, die der Orchestrator kennt
STYLE_TO_GENRE = {
    "J-Pop Energy": "J-Pop",
    "Dark Vocaloid": "J-Pop",
    "Kawaii Chiptune": "EDM",
    "Rock": "Rock",
    "Ballade": "Lo-Fi",
    "City Pop": "Lo-Fi",
    "Future Bass": "EDM",
    "Drum and Bass": "EDM",
    "Lo-Fi": "Lo-Fi",
    "Idol-Pop": "J-Pop",
    "Wafuu-Rock": "Rock",
    "Electro-Swing": "EDM",
    "Hyperpop": "EDM",
}

ProgressFn = Callable[[float, str], None]

# Neuerungen aus 1.3.0, die die Noten ändern: orchestrate_song bekommt die eingeschalteten als extras
NEW_COMPOSITION = ("best_melody", "melody_pickups", "intro_riff", "kime", "melody_tensions", "melody_climax",
                   "chord_spice", "melody_triplets", "band_groove", "bass_runs", "band_runs", "anison_grooves",
                   "section_buildup")
# Neuerungen aus 1.4.0, die die Noten ändern (Charakter je Stil und Song)
NEW_140 = ("style_chords", "melody_character", "style_arrangement", "song_character")
# Neuerungen aus 1.5.0, die die Noten ändern (wichtige Wörter, Ohrwurm, Refrain-Steigerung)
NEW_150 = ("key_words", "catchy_chorus", "chorus_lift", "jpop_idol_split", "producer_profile", "taste_learning",
           "style_blend")
COMPOSITION_EXTRAS = NEW_COMPOSITION + NEW_140 + NEW_150     # die Tests schalten sie hier ab (conftest.py)


@dataclass
class SongResult:
    seed: int
    output_dir: str
    midi_files: dict = field(default_factory=dict)
    wav_files: dict = field(default_factory=dict)
    vocals_wav: Optional[str] = None
    harmony_wav: Optional[str] = None
    choir_wav: Optional[str] = None            # Chor im letzten Refrain
    mix_wav: Optional[str] = None
    mp3: Optional[str] = None
    settings: Optional[SongSettings] = None    # die benutzten Einstellungen, mit Seed
    history: Optional[str] = None              # Kopie im Verlauf
    rating: Optional[object] = None            # rating.Rating, wenn mehrere Fassungen bewertet wurden
    polished_wav: Optional[str] = None         # zweite Fassung mit der vom Klang-Veredler neu eingespielten Band
    polished_mp3: Optional[str] = None
    versions: dict = field(default_factory=dict)   # {"offvocal" / "acappella": MP3, ohne ffmpeg WAV} (v6 Nr. 4)
    hearing: list = field(default_factory=list)    # hoercheck.Line je Zeile, wenn der Hör-Check lief (1.5.0 St4)

    @property
    def audio(self) -> Optional[str]:
        """Der fertige Song: die MP3, ohne ffmpeg die WAV."""
        return self.mp3 or self.mix_wav


def genre_for_style(style: str) -> str:
    """Preset-Name → Genre; echte Genre-Namen (\"Rock\", \"EDM\") gehen unverändert durch."""
    return STYLE_TO_GENRE.get(style, style)


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 1_000_000)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % 2**32)


def sung_lyrics(settings: SongSettings) -> dict:
    """Die Silben je Sektion; mit numbered_lyrics auch die eigenen Texte einzelner Vorkommen („[Verse 2]“)."""
    lyrics = parse_lyrics(settings.lyrics, **lyric_options(settings))
    return lyrics if settings.numbered_lyrics else shared_only(lyrics)


def composition_extras(settings: SongSettings) -> dict:
    """{Schalter: Wert} der eingeschalteten Neuerungen ab 1.3.0, die die Noten ändern (0 und aus fehlen); dazu
    "producer": das Produzenten-Profil (produzent.Profile), wenn eins gilt."""
    extras = {name: getattr(settings, name) for name in COMPOSITION_EXTRAS if getattr(settings, name)}
    if extras.pop("producer_profile", False):
        import produzent
        found = produzent.profile(settings)
        if found:
            extras["producer"] = found
    from styles import STYLES
    if extras.pop("style_blend", False) and settings.blend_style in STYLES and settings.blend_style != settings.style:
        extras["blend"] = (settings.blend_style, settings.blend_share)
    if extras.pop("taste_learning", False) and settings.taste_snapshot:
        import geschmack
        extras["taste"] = geschmack.from_snapshot(settings.taste_snapshot)
    return extras


def with_taste(settings: SongSettings, seed: Optional[int] = None) -> SongSettings:
    """C3 (1.5.0): ein neuer Song (ohne Seed) merkt sich den Geschmack aus dem Verlauf, mit dem er entsteht; ein Song
    mit Seed behält seinen, damit derselbe Seed derselbe Song bleibt, auch wenn neue Daumen dazukommen."""
    if settings.seed is not None or seed is not None or not settings.taste_learning:
        return settings
    import geschmack
    return settings.with_updates(taste_snapshot=geschmack.snapshot(settings))


def song_character(tracks: dict) -> dict:
    """Was der Song gewürfelt hat (Charakter und Akkordfolgen), für die Daumen im Verlauf (geschmack.py)."""
    from dataclasses import asdict
    character = tracks.get("character")
    out = asdict(character) if character is not None else {}
    plan = tracks.get("plan")
    if plan is not None:
        out["chords"] = {kind: p for kind, p in plan.progressions.items()
                         if kind in ("Verse", "PreChorus", "Chorus", "Bridge")}
    return out


def compose(settings: SongSettings, seed: Optional[int] = None):
    """Erzeugt alle MIDI-Spuren. Gleicher Seed + gleiche Einstellungen = gleicher Song."""
    if seed is None:
        seed = settings.seed if settings.seed is not None else new_seed()
    seed_everything(seed)
    from vocal_synthesizer import stimmlage
    lo, hi, _ = stimmlage(settings.singer)
    own = _own_melody(settings)
    tracks = _orchestrate(settings, own, lo, hi)
    if settings.ai_melody and not settings.draft and "Chorus" not in own:
        import ai_melody
        melody = ai_melody.for_song(tracks, seed, settings.output_dir(), settings.reuse_steps)
        if melody:
            seed_everything(seed)              # derselbe Song, nur der Refrain singt die Melodie des Modells
            tracks = _orchestrate(settings, {**own, "Chorus": melody}, lo, hi)
    import backing_vocals
    backing_vocals.add(tracks, settings)
    return tracks, seed


def _orchestrate(settings: SongSettings, imported: dict, lo: int, hi: int) -> dict:
    import motifs
    return orchestrate_song(
        genre=genre_for_style(settings.style),
        bpm=settings.bpm,
        structure=list(settings.active_sections),
        key=settings.key,
        mode=settings.scale,
        section_config=settings.section_config(),
        output_dir=settings.output_dir(),
        lyrics=sung_lyrics(settings),
        swing=settings.swing,
        jitter_scale=settings.jitter / DEFAULT_JITTER,
        instrument_styles=settings.instrument_styles(),
        style=settings.remix_from or settings.style,
        band_style=settings.style if settings.remix_from else None,
        melody_bpm=settings.remix_bpm or None,
        vocal_range=(lo, hi),
        variations=settings.variations,
        custom_chords=settings.custom_chords,
        imported_melody=imported,
        melody_edits=settings.melody_edits,
        melody_lengths=settings.melody_lengths,
        motifs=motifs.for_settings(settings),
        real_grooves=settings.real_grooves,
        lively_bass=settings.lively_bass,
        guitar_strums=settings.guitar_strums,
        singable=settings.singable_melody,
        meter=settings.meter,
        ritardando=settings.ritardando,
        extras=composition_extras(settings),
    )


def remix(settings: SongSettings, style: str) -> SongSettings:
    """
    Remix (v6 Nr. 8): derselbe Song (Seed, Melodie, Text, Akkorde, Stimme) mit Band, Tempo und Lautstärken des
    Stils style. Ein Remix eines Remixes geht vom ursprünglichen Song aus. Wirft ValueError ohne Seed.
    """
    if settings.seed is None:
        raise ValueError("Erst einen Song erzeugen, dann davon einen Remix machen.")
    original, melody_bpm = settings.remix_from or settings.style, settings.remix_bpm or settings.bpm
    if style == original:
        return settings.with_updates(style=style, bpm=melody_bpm, remix_from="", remix_bpm=0)
    from preset_manager import preset_settings
    typical = preset_settings(style, settings)
    if typical is None:
        return settings.with_updates(style=style, remix_from=original, remix_bpm=melody_bpm)
    bpm = typical.bpm if settings.meter != "6/8" else round(typical.bpm / 1.5)    # 6/8 zählt punktierte Viertel
    log.info("Remix von %s als %s: %d statt %d BPM", original, style, bpm, melody_bpm)
    return settings.with_updates(style=style, bpm=max(40, bpm), channels=typical.channels, remix_from=original,
                                 remix_bpm=melody_bpm)


def _own_melody(settings: SongSettings) -> dict:
    """{Sektionsart: Melodie} aus der eigenen MIDI-Datei; ohne Datei oder wenn sie nicht passt, komponiert."""
    if not settings.melody_midi:
        return {}
    import melody_import
    if not os.path.exists(settings.melody_midi):
        log.warning("Eigene Melodie nicht gefunden: %s. Die Melodie wird komponiert.", settings.melody_midi)
        return {}
    try:
        melody = melody_import.load(settings.melody_midi)
    except ValueError as e:
        log.warning("Eigene Melodie nicht benutzt: %s. Die Melodie wird komponiert.", e)
        return {}
    if settings.melody_midi_section not in settings.active_sections:
        log.warning("Eigene Melodie für %s, aber der Song hat keine solche Sektion", settings.melody_midi_section)
    log.info("Eigene Melodie aus %s (%d Töne) im %s", os.path.basename(settings.melody_midi), len(melody),
             settings.melody_midi_section)
    return {settings.melody_midi_section: melody}


def _checked(progress: Optional[ProgressFn]) -> ProgressFn:
    """Fortschritt melden und dabei nachsehen, ob abgebrochen wurde (wirft cancel.Cancelled)."""
    def report(fraction: float, message: str) -> None:
        cancel.check()
        if progress:
            progress(fraction, message)
    return report


DRAFT_FOLDER = "Entwurf"


def draft_settings(settings: SongSettings) -> SongSettings:
    """
    Ein schneller Entwurf: der ganze Song, aber ohne Gesang-Synthese (die Lead-Stimme spielt die Gesangsmelodie),
    Orchester und Synths aus dem SoundFont, ohne Veredler, Vorbild-Mastering, MP3 und Verlauf. Er liegt in einem
    eigenen Ordner, damit der letzte richtige Song samt Gesang erhalten bleibt. Mit demselben Seed wird daraus der
    richtige.
    """
    if settings.draft:
        return settings
    out = settings.output_dir()
    os.makedirs(out, exist_ok=True)              # sonst gilt der Unterordner als unerreichbar (output_dir)
    draft = settings.with_updates(draft=True, output_ordner=os.path.join(out, DRAFT_FOLDER), vocal_takes=1,
                                  polish=False, samples=False, reuse_steps=False)
    draft.channels["vocals"].enabled = False
    draft.channels["melody"].enabled = True
    return draft


def generate_song(settings: SongSettings, progress: Optional[ProgressFn] = None, seed: Optional[int] = None,
                  keep_history: bool = True) -> SongResult:
    """Komponieren, Gesang, Rendern, Mischen, Exportieren und im Verlauf ablegen.
    Wirft RuntimeError, wenn keine Spur entsteht, und cancel.Cancelled, wenn abgebrochen wurde."""
    import resume
    report = _checked(progress)
    keep_history = keep_history and not settings.draft
    out = settings.output_dir()
    os.makedirs(out, exist_ok=True)
    import speicher
    if speicher.low_space(out):
        log.warning(speicher.low_space(out))

    report(0.05, "Komponiere Song...")
    settings = with_taste(settings, seed)
    tracks, seed = compose(settings, seed)
    log.info("Seed: %d (mit diesem Seed entsteht derselbe Song noch einmal)", seed)
    settings = settings.with_updates(seed=seed)
    if keep_history and settings.reuse_steps:
        resume.start(settings)     # stürzt die App ab, bietet sie beim nächsten Start an, hier weiterzumachen
    try:
        result = _produce(settings, tracks, out, report, keep_history)
    finally:
        resume.finish()
    if progress:
        progress(1.0, "Fertig")        # ohne Prüfung: ein fertiger Song wird nicht mehr abgebrochen
    return result


def _produce(settings: SongSettings, tracks: dict, out: str, report: ProgressFn, keep_history: bool) -> SongResult:
    seed = settings.seed
    result = SongResult(seed=seed, output_dir=out, settings=settings)
    if settings.ai_accompaniment and not settings.draft:
        report(0.10, "KI schreibt die Begleitung (Versuch)...")
        _ai_accompaniment(settings, tracks, out, seed)
    result.midi_files = {inst: os.path.join(out, f"{inst}.mid") for inst in INSTRUMENTS if tracks.get(inst)}

    _write_ust(settings, tracks, out)
    _write_karaoke(settings, tracks, out)
    report(0.30, "Synthetisiere Gesang...")
    result.vocals_wav = singing._synthesize_vocals(settings, tracks, out)
    _hearing_check(settings, result, report)
    lead_sings = result.vocals_wav is None and settings.channels["melody"].enabled
    if lead_sings:
        _lead_sings_melody(tracks, out)

    report(0.55, "Rendere Instrumente...")
    result.wav_files = rendering._render_instruments(settings, tracks, out, report)
    fx_wav = rendering._render_fx(settings, tracks, out, seed) if result.wav_files else None
    if fx_wav:
        result.wav_files["fx"] = fx_wav

    stems = list(result.wav_files.values()) + _vocal_stems(settings, result, out) + \
        _vocal_chops(settings, tracks, result, out)
    if not stems:
        raise RuntimeError("Keine Audiospuren zum Mischen vorhanden.")

    report(0.85, "Mische und mastere...")
    from mixer import mische_spuren
    result.mix_wav = os.path.join(out, "final_mix.wav")
    mix_args = mixdown.mix_arguments(settings, tracks, out, has_vocals=result.vocals_wav is not None,
                                     lead_sings=lead_sings, stems=len(stems))
    level = mische_spuren(spur_pfade=stems, output_pfad=result.mix_wav, **mix_args)
    _polish(settings, tracks, result, stems, mix_args, report)
    _mix_versions(settings, result, stems, mix_args, level, report)

    remove_file(os.path.join(out, "vorbilder_zusammen.wav"))   # Zusammenschnitt der Vorbilder fürs Mastering

    from exporter import exportiere_song
    mp3 = os.path.join(out, "final_song.mp3")
    remove_file(mp3)  # eine MP3 vom letzten Song darf nicht als neue gelten
    if not settings.draft:                         # den Entwurf spielt der Player als WAV
        report(0.95, "Exportiere MP3...")
        result.mp3 = exportiere_song(wav_pfad=result.mix_wav, mp3_pfad=mp3)
    polished_mp3 = os.path.join(out, "final_song_veredelt.mp3")
    remove_file(polished_mp3)
    if result.polished_wav:
        result.polished_mp3 = exportiere_song(wav_pfad=result.polished_wav, mp3_pfad=polished_mp3)
    for kind, wav in list(result.versions.items()):
        mp3_version = os.path.join(out, VERSIONS[kind][1])
        result.versions[kind] = exportiere_song(wav_pfad=wav, mp3_pfad=mp3_version) or wav
    if settings.id3_tags and not settings.draft:
        _write_tags(result)

    if keep_history:
        import history
        entry = history.record(result.audio, settings, out, keep=settings.history_keep,
                               character=song_character(tracks))
        result.history = entry.audio if entry else None
        if entry:
            import speicher
            speicher.cloud_copy(out, entry.audio)       # die MP3 auch nach OneDrive, wenn die App außerhalb arbeitet
        if entry and settings.keep_projects:
            import project
            report(0.98, "Hebe den Gesang als Projekt auf...")
            project.save(out, tracks, entry.audio)
    return result


def _hearing_check(settings: SongSettings, result: SongResult, report: ProgressFn) -> None:
    """St4 (1.5.0): die Spracherkennung hört den fertigen Gesang ab (nicht im Entwurf und nicht die eigene Spur);
    ohne Schalter oder Erkennung verschwindet nur ein altes Ergebnis aus dem Songordner."""
    import hoercheck
    wanted = settings.hearing_check and not settings.draft and not settings.own_vocal
    result.hearing = hoercheck.check_song(result.output_dir, result.vocals_wav if wanted else None,
                                          lambda fraction, message: report(0.52, message))


# Off-Vocal und A-cappella (v6 Nr. 4): (WAV, MP3, Zusatz zum Titel in den Tags)
VERSIONS = {"offvocal": ("final_offvocal.wav", "final_song_offvocal.mp3", "Off Vocal"),
            "acappella": ("final_acappella.wav", "final_song_acappella.mp3", "A Cappella")}


def _mix_versions(settings: SongSettings, result: SongResult, stems: list, mix_args: dict, level,
                  report: ProgressFn) -> None:
    """Die Band ohne Gesang (Off-Vocal, zum Mitsingen und für Cover) und der Gesang allein (A-cappella), jeweils so
    laut, wie sie im Song klingen: mit denselben Einstellungen gemischt, nur stumm geschaltet (mixer: level_of)."""
    out = result.output_dir
    for wav, mp3, _ in VERSIONS.values():
        for name in (wav, mp3):
            remove_file(os.path.join(out, name))        # eine Fassung vom letzten Song darf nicht als neue gelten
    if not settings.vocal_versions or settings.draft or not result.vocals_wav or level is None:
        return
    from mixer import mische_spuren
    report(0.9, "Mische Off-Vocal und A-cappella...")
    base = {**mix_args, "reference": None, "level_of": level}
    mutes = mix_args.get("mutes") or {}
    parts = {
        # ohne Gesang spielt der Keyboard-Chor wieder, wo sonst gesungene Flächen liegen
        "offvocal": {**base, "mutes": {**mutes, "vocals": True}, "sung_pads": None},
        "acappella": {**base, "solos": {channel: channel == "vocals" for channel in mutes or ("vocals",)}},
    }
    for kind, args in parts.items():
        path = os.path.join(out, VERSIONS[kind][0])
        try:
            mische_spuren(spur_pfade=stems, output_pfad=path, **args)
        except Exception as e:  # noqa: BLE001 – der Song selbst ist fertig
            log.warning("%s nicht gemischt: %s", VERSIONS[kind][2], e)
        if os.path.exists(path):
            result.versions[kind] = path


def _write_tags(result: SongResult) -> None:
    """Titel, Stimme, Stil, Tempo, Tonart, Liedtext und Titelbild in jede MP3 des Songs (v6 Nr. 6)."""
    import tags
    cover = None
    for path, version in ((result.mp3, ""), (result.polished_mp3, "ACE-Step"),
                          *((result.versions.get(kind), VERSIONS[kind][2]) for kind in VERSIONS)):
        if path and path.lower().endswith(".mp3"):
            cover = tags.write(path, result, "", version, cover) or cover


def _vocal_stems(settings: SongSettings, result: SongResult, out: str) -> list:
    """Die Gesangsspuren zum Mischen: Hauptstimme, zweite Stimme, Chor, Doppelung und die Begleitstimmen."""
    if not result.vocals_wav:
        return []
    stems = [result.vocals_wav]
    harmony = os.path.join(out, "vocals_harmony.wav")
    if os.path.exists(harmony):
        result.harmony_wav = harmony
        stems.append(harmony)
    choir = os.path.join(out, "vocals_chor.wav")
    if os.path.exists(choir):
        result.choir_wav = choir
        stems.append(choir)
    double = os.path.join(out, "vocals_double.wav")
    if settings.vocal_chain and os.path.exists(double):
        stems.append(double)          # echte Doppelung im Refrain aus der zweitbesten Fassung
    return stems + [p for p in (os.path.join(out, n) for n in singing.EXTRA_VOCALS) if os.path.exists(p)]


def _vocal_chops(settings: SongSettings, tracks: dict, result: SongResult, out: str) -> list:
    """Vocal Chops im Drop aus dem fertigen Gesang (v6 Nr. 14); leer ohne Schalter, Gesang oder Drop."""
    import vocal_chops
    path = os.path.join(out, vocal_chops.FILE)
    remove_file(path)
    if not settings.vocal_chops or not result.vocals_wav or tracks.get("plan") is None:
        return []
    try:
        made = vocal_chops.render(tracks["plan"], tracks["melody_data"], tracks["silben"], settings.bpm,
                                  result.vocals_wav, path)
    except Exception as e:  # noqa: BLE001 – Chops sind kein Grund, den Song aufzugeben
        log.warning("Vocal Chops übersprungen: %s", e)
        return []
    return [made] if made else []


def _polish(settings: SongSettings, tracks: dict, result: SongResult, stems: list, mix_args: dict,
            report: ProgressFn) -> None:
    """Klang-Veredler (Versuch): ACE-Step spielt die Band neu ein, der Gesang bleibt; ergibt final_mix_veredelt.wav."""
    import polish
    out = result.output_dir
    target, new_band = os.path.join(out, "final_mix_veredelt.wav"), os.path.join(out, "band_veredelt.wav")
    for old in (target, new_band):
        remove_file(old)         # eine Fassung vom letzten Song darf nicht als neue gelten
    band = [path for inst, path in result.wav_files.items() if inst != "fx"]
    if not settings.polish or not band or tracks.get("plan") is None or not polish.available():
        return
    from mixer import mische_spuren
    report(0.88, "Veredle den Klang der Band mit ACE-Step (Versuch)...")
    band_mix = os.path.join(out, "band_vorlage.wav")
    # Die Vorlage ist die Band, wie sie im Song klingt, ohne Gesang und Effekte; Lo-Fi kommt erst danach dazu
    mische_spuren(spur_pfade=band, output_pfad=band_mix, **{**mix_args, "throw_windows": None, "texture": ""})
    try:
        if polish.polish(band_mix, new_band, settings, tracks["plan"], result.seed):
            mische_spuren(spur_pfade=stems, output_pfad=target, band=new_band, **mix_args)
            result.polished_wav = target if os.path.exists(target) else None
    finally:
        remove_file(band_mix)
    if result.polished_wav:
        log.info("Veredelte Fassung: %s", target)


def from_references(settings: SongSettings) -> SongSettings:
    """Tempo, Tonart und Stil der Vorbild-Songs übernehmen, soweit das in den Einstellungen erlaubt ist."""
    import reference
    from styles import STYLES
    summary = reference.summarize(settings.reference_tracks, STYLES)
    if summary is None:
        log.warning("Keine Vorbild-Songs zum Übernehmen.")
        return settings
    updates = {}
    if settings.ref_tempo_key:
        updates.update(bpm=summary.bpm, key=summary.key, scale=summary.scale)
    if settings.ref_style:
        updates["style"] = summary.style
    log.info("Vom Vorbild übernommen: %s", summary.describe())
    settings = settings.with_updates(**updates)
    if settings.ref_structure:
        import vorbild_ablauf
        template = vorbild_ablauf.for_references(settings.reference_tracks)
        if template is not None:
            log.info("Ablauf und Akkorde vom Vorbild: %s", template.describe())
            settings = settings.with_updates(**template.updates(settings))
    return settings


def generate_variants(settings: SongSettings, count: int, parts: tuple = (),
                      progress: Optional[ProgressFn] = None) -> list:
    """Mehrere Songs am Stück, alle im Verlauf. Ohne parts mit neuem Seed je Song; mit parts derselbe Song,
    nur diese Teile jedes Mal neu gewürfelt (z. B. drei Melodien zur Auswahl). Ist die automatische Bewertung
    eingerichtet und an, bekommt jede Fassung eine Note (rating.py); best() sucht dann die beste heraus."""
    import tempfile

    import rating
    report = progress or (lambda fraction, message: None)
    if not parts:
        settings = settings.with_updates(seed=None, variations={})
    elif settings.seed is None:
        raise ValueError("Zum Neu-Würfeln einzelner Teile braucht der Song einen festen Seed.")
    judge = settings.auto_rating and count > 1 and rating.available()
    results, clips = [], []
    with tempfile.TemporaryDirectory() as folder:
        for i in range(count):
            cancel.check()
            for part in parts:
                settings = settings.rerolled(part)

            def step(fraction, message, i=i):
                share = 0.95 if judge else 1.0
                report((i + fraction) / count * share, f"Variante {i + 1}/{count}: {message}" if count > 1 else message)
            result = generate_song(settings, progress=step)
            results.append(result)
            if judge and result is not None and result.mix_wav:
                # jetzt ausschneiden: die nächste Fassung überschreibt den Mix
                clips.append((result, rating.excerpt(result.mix_wav, os.path.join(folder, f"{i + 1}.wav"))))
        if clips:
            report(0.96, "Bewerte die Fassungen...")
            _rate(clips)
    chosen = best(results)
    if chosen is not None and chosen is not results[-1]:
        # Player, Noten und Export nehmen die beste; im Ausgabeordner liegt aber die zuletzt erzeugte
        report(0.97, f"Lade die beste Fassung (Seed {chosen.seed})...")
        results[next(i for i, r in enumerate(results) if r is chosen)] = bring_back(
            chosen, lambda fraction, message: report(0.97 + 0.03 * fraction, f"Beste Fassung: {message}"))
    return results


def bring_back(result: SongResult, progress: Optional[ProgressFn] = None) -> SongResult:
    """
    Mehrere Fassungen und die Songs eines Albums entstehen nacheinander im selben Ausgabeordner, am Ende liegt dort
    nur der zuletzt erzeugte. Dieser Song entsteht dort noch einmal, damit Player, Noten, Text und Export wieder zu
    ihm passen: derselbe Seed, der Gesang aus seinem Projekt im Verlauf (sonst wird er neu gesungen), Band und Mix
    neu. Verlauf und Note bleiben; ein Fehler hier lässt result, wie es war.
    """
    import project
    settings = result.settings.with_updates(reuse_steps=True)
    try:
        if result.history:
            project.unpack(result.history, settings, result.output_dir)
        again = generate_song(settings, progress=progress, keep_history=False)
    except cancel.Cancelled:
        raise
    except Exception as e:  # noqa: BLE001 – die Fassungen selbst sind fertig und im Verlauf
        log.warning("Beste Fassung (Seed %s) nicht wieder geladen: %s", result.seed, e)
        return result
    again.history, again.rating = result.history, result.rating
    return again


def _rate(clips: list) -> None:
    import history
    import rating
    ready = [(result, clip) for result, clip in clips if clip]
    for (result, _), found in zip(ready, rating.rate([clip for _, clip in ready])):
        result.rating = found
        if found and result.history:
            history.set_rating(result.history, found.to_dict())
    rated = sorted((r for r, _ in ready if r.rating), key=lambda r: -r.rating.overall)
    if rated:
        log.info("Bewertung: %s", "; ".join(f"Seed {r.seed}: {r.rating.describe()}" for r in rated))


def best(results: list):
    """Die Fassung mit der besten Note; ohne Noten die letzte."""
    results = [r for r in results if r is not None]
    rated = [r for r in results if r.rating]
    if rated:
        return max(rated, key=lambda r: r.rating.overall)
    return results[-1] if results else None


def lyric_video(result: SongResult, path: Optional[str] = None, label: str = "", preview: bool = False,
                progress=None) -> str:
    """Video (MP4) des Songs mit dem Text zum Mitlesen; Standard: lyric_video.mp4 neben dem Song. Mit music_video das
    Musikvideo, dessen Bild dem Song folgt (musikvideo.py), sonst das Lyric-Video wie bis 1.4. preview: nur 10
    Sekunden ab dem ersten Refrain als video_vorschau.mp4 (V11)."""
    import karaoke
    if not result.audio or not os.path.exists(result.audio):
        raise RuntimeError("Der Song fehlt, erst einen Song erzeugen.")
    s = result.settings
    if s is not None and s.music_video:
        import musikvideo
        name = "video_vorschau.mp4" if preview else "lyric_video.mp4"
        return musikvideo.for_song(result, path or os.path.join(result.output_dir, name), label, preview=preview,
                                   progress=progress)
    found = karaoke.load(os.path.join(result.output_dir, karaoke.FILE))
    title = f"{s.style} · {s.bpm} BPM" if s else ""
    return karaoke.video(result.audio, found, path or os.path.join(result.output_dir, "lyric_video.mp4"), title,
                         background=(s.video_background or None) if s else None,
                         style=s.style if s and s.video_colors else "")


HOOK_BARS = 8           # so lang ist die Vorschau einer Refrain-Melodie
HOOK_FOLDER = "refrains"


@dataclass
class HookChoice:
    number: int
    settings: SongSettings     # mit Seed und Zähler: damit entsteht der ganze Song mit dieser Melodie
    preview: str               # kurze WAV: die Melodie als Synth über den Akkorden


def hook_choices(settings: SongSettings, count: int = 3, progress: Optional[ProgressFn] = None) -> list:
    """
    count neue Refrain-Melodien zum Anhören, der Rest des Songs bleibt. Jede ist eine kurze Vorschau (Melodie
    als Synth über Flächen und Bass), das dauert Sekunden statt Minuten. Ohne festen Seed bekommt der Song einen.
    Wirft ValueError, wenn der Song keinen Gesang hat oder der Refrain die eigene MIDI-Melodie singt.
    """
    report = progress or (lambda fraction, message: None)
    kind = hook_kind(settings)
    if settings.melody_midi and settings.melody_midi_section == kind:
        raise ValueError(f"Im {kind} singt deine eigene MIDI-Melodie; dort gibt es nichts zu würfeln.")
    if settings.seed is None:
        settings = settings.with_updates(seed=new_seed())
    folder = os.path.join(settings.output_dir(), HOOK_FOLDER)
    choices = []
    for i in range(count):
        report(i / count, f"Refrain-Melodie {i + 1}/{count}...")
        settings = settings.rerolled(f"melody:{kind}")
        target = os.path.join(folder, str(i + 1))
        os.makedirs(target, exist_ok=True)
        tracks, _ = compose(settings.with_updates(output_ordner=target))
        preview = os.path.join(target, "refrain.wav")
        _hook_preview(tracks, kind, preview)
        choices.append(HookChoice(i + 1, settings, preview))
    report(1.0, "Fertig")
    return choices


def hook_kind(settings: SongSettings) -> str:
    """Der Refrain, ohne Refrain die erste Sektion mit Gesang."""
    sung = [k for k in settings.active_sections if config.SECTION_CONFIG.get(k, {}).get("has_vocals", True)]
    if not sung:
        raise ValueError("Der Song hat keine Sektion mit Gesang.")
    return "Chorus" if "Chorus" in sung else sung[0]


def _hook_preview(tracks: dict, kind: str, path: str, lead: bool = True) -> None:
    """Die ersten HOOK_BARS Takte der Sektion: Melodie als Lead-Synth (ohne lead nicht), Akkorde als Fläche und Bass."""
    import pretty_midi
    import soundfile as sf
    from synth_engine import SAMPLE_RATE, render_notes
    from theory import voice_chord
    plan = tracks["plan"]
    sec = next(s for s in plan.sections if s.kind == kind)
    spb = plan.seconds_per_beat
    t0, t1 = sec.start * spb, min(sec.end, sec.start + HOOK_BARS * sec.bar_beats) * spb

    def note(velocity: int, pitch: int, start: float, end: float) -> pretty_midi.Note:
        return pretty_midi.Note(velocity=velocity, pitch=pitch, start=start - t0, end=min(end, t1) - t0)

    lead = [note(105, n.pitch, n.start, n.end) for n in tracks["vocal_melody"] if t0 <= n.start < t1] if lead else []
    pad, bass, previous = [], [], None
    for slot in sec.chords:
        start, end = slot.start * spb, (slot.start + slot.dur) * spb
        if start >= t1:
            break
        previous = voice_chord(slot.chord, 52, 72, 4, previous)
        pad += [note(70, p, start, end) for p in previous]
        root = slot.chord.root if slot.chord.bass is None else slot.chord.bass
        bass.append(note(90, 36 + root, start, end))
    length = int((t1 - t0 + 1.0) * SAMPLE_RATE)
    mix = (render_notes(lead, "lead", length) + 0.45 * render_notes(pad, "pad", length)
           + 0.6 * render_notes(bass, "sub", length))
    peak = float(np.max(np.abs(mix))) or 1.0
    sf.write(path, (mix * (0.89 / peak)).T, SAMPLE_RATE)


UST_FILES = ("vocals.ust", "vocals_harmony.ust", "vocals_duett_1.ust", "vocals_duett_2.ust")


def _write_karaoke(settings: SongSettings, tracks: dict, out: str) -> None:
    """Der Liedtext mit der Zeit jeder Silbe, zum Mitlesen im Player und fürs Lyric-Video."""
    import karaoke
    import songkarte
    from lyrics import sung_lines
    from settings import DEFAULT_LYRICS, DEFAULT_RAP_LYRICS
    own = sung_lines(settings.lyrics, **lyric_options(settings))
    merged = {**sung_lines(DEFAULT_LYRICS + DEFAULT_RAP_LYRICS),
              **(own if settings.numbered_lyrics else shared_only(own))}
    lengths = {kind: [len(sung) for _, sung, _ in text_lines] for kind, text_lines in merged.items()}
    texts = {kind: [(written, translation) for written, _, translation in text_lines]
             for kind, text_lines in merged.items()}
    found = karaoke.lines(tracks["vocal_melody"], tracks["silben"], settings.bpm, tracks.get("plan"), lengths, texts)
    try:
        karaoke.save(os.path.join(out, karaoke.FILE), found)
    except OSError as e:
        log.warning("Liedtext zum Mitlesen nicht gespeichert: %s", e)
    songkarte.write(settings, tracks, out)          # 1.5.0 V1: was wann passiert, fürs Video


def _write_ust(settings: SongSettings, tracks: dict, out: str) -> list:
    """Die Gesangsnoten als UTAU-Projekte für OpenUtau: Melodie, zweite Stimme und beim Duett beide Teile."""
    from melody_writer import split_for_duet
    from ust_export import schreibe_ust
    from vocal_synthesizer import stimmlage
    for name in UST_FILES:
        remove_file(os.path.join(out, name))
    if not tracks.get("melody_data"):
        return []
    transpose = stimmlage(settings.singer)[2]
    jobs = [("vocals.ust", tracks["melody_data"], tracks["silben"], transpose)]
    if tracks.get("harmony_data"):
        jobs.append(("vocals_harmony.ust", tracks["harmony_data"], tracks["harmony_silben"], transpose))
    if settings.duet_singer and settings.duet_singer != settings.singer and tracks.get("plan"):
        parts = split_for_duet(tracks["plan"], tracks["melody_data"], tracks["silben"])
        for k, (singer, (data, silben)) in enumerate(zip((settings.singer, settings.duet_singer), parts)):
            jobs.append((f"vocals_duett_{k + 1}.ust", data, silben, stimmlage(singer)[2]))
    written = []
    for name, data, silben, shift in jobs:
        try:
            written.append(schreibe_ust(data, silben, settings.bpm, os.path.join(out, name), shift))
        except Exception as e:
            log.warning("%s nicht geschrieben: %s", name, e)
    return written


def _lead_sings_melody(tracks: dict, out: str) -> None:
    """Ohne Gesang spielt die Lead-Stimme die Gesangsmelodie, damit der Song eine Melodie hat."""
    import pretty_midi
    path = os.path.join(out, "melody.mid")
    if not tracks.get("vocal_melody") or not os.path.exists(path):
        return
    midi = pretty_midi.PrettyMIDI(path)
    if not midi.instruments:
        return
    lead = midi.instruments[0]
    lead.notes.extend(pretty_midi.Note(velocity=95, pitch=n.pitch, start=n.start, end=n.end)
                      for n in tracks["vocal_melody"])
    lead.notes.sort(key=lambda n: n.start)
    midi.write(path)
    tracks["melody"] = lead.notes
    log.info("Kein Gesang: die Lead-Stimme spielt die Melodie.")


def _ai_accompaniment(settings: SongSettings, tracks: dict, out: str, seed: int) -> None:
    """Die Begleitstimmen vom Anticipatory Music Transformer; ohne ihn bleibt die komponierte Begleitung."""
    import accompaniment
    plan = tracks.get("plan")
    sections = mixdown._section_energies(plan) if plan is not None else []
    if not accompaniment.accompany(tracks, out, settings.bpm, seed, sections, reuse=settings.reuse_steps) \
            and not accompaniment.available():
        log.info("KI-Begleitung eingeschaltet, aber nicht eingerichtet (Hilfe › Einrichten); die komponierte bleibt.")

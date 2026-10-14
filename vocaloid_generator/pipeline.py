# pipeline.py – Der komplette Ablauf von den Einstellungen bis zur fertigen MP3.
# Kommandozeile (main.py) und Oberfläche (gui/page.py) rufen beide nur generate_song() auf.
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

import cancel
import config
import neutrino_score
from lyrics import parse_lyrics
from orchestrator import orchestrate_song
from settings import CHANNELS, DEFAULT_JITTER, INSTRUMENTS, SongSettings

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
}

# Spuren, die mit dem eigenen VST3-Synth gerendert werden, wenn einer gewählt ist und keine Klänge pro Spur
VST_TRACKS = ("synth", "melody")
# So viele Spuren rendern gleichzeitig (FluidSynth, die eigenen Synths und die Filter geben den Prozessor frei)
RENDER_WORKERS = max(1, min(6, (os.cpu_count() or 2)))

ProgressFn = Callable[[float, str], None]


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


def compose(settings: SongSettings, seed: Optional[int] = None):
    """Erzeugt alle MIDI-Spuren. Gleicher Seed + gleiche Einstellungen = gleicher Song."""
    if seed is None:
        seed = settings.seed if settings.seed is not None else new_seed()
    seed_everything(seed)
    import motifs
    from vocal_synthesizer import stimmlage
    lo, hi, _ = stimmlage(settings.singer)
    tracks = orchestrate_song(
        genre=genre_for_style(settings.style),
        bpm=settings.bpm,
        structure=list(settings.active_sections),
        key=settings.key,
        mode=settings.scale,
        section_config=settings.section_config(),
        output_dir=settings.output_dir(),
        lyrics=parse_lyrics(settings.lyrics, settings.romaji, settings.english_kana),
        swing=settings.swing,
        jitter_scale=settings.jitter / DEFAULT_JITTER,
        instrument_styles=settings.instrument_styles(),
        style=settings.style,
        vocal_range=(lo, hi),
        variations=settings.variations,
        custom_chords=settings.custom_chords,
        imported_melody=_own_melody(settings),
        melody_edits=settings.melody_edits,
        melody_lengths=settings.melody_lengths,
        motifs=motifs.for_settings(settings),
        real_grooves=settings.real_grooves,
        lively_bass=settings.lively_bass,
        guitar_strums=settings.guitar_strums,
    )
    return tracks, seed


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

    report(0.05, "Komponiere Song...")
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
    result.vocals_wav = _synthesize_vocals(settings, tracks, out)
    lead_sings = result.vocals_wav is None and settings.channels["melody"].enabled
    if lead_sings:
        _lead_sings_melody(tracks, out)

    report(0.55, "Rendere Instrumente...")
    result.wav_files = _render_instruments(settings, tracks, out, report)
    fx_wav = _render_fx(settings, tracks, out, seed) if result.wav_files else None
    if fx_wav:
        result.wav_files["fx"] = fx_wav

    stems = list(result.wav_files.values())
    if result.vocals_wav:
        stems.append(result.vocals_wav)
    harmony = os.path.join(out, "vocals_harmony.wav")
    if result.vocals_wav and os.path.exists(harmony):
        result.harmony_wav = harmony
        stems.append(harmony)
    choir = os.path.join(out, "vocals_chor.wav")
    if result.vocals_wav and os.path.exists(choir):
        result.choir_wav = choir
        stems.append(choir)
    double = os.path.join(out, "vocals_double.wav")
    if result.vocals_wav and settings.vocal_chain and os.path.exists(double):
        stems.append(double)          # echte Doppelung im Refrain aus der zweitbesten Fassung
    if not stems:
        raise RuntimeError("Keine Audiospuren zum Mischen vorhanden.")

    report(0.85, "Mische und mastere...")
    from mixer import mische_spuren
    from styles import get_style
    profile = get_style(settings.style)
    result.mix_wav = os.path.join(out, "final_mix.wav")
    mix_args = dict(
        lautstaerken=[1.0] * len(stems),
        volumes={ch: settings.channels[ch].volume for ch in CHANNELS},
        panning={ch: settings.channels[ch].pan for ch in CHANNELS},
        mutes={ch: settings.channels[ch].mute for ch in CHANNELS},
        solos={ch: settings.channels[ch].solo for ch in CHANNELS},
        compressor_threshold=settings.compressor_threshold,
        compressor_ratio=settings.compressor_ratio,
        limiter_threshold=settings.limiter_threshold,
        # Singt die Lead-Stimme die Melodie, steht sie so weit vorn wie sonst der Gesang
        levels={**profile.mix, "melody": profile.mix["vocals"] - 1.0} if lead_sings else profile.mix,
        reverb=profile.reverb,
        bpm=settings.bpm,
        sidechain_depth=profile.sidechain,
        double_windows=_chorus_windows(tracks.get("plan")),
        throw_windows=_throw_windows(settings, tracks) if result.vocals_wav else None,
        target_lufs=settings.master_lufs,
        texture=profile.texture if settings.lofi_texture else "",
        movement=_movement(tracks.get("plan")) if settings.mix_movement else None,
        vocal_chain=settings.vocal_chain,
        vocal_space=_sections_in_seconds(tracks["plan"]) if tracks.get("plan") is not None else None,
        **({} if settings.draft else
           _reference_targets(settings, tracks, out, has_vocals=result.vocals_wav is not None)),
    )
    mische_spuren(spur_pfade=stems, output_pfad=result.mix_wav, **mix_args)
    _polish(settings, tracks, result, stems, mix_args, report)

    _remove(os.path.join(out, "vorbilder_zusammen.wav"))   # Zusammenschnitt der Vorbilder fürs Mastering

    from exporter import exportiere_song
    mp3 = os.path.join(out, "final_song.mp3")
    _remove(mp3)  # eine MP3 vom letzten Song darf nicht als neue gelten
    if not settings.draft:                         # den Entwurf spielt der Player als WAV
        report(0.95, "Exportiere MP3...")
        result.mp3 = exportiere_song(wav_pfad=result.mix_wav, mp3_pfad=mp3)
    polished_mp3 = os.path.join(out, "final_song_veredelt.mp3")
    _remove(polished_mp3)
    if result.polished_wav:
        result.polished_mp3 = exportiere_song(wav_pfad=result.polished_wav, mp3_pfad=polished_mp3)

    if keep_history:
        import history
        entry = history.record(result.audio, settings, out, keep=settings.history_keep)
        result.history = entry.audio if entry else None
    return result


def _polish(settings: SongSettings, tracks: dict, result: SongResult, stems: list, mix_args: dict,
            report: ProgressFn) -> None:
    """Klang-Veredler (Versuch): ACE-Step spielt die Band neu ein, der Gesang bleibt; ergibt final_mix_veredelt.wav."""
    import polish
    out = result.output_dir
    target, new_band = os.path.join(out, "final_mix_veredelt.wav"), os.path.join(out, "band_veredelt.wav")
    for old in (target, new_band):
        _remove(old)         # eine Fassung vom letzten Song darf nicht als neue gelten
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
        _remove(band_mix)
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
    return settings.with_updates(**updates)


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
    return results


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


def lyric_video(result: SongResult, path: Optional[str] = None) -> str:
    """Lyric-Video (MP4) des Songs mit dem Text zum Mitlesen; Standard: lyric_video.mp4 neben dem Song."""
    import karaoke
    if not result.audio or not os.path.exists(result.audio):
        raise RuntimeError("Der Song fehlt, erst einen Song erzeugen.")
    found = karaoke.load(os.path.join(result.output_dir, karaoke.FILE))
    s = result.settings
    title = f"{s.style} · {s.bpm} BPM" if s else ""
    return karaoke.video(result.audio, found, path or os.path.join(result.output_dir, "lyric_video.mp4"), title)


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


def _hook_preview(tracks: dict, kind: str, path: str) -> None:
    """Die ersten HOOK_BARS Takte der Sektion: Melodie als Lead-Synth, dazu Akkorde als Fläche und Bass."""
    import pretty_midi
    import soundfile as sf
    from song_plan import BEATS_PER_BAR
    from synth_engine import SAMPLE_RATE, render_notes
    from theory import voice_chord
    plan = tracks["plan"]
    sec = next(s for s in plan.sections if s.kind == kind)
    spb = plan.seconds_per_beat
    t0, t1 = sec.start * spb, min(sec.end, sec.start + HOOK_BARS * BEATS_PER_BAR) * spb

    def note(velocity: int, pitch: int, start: float, end: float) -> pretty_midi.Note:
        return pretty_midi.Note(velocity=velocity, pitch=pitch, start=start - t0, end=min(end, t1) - t0)

    lead = [note(105, n.pitch, n.start, n.end) for n in tracks["vocal_melody"] if t0 <= n.start < t1]
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


VOCAL_FILES = ("vocals.wav", "vocals_duett_1.wav", "vocals_duett_2.wav", "vocals_harmony.wav", "vocals_chor.wav",
               "vocals_double.wav")
# Welche Engine singt, wenn die gewählte fehlt; ganz zuletzt die lokale Vorschau-Stimme
ENGINE_ORDER = {"NEUTRINO": ("NEUTRINO", "VOICEVOX"), "VOICEVOX": ("VOICEVOX", "NEUTRINO"), "Vorschau": ()}


# Was den Gesang bestimmt: ändert sich nichts davon, bleibt der gesungene Gesang (z. B. beim Neu-Würfeln des Basses)
VOCAL_KEY = "vocals.key"
VOCAL_CODE = ("pipeline.py", "vocal_synthesizer.py", "voice_fx.py", "voicevox.py", "neutrino_score.py")
VOCAL_FIELDS = ("bpm", "seed", "singer", "vocal_engine", "harmonies", "duet_singer", "style_shift", "vocal_takes",
                "vibrato", "glide", "breaths", "final_choir", "voicevox_url", "voicevox_singer", "neutrino_pfad",
                "vocal_comping", "phrase_expression", "long_vowel_mark", "breath_marks", "fast_diphthongs")


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
    data["notes"] = [tracks.get(k) for k in ("melody_data", "silben", "harmony_data", "harmony_silben")]
    data["sections"] = [(sec.kind, sec.start, sec.end) for sec in plan.sections] if plan else []
    data["neutrino"] = neutrino_info(settings.neutrino_dir())
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
    for name in VOCAL_FILES + (VOCAL_KEY,):
        _remove(os.path.join(out, name))
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

    engines = {"NEUTRINO": _sing_neutrino, "VOICEVOX": _sing_voicevox}
    sung = False
    for name in ENGINE_ORDER.get(settings.vocal_engine, ENGINE_ORDER["NEUTRINO"]):
        try:
            engines[name](settings, tracks, out, vocals_wav, xml)
            sung = True
            break
        except Exception as e:  # noqa: BLE001 – dann singt die nächste Engine
            log.warning("%s nicht verfügbar: %s", name, e)
            for leftover in VOCAL_FILES:
                _remove(os.path.join(out, leftover))
    if not sung:
        if settings.vocal_engine != "Vorschau":
            log.warning("Weder NEUTRINO noch VOICEVOX singen, nutze die lokale Vorschau-Stimme.")
        if not _sing_preview(settings, tracks, vocals_wav):
            return None
    _liven(settings, tracks, out, vocals_wav)
    if sung and key:
        _remember_vocals(out, key)     # die Vorschau-Stimme nicht: fehlte NEUTRINO nur kurz, singt es beim nächsten Mal
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


def _liven(settings: SongSettings, tracks: dict, out: str, vocals_wav: str) -> None:
    """Was jede Engine bekommt: Chor im letzten Refrain (aus der eigenen Stimme, wenn die Engine keinen gesungen
    hat), Ausdruck pro Phrase und Atmer vor den Phrasen."""
    import voice_fx
    if settings.phrase_expression and tracks.get("plan") is not None:
        notes = voice_fx.timeline(tracks["melody_data"], settings.bpm)
        if voice_fx.express(vocals_wav, notes, _sections_in_seconds(tracks["plan"])):
            log.info("Ausdruck pro Phrase: zum Höhepunkt lauter, am Ende weicher")
    choir = os.path.join(out, "vocals_chor.wav")
    window = _final_chorus(tracks.get("plan"))
    if settings.final_choir and window and not os.path.exists(choir):
        spb = 60.0 / settings.bpm
        try:
            if voice_fx.choir_from_lead(vocals_wav, choir, (window[0] * spb, window[1] * spb)):
                log.info("Chor im letzten Refrain aus der eigenen Stimme")
        except Exception as e:  # noqa: BLE001
            log.warning("Chor im letzten Refrain fehlgeschlagen: %s", e)
    if settings.breaths:
        count = voice_fx.add_breaths(vocals_wav, voice_fx.timeline(tracks["melody_data"], settings.bpm),
                                     seed=settings.seed or 0)
        log.info("%d Atmer vor den Phrasen", count)


def _sections_in_seconds(plan) -> list:
    """[(Start, Ende in Sekunden, Sektionsart)]."""
    spb = plan.seconds_per_beat
    return [(sec.start * spb, sec.end * spb, sec.kind) for sec in plan.sections]


def _final_chorus(plan) -> Optional[tuple]:
    """(Start, Ende) des letzten Refrains in Schlägen; bei leisem Anfang (Breakdown) ab dem vollen Teil."""
    choruses = [sec for sec in plan.sections if sec.kind == "Chorus" and sec.has_vocals] if plan else []
    if not choruses:
        return None
    sec = choruses[-1]
    return (sec.resume if sec.feel == "breakdown" and sec.resume is not None else sec.start), sec.end


# ── NEUTRINO ────────────────────────────────────────────────────────────────────
def _sing_neutrino(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, xml: str) -> None:
    from vocal_synthesizer import neutrino_info, stimmlage
    if not xml:
        raise RuntimeError("ohne music21 gibt es keine Noten für NEUTRINO")
    neutrino_dir = settings.neutrino_dir()
    duet = _duet_partner(settings, neutrino_dir)
    log.info("%s; singe mit %s", neutrino_info(neutrino_dir), settings.singer + (f" und {duet}" if duet else ""))
    if duet:
        _sing_duet(settings, tracks, out, neutrino_dir, duet, vocals_wav)
    else:
        _neutrino_lead(settings, tracks["melody_data"], xml, vocals_wav, neutrino_dir, settings.singer,
                       _chorus_windows(tracks.get("plan")))
    harmony_wav = os.path.join(out, "vocals_harmony.wav")
    if (settings.harmonies or duet) and tracks.get("harmony_data"):
        # im Duett singt die zweite Stimme die zweite Stimme im Refrain
        singer = duet or settings.singer
        _sing_harmony(settings, tracks, out, neutrino_dir, os.path.join(neutrino_dir, "model", singer),
                      stimmlage(singer)[2], harmony_wav)
    if settings.final_choir:
        _neutrino_choir(settings, tracks, out, neutrino_dir, duet)


def _neutrino_lead(settings: SongSettings, data: list, xml: str, wav: str, neutrino_dir: str, singer: str,
                   double_windows: list = ()) -> None:
    """Eine Hauptstimme mit NEUTRINO, danach Vibrato und Übergänge. Bei mehreren Fassungen kommt jede Phrase aus der
    saubersten (Comping, ohne: die sauberste ganze Fassung); in den double_windows (Sekunden) wird aus den
    zweitbesten Phrasen eine echte Doppelung (vocals_double.wav)."""
    import voice_fx
    from vocal_synthesizer import neutrino_synthese, stimmlage
    transpose = stimmlage(singer)[2]
    model_dir = os.path.join(neutrino_dir, "model", singer)
    notes = voice_fx.timeline(data, settings.bpm, transpose)
    shifts = voice_fx.take_shifts(settings.style_shift, settings.vocal_takes)
    if len(shifts) == 1:
        neutrino_synthese(xml, wav, neutrino_dir, model_dir, style_shift=shifts[0])
    else:
        takes = []
        for k, shift in enumerate(shifts):
            take = wav[:-4] + f"_fassung_{k + 1}.wav"
            try:
                neutrino_synthese(xml, take, neutrino_dir, model_dir, style_shift=shift)
            except Exception as e:  # noqa: BLE001 – eine misslungene Fassung ist kein Grund aufzuhören
                if k == 0:
                    raise
                log.warning("Fassung %d nicht gesungen: %s", k + 1, e)
                continue
            score = voice_fx.pitch_error(take, notes)
            log.info("Fassung %d (StyleShift %+d): %.0f Cent neben den Noten", k + 1, shift, score)
            takes.append((score, k, take, shift))
        double = os.path.join(os.path.dirname(wav), "vocals_double.wav")
        if settings.vocal_comping and len(takes) > 1:
            paths = [take for _, _, take, _ in takes]
            choice = voice_fx.comp(paths, notes, wav, double, double_windows)
            counts = {takes[k][1] + 1: choice.count(k) for k in sorted(set(choice))}
            log.info("%s: Phrasen aus den saubersten Fassungen (%s)", singer,
                     ", ".join(f"Fassung {n}: {c}×" for n, c in counts.items()))
        else:
            _, k, best, shift = min(takes)
            os.replace(best, wav)
            log.info("%s: Fassung %d klingt am saubersten (StyleShift %+d)", singer, k + 1, shift)
        for _, _, take, _ in takes:
            _remove(take)
        if os.path.exists(double):
            voice_fx.reshape(double, notes, settings.vibrato, settings.glide)
    voice_fx.reshape(wav, notes, settings.vibrato, settings.glide)


def _neutrino_choir(settings: SongSettings, tracks: dict, out: str, neutrino_dir: str, duet: Optional[str]) -> None:
    """Im letzten Refrain singen zwei weitere Stimmen die Melodie mit (andere installierte Stimmen, sonst dieselbe
    heller und dunkler)."""
    import soundfile as sf
    import voice_fx
    from vocal_synthesizer import erstelle_musicxml, installed_singers, neutrino_synthese, stimmlage
    window = _final_chorus(tracks.get("plan"))
    if window is None:
        return
    data, silben = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], *window)
    if not data:
        return
    singers = [n for n in installed_singers(neutrino_dir) if n != settings.singer
               and os.path.isdir(os.path.join(neutrino_dir, "model", n))]
    singers.sort(key=lambda n: n != duet)
    voices = [(n, settings.style_shift) for n in singers[:2]] or [
        (settings.singer, max(-6, settings.style_shift - 2)), (settings.singer, min(6, settings.style_shift + 2))]
    sung, rate = [], 48000
    for k, (singer, shift) in enumerate(voices):
        xml = os.path.join(out, f"vocals_chor_{k + 1}.xml")
        wav = os.path.join(out, f"vocals_chor_{k + 1}.wav")
        try:
            erstelle_musicxml(data, silben, settings.bpm, xml, stimmlage(singer)[2], neutrino_score.options(settings))
            neutrino_synthese(xml, wav, neutrino_dir, os.path.join(neutrino_dir, "model", singer), style_shift=shift)
            audio, rate = sf.read(wav, dtype="float32", always_2d=True)
            sung.append(audio.mean(axis=1))
        except Exception as e:  # noqa: BLE001
            log.warning("Chorstimme %s fehlgeschlagen: %s", singer, e)
        finally:
            _remove(wav)
            _remove(xml)
    if sung:
        voice_fx.write_choir(os.path.join(out, "vocals_chor.wav"), sung, rate, window[0] * 60.0 / settings.bpm)
        log.info("Chor im letzten Refrain: %s", ", ".join(f"{n} ({s:+d})" for n, s in voices))


# ── VOICEVOX ────────────────────────────────────────────────────────────────────
def _sing_voicevox(settings: SongSettings, tracks: dict, out: str, vocals_wav: str, xml: str = "") -> None:
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
    voicevox.sing(tracks["melody_data"], tracks["silben"], settings.bpm, vocals_wav, url, singer, pitch=shape)
    if settings.harmonies and tracks.get("harmony_data"):
        try:
            voicevox.sing(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                          os.path.join(out, "vocals_harmony.wav"), url, singer)
            log.info("Zweite Stimme im Refrain gesungen.")
        except Exception as e:  # noqa: BLE001
            log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)
    window = _final_chorus(tracks.get("plan"))
    if settings.final_choir and window:
        _voicevox_choir(settings, tracks, out, url, singer, window)


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
            _remove(wav)
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
        _neutrino_lead(settings, data, xml, wav, neutrino_dir, singer)
        data_k, rate = sf.read(wav, dtype="float32", always_2d=True)
        mono = data_k.mean(axis=1)
        angle = (1 + (-DUET_PAN if k == 0 else DUET_PAN)) * np.pi / 4
        audio.append(np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1) * np.sqrt(2))
    length = max(len(a) for a in audio)
    mix = sum(np.pad(a, ((0, length - len(a)), (0, 0))) for a in audio)
    sf.write(vocals_wav, mix, rate, subtype="FLOAT")
    log.info("Duett: %s und %s", settings.singer, partner)


def _sing_harmony(settings, tracks, out, neutrino_dir, model_dir, transpose, harmony_wav) -> None:
    """Zweite Stimme im Refrain, mit NEUTRINO gesungen."""
    from vocal_synthesizer import erstelle_musicxml, neutrino_synthese
    xml = erstelle_musicxml(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                            os.path.join(out, "vocals_harmony.xml"), transpose, neutrino_score.options(settings))
    try:
        neutrino_synthese(xml, harmony_wav, neutrino_dir, model_dir, style_shift=settings.style_shift)
        log.info("Zweite Stimme im Refrain gesungen.")
    except Exception as e:
        log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)


UST_FILES = ("vocals.ust", "vocals_harmony.ust", "vocals_duett_1.ust", "vocals_duett_2.ust")


def _write_karaoke(settings: SongSettings, tracks: dict, out: str) -> None:
    """Der Liedtext mit der Zeit jeder Silbe, zum Mitlesen im Player und fürs Lyric-Video."""
    import karaoke
    from lyrics import section_lines
    from settings import DEFAULT_LYRICS
    lengths = {kind: [len(line) for line in text_lines]
               for kind, text_lines in {**section_lines(DEFAULT_LYRICS),
                                        **section_lines(settings.lyrics, settings.romaji, settings.english_kana)}.items()}
    found = karaoke.lines(tracks["vocal_melody"], tracks["silben"], settings.bpm, tracks.get("plan"), lengths)
    try:
        karaoke.save(os.path.join(out, karaoke.FILE), found)
    except OSError as e:
        log.warning("Liedtext zum Mitlesen nicht gespeichert: %s", e)


def _write_ust(settings: SongSettings, tracks: dict, out: str) -> list:
    """Die Gesangsnoten als UTAU-Projekte für OpenUtau: Melodie, zweite Stimme und beim Duett beide Teile."""
    from melody_writer import split_for_duet
    from ust_export import schreibe_ust
    from vocal_synthesizer import stimmlage
    for name in UST_FILES:
        _remove(os.path.join(out, name))
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


def _reference_targets(settings: SongSettings, tracks: dict, out: str, has_vocals: bool) -> dict:
    """Was die Vorbild-Songs am Mix bestimmen dürfen: Mastering, Lautstärke-Verlauf, Gesangspegel und, mit Demucs,
    Pegel und Helligkeit von Gesang, Schlagzeug, Bass und Rest einzeln."""
    import reference
    from styles import STYLES
    refs = settings.reference_tracks
    if not reference.active(refs):
        return {}
    targets = {}
    if settings.ref_mastering:
        try:
            targets["reference"] = reference.mastering_reference(refs, folder=out)
        except Exception as e:  # noqa: BLE001 – ohne Vorbild bleibt das normale Mastering
            log.warning("Vorbilder fürs Mastering nicht nutzbar: %s", e)
    plan = tracks.get("plan")
    wants_energy = settings.ref_energy and plan is not None
    wants_voice = settings.ref_vocal_level and has_vocals
    summary = reference.summarize(refs, STYLES) if (wants_energy or wants_voice) else None
    if summary is not None:
        log.info("Vorbilder: %s", summary.describe())
        if wants_energy:
            targets["energy_contrast_db"] = summary.contrast_db
            targets["sections"] = _section_energies(plan)
        if wants_voice and summary.vocal_db is None:
            log.info("In den Vorbildern ist kein Gesang zu hören; die Gesangslautstärke bleibt, wie sie ist.")
        elif wants_voice:
            targets["vocal_ratio_db"] = summary.vocal_db
    if settings.ref_stems:
        groups = _group_targets(refs, has_vocals)
        if groups:
            targets["group_targets"] = groups
            if "vocals" in groups:
                targets.pop("vocal_ratio_db", None)     # die Zerlegung misst den Gesang genauer als die Schätzung
    return targets


def _group_targets(refs, has_vocals: bool) -> Optional[dict]:
    import separation
    try:
        groups = separation.summarize(refs)
    except Exception as e:  # noqa: BLE001 – ohne Zerlegung bleibt der Mix wie bisher
        log.warning("Vorbilder nicht zerlegbar: %s", e)
        return None
    if groups is None:
        return None
    if not has_vocals:
        groups.pop("vocals", None)
    log.info("Vorbilder einzeln: %s", separation.describe(groups))
    return groups or None


def _ai_accompaniment(settings: SongSettings, tracks: dict, out: str, seed: int) -> None:
    """Die Begleitstimmen vom Anticipatory Music Transformer; ohne ihn bleibt die komponierte Begleitung."""
    import accompaniment
    plan = tracks.get("plan")
    sections = _section_energies(plan) if plan is not None else []
    if not accompaniment.accompany(tracks, out, settings.bpm, seed, sections, reuse=settings.reuse_steps) \
            and not accompaniment.available():
        log.info("KI-Begleitung eingeschaltet, aber nicht eingerichtet (Hilfe › Einrichten); die komponierte bleibt.")


def _section_energies(plan) -> list:
    """[(Start, Ende in Sekunden, Energie)], leise Anfänge (Breakdown) als eigener Teil."""
    from orchestrator import _pieces
    spb = plan.seconds_per_beat
    return [(p.start * spb, p.end * spb, p.energy) for sec in plan.sections for p in _pieces(sec)]


def _throw_windows(settings: SongSettings, tracks: dict) -> list:
    """Wo das Echo auf dem letzten Wort einer Phrase liegt (Sekunden)."""
    if not settings.echo_throws or not tracks.get("melody_data"):
        return []
    import voice_fx
    plan = tracks.get("plan")
    sections = [(sec.start * plan.seconds_per_beat, sec.end * plan.seconds_per_beat, sec.kind)
                for sec in plan.sections] if plan else []
    return voice_fx.throw_windows(voice_fx.timeline(tracks["melody_data"], settings.bpm), settings.bpm, sections)


def _chorus_windows(plan) -> list:
    if plan is None:
        return []
    spb = plan.seconds_per_beat
    # im leisen Anfang eines Refrains (Breakdown) bleibt der Gesang einfach
    return [((sec.resume if sec.feel == "breakdown" else sec.start) * spb, sec.end * spb)
            for sec in plan.sections if sec.kind == "Chorus"]


def _movement(plan) -> Optional[list]:
    """Die Sektionen für die Bewegung im Mix (mix_movement.Part), in Sekunden."""
    if plan is None:
        return None
    from mix_movement import Part
    from song_plan import BEATS_PER_BAR
    spb = plan.seconds_per_beat
    return [Part(sec.start * spb, sec.end * spb, sec.kind, BEATS_PER_BAR * spb) for sec in plan.sections]


def _render_fx(settings: SongSettings, tracks: dict, out: str, seed: int) -> Optional[str]:
    """Riser, Becken-Swells und Impacts an den Übergängen als eigene Spur."""
    wav = os.path.join(out, "fx.wav")
    _remove(wav)
    plan = tracks.get("plan")
    if plan is None or not settings.channels["fx"].enabled or plan.style.fx == "none":
        return None
    import soundfile as sf
    from fx import SAMPLE_RATE, render_fx
    audio = render_fx(plan, seed)
    if not np.any(audio):
        return None
    sf.write(wav, audio.T, SAMPLE_RATE, subtype="FLOAT")
    return wav


def _render_instruments(settings: SongSettings, tracks: dict, out: str, report: ProgressFn) -> dict:
    """Rendert jede Spur in ihre WAV; mehrere Spuren gleichzeitig auf mehreren Kernen (VST-Instrumente nacheinander)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from renderer import engine_name
    import sound_library
    log.info("Instrumente aus dem SoundFont mit %s", engine_name())
    extra = sound_library.installed() if settings.sound_library and not settings.own_soundfont() else []
    if extra:
        log.info("Zusätzliche SoundFonts: %s", ", ".join(extra))
    if _samples(settings):
        import sample_library
        orchestra = sample_library.installed()
        if orchestra:
            log.info("Orchester-Aufnahmen: %d Instrumente", len(orchestra))
        extra = extra + orchestra
    if settings.real_drums and not settings.own_soundfont():
        import drum_kit
        if drum_kit.installed():
            log.info("%s", drum_kit.status())
            extra = extra + [drum_kit.SFZ_NAME, str(os.path.getmtime(drum_kit.path()))]
    active = [inst for inst in INSTRUMENTS if settings.channels[inst].enabled and tracks.get(inst)]
    jobs = {inst: _render_job(settings, out, inst) for inst in active}
    keys = {inst: _render_key(jobs[inst], extra) for inst in active}
    kept = [inst for inst in active if _rendered_before(jobs[inst]["wav_pfad"], keys[inst])]
    for inst in INSTRUMENTS:
        if inst not in kept:
            _remove(os.path.join(out, f"{inst}.wav"))  # alte Spuren nicht versehentlich mitmischen
            _remove(os.path.join(out, f"{inst}.wav.key"))
    if kept:
        log.info("Unverändert, nicht neu gerendert: %s", ", ".join(kept))
    together = [inst for inst in active if inst not in kept and not jobs[inst]["vst_pfad"]]
    alone = [inst for inst in active if inst not in kept and jobs[inst]["vst_pfad"]]
    done = len(kept)

    def finished(inst: str) -> None:
        nonlocal done
        done += 1
        if os.path.exists(jobs[inst]["wav_pfad"]):
            _remember_render(jobs[inst]["wav_pfad"], keys[inst])    # gleich: nach Abbruch oder Absturz bleibt sie
        report(round(0.55 + 0.29 * done / max(len(active), 1), 3), f"{inst} gerendert ({done} von {len(active)})")

    from mixer import midi_zu_wav
    pool = ThreadPoolExecutor(max_workers=RENDER_WORKERS)
    try:
        futures = {pool.submit(midi_zu_wav, **jobs[inst]): inst for inst in together}
        for future in as_completed(futures):
            future.result()
            finished(futures[future])
    except cancel.Cancelled:
        pool.shutdown(wait=True, cancel_futures=True)    # was noch nicht angefangen hat, fällt weg
        raise
    finally:
        pool.shutdown(wait=True)
    for inst in alone:
        midi_zu_wav(**jobs[inst])
        finished(inst)
    return {inst: jobs[inst]["wav_pfad"] for inst in active if os.path.exists(jobs[inst]["wav_pfad"])}


# Der Code, der Klang macht: ändert er sich (neue Version der App), wird alles neu gerendert
RENDER_CODE = ("renderer.py", "mixer.py", "synth_engine.py", "drum_machine.py", "guitar_amp.py", "sound_library.py",
               "styles.py", "sfz.py", "sample_library.py", "drum_kit.py")


def _render_key(job: dict, library: list) -> str:
    """
    Fingerabdruck einer Spur: ihre MIDI-Datei, alle Angaben zum Klang, SoundFont, Impulsantwort und VST-Instrument
    (Größe und Zeit) und der Klang-Code. Gleicher Fingerabdruck = gleiche WAV, so rendert neu Singen oder ein neu gewürfeltes
    Schlagzeug nur, was sich geändert hat.
    """
    import hashlib
    import json
    digest = hashlib.sha1()
    for path in (job["midi_pfad"], *(os.path.join(config.BASE_DIR, f) for f in RENDER_CODE)):
        try:
            with open(path, "rb") as f:
                digest.update(f.read())
        except OSError:
            digest.update(path.encode())
    files = [(p, os.path.getsize(p), os.path.getmtime(p))
             for p in (job["soundfont_pfad"], job["cabinet_ir"], job["vst_pfad"]) if p and os.path.exists(p)]
    described = {k: v for k, v in job.items() if k not in ("midi_pfad", "wav_pfad")}
    digest.update(json.dumps([described, files, sorted(library)], sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _rendered_before(wav: str, key: str) -> bool:
    try:
        with open(wav + ".key", encoding="utf-8") as f:
            return f.read().strip() == key and os.path.exists(wav)
    except OSError:
        return False


def _remember_render(wav: str, key: str) -> None:
    try:
        with open(wav + ".key", "w", encoding="utf-8") as f:
            f.write(key)
    except OSError as e:
        log.debug("Fingerabdruck für %s nicht gespeichert: %s", wav, e)


def _render_job(settings: SongSettings, out: str, inst: str) -> dict:
    """Die Angaben für mixer.midi_zu_wav: welche Klänge diese Spur spielen."""
    from styles import get_style
    profile = get_style(settings.style)
    vst, state = _vst_for(settings, inst)
    return dict(
        midi_pfad=os.path.join(out, f"{inst}.mid"), wav_pfad=os.path.join(out, f"{inst}.wav"),
        is_drum=inst in ("drums", "perc"),
        instrument_type=inst,
        vst_pfad=vst,
        vst_state=state,
        soundfont_pfad=settings.soundfont_file(),
        voices=None if settings.draft else profile.voices.get(inst),     # eigene Synths brauchen Zeit
        library=settings.sound_library and not settings.own_soundfont(),
        drum_machine=_drum_machine(settings) if inst == "drums" else None,
        amp=settings.guitar_amp,
        cabinet_ir=settings.cabinet_ir,
        samples=_samples(settings),
        real_drums=settings.real_drums and not settings.own_soundfont() and inst == "drums",
    )


def _samples(settings: SongSettings) -> bool:
    """Orchester-Aufnahmen statt SoundFont: eingeschaltet und kein eigener SoundFont gewählt."""
    return settings.samples and not settings.own_soundfont()


def _vst_for(settings: SongSettings, inst: str) -> tuple:
    """
    (VST-Pfad, gespeicherter Klang) für eine Spur, sonst (None, "").
    Hat man Klänge pro Spur gewählt, spielen nur diese Spuren das Instrument; sonst Synth und Lead mit seinem
    Standardklang.
    """
    if not settings.vst_path:
        return None, ""
    if inst in settings.vst_sounds:
        return settings.vst_path, settings.vst_sounds[inst]
    if not settings.vst_sounds and inst in VST_TRACKS:
        return settings.vst_path, ""
    return None, ""


def _drum_machine(settings: SongSettings) -> Optional[str]:
    """ "808" oder "909", wenn das Schlagzeug aus der Drum-Machine kommt: so gewählt oder vom Stil vorgegeben."""
    from styles import get_style
    chosen = settings.channels["drums"].style
    if chosen in ("808", "909"):
        return chosen
    if chosen == "soundfont":
        return None
    return get_style(settings.style).drum_machine or None


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        log.warning("Konnte %s nicht löschen: %s", path, e)

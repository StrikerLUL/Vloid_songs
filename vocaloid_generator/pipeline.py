# pipeline.py – Der komplette Ablauf von den Einstellungen bis zur fertigen MP3.
# Kommandozeile (main.py) und Oberfläche (gui/page.py) rufen beide nur generate_song() auf.
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

import config
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
}

# Spuren, die mit dem eigenen VST3-Synth gerendert werden, wenn einer gewählt ist
VST_TRACKS = ("synth", "melody")

ProgressFn = Callable[[float, str], None]


@dataclass
class SongResult:
    seed: int
    output_dir: str
    midi_files: dict = field(default_factory=dict)
    wav_files: dict = field(default_factory=dict)
    vocals_wav: Optional[str] = None
    harmony_wav: Optional[str] = None
    mix_wav: Optional[str] = None
    mp3: Optional[str] = None
    settings: Optional[SongSettings] = None    # die benutzten Einstellungen, mit Seed
    history: Optional[str] = None              # Kopie im Verlauf

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
    from vocal_synthesizer import stimmlage
    lo, hi, _ = stimmlage(settings.singer)
    tracks = orchestrate_song(
        genre=genre_for_style(settings.style),
        bpm=settings.bpm,
        structure=list(settings.active_sections),
        key=settings.key,
        mode=settings.scale,
        section_config=config.SECTION_CONFIG,
        output_dir=settings.output_dir(),
        lyrics=parse_lyrics(settings.lyrics),
        swing=settings.swing,
        jitter_scale=settings.jitter / DEFAULT_JITTER,
        instrument_styles=settings.instrument_styles(),
        style=settings.style,
        vocal_range=(lo, hi),
        variations=settings.variations,
    )
    return tracks, seed


def generate_song(settings: SongSettings, progress: Optional[ProgressFn] = None, seed: Optional[int] = None,
                  keep_history: bool = True) -> SongResult:
    """Komponieren, Gesang, Rendern, Mischen, Exportieren und im Verlauf ablegen.
    Wirft RuntimeError, wenn keine Spur entsteht."""
    report = progress or (lambda fraction, message: None)
    out = settings.output_dir()
    os.makedirs(out, exist_ok=True)

    report(0.05, "Komponiere Song...")
    tracks, seed = compose(settings, seed)
    log.info("Seed: %d (mit diesem Seed entsteht derselbe Song noch einmal)", seed)
    settings = settings.with_updates(seed=seed)
    result = SongResult(seed=seed, output_dir=out, settings=settings)
    result.midi_files = {inst: os.path.join(out, f"{inst}.mid") for inst in INSTRUMENTS if tracks.get(inst)}

    _write_ust(settings, tracks, out)
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
    if not stems:
        raise RuntimeError("Keine Audiospuren zum Mischen vorhanden.")

    report(0.85, "Mische und mastere...")
    from mixer import mische_spuren
    from styles import get_style
    profile = get_style(settings.style)
    result.mix_wav = os.path.join(out, "final_mix.wav")
    mische_spuren(
        spur_pfade=stems,
        lautstaerken=[1.0] * len(stems),
        output_pfad=result.mix_wav,
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
        sidechain_depth=0.45 if profile.name == "Kawaii Chiptune" else 0.25,
        double_windows=_chorus_windows(tracks.get("plan")),
        target_lufs=settings.master_lufs,
        **_reference_targets(settings, tracks, out, has_vocals=result.vocals_wav is not None),
    )

    _remove(os.path.join(out, "vorbilder_zusammen.wav"))   # Zusammenschnitt der Vorbilder fürs Mastering

    report(0.95, "Exportiere MP3...")
    from exporter import exportiere_song
    mp3 = os.path.join(out, "final_song.mp3")
    _remove(mp3)  # eine MP3 vom letzten Song darf nicht als neue gelten
    result.mp3 = exportiere_song(wav_pfad=result.mix_wav, mp3_pfad=mp3)

    if keep_history:
        import history
        entry = history.record(result.audio, settings, out)
        result.history = entry.audio if entry else None

    report(1.0, "Fertig")
    return result


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
    nur diese Teile jedes Mal neu gewürfelt (z. B. drei Melodien zur Auswahl)."""
    report = progress or (lambda fraction, message: None)
    if not parts:
        settings = settings.with_updates(seed=None, variations={})
    elif settings.seed is None:
        raise ValueError("Zum Neu-Würfeln einzelner Teile braucht der Song einen festen Seed.")
    results = []
    for i in range(count):
        for part in parts:
            settings = settings.rerolled(part)

        def step(fraction, message, i=i):
            report((i + fraction) / count, f"Variante {i + 1}/{count}: {message}" if count > 1 else message)
        results.append(generate_song(settings, progress=step))
    return results


def _synthesize_vocals(settings: SongSettings, tracks: dict, out: str) -> Optional[str]:
    vocals_wav = os.path.join(out, "vocals.wav")
    for name in ("vocals.wav", "vocals_duett_1.wav", "vocals_duett_2.wav"):
        _remove(os.path.join(out, name))
    melody_data = tracks.get("melody_data", [])
    silben = tracks.get("silben", [])
    if not settings.channels["vocals"].enabled:
        log.info("Gesang ist ausgeschaltet.")
        return None
    if not melody_data or not silben:
        log.warning("Keine Melodie oder keine Silben vorhanden, überspringe den Gesang.")
        return None

    from vocal_synthesizer import erstelle_musicxml, generiere_lokale_vocals, neutrino_info, neutrino_synthese, stimmlage
    _, _, transpose = stimmlage(settings.singer)
    xml = erstelle_musicxml(melody_data, silben, settings.bpm, os.path.join(out, "vocals.xml"), transpose)
    harmony_wav = os.path.join(out, "vocals_harmony.wav")
    _remove(harmony_wav)

    if settings.vocal_engine == "NEUTRINO" and xml:
        neutrino_dir = settings.neutrino_dir()
        model_dir = os.path.join(neutrino_dir, "model", settings.singer)
        duet = _duet_partner(settings, neutrino_dir)
        log.info("%s; singe mit %s", neutrino_info(neutrino_dir), settings.singer + (f" und {duet}" if duet else ""))
        try:
            if duet:
                _sing_duet(settings, tracks, out, neutrino_dir, duet, vocals_wav)
            else:
                neutrino_synthese(xml, vocals_wav, neutrino_dir, model_dir, style_shift=settings.style_shift)
            if (settings.harmonies or duet) and tracks.get("harmony_data"):
                # im Duett singt die zweite Stimme die zweite Stimme im Refrain
                singer = duet or settings.singer
                _sing_harmony(settings, tracks, out, neutrino_dir, os.path.join(neutrino_dir, "model", singer),
                              stimmlage(singer)[2], harmony_wav)
            return vocals_wav
        except Exception as e:
            log.warning("NEUTRINO fehlgeschlagen: %s", e)
        log.warning("NEUTRINO nicht verfügbar, nutze die lokale Vorschau-Stimme.")

    try:
        generiere_lokale_vocals(
            melody_data, silben, settings.bpm, vocals_wav,
            breathiness=settings.breathiness, shimmer=settings.shimmer,
        )
    except Exception as e:
        log.error("Lokale Stimme fehlgeschlagen, der Song entsteht ohne Gesang: %s", e)
        return None
    return vocals_wav if os.path.exists(vocals_wav) else None


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
    from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, stimmlage
    parts = split_for_duet(tracks["plan"], tracks["melody_data"], tracks["silben"])
    audio, rate = [], None
    for k, (singer, (data, silben)) in enumerate(zip((settings.singer, partner), parts)):
        wav = os.path.join(out, f"vocals_duett_{k + 1}.wav")
        xml = erstelle_musicxml(data, silben, settings.bpm, os.path.join(out, f"vocals_duett_{k + 1}.xml"),
                                stimmlage(singer)[2])
        neutrino_synthese(xml, wav, neutrino_dir, os.path.join(neutrino_dir, "model", singer),
                          style_shift=settings.style_shift)
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
                            os.path.join(out, "vocals_harmony.xml"), transpose)
    try:
        neutrino_synthese(xml, harmony_wav, neutrino_dir, model_dir, style_shift=settings.style_shift)
        log.info("Zweite Stimme im Refrain gesungen.")
    except Exception as e:
        log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)


UST_FILES = ("vocals.ust", "vocals_harmony.ust", "vocals_duett_1.ust", "vocals_duett_2.ust")


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
    """Was die Vorbild-Songs am Mix bestimmen dürfen: Mastering, Lautstärke-Verlauf, Gesangspegel."""
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
    return targets


def _section_energies(plan) -> list:
    """[(Start, Ende in Sekunden, Energie)], leise Anfänge (Breakdown) als eigener Teil."""
    from orchestrator import _pieces
    spb = plan.seconds_per_beat
    return [(p.start * spb, p.end * spb, p.energy) for sec in plan.sections for p in _pieces(sec)]


def _chorus_windows(plan) -> list:
    if plan is None:
        return []
    spb = plan.seconds_per_beat
    # im leisen Anfang eines Refrains (Breakdown) bleibt der Gesang einfach
    return [((sec.resume if sec.feel == "breakdown" else sec.start) * spb, sec.end * spb)
            for sec in plan.sections if sec.kind == "Chorus"]


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
    from mixer import midi_zu_wav
    from renderer import engine_name
    from styles import get_style
    voices = get_style(settings.style).voices
    import sound_library
    log.info("Instrumente aus dem SoundFont mit %s", engine_name())
    extra = sound_library.installed() if settings.sound_library and not settings.soundfont_pfad else []
    if extra:
        log.info("Zusätzliche SoundFonts: %s", ", ".join(extra))
    wav_files = {}
    active = [inst for inst in INSTRUMENTS if settings.channels[inst].enabled and tracks.get(inst)]
    for inst in INSTRUMENTS:
        wav = os.path.join(out, f"{inst}.wav")
        _remove(wav)  # alte Spuren nicht versehentlich mitmischen
        if inst not in active:
            continue
        report(0.55 + 0.3 * active.index(inst) / max(len(active), 1), f"Rendere {inst}...")
        midi_zu_wav(
            os.path.join(out, f"{inst}.mid"), wav,
            is_drum=inst in ("drums", "perc"),
            instrument_type=inst,
            vst_pfad=settings.vst_path if (settings.vst_path and inst in VST_TRACKS) else None,
            soundfont_pfad=settings.soundfont_file(),
            voices=voices.get(inst),
            library=settings.sound_library and not settings.soundfont_pfad,
        )
        if os.path.exists(wav):
            wav_files[inst] = wav
    return wav_files


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        log.warning("Konnte %s nicht löschen: %s", path, e)

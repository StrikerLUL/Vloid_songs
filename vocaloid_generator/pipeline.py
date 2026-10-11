# pipeline.py – Der komplette Ablauf von den Einstellungen bis zur fertigen MP3.
# Kommandozeile (main.py) und Oberfläche (controller.py) rufen beide nur generate_song() auf.
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
    mix_wav: Optional[str] = None
    mp3: Optional[str] = None


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
    )
    return tracks, seed


def generate_song(settings: SongSettings, progress: Optional[ProgressFn] = None, seed: Optional[int] = None) -> SongResult:
    """Komponieren, Gesang, Rendern, Mischen, Exportieren. Wirft RuntimeError, wenn keine Spur entsteht."""
    report = progress or (lambda fraction, message: None)
    out = settings.output_dir()
    os.makedirs(out, exist_ok=True)

    report(0.05, "Komponiere Song...")
    tracks, seed = compose(settings, seed)
    log.info("Seed: %d (mit diesem Seed entsteht derselbe Song noch einmal)", seed)
    result = SongResult(seed=seed, output_dir=out)
    result.midi_files = {inst: os.path.join(out, f"{inst}.mid") for inst in INSTRUMENTS if tracks.get(inst)}

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
    )

    report(0.95, "Exportiere MP3...")
    from exporter import exportiere_song
    mp3 = os.path.join(out, "final_song.mp3")
    _remove(mp3)  # eine MP3 vom letzten Song darf nicht als neue gelten
    result.mp3 = exportiere_song(wav_pfad=result.mix_wav, mp3_pfad=mp3)

    report(1.0, "Fertig")
    return result


def _synthesize_vocals(settings: SongSettings, tracks: dict, out: str) -> Optional[str]:
    vocals_wav = os.path.join(out, "vocals.wav")
    _remove(vocals_wav)
    melody_data = tracks.get("melody_data", [])
    silben = tracks.get("silben", [])
    if not settings.channels["vocals"].enabled:
        log.info("Gesang ist ausgeschaltet.")
        return None
    if not melody_data or not silben:
        log.warning("Keine Melodie oder keine Silben vorhanden, überspringe den Gesang.")
        return None

    from vocal_synthesizer import erstelle_musicxml, generiere_lokale_vocals, neutrino_synthese, stimmlage
    _, _, transpose = stimmlage(settings.singer)
    xml = erstelle_musicxml(melody_data, silben, settings.bpm, os.path.join(out, "vocals.xml"), transpose)
    harmony_wav = os.path.join(out, "vocals_harmony.wav")
    _remove(harmony_wav)

    if settings.vocal_engine == "NEUTRINO" and xml:
        neutrino_dir = settings.neutrino_dir()
        model_dir = os.path.join(neutrino_dir, "model", settings.singer)
        try:
            neutrino_synthese(xml, vocals_wav, neutrino_dir, model_dir)
            if settings.harmonies and tracks.get("harmony_data"):
                _sing_harmony(settings, tracks, out, neutrino_dir, model_dir, transpose, harmony_wav)
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


def _sing_harmony(settings, tracks, out, neutrino_dir, model_dir, transpose, harmony_wav) -> None:
    """Zweite Stimme im Refrain, mit derselben NEUTRINO-Stimme gesungen."""
    from vocal_synthesizer import erstelle_musicxml, neutrino_synthese
    xml = erstelle_musicxml(tracks["harmony_data"], tracks["harmony_silben"], settings.bpm,
                            os.path.join(out, "vocals_harmony.xml"), transpose)
    try:
        neutrino_synthese(xml, harmony_wav, neutrino_dir, model_dir)
        log.info("Zweite Stimme im Refrain gesungen.")
    except Exception as e:
        log.warning("Zweite Stimme fehlgeschlagen, der Song bekommt nur die Hauptstimme: %s", e)


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


def _chorus_windows(plan) -> list:
    if plan is None:
        return []
    spb = plan.seconds_per_beat
    return [(sec.start * spb, sec.end * spb) for sec in plan.sections if sec.kind == "Chorus"]


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
    log.info("Instrumente aus dem SoundFont mit %s", engine_name())
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

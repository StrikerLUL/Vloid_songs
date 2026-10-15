# rendering.py – Die MIDI-Spuren eines Songs als WAV: SoundFont, Orchester-Aufnahmen, echtes Schlagzeug, eigene Synths,
# VST-Instrumente und die Effekt-Spur (Riser, Impacts). Mehrere Spuren rendern gleichzeitig; eine Spur, deren
# Fingerabdruck (<inst>.wav.key) gleich geblieben ist, wird nicht neu gerendert.
import logging
import os
from typing import Callable, Optional

import numpy as np

import cancel
import config
from config import remove_file
from settings import INSTRUMENTS, SongSettings

log = logging.getLogger(__name__)

# Spuren, die mit dem eigenen VST3-Synth gerendert werden, wenn einer gewählt ist und keine Klänge pro Spur
VST_TRACKS = ("synth", "melody")
# So viele Spuren rendern gleichzeitig (FluidSynth, die eigenen Synths und die Filter geben den Prozessor frei)
RENDER_WORKERS = max(1, min(6, (os.cpu_count() or 2)))

ProgressFn = Callable[[float, str], None]


def _render_fx(settings: SongSettings, tracks: dict, out: str, seed: int) -> Optional[str]:
    """Riser, Becken-Swells und Impacts an den Übergängen als eigene Spur."""
    wav = os.path.join(out, "fx.wav")
    remove_file(wav)
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
            remove_file(os.path.join(out, f"{inst}.wav"))  # alte Spuren nicht versehentlich mitmischen
            remove_file(os.path.join(out, f"{inst}.wav.key"))
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

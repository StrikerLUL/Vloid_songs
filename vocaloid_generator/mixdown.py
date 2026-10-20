# mixdown.py – Womit der Song gemischt wird: Pegel und Panorama der Kanäle, Stil, Gesangskette, Bewegung im Mix
# und was die Vorbild-Songs bestimmen dürfen. mix_arguments() gibt die Angaben für mixer.mische_spuren.
import logging
import os
from typing import Optional

from settings import CHANNELS, SongSettings
from song_plan import chorus_windows, sections_in_seconds

log = logging.getLogger(__name__)


def mix_arguments(settings: SongSettings, tracks: dict, out: str, has_vocals: bool, lead_sings: bool = False,
                  stems: int = 0) -> dict:
    """Alles außer den Spuren selbst für mixer.mische_spuren. has_vocals: es gibt eine Gesangsspur; lead_sings: die
    Lead-Stimme spielt die Melodie statt des Gesangs (dann steht sie so weit vorn wie sonst der Gesang); stems: so
    viele Spuren werden gemischt."""
    from styles import get_style
    profile = get_style(settings.style)
    plan = tracks.get("plan")
    return dict(
        lautstaerken=[1.0] * stems,
        volumes={ch: settings.channels[ch].volume for ch in CHANNELS},
        panning={ch: settings.channels[ch].pan for ch in CHANNELS},
        mutes={ch: settings.channels[ch].mute for ch in CHANNELS},
        solos={ch: settings.channels[ch].solo for ch in CHANNELS},
        compressor_threshold=settings.compressor_threshold,
        compressor_ratio=settings.compressor_ratio,
        limiter_threshold=settings.limiter_threshold,
        levels={**profile.mix, "melody": profile.mix["vocals"] - 1.0} if lead_sings else profile.mix,
        reverb=profile.reverb,
        bpm=settings.bpm,
        sidechain_depth=profile.sidechain,
        double_windows=chorus_windows(plan),
        throw_windows=_throw_windows(settings, tracks) if has_vocals else None,
        target_lufs=settings.master_lufs,
        texture=profile.texture if settings.lofi_texture else "",
        movement=_movement(plan) if settings.mix_movement else None,
        vocal_chain=settings.vocal_chain,
        unmask=settings.vocal_unmask,
        ride=settings.vocal_ride,
        convolution=settings.convolution_reverb,
        ducked_delay=settings.ducked_delay,
        vocal_tone=_vocal_tone(settings, out) if has_vocals else None,
        airwindows=settings.airwindows,
        true_peak=settings.true_peak,
        tame=settings.resonance_tamer,
        punch=settings.mix_punch,
        sung_pads=chorus_windows(plan) if has_vocals and os.path.exists(
            os.path.join(out, "vocals_flaechen.wav")) else None,
        vocal_space=sections_in_seconds(plan) if plan is not None else None,
        **({} if settings.draft else _reference_targets(settings, tracks, out, has_vocals=has_vocals)),
    )


def _vocal_tone(settings: SongSettings, out: str):
    """Kette pro Stimme und Stil (vocal_tone.py); die Stimmlage kennt die App nur von NEUTRINO-Stimmen."""
    if not settings.vocal_tone:
        return None
    import vocal_check
    import vocal_tone
    info = vocal_check.read(out) or {}
    singer = settings.singer if info.get("engine") == "NEUTRINO" else None
    tone = vocal_tone.for_song(singer, settings.style)
    log.info("Gesangskette: %s Stimme, %s (%s)", vocal_tone.voice_kind(singer), settings.style, tone.describe())
    return tone


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
        if groups and not settings.ref_vocal_curve and "vocals" in groups:
            groups["vocals"].pop("bands", None)
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


def _movement(plan) -> Optional[list]:
    """Die Sektionen für die Bewegung im Mix (mix_movement.Part), in Sekunden."""
    if plan is None:
        return None
    from mix_movement import Part
    spb = plan.seconds_per_beat
    return [Part(sec.start * spb, sec.end * spb, sec.kind, sec.bar_beats * spb) for sec in plan.sections]

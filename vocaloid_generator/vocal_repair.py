"""Transactional repair of an existing lead phrase.

Only phrase_fixes may differ from the source settings. Other voices and stems
are copied verbatim. The lead is identical outside midpoint cuts in the adjacent
rests (including short breath/tail margins). Mastering is global, so the final
mix outside these cuts need not be identical. No engine fallback is attempted.
Own recordings, group/duet and rap/spoken phrases need separate voice ownership
and are deliberately rejected. Results predating captured repair_tracks must be
regenerated once. Compact scores retain bar alignment for swing and effects.
"""
import copy
import math
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import soundfile as sf

import cancel
import singing
import voice_fx
from song_plan import sections_in_seconds


@dataclass(frozen=True)
class VocalPhrase:
    index: int
    start: float
    end: float
    text: str
    section: str


def list_phrases(result):
    tracks = getattr(result, "repair_tracks", None)
    if not tracks or not result.vocals_wav or not os.path.isfile(result.vocals_wav):
        return []
    groups = voice_fx.phrases(voice_fx.timeline(tracks.get("melody_data", []), result.settings.bpm))
    kinds = voice_fx.phrase_kinds(groups, sections_in_seconds(tracks["plan"]) if tracks.get("plan") else [])
    syllables, pos, found = tracks.get("silben", []), 0, []
    for i, (group, kind) in enumerate(zip(groups, kinds)):
        found.append(VocalPhrase(i, group[0].start, group[-1].end,
                                 "".join(syllables[pos:pos + len(group)]), kind))
        pos += len(group)
    return found


def source_signature(result):
    """Detect overwritten output folders before a repair reuses any audio."""
    import hashlib
    paths = set(result.wav_files.values())
    if result.vocals_wav:
        paths.add(result.vocals_wav)
    paths.update(str(Path(result.output_dir) / name) for name in (*singing.VOCAL_FILES, "chops.wav", "band_veredelt.wav", "gesang.json")
                 if (Path(result.output_dir) / name).is_file())
    found = {}
    for path in paths:
        if os.path.isfile(path):
            with open(path, "rb") as stream:
                found[path] = hashlib.file_digest(stream, "sha256").hexdigest()
    return found


def _validate(settings, result, index):
    phrases = list_phrases(result)
    if not phrases:
        raise ValueError("Kein Gesang mit aufbewahrtem Bauplan; Song bitte einmal neu erzeugen.")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(phrases):
        raise ValueError("Ungültige Phrasennummer.")
    before, after = result.settings.model_dump(), settings.model_dump()
    before.pop("phrase_fixes", None)
    after.pop("phrase_fixes", None)
    if before != after:
        raise ValueError("Für eine einzelne Phrase nur deren Stimme und StyleShift ändern; sonst Song neu erzeugen.")
    if settings.draft or settings.own_vocal or settings.duet_singer or settings.group_vocals:
        raise ValueError("Phrasen-Reparatur braucht eine einzelne synthetisierte Hauptstimme (kein Entwurf, Duett oder Aufnahme).")
    if result.repair_sources and source_signature(result) != result.repair_sources:
        raise ValueError("Die Spuren im Ausgabeordner wurden überschrieben; passenden Song bitte erneut öffnen.")
    import vocal_check
    actual = vocal_check.read(result.output_dir)
    if not actual or actual.get("engine") != settings.vocal_engine:
        raise ValueError("Die tatsächliche Gesangs-Engine fehlt oder war eine Ersatzstimme; Song mit der gewählten Engine neu erzeugen.")
    for path in (result.harmony_wav, result.choir_wav):
        if path and not os.path.isfile(path):
            raise ValueError("Eine gespeicherte Begleitstimme fehlt; passenden Song erneut öffnen.")
    phrase = phrases[index]
    spb = 60 / settings.bpm
    for sec in result.repair_tracks["plan"].sections:
        if sec.kind in ("Rap", "Spoken") and sec.start * spb < phrase.end and sec.end * spb > phrase.start:
            raise ValueError("Rap und gesprochene Phrasen werden nicht einzeln neu gesungen.")
    # An edit for a different phrase would lie about the preserved audio.
    for key in set(settings.phrase_fixes) | set(result.settings.phrase_fixes):
        if settings.phrase_fixes.get(key) != result.settings.phrase_fixes.get(key):
            if not phrase.start - .05 <= float(key) * spb <= phrase.end + .05:
                raise ValueError("Nur die gewählte Phrase darf geändert werden.")
    return phrases, phrase


def _scoped(settings, tracks, phrase):
    """A short, bar-aligned score with the original section/effect context."""
    spb = 60 / settings.bpm
    bar = tracks["plan"].bar_beats
    # Keep at least 0.2s of preroll, aligned to the original bar grid.
    offset = max(0, math.floor((phrase.start / spb - .2 / spb) / bar) * bar)
    data, syllables = voice_fx.excerpt(tracks["melody_data"], tracks["silben"], offset,
                                     phrase.end / spb + 1e-6)
    # excerpt can include previous notes in the preroll bar: mask them explicitly.
    t, selected, text, i = offset * spb, [], [], 0
    for pitch, dur in data:
        keep = pitch is not None and t >= phrase.start - 1e-5
        selected.append((pitch if keep else None, dur))
        if pitch is not None:
            if keep:
                text.append(syllables[i])
            i += 1
        t += dur * spb
    scoped = copy.deepcopy(tracks)
    for key in singing.NOTE_KEYS:
        scoped[key] = []
    scoped.update(melody_data=selected, silben=text)
    for sec in scoped["plan"].sections:
        sec.start -= offset
        if sec.resume is not None:
            sec.resume -= offset
        for chord in sec.chords:
            chord.start -= offset
    fix = next((fix for key, fix in sorted(settings.phrase_fixes.items(), key=lambda x: float(x[0]))
                if phrase.start - .05 <= float(key) * spb <= phrase.end + .05), None)
    updates = dict(phrase_fixes={}, harmonies=False, final_choir=False, harmony_double=False,
                   sung_pads=False, adlibs=False, idol_calls=False)
    if fix is not None:
        if settings.vocal_engine != "NEUTRINO":
            raise ValueError("Stimme und StyleShift pro Phrase benötigen NEUTRINO.")
        singer = fix.get("singer") or settings.singer
        if not os.path.isdir(os.path.join(settings.neutrino_dir(), "model", singer)):
            raise ValueError(f"NEUTRINO-Stimme {singer} ist nicht installiert.")
        updates.update(singer=singer, style_shift=int(fix.get("style_shift", settings.style_shift)), section_style=False)
    return settings.with_updates(**updates), scoped, offset * spb


def _synthesize(settings, tracks, out):
    """Use existing engine and effects code, with no silent engine substitution."""
    from vocal_synthesizer import erstelle_musicxml, stimmlage
    wav = str(Path(out) / "vocals.wav")
    engine = settings.vocal_engine
    cancel.check()
    if engine == "NEUTRINO":
        xml = erstelle_musicxml(tracks["melody_data"], tracks["silben"], settings.bpm,
                                str(Path(out) / "vocals.xml"), stimmlage(settings.singer)[2],
                                singing.neutrino_score.options(settings))
        singing._neutrino_lead(settings, tracks["melody_data"], xml, wav, settings.neutrino_dir(),
                               settings.singer, silben=tracks["silben"],
                               sections=sections_in_seconds(tracks["plan"]))
    elif engine == "VOICEVOX":
        singing._sing_voicevox(settings, tracks, out, wav)
    elif engine == "DiffSinger":
        singing._sing_diffsinger(settings, tracks, out, wav, "")
    elif engine == "Vorschau":
        if not singing._sing_preview(settings, tracks, wav):
            raise RuntimeError("Vorschau-Stimme konnte die Phrase nicht singen.")
    else:
        raise ValueError("Unbekannte Gesangs-Engine.")
    cancel.check()
    singing._liven(settings, tracks, out, wav,
                    sung_dynamics=engine == "VOICEVOX" and singing._voicevox_dynamics(settings))
    singing._style_effects(settings, tracks, wav)
    singing._vocal_swing(settings, tracks, out)
    singing._vocal_pocket(settings, out)
    cancel.check()
    return wav


def _splice(source, replacement, target, start, end, offset, phrase_start=None, phrase_end=None):
    # float64 retains PCM_32/DOUBLE input too; preserve original subtype.
    info = sf.info(source)
    audio, rate = sf.read(source, dtype="float64", always_2d=True)
    fresh, fresh_rate = sf.read(replacement, dtype="float64", always_2d=True)
    if fresh_rate != rate:
        from scipy.signal import resample_poly
        divisor = math.gcd(rate, fresh_rate)
        fresh = resample_poly(fresh, rate // divisor, fresh_rate // divisor)
    if fresh.shape[1] != audio.shape[1]:
        if fresh.shape[1] == 1:
            fresh = np.repeat(fresh, audio.shape[1], axis=1)
        elif audio.shape[1] == 1:
            fresh = fresh.mean(axis=1, keepdims=True)
        else:
            raise ValueError("Unvereinbare Kanalzahl der Gesangsaufnahme.")
    if not np.isfinite(fresh).all() or not np.any(fresh):
        raise RuntimeError("Die neue Phrase enthält kein gültiges Audiosignal.")
    if phrase_start is not None:
        first = max(0, round((phrase_start - offset) * rate))
        last = round((phrase_end - offset) * rate)
        if len(fresh) < last - round(.05 * rate) or not np.any(fresh[first:min(last, len(fresh))]):
            raise RuntimeError("Die neue Aufnahme ist abgeschnitten oder die gewählte Phrase ist stumm.")
    a, b = max(0, round(start * rate)), min(len(audio), round(end * rate))
    if a >= b:
        raise ValueError("Phrase liegt außerhalb der Gesangsspur.")
    indices = np.arange(a, b) - round(offset * rate)
    patch = np.zeros_like(audio[a:b])
    valid = (indices >= 0) & (indices < len(fresh))
    patch[valid] = fresh[indices[valid]]
    # Crossfades live entirely inside the selected repair window.
    fade = min(round(.015 * rate), (b - a) // 2)
    weights = np.ones((b - a, 1))
    if fade:
        weights[:fade, 0] = np.linspace(0, 1, fade)
        weights[-fade:, 0] = np.linspace(1, 0, fade)
    audio[a:b] = audio[a:b] * (1 - weights) + patch * weights
    sf.write(target, audio, rate, subtype=info.subtype)


def repair_phrase(settings, result, index, progress=None, keep_history=True):
    """Return a new SongResult; the source and history are untouched on cancellation.

    settings is result.settings with only the selected phrase_fixes entry changed.
    May raise ValueError, RuntimeError, engine exceptions, or cancel.Cancelled.
    Publication uses a directory rename after synthesis, splice, remix and export.
    """
    import pipeline
    from mixer import mische_spuren
    from exporter import exportiere_song
    report = pipeline._checked(progress)
    report(0, "Prüfe Gesangsphrase...")
    phrases, phrase = _validate(settings, result, index)
    scoped_settings, scoped_tracks, offset = _scoped(settings, result.repair_tracks, phrase)
    root = Path(result.output_dir).resolve()
    history_root = settings.output_dir()
    final = root.parent / (root.name.split("_reparatur_")[0] + "_reparatur_" + uuid.uuid4().hex[:12])
    stage = Path(tempfile.mkdtemp(prefix=".vocal-repair-", dir=root.parent))
    published = False
    try:
        # Metadata/MIDI/backing stems remain usable by existing export/player code.
        for path in root.iterdir():
            cancel.check()
            if path.is_file() and path.suffix.lower() not in (".mp4", ".mp3") and not path.name.startswith("final_") and not path.name.startswith("hoer_check"):
                shutil.copy2(path, stage / path.name)
        mapped = {}
        for name, path in result.wav_files.items():
            if not os.path.isfile(path):
                raise ValueError(f"Instrumentenspur fehlt: {name}")
            dest = stage / Path(path).name
            if not dest.exists():
                shutil.copy2(path, dest)
            mapped[name] = str(dest)
        for path in (result.harmony_wav, result.choir_wav):
            if path:
                dest = stage / Path(path).name
                if not dest.exists():
                    shutil.copy2(path, dest)
        report(.15, "Singe nur die gewählte Phrase...")
        with tempfile.TemporaryDirectory(prefix="phrase-", dir=stage) as scratch:
            fresh = _synthesize(scoped_settings, scoped_tracks, scratch)
            start = max(0, phrase.start - .2)
            end = phrase.end + .25
            if index:
                start = max(start, (phrases[index - 1].end + phrase.start) / 2)
            if index + 1 < len(phrases):
                end = min(end, (phrase.end + phrases[index + 1].start) / 2)
            _splice(result.vocals_wav, fresh, str(stage / "vocals.wav"), start, end, offset, phrase.start, phrase.end)
        updated = replace(result, output_dir=str(stage), settings=settings.model_copy(deep=True),
                          vocals_wav=str(stage / "vocals.wav"), wav_files=mapped,
                          harmony_wav=str(stage / Path(result.harmony_wav).name) if result.harmony_wav else None,
                          choir_wav=str(stage / Path(result.choir_wav).name) if result.choir_wav else None,
                          midi_files={k: str(stage / Path(v).name) for k, v in result.midi_files.items()},
                          history=None, rating=None, hearing=[], versions={}, polished_wav=None, polished_mp3=None,
                          mp3=None, mix_wav=str(stage / "final_mix.wav"), share_dir=None)
        stems = list(mapped.values()) + pipeline._vocal_stems(settings, updated, str(stage))
        # Chops are a separate, already performed voice: preserve them exactly.
        chops = stage / "chops.wav"
        if chops.is_file():
            stems.append(str(chops))
        report(.65, "Mische vorhandene Spuren mit reparierter Phrase...")
        args = pipeline.mixdown.mix_arguments(settings, result.repair_tracks, str(stage), has_vocals=True,
                                              lead_sings=False, stems=len(stems))
        level = mische_spuren(spur_pfade=stems, output_pfad=updated.mix_wav, **args)
        # Reuse the already polished band; never run ACE-Step again.
        if result.polished_wav and (stage / "band_veredelt.wav").exists():
            updated.polished_wav = str(stage / "final_mix_veredelt.wav")
            mische_spuren(spur_pfade=stems, output_pfad=updated.polished_wav,
                          band=str(stage / "band_veredelt.wav"), **args)
        pipeline._mix_versions(settings, updated, stems, args, level, report)
        report(.92, "Exportiere reparierten Song...")
        updated.mp3 = exportiere_song(updated.mix_wav, str(stage / "final_song.mp3"))
        if updated.polished_wav:
            updated.polished_mp3 = exportiere_song(updated.polished_wav, str(stage / "final_song_veredelt.mp3"))
        for kind, wav in list(updated.versions.items()):
            updated.versions[kind] = exportiere_song(wav, str(stage / pipeline.VERSIONS[kind][1])) or wav
        # The mixed lead is now the cache entry for the full, original score.
        singing._remember_vocals(str(stage), singing.vocal_key(settings, result.repair_tracks))
        # Keep source identity plus an explicit record of the mixed-in phrase.
        meta = stage / "vocal_repairs.json"
        import json
        previous = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else []
        previous.append(dict(index=index, start=phrase.start, end=phrase.end,
                             window=[start, end], engine=scoped_settings.vocal_engine,
                             singer=scoped_settings.singer, style_shift=scoped_settings.style_shift))
        meta.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
        if settings.id3_tags:
            pipeline._write_tags(updated)
        staged_signature = source_signature(updated)
        character = pipeline.song_character(result.repair_tracks) if keep_history else None
        report(.98, "Speichere reparierten Song...")
        cancel.check()
        for path in (updated.vocals_wav, updated.harmony_wav, updated.choir_wav,
                     updated.mix_wav, updated.mp3, updated.polished_wav, updated.polished_mp3,
                     *updated.wav_files.values(), *updated.midi_files.values(), *updated.versions.values()):
            if path:
                Path(path).relative_to(stage)
        os.replace(stage, final)
        published = True
        def move(path):
            return str(final / Path(path).relative_to(stage)) if path else None
        for name in ("vocals_wav", "harmony_wav", "choir_wav", "mix_wav", "mp3", "polished_wav", "polished_mp3"):
            setattr(updated, name, move(getattr(updated, name)))
        for name in ("wav_files", "midi_files", "versions"):
            setattr(updated, name, {key: move(path) for key, path in getattr(updated, name).items()})
        updated.output_dir = str(final)
        updated.repair_sources = {move(path): digest for path, digest in staged_signature.items()}
        if keep_history:
            import history
            import project
            entry = history.record(updated.audio, settings, history_root, keep=settings.history_keep,
                                   character=character)
            updated.history = entry.audio if entry else None
            if entry:
                if settings.keep_projects:
                    project.save(str(final), result.repair_tracks, entry.audio)
                project.keep_map(str(final), entry.audio)
                import speicher
                speicher.cloud_copy(history_root, entry.audio)
        return updated
    finally:
        if not published:
            shutil.rmtree(stage, ignore_errors=True)

# vocal_synthesizer.py – Gesang: NEUTRINO (MusicXML → WAV) und die lokale Vorschau-Stimme
import logging
import os
import subprocess

import soundfile as sf

log = logging.getLogger(__name__)

SAMPLERATE = 44100


# ── Vorschau-Stimme (wenn NEUTRINO und VOICEVOX fehlen) ─────────────────────
def generiere_lokale_vocals(melodie_daten, silben, bpm, output_wav_pfad, **kwargs):
    """Lokale Vorschau-Stimme (TTS + pyworld). kwargs: breathiness (0.0-0.12), shimmer (Chorus an/aus),
    vibrato (0 = gerade Töne, 1 = normal, 2 = doppelt so tief), glide (0 = springen, 1 = normal, 2 = doppelt so lang)."""
    import tempfile
    import pyttsx3
    import pyworld as pw
    from scipy.interpolate import interp1d
    from scipy.signal import resample, butter, filtfilt
    from pedalboard import Pedalboard, Chorus, Reverb, Compressor, Delay
    import os, soundfile as sf, numpy as np
    
    SAMPLERATE = 44100
    quarter_sec = 60.0 / bpm
    breath_level = float(kwargs.get("breathiness", 0.04)) / 10.0
    shimmer = bool(kwargs.get("shimmer", True))
    vibrato = float(kwargs.get("vibrato", 1.0))
    glide = float(kwargs.get("glide", 1.0))
    silben_idx = 0
    final_audio = []
    temp_wav = os.path.join(tempfile.gettempdir(), "temp_tts_voc.wav")
    
    engine = pyttsx3.init()
    engine.setProperty('rate', 120)
    engine.setProperty('volume', 1.0)
    
    voices = engine.getProperty('voices')
    best_voice = None
    for voice in voices:
        name_lower = voice.name.lower()
        if any(k in name_lower for k in ["zira", "female", "haruka", "ayumi", "hikari"]):
            best_voice = voice.id
            break
    if best_voice:
        engine.setProperty('voice', best_voice)
    
    prev_pitch_hz = None
    
    for note_idx, (pitch, dauer) in enumerate(melodie_daten):
        target_duration = dauer * quarter_sec
        target_frames_len = int(target_duration * SAMPLERATE)
        
        if pitch is None:
            noise_len = target_frames_len
            breath = np.random.normal(0, breath_level, noise_len) if breath_level > 0 else np.zeros(noise_len)
            b, a = butter(2, 800 / (SAMPLERATE / 2), btype='low')
            breath = filtfilt(b, a, breath)
            final_audio.append(breath.astype(np.float64))
            prev_pitch_hz = None
            continue
        
        lyric = silben[silben_idx % len(silben)] if silben else "a"
        silben_idx += 1
        
        if os.path.exists(temp_wav):
            try: os.remove(temp_wav)
            except: pass
        engine.save_to_file(lyric, temp_wav)
        engine.runAndWait()
        
        try:
            data, fs = sf.read(temp_wav)
            if len(data.shape) > 1: data = data[:, 0]
            data = data.astype(np.float64)
            
            if len(data) < 800:
                final_audio.append(np.zeros(target_frames_len, dtype=np.float64))
                continue
            
            _f0, t = pw.dio(data, fs, f0_floor=80.0, f0_ceil=800.0)
            f0 = pw.stonemask(data, _f0, t, fs)
            sp = pw.cheaptrick(data, f0, t, fs)
            ap = pw.d4c(data, f0, t, fs)
            
            sp_enhanced = sp * 1.15
            
            frame_period = 0.005
            target_num_frames = max(2, int(target_duration / frame_period))
            orig_len = len(f0)
            
            if orig_len < 2:
                final_audio.append(np.zeros(target_frames_len, dtype=np.float64))
                continue
            
            orig_indices = np.linspace(0, 1, orig_len)
            target_indices = np.linspace(0, 1, target_num_frames)
            
            f0_stretched = interp1d(orig_indices, f0, kind='linear')(target_indices)
            sp_stretched = interp1d(orig_indices, sp_enhanced, axis=0, kind='linear')(target_indices)
            ap_stretched = interp1d(orig_indices, ap, axis=0, kind='linear')(target_indices)
            
            target_hz = 440.0 * (2.0 ** ((pitch - 69.0) / 12.0))
            f0_vocoded = np.where(f0_stretched > 0, target_hz, 0.0).astype(np.float64)
            
            if prev_pitch_hz is not None and prev_pitch_hz > 0 and glide > 0:
                glide_frames = min(int(0.060 * glide / frame_period), len(f0_vocoded) // 3)
                for j in range(glide_frames):
                    if f0_vocoded[j] > 0:
                        alpha = (1 - np.cos(np.pi * j / glide_frames)) / 2
                        f0_vocoded[j] = prev_pitch_hz * (1.0 - alpha) + target_hz * alpha
            
            vibrato_onset_frames = int(0.300 / frame_period)
            if vibrato > 0 and target_duration > 0.400 and len(f0_vocoded) > vibrato_onset_frames:
                for j in range(len(f0_vocoded)):
                    if f0_vocoded[j] > 0:
                        t_sec = j * frame_period
                        vib_env = min(1.0, max(0.0, (j - vibrato_onset_frames) / (0.200 / frame_period)))
                        rate = 5.2 + 0.3 * np.sin(2 * np.pi * 0.8 * t_sec)
                        depth = 0.45 * vibrato * vib_env
                        mod = depth * np.sin(2.0 * np.pi * rate * t_sec)
                        f0_vocoded[j] = f0_vocoded[j] * (2.0 ** (mod / 12.0))
            
            voiced = f0_vocoded[f0_vocoded > 0]
            prev_pitch_hz = voiced[-1] if len(voiced) > 0 else target_hz
            
            sung_syllable = pw.synthesize(
                f0_vocoded,
                np.ascontiguousarray(sp_stretched),
                np.ascontiguousarray(ap_stretched),
                fs
            )
            
            if fs != SAMPLERATE:
                target_len = int(len(sung_syllable) * SAMPLERATE / fs)
                sung_syllable = resample(sung_syllable, target_len)
            
            if len(sung_syllable) > target_frames_len:
                sung_syllable = sung_syllable[:target_frames_len]
            else:
                sung_syllable = np.pad(sung_syllable, (0, target_frames_len - len(sung_syllable)))
            
            total_len = len(sung_syllable)
            attack_sek = min(0.040, target_duration * 0.15)
            release_sek = min(0.060, target_duration * 0.20)
            attack_len = int(attack_sek * SAMPLERATE)
            release_len = int(release_sek * SAMPLERATE)
            
            envelope = np.ones(total_len, dtype=np.float64)
            if attack_len > 0 and attack_len < total_len:
                envelope[:attack_len] = np.power(np.linspace(0, 1, attack_len), 0.5)
            if release_len > 0 and release_len < total_len:
                envelope[-release_len:] = np.power(np.linspace(1, 0, release_len), 2.0)
            
            sung_syllable *= envelope
            final_audio.append(sung_syllable)
            
        except Exception as e:
            log.warning(f"Vocoder Fehler für '{lyric}': {e}")
            final_audio.append(np.zeros(target_frames_len, dtype=np.float64))
            prev_pitch_hz = None
    
    if os.path.exists(temp_wav):
        try: os.remove(temp_wav)
        except: pass
    
    final_audio_np = np.concatenate(final_audio) if final_audio else np.zeros(SAMPLERATE)
    
    effects = [
        Delay(delay_seconds=0.012, feedback=0.0, mix=0.15),
        Compressor(threshold_db=-20.0, ratio=3.0, attack_ms=5.0, release_ms=80.0),
    ]
    if shimmer:
        effects.append(Chorus(rate_hz=1.2, depth=0.08, mix=0.12))
    effects.append(Reverb(room_size=0.35, damping=0.7, wet_level=0.08, dry_level=0.95))
    board = Pedalboard(effects)
    
    audio_stereo = np.vstack((final_audio_np, final_audio_np)).astype(np.float32)
    audio_stereo = board(audio_stereo, SAMPLERATE)
    
    peak = np.max(np.abs(audio_stereo))
    if peak > 0:
        audio_stereo = audio_stereo / peak * 0.88
    
    sf.write(output_wav_pfad, audio_stereo.T, SAMPLERATE)
    log.info(f"[OK] Verbesserte KI-Vocals generiert: {output_wav_pfad}")


# ── MusicXML & NEUTRINO ──────────────────────────────────────────────────────
_REST_WERTE = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25, 0.125)
# NEUTRINO setzt vor einen Song ohne Pausentakt selbst einen. Wir schreiben immer einen Takt Pause
# davor und schneiden ihn nach dem Rendern wieder ab, dann bleibt der Gesang im Takt der Band.
VORLAUF_SCHLAEGE = 4.0
# Kurze Pausen in einer Phrase klingen bei NEUTRINO abgehackt; bis zu dieser Länge wird gebunden (neutrino_score)
from neutrino_score import LEGATO_BIS  # noqa: E402
# Empfohlener Tonumfang der NEUTRINO-Stimmen (MIDI, C4 = 60) laut studio-neutrino.com.
# Männliche Stimmen singen eine Oktave tiefer, als die Melodie notiert ist.
STIMMEN = {
    "MERROW": (57, 76), "REINA": (53, 72), "KIRITAN": (59, 74), "ITAKO": (57, 74), "ZUNDAMON": (57, 74),
    "SEVEN": (57, 72), "NAKUMO": (45, 71), "SOMA": (48, 72), "RUNO": (43, 69),
}
OKTAVE_TIEFER = {"NAKUMO", "SOMA", "RUNO"}


def stimmlage(singer: str) -> tuple:
    """(tiefster, höchster Ton der notierten Melodie, Transposition beim Singen) für eine Stimme."""
    name = (singer or "").upper()
    lo, hi = STIMMEN.get(name, STIMMEN["MERROW"])
    shift = -12 if name in OKTAVE_TIEFER else 0
    return max(lo - shift, 55), min(hi - shift, 79), shift


def installed_singers(neutrino_pfad: str) -> list:
    """Namen der Stimmen im Ordner model von NEUTRINO; ohne NEUTRINO die bekannten Stimmen."""
    model = os.path.join(neutrino_pfad or "", "model")
    try:
        found = [d for d in os.listdir(model) if os.path.isdir(os.path.join(model, d))]
    except OSError:
        found = []
    return sorted(found) or sorted(STIMMEN)


def _quantisiere_dauer(d: float) -> float:
    """Auf Zweiunddreißigstel runden, ohne die Länge zu verfälschen (Taktgrenzen bindet music21 selbst über)."""
    return max(0.125, round(float(d) * 8) / 8)


def _pausen(dauer: float) -> list:
    """Lange Pausen in notierbare Stücke teilen, damit Gesang und Band synchron bleiben."""
    rest, teile = _quantisiere_dauer(dauer), []
    for wert in _REST_WERTE:
        while rest >= wert - 1e-9:
            teile.append(wert)
            rest -= wert
    return teile


def _gebunden(melodie_daten) -> list:
    """Kurze Pausen innerhalb einer Phrase der Note davor zuschlagen."""
    out = []
    for pitch, dauer in melodie_daten:
        if pitch is None and dauer <= LEGATO_BIS + 1e-9 and out and out[-1][0] is not None:
            out[-1] = (out[-1][0], out[-1][1] + dauer)
        else:
            out.append((pitch, dauer))
    return out


def erstelle_musicxml(melodie_daten, liedtext_silben, bpm, output_xml_pfad, transpose: int = 0, options=None):
    """Gesangsstimme als MusicXML für NEUTRINO: ein Takt Vorlauf, jede Note mit Silbe, Tempo, 4/4.
    options: neutrino_score.ScoreOptions (Haltezeichen, Atemzeichen, schnelle Stellen); None = nur gebunden."""
    try:
        from music21 import articulations, meter, note, stream, tempo
    except ImportError:
        log.warning("music21 nicht installiert. MusicXML kann nicht generiert werden.")
        return ""
    import neutrino_score

    s = stream.Stream()
    s.append(tempo.MetronomeMark(number=bpm))
    s.append(meter.TimeSignature("4/4"))
    s.append(note.Rest(quarterLength=VORLAUF_SCHLAEGE))
    for n in neutrino_score.build(melodie_daten, list(liedtext_silben), bpm, options):
        if n.pitch is None:
            for teil in _pausen(n.beats):
                s.append(note.Rest(quarterLength=teil))
            continue
        n_ = note.Note(n.pitch + transpose, quarterLength=_quantisiere_dauer(n.beats))
        n_.addLyric(n.lyric)
        if n.breath:
            n_.articulations.append(articulations.BreathMark())
        s.append(n_)

    pfad = s.write("musicxml", fp=output_xml_pfad)
    log.info(f"[OK] MusicXML: {pfad}")
    return str(pfad)


def neutrino_version(neutrino_pfad: str) -> int:
    """2 für NEUTRINO v2 (eigener Vocoder NSF.exe), sonst 3."""
    return 2 if os.path.exists(os.path.join(neutrino_pfad, "bin", "NSF.exe")) else 3


def neutrino_info(neutrino_pfad: str) -> str:
    """Kurzbeschreibung für das Protokoll: Version, Ordner und installierte Stimmen."""
    if not os.path.exists(os.path.join(neutrino_pfad, "bin", "NEUTRINO.exe")):
        return f"kein NEUTRINO unter {neutrino_pfad}"
    import re
    versionen = re.findall(r"v\d+(?:\.\d+)+", os.path.abspath(neutrino_pfad))
    ordner = versionen[-1] if versionen else ""
    model = os.path.join(neutrino_pfad, "model")
    stimmen = sorted(d for d in os.listdir(model) if os.path.isdir(os.path.join(model, d))) if os.path.isdir(model) else []
    return (f"NEUTRINO v{neutrino_version(neutrino_pfad)}" + (f" ({ordner})" if ordner else "")
            + f", Stimmen: {', '.join(stimmen) or 'keine'}")


NEUESTE_AUSGABE = (3, 2, 2)     # die neueste normale Windows-Ausgabe (neuer Vocoder seit 3.2.2)


def neutrino_ausgabe(neutrino_pfad: str) -> str:
    """Die Versionsnummer der installierten NEUTRINO-Ausgabe (z. B. "3.2.2"), soweit sie sich finden lässt: im Namen
    des Ordners, der Dateien darin oder in den Textdateien (Readme). Leer, wenn nicht."""
    import re
    muster = re.compile(r"(?i)(?:\bver(?:sion)?\.?\s*|[v_-])(\d+\.\d+(?:\.\d+)?)")
    def neutrino(text: str) -> list:
        return [v for v in muster.findall(text) if v.startswith(("2.", "3.", "4."))]

    ordner = os.path.abspath(neutrino_pfad)
    gefunden = neutrino(os.path.basename(ordner)) + neutrino(os.path.basename(os.path.dirname(ordner)))
    try:
        eintraege = sorted(os.listdir(neutrino_pfad))
    except OSError:
        eintraege = []
    for name in eintraege:
        gefunden += neutrino(name)
    if not gefunden:
        for name in eintraege:
            pfad = os.path.join(neutrino_pfad, name)
            if name.lower().endswith((".txt", ".md")) and os.path.isfile(pfad) and os.path.getsize(pfad) < 200_000:
                with open(pfad, "rb") as f:
                    gefunden += neutrino(f.read().decode("utf-8", errors="replace"))
                if gefunden:
                    break
    return max(gefunden, key=_versionsnummer) if gefunden else ""


def _versionsnummer(text: str) -> tuple:
    return tuple(int(t) for t in text.split(".") if t.isdigit())


def neutrino_hinweis(neutrino_pfad: str) -> str:
    """Ein Hinweis zur installierten NEUTRINO-Ausgabe (leer, wenn alles passt oder sich nichts sagen lässt)."""
    if not os.path.exists(os.path.join(neutrino_pfad, "bin", "NEUTRINO.exe")):
        return ""
    ausgabe = neutrino_ausgabe(neutrino_pfad)
    neueste = ".".join(map(str, NEUESTE_AUSGABE))
    if neutrino_version(neutrino_pfad) == 2 or (ausgabe and _versionsnummer(ausgabe) < NEUESTE_AUSGABE):
        return (f"NEUTRINO {ausgabe or 'v2'} ist älter als {neueste}. Seit {neueste} singt NEUTRINO mit einem neuen "
                "Vocoder deutlich sauberer; die neue Ausgabe gibt es kostenlos auf studio-neutrino.com.")
    if ausgabe and _versionsnummer(ausgabe) > NEUESTE_AUSGABE:
        return (f"NEUTRINO {ausgabe} gibt es für Windows nur mit dem Tuning-Tool (.ex). Diese Ausgabe kennt keinen "
                "StyleShift: Strophe und Refrain klingen gleich, sonst läuft alles.")
    return ""


# Wie der letzte NEUTRINO-Lauf gesungen hat (für den Gesangs-Check und StyleShift pro Sektion):
# grafikkarte: auf der Grafikkarte (False = Prozessor), styleshift: der gewünschte StyleShift kam an
LETZTER_LAUF = {"grafikkarte": None, "styleshift": None, "version": ""}
CPU_MELDUNG = "CPU モード"         # so meldet NEUTRINO, dass es ohne Grafikkarte singt
_AUF_DEM_PROZESSOR: set = set()     # schon gewarnt (je NEUTRINO-Ordner einmal pro Programmstart)


def _run(cmd: list, cwd: str, timeout: int) -> subprocess.CompletedProcess:
    import cancel
    log.debug("NEUTRINO: %s", " ".join(cmd))
    return cancel.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace",
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def neutrino_synthese(xml_pfad, output_wav_pfad, neutrino_pfad, model_pfad, threads: int = None,
                      timeout: int = 1800, style_shift: int = 0) -> bool:
    """
    Rendert die Gesangsstimme mit NEUTRINO. v3 (Tau) schreibt die WAV selbst, v2 (Muon) braucht danach
    noch den Vocoder NSF.exe. Wirft RuntimeError mit NEUTRINOs Meldung, wenn etwas schiefgeht.
    Der Vorlauf-Takt aus erstelle_musicxml wird am Ende abgeschnitten.
    style_shift: NEUTRINOs StyleShift in Halbtönen; positiv klingt die Stimme heller, negativ dunkler.
    Versionen ohne StyleShift singen dann ohne.
    """
    import tempfile

    if not os.path.isdir(neutrino_pfad):
        raise FileNotFoundError(f"NEUTRINO nicht gefunden unter {neutrino_pfad}")
    if not os.path.isdir(model_pfad):
        raise FileNotFoundError(f"Stimme nicht gefunden: {model_pfad}")
    bin_pfad = os.path.join(neutrino_pfad, "bin")
    label_exe = os.path.join(bin_pfad, "musicXMLtoLabel.exe")
    neutrino_exe = os.path.join(bin_pfad, "NEUTRINO.exe")
    for exe in (label_exe, neutrino_exe):
        if not os.path.exists(exe):
            raise FileNotFoundError(f"{os.path.basename(exe)} fehlt in {bin_pfad}")
    threads = str(threads or max(1, min(8, (os.cpu_count() or 4))))
    model = os.path.join(os.path.abspath(model_pfad), "")

    with tempfile.TemporaryDirectory() as td:
        full, mono, timing = (os.path.join(td, n) for n in ("full.lab", "mono.lab", "timing.lab"))
        f0, mel, wav = (os.path.join(td, n) for n in ("vocals.f0", "vocals.melspec", "vocals.wav"))

        run = _run([label_exe, os.path.abspath(xml_pfad), full, mono], neutrino_pfad, 300)
        if run.returncode != 0 or not os.path.exists(full):
            raise RuntimeError(f"musicXMLtoLabel: {(run.stderr or run.stdout).strip()[-400:]}")

        if neutrino_version(neutrino_pfad) == 3:
            log.info("[NEUTRINO v3] Singe...")
            cmd = [neutrino_exe, full, timing, f0, mel, wav, model, "-n", threads, "-t"]
            dateien = {"full": full, "timing": timing, ".f0": f0, ".melspec": mel, ".wav": wav, "model": model,
                       ".mgc": os.path.join(td, "vocals.mgc"), ".bap": os.path.join(td, "vocals.bap")}
            shift = ["-k", str(style_shift)] if style_shift else []
            bat = _run_bat_aufruf(neutrino_pfad, neutrino_exe, dateien, threads, style_shift)
            versuche = [bat,
                        cmd + shift + ["-m"],                          # -m: Grafikkarte, sonst Prozessor
                        cmd + shift,
                        cmd if shift else None]
            for versuch in filter(None, versuche):
                run = _run(versuch, neutrino_pfad, timeout)
                if run.returncode == 0 and os.path.exists(wav):
                    ausgabe = f"{run.stdout or ''}{run.stderr or ''}"
                    mit_shift = (versuch is not versuche[3] and (versuch is not bat or not style_shift
                                                                   or _bat_kennt_styleshift(neutrino_pfad)))
                    LETZTER_LAUF.update(grafikkarte="-m" in versuch and CPU_MELDUNG not in ausgabe,
                                        styleshift=mit_shift if style_shift else None)
                    if not LETZTER_LAUF["grafikkarte"] and neutrino_pfad not in _AUF_DEM_PROZESSOR:
                        _AUF_DEM_PROZESSOR.add(neutrino_pfad)
                        log.warning("NEUTRINO singt auf dem Prozessor statt auf der Grafikkarte, das dauert deutlich "
                                    "länger. Hilft ein aktueller Grafiktreiber (NVIDIA)?")
                    break
        else:
            log.info("[NEUTRINO v2] Singe...")
            run = _run([neutrino_exe, full, timing, f0, mel, model, "-n", "1", "-k", str(style_shift), "-o", threads,
                        "-d", "3", "-t"], neutrino_pfad, timeout)
            if run.returncode == 0:
                vocoder = next((os.path.join(model, f"{m}.bin") for m in ("vs", "va", "ve")
                                if os.path.exists(os.path.join(model, f"{m}.bin"))), os.path.join(model, "vs.bin"))
                run = _run([os.path.join(bin_pfad, "NSF.exe"), f0, mel, vocoder, wav, "-l", timing,
                            "-n", "1", "-p", threads, "-s", "48", "-t"], neutrino_pfad, timeout)
        if run.returncode != 0 or not os.path.exists(wav):
            raise RuntimeError(f"NEUTRINO: {(run.stderr or run.stdout).strip()[-400:]}")

        audio, sr = sf.read(wav, always_2d=True, dtype="float32")
    bpm = _tempo_aus_musicxml(xml_pfad)
    audio = audio[int(round(VORLAUF_SCHLAEGE * 60.0 / bpm * sr)):]
    os.makedirs(os.path.dirname(os.path.abspath(output_wav_pfad)), exist_ok=True)
    sf.write(output_wav_pfad, audio, sr, subtype="FLOAT")
    log.info(f"[OK] NEUTRINO-Gesang: {output_wav_pfad}")
    return True


def _bat_kennt_styleshift(neutrino_pfad: str) -> bool:
    """Reicht die Run.bat einen StyleShift an NEUTRINO.exe weiter?"""
    try:
        with open(os.path.join(neutrino_pfad, "Run.bat"), "rb") as f:
            return "styleshift" in f.read().decode("utf-8", errors="replace").lower()
    except OSError:
        return False


def _run_bat_aufruf(neutrino_pfad: str, neutrino_exe: str, dateien: dict, threads: str, style_shift: int = 0):
    """
    Der NEUTRINO.exe-Aufruf aus der Run.bat, die jeder NEUTRINO-Version beiliegt, mit unseren Dateien
    und Einstellungen. So passt er genau zur installierten Version. None ohne Run.bat oder ohne WAV-Ausgabe.
    """
    import re
    pfad = os.path.join(neutrino_pfad, "Run.bat")
    if not os.path.exists(pfad):
        return None
    with open(pfad, "rb") as f:
        text = f.read().decode("utf-8", errors="replace")
    werte, zeile = {}, None
    for line in (z.strip() for z in text.splitlines()):
        gesetzt = re.match(r'(?i)set\s+"?(\w+)=([^"]*)"?$', line)
        if gesetzt:
            werte[gesetzt.group(1).lower()] = gesetzt.group(2).strip()
        elif zeile is None and re.search(r"(?i)neutrino\.exe", line) and not re.match(r"(?i)(rem\b|::?|echo\b)", line):
            zeile = line
    if not zeile:
        return None
    werte["numthreads"] = threads
    werte["styleshift"] = str(style_shift)
    tokens = zeile.split()
    start = next(k for k, t in enumerate(tokens) if t.lower().endswith("neutrino.exe"))
    cmd = [neutrino_exe]
    for token in tokens[start + 1:]:
        if token in ("&", "&&", "|", "||") or token.startswith((">", "2>")):
            break
        token = re.sub(r"[%!](\w+)[%!]", lambda m: werte.get(m.group(1).lower(), m.group(0)), token)
        name = token.lower().replace("/", "\\").lstrip(".\\")
        endung = os.path.splitext(name)[1]
        if endung == ".lab":
            cmd.append(dateien["timing" if "timing" in name else "full"])
        elif endung in dateien:
            cmd.append(dateien[endung])
        elif name.startswith("model"):
            cmd.append(dateien["model"])
        else:
            cmd.append(token)
    return cmd if dateien[".wav"] in cmd else None


def _tempo_aus_musicxml(xml_pfad: str) -> float:
    import re
    text = open(xml_pfad, encoding="utf-8").read()
    m = re.search(r'<sound[^>]*tempo="([0-9.]+)"', text) or re.search(r"<per-minute>([0-9.]+)</per-minute>", text)
    return float(m.group(1)) if m else 120.0

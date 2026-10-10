# vocal_synthesizer.py – Vocaloid Synthesizer v4.0 (KI-Engine API Wrapper)
# Unterstützt NEUTRINO, OpenUTAU und DiffSinger via CLI/Project-Files
import os
import subprocess
import shutil
import pretty_midi
import numpy as np
import soundfile as sf
import json

SAMPLERATE = 44100

# ── API für OpenUTAU ─────────────────────────────────────────────────────────
def openutau_synthese(xml_pfad, output_wav_pfad, openutau_cli_pfad=r"C:\OpenUtau\OpenUtau.Cli.exe"):
    """
    Ruft das OpenUTAU Command Line Interface auf, um Vocals zu rendern.
    OpenUTAU unterstützt DiffSinger, VCCV, etc.
    """
    if not os.path.exists(openutau_cli_pfad):
        print(f"[Warnung] OpenUTAU CLI nicht gefunden unter {openutau_cli_pfad}.")
        return False
        
    try:
        # OpenUtau.Cli.exe kann MusicXML (.musicxml) lesen und rendern
        print(f"[OpenUTAU] Rendere {xml_pfad}...")
        subprocess.run([
            openutau_cli_pfad,
            "render",
            "--input", os.path.abspath(xml_pfad),
            "--output", os.path.abspath(output_wav_pfad)
        ], check=True, capture_output=True, timeout=60)
        
        if os.path.exists(output_wav_pfad):
            print(f"[OK] OpenUTAU Vocals: {output_wav_pfad}")
            return True
        return False
    except subprocess.TimeoutExpired:
        print("[Fehler] OpenUTAU CLI hat nicht rechtzeitig geantwortet (Timeout). Nutze Fallback.")
        return False
    except Exception as e:
        print(f"[Fehler] OpenUTAU Rendering fehlgeschlagen: {e}")
        return False

# ── API für DiffSinger (OpenVPI) ─────────────────────────────────────────────
def diffsinger_synthese(melodie_daten, silben, bpm, output_wav_pfad):
    """
    Erstellt ein DiffSinger/OpenVPI Projekt und versucht, es zu rendern.
    Dies ist eine Schnittstelle für DiffSinger Python-Inference.
    """
    ds_pfad = output_wav_pfad.replace(".wav", ".ds")
    
    # Erstelle rudimentäre .ds Datei für DiffSinger
    ds_data = {
        "bpm": bpm,
        "notes": []
    }
    
    current_time = 0.0
    silben_idx = 0
    quarter_sec = 60.0 / bpm
    
    for pitch, dauer in melodie_daten:
        if pitch is None:
            current_time += dauer * quarter_sec
            continue
            
        lyric = silben[silben_idx] if silben_idx < len(silben) else "a"
        silben_idx += 1
        
        ds_data["notes"].append({
            "lyric": lyric,
            "midi": pitch,
            "time": current_time,
            "duration": dauer * quarter_sec
        })
        current_time += dauer * quarter_sec
        
    with open(ds_pfad, "w", encoding="utf-8") as f:
        json.dump(ds_data, f, indent=4, ensure_ascii=False)
        
    print(f"[DiffSinger] Projektdatei erstellt: {ds_pfad}")
    print("[DiffSinger] (Auto-Rendering erfordert lokale DiffSinger Python-Umgebung. Bitte .ds Datei manuell rendern oder CLI konfigurieren.)")
    return False

# ── Fallback (Pedalboard Synth) ─────────────────────────────────────────────
def generiere_lokale_vocals(melodie_daten, silben, bpm, output_wav_pfad, **kwargs):
    import tempfile
    import pyttsx3
    import pyworld as pw
    from scipy.interpolate import interp1d
    from scipy.signal import resample, butter, filtfilt
    from pedalboard import Pedalboard, Chorus, Reverb, Compressor, Delay, LadderFilter
    import os, soundfile as sf, numpy as np
    
    SAMPLERATE = 44100
    quarter_sec = 60.0 / bpm
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
            breath = np.random.normal(0, 0.004, noise_len)
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
            
            if prev_pitch_hz is not None and prev_pitch_hz > 0:
                glide_frames = min(int(0.060 / frame_period), len(f0_vocoded) // 3)
                for j in range(glide_frames):
                    if f0_vocoded[j] > 0:
                        alpha = (1 - np.cos(np.pi * j / glide_frames)) / 2
                        f0_vocoded[j] = prev_pitch_hz * (1.0 - alpha) + target_hz * alpha
            
            vibrato_onset_frames = int(0.300 / frame_period)
            if target_duration > 0.400 and len(f0_vocoded) > vibrato_onset_frames:
                for j in range(len(f0_vocoded)):
                    if f0_vocoded[j] > 0:
                        t_sec = j * frame_period
                        vib_env = min(1.0, max(0.0, (j - vibrato_onset_frames) / (0.200 / frame_period)))
                        rate = 5.2 + 0.3 * np.sin(2 * np.pi * 0.8 * t_sec)
                        depth = 0.45 * vib_env
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
            print(f"[Warnung] Vocoder Fehler für '{lyric}': {e}")
            final_audio.append(np.zeros(target_frames_len, dtype=np.float64))
            prev_pitch_hz = None
    
    if os.path.exists(temp_wav):
        try: os.remove(temp_wav)
        except: pass
    
    final_audio_np = np.concatenate(final_audio) if final_audio else np.zeros(SAMPLERATE)
    
    board = Pedalboard([
        Delay(delay_seconds=0.012, feedback=0.0, mix=0.15),
        Compressor(threshold_db=-20.0, ratio=3.0, attack_ms=5.0, release_ms=80.0),
        Chorus(rate_hz=1.2, depth=0.08, mix=0.12),
        Reverb(room_size=0.35, damping=0.7, wet_level=0.08, dry_level=0.95)
    ])
    
    audio_stereo = np.vstack((final_audio_np, final_audio_np)).astype(np.float32)
    audio_stereo = board(audio_stereo, SAMPLERATE)
    
    peak = np.max(np.abs(audio_stereo))
    if peak > 0:
        audio_stereo = audio_stereo / peak * 0.88
    
    sf.write(output_wav_pfad, audio_stereo.T, SAMPLERATE)
    print(f"[OK] Verbesserte KI-Vocals generiert: {output_wav_pfad}")


# ── MusicXML & NEUTRINO ──────────────────────────────────────────────────────
def _quantisiere_dauer(d: float) -> float:
    erlaubt = [0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
    return min(erlaubt, key=lambda x: abs(x - d))

def erstelle_musicxml(melodie_daten, liedtext_silben, bpm, output_xml_pfad):
    try:
        from music21 import stream, note, tempo, meter, expressions, dynamics
    except ImportError:
        print("[Warnung] music21 nicht installiert. MusicXML kann nicht generiert werden.")
        return ""
        
    s = stream.Stream()
    s.append(tempo.MetronomeMark(number=bpm))
    s.append(meter.TimeSignature("4/4"))
    silben_index = 0
    
    for pitch, dauer in melodie_daten:
        dauer_q = _quantisiere_dauer(float(dauer))
        if pitch is None:
            r = note.Rest(quarterLength=dauer_q)
            s.append(r)
        else:
            if silben_index < len(liedtext_silben):
                n_ = note.Note(pitch, quarterLength=dauer_q)
                n_.addLyric(liedtext_silben[silben_index])
                if dauer >= 1.0:
                    n_.expressions.append(expressions.TextExpression("vibrato"))
                s.append(n_)
                if silben_index % 8 == 0:
                    s.insert(n_.offset, dynamics.Dynamic("mf"))
                silben_index += 1
                
    pfad = s.write("musicxml", fp=output_xml_pfad)
    print(f"[OK] MusicXML: {pfad}")
    return str(pfad)

def extract_data_from_musicxml(xml_pfad):
    """
    Helper function to parse a MusicXML file and extract melody_data, silben, and bpm
    using music21 first, and falling back to a lightweight ElementTree parser.
    """
    try:
        from music21 import converter, note, tempo
        score = converter.parse(xml_pfad)
        
        # 1. Extract BPM
        bpm = 148
        for el in score.recurse():
            if isinstance(el, tempo.MetronomeMark):
                if el.number:
                    bpm = float(el.number)
                    break
        
        # 2. Extract notes, rests, and lyrics
        melody_data = []
        silben = []
        for el in score.recurse():
            if isinstance(el, note.Note):
                pitch = el.pitch.midi
                dauer = float(el.duration.quarterLength)
                melody_data.append((pitch, dauer))
                if el.lyrics:
                    lyric_text = "".join([l.text for l in el.lyrics if l.text])
                    silben.append(lyric_text if lyric_text else "a")
                else:
                    silben.append("a")
            elif isinstance(el, note.Rest):
                dauer = float(el.duration.quarterLength)
                melody_data.append((None, dauer))
                
        if not silben:
            silben = ["a"]
            
        if len(melody_data) > 0:
            return melody_data, silben, bpm
    except Exception as e:
        print(f"[Fallback Parser] music21 parsing failed: {e}. Trying ElementTree parser...")
        
    # ElementTree backup parser
    import xml.etree.ElementTree as ET
    melody_data = []
    silben = []
    bpm = 148
    try:
        tree = ET.parse(xml_pfad)
        root = tree.getroot()
        
        divisions = 1
        div_elem = root.find(".//divisions")
        if div_elem is not None:
            divisions = int(div_elem.text)
            
        sound_elem = root.find(".//sound")
        if sound_elem is not None and "tempo" in sound_elem.attrib:
            bpm = float(sound_elem.attrib["tempo"])
            
        step_offsets = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        
        for note_elem in root.findall(".//note"):
            dur_elem = note_elem.find("duration")
            duration_val = int(dur_elem.text) if dur_elem is not None else divisions
            duration_quarters = duration_val / divisions
            
            rest_elem = note_elem.find("rest")
            if rest_elem is not None:
                melody_data.append((None, duration_quarters))
                continue
                
            pitch_elem = note_elem.find("pitch")
            if pitch_elem is not None:
                step = pitch_elem.find("step").text
                octave = int(pitch_elem.find("octave").text)
                alter_elem = pitch_elem.find("alter")
                alter = int(alter_elem.text) if alter_elem is not None else 0
                
                midi_pitch = 12 * (octave + 1) + step_offsets.get(step, 0) + alter
                melody_data.append((midi_pitch, duration_quarters))
            else:
                melody_data.append((None, duration_quarters))
                
            lyric_elem = note_elem.find(".//lyric/text")
            if lyric_elem is not None and lyric_elem.text:
                silben.append(lyric_elem.text)
            else:
                silben.append("a")
                
        if not silben:
            silben = ["a"]
        return melody_data, silben, bpm
    except Exception as ex:
        print(f"[Fallback XML Parser] Failed to parse: {ex}")
        return [], [], bpm

def neutrino_synthese(xml_pfad, output_wav_pfad, neutrino_pfad, model_pfad):
    try:
        if not os.path.exists(neutrino_pfad):
            raise FileNotFoundError(f"NEUTRINO nicht gefunden unter {neutrino_pfad}")
            
        bin_pfad = os.path.abspath(os.path.join(neutrino_pfad, "bin"))
        if bin_pfad not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_pfad + os.pathsep + os.environ.get("PATH", "")
            
        ml_exe   = os.path.join(bin_pfad, "musicXMLtoLabel.exe")
        neu_exe  = os.path.join(bin_pfad, "neutrino.exe")
        
        if not os.path.exists(ml_exe) or not os.path.exists(neu_exe):
            raise FileNotFoundError(f"NEUTRINO executables missing in {bin_pfad}")
            
        import tempfile
        import pyworld as pw
        import librosa
        from scipy.signal import resample
        
        with tempfile.TemporaryDirectory() as td:
            full_l   = os.path.join(td, "temp_vocals.lab")
            mono_l   = os.path.join(td, "temp_vocals_mono.lab")
            tim_l    = os.path.join(td, "temp_vocals_timing.lab")
            f0_f     = os.path.join(td, "temp_vocals.f0")
            mel_f    = os.path.join(td, "temp_vocals.melspec")
            tmp_w    = os.path.join(td, "temp_vocals_out.wav")
            
            # 1. MusicXML zu Label (Phoneme)
            print("[NEUTRINO] Generating label files...")
            subprocess.run(
                [ml_exe, os.path.abspath(xml_pfad), os.path.abspath(full_l), os.path.abspath(mono_l)],
                check=True, cwd=neutrino_pfad, capture_output=True, timeout=120)
                
            # 2. NEUTRINO v3 generiert Akustik-Parameter
            print("[NEUTRINO] Running neutrino.exe...")
            subprocess.run(
                [neu_exe, os.path.abspath(full_l), os.path.abspath(tim_l), os.path.abspath(f0_f),
                 os.path.abspath(mel_f), os.path.abspath(tmp_w), model_pfad, "-n", "4", "-t"],
                check=True, cwd=neutrino_pfad, capture_output=True, timeout=120)
                 
            # Ensure f0 and melspec files are successfully generated
            if not os.path.exists(f0_f) or not os.path.exists(mel_f):
                raise FileNotFoundError(f"NEUTRINO did not generate expected .f0 or .melspec files. f0: {os.path.exists(f0_f)}, melspec: {os.path.exists(mel_f)}")
            
            # Verify if neutrino.exe writes a wav directly (which it won't with 5 positional arguments, but let's check)
            if os.path.exists(tmp_w):
                shutil.move(tmp_w, output_wav_pfad)
                print(f"[OK] NEUTRINO Vocals (direct WAV): {output_wav_pfad}")
                return True
                
            # Since it doesn't write wav directly, use pyworld to synthesize the wav file from the f0 and melspec data.
            print("[NEUTRINO] Synthesizing WAV using local vocoder (pyworld) from f0/melspec...")
            
            # Load f0 and melspec
            f0 = np.fromfile(f0_f, dtype=np.float32).astype(np.float64)
            melspec_flat = np.fromfile(mel_f, dtype=np.float32)
            
            num_frames = len(f0)
            if num_frames == 0 or len(melspec_flat) == 0:
                raise ValueError("Generated f0 or melspec is empty.")
                
            num_channels = len(melspec_flat) // num_frames
            melspec = melspec_flat.reshape(num_frames, num_channels)
            
            fs = 48000  # standard NEUTRINO v3.1 model sample rate
            fft_size = pw.get_cheaptrick_fft_size(fs)
            num_bins = fft_size // 2 + 1
            
            # Reconstruct linear spectrogram from log-mel spectrogram
            mel_linear = np.exp(np.clip(melspec, -20.0, 20.0))
            mel_fb = librosa.filters.mel(sr=fs, n_fft=fft_size, n_mels=num_channels)
            mel_fb_pinv = np.linalg.pinv(mel_fb)
            sp_approx = np.matmul(mel_linear, mel_fb_pinv.T)
            sp_approx = np.clip(sp_approx, 1e-10, None)
            
            # Construct aperiodicity
            frequencies = np.linspace(0, fs / 2, num_bins)
            ap = np.zeros_like(sp_approx)
            for t in range(num_frames):
                if f0[t] == 0:
                    ap[t, :] = 1.0
                else:
                    ap[t, :] = 0.15 + 0.7 * (frequencies / (fs / 2))
                    
            f0 = np.ascontiguousarray(f0)
            sp_approx = np.ascontiguousarray(sp_approx)
            ap = np.ascontiguousarray(ap)
            
            synthesized = pw.synthesize(f0, sp_approx, ap, fs)
            
            # Resample if needed
            if fs != SAMPLERATE:
                target_len = int(len(synthesized) * SAMPLERATE / fs)
                synthesized = resample(synthesized, target_len)
                
            peak = np.max(np.abs(synthesized))
            if peak > 0:
                synthesized = synthesized / peak * 0.88
                
            synthesized_stereo = np.vstack((synthesized, synthesized)).T.astype(np.float32)
            
            os.makedirs(os.path.dirname(os.path.abspath(output_wav_pfad)), exist_ok=True)
            sf.write(output_wav_pfad, synthesized_stereo, SAMPLERATE)
            print(f"[OK] NEUTRINO Vocals (synthesized): {output_wav_pfad}")
            return True
            
    except Exception as e:
        print(f"[NEUTRINO Engine Failed] Error: {e}. Executing robust fallback to local vocals...")
        try:
            melody_data, silben, bpm = extract_data_from_musicxml(xml_pfad)
            if len(melody_data) > 0:
                generiere_lokale_vocals(melody_data, silben, bpm, output_wav_pfad)
                print(f"[Fallback OK] Rendered local vocals to {output_wav_pfad}")
                return True
            else:
                print("[Fallback Failed] No melody data parsed from MusicXML.")
                return False
        except Exception as ex:
            print(f"[Fallback Failed] Critical error rendering local vocals fallback: {ex}")
            return False



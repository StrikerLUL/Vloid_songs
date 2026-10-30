# musikvideo.py – Das Video zum Song, das dem Song folgt (1.5.0 V3, V4, V5, V9 bis V12)
#
# Bis 1.4 lief der Text vor einem stehenden Bild. Jetzt malt video_szenen.py jedes Bild aus dem, was der Song gerade
# macht (Songkarte: Sektion, Schlag, Kick, Snare, Akkord, Melodie; dazu das Spektrum des fertigen Mixes), und ffmpeg
# legt den Text darüber: wie geschrieben mit Kanji, Wort für Wort im Takt eingefärbt, darunter Romaji und deine
# Übersetzung, dazu Sektion, Akkord, eine Titelkarte am Anfang und der Abspann am Ende. Gezeichnet wird in 960×540,
# ffmpeg vergrößert auf 1080p; der Text (libass) ist gestochen scharf.
import bisect
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

import karaoke
import songkarte
import video_szenen as szenen

log = logging.getLogger(__name__)

FPS = 30
SIZE = karaoke.VIDEO_SIZE
BANDS = 48
WINDOW = 2048
FADE_IN, FADE_OUT = 1.0, 2.5           # Sekunden schwarz → Bild und Bild → schwarz
TITLE_MIN_GAP = 4.0                    # so lange muss bis zur ersten Zeile Platz sein, sonst kein großer Titel
CREDITS_SECONDS = 7.0
PREVIEW_SECONDS = 10.0
LABEL_SECONDS = 3.0                    # so lange steht der Name einer neuen Sektion oben links
ProgressFn = Callable[[float, str], None]


@dataclass
class Options:
    """Was im Video steht; jedes mit Schalter in den Einstellungen (Tab Video)."""
    scene: str = ""                    # "" = wie der Stil, ein Stilname oder „Textkunst“
    motion: str = "Stil"               # Stil, ruhig, lebhaft
    kanji: bool = True                 # V2: Text wie geschrieben statt Hiragana
    romaji: bool = True
    german: bool = True
    chords: bool = True                # V5
    melody_line: bool = True           # V5
    spectrum: bool = True              # V5
    words: bool = True                 # V8: Bilder aus dem Text
    titles: bool = True                # V10: Titelkarte und Abspann
    hud: bool = True                   # Ablaufleiste und Schläge
    figure: tuple = ()                 # V9: (Mund zu, Mund auf)
    pictures: dict = field(default_factory=dict)   # V13: {Sektionsart: Bild}
    background: str = ""               # eigenes Bild


def options_from(settings) -> Options:
    s = settings
    return Options(scene=s.video_scene, motion=s.video_motion, kanji=s.video_kanji, romaji=s.video_romaji,
                   german=s.video_german, chords=s.video_chords, melody_line=s.video_melody_line,
                   spectrum=s.video_spectrum, words=s.video_words, titles=s.video_titles, hud=s.video_hud,
                   figure=tuple(p for p in (s.video_figure, s.video_figure_open) if p and os.path.exists(p)),
                   background=s.video_background if s.video_background and os.path.exists(s.video_background) else "")


# ── Ton: Spektrum und Lautstärke pro Bild ─────────────────────────────────────
def read_audio(path: str, ffmpeg: Optional[str] = None) -> tuple:
    """(Mono-Samples, Rate). Liest WAV/FLAC mit soundfile, MP3 notfalls über ffmpeg."""
    try:
        import soundfile as sf
        data, rate = sf.read(path, dtype="float32", always_2d=True)
        return data.mean(axis=1), rate
    except (RuntimeError, OSError):
        pass
    exe = ffmpeg or karaoke.find_ffmpeg()
    if not exe:
        raise RuntimeError("Für das Video fehlt ffmpeg (winget install Gyan.FFmpeg).")
    done = subprocess.run([exe, "-v", "error", "-i", path, "-ac", "1", "-ar", "22050", "-f", "f32le", "-"],
                          capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise RuntimeError(f"Der Song lässt sich nicht lesen: {done.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(done.stdout, dtype=np.float32), 22050


@dataclass
class Sound:
    bands: np.ndarray                  # (Bilder, BANDS) 0..1
    level: np.ndarray                  # (Bilder,) 0..1
    mono: np.ndarray
    rate: int
    peak: float = 0.0                  # lautester Wert des Songs; einmal gemessen statt in jedem Bild

    def __post_init__(self) -> None:
        if not self.peak:
            self.peak = float(np.max(np.abs(self.mono))) if len(self.mono) else 0.0

    def wave(self, t: float, points: int = 160) -> np.ndarray:
        i = int(t * self.rate)
        part = self.mono[max(0, i - 1024):i + 1024]
        if len(part) < 32:
            return np.zeros(points)
        part = part[::max(1, len(part) // points)][:points]
        return np.clip(part / (self.peak or 1.0), -1, 1)


def analyse(mono: np.ndarray, rate: int, frames: int, fps: int = FPS) -> Sound:
    """Spektrum in BANDS Bändern (40 Hz bis 12 kHz, logarithmisch) und Lautstärke für jedes Bild, schnell steigend
    und langsam fallend wie ein Pegel."""
    edges = np.geomspace(40, min(12000, rate / 2 - 1), BANDS + 1)
    freqs = np.fft.rfftfreq(WINDOW, 1 / rate)
    which = np.clip(np.searchsorted(edges, freqs) - 1, -1, BANDS)
    window = np.hanning(WINDOW).astype(np.float32)
    padded = np.concatenate([np.zeros(WINDOW, np.float32), mono.astype(np.float32), np.zeros(WINDOW, np.float32)])
    raw = np.zeros((frames, BANDS), dtype=np.float32)
    level = np.zeros(frames, dtype=np.float32)
    for begin in range(0, frames, 512):
        idx = np.arange(begin, min(frames, begin + 512))
        starts = (idx / fps * rate).astype(np.int64) + WINDOW // 2
        chunk = padded[starts[:, None] + np.arange(WINDOW)[None, :]]
        level[idx] = np.sqrt(np.mean(chunk ** 2, axis=1))
        mag = np.abs(np.fft.rfft(chunk * window, axis=1))
        for b in range(BANDS):
            sel = which == b
            if sel.any():
                raw[idx, b] = mag[:, sel].mean(axis=1)
    raw = np.log1p(raw * 10)
    top = np.percentile(raw, 97, axis=0) + 1e-6
    bands = np.clip(raw / top[None, :], 0, 1)
    peak = float(np.percentile(level, 99)) or 1.0
    level = np.clip(level / peak, 0, 1)
    for i in range(1, frames):                 # Pegel: sofort hoch, langsam runter
        bands[i] = np.maximum(bands[i], bands[i - 1] * 0.82)
        level[i] = max(level[i], level[i - 1] * 0.9)
    return Sound(bands, level, mono, rate)


# ── was der Song in jedem Bild macht ─────────────────────────────────────────
class Timeline:
    """Baut aus Songkarte, Text und Ton für jede Zeit ein video_szenen.Frame."""

    def __init__(self, found: Optional[songkarte.Map], lines: list, sound: Optional[Sound], length: float,
                 motifs: Optional[list] = None, bpm: float = 120.0):
        self.map = found or songkarte.Map(bpm=bpm, length=length)
        if not self.map.beats:
            step = 60.0 / (self.map.bpm or bpm)
            self.map.beats = [round(i * step, 4) for i in range(int(length / step) + 1)]
        self.lines = lines
        self.sound = sound
        self.length = length
        self.motifs = motifs or [set() for _ in lines]
        self.line_starts = [line["start"] - karaoke.LEAD_SECONDS for line in lines]
        self.note_starts = [n[0] for n in self.map.melody]
        pitches = [n[2] for n in self.map.melody]
        self.pitch_range = (min(pitches), max(pitches)) if pitches else (60, 72)
        total = self.map.length or length or 1.0
        self.sections = [(s.start / total, min(1.0, s.end / total), s.kind) for s in self.map.sections]
        self.last_chorus_start = max((s.start for s in self.map.sections if s.kind == "Chorus"), default=None)

    @staticmethod
    def _since(times: list, t: float) -> float:
        i = bisect.bisect_right(times, t) - 1
        return t - times[i] if i >= 0 else 1e9

    def frame(self, t: float, index: int = 0) -> szenen.Frame:
        f = szenen.Frame(t=t, index=index)
        sec = self.map.section_at(t)
        if sec is not None:
            f.kind = sec.kind
            f.progress = (t - sec.start) / max(1e-6, sec.end - sec.start)
            f.energy = sec.energy
            f.vocals = sec.vocals
            f.chorus = sec.kind == "Chorus"
            f.last_chorus = f.chorus and self.last_chorus_start is not None and sec.start >= self.last_chorus_start
            f.change = math.exp(-(t - sec.start) / 0.6) if sec.start > 0 else 0.0
            f.index = self.map.sections.index(sec)
        beat, phase = self.map.beat_at(t)
        f.beat, f.phase = beat, phase
        f.downbeat = beat >= 0 and beat % max(1, self.map.accents) == 0
        f.beat_pulse = math.exp(-phase * 3.5) if beat >= 0 else 0.0
        f.kick = math.exp(-self._since(self.map.kicks, t) / 0.18)
        f.snare = math.exp(-self._since(self.map.snares, t) / 0.15)
        f.crash = math.exp(-self._since(self.map.crashes, t) / 0.5)
        if self.sound is not None:
            i = min(len(self.sound.level) - 1, max(0, int(round(t * FPS))))
            f.level = float(self.sound.level[i])
            f.bands = self.sound.bands[i]
            f.wave = self.sound.wave(t)
            if sec is None:
                f.energy = 0.3 + 0.6 * f.level
        name, _ = self.map.chord_at(t)
        f.chord_minor = name[1:2] == "m" or name[2:3] == "m" if name else False
        lo = bisect.bisect_left(self.note_starts, t - 6.0)
        f.notes = [n for n in self.map.melody[lo:bisect.bisect_right(self.note_starts, t + 4.0)] if n[1] > t - 2.0]
        f.singing = any(n[0] <= t < n[1] for n in f.notes)
        f.pitch_range = self.pitch_range
        i = bisect.bisect_right(self.line_starts, t) - 1
        if 0 <= i < len(self.lines) and t <= self.lines[i]["end"] + karaoke.HOLD_SECONDS:
            f.motifs = self.motifs[i]
        f.song_progress = min(1.0, t / max(1e-6, self.length))
        f.sections = self.sections
        f.fade = min(1.0, t / FADE_IN, max(0.0, (self.length - t) / FADE_OUT))
        crash_now = self._since(self.map.crashes, t) < 1.0 / FPS
        if crash_now and (f.chorus or f.kind == "Drop") and f.progress < 0.05:
            f.flash = 0.8
        elif f.chorus and f.snare > 0.9:
            f.flash = 0.25
        return f


# ── Text (libass) ─────────────────────────────────────────────────────────────
def _ass_color(color: str, alpha: int = 0) -> str:
    c = color.lstrip("#")
    return f"&H{alpha:02X}{c[4:6]}{c[2:4]}{c[0:2]}".upper()


def _cs(seconds: float) -> int:
    return max(0, int(round(seconds * 100)))


def chunks(line: dict, kanji: bool = True) -> list:
    """[(Text, Hundertstel)]: die Zeile im Takt der Silben eingefärbt. Mit Kanji Wort für Wort nach lyrics.shown_parts,
    die Moren eines Worts bestimmen, wie lange es dauert; sonst Silbe für Silbe wie gesungen (Hiragana)."""
    sylls = line["syllables"]
    bounds = [s[0] for s in sylls] + [sylls[-1][1]]
    if not kanji or not line.get("text"):
        return [(karaoke._clean(s[2]), _cs(bounds[j + 1] - s[0])) for j, s in enumerate(sylls)]
    from lyrics import shown_parts
    parts = shown_parts(line["text"])
    total = sum(n for _, n in parts) or 1.0
    n = len(sylls)

    def at(share: float) -> float:
        x = min(n, max(0.0, share * n))
        k = min(n - 1, int(x))
        return bounds[k] + (bounds[k + 1] - bounds[k]) * (x - k)

    out, done = [], 0.0
    for text, weight in parts:
        begin, done = at(done / total), done + weight
        out.append((karaoke._clean(text), _cs(at(done / total) - begin)))
    return out


def ass(lines: list, scene: szenen.Scene, opts: Options, style: str, title: str = "", subtitle: str = "",
        credits: tuple = (), found: Optional[songkarte.Map] = None, length: float = 0.0, offset: float = 0.0,
        until: Optional[float] = None, strength: float = 1.0) -> str:
    """Untertitel fürs Musikvideo, Zeiten ab offset (Vorschau) bis until."""
    width, height = SIZE
    look = scene.look
    sung, _, edge = karaoke.colors(style) if not look.sung else (look.sung, "", karaoke.colors(style)[2])
    light = scene.palette[3]
    big = int(height / 12 * look.size)
    bold = -1 if look.bold else 0
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Line,{look.font},{big},{_ass_color(sung)},&H00FFFFFF,{_ass_color(edge)},&H80000000,{bold},0,0,0,"
        f"100,100,0,0,1,{look.outline:g},2,5,40,40,0,1",
        f"Style: Romaji,{look.latin},{height // 26},&H18FFFFFF,&H18FFFFFF,{_ass_color(edge)},&H80000000,0,0,0,0,"
        f"100,100,1,0,1,2,0,5,40,40,0,1",
        f"Style: Deutsch,{look.latin},{height // 30},{_ass_color(light, 0x10)},{_ass_color(light, 0x10)},"
        f"{_ass_color(edge)},&H80000000,0,-1,0,0,100,100,0,0,1,2,0,5,40,40,0,1",
        f"Style: Next,{look.font},{height // 26},&H70FFFFFF,&H70FFFFFF,{_ass_color(edge)},&H80000000,0,0,0,0,"
        f"100,100,0,0,1,2,0,5,40,40,0,1",
        f"Style: Label,{look.latin},{height // 34},&H40FFFFFF,&H40FFFFFF,&H90000000,&H00000000,-1,0,0,0,100,100,1,0,"
        f"1,1.5,0,7,40,40,26,1",
        f"Style: Chord,{look.latin},{height // 24},&H10FFFFFF,&H10FFFFFF,&H90000000,&H00000000,-1,0,0,0,100,100,0,0,"
        f"1,2,0,1,48,40,40,1",
        f"Style: Title,{look.font},{height // 9},&H00FFFFFF,&H00FFFFFF,{_ass_color(edge)},&H80000000,-1,0,0,0,100,"
        f"100,0,0,1,4,3,5,40,40,0,1",
        f"Style: Sub,{look.latin},{height // 26},{_ass_color(light)},{_ass_color(light)},{_ass_color(edge)},"
        f"&H80000000,0,0,0,0,100,100,1,0,1,2,0,5,40,40,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    end_all = until if until is not None else length or (lines[-1]["end"] + 5 if lines else 0)

    def event(start: float, end: float, style_name: str, text: str, layer: int = 1) -> None:
        start, end = max(start, offset), min(end, end_all)
        if end - start < 0.05:
            return
        events.append(f"Dialogue: {layer},{karaoke._time(start - offset)},{karaoke._time(end - offset)},"
                      f"{style_name},,0,0,0,,{text}")

    y = int(height * look.y)
    first = lines[0]["start"] if lines else length
    card = opts.titles and title and first - karaoke.LEAD_SECONDS >= TITLE_MIN_GAP
    if card:
        until_card = min(first - karaoke.LEAD_SECONDS - 0.5, 8.0)
        event(0.4, until_card, "Title", "{\\fad(500,500)}" + karaoke._clean(title), 2)
        if subtitle:
            event(0.8, until_card, "Sub", f"{{\\fad(500,500)\\pos({width // 2},{int(height * 0.6)})}}"
                  + karaoke._clean(subtitle), 2)
    if title:
        event(until_card + 0.5 if card else 0.0, length or end_all, "Label",
              f"{{\\pos(40,{height - 96})}}" + karaoke._clean(title), 0)
    lively = strength > 0.5
    shown_until = 0.0
    for i, line in enumerate(lines):
        following = lines[i + 1] if i + 1 < len(lines) else None
        start = max(line["start"] - karaoke.LEAD_SECONDS, shown_until)
        end = line["end"] + karaoke.HOLD_SECONDS
        if following:
            end = max(line["end"], min(end, following["start"] - karaoke.LEAD_SECONDS))
        shown_until = end
        sec = found.section_at(line["start"]) if found else None
        pop = "{\\fscx112\\fscy112\\t(0,220,\\fscx100\\fscy100)}" if lively and sec is not None and \
            sec.kind == "Chorus" else ""
        lead = [f"{{\\k{_cs(line['start'] - start)}}}"] if line["start"] > start else []
        body = "".join(f"{{\\kf{max(1, cs) if text.strip() else cs}}}{text}" for text, cs in chunks(line, opts.kanji))
        event(start, end, "Line", f"{{\\pos({width // 2},{y})}}" + pop + "".join(lead) + body)
        below = y + int(height * 0.085)
        if opts.romaji and line.get("romaji"):
            event(start, end, "Romaji", f"{{\\pos({width // 2},{below})\\fad(150,150)}}"
                  + karaoke._clean(line["romaji"]))
            below += int(height * 0.055)
        if opts.german and line.get("de"):
            event(start, end, "Deutsch", f"{{\\pos({width // 2},{below})\\fad(150,150)}}" + karaoke._clean(line["de"]))
            below += int(height * 0.05)
        if following:
            text = following.get("text") if opts.kanji and following.get("text") else karaoke.text(following)
            event(start, end, "Next", f"{{\\pos({width // 2},{max(below + 20, int(height * 0.79))})}}"
                  + karaoke._clean(text))
    if found is not None:
        for sec in found.sections:
            event(sec.start + 0.1, min(sec.end, sec.start + LABEL_SECONDS), "Label",
                  f"{{\\fad(250,400)\\pos(40,58)}}{karaoke._clean(found.label(sec))}", 0)
        if opts.chords:
            for k, (start, end, name) in enumerate(found.chords):
                nxt = found.chords[k + 1][2] if k + 1 < len(found.chords) else ""
                event(start, end, "Chord", f"{{\\pos(48,{height - 30})}}{karaoke._clean(name)}"
                      + (f"{{\\fs{height // 40}\\alpha&H80&}}  → {karaoke._clean(nxt)}" if nxt else ""), 0)
    if opts.titles and credits:
        # der Abspann läuft im Outro wie am Ende eines Animes, ohne Outro in den letzten Sekunden
        outro = next((s.start for s in found.sections if s.kind == "Outro"), None) if found else None
        begin = max(lines[-1]["end"] + karaoke.HOLD_SECONDS + 0.5 if lines else 0.0,
                    min(outro, length - CREDITS_SECONDS) if outro is not None else length - CREDITS_SECONDS)
        if length - begin >= 2.5:
            text = "\\N".join(karaoke._clean(c) for c in credits)
            event(begin, length - 0.3, "Sub", f"{{\\fad(600,600)\\pos({width // 2},{int(height * 0.45)})}}" + text, 2)
    return "\n".join(head + events) + "\n"


# ── Rendern ──────────────────────────────────────────────────────────────────
def render(audio: str, out: str, lines: list, found: Optional[songkarte.Map], style: str, opts: Options,
           title: str = "", subtitle: str = "", credits: tuple = (), seed: int = 0, analysis_audio: str = "",
           start: float = 0.0, seconds: Optional[float] = None, ffmpeg: Optional[str] = None,
           progress: Optional[ProgressFn] = None) -> str:
    """
    Das Musikvideo als MP4 in 1080p. start/seconds: nur ein Stück (Vorschau, V11). analysis_audio: eine WAV zum
    Messen des Spektrums (schneller als die MP3). Wirft RuntimeError ohne ffmpeg oder wenn ffmpeg scheitert.
    """
    import cancel
    report = progress or (lambda fraction, message: None)
    exe = ffmpeg or karaoke.find_ffmpeg()
    if not exe:
        raise RuntimeError("Für das Video fehlt ffmpeg (winget install Gyan.FFmpeg).")
    mono, rate = read_audio(analysis_audio if analysis_audio and os.path.exists(analysis_audio) else audio, exe)
    length = len(mono) / rate
    if found is not None and found.length:
        length = min(length, found.length + 8.0) if found.length < length else length
    first, last = max(0.0, start), length if seconds is None else min(length, start + seconds)
    frames = max(1, int(math.ceil((last - first) * FPS)))
    total = int(math.ceil(length * FPS)) + 1
    report(0.02, "Video: höre den Song an...")
    sound = analyse(mono, rate, total)
    scene = szenen.for_style(style, opts.scene)
    strength = szenen.motion(scene, opts.motion)
    import textmotive
    motifs = textmotive.for_lines(lines) if opts.words else [set() for _ in lines]
    weather = textmotive.weather(lines) if opts.words else None
    chat = opts.words and bool(textmotive.song_motifs(lines).get("chat"))
    chars = "".join(line.get("text") or karaoke.text(line) for line in lines)
    timeline = Timeline(found, lines, sound, length, motifs, found.bpm if found else 120.0)
    painter = szenen.Painter(scene, strength, seed, chars, weather, chat, opts.background or None, opts.pictures,
                             opts.figure or None, opts.melody_line, opts.spectrum, opts.hud)
    folder = os.path.dirname(os.path.abspath(out))
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(out))[0]
    subtitles = stem + ".ass"
    with open(os.path.join(folder, subtitles), "w", encoding="utf-8") as f:
        f.write(ass(lines, scene, opts, style, title, subtitle, credits, found, length, first, last, strength))
    flags = "neighbor" if scene.pixel else "bicubic"
    width, height = SIZE
    audio_in = (["-ss", f"{first:.3f}"] if first > 0 else []) + (["-t", f"{last - first:.3f}"] if seconds else [])
    command = [exe, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{szenen.W}x{szenen.H}", "-r", str(FPS), "-i", "-",
               *audio_in, "-i", os.path.abspath(audio),
               "-filter_complex", f"[0:v]scale={width}:{height}:flags={flags},ass={subtitles}[video]",
               "-map", "[video]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", os.path.abspath(out)]
    log.info("Musikvideo: %s (%s, %d Bilder)", out, scene.name, frames)
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(command, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                       stderr=errors, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            raise RuntimeError(f"ffmpeg konnte das Video nicht bauen: {e}") from e
        broken = False
        with cancel.watched(process):
            try:
                for k in range(frames):
                    if k % FPS == 0:
                        cancel.check()
                        report(0.05 + 0.9 * k / frames, f"Video: Bild {k} von {frames}...")
                    t = first + k / FPS
                    image = painter.frame(timeline.frame(t, k))
                    process.stdin.write(image.tobytes())
            except (BrokenPipeError, OSError):
                broken = True
            except cancel.Cancelled:
                process.kill()
                raise
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            code = process.wait()
        errors.seek(0)
        message = errors.read().decode("utf-8", errors="replace").strip()
    if code != 0 or broken:
        raise RuntimeError(f"ffmpeg konnte das Video nicht bauen: {message[-400:] or 'Abbruch'}")
    try:
        os.remove(os.path.join(folder, subtitles))
    except OSError:
        pass
    report(1.0, "Video fertig")
    return out


def for_song(result, out: str, label: str = "", audio: Optional[str] = None, preview: bool = False,
             progress: Optional[ProgressFn] = None) -> str:
    """Das Musikvideo eines fertigen Songs (pipeline.SongResult): Text und Songkarte aus seinem Ordner, Titel aus
    label (sonst der Stil), Abspann mit der Stimme. preview: nur PREVIEW_SECONDS ab dem ersten Refrain (V11)."""
    import youtube
    s = result.settings
    source = audio or result.audio
    if not source or not os.path.exists(source):
        raise RuntimeError("Der Song fehlt, erst einen Song erzeugen.")
    lines = karaoke.load(os.path.join(result.output_dir, karaoke.FILE))
    found = songkarte.load(os.path.join(result.output_dir, songkarte.FILE))
    style = s.style if s else ""
    opts = options_from(s) if s else Options()
    import bilder
    opts.pictures = bilder.for_song(result) if s and s.ai_backgrounds else {}
    title = label.strip() or style
    subtitle = " · ".join(d for d in youtube.details(result) if d != title)
    start = preview_start(found, lines) if preview else 0.0
    return render(source, out, lines, found, style, opts, title, subtitle, tuple(youtube.credits(result)),
                  result.seed, result.mix_wav or "", start, PREVIEW_SECONDS if preview else None, progress=progress)


def preview_start(found: Optional[songkarte.Map], lines: list) -> float:
    """Wo die Vorschau beginnt: am ersten Refrain, sonst an der ersten Zeile."""
    if found is not None:
        chorus = next((s for s in found.sections if s.kind == "Chorus"), None)
        if chorus is not None:
            return max(0.0, chorus.start - 0.5)
    return max(0.0, lines[0]["start"] - 1.0) if lines else 0.0

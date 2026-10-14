# karaoke.py – Der Liedtext zum Mitlesen: Zeilen mit der Zeit jeder Silbe, für den Player und das Lyric-Video
#
# Die Zeiten kommen aus der Gesangsmelodie, also stimmen sie mit dem fertigen Song überein. Das Lyric-Video baut
# ffmpeg: einfarbiger Hintergrund oder ein Bild (das Titelbild aus youtube.py), die Wellenform des Songs und der
# Text als Karaoke-Untertitel (ASS, libass).
import json
import logging
import os
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

FILE = "liedtext.json"
LINE_GAP_BEATS = 1.0      # so lange Pause beginnt eine neue Zeile
MAX_SYLLABLES = 18        # längere Zeilen werden an der größten Pause geteilt
LEAD_SECONDS = 1.0        # so früh erscheint eine Zeile vor ihrer ersten Silbe
HOLD_SECONDS = 0.8        # so lange bleibt sie nach der letzten stehen

VIDEO_SIZE = (1280, 720)
VIDEO_FPS = 30
VIDEO_FONT = "Meiryo"     # unter Windows immer da; fehlt sie, nimmt libass eine Schrift mit Kana
BACKGROUND = "0x1a1030"
WAVE_COLOR = "0xff4f8b"


def lines(notes: list, syllables: list, bpm: float, plan=None, line_lengths: Optional[dict] = None) -> list:
    """
    Zeilen zum Mitlesen: [{"start", "end", "syllables": [[start, ende, text]]}], Zeiten in Sekunden ab Songanfang.
    notes: die Töne der Gesangsmelodie (pretty_midi.Note), syllables: die Silben dazu in zeitlicher Reihenfolge
    (melody_writer.melody_data). Ein Melisma verlängert die Silbe davor.
    line_lengths {Sektionsart: [Silben pro Zeile]} (aus lyrics.section_lines): die Zeilen wie im Liedtext, auch
    wenn der Text in der Sektion wiederholt wird. Ohne sie beginnt eine neue Zeile nach einer Pause ab einem
    Schlag. Jede Sektion beginnt mit einer neuen Zeile.
    """
    spb = 60.0 / bpm
    sections = []
    for note, syllable in zip(sorted(notes, key=lambda n: n.start), syllables):
        if getattr(syllable, "melisma", False) and sections:
            sections[-1][1][-1][1] = note.end
            continue
        sec = plan.section_at(note.start / spb + 1e-6) if plan is not None else None
        key = (sec.index, sec.kind) if sec is not None else (0, "")
        if not sections or sections[-1][0] != key:
            sections.append((key, []))
        sections[-1][1].append([note.start, note.end, str(syllable), bool(getattr(syllable, "word_start", False))])
    found = []
    for (_, kind), sung in sections:
        lengths = [n for n in (line_lengths or {}).get(kind, []) if n > 0]
        for line in _by_lengths(sung, lengths) if lengths else _by_pauses(sung, LINE_GAP_BEATS * spb):
            found += _split(line)
    return [{"start": round(line[0][0], 3), "end": round(line[-1][1], 3),
             "syllables": [[round(s[0], 3), round(s[1], 3), s[2]] for s in line]} for line in found]


def _by_lengths(sung: list, lengths: list) -> list:
    """Die Silben der Sektion Zeile für Zeile wie im Text; wird der Text wiederholt, beginnen die Zeilen von vorn."""
    out, i, k = [], 0, 0
    while i < len(sung):
        out.append(sung[i:i + lengths[k % len(lengths)]])
        i += lengths[k % len(lengths)]
        k += 1
    return out


def _by_pauses(sung: list, gap: float) -> list:
    out = []
    for item in sung:
        if not out or item[0] - out[-1][-1][1] >= gap - 1e-6:
            out.append([])
        out[-1].append(item)
    return out


def _split(line: list) -> list:
    """Zu lange Zeilen an der größten Pause in ihrer Mitte teilen, bei gleicher Pause an einem Wortanfang."""
    if len(line) <= MAX_SYLLABLES:
        return [line]
    quarter = len(line) // 4
    cut = max(range(max(quarter, 1), len(line) - quarter),
              key=lambda i: (round(line[i][0] - line[i - 1][1], 3), line[i][3], -abs(i - len(line) / 2)))
    return _split(line[:cut]) + _split(line[cut:])


def text(line: dict) -> str:
    return "".join(s[2] for s in line["syllables"])


def save(path: str, found: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"lines": found}, f, ensure_ascii=False)


def load(path: str) -> list:
    """Die Zeilen eines Songs; leer, wenn es keine gibt (Song ohne Gesang oder von einer älteren Version)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("lines", [])
    except (OSError, ValueError, AttributeError) as e:
        log.debug("Kein Liedtext zum Mitlesen in %s: %s", path, e)
        return []


# ── Lyric-Video ──────────────────────────────────────────────────────────────────
def _time(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _clean(syllable: str) -> str:
    return syllable.replace("\\", "").replace("{", "(").replace("}", ")")


def ass(found: list, title: str = "", size: tuple = VIDEO_SIZE) -> str:
    """
    Untertitel im ASS-Format: die laufende Zeile groß in der Mitte, Silbe für Silbe eingefärbt (\\kf), die nächste
    kleiner darunter, oben links der Titel.
    """
    width, height = size
    big, small = height // 12, height // 22
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        # Farben als &HAABBGGRR: gesungen pink, noch nicht gesungen weiß
        f"Style: Line,{VIDEO_FONT},{big},&H008B4FFF,&H00FFFFFF,&H00301A1A,&H80000000,1,0,0,0,100,100,0,0,1,3,1,5,"
        "40,40,0,1",
        f"Style: Next,{VIDEO_FONT},{small},&H60FFFFFF,&H60FFFFFF,&H00301A1A,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,"
        "40,40,0,1",
        f"Style: Title,{VIDEO_FONT},{small},&H90FFFFFF,&H90FFFFFF,&H00301A1A,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,"
        "40,40,30,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    if title and found:
        events.append(f"Dialogue: 0,{_time(0)},{_time(found[-1]['end'] + HOLD_SECONDS)},Title,,0,0,0,,{_clean(title)}")
    shown_until = 0.0
    for i, line in enumerate(found):
        following = found[i + 1] if i + 1 < len(found) else None
        start = max(line["start"] - LEAD_SECONDS, shown_until)
        end = line["end"] + HOLD_SECONDS
        if following:
            end = max(line["end"], min(end, following["start"] - LEAD_SECONDS))
        shown_until = end
        karaoke = [f"{{\\k{round((line['start'] - start) * 100)}}}"] if line["start"] > start else []
        for j, (s, e, syllable) in enumerate(line["syllables"]):
            until = line["syllables"][j + 1][0] if j + 1 < len(line["syllables"]) else e
            karaoke.append(f"{{\\kf{max(1, round((until - s) * 100))}}}{_clean(syllable)}")
        events.append(f"Dialogue: 1,{_time(start)},{_time(end)},Line,,0,0,0,,"
                      f"{{\\pos({width // 2},{int(height * 0.42)})}}" + "".join(karaoke))
        if following:
            events.append(f"Dialogue: 1,{_time(start)},{_time(end)},Next,,0,0,0,,"
                          f"{{\\pos({width // 2},{int(height * 0.56)})}}{_clean(text(following))}")
    return "\n".join(head + events) + "\n"


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def video(audio: str, found: list, out: str, title: str = "", ffmpeg: Optional[str] = None,
          background: Optional[str] = None) -> str:
    """
    Lyric-Video als MP4: Hintergrund, Wellenform des Songs unten und der Text als Karaoke. Gibt out zurück.
    background: ein Bild statt der einfarbigen Fläche; mit Bild darf der Text fehlen (Video ohne Karaoke).
    Wirft RuntimeError ohne ffmpeg oder wenn ffmpeg scheitert.
    """
    exe = ffmpeg or find_ffmpeg()
    if not exe:
        raise RuntimeError("Für das Lyric-Video fehlt ffmpeg (winget install Gyan.FFmpeg).")
    if not found and not background:
        raise RuntimeError("Der Song hat keinen Text zum Mitlesen.")
    width, height = VIDEO_SIZE
    folder = os.path.dirname(os.path.abspath(out))
    os.makedirs(folder, exist_ok=True)
    subtitles = os.path.splitext(os.path.basename(out))[0] + ".ass"
    if found:
        with open(os.path.join(folder, subtitles), "w", encoding="utf-8") as f:
            f.write(ass(found, title))
    wave_height = height // 4
    if background:
        source = ["-loop", "1", "-framerate", str(VIDEO_FPS), "-i", os.path.abspath(background)]
        picture = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[bg];"
    else:
        source = ["-f", "lavfi", "-i", f"color=c={BACKGROUND}:s={width}x{height}:r={VIDEO_FPS}"]
        picture = "[0:v]null[bg];"
    # Die Untertitel liegen im selben Ordner wie das Video: so braucht der Filter keinen Pfad mit Laufwerk
    graph = (f"{picture}[1:a]showwaves=s={width}x{wave_height}:mode=cline:rate={VIDEO_FPS}:"
             f"colors={WAVE_COLOR}@0.5[wave];"
             f"[bg][wave]overlay=0:{height - wave_height}:shortest=1{f',ass={subtitles}' if found else ''}[video]")
    command = [exe, "-y", "-hide_banner", "-loglevel", "error", *source, "-i", os.path.abspath(audio),
               "-filter_complex", graph, "-map", "[video]", "-map", "1:a",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-shortest", os.path.abspath(out)]
    log.info("Lyric-Video: %s", out)
    import cancel
    try:
        done = cancel.run(command, cwd=folder, capture_output=True, text=True, errors="replace", timeout=1800,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"ffmpeg konnte das Video nicht bauen: {e}") from e
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg konnte das Video nicht bauen: {(done.stderr or '').strip()[-400:]}")
    return out

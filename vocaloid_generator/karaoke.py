# karaoke.py – Der Liedtext zum Mitlesen: Zeilen mit der Zeit jeder Silbe, für den Player und das Lyric-Video
#
# Die Zeiten kommen aus der Gesangsmelodie, also stimmen sie mit dem fertigen Song überein. Das Lyric-Video baut
# ffmpeg in 1080p: der Farbverlauf des Stils (wie das Titelbild aus youtube.py) oder ein eigenes Bild, die
# Wellenform des Songs und der Text als Karaoke-Untertitel (ASS, libass), gesungen in der Farbe des Stils.
import json
import logging
import os
import shutil
import subprocess
from typing import Optional

from lyrics import OCCURRENCE

log = logging.getLogger(__name__)

FILE = "liedtext.json"
LINE_GAP_BEATS = 1.0      # so lange Pause beginnt eine neue Zeile
MAX_SYLLABLES = 18        # längere Zeilen werden an der größten Pause geteilt
LEAD_SECONDS = 1.0        # so früh erscheint eine Zeile vor ihrer ersten Silbe
HOLD_SECONDS = 0.8        # so lange bleibt sie nach der letzten stehen
SPACE_BONUS = 0.15        # geteilt wird lieber an einem Leerzeichen, wenn es höchstens so viel weiter weg liegt

VIDEO_SIZE = (1920, 1080)
VIDEO_FPS = 30
VIDEO_FONT = "Meiryo"     # unter Windows immer da; fehlt sie, nimmt libass eine Schrift mit Kana
BACKGROUND = "0x1a1030"   # ohne Stil: einfarbig wie bis 1.1
PLAIN = ("#ff4f8b", "#ff4f8b", "#1a1a30")      # (gesungen, Wellenform, Rand) ohne Stil
LIGHT = 0.8               # hellere Farben gehen neben dem weißen, noch nicht gesungenen Text unter


def lines(notes: list, syllables: list, bpm: float, plan=None, line_lengths: Optional[dict] = None,
          line_texts: Optional[dict] = None) -> list:
    """
    Zeilen zum Mitlesen: [{"start", "end", "syllables": [[start, ende, text]]}], Zeiten in Sekunden ab Songanfang.
    notes: die Töne der Gesangsmelodie (pretty_midi.Note), syllables: die Silben dazu in zeitlicher Reihenfolge
    (melody_writer.melody_data). Ein Melisma verlängert die Silbe davor.
    line_lengths {Sektionsart: [Silben pro Zeile]} (aus lyrics.section_lines): die Zeilen wie im Liedtext, auch
    wenn der Text in der Sektion wiederholt wird; "Verse#2" für ein Vorkommen mit eigenem Text („[Verse 2]“). Ohne
    sie beginnt eine neue Zeile nach einer Pause ab einem Schlag. Jede Sektion beginnt mit einer neuen Zeile.
    line_texts {Sektionsart: [(Zeile wie geschrieben, Übersetzung)]} parallel zu line_lengths (1.5.0 V2): jede Zeile
    bekommt dazu "text" (wie geschrieben, mit Kanji), "romaji" und "de" (die Übersetzung, sonst leer).
    """
    spb = 60.0 / bpm
    sections = []
    for note, syllable in zip(sorted(notes, key=lambda n: n.start), syllables):
        if getattr(syllable, "melisma", False) and sections:
            sections[-1][1][-1][1] = note.end
            continue
        sec = plan.section_at(note.start / spb + 1e-6) if plan is not None else None
        key = (sec.index, sec.kind, sec.occurrence) if sec is not None else (0, "", 1)
        if not sections or sections[-1][0] != key:
            sections.append((key, []))
        sections[-1][1].append([note.start, note.end, str(syllable), bool(getattr(syllable, "word_start", False))])
    found = []
    for (_, kind, occurrence), sung in sections:
        name = f"{kind}{OCCURRENCE}{occurrence}"
        own = (line_lengths or {}).get(name) if occurrence > 1 else None
        lengths = [n for n in own or (line_lengths or {}).get(kind, []) if n > 0]
        texts = ((line_texts or {}).get(name) if own else None) or (line_texts or {}).get(kind) or []
        if lengths:
            for k, line in enumerate(_by_lengths(sung, lengths)):
                written = texts[k % len(texts)] if texts and len(texts) == len(lengths) else None
                found += _split(line, written)
        else:
            for line in _by_pauses(sung, LINE_GAP_BEATS * spb):
                found += _split(line)
    out = []
    for line, written in found:
        entry = {"start": round(line[0][0], 3), "end": round(line[-1][1], 3),
                 "syllables": [[round(s[0], 3), round(s[1], 3), s[2]] for s in line]}
        if line_texts is not None:
            entry["romaji"] = romaji(line, written[0] if written else "")
            if written:
                entry["text"], entry["de"] = written
        out.append(entry)
    return out


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


def _split(line: list, written: Optional[tuple] = None) -> list:
    """Zu lange Zeilen an der größten Pause in ihrer Mitte teilen, bei gleicher Pause an einem Wortanfang.
    written (Zeile wie geschrieben, Übersetzung) wird an derselben Stelle geteilt; die Übersetzung bleibt vorn."""
    if len(line) <= MAX_SYLLABLES:
        return [(line, written)]
    quarter = len(line) // 4
    cut = max(range(max(quarter, 1), len(line) - quarter),
              key=lambda i: (round(line[i][0] - line[i - 1][1], 3), line[i][3], -abs(i - len(line) / 2)))
    first = second = None
    if written:
        head, tail = _cut_text(written[0], cut / len(line))
        first, second = (head, written[1]), (tail, "")
    return _split(line[:cut], first) + _split(line[cut:], second)


def _cut_text(text: str, share: float) -> tuple:
    """Die Zeile wie geschrieben an der Wortgrenze, die share ihrer Moren am nächsten liegt."""
    from lyrics import shown_parts
    parts = shown_parts(text)
    total = sum(n for _, n in parts) or 1.0
    before = [sum(n for _, n in parts[:i]) for i in range(len(parts) + 1)]
    inner = [i for i in range(1, len(parts)) if parts[i][1] > 0 or parts[i][0].isspace()]
    if not inner:
        return text, ""
    # an einem Leerzeichen trennen, wenn es nicht viel weiter weg liegt
    at = min(inner, key=lambda i: abs(before[i] / total - share)
             - (SPACE_BONUS if parts[i][0].isspace() or parts[i - 1][0].isspace() else 0.0))
    head = "".join(p for p, _ in parts[:at]).strip()
    tail = "".join(p for p, _ in parts[at:]).strip()
    return (head, tail) if head and tail else (text, "")


# Romaji der gesungenen Silben (V2); jaconv kennt einige Lautverbindungen nicht
_DIGRAPHS = {"てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du", "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe",
             "ふぉ": "fo", "うぃ": "wi", "うぇ": "we", "うぉ": "wo", "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve",
             "ゔぉ": "vo", "しぇ": "she", "じぇ": "je", "ちぇ": "che", "てゅ": "tyu", "でゅ": "dyu"}


def romaji(line: list, written: str = "") -> str:
    """Die gesungenen Silben einer Zeile in lateinischen Buchstaben, Wörter getrennt: „ame no machi o kimi o“.
    Gesungen heißt wie gesprochen: das Partikel は steht als wa, を als o. Die Wörter kommen aus der Zeile wie
    geschrieben (written, auch die Partikel einzeln), sonst aus den Wortanfängen der Silben."""
    words = _words_of(line, written) if written else []
    if not words:
        for item in line:
            if not words or (len(item) > 3 and item[3]):
                words.append("")
            words[-1] += item[2]
    return " ".join(w for w in (_kana_romaji(w) for w in words) if w)


def _words_of(line: list, written: str) -> list:
    """Die gesungenen Silben nach den Wörtern der geschriebenen Zeile gruppiert (lyrics.shown_parts); passen die
    Moren nicht genau, verteilt sie der Anteil jedes Worts."""
    from lyrics import shown_parts
    parts = [n for _, n in shown_parts(written) if n > 0]
    total = sum(parts)
    if not parts or not total:
        return []
    out, done, taken = [], 0.0, 0
    for n in parts:
        done += n
        until = len(line) if done >= total else round(done / total * len(line))
        if until > taken:
            out.append("".join(item[2] for item in line[taken:until]))
            taken = until
    return out


def _kana_romaji(kana: str) -> str:
    try:
        import jaconv
    except ImportError:                     # gehört zur App; ohne bleibt die Zeile, wie sie gesungen wird
        return kana
    text = jaconv.kata2hira(kana).replace("を", "お")     # gesungen wie o
    for digraph, latin in _DIGRAPHS.items():
        text = text.replace(digraph, latin)
    text = jaconv.kana2alphabet(text)
    out = ""
    for c in text:
        if c == "-":                        # ー: der Vokal davor klingt weiter
            vowel = next((v for v in reversed(out) if v in "aiueo"), "")
            out += vowel
        else:
            out += c
    return out


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


def colors(style: str = "") -> tuple:
    """(gesungen, Wellenform, Rand) als #rrggbb in den Farben des Stils (youtube.PALETTES); ohne Stil wie bis 1.1.
    Gesungen wird in der Akzentfarbe, außer sie ist zu hell neben Weiß, dann in der oberen oder unteren Farbe."""
    if not style:
        return PLAIN
    from youtube import DEFAULT_PALETTE, PALETTES, _rgb
    top, bottom, accent = PALETTES.get(style, DEFAULT_PALETTE)
    sung = next((c for c in (accent, top, bottom) if _lightness(_rgb(c)) < LIGHT), bottom)
    edge = "#" + "".join(f"{int(v * 0.35):02x}" for v in _rgb(bottom))
    return sung, accent, edge


def _lightness(rgb: tuple) -> float:
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def _ass_color(color: str, alpha: str = "00") -> str:
    """#rrggbb → &HAABBGGRR."""
    color = color.lstrip("#")
    return f"&H{alpha}{color[4:6]}{color[2:4]}{color[0:2]}".upper()


def ass(found: list, title: str = "", size: tuple = VIDEO_SIZE, style: str = "") -> str:
    """
    Untertitel im ASS-Format: die laufende Zeile groß in der Mitte, Silbe für Silbe eingefärbt (\\kf), die nächste
    kleiner darunter, oben links der Titel. style: gesungen wird in seiner Farbe (colors), ohne Stil pink.
    """
    width, height = size
    big, small = height // 12, height // 22
    sung, _, edge = (_ass_color(c) for c in colors(style))
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        # Farben als &HAABBGGRR: gesungen in der Farbe des Stils, noch nicht gesungen weiß
        f"Style: Line,{VIDEO_FONT},{big},{sung},&H00FFFFFF,{edge},&H80000000,1,0,0,0,100,100,0,0,1,3,1,5,"
        "40,40,0,1",
        f"Style: Next,{VIDEO_FONT},{small},&H60FFFFFF,&H60FFFFFF,{edge},&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,"
        "40,40,0,1",
        f"Style: Title,{VIDEO_FONT},{small},&H90FFFFFF,&H90FFFFFF,{edge},&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,"
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
          background: Optional[str] = None, style: str = "") -> str:
    """
    Lyric-Video als MP4 (1080p): Hintergrund, Wellenform des Songs unten und der Text als Karaoke. Gibt out zurück.
    background: ein eigenes Bild; mit Bild darf der Text fehlen (Video ohne Karaoke). style: Farbverlauf, Wellenform
    und gesungener Text in den Farben des Stils; ohne Stil und Bild einfarbig dunkel wie bis 1.1.
    Wirft RuntimeError ohne ffmpeg oder wenn ffmpeg scheitert.
    """
    exe = ffmpeg or find_ffmpeg()
    if not exe:
        raise RuntimeError("Für das Lyric-Video fehlt ffmpeg (winget install Gyan.FFmpeg).")
    if not found and not background:
        raise RuntimeError("Der Song hat keinen Text zum Mitlesen.")
    if background and not os.path.exists(background):
        raise RuntimeError(f"Das Hintergrundbild fehlt: {background}")
    folder = os.path.dirname(os.path.abspath(out))
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(out))[0]
    subtitles = stem + ".ass"
    if found:
        with open(os.path.join(folder, subtitles), "w", encoding="utf-8") as f:
            f.write(ass(found, title, style=style))
    gradient = None
    if not background and style:
        import youtube
        try:
            gradient = background = youtube.title_image(os.path.join(folder, stem + ".hintergrund.png"), "", "",
                                                        style, bars=False, size=VIDEO_SIZE)
        except (ImportError, OSError, ValueError) as e:
            log.warning("Kein Farbverlauf für das Video, es bleibt einfarbig: %s", e)
    try:
        return _render(exe, audio, out, folder, subtitles if found else "", background, colors(style)[1])
    finally:
        if gradient and os.path.exists(gradient):
            os.remove(gradient)


def _render(exe: str, audio: str, out: str, folder: str, subtitles: str, background: Optional[str],
            wave: str) -> str:
    width, height = VIDEO_SIZE
    wave_height = height // 4
    if background:
        source = ["-loop", "1", "-framerate", str(VIDEO_FPS), "-i", os.path.abspath(background)]
        picture = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[bg];"
    else:
        source = ["-f", "lavfi", "-i", f"color=c={BACKGROUND}:s={width}x{height}:r={VIDEO_FPS}"]
        picture = "[0:v]null[bg];"
    # Die Untertitel liegen im selben Ordner wie das Video: so braucht der Filter keinen Pfad mit Laufwerk
    # draw=full: mit dem Standard (scale) liefen die Farben über, die Wellenform wurde türkis statt in der Stilfarbe
    graph = (f"{picture}[1:a]showwaves=s={width}x{wave_height}:mode=cline:rate={VIDEO_FPS}:draw=full:"
             f"colors=0x{wave.lstrip('#')}@0.5[wave];"
             f"[bg][wave]overlay=0:{height - wave_height}:shortest=1{f',ass={subtitles}' if subtitles else ''}[video]")
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

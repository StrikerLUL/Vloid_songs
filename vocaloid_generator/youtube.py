# youtube.py – „Fertig für YouTube“: MP3, Video, Titelbild und Beschreibung eines Songs in einem eigenen Ordner
#
# Das Titelbild malt Pillow, ohne KI: ein Farbverlauf in den Farben des Stils, die echte Wellenform des Songs als
# Balken und der Titel. Das Video ist das Lyric-Video vor diesem Bild (ohne Text nur Bild und Wellenform), die
# Beschreibung nennt Stil, Tempo, Tonart und was eine Veröffentlichung nennen muss (Stimme und NEUTRINO). Alles liegt
# unter <Ausgabe>/YouTube/<Datum> <Titel>. Fehlt ffmpeg, gibt es Bild und Beschreibung trotzdem, mit Hinweis.
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import numpy as np

from album import free_folder, safe_name

log = logging.getLogger(__name__)

FOLDER = "YouTube"
IMAGE_SIZE = (1280, 720)            # Größe eines YouTube-Vorschaubilds
BARS = 96                           # Balken der Wellenform im Titelbild
# Stil → (oben, unten, Akzent) für Farbverlauf und Wellenform
PALETTES = {
    "J-Pop Energy": ("#ff5f9e", "#3a1c71", "#ffe66d"),
    "Dark Vocaloid": ("#2b2d42", "#0b0c10", "#c3073f"),
    "Kawaii Chiptune": ("#ffb6e1", "#7f7fd5", "#fffb96"),
    "Rock": ("#3d0000", "#0d0d0d", "#ff6b35"),
    "Ballade": ("#355c7d", "#1b2735", "#f8b195"),
    "City Pop": ("#ff9a8b", "#5f2c82", "#49c6e5"),
    "Future Bass": ("#43cea2", "#185a9d", "#ffffff"),
    "Drum and Bass": ("#141e30", "#000000", "#00f5d4"),
    "Lo-Fi": ("#c9a27e", "#3e3a4f", "#f2e8cf"),
    "Idol-Pop": ("#fbc2eb", "#a18cd1", "#ffffff"),
    "Wafuu-Rock": ("#7a1022", "#140a1e", "#ffb000"),
    "Electro-Swing": ("#3a2f1c", "#0b0a12", "#d4af37"),
    "Hyperpop": ("#ff3cac", "#2b86c5", "#f6ff00"),
}
DEFAULT_PALETTE = ("#6a3093", "#1a1030", "#ff4f8b")
# Schriften mit japanischen Zeichen zuerst (Windows, dann Linux), sonst die eingebaute von Pillow
FONTS = ("YuGothB.ttc", "meiryob.ttc", "meiryo.ttc", "msgothic.ttc", "NotoSansCJK-Bold.ttc", "NotoSansJP-Bold.otf",
         "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
FONT_FOLDERS = (os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"), "/usr/share/fonts/opentype/noto",
                "/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts")

ProgressFn = Callable[[float, str], None]


@dataclass
class Package:
    folder: str
    title: str
    audio: Optional[str] = None
    video: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    problems: list = field(default_factory=list)

    def describe(self) -> str:
        made = [name for name, path in (("MP3", self.audio), ("Video", self.video), ("Titelbild", self.image),
                                        ("Beschreibung", self.description)) if path]
        text = f"{', '.join(made)} in {self.folder}"
        return text + ("; " + "; ".join(self.problems) if self.problems else "")


def title_for(result, label: str = "") -> str:
    s = result.settings
    return label.strip() or (f"{s.style} (Seed {result.seed})" if s else f"Song {result.seed}")


def make(result, label: str = "", progress: Optional[ProgressFn] = None) -> Package:
    """Legt den Ordner an. Wirft RuntimeError, wenn der Song fehlt; alles andere landet in Package.problems."""
    report = progress or (lambda fraction, message: None)
    source = result.mp3 or result.mix_wav
    if not source or not os.path.exists(source):
        raise RuntimeError("Der Song fehlt, erst einen Song erzeugen.")
    s = result.settings
    title = title_for(result, label)
    home = getattr(result, "share_dir", None) or result.output_dir      # 1.7.1: ein Song aus dem Verlauf
    base = os.path.join(home, os.pardir) if s and s.draft else home
    name = safe_name(title, "Song")
    folder = free_folder(os.path.join(os.path.abspath(base), FOLDER), f"{datetime.now():%Y-%m-%d} {name}")
    os.makedirs(folder)
    package = Package(folder, title)

    report(0.05, "YouTube: MP3...")
    package.audio = _mp3(source, os.path.join(folder, name + ".mp3"))
    if package.audio is None:
        package.audio = os.path.join(folder, name + os.path.splitext(source)[1])
        shutil.copyfile(source, package.audio)
        package.problems.append("ohne ffmpeg nur als WAV")

    report(0.15, "YouTube: Titelbild...")
    subtitle = " · ".join(details(result))
    package.image = title_image(os.path.join(folder, "Titelbild.png"), title, subtitle,
                                s.style if s else "", result.mix_wav)

    report(0.25, "YouTube: Video...")
    if s is not None and s.music_video:
        import musikvideo
        try:
            # 1.7.0: die Titelkarte nur mit echtem Namen, nicht mit „Ballade (Seed …)“
            package.video = musikvideo.for_song(result, os.path.join(folder, name + ".mp4"), label,
                                                audio=package.audio,
                                                progress=lambda f, m: report(0.25 + 0.7 * f, m))
        except RuntimeError as e:
            package.problems.append(f"kein Video: {e}")
        except Exception as e:  # noqa: BLE001 – 1.7.1: MP3, Titelbild und Beschreibung entstehen trotzdem
            import cancel
            if isinstance(e, cancel.Cancelled):
                raise
            log.exception("YouTube: Video fehlgeschlagen: %s", e)
            package.problems.append(f"kein Video: {type(e).__name__}: {e} (Einzelheiten im Protokoll)")
    else:
        _lyric_video(result, package, folder, name, title, subtitle)

    report(0.95, "YouTube: Beschreibung...")
    package.description = os.path.join(folder, "Beschreibung.txt")
    with open(package.description, "w", encoding="utf-8") as f:
        f.write(description(result, title))
    report(1.0, "YouTube-Ordner fertig")
    log.info("YouTube: %s", package.describe())
    return package


def _lyric_video(result, package: Package, folder: str, name: str, title: str, subtitle: str) -> None:
    """Das Lyric-Video wie bis 1.4: Text vor dem Titelbild mit der Wellenform."""
    import karaoke
    s = result.settings
    found = karaoke.load(os.path.join(result.output_dir, karaoke.FILE))
    own = s.video_background if s and s.video_background and os.path.exists(s.video_background) else ""
    with tempfile.TemporaryDirectory() as temp:
        # im Video läuft die echte Wellenform; mit Text steht in der Mitte die Karaoke-Zeile statt des Titels
        background = own or title_image(os.path.join(temp, "hintergrund.png"), "" if found else title,
                                        "" if found else subtitle, s.style if s else "", bars=False,
                                        size=karaoke.VIDEO_SIZE)
        try:
            package.video = karaoke.video(package.audio, found, os.path.join(folder, name + ".mp4"), title,
                                          background=background, style=s.style if s and s.video_colors else "")
        except RuntimeError as e:
            package.problems.append(f"kein Video: {e}")
    subtitles = os.path.join(folder, name + ".ass")       # die Untertitel stecken im Video
    if os.path.exists(subtitles):
        os.remove(subtitles)


def _mp3(source: str, target: str) -> Optional[str]:
    if source.lower().endswith(".mp3"):
        shutil.copyfile(source, target)
        return target
    from exporter import exportiere_song
    return exportiere_song(wav_pfad=source, mp3_pfad=target)


def details(result) -> list:
    """Stil, Tempo und Tonart. 1.7.0: aus der Songkarte neben dem Song, die mit ihm entsteht (die Einstellungen
    gehören zum gewählten Song, im Ordner kann inzwischen ein anderer liegen), die Tonart so, wie die Akkorde klingen
    (songkarte.sounding_key), mit ♭ in B-Tonarten."""
    s = result.settings
    if s is None:
        return []
    import gui.labels as labels
    import songkarte
    import theory
    found = songkarte.load(os.path.join(result.output_dir, songkarte.FILE)) if result.output_dir else None
    if found is None:
        return [s.style, f"{s.bpm} BPM", f"{s.key} {labels.SCALES.get(s.scale, s.scale)}"]
    tonic, scale = songkarte.sounding_key(found)
    same = found.seed == result.seed and found.style in ("", s.style)
    bpm = s.bpm if same else int(round(found.bpm))
    return [found.style or s.style, f"{bpm} BPM",
            f"{theory.key_name(tonic, theory.is_minor(scale))} {labels.SCALES.get(scale, scale)}"]


def singers(result) -> list:
    """Wer singt, wie es eine Veröffentlichung nennen muss (Beschreibung und Abspann im Video)."""
    s = result.settings
    if not s or not s.channels["vocals"].enabled or s.draft:
        return []
    if s.vocal_engine == "VOICEVOX":
        return ["Gesang: VOICEVOX:<Name der Figur> (bitte eintragen, VOICEVOX verlangt diesen Hinweis)"]
    if s.vocal_engine == "NEUTRINO":
        names = " und ".join(x for x in (s.singer, s.duet_singer) if x)
        return [f"Gesang: NEUTRINO, Stimme {names}",
                "(Die Nutzungsbedingungen der Stimme stehen in ihrer Readme im NEUTRINO-Ordner model.)"]
    return []


def producer(result) -> list:
    """1.5.0: „Produziert von …“ aus dem Produzenten-Profil; leer ohne Namen."""
    import produzent
    found = produzent.name(result.settings)
    return [f"Produziert von {found}"] if found else []


def credits(result) -> list:
    """Abspann des Musikvideos: Stimme, wer produziert und wer komponiert hat."""
    sung = [line for line in singers(result) if not line.startswith("(")]
    sung = [line.split(" (bitte")[0] for line in sung]
    return sung + producer(result) + ["Musik, Melodie und Arrangement: Vloid Songs"]


def chapters(result) -> list:
    """YouTube-Kapitel („0:00 Intro“) aus der Songkarte (1.5.0); leer bei älteren Songs oder ausgeschaltet."""
    s = result.settings
    if s is None or not s.youtube_chapters:
        return []
    import songkarte
    found = songkarte.load(os.path.join(result.output_dir, songkarte.FILE))
    return [f"{songkarte.timestamp(at)} {name}" for at, name in songkarte.chapters(found)] if found else []


def description(result, title: str) -> str:
    """Text für das Beschreibungsfeld: worum es geht und was genannt werden muss."""
    lines = [title, "", " · ".join(details(result)), ""]
    marks = chapters(result)
    if marks:
        lines += marks + [""]
    lines += singers(result)
    lines += producer(result)
    lines += ["Musik, Melodie und Arrangement: komponiert mit Vloid Songs", ""]
    lines.append(f"Seed {result.seed}")
    return "\n".join(lines) + "\n"


def title_image(path: str, title: str, subtitle: str = "", style: str = "", audio: Optional[str] = None,
                bars: bool = True, size: tuple = IMAGE_SIZE) -> str:
    """Ein schlichtes Titelbild (PNG, sonst 1280×720): Farbverlauf des Stils, Wellenform des Songs, Titel und
    Details. size (Breite, Höhe): quadratisch für das Cover in der MP3 (tags.py), 1920×1080 fürs Video."""
    from PIL import Image, ImageDraw, ImageFilter
    width, height = size
    scale = max(1.0, width / IMAGE_SIZE[0])            # größere Bilder: Schrift wächst mit
    top, bottom, accent = (_rgb(c) for c in PALETTES.get(style, DEFAULT_PALETTE))
    mix = np.linspace(0.0, 1.0, height)[:, None, None]
    gradient = (np.array(top)[None, None] * (1 - mix) + np.array(bottom)[None, None] * mix)
    image = Image.fromarray(np.repeat(gradient, width, axis=1).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    levels = _envelope(audio, BARS) if bars else None
    if levels is not None:
        bar, base = width / BARS, height * 0.86
        for i, level in enumerate(levels):
            h = max(4.0, level * height * 0.32)
            draw.rounded_rectangle([i * bar + bar * 0.2, base - h, (i + 1) * bar - bar * 0.2, base],
                                   radius=bar * 0.3, fill=(*accent, 150))

    if not title:
        image.save(path)
        return path
    title_font = _fit(draw, title, width * 0.86, int(104 * scale))
    box = draw.textbbox((0, 0), title, font=title_font)
    x, y = (width - (box[2] - box[0])) / 2 - box[0], height * 0.30 - (box[3] - box[1]) / 2 - box[1]
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x + 4 * scale, y + 6 * scale), title, font=title_font,
                                fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    image.paste(shadow, (0, 0), shadow)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.text((x, y), title, font=title_font, fill=(255, 255, 255, 255))
    if subtitle:
        small = _font(int(40 * scale))
        box = draw.textbbox((0, 0), subtitle, font=small)
        draw.text(((width - (box[2] - box[0])) / 2 - box[0], height * 0.30 + 90 * scale), subtitle, font=small,
                  fill=(*accent, 255))
    image.save(path)
    return path


def _envelope(audio: Optional[str], bars: int) -> Optional[np.ndarray]:
    """Lautstärke des Songs in bars Abschnitten (0 bis 1); None, wenn die Datei fehlt oder unlesbar ist."""
    if not audio or not os.path.exists(audio):
        return None
    try:
        import soundfile as sf
        data, _ = sf.read(audio, dtype="float32", always_2d=True)
    except (RuntimeError, OSError):
        return None
    mono = np.abs(data.mean(axis=1))
    if len(mono) < bars:
        return None
    rms = np.array([np.sqrt(np.mean(np.square(part))) for part in np.array_split(mono, bars)])
    return rms / rms.max() if rms.max() > 0 else rms


def _font(size: int):
    from PIL import ImageFont
    for name in FONTS:
        for folder in FONT_FOLDERS:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
    return ImageFont.load_default(size)


def _fit(draw, text: str, width: float, size: int):
    """Die größte Schrift bis size, in der text in width passt."""
    while size > 28:
        font = _font(size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= width:
            return font
        size -= 6
    return _font(size)


def _rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

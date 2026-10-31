# video_szenen.py – Eine Szene pro Stil für das Musikvideo (1.5.0 V6, V7, V8, V9)
#
# Jeder Stil hat ein eigenes Bild, eigene Teilchen, ein eigenes Spektrum und eine eigene Bewegung: Rock eine Bühne mit
# Scheinwerfern, die Ballade ein Fenster bei Nacht, City Pop ein Neonraster, Kawaii Textkunst aus Zeichen. Alles, was
# sich bewegt, hängt am Song (musikvideo.Frame: Schlag, Kick, Snare, Sektion, Energie, Spektrum, Akkord, Melodie),
# nichts ist Zufall von außen. Gezeichnet wird mit Pillow und numpy in halber Auflösung (960×540); ffmpeg vergrößert
# und legt den Text (libass) gestochen scharf darüber.
#
# Jede Position eines Teilchens ist eine Formel der Zeit, nicht ein Zustand: so sieht ein Bild bei 1:23 immer gleich
# aus, egal ob das Video vorn anfängt oder nur die Vorschau ab dem Refrain läuft.
import colorsys
import math
import os
import random
from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 960, 540                    # gezeichnet wird in halber 1080p-Auflösung
TEXT_BAND = (0.47, 0.83)           # dort steht der Text: dahinter wird es ruhiger und dunkler (V12)
ROLL_BAND = (0.27, 0.43)           # dort läuft die Notenlinie der Melodie (V5)
SPECTRUM_BAND = (0.85, 0.975)
CALM_DARKEN = 0.55                 # so dunkel wird es höchstens hinter dem Text
MAX_FLASH = 0.35                   # ein Blitz hellt das ganze Bild höchstens so weit auf (V12)
FLASHES_PER_SECOND = 3.0           # höchstens so viele Blitze pro Sekunde (Schutz bei Lichtempfindlichkeit)
CALM, LIVELY = 0.35, 1.0           # Stärke der Bewegung: ruhig und lebhaft
MOTIONS = ("Stil", "ruhig", "lebhaft")
# Schriften mit Kana und gleich breiten Zeichen für Textkunst und flackernde Zeichen (Windows, dann Linux)
MONO_FONTS = ("msgothic.ttc", "YuGothM.ttc", "ipag.ttf", "NotoSansMonoCJKjp-Regular.otf", "NotoSansCJK-Regular.ttc",
              "DejaVuSansMono.ttf")
MONO_FOLDERS = (os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"), "/usr/share/fonts/opentype/ipafont-gothic",
                "/usr/share/fonts/truetype/fonts-japanese-gothic", "/usr/share/fonts/opentype/noto",
                "/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/dejavu")
KANA_FREE = ("DejaVuSansMono.ttf",)


@dataclass(frozen=True)
class Look:
    """Wie der Text (libass) in dieser Szene aussieht."""
    font: str = "Meiryo"
    latin: str = "Segoe UI"
    y: float = 0.565               # Mitte der laufenden Zeile, Anteil der Bildhöhe
    size: float = 1.0
    bold: bool = True
    outline: float = 3.0
    sung: str = ""                 # Farbe des Gesungenen; leer = karaoke.colors des Stils
    box: bool = False              # Textkunst: Text in einem Rahmen


@dataclass(frozen=True)
class Scene:
    name: str
    palette: tuple                 # (oben, unten, Akzent, hell)
    background: str
    particles: str = ""
    spectrum: str = "bars"
    lively: bool = True            # Bewegung, wenn sie „wie der Stil“ steht
    beat: str = "pulse"            # pulse, zoom, shake, sway, glitch
    chorus: str = "bright"         # was im Refrain dazukommt
    look: Look = field(default_factory=Look)
    pixel: bool = False            # beim Vergrößern Pixel behalten (Textkunst)


SCENES = {
    "J-Pop Energy": Scene("Anime-Opening", ("#ff5f9e", "#3a1c71", "#ffe66d", "#ffffff"), "speedlines", "sparks",
                          "bars", True, "zoom", "burst"),
    "Dark Vocaloid": Scene("Glitch", ("#2b2d42", "#0b0c10", "#c3073f", "#ff4d6d"), "glitch", "", "scope", True,
                           "glitch", "glitch", Look(sung="#ff2e63")),
    "Kawaii Chiptune": Scene("Textkunst", ("#2a1b4a", "#140c26", "#fffb96", "#ffb6e1"), "ascii", "", "blocks", True,
                             "pulse", "confetti", Look(font="MS Gothic", latin="MS Gothic", y=0.55, box=True), True),
    "Rock": Scene("Bühne", ("#3d0000", "#0d0d0d", "#ff6b35", "#ffd166"), "stage", "sparks", "meters", True, "shake",
                  "lights"),
    "Ballade": Scene("Fenster bei Nacht", ("#2b4a66", "#141d29", "#f8b195", "#fde2d4"), "window", "", "soft", False,
                     "sway", "warm", Look(font="Yu Mincho", latin="Georgia", bold=False, outline=2.0)),
    "City Pop": Scene("80er", ("#ff9a8b", "#2a1650", "#49c6e5", "#ffe3f1"), "neon_grid", "", "bars", False, "pulse",
                      "neon"),
    "Future Bass": Scene("Kreis", ("#43cea2", "#185a9d", "#ffffff", "#c9fff1"), "radial", "", "radial", True, "zoom",
                         "flash"),
    "Drum and Bass": Scene("Tunnel", ("#141e30", "#000000", "#00f5d4", "#7bffb5"), "tunnel", "", "scope", True,
                           "pulse", "speed"),
    "Lo-Fi": Scene("Zimmer", ("#5a4a5f", "#241f2e", "#f2e8cf", "#ffcf8f"), "room", "", "soft", False, "sway", "lamp",
                   Look(font="Yu Gothic", bold=False, outline=2.0)),
    "Idol-Pop": Scene("Bühne mit Leuchtstäben", ("#fbc2eb", "#3b2a6b", "#ffffff", "#ffe3fa"), "audience", "hearts",
                      "bars", True, "pulse", "lights"),
    "Wafuu-Rock": Scene("Wafuu", ("#3b0d1a", "#0f0a1e", "#ffb000", "#ffd9e1"), "washi", "petals", "none", True,
                        "shake", "burst", Look(font="Yu Mincho", latin="Georgia")),
    "Electro-Swing": Scene("Art déco", ("#1d1a2f", "#0b0a12", "#d4af37", "#fff3c4"), "deco", "", "bars", True,
                           "sway", "lights", Look(font="Yu Mincho", latin="Georgia")),
    "Hyperpop": Scene("Hyperpop", ("#ff3cac", "#2b86c5", "#ffffff", "#f6ff00"), "chrome", "stars", "mirror", True,
                      "zoom", "glitch"),
}
TEXTKUNST = SCENES["Kawaii Chiptune"]
DEFAULT = Scene("Farbverlauf", ("#6a3093", "#1a1030", "#ff4f8b", "#ffd1e3"), "gradient", "", "bars", True)
CHOICES = {"": "wie der Stil", **{style: f"{scene.name} ({style})" for style, scene in SCENES.items()
                                  if scene is not TEXTKUNST}, "Textkunst": "Textkunst (ASCII)"}


def for_style(style: str, choice: str = "") -> Scene:
    """Die Szene: die gewählte (ein Stilname oder „Textkunst“), sonst die des Stils."""
    if choice == "Textkunst":
        return replace(TEXTKUNST, palette=SCENES.get(style, TEXTKUNST).palette) if style != "Kawaii Chiptune" \
            else TEXTKUNST
    if choice in SCENES:
        return SCENES[choice]
    return SCENES.get(style, DEFAULT)


def motion(scene: Scene, setting: str) -> float:
    if setting == "ruhig":
        return CALM
    if setting == "lebhaft":
        return LIVELY
    return LIVELY if scene.lively else CALM


def rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a: tuple, b: tuple, share: float) -> tuple:
    return tuple(int(x + (y - x) * share) for x, y in zip(a, b))


def _hue(color: tuple, turn: float) -> tuple:
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in color))
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb((h + turn) % 1.0, s, v))


def _gradient(top: tuple, bottom: tuple, size=(W, H)) -> Image.Image:
    w, h = size
    mix = np.linspace(0.0, 1.0, h)[:, None, None]
    g = np.array(top)[None, None] * (1 - mix) + np.array(bottom)[None, None] * mix
    return Image.fromarray(np.repeat(g, w, axis=1).astype(np.uint8), "RGB")


def mono_font(size: int):
    """(Schrift, kann Kana): eine gleich breite Schrift, möglichst mit Kana."""
    from PIL import ImageFont
    for name in MONO_FONTS:
        for folder in MONO_FOLDERS:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size), name not in KANA_FREE
                except OSError:
                    continue
    return ImageFont.load_default(size), False


@dataclass
class Frame:
    """Was der Song in diesem Bild gerade macht; baut musikvideo.Timeline."""
    t: float
    index: int = 0
    kind: str = ""                 # Sektionsart
    progress: float = 0.0          # 0..1 durch die Sektion
    energy: float = 0.5
    vocals: bool = False
    chorus: bool = False
    last_chorus: bool = False      # mit Rückung oder der letzte Refrain
    beat: int = -1
    phase: float = 0.0             # 0..1 bis zum nächsten Schlag
    downbeat: bool = False
    beat_pulse: float = 0.0        # 1 auf dem Schlag, fällt bis zum nächsten
    kick: float = 0.0              # 1 auf der Kick, fällt in etwa 0,2 s
    snare: float = 0.0
    crash: float = 0.0
    change: float = 0.0            # 1 beim Sektionswechsel, fällt in etwa 0,6 s
    level: float = 0.0             # Lautstärke 0..1
    bands: Optional[np.ndarray] = None    # Spektrum 0..1
    wave: Optional[np.ndarray] = None     # Wellenform um t (-1..1)
    chord_minor: bool = False
    notes: list = field(default_factory=list)   # [(Anfang, Ende, Tonhöhe)] um t, für die Notenlinie
    pitch_range: tuple = (60, 72)
    singing: bool = False          # gerade klingt ein Ton der Melodie (Mund der Figur)
    motifs: set = field(default_factory=set)    # Motive der Zeile, die gerade läuft (V8)
    song_progress: float = 0.0
    sections: list = field(default_factory=list)  # [(Anteil Anfang, Anteil Ende, Art)] für die Ablaufleiste
    fade: float = 1.0              # 0 = schwarz (Anfang und Ende)
    flash: float = 0.0             # gewünschter Blitz 0..1 (wird in Painter begrenzt)
    prev_kind: str = ""            # 1.7.0: Art der Sektion davor, zum Überblenden der Bilder
    words: tuple = ()              # 1.7.0: Wörter der laufenden Zeile (Chat-Blasen)


class Painter:
    """Malt die Bilder einer Szene. Einmal anlegen, dann frame() für jedes Bild."""

    def __init__(self, scene: Scene, strength: float, seed: int = 0, lyric_chars: str = "",
                 weather: Optional[str] = None, chat: bool = False, background: Optional[str] = None,
                 pictures: Optional[dict] = None, figure: Optional[tuple] = None, roll: bool = True,
                 spectrum: bool = True, hud: bool = True, tidy: bool = False, sharp: bool = False):
        self.scene = scene
        self.strength = strength
        self.rng = random.Random(seed)
        self.top, self.bottom, self.accent, self.light = (rgb(c) for c in scene.palette)
        self.chars = "".join(dict.fromkeys(c for c in lyric_chars if not c.isspace())) or "ボカロウタ"
        self.weather = weather
        self.chat = chat
        # 1.7.0 video_tidy: in ruhigen Szenen (Ballade, Lo-Fi, City Pop) keine Notenlinie und Ablaufleiste, ein
        # kleineres, blasseres Spektrum (B7); Teilchen lassen das Textband frei (B5); Bilder blenden über (B6)
        self.tidy = tidy
        self.calm = tidy and strength <= CALM
        self.roll = roll and not self.calm
        self.show_spectrum = spectrum
        self.hud = hud and not self.calm
        self.font, self.kana = mono_font(16)
        self.small_font, _ = mono_font(12)
        self._last_flash = -10.0
        self._flash_times: list = []
        self._tones = self._section_tones()
        self._own = self._load(background, sharp) if background else None
        self._pictures = {kind: self._load(path, sharp) for kind, path in (pictures or {}).items() if path}
        self._free = self._free_mask() if tidy else None
        self._figure = self._figure_images(figure) if figure else None
        self._calm = self._calm_mask()
        self._static = {}
        self._particles = self._seed_particles(160)

    # ── Vorbereitung ────────────────────────────────────────────────────────────
    def _section_tones(self) -> dict:
        """Grundbild je Stimmung: ruhig (Strophe), voll (Refrain), anders (Bridge)."""
        dark = _gradient(_mix(self.top, (0, 0, 0), 0.35), _mix(self.bottom, (0, 0, 0), 0.25))
        full = _gradient(self.top, self.bottom)
        other = _gradient(_hue(self.bottom, 0.08), _hue(_mix(self.top, (0, 0, 0), 0.3), 0.12))
        return {"dark": dark, "full": full, "other": other}

    @staticmethod
    def _load(path: str, sharp: bool = False) -> Optional[Image.Image]:
        try:
            with Image.open(path) as image:
                picture = image.convert("RGB")
        except OSError:
            return None
        scale = max(W / picture.width, H / picture.height)
        picture = picture.resize((max(W, int(picture.width * scale + 0.5)), max(H, int(picture.height * scale + 0.5))),
                                 Image.LANCZOS if sharp else Image.BICUBIC)
        left, top = (picture.width - W) // 2, (picture.height - H) // 2
        return picture.crop((left, top, left + W, top + H))

    @staticmethod
    def _figure_images(paths: tuple) -> Optional[tuple]:
        """(Mund zu, Mund auf) als RGBA, höchstens 45 % der Bildhöhe; ohne zweites Bild zweimal dasselbe."""
        found = []
        for path in paths:
            if not path:
                continue
            try:
                with Image.open(path) as image:
                    picture = image.convert("RGBA")
            except OSError:
                continue
            scale = min(H * 0.45 / picture.height, W * 0.3 / picture.width)
            found.append(picture.resize((max(1, int(picture.width * scale)), max(1, int(picture.height * scale)))))
        if not found:
            return None
        return found[0], found[1] if len(found) > 1 else found[0]

    @staticmethod
    def _calm_mask() -> Image.Image:
        """Weiche Abdunklung hinter dem Text (V12)."""
        y = np.linspace(0.0, 1.0, H)
        lo, hi = TEXT_BAND
        inside = np.clip(np.minimum((y - lo) / 0.06, (hi - y) / 0.06), 0, 1)
        x = np.linspace(-1, 1, W)
        across = np.clip(1.25 - np.abs(x) ** 3, 0, 1)
        alpha = (inside[:, None] * across[None, :] * 255 * CALM_DARKEN).astype(np.uint8)
        return Image.fromarray(alpha, "L")

    @staticmethod
    def _free_mask() -> Image.Image:
        """1.7.0: wo Teilchen fliegen dürfen: überall außer im Band hinter dem Text (weicher Rand)."""
        y = np.linspace(0.0, 1.0, H)
        lo, hi = TEXT_BAND
        inside = np.clip(np.minimum((y - lo + 0.03) / 0.05, (hi + 0.03 - y) / 0.05), 0, 1)
        alpha = np.repeat(((1.0 - inside) * 255).astype(np.uint8)[:, None], W, axis=1)
        return Image.fromarray(alpha, "L")

    def _seed_particles(self, count: int) -> list:
        rng = random.Random(self.rng.random())
        return [(rng.random(), rng.random(), 0.5 + rng.random(), rng.random(), rng.random()) for _ in range(count)]

    def _cached(self, key: str, make):
        if key not in self._static:
            self._static[key] = make()
        return self._static[key]

    # ── ein Bild ────────────────────────────────────────────────────────────────
    def frame(self, f: Frame) -> Image.Image:
        image = self._base(f)
        draw = ImageDraw.Draw(image, "RGBA")
        if not self._picture_for(f):                    # ein eigenes Bild bleibt frei, nur Teilchen und Linien darauf
            getattr(self, "_bg_" + self.scene.background, self._bg_gradient)(image, draw, f)
        draw = ImageDraw.Draw(image, "RGBA")
        if self._free is not None:                      # Teilchen auf eine eigene Ebene, das Textband bleibt frei
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            spots = ImageDraw.Draw(layer)
            self._weather(spots, f)
            if self.scene.particles:
                self._particles_of(self.scene.particles, spots, f, 0.3)
            self._line_motifs(spots, f, chat=False)
            alpha = layer.getchannel("A")
            layer.putalpha(Image.fromarray((np.asarray(alpha, np.uint16) * np.asarray(self._free) // 255)
                                           .astype(np.uint8), "L"))
            image.paste(layer, (0, 0), layer)
            draw = ImageDraw.Draw(image, "RGBA")
            self._line_motifs(draw, f, particles=False)
        else:
            self._weather(draw, f)
            if self.scene.particles:
                self._particles_of(self.scene.particles, draw, f, 0.6)
            self._line_motifs(draw, f)
        if self.show_spectrum:
            self._spectrum(image, draw, f)
        if self.roll and f.notes and self.scene.background != "ascii":
            self._melody_line(draw, f)
        if self.hud and self.scene.background != "ascii":
            self._timeline(draw, f)
        if self._figure:
            self._paste_figure(image, f)
        image.paste((0, 0, 0), (0, 0), self._calm)
        image = self._move(image, f)
        return self._light(image, f)

    def _picture_for(self, f: Frame) -> Optional[Image.Image]:
        picture = self._pictures.get(f.kind)
        return picture if picture is not None else self._own

    @staticmethod
    def _tone_of(kind: str) -> str:
        return "full" if kind in ("Chorus", "Drop", "Solo") else "other" if kind in ("Bridge", "Spoken") else "dark"

    def _base(self, f: Frame) -> Image.Image:
        picture = self._picture_for(f)
        if self.tidy and f.change > 0.02 and f.index > 0 and f.prev_kind:
            # B6: das Bild der Sektion davor blendet in etwa einer Sekunde in das neue über, auch bei KI-Bildern
            now = picture if picture is not None else self._tones[self._tone_of(f.kind)]
            before = self._pictures.get(f.prev_kind, self._own)
            before = before if before is not None else self._tones[self._tone_of(f.prev_kind)]
            return Image.blend(now, before, min(1.0, f.change)) if before is not now else now.copy()
        if picture is not None:
            return picture.copy()
        tone = self._tone_of(f.kind)
        image = self._tones[tone].copy()
        if f.change > 0 and f.index > 0:                 # weich in die neue Stimmung
            previous = self._tones["dark" if tone != "dark" else "full"]
            image = Image.blend(image, previous, min(0.6, f.change * 0.6))
        return image

    # ── Hintergründe der Stile ─────────────────────────────────────────────────
    def _bg_gradient(self, image, draw, f: Frame) -> None:
        glow = 0.15 + 0.35 * f.energy + 0.25 * f.beat_pulse * self.strength
        r = int(H * (0.55 + 0.1 * f.beat_pulse * self.strength))
        draw.ellipse([W / 2 - r, H * 0.45 - r, W / 2 + r, H * 0.45 + r], fill=(*self.accent, int(40 * glow)))

    def _bg_speedlines(self, image, draw, f: Frame) -> None:
        """Anime-Opening: Speedlines vom Zentrum, sie rucken auf der Kick."""
        cx, cy = W / 2, H * 0.48
        rng = random.Random(f.beat if f.beat >= 0 else 0)
        count = int(30 + 50 * f.energy)
        for i in range(count):
            angle = rng.random() * math.tau
            inner = 120 + rng.random() * 120 - 60 * f.kick * self.strength
            length = 300 + rng.random() * 400
            width = 1 + int(rng.random() * 3)
            alpha = int((60 + 120 * f.energy) * (0.5 + 0.5 * rng.random()))
            x0, y0 = cx + math.cos(angle) * inner, cy + math.sin(angle) * inner
            x1, y1 = cx + math.cos(angle) * (inner + length), cy + math.sin(angle) * (inner + length)
            draw.line([x0, y0, x1, y1], fill=(*self.light, alpha), width=width)
        if f.chorus:
            r = 60 + 30 * f.beat_pulse
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*self.accent, int(70 * f.energy)))

    def _bg_glitch(self, image, draw, f: Frame) -> None:
        """Glitch: Scanlines, flackernde Zeichen aus dem Liedtext, Streifen, die auf der Snare verrutschen."""
        lines = self._cached("scan", self._scanlines)
        image.paste((0, 0, 0), (0, 0), lines)
        rng = random.Random(f.beat * 7 + 3)
        for _ in range(int(14 + 30 * f.energy)):
            x, y = rng.random() * W, rng.random() * H
            if TEXT_BAND[0] * H < y < TEXT_BAND[1] * H and W * 0.15 < x < W * 0.85:
                continue
            c = rng.choice(self.chars) if self.kana else rng.choice("#/\\|=+")
            draw.text((x, y), c, font=self.font, fill=(*self.accent, int(40 + 80 * rng.random())))
        if f.snare > 0.6 and self.strength > 0.5:
            for _ in range(4):
                y0 = int(rng.random() * (H - 20))
                strip = image.crop((0, y0, W, y0 + 4 + int(rng.random() * 10)))
                image.paste(strip, (int((rng.random() - 0.5) * 40 * f.snare), y0))

    def _scanlines(self) -> Image.Image:
        mask = np.zeros((H, W), dtype=np.uint8)
        mask[::3, :] = 70
        return Image.fromarray(mask, "L")

    def _bg_stage(self, image, draw, f: Frame) -> None:
        """Bühne: Scheinwerferkegel, die im Takt schwenken; im Refrain gehen alle an."""
        beams = 6 if f.chorus else 3 if f.energy > 0.4 else 2
        colors = [self.accent, self.light, _hue(self.accent, 0.08), (255, 255, 255)]
        for i in range(beams):
            base_x = W * (i + 0.5) / beams
            swing = math.sin(f.t * 0.9 + i * 1.7) * 0.35 + (f.beat_pulse - 0.5) * 0.12 * self.strength
            end_x = base_x + math.sin(swing) * H * 1.1
            spread = 70 + 30 * f.energy
            color = colors[(i + max(f.beat, 0) // 8) % len(colors)]
            alpha = int(22 + 40 * f.energy + 30 * f.kick * self.strength)
            draw.polygon([(base_x - 6, -10), (base_x + 6, -10), (end_x + spread, H), (end_x - spread, H)],
                         fill=(*color, alpha))
        draw.rectangle([0, H * 0.93, W, H], fill=(0, 0, 0, 160))

    def _bg_window(self, image, draw, f: Frame) -> None:
        """Fenster bei Nacht: Lichter der Stadt unscharf dahinter, Fensterkreuz, im Refrain wärmer."""
        lights = self._cached("bokeh", self._bokeh)
        dx = int((f.t * 4) % 200)
        image.paste(lights.crop((dx, 0, dx + W, H)), (0, 0), lights.crop((dx, 0, dx + W, H)))
        warm = (0.15 + 0.25 * f.energy) * (1.3 if f.chorus else 1.0)
        draw.rectangle([0, 0, W, H], fill=(*self.accent, int(30 * warm)))
        frame_color = (12, 16, 24, 230)
        draw.rectangle([0, 0, W, 18], fill=frame_color)
        draw.rectangle([W // 2 - 5, 18, W // 2 + 5, H], fill=(12, 16, 24, 170))
        draw.rectangle([0, H * 0.5 - 4, W, H * 0.5 + 4], fill=(12, 16, 24, 90))

    def _bokeh(self) -> Image.Image:
        rng = random.Random(11)
        layer = Image.new("RGBA", (W + 200, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        palette = [self.accent, self.light, (130, 180, 255), (255, 214, 150), (200, 220, 255)]
        for _ in range(70):
            x, y, r = rng.random() * (W + 200), H * (0.15 + 0.75 * rng.random()), 8 + rng.random() * 30
            d.ellipse([x - r, y - r, x + r, y + r], fill=(*rng.choice(palette), int(40 + 70 * rng.random())))
        return layer.filter(ImageFilter.GaussianBlur(9))

    def _bg_neon_grid(self, image, draw, f: Frame) -> None:
        """80er: Sonne mit Streifen, ein Neonraster läuft im Tempo auf dich zu."""
        sun = self._cached("sun", self._sun)
        image.paste(sun, (W // 2 - sun.width // 2, int(H * 0.16)), sun)
        horizon = H * 0.58
        draw.rectangle([0, horizon, W, H], fill=(18, 6, 40, 235))
        neon = _mix(self.accent, (255, 255, 255), 0.25 * f.beat_pulse)
        alpha = int(110 + 120 * f.energy)
        travel = (f.beat + f.phase) if f.beat >= 0 else f.t
        for k in range(12):
            z = (k + 1 - (travel % 1.0)) / 12
            y = horizon + (H - horizon) * z ** 2
            draw.line([0, y, W, y], fill=(*neon, alpha), width=1 + int(z * 2))
        for k in range(-12, 13):
            draw.line([W / 2 + k * 18, horizon, W / 2 + k * 120, H], fill=(*neon, alpha), width=1)

    def _sun(self) -> Image.Image:
        size = int(H * 0.5)
        sun = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(sun)
        for y in range(size):
            color = _mix((255, 230, 120), (255, 80, 160), y / size)
            d.line([0, y, size, y], fill=(*color, 255))
        mask = Image.new("L", (size, size), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([0, 0, size - 1, size - 1], fill=255)
        for k in range(6):
            y = size * (0.55 + k * 0.075)
            md.rectangle([0, y, size, y + 2 + k], fill=0)
        sun.putalpha(mask)
        return sun

    def _bg_radial(self, image, draw, f: Frame) -> None:
        """Future Bass: weiße Formen drehen sich um einen Kreis, der im Takt pulsiert (das Spektrum läuft rundum)."""
        cx, cy = W / 2, H * 0.40
        turn = f.t * 0.3
        for k in range(3):
            r = 150 + k * 40 + 18 * f.beat_pulse * self.strength
            points = [(cx + r * math.cos(turn * (1 + k * 0.3) + a * math.tau / 3),
                       cy + r * math.sin(turn * (1 + k * 0.3) + a * math.tau / 3)) for a in range(3)]
            draw.polygon(points, outline=(*self.light, int(60 + 80 * f.energy)), width=2)

    def _bg_tunnel(self, image, draw, f: Frame) -> None:
        """Drum and Bass: ein Tunnel aus Ringen, ein Ring pro Schlag; im Refrain doppelt so schnell."""
        cx, cy = W / 2, H * 0.45
        speed = 2.0 if f.chorus else 1.0
        travel = ((f.beat + f.phase) if f.beat >= 0 else f.t * 2) * speed
        for k in range(14):
            z = ((k - travel) % 14) / 14
            s = 0.04 + z ** 2.2 * 1.3
            color = _mix(self.accent, self.light, z)
            draw.rectangle([cx - W * s, cy - H * s, cx + W * s, cy + H * s], outline=(*color, int(50 + 160 * z)),
                           width=1 + int(z * 3))

    def _bg_room(self, image, draw, f: Frame) -> None:
        """Lo-Fi: Zimmer mit Fenster in die Nacht, Kassette dreht sich im Tempo, die Lampe geht im Refrain an."""
        wx0, wy0, wx1, wy1 = W * 0.55, H * 0.08, W * 0.92, H * 0.5
        draw.rectangle([wx0, wy0, wx1, wy1], fill=(20, 24, 48, 255), outline=(30, 26, 34, 255), width=6)
        draw.line([(wx0 + wx1) / 2, wy0, (wx0 + wx1) / 2, wy1], fill=(30, 26, 34, 255), width=4)
        rng = random.Random(5)
        for _ in range(18):
            x, y = wx0 + 8 + rng.random() * (wx1 - wx0 - 16), wy0 + 8 + rng.random() * (wy1 - wy0) * 0.6
            twinkle = 0.5 + 0.5 * math.sin(f.t * 2 + x)
            draw.point([(x, y)], fill=(255, 255, 230, int(120 + 120 * twinkle)))
        if self.weather != "rain":                          # Regen am Fenster gehört zum Lo-Fi-Zimmer
            for i, (x0, y0, speed, size, _) in enumerate(self._particles[:40]):
                x = wx0 + x0 * (wx1 - wx0)
                y = wy0 + ((y0 + f.t * 0.5 * speed) % 1.0) * (wy1 - wy0)
                draw.line([x, y, x - 2, y + 8], fill=(180, 200, 255, 90), width=1)
        draw.rectangle([0, H * 0.78, W, H], fill=(30, 22, 26, 255))
        lamp = 0.35 + 0.65 * (1.0 if f.chorus else f.energy * 0.6)
        glow = self._cached("lamp", self._lamp)
        image.paste((255, 200, 120), (0, 0), glow.point(lambda v: int(v * lamp)))
        draw = ImageDraw.Draw(image, "RGBA")
        self._cassette(draw, W * 0.83, H * 0.81, f)      # links unten steht der Akkord

    def _lamp(self) -> Image.Image:
        y, x = np.mgrid[0:H, 0:W]
        d = np.hypot((x - W * 0.2) / W, (y - H * 0.35) / H)
        return Image.fromarray((np.clip(1 - d * 2.2, 0, 1) ** 2 * 90).astype(np.uint8), "L")

    def _cassette(self, draw, x: float, y: float, f: Frame) -> None:
        w, h = 120, 74
        draw.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=(60, 50, 60, 255), outline=(*self.accent, 200),
                               width=2)
        draw.rectangle([x + 12, y + 10, x + w - 12, y + 26], fill=(*self.light, 220))
        angle = f.t * 2.4 * (f.energy + 0.5)
        for cx in (x + 36, x + w - 36):
            cy = y + 46
            draw.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=(30, 26, 30, 255), outline=(200, 190, 180, 255))
            for k in range(3):
                a = angle + k * math.tau / 3
                draw.line([cx, cy, cx + math.cos(a) * 11, cy + math.sin(a) * 11], fill=(200, 190, 180, 255), width=2)

    def _bg_audience(self, image, draw, f: Frame) -> None:
        """Idol-Bühne: Lichtkegel und ein Publikum mit Leuchtstäben, die im Takt schwingen."""
        self._bg_stage(image, draw, f)
        rows = self._cached("crowd", self._crowd)
        image.paste((10, 6, 20), (0, int(H * 0.86)), rows)
        colors = [self.accent, (255, 90, 170), (120, 200, 255), (255, 230, 90), (140, 255, 170)]
        swing = math.sin(math.pi * ((f.beat % 2) + f.phase)) if f.beat >= 0 else 0
        for i in range(26):
            x = W * (i + 0.5) / 26
            color = colors[(i + (max(f.beat, 0) // 4 if f.chorus else 0)) % len(colors)] if f.chorus else colors[1]
            a = swing * 0.5 * (1 if i % 2 else -1) * (0.4 + 0.6 * self.strength)
            x1, y1 = x + math.sin(a) * 40, H * 0.86 - math.cos(a) * 40
            draw.line([x, H * 0.9, x1, y1], fill=(*color, 230), width=5)
            draw.ellipse([x1 - 6, y1 - 6, x1 + 6, y1 + 6], fill=(*color, 90))

    def _crowd(self) -> Image.Image:
        mask = Image.new("L", (W, int(H * 0.14) + 1), 0)
        d = ImageDraw.Draw(mask)
        rng = random.Random(3)
        for i in range(34):
            x = W * (i + rng.random() * 0.6) / 34
            r = 13 + rng.random() * 6
            d.ellipse([x - r, 10 + rng.random() * 8, x + r, 10 + 2 * r], fill=230)
            d.rectangle([x - r - 4, 10 + 1.6 * r, x + r + 4, H], fill=230)
        return mask

    def _bg_washi(self, image, draw, f: Frame) -> None:
        """Wafuu: rote Sonne, Seigaiha-Wellen am Boden, goldene Linien, im Takt."""
        r = int(H * 0.2 + 6 * f.beat_pulse * self.strength)
        cx, cy = W * 0.5, H * 0.33
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(205, 30, 45, 230))
        waves = self._cached("seigaiha", self._seigaiha)
        image.paste(waves, (0, int(H * (0.9 - 0.06 * f.level))), waves)     # die Wellen steigen mit der Lautstärke
        gold = (*self.accent, int(120 + 100 * f.energy))
        draw.line([W * 0.06, H * 0.12, W * 0.94, H * 0.12], fill=gold, width=2)
        draw.line([W * 0.06, H * 0.865, W * 0.94, H * 0.865], fill=gold, width=2)

    def _seigaiha(self) -> Image.Image:
        h = int(H * 0.18) + 2
        layer = Image.new("RGBA", (W, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        r = 26
        for row in range(5):
            for col in range(-1, W // (2 * r) + 2):
                x = col * 2 * r + (r if row % 2 else 0)
                y = row * r * 0.55 + r
                for k in range(4):
                    rr = r - k * 6
                    d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(25, 40, 90, 170) if k % 2 == 0 else
                              (230, 220, 200, 130))     # durchscheinend: unten links stehen Titel und Akkord
        return layer

    def _bg_deco(self, image, draw, f: Frame) -> None:
        """Art déco: goldener Strahlenkranz, der sich im Swing wiegt, Rahmen wie ein altes Plakat."""
        rays = self._cached("rays", self._rays)
        angle = math.sin(f.t * 0.5) * 3 + (f.beat_pulse - 0.5) * 2 * self.strength
        turned = rays.rotate(angle, center=(W / 2, H * 0.62))
        image.paste(turned, (0, 0), turned)
        gold = (*self.accent, 220)
        for inset in (14, 22):
            draw.rectangle([inset, inset, W - inset, H - inset], outline=gold, width=2)
        for corner_x, corner_y, sx, sy in ((14, 14, 1, 1), (W - 14, 14, -1, 1), (14, H - 14, 1, -1),
                                           (W - 14, H - 14, -1, -1)):
            draw.line([corner_x, corner_y + sy * 40, corner_x + sx * 40, corner_y], fill=gold, width=2)

    def _rays(self) -> Image.Image:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        cx, cy = W / 2, H * 0.62
        for k in range(28):
            a0, a1 = math.pi + k * math.pi / 28, math.pi + (k + 0.5) * math.pi / 28
            d.polygon([(cx, cy), (cx + math.cos(a0) * W, cy + math.sin(a0) * W),
                       (cx + math.cos(a1) * W, cy + math.sin(a1) * W)], fill=(*self.accent, 34))
        return layer

    def _bg_chrome(self, image, draw, f: Frame) -> None:
        """Hyperpop: knallige Farbflecken, die wandern, Sticker, auf der Kick ein Farbversatz."""
        blob = self._cached("blob", self._blob)
        colors = [(255, 60, 172), (43, 134, 197), (246, 255, 0), (120, 75, 255)]
        for k, color in enumerate(colors):
            x = W * (0.5 + 0.38 * math.sin(f.t * (0.21 + k * 0.07) + k * 1.9)) - blob.width / 2
            y = H * (0.45 + 0.32 * math.cos(f.t * (0.17 + k * 0.05) + k)) - blob.height / 2
            image.paste(color, (int(x), int(y)), blob)

    def _blob(self) -> Image.Image:
        size = 360
        y, x = np.mgrid[0:size, 0:size]
        d = np.hypot(x - size / 2, y - size / 2) / (size / 2)
        return Image.fromarray((np.clip(1 - d, 0, 1) ** 1.6 * 150).astype(np.uint8), "L")

    def _bg_ascii(self, image, draw, f: Frame) -> None:
        """Textkunst (V7): Zeichenregen nur aus dem eigenen Liedtext, Spielanzeige oben, Pixel-Herzen im Takt."""
        cw, ch = 8, 16
        cols, rows = W // cw, H // ch
        image.paste((24, 16, 44), (0, 0, W, H))
        rng = random.Random(17)
        speed = 6 + 10 * f.energy
        for c in range(0, cols, 2):
            if rng.random() > 0.5:
                continue
            length = rng.randint(4, 12)
            head = (rng.random() * rows * 1.5 + f.t * speed * (0.6 + rng.random())) % (rows + length) - 1
            for k in range(length):
                r = int(head) - k
                if 4 <= r < rows - 7 and not (rows * TEXT_BAND[0] - 1 < r < rows * TEXT_BAND[1] + 1
                                              and cols * 0.12 < c < cols * 0.88):
                    alpha = int(220 * (1 - k / length))
                    color = self.accent if k == 0 else self.light
                    char = self.chars[(c * 7 + r * 3 + int(f.t * 3)) % len(self.chars)] if self.kana else \
                        "01*+"[(c + r) % 4]
                    draw.text((c * cw, r * ch), char, font=self.font, fill=(*color, alpha))
        draw.rectangle([0, 0, W, ch + 6], fill=(40, 26, 70, 255))
        lives = max(1, min(5, int(round(f.energy * 5))))
        hud = "♥" * lives + "♡" * (5 - lives)
        draw.text((8, 3), hud, font=self.font, fill=(255, 120, 170, 255))
        bar = int(f.song_progress * 12)
        draw.text((W - 8 * 16, 3), "[" + "■" * bar + "□" * (12 - bar) + "]", font=self.font, fill=(*self.light, 255))
        # Pixel-Herzen als Kästchen gemalt: nicht jede Schrift hat die Blockzeichen
        heart = (".##..##.", "########", "########", ".######.", "..####..", "...##...")
        jump = int(6 * f.beat_pulse * self.strength)
        px = 7
        for side, x in ((0, 24), (1, W - 24 - 8 * px)):
            top = H * 0.48 - (jump if side == (max(f.beat, 0) % 2) else 0)
            for i, line in enumerate(heart):
                for k, cell in enumerate(line):
                    if cell == "#":
                        draw.rectangle([x + k * px, top + i * px, x + (k + 1) * px - 2, top + (i + 1) * px - 2],
                                       fill=(255, 120 + 60 * side, 170, 255))
        if f.chorus and self.strength > 0.5:                # Pixel-Konfetti im Refrain
            for i, (x0, y0, sp, size, hue) in enumerate(self._particles[:50]):
                y = ((y0 + f.t * 0.25 * sp) % 1.0) * H
                x = x0 * W
                color = _hue(self.accent, hue)
                draw.rectangle([x, y, x + 4, y + 4], fill=(*color, 220))

    # ── Teilchen ────────────────────────────────────────────────────────────────
    def _weather(self, draw, f: Frame) -> None:
        if self.weather and self.scene.background != "ascii":
            self._particles_of(self.weather, draw, f, 1.0)

    def _particles_of(self, kind: str, draw, f: Frame, share: float) -> None:
        count = int(len(self._particles) * share * (0.35 + 0.65 * f.energy))
        speed = 0.6 + 0.4 * self.strength
        for i, (x0, y0, sp, size, hue) in enumerate(self._particles[:count]):
            if kind == "rain":
                y = ((y0 + f.t * 0.9 * sp * speed) % 1.1 - 0.05) * H
                x = (x0 * (W + 100) - y * 0.18) % (W + 100) - 50
                draw.line([x, y, x + 4, y + 16 + 10 * size], fill=(200, 220, 255, int(60 + 60 * size)), width=1)
            elif kind == "snow":
                y = ((y0 + f.t * 0.08 * sp * speed) % 1.05) * H
                x = (x0 * W + math.sin(f.t + i) * 14) % W
                r = 1 + size * 2.5
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(120 + 100 * size)))
            elif kind == "petals":
                y = ((y0 + f.t * 0.07 * sp * speed) % 1.05) * H
                x = (x0 * W + math.sin(f.t * 0.8 + i) * 30 + f.t * 12) % W
                r = 3 + size * 4
                draw.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=(255, 183, 197, int(150 + 80 * size)))
            elif kind == "stars":
                x, y = x0 * W, y0 * H * 0.8
                twinkle = 0.5 + 0.5 * math.sin(f.t * (1 + sp) + i * 1.3)
                r = 1 + size * 2 + 2 * f.beat_pulse * twinkle * self.strength
                if self.tidy:                             # B5: kleinere, ruhigere Funkel-Kreuze
                    r, twinkle = r * 0.6, twinkle * 0.7
                draw.line([x - r * 2, y, x + r * 2, y], fill=(255, 255, 230, int(200 * twinkle)), width=1)
                draw.line([x, y - r * 2, x, y + r * 2], fill=(255, 255, 230, int(200 * twinkle)), width=1)
            elif kind in ("sparks", "fire"):
                y = (1.05 - (y0 + f.t * 0.12 * sp * speed) % 1.1) * H
                x = (x0 * W + math.sin(f.t * 2 + i) * 6) % W
                r = 1 + size * 1.5
                color = _mix(self.accent, (255, 230, 120), size)
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(*color, int(120 + 110 * size)))
            elif kind == "hearts":
                y = (1.05 - (y0 + f.t * 0.06 * sp * speed) % 1.1) * H
                x = (x0 * W + math.sin(f.t + i) * 10) % W
                self._heart(draw, x, y, 5 + size * 6, (255, 110, 170, int(120 + 100 * size)))
            elif kind == "tears":
                y = ((y0 + f.t * 0.35 * sp * speed) % 1.05) * H
                x = x0 * W
                draw.ellipse([x - 2, y - 2, x + 2, y + 4], fill=(180, 210, 255, 140))
            elif kind == "sea":
                y = (1.05 - (y0 + f.t * 0.05 * sp) % 1.1) * H
                x = (x0 * W + math.sin(f.t + i) * 8) % W
                r = 2 + size * 5
                draw.ellipse([x - r, y - r, x + r, y + r], outline=(200, 240, 255, 140), width=1)
            elif kind == "wind":
                x = ((x0 + f.t * 0.3 * sp * speed) % 1.2 - 0.1) * W
                y = y0 * H
                draw.line([x, y, x + 30 + 30 * size, y - 3], fill=(255, 255, 255, 70), width=1)
            elif kind == "music":
                y = (1.05 - (y0 + f.t * 0.05 * sp) % 1.1) * H
                x = x0 * W
                draw.ellipse([x - 4, y - 3, x + 4, y + 3], fill=(*self.light, 170))
                draw.line([x + 4, y, x + 4, y - 14], fill=(*self.light, 170), width=2)

    @staticmethod
    def _heart(draw, x: float, y: float, r: float, color: tuple) -> None:
        draw.ellipse([x - r, y - r * 0.6, x, y + r * 0.3], fill=color)
        draw.ellipse([x, y - r * 0.6, x + r, y + r * 0.3], fill=color)
        draw.polygon([(x - r, y - 0.1 * r), (x + r, y - 0.1 * r), (x, y + r)], fill=color)

    def _line_motifs(self, draw, f: Frame, particles: bool = True, chat: bool = True) -> None:
        """V8: Steht in der laufenden Zeile ein Wort mit Motiv, kommt es dazu: Herzen, Sterne, Tränen, Chat-Blasen."""
        if particles:
            extra = [m for m in ("hearts", "stars", "tears", "fire", "music", "petals", "snow") if m in f.motifs
                     and m != self.weather and m != self.scene.particles]
            for motif in extra[:2]:
                self._particles_of(motif, draw, f, 0.12 if self.tidy else 0.25)
        if chat and ("chat" in f.motifs or (self.chat and f.kind == "Spoken")):
            (self._chat_tidy if self.tidy else self._chat_bubbles)(draw, f)

    CHAT_SECONDS = 2.4                # 1.7.0: so lange braucht eine Blase, bis die nächste kommt

    def _chat_tidy(self, draw, f: Frame) -> None:
        """
        1.7.0 (B3): Chat mit Inhalt. In jeder Blase steht ein Wort der laufenden Zeile (ohne Schrift mit Kana drei
        Tipp-Punkte), die Blasen gleiten ruhig nach oben und blenden aus, abwechselnd rechts (mit „既読“) und links,
        immer über der Notenlinie. Bis 1.6 waren sie leer und sprangen alle zwei Sekunden.
        """
        words = [w for w in f.words if w.strip()] if self.kana else []
        step = f.t / self.CHAT_SECONDS
        for back in range(3):
            k = int(step) - back
            age = step - k                                # 0 = gerade gekommen, 3 = oben verschwunden
            alpha = max(0.0, min(1.0, age * 3, (3.0 - age) * 1.2))
            if alpha <= 0.02:
                continue
            mine = k % 2 == 0
            text = words[(k + k // 2) % len(words)] if words else "…"      # nicht immer dasselbe Wort je Seite
            box = draw.textbbox((0, 0), text, font=self.font)
            w = box[2] - box[0] + 26
            y = H * (ROLL_BAND[0] - 0.06) - age * H * 0.045 - 26
            x = W - 30 - w if mine else 30
            draw.rounded_rectangle([x, y, x + w, y + 26], radius=12,
                                   fill=(*(self.accent if mine else (70, 70, 85)), int(170 * alpha)))
            draw.text((x + 13 - box[0], y + 13 - (box[1] + box[3]) / 2), text, font=self.font,
                      fill=(255, 255, 255, int(235 * alpha)))
            if mine and self.kana:
                draw.text((x - 34, y + 8), "既読", font=self.small_font, fill=(200, 200, 210, int(160 * alpha)))

    def _chat_bubbles(self, draw, f: Frame) -> None:
        """Steht 既読, スマホ oder もしもし im Text, wird es zum Chat: Blasen steigen am Rand auf, „既読“ daneben."""
        rng = random.Random(int(f.t // 2))
        for k in range(3):
            mine = (k + int(f.t // 2)) % 2 == 0
            y = H * (0.12 + 0.11 * k) - (f.t % 2) * 8
            w = 90 + rng.random() * 90
            x = W - 30 - w if mine else 30
            draw.rounded_rectangle([x, y, x + w, y + 26], radius=12,
                                   fill=(*(self.accent if mine else (70, 70, 85)), 150))
            if mine and self.kana:
                draw.text((x - 34, y + 8), "既読", font=self.small_font, fill=(200, 200, 210, 160))

    # ── Musik sichtbar (V5) ────────────────────────────────────────────────────
    def _spectrum(self, image, draw, f: Frame) -> None:
        if f.bands is None:
            return
        kind = self.scene.spectrum
        bands = f.bands
        lo, hi = SPECTRUM_BAND
        base, top = H * hi, H * lo
        color = _mix(self.accent, self.light, 0.3)
        if self.calm:                                   # B7: halb so hoch und blasser
            top = base - (base - top) * 0.5
            kind = "soft" if kind not in ("none", "radial", "scope") else kind
        if kind == "radial":
            cx, cy, r0 = W / 2, H * 0.40, 110 + 10 * f.beat_pulse * self.strength
            n = len(bands)
            for i, v in enumerate(bands):
                for side in (1, -1):
                    a = -math.pi / 2 + side * (i + 0.5) / n * math.pi
                    r1 = r0 + 8 + v * 90
                    draw.line([cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1,
                               cy + math.sin(a) * r1], fill=(*self.light, 210), width=3)
            draw.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], outline=(*self.light, 230), width=3)
        elif kind == "scope" and f.wave is not None:
            n = len(f.wave)
            mid = (base + top) / 2
            points = [(W * 0.2 + W * 0.6 * i / (n - 1), mid + float(v) * (base - top) * 0.6) for i, v in
                      enumerate(f.wave)]
            draw.line(points, fill=(*self.accent, 230), width=2)
        elif kind == "meters":
            n = min(16, len(bands))
            seg_h = (base - top) / 8
            for i in range(n):
                v = float(np.mean(bands[i * len(bands) // n:(i + 1) * len(bands) // n]))
                x = W * 0.18 + (W * 0.64) * i / n
                lit = int(round(v * 8))
                for k in range(8):
                    on = k < lit
                    color_k = (255, 60, 40) if k >= 6 else (255, 200, 40) if k >= 4 else (80, 230, 90)
                    draw.rectangle([x, base - (k + 1) * seg_h + 2, x + W * 0.64 / n - 4, base - k * seg_h],
                                   fill=(*color_k, 230 if on else 40))
        elif kind == "blocks":                         # Pegel aus Kästchen wie in einem alten Spiel
            cw, rows = 16, 5
            ch = (base - top) / rows
            n = W // cw
            first, last = n // 5, n - n // 5          # links steht der Akkord
            for i in range(first, last):
                v = float(bands[min(len(bands) - 1, int((i - first) * len(bands) / (last - first)))]) * rows
                for r in range(rows):
                    fill = min(1.0, max(0.0, v - r))
                    if fill <= 0:
                        continue
                    color_r = _mix(self.light, self.accent, r / rows)
                    y1 = base - r * ch
                    draw.rectangle([i * cw + 1, y1 - max(2.0, (ch - 2) * fill), i * cw + cw - 2, y1 - 2],
                                   fill=(*color_r, 255))
        elif kind != "none":
            n = len(bands)
            width = W * 0.6 / n
            x0 = W * 0.2                                # links unten steht der Akkord
            for i, v in enumerate(bands):
                height = 3 + float(v) * (base - top)
                x = x0 + i * width
                alpha = (90 if self.calm else 150) if kind == "soft" else 210
                if kind == "mirror":
                    mid = (base + top) / 2
                    draw.rectangle([x + 1, mid - height / 2, x + width - 1, mid + height / 2],
                                   fill=(*_hue(color, i / n * 0.5), alpha))
                else:
                    draw.rounded_rectangle([x + 1, base - height, x + width - 1, base], radius=2,
                                           fill=(*_mix(color, (255, 255, 255), float(v) * 0.4), alpha))

    def _melody_line(self, draw, f: Frame) -> None:
        """Die Gesangsmelodie als laufende Notenlinie (wie im Piano-Roll): gesungene Töne in der Akzentfarbe."""
        lo, hi = ROLL_BAND
        low, high = f.pitch_range
        span = max(6, high - low)
        before, after = 2.0, 4.0
        x_now = W * 0.3
        px = (W * 0.6) / (before + after)
        for start, end, pitch in f.notes:
            x0 = x_now + (start - f.t) * px
            x1 = x_now + (end - f.t) * px - 2
            if x1 < W * 0.08 or x0 > W * 0.92:
                continue
            y = H * hi - (pitch - low) / span * H * (hi - lo)
            sung = start <= f.t
            color = (*self.accent, 220) if sung else (*self.light, 90)
            draw.rounded_rectangle([max(x0, W * 0.08), y - 3, min(x1, W * 0.92), y + 3], radius=3, fill=color)
        draw.line([x_now, H * lo - 6, x_now, H * hi + 6], fill=(*self.light, 60), width=1)

    def _timeline(self, draw, f: Frame) -> None:
        """Oben rechts der Ablauf des Songs mit Position, links daneben die Schläge des Takts (V3, V4). 1.7.0: die
        Schläge standen bis 1.6 unten links auf dem Akkord."""
        x0, x1, y = W * 0.62, W * 0.97, 10
        for start, end, kind in f.sections:
            color = self.accent if kind == "Chorus" else self.light if kind in ("Verse", "PreChorus") else \
                (255, 255, 255)
            alpha = 200 if kind == "Chorus" else 110
            draw.rounded_rectangle([x0 + (x1 - x0) * start + 1, y, x0 + (x1 - x0) * end - 1, y + 5], radius=2,
                                   fill=(*color, alpha))
        mx = x0 + (x1 - x0) * f.song_progress
        draw.polygon([(mx - 4, y - 5), (mx + 4, y - 5), (mx, y)], fill=(255, 255, 255, 230))
        if f.beat >= 0:
            for k in range(4):
                on = k == f.beat % 4
                r = 3 + (2 * f.beat_pulse if on else 0)
                cx = x0 - 60 + k * 12
                draw.ellipse([cx - r, y + 2.5 - r, cx + r, y + 2.5 + r],
                             fill=(*self.accent, 230) if on else (255, 255, 255, 60))

    def _paste_figure(self, image, f: Frame) -> None:
        """V9: deine Figur wippt im Takt und öffnet den Mund, wenn gerade ein Ton gesungen wird."""
        closed, opened = self._figure
        picture = opened if f.singing else closed
        bounce = int(8 * f.beat_pulse * self.strength)
        x = int(W * 0.03)
        y = int(H - picture.height - H * 0.02) - bounce
        image.paste(picture, (x, y), picture)

    # ── Bewegung und Licht ─────────────────────────────────────────────────────
    def _move(self, image, f: Frame) -> Image.Image:
        beat = self.scene.beat
        if self.strength < 0.5:
            beat = "sway" if beat in ("shake", "zoom", "glitch") else beat
        if beat == "zoom" and f.kick > 0.05:
            z = 1 + 0.025 * f.kick * self.strength * (1.4 if f.chorus else 1.0)
            w, h = int(W / z), int(H / z)
            return image.crop(((W - w) // 2, (H - h) // 2, (W - w) // 2 + w, (H - h) // 2 + h)).resize((W, H))
        if beat == "shake" and f.kick > 0.3:
            dx = int((random.Random(int(f.t * 30)).random() - 0.5) * 8 * f.kick * f.energy)
            moved = Image.new("RGB", (W, H), (0, 0, 0))
            moved.paste(image, (dx, int(dx / 2)))
            return moved
        if beat == "glitch" and f.snare > 0.7:
            r, g, b = image.split()
            shift = int(4 * f.snare)
            r = r.transform(r.size, Image.AFFINE, (1, 0, shift, 0, 1, 0))
            return Image.merge("RGB", (r, g, b))
        return image

    def _light(self, image, f: Frame) -> Image.Image:
        """Blitze und Ein-/Ausblenden. Blitze höchstens FLASHES_PER_SECOND pro Sekunde und MAX_FLASH hell (V12)."""
        flash = self.allowed_flash(f.t, f.flash)
        if flash > 0.01:
            image = Image.blend(image, Image.new("RGB", (W, H), (255, 255, 255)), flash)
        if f.fade < 0.999:
            image = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), image, max(0.0, f.fade))
        return image

    def allowed_flash(self, t: float, wanted: float) -> float:
        """So hell darf es jetzt aufblitzen: 0, wenn in der letzten Sekunde schon genug Blitze waren."""
        if wanted <= 0.02:
            return 0.0
        wanted = min(MAX_FLASH, wanted * self.strength)
        recent = [x for x in self._flash_times if t - x < 1.0]
        starting = not self._flash_times or t - self._flash_times[-1] > 0.12
        if starting:
            if len(recent) >= FLASHES_PER_SECOND:
                return 0.0
            self._flash_times = recent + [t]
        return wanted

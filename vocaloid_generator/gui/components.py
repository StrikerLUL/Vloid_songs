# components.py – Player mit Wellenform und Piano-Roll als eigene Elemente
from nicegui import ui
from nicegui.element import Element

STYLE = """
.vg-player { width: 100%; }
.vg-wave { width: 100%; cursor: pointer; }
.vg-controls { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.vg-play { width: 44px; height: 44px; border-radius: 50%; border: none; font-size: 16px; cursor: pointer;
           background: #ff4f8b; color: white; }
.vg-play:disabled { background: #555; cursor: default; }
.vg-time { font-variant-numeric: tabular-nums; opacity: 0.8; }
.vg-title { opacity: 0.6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vg-roll { position: relative; width: 100%; overflow-x: auto; overflow-y: hidden; border-radius: 8px;
           background: #1b1b24; cursor: crosshair; }
.vg-roll canvas { display: block; }
.vg-head { position: absolute; top: 0; left: 0; bottom: 14px; width: 2px; background: #ffffff; opacity: 0.8;
           pointer-events: none; }
.vg-karaoke { text-align: center; padding: 10px 0 4px; }
.vg-line { font-size: 26px; font-weight: 600; min-height: 36px; letter-spacing: 1px; }
.vg-line span { color: #ffffff; transition: color 0.08s; }
.vg-line span.sung { color: #ff4f8b; }
.vg-next { font-size: 16px; opacity: 0.5; min-height: 22px; }
.vg-roll.editing { cursor: ns-resize; }
"""


class WavePlayer(Element, component="wave_player.js", esm={"wavesurfer": "wavesurfer"}):
    """Spielt eine Datei ab und zeigt ihre Wellenform; peaks und duration kommen aus media.peaks()."""

    def __init__(self) -> None:
        super().__init__()
        self._props["url"] = ""
        self._props["title"] = ""
        self._props["peaks"] = []
        self._props["duration"] = 0

    def show(self, url: str, title: str, peaks: list, duration: float) -> None:
        self._props.update(url=url, title=title, peaks=peaks, duration=duration)
        self.update()

    @property
    def url(self) -> str:
        return self._props["url"]

    @property
    def title(self) -> str:
        return self._props["title"]


class PianoRoll(Element, component="piano_roll.js"):
    """
    Noten aller Spuren; Spuren lassen sich ausblenden. Mit editable lassen sich die Töne der Gesangsmelodie
    nach oben und unten ziehen (oder mit den Pfeiltasten verschieben); jede Änderung meldet das Ereignis "edit"
    mit {start, pitch} (Anfang in Sekunden, neue Tonhöhe). Am rechten Rand gezogen (oder mit Pfeil links/rechts)
    wird ein Ton kürzer oder länger; das meldet "resize" mit {start, end} (Sekunden). Ein Doppelklick auf einen Ton
    meldet "phrase" mit {start}: seine Phrase soll neu gesungen werden.
    """

    def __init__(self) -> None:
        super().__init__()
        self._props.update(notes=[], tracks=[], hidden=[], duration=0, editable=False, step=0.125)

    def show(self, data: dict) -> None:
        self._props.update(notes=data["notes"], tracks=data["tracks"], duration=data["duration"], hidden=[],
                           step=data.get("step", 0.125))
        self.update()

    @property
    def notes(self) -> list:
        return self._props["notes"]

    @property
    def editable(self) -> bool:
        return self._props["editable"]

    def set_editable(self, editable: bool) -> None:
        self._props["editable"] = editable
        self.update()

    def move(self, start: float, pitch: int) -> None:
        """Den Ton der Gesangsmelodie, der bei start (Sekunden) beginnt, auf pitch setzen (auch in Python)."""
        vocal = next((i for i, t in enumerate(self.tracks) if t.get("key") == "vocals"), None)
        for note in self._props["notes"]:
            if note[3] == vocal and abs(note[0] - start) < 1e-3:
                note[2] = pitch
        self.update()

    def resize(self, start: float, end: float) -> None:
        """Der Ton der Gesangsmelodie, der bei start (Sekunden) beginnt, endet bei end (auch in Python)."""
        vocal = next((i for i, t in enumerate(self.tracks) if t.get("key") == "vocals"), None)
        for note in self._props["notes"]:
            if note[3] == vocal and abs(note[0] - start) < 1e-3:
                note[1] = end
        self.update()

    @property
    def tracks(self) -> list:
        return self._props["tracks"]

    @property
    def hidden(self) -> list:
        return self._props["hidden"]

    def set_hidden(self, hidden: list) -> None:
        self._props["hidden"] = sorted(hidden)
        self.update()


class Karaoke(Element, component="karaoke.js"):
    """Der Liedtext zum Mitlesen; lines kommt aus karaoke.lines()."""

    def __init__(self) -> None:
        super().__init__()
        self._props["lines"] = []

    def show(self, lines: list) -> None:
        self._props["lines"] = lines
        self.update()

    @property
    def lines(self) -> list:
        return self._props["lines"]


def add_style() -> None:
    ui.add_css(STYLE)

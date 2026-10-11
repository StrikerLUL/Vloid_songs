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

    def play_pause(self) -> None:
        self.run_method("playPause")


class PianoRoll(Element, component="piano_roll.js"):
    """Noten aller Spuren; Spuren lassen sich ausblenden."""

    def __init__(self) -> None:
        super().__init__()
        self._props.update(notes=[], tracks=[], hidden=[], duration=0)

    def show(self, data: dict) -> None:
        self._props.update(notes=data["notes"], tracks=data["tracks"], duration=data["duration"], hidden=[])
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


def add_style() -> None:
    ui.add_css(STYLE)

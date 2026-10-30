# app.py – Startet die Oberfläche: ein eigenes Fenster (NiceGUI im nativen Modus) oder der Browser
#
#   uv run vocaloid_generator\app.py            eigenes Fenster
#   uv run vocaloid_generator\app.py --browser  im Browser (z. B. wenn das Fenster nicht aufgeht)
import argparse
import importlib.util
import logging
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

WINDOW_SIZE = (1500, 940)
FAVICON = os.path.join(APP_DIR, "gui", "vloid.png")
# Das eigene Fenster setzt sein Symbol unter Windows nur aus einer .ico-Datei (sonst „Could not set native window icon“)
WINDOW_ICON = os.path.join(os.path.dirname(APP_DIR), "installer", "vloid.ico")


def icon(native: bool) -> str:
    return WINDOW_ICON if native and os.path.isfile(WINDOW_ICON) else FAVICON


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Vocaloid Song Generator mit Oberfläche")
    p.add_argument("--browser", action="store_true", help="im Browser öffnen statt im eigenen Fenster")
    p.add_argument("--port", type=int, default=8090, help="Port für den Browser (Standard: 8090)")
    return p.parse_known_args(argv)[0]


def main(argv=None) -> None:
    # Erst hier importieren: das Fenster läuft in einem zweiten Prozess, der dieses Modul ebenfalls lädt
    from nicegui import app, ui

    from gui.page import build

    import applog
    import userdata
    from settings import SongSettings

    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    userdata.migrate()                  # alte Songs und Einstellungen aus dem Programmordner in den Datenordner
    applog.setup(SongSettings.load().log_file)
    native = not args.browser and importlib.util.find_spec("webview") is not None
    if not args.browser and not native:
        logging.warning("pywebview fehlt, die App öffnet sich im Browser.")
    if native:
        app.native.settings["ALLOW_DOWNLOADS"] = True
    remote = None
    if SongSettings.load().remote_lan:          # 1.6.0: das Handy als Fernbedienung, im WLAN mit Zugangscode
        import fernbedienung
        remote = fernbedienung.start(args.port)
        app.add_middleware(fernbedienung.Zugang)
    ui.run(
        build,
        title="Vloid Songs",
        favicon=icon(native),
        language="de",
        dark=True,
        reload=False,
        native=native,
        window_size=WINDOW_SIZE if native else None,
        host="0.0.0.0" if remote else "127.0.0.1",
        port=args.port if remote or not native else None,
        show=not native,
        reconnect_timeout=fernbedienung.RECONNECT_SECONDS if remote else 30,
    )


if __name__ == "__main__":
    main()

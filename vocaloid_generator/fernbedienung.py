# fernbedienung.py – Das Handy als Fernbedienung (1.6.0)
#
# Mit dem Schalter „Handy als Fernbedienung“ (remote_lan, aus) hört die App beim nächsten Start nicht nur auf diesem
# PC (127.0.0.1), sondern im ganzen WLAN, auf Port PORT. Das Handy öffnet die Adresse im Browser (QR-Code unter
# Hilfe › Handy als Fernbedienung) und bedient dieselbe App: Text eintippen, Song erzeugen, anhören, die MP3 aufs
# Handy laden. Rechnen tut weiter der PC; solange er rechnet, schläft er nicht ein (awake).
# Jedes andere Gerät als dieser PC braucht den Zugangscode (sechs Ziffern): im QR-Code steckt er schon, sonst fragt
# die App danach. Danach merkt sich der Browser den Zugang (Cookie, DAYS Tage); ein neuer Code sperrt alle Geräte
# wieder aus. Nach MOST_TRIES falschen Codes wartet ein Gerät LOCK_SECONDS. Zugang prüft jede Anfrage: die Seite,
# die Verbindung der Oberfläche (WebSocket), die Dateien für den Player, Downloads und das Hochladen.
# Code und Schlüssel liegen in fernbedienung.json im Datenordner, nicht in den Einstellungen (die landen im Verlauf
# und in Vorlagen).
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import socket
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import parse_qsl, urlencode

import config

log = logging.getLogger(__name__)

FILE = "fernbedienung.json"
PORT = 8090
COOKIE = "vloid_zugang"
DAYS = 30
MOST_TRIES, LOCK_SECONDS = 8, 60
RECONNECT_SECONDS = 600         # so lange wartet eine Seite auf ein Handy, dessen Bildschirm aus ist
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


@dataclass
class Fern:
    """Die laufende Fernbedienung: unter dieser Adresse ist die App im WLAN."""
    address: str
    port: int
    code: str

    @property
    def url(self) -> str:
        return f"http://{self.address}:{self.port}/"

    @property
    def login_url(self) -> str:
        """Für den QR-Code: mit dem Code, damit das Handy gleich hinein darf."""
        return f"{self.url}?code={self.code}"


ACTIVE: Optional[Fern] = None       # gesetzt, wenn die App im WLAN läuft (app.py)


def path() -> str:
    return os.path.join(config.DATA_DIR, FILE)


def _load() -> dict:
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    temp = path() + ".neu"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(temp, path())


def _valid(code: str) -> bool:
    return isinstance(code, str) and len(code) == 6 and code.isdigit()


def code() -> str:
    """Der Zugangscode; beim ersten Mal gewürfelt und gespeichert."""
    data = _load()
    if _valid(data.get("code")) and data.get("secret"):
        return data["code"]
    return new_code()


def new_code() -> str:
    """Würfelt einen neuen Code (und Schlüssel): alle Geräte, die schon drin waren, brauchen ihn neu."""
    data = {"code": f"{secrets.randbelow(10 ** 6):06d}", "secret": secrets.token_hex(16)}
    _save(data)
    if ACTIVE is not None:
        ACTIVE.code = data["code"]
    return data["code"]


def token(given: str) -> str:
    """Was der Browser sich merkt: aus dem Code abgeleitet, nicht der Code selbst."""
    secret = (_load().get("secret") or "").encode()
    return hmac.new(secret, given.encode(), hashlib.sha256).hexdigest()


def lan_address() -> str:
    """Die Adresse dieses PCs im WLAN (über die er ins Netz ginge); 127.0.0.1, wenn es keine gibt."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))         # ein Testnetz: es geht kein Paket hinaus
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def start(port: int = PORT) -> Fern:
    """Die App läuft ab jetzt im WLAN (app.py, vor ui.run)."""
    global ACTIVE
    ACTIVE = Fern(lan_address(), port, code())
    log.info("Handy als Fernbedienung: die App ist im WLAN unter %s (Zugangscode unter Hilfe › Handy als "
             "Fernbedienung)", ACTIVE.url)
    return ACTIVE


def is_local(host: Optional[str]) -> bool:
    """Kommt die Anfrage von diesem PC selbst?"""
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    return (mapped or address).is_loopback


def is_remote(client) -> bool:
    """Ist diese Seite auf einem anderen Gerät offen (dem Handy)? Nur, wenn die App im WLAN läuft."""
    if ACTIVE is None:
        return False
    request = getattr(client, "request", None)
    host = getattr(getattr(request, "client", None), "host", None)
    return not is_local(host)


def qr_image(text: str) -> str:
    """Der QR-Code als SVG-Bild (data:-URI), schwarz auf weiß, damit jede Kamera ihn liest."""
    import segno
    return segno.make(text, error="m").svg_data_uri(scale=6, border=3, dark="#000000", light="#ffffff")


# ── wach bleiben ────────────────────────────────────────────────────────────────
_busy = 0


def _set_state(flags: int) -> None:
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def awake(on: bool) -> None:
    """Während ein Song entsteht, schläft der PC nicht ein (Windows); der Bildschirm darf ausgehen. Mehrere Seiten
    zählen zusammen: erst wenn keine mehr rechnet, darf er wieder schlafen."""
    global _busy
    before = _busy
    _busy = max(0, _busy + (1 if on else -1))
    if sys.platform != "win32" or bool(before) == bool(_busy):
        return
    try:
        _set_state(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if _busy else 0))
    except (OSError, AttributeError) as e:
        log.debug("PC wach halten geht nicht: %s", e)


# ── der Zugang ──────────────────────────────────────────────────────────────────
PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vloid Songs</title>
<style>
body {{ background: #121212; color: #eee; font-family: system-ui, sans-serif; margin: 0; padding: 32px 16px; }}
main {{ max-width: 22rem; margin: 0 auto; }}
input {{ font-size: 2rem; letter-spacing: .3rem; width: 100%; box-sizing: border-box; padding: .5rem; text-align: center;
        background: #222; color: #fff; border: 1px solid #7e57c2; border-radius: 8px; }}
button {{ margin-top: 1rem; width: 100%; padding: .8rem; font-size: 1.1rem; background: #ff4f8b; color: #fff;
         border: 0; border-radius: 8px; }}
p {{ color: #bbb; }} .bad {{ color: #ff8a80; }}
</style></head><body><main>
<h1>Vloid Songs</h1>
<p>Gib den Zugangscode ein. Du findest ihn am PC unter Hilfe › Handy als Fernbedienung.</p>
{message}
<form method="get"><input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6"
pattern="[0-9]*" autofocus><button type="submit">Weiter</button></form>
</main></body></html>"""


class Zugang:
    """ASGI-Middleware vor der ganzen App: dieser PC darf immer, andere Geräte mit dem Zugangscode."""

    def __init__(self, app, current: Optional[Callable[[], str]] = None, clock: Callable[[], float] = time.monotonic):
        self.app = app
        self.current = current or (lambda: ACTIVE.code if ACTIVE is not None else code())
        self.clock = clock
        self.tries: dict = {}          # Adresse → (Fehlversuche, gesperrt bis)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        host = (scope.get("client") or (None, None))[0]
        if is_local(host) or self._let_in(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await receive()                 # websocket.connect
            await send({"type": "websocket.close", "code": 1008})
            return
        query = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        given = next((value.strip() for name, value in query if name == "code"), "")
        locked = self._locked(host)
        if given and not locked and hmac.compare_digest(given.encode(), self.current().encode()):
            self.tries.pop(host, None)
            rest = urlencode([(name, value) for name, value in query if name != "code"])
            target = scope.get("root_path", "") + scope["path"] + (f"?{rest}" if rest else "")
            cookie = f"{COOKIE}={token(given)}; Max-Age={DAYS * 86400}; Path=/; HttpOnly; SameSite=Lax"
            await _respond(send, 303, b"", [(b"location", target.encode()), (b"set-cookie", cookie.encode())])
            log.info("Fernbedienung: %s ist drin", host)
            return
        if given and not locked:
            locked = self._failed(host)
        message = ("<p class='bad'>Zu viele falsche Versuche: warte eine Minute.</p>" if locked else
                   "<p class='bad'>Der Code stimmt nicht.</p>" if given else "")
        await _respond(send, 401, PAGE.format(message=message).encode(),
                       [(b"content-type", b"text/html; charset=utf-8"), (b"cache-control", b"no-store")])

    def _let_in(self, scope) -> bool:
        for name, value in scope.get("headers", ()):
            if name != b"cookie":
                continue
            for part in value.decode("latin-1").split(";"):
                key, _, found = part.strip().partition("=")
                if key == COOKIE and hmac.compare_digest(found.encode(), token(self.current()).encode()):
                    return True
        return False

    def _locked(self, host) -> bool:
        return self.tries.get(host, (0, 0.0))[1] > self.clock()

    def _failed(self, host) -> bool:
        count, _ = self.tries.get(host, (0, 0.0))
        count += 1
        if count >= MOST_TRIES:
            self.tries[host] = (0, self.clock() + LOCK_SECONDS)
            log.warning("Fernbedienung: %d falsche Codes von %s, eine Minute gesperrt", count, host)
            return True
        self.tries[host] = (count, 0.0)
        return False


async def _respond(send, status: int, body: bytes, headers: list) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": headers + [(b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})

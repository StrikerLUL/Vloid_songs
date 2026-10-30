# test_fernbedienung_160.py – Das Handy als Fernbedienung (1.6.0): Zugangscode, QR-Code, Hochladen, MP3, wach bleiben
import asyncio
import os

import pytest
import pytest_asyncio
from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing.user_simulation import user_simulation

import fernbedienung
from gui import page
from settings import SongSettings
from test_app import fake_generation  # noqa: F401 – das Fixture gilt so auch hier
from test_app_160 import marked, settings_for, until


@pytest.fixture(autouse=True)
def nothing_running(monkeypatch):
    monkeypatch.setattr(fernbedienung, "ACTIVE", None)
    monkeypatch.setattr(fernbedienung, "_busy", 0)


def test_the_code_has_six_digits_stays_and_a_new_one_locks_everyone_out():
    first = fernbedienung.code()
    assert len(first) == 6 and first.isdigit() and fernbedienung.code() == first
    old = fernbedienung.token(first)
    assert old != first and len(old) == 64
    second = fernbedienung.new_code()
    assert fernbedienung.code() == second and fernbedienung.token(second) != old
    assert "remote_code" not in SongSettings.model_fields         # der Code steht nicht in Verlauf und Vorlagen
    running = fernbedienung.start(8090)
    assert running.code == second and running.url.startswith("http://") and running.url.endswith(":8090/")
    assert running.login_url == f"{running.url}?code={second}"
    assert fernbedienung.new_code() == running.code
    assert fernbedienung.qr_image(running.login_url).startswith("data:image/svg+xml")


async def _call(gate, path="/", query="", cookie=None, host="192.168.1.20", kind="http") -> list:
    sent, seen = [], []

    async def app(scope, receive, send):
        seen.append(scope["path"])
        if kind == "websocket":
            await send({"type": "websocket.accept"})
        else:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"App"})

    async def receive():
        return {"type": "websocket.connect"} if kind == "websocket" else {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    headers = [(b"cookie", cookie.encode())] if cookie else []
    gate.app = app
    await gate(dict(type=kind, path=path, root_path="", query_string=query.encode(), headers=headers,
                    client=(host, 50000)), receive, send)
    return sent


def _status(sent) -> int:
    return sent[0].get("status", 0)


def test_other_devices_need_the_code_this_pc_does_not():
    now = [0.0]
    gate = fernbedienung.Zugang(None, current=lambda: "424242", clock=lambda: now[0])
    run = asyncio.run
    assert _status(run(_call(gate, host="127.0.0.1"))) == 200
    assert _status(run(_call(gate, host="::ffff:127.0.0.1"))) == 200
    asked = run(_call(gate))
    assert _status(asked) == 401 and b"Zugangscode" in asked[1]["body"]
    assert b"stimmt nicht" in run(_call(gate, query="code=111111"))[1]["body"]
    inside = run(_call(gate, path="/datei", query="pfad=x.mp3&code=424242"))
    assert _status(inside) == 303
    headers = dict(inside[0]["headers"])
    assert headers[b"location"] == b"/datei?pfad=x.mp3"
    cookie = headers[b"set-cookie"].decode().split(";")[0]
    assert cookie == f"{fernbedienung.COOKIE}={fernbedienung.token('424242')}"
    assert _status(run(_call(gate, path="/datei", cookie=f"a=b; {cookie}"))) == 200
    assert run(_call(gate, path="/_nicegui_ws/socket.io/", cookie=cookie, kind="websocket"))[0]["type"] == \
        "websocket.accept"
    assert run(_call(gate, path="/_nicegui_ws/socket.io/", kind="websocket"))[0] == \
        {"type": "websocket.close", "code": 1008}
    assert _status(run(_call(gate, cookie=f"{fernbedienung.COOKIE}=falsch"))) == 401


def test_too_many_wrong_codes_lock_a_device_for_a_minute():
    now = [0.0]
    gate = fernbedienung.Zugang(None, current=lambda: "424242", clock=lambda: now[0])
    for _ in range(fernbedienung.MOST_TRIES):
        last = asyncio.run(_call(gate, query="code=000000"))
    assert b"warte eine Minute" in last[1]["body"]
    assert _status(asyncio.run(_call(gate, query="code=424242"))) == 401          # auch der richtige nicht
    assert _status(asyncio.run(_call(gate, query="code=424242", host="192.168.1.21"))) == 303
    now[0] = fernbedienung.LOCK_SECONDS + 1
    assert _status(asyncio.run(_call(gate, query="code=424242"))) == 303


def test_the_pc_stays_awake_while_any_page_makes_a_song(monkeypatch):
    calls = []
    monkeypatch.setattr(fernbedienung.sys, "platform", "win32")
    monkeypatch.setattr(fernbedienung, "_set_state", calls.append)
    one, two = page.Job(), page.Job()
    one.start()
    two.running = True
    two.running = False
    assert calls == [fernbedienung.ES_CONTINUOUS | fernbedienung.ES_SYSTEM_REQUIRED]
    one.running = False
    assert calls[-1] == fernbedienung.ES_CONTINUOUS and fernbedienung._busy == 0
    page.Job()                                       # eine neue Seite ändert nichts
    assert len(calls) == 2


def test_with_the_switch_the_app_listens_in_the_wlan_with_the_code(monkeypatch):
    import nicegui

    import app
    seen, added = {}, []
    monkeypatch.setattr(ui, "run", lambda *a, **kw: seen.update(kw))
    monkeypatch.setattr(nicegui.app, "add_middleware", lambda cls, **kw: added.append(cls))
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda name: object())
    SongSettings(remote_lan=True).save()
    app.main([])
    assert (seen["host"], seen["port"], seen["reconnect_timeout"]) == ("0.0.0.0", 8090, 600)
    assert added == [fernbedienung.Zugang] and fernbedienung.ACTIVE.port == 8090
    SongSettings(remote_lan=False).save()
    app.main([])
    assert seen["host"] == "127.0.0.1" and seen["port"] is None and len(added) == 1


@pytest_asyncio.fixture
async def phone(tmp_path, monkeypatch):
    monkeypatch.setattr(fernbedienung, "ACTIVE", fernbedienung.Fern("192.168.1.5", 8090, "424242"))
    monkeypatch.setattr(fernbedienung, "is_remote", lambda client: True)
    settings_for(tmp_path).save()
    async with user_simulation(root=page.build) as user:
        yield user


async def test_on_the_phone_files_are_uploaded_and_the_mp3_comes_to_the_phone(phone, fake_generation, tmp_path):  # noqa: F811
    await phone.open("/")
    assert marked(phone, "mp3-download")[0].visible
    assert marked(phone, "upload-own_vocal") and not marked(phone, "upload-diffsinger_voice")   # Ordner nicht
    [upload] = marked(phone, "upload-own_vocal-file")
    await upload.handle_uploads([SmallFileUpload("meine stimme.wav", "audio/wav", b"RIFF0000WAVE")])
    await until(lambda: SongSettings.load().own_vocal.endswith(os.path.join("hochgeladen", "meine stimme.wav")))
    assert os.path.getsize(SongSettings.load().own_vocal) == 12
    phone.find(marker="generate").click()
    await phone.should_see("Seed 1000", retries=50)
    phone.find(marker="mp3-download").click()
    response = await phone.download.next(timeout=5)
    assert response.status_code == 200 and len(response.content) > 0
    phone.find(marker="help-menu").click()
    phone.find(marker="menu-remote").click()
    await phone.should_see("424242")
    await phone.should_see("http://192.168.1.5:8090/")
    assert marked(phone, "remote-qr")[0].source.startswith("data:image/svg+xml")
    phone.find(marker="remote-new-code").click()
    await until(lambda: fernbedienung.ACTIVE.code != "424242")
    await phone.should_see(fernbedienung.ACTIVE.code)


async def test_on_the_pc_the_switch_says_it_counts_from_the_next_start(tmp_path):
    settings_for(tmp_path).save()
    async with user_simulation(root=page.build) as user:
        await user.open("/")
        assert not marked(user, "mp3-download")[0].visible and not marked(user, "upload-own_vocal")
        user.find(marker="help-menu").click()
        user.find(marker="menu-remote").click()
        marked(user, "switch-remote_lan")[0].value = True
        await user.should_see("Gilt ab dem nächsten Start")
        await until(lambda: SongSettings.load().remote_lan)
        assert not marked(user, "remote-qr")

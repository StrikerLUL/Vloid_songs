# test_durchsicht_161.py – Fehler aus der Durchsicht nach 1.6.0 (Version 1.6.1)
import asyncio

import numpy as np
import pytest
from PIL import Image

import bilder
import fernbedienung
import musikvideo
from gui import page
from settings import SongSettings
from test_app import fake_generation  # noqa: F401 – das Fixture gilt so auch hier
from test_app_160 import marked, until, user  # noqa: F401
from test_fernbedienung_160 import _call, _status


@pytest.fixture(autouse=True)
def nothing_running(monkeypatch):
    monkeypatch.setattr(page, "_running", 0)
    monkeypatch.setattr(fernbedienung, "_busy", 0)


# ── PC und Handy erzeugen nie gleichzeitig ──────────────────────────────────────────────────
def test_a_second_page_waits_while_another_page_makes_a_song(monkeypatch):
    """PC und Handy (oder zwei Fenster) haben je eine Seite, aber denselben Ausgabeordner, denselben Zufall und
    dasselbe Abbrechen: ein zweiter Song zur selben Zeit überschriebe die Spuren des ersten."""
    notes = []
    monkeypatch.setattr(page.ui, "notify", lambda text, **kw: notes.append(text))
    pc, phone = page.Job(), page.Job()
    assert not pc.blocked() and not phone.blocked() and not notes
    pc.start()
    assert pc.blocked() and not notes                   # läuft auf dieser Seite: still, wie bisher
    assert phone.elsewhere() and phone.blocked() and notes == [page.BUSY_ELSEWHERE]
    assert not pc.elsewhere()
    pc.running = False
    assert not phone.blocked() and not phone.elsewhere()
    phone.start()
    assert pc.blocked() and phone.blocked()
    phone.running = False
    assert page._running == 0


async def test_the_generate_button_says_why_it_waits(user, fake_generation, monkeypatch):
    await user.open("/")
    monkeypatch.setattr(page, "_running", 1)                # auf dem Handy entsteht gerade ein Song
    user.find(marker="generate").click()
    await user.should_see(page.BUSY_ELSEWHERE)
    assert fake_generation == []
    monkeypatch.setattr(page, "_running", 0)
    user.find(marker="generate").click()
    await until(lambda: len(fake_generation) == 1)


# ── Musikvideo: der lauteste Wert wird einmal gemessen ─────────────────────────────────────
class _Counted(np.ndarray):
    absolute = 0

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if ufunc is np.absolute:
            _Counted.absolute += 1
        inputs = tuple(np.asarray(x) if isinstance(x, _Counted) else x for x in inputs)
        return getattr(ufunc, method)(*inputs, **kwargs)


def test_the_wave_in_the_video_does_not_measure_the_whole_song_in_every_frame():
    """Vorher maß jedes Bild den lautesten Wert des ganzen Songs neu: bei 4 Minuten etwa eine Minute pro Video."""
    rate = 22050
    mono = (0.5 * np.sin(2 * np.pi * 220 * np.arange(rate * 4) / rate)).astype(np.float32)
    mono[rate] = 0.8
    sound = musikvideo.Sound(np.zeros((1, musikvideo.BANDS)), np.zeros(1), mono.view(_Counted), rate)
    _Counted.absolute = 0
    waves = [sound.wave(k / musikvideo.FPS) for k in range(1, 100)]
    assert _Counted.absolute == 0 and sound.peak == pytest.approx(0.8)
    assert all(np.max(np.abs(w)) <= 1.0 for w in waves)
    part = mono[rate - 1024:rate + 1024]
    expected = np.clip(part[::len(part) // 160][:160] / 0.8, -1, 1)
    assert np.allclose(sound.wave(1.0), expected)
    assert not np.any(musikvideo.Sound(np.zeros((1, 1)), np.zeros(1), np.zeros(0, np.float32), rate).wave(0.0))


# ── Fernbedienung: wer immer wieder falsch rät, wartet immer länger ─────────────────────────
def test_every_further_lock_lasts_twice_as_long_up_to_an_hour():
    """Mit einer Minute nach acht Fehlversuchen ließen sich die sechs Ziffern in ein paar Wochen durchprobieren."""
    now = [0.0]
    gate = fernbedienung.Zugang(None, current=lambda: "424242", clock=lambda: now[0])
    run = asyncio.run

    def guess_wrong() -> bytes:
        for _ in range(fernbedienung.MOST_TRIES):
            last = run(_call(gate, query="code=000000"))
        return last[1]["body"]

    assert b"warte eine Minute" in guess_wrong()
    now[0] += fernbedienung.LOCK_SECONDS + 1
    assert b"warte 2 Minuten" in guess_wrong()
    now[0] += fernbedienung.LOCK_SECONDS + 1
    assert _status(run(_call(gate, query="code=424242"))) == 401          # die zweite Sperre hält noch
    now[0] += fernbedienung.LOCK_SECONDS
    for _ in range(10):
        guess_wrong()
        assert gate._left("192.168.1.20") <= fernbedienung.LONGEST_LOCK
        now[0] += fernbedienung.LONGEST_LOCK + 1
    assert b"warte 60 Minuten" in guess_wrong()
    now[0] += fernbedienung.LONGEST_LOCK + 1
    assert _status(run(_call(gate, query="code=424242"))) == 303          # der richtige Code setzt alles zurück
    assert b"warte eine Minute" in guess_wrong()


# ── KI-Bilder: jeder Song bekommt seine eigenen ─────────────────────────────────────────────
def test_a_new_song_in_the_same_folder_gets_its_own_pictures(tmp_path, monkeypatch):
    """Alle Songs teilen sich den Ausgabeordner. Vorher bekam ein neuer Song im selben Stil (gleicher Prompt) die
    Bilder des vorigen, obwohl sein Seed andere malt."""
    painted = []

    def fake_run(jobs, folder, size=bilder.SIZE):
        painted.append([job["seed"] for job in jobs])
        for job in jobs:
            Image.new("RGB", bilder.SIZE, (job["seed"] % 255, 0, 0)).save(job["path"])
        return True
    monkeypatch.setattr(bilder, "_run", fake_run)
    wanted = bilder.prompts("Ballade", ["Verse", "Chorus"], {}, ["rain"])
    folder = str(tmp_path / "bilder")
    first = bilder.paint(wanted, folder, 5)
    assert set(first) == {"Verse", "Chorus"} and painted == [[155, 156]]
    assert bilder.paint(wanted, folder, 5) == first and len(painted) == 1      # derselbe Song: nicht noch einmal
    bilder.paint(wanted, folder, 6)
    assert painted[-1] == [186, 187]                                            # ein neuer Song malt neu
    bilder.paint(dict(wanted, Chorus=wanted["Chorus"] + ", snow"), folder, 6)
    assert painted[-1] == [187]                                                 # nur, was sich geändert hat


# ── Setup.exe: auch die KI-Bilder bekommen nach einem Update neue Pakete ───────────────────
def test_the_setup_exe_tops_up_the_pictures_like_the_rating():
    """setup_bilder.py --ergaenzen stand als „macht die Setup.exe“ da, die Setup.exe rief es aber nie auf."""
    import os

    import config
    starter = open(os.path.join(config.REPO_ROOT, "Vloid Songs starten.bat"), encoding="utf-8").read()
    einrichten = starter[starter.index('if "%~1"=="--einrichten"'):starter.index("app.py")]
    assert 'exist "%~dp0tools\\bilder\\venv\\Scripts\\python.exe"' in einrichten
    assert einrichten.index("sync --frozen") < einrichten.index("setup_bilder.py --ergaenzen") < \
        einrichten.index("exit /b 0")


# ── Video-Link: ein Fehler ohne Text bringt die Seite nicht durcheinander ──────────────────
async def test_a_failed_link_without_message_still_says_so(user, monkeypatch):
    import vorbild_link

    def broken(url, progress=None, again=False):
        raise KeyError()
    monkeypatch.setattr(vorbild_link, "measure", broken)
    await user.open("/")
    marked(user, "switch-video_links")[0].value = True
    await until(lambda: marked(user, "reference-link-box")[0].visible)
    user.find(marker="reference-link").type("https://x.y/v")
    user.find(marker="reference-link-measure").click()
    await user.should_see("Das Video ließ sich nicht messen: KeyError", retries=50)
    assert SongSettings.load().video_links

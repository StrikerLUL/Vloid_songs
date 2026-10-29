# test_app_160.py – Die Neuerungen aus 1.6.0 in der Oberfläche: Hör-Duell, einfache Ansicht, Text-Baukasten
import asyncio
import os

import numpy as np
import pytest_asyncio
import soundfile as sf
from nicegui import ElementFilter
from nicegui.testing.user_simulation import user_simulation

import hoer_duell
import laufzeit
import qualitaet
from gui import einfach, labels, page
from settings import SongSettings
from test_app import fake_generation  # noqa: F401 – das Fixture gilt so auch hier


async def until(condition, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    assert condition()


def marked(user, marker: str) -> list:
    """Alle Elemente mit dieser Markierung, auch ausgeblendete (user.find sieht nur sichtbare)."""
    with user:
        return list(ElementFilter(marker=marker))


def settings_for(tmp_path, **extra) -> SongSettings:
    return SongSettings(output_ordner=str(tmp_path / "out"), seed=None, setup_wizard=False, update_check=False,
                        **{"simple_view": False, **extra})


@pytest_asyncio.fixture
async def user(tmp_path):
    settings_for(tmp_path).save()
    async with user_simulation(root=page.build) as user:
        yield user


@pytest_asyncio.fixture
async def simple_user(tmp_path):
    settings_for(tmp_path, simple_view=True).save()
    async with user_simulation(root=page.build) as user:
        yield user


def fake_duels(monkeypatch, tmp_path):
    """prepare() ohne Rendern: A ist immer die Fassung mit der Funktion."""
    made = []

    def prepare(settings, candidate, folder, seed, number=1, progress=None, rng=None):
        paths = []
        for side in ("A", "B"):
            path = str(tmp_path / f"{number:02d}_{side}.wav")
            sf.write(path, np.zeros((2205, 2), dtype=np.float32), 22050)
            paths.append(path)
        made.append((candidate.field, seed))
        return hoer_duell.Duel(candidate, paths[0], paths[1], True, hoer_duell.on_value(settings, candidate))
    monkeypatch.setattr(hoer_duell, "prepare", prepare)
    return made


async def test_the_duel_asks_blind_and_takes_the_winners(user, tmp_path, monkeypatch):
    made = fake_duels(monkeypatch, tmp_path)
    await user.open("/")
    user.find(marker="duel").click()
    await user.should_see(marker="duel-start")
    user.find(marker="duel-groups").elements.pop().value = ["mix"]
    user.find(marker="duel-count").elements.pop().value = 5
    user.find(marker="duel-start").click()
    for number in range(1, 6):
        await user.should_see(f"Duell {number} von 5", retries=50)
        user.find(marker="duel-b" if number % 2 else "duel-a").click()      # 1, 3, 5: ohne; 2, 4: mit
    await user.should_see(marker="duel-result", retries=50)
    fields = [field for field, _ in made]
    assert len(fields) == 5 and all(hoer_duell.BY_FIELD[f].group == "mix" for f in fields)
    assert len({seed for _, seed in made}) == 1                # alle Duelle mit demselben Song
    user.find(marker="duel-apply").click()
    await until(lambda: not getattr(SongSettings.load(), fields[0]))
    saved = SongSettings.load()
    assert [getattr(saved, f) for f in fields] == [False, True, False, True, False]


async def test_the_duel_can_be_stopped_and_inaudible_switches_hide(user, tmp_path, monkeypatch):
    fake_duels(monkeypatch, tmp_path)
    await user.open("/")
    user.find(marker="duel").click()
    await user.should_see(marker="duel-start")
    user.find(marker="duel-groups").elements.pop().value = ["mix"]
    user.find(marker="duel-start").click()
    await user.should_see("Duell 1 von", retries=50)
    first = hoer_duell.plan(SongSettings(), ["mix"])[0].field
    user.find(marker="duel-gleich").click()
    await user.should_see("Duell 2 von", retries=50)
    user.find(marker="duel-stop").click()
    await user.should_see(marker="duel-result", retries=50)
    user.find(marker="duel-apply").click()
    await until(lambda: hoer_duell.inaudible() == {first} and not getattr(SongSettings.load(), first))
    await until(lambda: all(not e.visible for e in marked(user, f"switch-{first}")))
    assert marked(user, f"switch-{first}")
    marked(user, "switch-tidy_switches")[0].value = False
    await until(lambda: all(e.visible for e in marked(user, f"switch-{first}")))
    assert os.path.exists(hoer_duell.path())


async def test_the_simple_view_shows_only_the_essentials_and_profi_shows_everything(simple_user):
    await simple_user.open("/")
    await simple_user.should_see(marker="simple-generate")
    assert [e.visible for e in marked(simple_user, "tab-Song")] == [False]
    assert [e.visible for e in marked(simple_user, "tab-Verlauf")] == [True]
    marked(simple_user, "view-toggle")[0].value = False
    await until(lambda: marked(simple_user, "tab-Song")[0].visible and not marked(simple_user, "tab-Einfach")[0].visible)
    await until(lambda: not SongSettings.load().simple_view)
    marked(simple_user, "view-toggle")[0].value = True
    await until(lambda: not marked(simple_user, "tab-Song")[0].visible)


async def test_song_machen_takes_quality_and_length_but_keeps_the_switches(simple_user, fake_generation):  # noqa: F811
    await simple_user.open("/")
    await simple_user.should_see(marker="simple-generate")
    marked(simple_user, "simple-quality")[0].value = "Schnell"
    marked(simple_user, "simple-length")[0].value = "Kurz"
    await until(lambda: SongSettings.load().quality == "Schnell")
    assert "langsamen" in marked(simple_user, "simple-quality-hint")[0].text
    simple_user.find(marker="simple-generate").click()
    await until(lambda: len(fake_generation) == 1, 10)
    made = fake_generation[0]
    assert not made.best_melody and not made.hearing_check and made.vocal_takes == 1
    assert made.active_sections == labels.STRUCTURES["Kurz"]
    saved = SongSettings.load()
    assert saved.best_melody and saved.hearing_check           # die Schalter der Profi-Ansicht bleiben
    await until(lambda: laufzeit.typical(einfach.run_kind(saved, "Schnell")) is not None)
    assert einfach.estimate(saved, "Schnell").startswith("zuletzt etwa")


async def test_the_style_brings_its_tempo_and_key(simple_user):
    await simple_user.open("/")
    await simple_user.should_see(marker="simple-style")
    simple_user.find(marker="simple-style").elements.pop().value = "Rock"
    simple_user.find(marker="simple-style").trigger("update:modelValue")        # so heißt das Ereignis intern
    await until(lambda: SongSettings.load().bpm == 130 and SongSettings.load().key == "E")


async def test_the_history_tells_what_is_in_a_song(user, fake_generation, tmp_path):  # noqa: F811
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="tab-Verlauf").click()
    await user.should_see(marker="history-info", retries=80)
    user.find(marker="history-info").click()
    await user.should_see("Was steckt in diesem Song?")
    on = marked(user, "song-info-on")[0].text
    assert "Gesang" in on or "Harmonien" in on or len(on) > 20
    assert marked(user, "song-info-differs") == []
    user.find(marker="song-info-close").click()
    marked(user, "switch-harmonies")[0].value = not SongSettings.load().harmonies
    await until(lambda: SongSettings.load().harmonies != fake_generation[0].harmonies)
    user.find(marker="history-info").click()
    await until(lambda: any("damals" in e.text for e in marked(user, "song-info-differs")))


def test_a_quality_only_turns_slow_things_off_and_never_on():
    s = SongSettings(best_melody=False, vocal_takes=3)
    assert qualitaet.overrides(s, "Beste") == {}                     # drei Fassungen bleiben drei
    fast = qualitaet.apply(SongSettings(), "Schnell")
    assert not fast.best_melody and not fast.hearing_check and fast.vocal_takes == 1
    assert qualitaet.apply(SongSettings(vocal_takes=1), "Beste").vocal_takes == 2
    assert not qualitaet.apply(s, "Beste").best_melody

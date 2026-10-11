# test_app.py – Die neue Oberfläche (NiceGUI), ohne Browser simuliert
import asyncio
import os

import numpy as np
import pretty_midi
import pytest
import pytest_asyncio
import soundfile as sf
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation

import history
import pipeline
import vorlagen
from gui import media, page
from gui.components import PianoRoll, WavePlayer
from pipeline import SongResult
from settings import SongSettings


@pytest_asyncio.fixture
async def user(tmp_path):
    SongSettings(output_ordner=str(tmp_path / "out"), seed=None).save()
    async with user_simulation(root=page.build) as user:
        yield user


def write_song(out: str, seed: int) -> SongResult:
    """Ein winziger fertiger Song: Mix, zwei Spuren, MIDI für die Piano-Roll."""
    os.makedirs(out, exist_ok=True)
    tone = (0.3 * np.sin(np.linspace(0, 440 * 2 * np.pi, 22050))).astype(np.float32)
    for name in ("final_mix", "piano", "drums"):
        sf.write(os.path.join(out, f"{name}.wav"), np.stack([tone, tone], axis=1), 22050)
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(0)
    inst.notes += [pretty_midi.Note(90, 60 + i, i * 0.1, i * 0.1 + 0.1) for i in range(5)]
    midi.instruments.append(inst)
    midi.write(os.path.join(out, "piano.mid"))
    return SongResult(seed=seed, output_dir=out, mix_wav=os.path.join(out, "final_mix.wav"),
                      wav_files={"piano": os.path.join(out, "piano.wav"), "drums": os.path.join(out, "drums.wav")},
                      midi_files={"piano": os.path.join(out, "piano.mid")})


async def until(condition, seconds: float = 5.0) -> None:
    """Wartet, bis die Oberfläche (Timer, Hintergrund-Threads) so weit ist."""
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    assert condition()


@pytest.fixture
def fake_generation(monkeypatch):
    """Ersetzt das echte Erzeugen: jeder Aufruf merkt sich seine Einstellungen und legt einen Song ab."""
    calls = []

    def fake_song(settings, progress=None, seed=None):
        seed = settings.seed if settings.seed is not None else 1000 + len(calls)
        settings = settings.with_updates(seed=seed)
        calls.append(settings)
        for step in ("Komponiere Song...", "Rendere piano...", "Fertig"):
            progress(0.5, step)
        result = write_song(settings.output_dir(), seed)
        result.settings = settings
        entry = history.record(result.audio, settings, settings.output_dir())
        result.history = entry.audio
        return result

    monkeypatch.setattr(pipeline, "generate_song", fake_song)
    return calls


async def test_page_shows_settings_and_waits_for_a_song(user):
    await user.open("/")
    await user.should_see("Noch kein Song")
    await user.should_see(marker="generate")
    await user.should_see("Bereit")


async def test_generating_shows_the_song_and_its_tracks(user, fake_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    await user.should_see(marker="stem-Mix")
    await user.should_see(marker="stem-Klavier")
    [player] = user.find(WavePlayer).elements
    assert player.title == "Mix" and player.url.startswith("/datei?pfad=")
    [roll] = user.find(PianoRoll).elements
    await until(lambda: roll.tracks)       # die Noten liest ein Hintergrund-Thread
    assert roll.tracks[0]["name"] == "Klavier"

    # Der Player bekommt die Datei über die eigene Route
    response = await user.http_client.get(player.url)
    assert response.status_code == 200 and response.content[:4] == b"RIFF"
    assert (await user.http_client.get("/datei?pfad=/etc/passwd")).status_code == 404


async def test_rerolling_keeps_the_seed_and_counts_up(user, fake_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="reroll-melody").click()
    await user.should_see("neu gewürfelt: Melodie 1×", retries=50)
    user.find(marker="reroll-melody").click()
    await user.should_see("Melodie 2×", retries=50)
    assert [c.seed for c in fake_generation] == [1000, 1000, 1000]
    assert fake_generation[-1].variations == {"melody": 2}

    # Ein neuer Song ohne festen Seed fängt wieder bei null an
    user.find(marker="generate").click()
    await user.should_see("Seed 1003", retries=50)
    assert fake_generation[-1].variations == {}


async def test_locked_seed_keeps_song_and_rerolls(user, fake_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="reroll-drums").click()
    await user.should_see("Schlagzeug 1×", retries=50)
    user.find(marker="lock-seed").click()
    user.find(marker="generate").click()
    await until(lambda: len(fake_generation) == 3)
    assert fake_generation[-1].seed == 1000 and fake_generation[-1].variations == {"drums": 1}


async def test_several_versions_land_in_the_history(user, fake_generation):
    await user.open("/")
    user.find(marker="count").elements.pop().value = 3
    user.find(marker="generate").click()
    await user.should_see("Seed 1002", retries=80)
    assert len(fake_generation) == 3
    user.find(marker="tab-Verlauf").click()
    assert len(user.find(marker="history-play").elements) == 3


async def test_restoring_from_history_takes_settings_and_seed(user, fake_generation, tmp_path):
    out = str(tmp_path / "out")
    old = SongSettings(output_ordner=out, bpm=99, style="Rock", seed=77, variations={"bass": 2})
    history.record(write_song(str(tmp_path / "alt"), 77).mix_wav, old, out)
    await user.open("/")
    user.find(marker="tab-Verlauf").click()
    user.find(marker="history-restore").click()
    await user.should_see("99")
    user.find(marker="generate").click()
    await until(lambda: fake_generation)
    assert fake_generation[-1].bpm == 99 and fake_generation[-1].variations == {"bass": 2}


async def test_settings_changes_are_saved(user):
    await user.open("/")
    user.find(marker="bpm").elements.pop().set_value(133)
    await until(lambda: SongSettings.load().bpm == 133)


async def test_lyrics_preview_counts_morae(user):
    await user.open("/")
    user.find(marker="tab-Text").click()
    user.find(marker="lyrics").elements.pop().set_value("[Chorus]\n夜の街")
    await user.should_see("So wird gesungen: 5 Silben")
    await user.should_see("よ る の ま ち")


async def test_templates_keep_sound_but_not_text(user, tmp_path, monkeypatch):
    monkeypatch.setattr(vorlagen, "FOLDER", str(tmp_path / "vorlagen"))
    await user.open("/")
    user.find(marker="bpm").elements.pop().set_value(171)
    user.find(marker="template-name").type("Mein Stil")
    user.find(marker="save-template").click()
    await user.should_see("Vorlage „Mein Stil“ gespeichert")
    assert vorlagen.names() == ["Mein Stil"]
    applied = vorlagen.apply("Mein Stil", SongSettings(bpm=90, lyrics="[Chorus]\nら"))
    assert applied.bpm == 171 and applied.lyrics == "[Chorus]\nら"


async def test_structure_can_be_changed(user):
    await user.open("/")
    user.find("Kurz").click()
    await until(lambda: SongSettings.load().active_sections == ["Intro", "Verse", "PreChorus", "Chorus", "Outro"])


# ── Daten für Player und Piano-Roll ─────────────────────────────────────────────
def test_peaks_are_normalised_and_know_the_duration(tmp_path):
    path = str(tmp_path / "a.wav")
    audio = np.zeros((44100, 2), dtype=np.float32)
    audio[22050:, :] = 0.5
    sf.write(path, audio, 44100)
    peaks, duration = media.peaks(path, count=10)
    assert duration == pytest.approx(1.0)
    assert peaks[:5] == [0.0] * 5 and peaks[-1] == 1.0


def test_piano_roll_has_vocals_first_and_no_drums(tmp_path):
    out = str(tmp_path)
    result = write_song(out, 1)
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(0)
    inst.notes.append(pretty_midi.Note(100, 70, 0.0, 2.5))
    midi.instruments.append(inst)
    midi.write(os.path.join(out, "vocal_melody.mid"))
    drums = pretty_midi.PrettyMIDI()
    kit = pretty_midi.Instrument(0, is_drum=True)
    kit.notes.append(pretty_midi.Note(100, 36, 0.0, 0.1))
    drums.instruments.append(kit)
    drums.write(os.path.join(out, "drums.mid"))
    result.midi_files["drums"] = os.path.join(out, "drums.mid")

    data = media.piano_roll(result)
    assert [t["name"] for t in data["tracks"]] == ["Gesang", "Klavier"]
    assert data["duration"] == 2.5
    assert all(n[2] != 36 for n in data["notes"])


def test_stems_list_mix_first(tmp_path):
    result = write_song(str(tmp_path), 1)
    assert list(media.stems(result)) == ["Mix", "Klavier", "Schlagzeug"]


def test_app_starts_in_the_browser_without_pywebview(monkeypatch):
    import app
    seen = {}
    monkeypatch.setattr(ui, "run", lambda *a, **kw: seen.update(kw))
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda name: None)
    app.main([])
    assert seen["native"] is False and seen["show"] is True and seen["host"] == "127.0.0.1"


async def test_typical_values_of_a_style(user):
    from preset_manager import PRESETS
    await user.open("/")
    user.find(marker="style").elements.pop().set_value("Ballade")
    user.find(marker="typical").click()
    await until(lambda: SongSettings.load().bpm == PRESETS["Ballade"]["bpm"])
    saved = SongSettings.load()
    assert saved.active_sections == PRESETS["Ballade"]["active_sections"]
    assert saved.channels["piano"].volume == PRESETS["Ballade"]["volumes"]["piano"]


async def test_paths_tab_tells_whether_the_extra_soundfonts_are_there(user):
    await user.open("/")
    user.find(marker="tab-Pfade").click()
    await user.should_see("setup_soundfonts.py ausführen")
    user.find(marker="sound-library-switch").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().sound_library is False)

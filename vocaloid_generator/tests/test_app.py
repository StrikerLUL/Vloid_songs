# test_app.py – Die neue Oberfläche (NiceGUI), ohne Browser simuliert
import asyncio
import os
import shutil

import numpy as np
import pretty_midi
import pytest
import pytest_asyncio
import soundfile as sf
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation

import history
import karaoke
import pipeline
import vorlagen
from gui import media, page
from gui.components import Karaoke, PianoRoll, WavePlayer
from pipeline import SongResult
from settings import SongSettings, edit_key


@pytest_asyncio.fixture
async def user(tmp_path):
    SongSettings(output_ordner=str(tmp_path / "out"), seed=None, setup_wizard=False, update_check=False).save()
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

    def fake_song(settings, progress=None, seed=None, keep_history=True):
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


@pytest.fixture
def sung_generation(fake_generation, monkeypatch):
    """Wie fake_generation, aber der Song hat Gesang: eine Gesangsmelodie und den Text zum Mitlesen."""
    fake_song = pipeline.generate_song

    def sung_song(settings, progress=None, seed=None, keep_history=True):
        result = fake_song(settings, progress, seed)
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(0)
        inst.notes += [pretty_midi.Note(100, 64 + i, 0.5 * i, 0.5 * i + 0.4) for i in range(4)]
        midi.instruments.append(inst)
        midi.write(os.path.join(result.output_dir, "vocal_melody.mid"))
        karaoke.save(os.path.join(result.output_dir, karaoke.FILE),
                     [{"start": 0.0, "end": 0.9, "syllables": [[0.0, 0.4, "よ"], [0.5, 0.9, "る"]]},
                      {"start": 1.0, "end": 1.9, "syllables": [[1.0, 1.4, "の"], [1.5, 1.9, "ま"]]}])
        return result

    monkeypatch.setattr(pipeline, "generate_song", sung_song)
    return fake_generation


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
    await until(lambda: player.title == "Mix")          # die Wellenform lädt erst nach den Knöpfen
    assert player.url.startswith("/datei?pfad=")
    [roll] = user.find(PianoRoll).elements
    await until(lambda: roll.tracks)       # die Noten liest ein Hintergrund-Thread
    assert roll.tracks[0]["name"] == "Klavier"

    # Der Player bekommt die Datei über die eigene Route
    response = await user.http_client.get(player.url)
    assert response.status_code == 200 and response.content[:4] == b"RIFF"
    assert (await user.http_client.get("/datei?pfad=/etc/passwd")).status_code == 404


async def test_draft_first_then_the_real_song_with_the_same_seed(user, fake_generation):
    await user.open("/")
    user.find(marker="count").elements.pop().value = 3
    user.find(marker="draft").click()
    await user.should_see("Entwurf · ", retries=50)
    [sketch] = fake_generation                                        # ein Entwurf, nicht drei
    assert sketch.draft and not sketch.channels["vocals"].enabled
    assert sketch.output_ordner.endswith(pipeline.DRAFT_FOLDER)
    [full] = user.find(marker="draft-full").elements
    assert full.visible
    user.find(marker="draft-full").click()
    await until(lambda: len(fake_generation) == 2)
    real = fake_generation[-1]
    assert real.seed == sketch.seed and not real.draft and real.channels["vocals"].enabled
    await until(lambda: not full.visible)
    assert not SongSettings.load().draft


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
    await user.should_see(marker="history-play", retries=80)      # der Verlauf baut sich nach dem Song auf
    await until(lambda: len(user.find(marker="history-play").elements) == 3)


async def test_the_best_rated_version_is_loaded(user, fake_generation, monkeypatch):
    import rating
    notes = iter([4.0, 8.0, 6.0])
    monkeypatch.setattr(rating, "available", lambda: True)
    monkeypatch.setattr(rating, "rate", lambda paths: [rating.Rating(n, 5.0, 5.0, n) for n, _ in zip(notes, paths)])
    await user.open("/")
    user.find(marker="count").elements.pop().value = 3
    user.find(marker="generate").click()
    await user.should_see("Geladen ist die beste: Note 8.0", retries=80)
    await user.should_see("Seed 1001")
    user.find(marker="tab-Verlauf").click()
    assert sorted(b.text for b in user.find(marker="history-rating").elements) == ["4.0", "6.0", "8.0"]


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


async def test_library_names_finds_and_deletes_songs(user, tmp_path):
    out = str(tmp_path / "out")
    history.record(write_song(str(tmp_path / "a"), 11).mix_wav, SongSettings(style="Rock", seed=11), out)
    history.record(write_song(str(tmp_path / "b"), 4711).mix_wav, SongSettings(style="Ballade", seed=4711), out)
    await user.open("/")
    user.find(marker="tab-Verlauf").click()
    await until(lambda: len(user.find(marker="history-play").elements) == 2)

    user.find(marker="library-search").type("rock")
    await until(lambda: len(user.find(marker="history-play").elements) == 1)
    user.find(marker="history-edit").click()
    user.find(marker="edit-name").type("Sommerregen")
    user.find(marker="edit-note").type("Bridge kürzer")
    user.find(marker="edit-save").click()
    await user.should_see("Sommerregen")
    await user.should_see("Bridge kürzer")
    assert [e.label for e in history.entries(out) if e.settings.seed == 11] == ["Sommerregen"]

    user.find(marker="library-search").clear()
    user.find(marker="library-search").type("4711")
    await until(lambda: len(user.find(marker="history-play").elements) == 1)
    user.find(marker="history-delete").click()
    user.find(marker="delete-keep").click()
    assert len(history.entries(out)) == 2
    user.find(marker="history-delete").click()
    user.find(marker="delete-confirm").click()
    await user.should_see(marker="library-empty")
    assert [e.settings.seed for e in history.entries(out)] == [11]


async def test_album_overnight_from_the_app(user, fake_generation, tmp_path):
    await user.open("/")
    user.find(marker="album").click()
    user.find(marker="album-count").elements.pop().set_value(3)
    user.find(marker="album-styles").elements.pop().set_value(["Rock", "Ballade"])
    user.find(marker="album-name").type("Probe")
    user.find(marker="album-start").click()
    await until(lambda: len(fake_generation) == 3, seconds=10)
    assert [c.style for c in fake_generation] == ["Rock", "Ballade", "Rock"]
    await until(lambda: user.find(marker="library-search").elements.pop().value == "Probe")
    out = str(tmp_path / "out")
    [folder] = os.listdir(os.path.join(out, "Alben"))
    assert folder.endswith("Probe") and len(os.listdir(os.path.join(out, "Alben", folder))) == 3 + 2
    assert all(e.album == "Probe" for e in history.entries(out))
    await until(lambda: len(user.find(marker="history-play").elements) == 3)


async def test_youtube_folder_from_the_app_uses_the_song_name(user, fake_generation, monkeypatch, tmp_path):
    import youtube
    made, opened = [], []
    monkeypatch.setattr(youtube, "make", lambda result, label="", progress=None: made.append((result.seed, label))
                        or youtube.Package(str(tmp_path), label))
    monkeypatch.setattr(media, "open_folder", lambda path: opened.append(path) or True)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    history.set_details(history.entries(str(tmp_path / "out"))[0], label="Sommerregen")
    user.find(marker="youtube").click()
    await until(lambda: opened)
    assert made == [(1000, "Sommerregen")] and opened == [str(tmp_path)]


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
    await user.should_see("setup_samples.py ausführen")
    user.find(marker="sound-library-switch").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().sound_library is False)
    user.find(marker="samples-switch").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().samples is False)
    await user.should_see("setup_bewertung.py ausführen")
    user.find(marker="rating-switch").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().auto_rating is False)
    await user.should_see("setup_ace_step.py ausführen")
    user.find(marker="polish-switch").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().polish is False)


async def test_the_polished_version_can_be_played_and_tuned(user, fake_generation, monkeypatch):
    fake_song = pipeline.generate_song

    def polished_song(settings, progress=None, seed=None, keep_history=True):
        result = fake_song(settings, progress, seed)
        result.polished_wav = os.path.join(result.output_dir, "final_mix_veredelt.wav")
        shutil.copy(result.mix_wav, result.polished_wav)
        return result
    monkeypatch.setattr(pipeline, "generate_song", polished_song)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see(marker="stem-Veredelt", retries=50)
    user.find(marker="tab-Mix").click()
    user.find(marker="polish-strength").elements.pop().set_value(0.7)
    user.find(marker="polish-caption").elements.pop().set_value("dream pop")
    await until(lambda: (SongSettings.load().polish_strength, SongSettings.load().polish_caption) == (0.7, "dream pop"))


async def test_movement_in_the_mix_can_be_switched_off(user):
    await user.open("/")
    user.find(marker="tab-Mix").click()
    user.find(marker="switch-mix_movement").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().mix_movement is False)


async def test_melody_motifs_can_be_switched_and_say_what_they_learned(user):
    await user.open("/")
    await user.should_see("Gelernte Motive: keine MIDI-Dateien")
    user.find(marker="more-motifs").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().more_motifs is False)
    user.find(marker="learned-motifs").elements.pop().set_value(False)
    await user.should_see("Gelernte Motive: aus")
    await until(lambda: SongSettings.load().learned_motifs is False)


async def test_references_from_the_library_suggest_tempo_key_and_style(user, monkeypatch):
    import reference
    os.makedirs(reference.LIBRARY)
    path = os.path.join(reference.LIBRARY, "lieblingssong.wav")
    sf.write(path, np.zeros((22050, 2), dtype=np.float32), 22050)
    summary = reference.Summary(bpm=172, key="D", scale="minor", style="Dark Vocaloid", contrast_db=4.0,
                                vocal_db=-3.0, names=["lieblingssong.wav"])
    monkeypatch.setattr(reference, "summarize", lambda refs, styles=None: summary if reference.active(refs) else None)
    await user.open("/")
    user.find(marker="reference-library").elements.pop().set_value(path)
    await until(lambda: [r.path for r in SongSettings.load().reference_tracks] == [path])
    await user.should_see("Vorbilder: 172 BPM, D Moll, klingt nach Dark Vocaloid", retries=50)
    user.find(marker="reference-take-tempo").click()
    user.find(marker="reference-take-style").click()
    await until(lambda: (SongSettings.load().bpm, SongSettings.load().style) == (172, "Dark Vocaloid"))
    assert (SongSettings.load().key, SongSettings.load().scale) == ("D", "minor")


async def test_reference_suggestions_can_be_switched_off(user, monkeypatch):
    import reference
    summary = reference.Summary(bpm=172, key="D", scale="minor", style="Dark Vocaloid", contrast_db=4.0,
                                vocal_db=-3.0, names=["a.wav"])
    monkeypatch.setattr(reference, "summarize", lambda refs, styles=None: summary)
    monkeypatch.setattr(reference, "active", lambda refs: [("a.wav", 1.0)])
    await user.open("/")
    await user.should_see(marker="reference-take-tempo")
    user.find(marker="switch-ref_tempo_key").elements.pop().set_value(False)
    await user.should_not_see(marker="reference-take-tempo")
    await until(lambda: SongSettings.load().ref_tempo_key is False)
    await user.should_see("Demucs fehlt")
    user.find(marker="switch-ref_stems").elements.pop().set_value(False)
    await until(lambda: SongSettings.load().ref_stems is False)


async def test_lively_singing_can_be_switched_and_voicevox_singers_are_listed(user, monkeypatch):
    import voicevox
    monkeypatch.setattr(voicevox, "singers", lambda url=None, timeout=None: {3002: "四国めたん (ノーマル)"})
    await user.open("/")
    await user.should_see("VOICEVOX läuft, 1 Singstimmen.", retries=50)   # Timer, dann ein Thread
    select = user.find(marker="voicevox-singer").elements.pop()
    assert select.options[3002] == "四国めたん (ノーマル)"
    select.set_value(3002)
    user.find(marker="switch-final_choir").elements.pop().set_value(False)
    user.find(marker="slider-vibrato").elements.pop().set_value(0.4)
    await until(lambda: (SongSettings.load().voicevox_singer, SongSettings.load().final_choir,
                         SongSettings.load().vibrato) == (3002, False, 0.4))


async def test_without_voicevox_the_app_says_how_to_get_it(user):
    await user.open("/")
    await user.should_see("VOICEVOX läuft nicht. Kostenlos unter voicevox.hiroshiba.jp; App starten, dann neu laden.",
                          retries=50)


async def test_sound_switches_and_a_vst_sound_per_part(user, monkeypatch, tmp_path):
    import vst_sounds
    plugin = tmp_path / "Surge XT.vst3"
    plugin.mkdir()
    monkeypatch.setattr(vst_sounds, "_surge_candidates", lambda: (str(plugin),))
    monkeypatch.setattr(vst_sounds, "choose", lambda path, state="": "QUJD" if path == str(plugin) else None)
    await user.open("/")
    user.find(marker="switch-guitar_amp").elements.pop().set_value(False)
    user.find(marker="style-drums").elements.pop().set_value("909")
    await until(lambda: (SongSettings.load().guitar_amp, SongSettings.load().channels["drums"].style) == (False, "909"))
    assert not user.find(marker="vst-choose-bass").elements.pop().enabled
    user.find(marker="use-surge").click()
    await until(lambda: SongSettings.load().vst_path == str(plugin))
    user.find(marker="vst-choose-bass").click()
    await until(lambda: SongSettings.load().vst_sounds == {"bass": "QUJD"})
    assert user.find(marker="vst-status-bass").elements.pop().text == "eigener Klang"
    user.find(marker="vst-forget-bass").click()
    await until(lambda: SongSettings.load().vst_sounds == {})


async def test_rerolling_only_in_one_section(user, fake_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="reroll-where").elements.pop().set_value("Chorus")
    user.find(marker="reroll-melody").click()
    await user.should_see("Melodie (Refrain) 1×", retries=50)
    assert fake_generation[-1].seed == 1000 and fake_generation[-1].variations == {"melody:Chorus": 1}

    # Eine Sektion, die der Song nicht hat, würfelt nichts
    user.find(marker="reroll-where").elements.pop().set_value("Solo")
    user.find(marker="reroll-drums").click()
    await user.should_see("keine Sektion Solo", retries=20)
    assert len(fake_generation) == 2


async def test_choosing_one_of_three_chorus_melodies(user, fake_generation, monkeypatch, tmp_path):
    asked = []

    def fake_hooks(settings, count=3, progress=None):
        asked.append(settings)
        choices = []
        for n in range(1, count + 1):
            preview = tmp_path / f"refrain{n}.wav"
            sf.write(str(preview), np.zeros((2205, 2), dtype=np.float32), 22050)
            choices.append(pipeline.HookChoice(n, settings.with_updates(seed=55, variations={"melody:Chorus": n}),
                                               str(preview)))
        return choices

    monkeypatch.setattr(pipeline, "hook_choices", fake_hooks)
    await user.open("/")
    user.find(marker="hooks").click()
    await user.should_see(marker="hook-take-3", retries=50)
    [player] = user.find(WavePlayer).elements
    await until(lambda: player.title == "Refrain 1")     # die Wellenform lädt erst nach den Knöpfen
    user.find(marker="hook-play-2").click()
    await until(lambda: player.title == "Refrain 2")
    user.find(marker="hook-take-2").click()
    await until(lambda: len(fake_generation) == 1)
    assert fake_generation[0].seed == 55 and fake_generation[0].variations == {"melody:Chorus": 2}
    await user.should_see("Melodie (Refrain) 2×", retries=50)


async def test_hooks_that_cannot_be_made_explain_why(user, monkeypatch):
    def refuse(settings, count=3, progress=None):
        raise ValueError("Im Chorus singt deine eigene MIDI-Melodie")

    monkeypatch.setattr(pipeline, "hook_choices", refuse)
    await user.open("/")
    user.find(marker="hooks").click()
    await user.should_see("eigene MIDI-Melodie", retries=50)


async def test_own_chords_and_melody_are_saved(user):
    await user.open("/")
    user.find(marker="chords-Chorus").type("F G Em Am")
    user.find(marker="chords-Verse").type("vi IV I V")
    await until(lambda: SongSettings.load().custom_chords == {"Chorus": "F G Em Am", "Verse": "vi IV I V"})
    user.find(marker="chords-Chorus").clear()
    await until(lambda: SongSettings.load().custom_chords == {"Verse": "vi IV I V"})
    user.find(marker="chords-Bridge").type("F Fxyz")
    await user.should_see("Unbekannter Akkord: Fxyz", retries=20)
    user.find(marker="melody-midi").type("C:/melodie.mid")
    user.find(marker="melody-section").elements.pop().set_value("Verse")
    await until(lambda: (SongSettings.load().melody_midi, SongSettings.load().melody_midi_section)
                == ("C:/melodie.mid", "Verse"))


# ── Bedienung: Mitlesen, Lyric-Video, Vergleich, Ablauf, Töne ändern ──────────────
async def test_lyrics_to_read_along_and_the_switch_to_hide_them(user, sung_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    [view] = user.find(Karaoke).elements
    await until(lambda: view.lines)         # den Text liest ein Hintergrund-Thread
    assert [karaoke.text(line) for line in view.lines] == ["よる", "のま"]
    assert view.visible
    user.find(marker="switch-karaoke").click()
    await until(lambda: not view.visible)
    await until(lambda: SongSettings.load().show_karaoke is False)


async def test_lyric_video_is_made_for_the_current_song(user, fake_generation, monkeypatch, tmp_path):
    made = []

    def fake_video(result, path=None):
        made.append(result.seed)
        path = str(tmp_path / "lyric_video.mp4")
        open(path, "wb").close()
        return path

    monkeypatch.setattr(pipeline, "lyric_video", fake_video)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    user.find(marker="video").click()
    await user.should_see("Lyric-Video gespeichert", retries=50)
    assert made == [1000]

    def no_ffmpeg(result, path=None):
        raise RuntimeError("Für das Lyric-Video fehlt ffmpeg")

    monkeypatch.setattr(pipeline, "lyric_video", no_ffmpeg)
    user.find(marker="video").click()
    await user.should_see("fehlt ffmpeg", retries=50)


async def test_two_songs_from_the_history_can_be_compared(user, fake_generation):
    await user.open("/")
    user.find(marker="count").elements.pop().value = 2
    user.find(marker="generate").click()
    await user.should_see("Seed 1001", retries=80)
    user.find(marker="tab-Verlauf").click()
    await user.should_see(marker="history-A-1", retries=50)     # der Verlauf baut sich nach dem Song neu auf
    user.find(marker="history-A-1").click()
    user.find(marker="history-B-2").click()
    await user.should_see(marker="compare-B")
    [player] = user.find(WavePlayer).elements
    user.find(marker="compare-B").click()
    await until(lambda: player.title.startswith("B · "))
    user.find(marker="compare-A").click()
    await until(lambda: player.title.startswith("A · "))
    user.find(marker="compare-close").click()
    await user.should_not_see(marker="compare-A")


async def test_sections_can_be_dragged_and_their_length_chosen(user):
    await user.open("/")
    before = SongSettings.load().active_sections
    user.find(marker="section-0").trigger("dragstart")
    user.find(marker="section-2").trigger("drop")
    await until(lambda: SongSettings.load().active_sections == before[1:3] + before[:1] + before[3:])
    user.find(marker="bars-Chorus-8").click()
    await until(lambda: SongSettings.load().section_bars == {"Chorus": 8})
    await user.should_see("Refrain · 8")
    user.find(marker="bars-Chorus-16").click()      # die Standardlänge braucht keinen Eintrag
    await until(lambda: SongSettings.load().section_bars == {})


async def test_sung_notes_can_be_moved_and_sung_again(user, sung_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    [roll] = user.find(PianoRoll).elements
    await until(lambda: roll.tracks)
    assert roll.tracks[0]["key"] == "vocals"
    user.find(marker="edit-melody").click()
    await until(lambda: roll.editable)

    # Der zweite Ton (0,5 s) geht von 65 auf 67
    user.find(PianoRoll).trigger("edit", {"start": 0.5, "pitch": 67})
    await user.should_see("1 Ton geändert")
    assert [n[2] for n in roll.notes if n[3] == 0] == [64, 67, 66, 67]
    beat = edit_key(0.5 * SongSettings.load().bpm / 60)
    await until(lambda: SongSettings.load().melody_edits == {beat: 67})

    # Neu singen: derselbe Song mit dem geänderten Ton
    user.find(marker="resing").click()
    await until(lambda: len(sung_generation) == 2)
    assert sung_generation[-1].seed == 1000 and sung_generation[-1].melody_edits == {beat: 67}
    await user.should_see("Seed 1000 · 1 Ton geändert", retries=50)

    # Verwerfen: die Töne stehen wieder wie gesungen
    user.find(marker="drop-edits").click()
    await until(lambda: SongSettings.load().melody_edits == {})
    await until(lambda: [n[2] for n in roll.notes if n[3] == 0] == [64, 65, 66, 67])


async def test_sung_notes_can_be_made_longer_and_heard_at_once(user, sung_generation):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    [roll] = user.find(PianoRoll).elements
    await until(lambda: roll.tracks)
    user.find(marker="edit-melody").click()
    await until(lambda: roll.editable)

    # Der dritte Ton (1,0 s) wird länger, der zweite höher: zwei geänderte Töne
    user.find(PianoRoll).trigger("resize", {"start": 1.0, "end": 1.45})
    await user.should_see("1 Ton geändert")
    assert [n[1] for n in roll.notes if n[3] == 0] == [0.4, 0.9, 1.45, 1.9]
    user.find(PianoRoll).trigger("edit", {"start": 0.5, "pitch": 67})
    await user.should_see("2 Töne geändert")
    bpm = SongSettings.load().bpm
    beats = min(max(round(0.45 * bpm / 60 * 4) / 4, 0.25), 16)
    await until(lambda: SongSettings.load().melody_lengths == {edit_key(1.0 * bpm / 60): beats})

    # Vorschau: Synth über der Band, ohne neu zu singen
    out = SongSettings.load().output_dir()
    user.find(marker="preview-edits").click()
    await until(lambda: os.path.exists(os.path.join(out, "vorschau_aenderungen.wav")), seconds=20)
    assert len(sung_generation) == 1

    # Neu singen nimmt beides mit, Verwerfen setzt beides zurück
    user.find(marker="resing").click()
    await until(lambda: len(sung_generation) == 2)
    assert sung_generation[-1].melody_lengths == {edit_key(1.0 * bpm / 60): beats}
    await user.should_see("Seed 1000 · 2 Töne geändert", retries=50)
    user.find(marker="drop-edits").click()
    await until(lambda: (SongSettings.load().melody_edits, SongSettings.load().melody_lengths) == ({}, {}))


async def test_a_hummed_melody_becomes_the_own_melody(user, monkeypatch):
    # Das Erkennen selbst prüft test_humming.py; hier zählt, was die Oberfläche daraus macht
    import humming
    from nicegui.elements.upload_files import SmallFileUpload
    heard = []

    def transcribe(path, bpm, target):
        heard.append((os.path.basename(path), bpm))
        with open(path, "rb") as f:
            if not f.read().startswith(b"summ"):
                return None
        open(target, "wb").close()
        return 7
    monkeypatch.setattr(humming, "transcribe", transcribe)
    SongSettings.load().with_updates(bpm=100).save()
    await user.open("/")
    [upload] = user.find(marker="hum-upload").elements
    await upload.handle_uploads([SmallFileUpload("idee.wav", "audio/wav", b"summ summ")])
    await user.should_see("Gesummte Melodie: 7 Töne", retries=100)
    out = SongSettings.load().output_dir()
    await until(lambda: SongSettings.load().melody_midi == os.path.join(out, "summen", "idee.mid"))
    assert heard == [("idee.wav", 100)]
    await upload.handle_uploads([SmallFileUpload("kaputt.wav", "audio/wav", b"RIFF kaputt")])
    await user.should_see("keine Melodie zu hören", retries=100)
    assert SongSettings.load().melody_midi == os.path.join(out, "summen", "idee.mid")


# ── Abbrechen, Weitermachen, Hilfe-Menü, Einrichten, Updates ─────────────────────
async def test_stop_cancels_a_running_song(user, monkeypatch):
    import time

    import cancel
    started = []

    def slow_song(settings, progress=None, seed=None, keep_history=True):
        started.append(settings)
        progress(0.3, "Rendere Instrumente...")
        for _ in range(400):
            cancel.check()
            time.sleep(0.05)
        raise AssertionError("nicht abgebrochen")
    monkeypatch.setattr(pipeline, "generate_song", slow_song)
    await user.open("/")
    user.find(marker="generate").click()
    await until(lambda: started)
    [stop] = user.find(marker="stop").elements
    await until(lambda: stop.visible)
    user.find(marker="stop").click()
    await user.should_see("Abgebrochen", retries=100)
    await until(lambda: not stop.visible)
    assert not cancel.requested()               # der nächste Song startet wieder normal


async def test_unfinished_song_can_be_continued(user, fake_generation, tmp_path):
    import resume
    resume.start(SongSettings(seed=77, bpm=99, style="Rock", output_ordner="woanders"))
    await user.open("/")
    await user.should_see(marker="resume")
    await user.should_see("nicht fertig geworden")
    user.find(marker="resume-continue").click()
    await until(lambda: fake_generation)
    assert fake_generation[-1].seed == 77 and fake_generation[-1].bpm == 99
    assert fake_generation[-1].output_ordner == str(tmp_path / "out")      # die Pfade dieses Rechners bleiben
    resume.finish()


async def test_unfinished_song_can_be_dropped(user):
    import resume
    resume.start(SongSettings(seed=78))
    await user.open("/")
    user.find(marker="resume-drop").click()
    await until(lambda: resume.pending() is None)
    await user.should_not_see(marker="resume")


async def test_help_menu_opens_the_system_check(user, monkeypatch):
    import systemcheck
    monkeypatch.setattr(systemcheck, "CHECKS", ())
    systemcheck.register("a", "Probe", lambda s, folder: (True, "klappt"))
    await user.open("/")
    user.find(marker="help-menu").click()
    user.find(marker="menu-check").click()
    await user.should_see(marker="check-run")
    user.find(marker="check-run").click()
    await user.should_see("Alles läuft", retries=100)
    await user.should_see("klappt")


async def test_help_menu_shows_credits_and_news(user):
    await user.open("/")
    user.find(marker="help-menu").click()
    user.find(marker="menu-news").click()
    await user.should_see(marker="whats-new")
    user.find(marker="help-menu").click()
    user.find(marker="menu-credits").click()
    await user.should_see(marker="page-CREDITS.md")
    user.find(marker="help-menu").click()
    user.find(marker="menu-guide").click()
    await user.should_see(marker="page-ANLEITUNG.md")
    user.find(marker="help-menu").click()
    user.find(marker="menu-help").click()
    await user.should_see(marker="page-FEHLERBEHEBUNG.md")


async def test_setup_wizard_shows_on_start_and_installs(user, monkeypatch):
    import einrichten
    monkeypatch.setattr(einrichten, "COMPONENTS", ())
    einrichten.register(einrichten.Component("klang", "Klänge", "besser", "1 MB", "setup_klang.py", lambda: False))
    einrichten.register(einrichten.Component("da", "Schon da", "da", "1 MB", "setup_da.py", lambda: True))
    asked = []

    def install(keys, say=print, progress=None):
        asked.append(keys)
        say("lade Klänge")
        return {k: True for k in keys}
    monkeypatch.setattr(einrichten, "install", install)
    SongSettings.load().with_updates(setup_wizard=True).save()
    await user.open("/")
    await user.should_see(marker="wizard-install")
    await user.should_see(marker="wizard-have-da")
    user.find(marker="wizard-install").click()
    await user.should_see("Alles eingerichtet.", retries=100)
    assert asked == [["klang"]]
    user.find(marker="wizard-done").click()
    await until(einrichten.wizard_done)


async def test_update_button_appears_when_there_is_a_new_version(user, monkeypatch):
    import updates
    monkeypatch.setattr(updates, "available", lambda force=False: updates.Release("v9.9.9", "- neu", "", "x"))
    monkeypatch.setattr(updates, "latest", lambda force=False: updates.Release("v9.9.9", "- neu", "", "x"))
    monkeypatch.setattr(updates, "unseen_changes", lambda: "")
    SongSettings.load().with_updates(update_check=True).save()
    await user.open("/")
    await user.should_see("Update v9.9.9", retries=150)
    user.find(marker="update-available").click()
    await user.should_see("Neue Version v9.9.9", retries=50)
    await user.should_see(marker="update-get")

"""Accessible phrase repair shares the page's asynchronous job and cancellation controls."""
import threading
from types import SimpleNamespace

import pytest

import cancel
import pipeline
from gui import media, page
from gui.components import PianoRoll
from settings import edit_key
from test_app import fake_generation, until, user, write_song  # noqa: F401
from test_app_160 import marked, simple_user  # noqa: F401


@pytest.fixture
def phrases(monkeypatch):
    found = [SimpleNamespace(index=0, start=0.0, end=0.8, section="Verse", text="First line"),
             SimpleNamespace(index=1, start=1.0, end=1.8, section="Chorus", text="Second line")]
    monkeypatch.setattr(pipeline, "list_vocal_phrases", lambda result: found)
    return found


async def generate(user):
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=80)
    await until(lambda: marked(user, "repair-phrase-start")[0].enabled)


async def test_repair_is_disabled_without_a_song_and_available_in_both_views(simple_user):
    await simple_user.open("/")
    await simple_user.should_see(marker="phrase-repair-card")
    assert not marked(simple_user, "repair-phrase-start")[0].enabled
    marked(simple_user, "view-toggle")[0].value = False
    await simple_user.should_see(marker="phrase-repair-card")
    assert not marked(simple_user, "repair-phrase-start")[0].enabled


async def test_phrase_list_and_repair_preserve_source_settings(user, fake_generation, phrases, monkeypatch, tmp_path):
    calls = []

    def repair(settings, result, index, progress):
        calls.append((settings, result, index))
        progress(0.5, "Repariere Phrase")
        repaired = write_song(str(tmp_path / "repaired"), result.seed)
        repaired.settings = settings
        return repaired

    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    select = marked(user, "repair-phrase")[0]
    assert "Second line" in select.options[1] and "Refrain" in select.options[1]
    select.value = 1
    marked(user, "repair-shift")[0].value = 3
    # Unrelated unsaved composition changes must not change the song being repaired.
    marked(user, "bpm")[0].value = 220
    user.find(marker="repair-phrase-start").click()
    await until(lambda: len(calls) == 1 and marked(user, "repair-phrase-start")[0].enabled)
    settings, original, index = calls[0]
    assert index == 1 and settings.bpm == original.settings.bpm
    assert settings.phrase_fixes[edit_key(settings.bpm / 60)]["style_shift"] == 3
    assert not original.settings.phrase_fixes
    assert len(fake_generation) == 1
    assert "repaired" in marked(user, "player")[0].url


@pytest.mark.parametrize("failure", [ValueError("Unsupported source"), cancel.Cancelled()])
async def test_failed_or_cancelled_repair_keeps_player_and_restores_controls(
        user, fake_generation, phrases, monkeypatch, failure):
    def repair(*args):
        raise failure

    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    player = marked(user, "player")[0]
    await until(lambda: bool(player.url))
    before = player.url
    user.find(marker="repair-phrase-start").click()
    await user.should_see("Phrase konnte nicht repariert werden" if isinstance(failure, ValueError)
                          else "Reparatur abgebrochen", retries=80)
    assert player.url == before
    assert marked(user, "generate")[0].enabled
    assert marked(user, "repair-phrase-start")[0].enabled


async def test_repair_runs_off_ui_thread_and_uses_shared_cancel(user, fake_generation, phrases, monkeypatch):
    started, finish = threading.Event(), threading.Event()
    ui_thread = threading.get_ident()

    def repair(*args):
        assert threading.get_ident() != ui_thread
        started.set()
        assert finish.wait(5)
        cancel.check()

    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    user.find(marker="repair-phrase-start").click()
    try:
        await until(started.is_set)
        for marker in ("generate", "repair-phrase", "repair-voice", "repair-shift", "repair-phrase-start"):
            assert not marked(user, marker)[0].enabled
        user.find(marker="stop").click()
    finally:
        finish.set()
    await user.should_see("Reparatur abgebrochen", retries=80)
    assert marked(user, "generate")[0].enabled


async def test_no_phrases_explains_unavailable_repair(user, fake_generation, monkeypatch):
    monkeypatch.setattr(pipeline, "list_vocal_phrases", lambda result: [])
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("keine reparierbaren Gesangsphrasen", retries=80)
    assert not marked(user, "repair-phrase-start")[0].enabled


async def test_other_engines_can_retry_without_neutrino_overrides(user, fake_generation, phrases, monkeypatch):
    calls = []
    original_generate = pipeline.generate_song

    def voicevox(settings, *args, **kwargs):
        return original_generate(settings.with_updates(vocal_engine="VOICEVOX"), *args, **kwargs)

    def repair(settings, result, index, progress):
        calls.append(settings)
        return result

    monkeypatch.setattr(pipeline, "generate_song", voicevox)
    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    assert not marked(user, "repair-voice")[0].enabled
    assert not marked(user, "repair-shift")[0].enabled
    user.find(marker="repair-phrase-start").click()
    await until(lambda: calls and marked(user, "repair-phrase-start")[0].enabled)
    assert not calls[0].phrase_fixes
    assert calls[0].vocal_engine == "VOICEVOX"


async def test_clearing_selection_disables_repair(user, fake_generation, phrases):
    await generate(user)
    marked(user, "repair-phrase")[0].value = None
    assert not marked(user, "repair-phrase-start")[0].enabled


async def test_existing_mid_phrase_override_is_shown_and_normalized(user, fake_generation, phrases, monkeypatch):
    calls = []
    original_generate = pipeline.generate_song

    def fixed(settings, *args, **kwargs):
        key = edit_key(0.3 * settings.bpm / 60)
        return original_generate(settings.with_updates(phrase_fixes={key: {"style_shift": -2}}), *args, **kwargs)

    def repair(settings, result, index, progress):
        calls.append(settings)
        return result

    monkeypatch.setattr(pipeline, "generate_song", fixed)
    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    assert marked(user, "repair-shift")[0].value == -2
    marked(user, "repair-shift")[0].value = 4
    user.find(marker="repair-phrase-start").click()
    await until(lambda: calls)
    assert list(calls[0].phrase_fixes) == [edit_key(0)]
    assert calls[0].phrase_fixes[edit_key(0)]["style_shift"] == 4


@pytest.mark.parametrize("restriction", ["draft", "own_vocal", "duet_singer", "group_vocals", "rap"])
async def test_unsupported_sources_explain_why_repair_is_disabled(
        user, fake_generation, phrases, monkeypatch, restriction):
    original_generate = pipeline.generate_song

    def restricted(settings, *args, **kwargs):
        overrides = {restriction: "another" if restriction in ("own_vocal", "duet_singer") else True}
        if restriction == "rap":
            phrases[0].section = "Rap"
            overrides = {}
        return original_generate(settings.with_updates(**overrides), *args, **kwargs)

    monkeypatch.setattr(pipeline, "generate_song", restricted)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("sind ausgeschlossen", retries=80)
    assert not marked(user, "repair-phrase-start")[0].enabled


async def test_phrase_listing_error_does_not_break_playback(user, fake_generation, monkeypatch):
    def broken(result):
        raise OSError("Missing phrase metadata")

    monkeypatch.setattr(pipeline, "list_vocal_phrases", broken)
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Der Song kann weiter angehört werden", retries=80)
    await until(lambda: bool(marked(user, "player")[0].url))
    assert marked(user, "generate")[0].enabled


async def test_piano_roll_dialog_repairs_with_source_voice(user, fake_generation, phrases, monkeypatch):
    calls = []
    monkeypatch.setattr(media, "phrase_at", lambda result, start: (1.0, 1.8))
    monkeypatch.setattr(page, "_singers", lambda settings: [settings.singer, "Other"])

    def repair(settings, result, index, progress):
        calls.append((settings, index))
        return result

    monkeypatch.setattr(pipeline, "repair_vocal_phrase", repair)
    await generate(user)
    original_voice = fake_generation[0].singer
    marked(user, "singer")[0].value = "Other"
    user.find(PianoRoll).trigger("phrase", {"start": 1.0})
    await user.should_see(marker="phrase-sing")
    assert marked(user, "phrase-singer")[0].value == original_voice
    marked(user, "phrase-shift")[0].value = 2
    user.find(marker="phrase-sing").click()
    await until(lambda: calls)
    assert calls[0][1] == 1
    assert calls[0][0].phrase_fixes[edit_key(calls[0][0].bpm / 60)]["style_shift"] == 2
    assert len(fake_generation) == 1

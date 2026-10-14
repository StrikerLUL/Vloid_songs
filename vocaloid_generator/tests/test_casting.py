# test_casting.py – Stimmen-Casting (casting.py), Gesangs-Check (vocal_check.py) und die NEUTRINO-Ausgabe
import asyncio
import json
import os

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf
from nicegui.testing.user_simulation import user_simulation

import casting
import main
import pipeline
import vocal_check
import vocal_synthesizer
from settings import SongSettings


@pytest.fixture
def voices(tmp_path, monkeypatch):
    """NEUTRINO mit drei Stimmen, das jede Partitur als Sinus singt."""
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "NAKUMO", "REINA"):
        (root / "model" / singer).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    calls = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        singer = os.path.basename(model_dir)
        calls.append((singer, style_shift))
        if singer == "NAKUMO":
            raise RuntimeError("NAKUMO ist kaputt")
        t = np.arange(48000 * 2) / 48000
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * t), 48000)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, calls


def test_every_installed_voice_sings_the_hook(tmp_path, voices):
    root, calls = voices
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root),
                     style_shift=1)
    seen = []
    auditions = casting.cast(s, lambda f, m: seen.append(m))
    assert [a.singer for a in auditions] == ["MERROW", "REINA"]        # NAKUMO singt nicht und fehlt
    assert sorted(calls) == [("MERROW", 2), ("NAKUMO", 2), ("REINA", 2)]   # wie im Refrain
    for a in auditions:
        audio, rate = sf.read(a.wav)
        assert audio.ndim == 2 and len(audio) > rate and np.max(np.abs(audio)) > 0.1
    assert any("REINA" in m for m in seen)


def test_casting_without_voices_says_so(tmp_path):
    s = SongSettings(output_ordner=str(tmp_path / "out"), neutrino_pfad=str(tmp_path / "fehlt"))
    os.makedirs(tmp_path / "fehlt" / "model")
    with pytest.raises(ValueError, match="Keine NEUTRINO-Stimme"):
        casting.cast(s)


def test_the_favorite_voice_follows_the_style(tmp_path, voices):
    root, _ = voices
    s = SongSettings(neutrino_pfad=str(root), style="Rock", singer="MERROW")
    casting.remember(s, "REINA")
    assert s.style_singers == {"Rock": "REINA"}
    assert casting.favorite(s).singer == "REINA"
    assert casting.favorite(s.with_updates(style="Ballade")).singer == "MERROW"
    assert casting.favorite(s.with_updates(style_singer=False)).singer == "MERROW"
    assert casting.favorite(s.with_updates(style_singers={"Rock": "KIRITAN"})).singer == "MERROW"   # nicht installiert


def test_casting_and_favorite_on_the_command_line(tmp_path, voices, monkeypatch):
    root, _ = voices
    SongSettings(neutrino_pfad=str(root), style_singers={"Rock": "REINA"}).save()
    seen = {}
    monkeypatch.setattr(casting, "cast", lambda s, progress=None: seen.setdefault("cast", s) and [])
    assert main.main(["--casting"]) == 0 and "cast" in seen

    def fake_generate(settings, progress=None, seed=None):
        seen["settings"] = settings
        return pipeline.SongResult(seed=1, output_dir=str(tmp_path), mix_wav=str(tmp_path / "final_mix.wav"))

    monkeypatch.setattr(main, "generate_song", fake_generate)
    assert main.main(["--style", "Rock"]) == 0 and seen["settings"].singer == "REINA"
    assert main.main(["--style", "Rock", "--stimme", "MERROW"]) == 0 and seen["settings"].singer == "MERROW"


# ── Gesangs-Check ──────────────────────────────────────────────────────────────
def test_the_check_names_engine_voice_version_and_graphics_card(tmp_path, monkeypatch):
    root = tmp_path / "NEUTRINO-windows-v3.2.2" / "NEUTRINO"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "NEUTRINO.exe").write_text("")
    s = SongSettings(neutrino_pfad=str(root))
    monkeypatch.setitem(vocal_synthesizer.LETZTER_LAUF, "grafikkarte", True)
    info = vocal_check.record(str(tmp_path), s, "NEUTRINO", "MERROW")
    assert vocal_check.read(str(tmp_path)) == info
    assert vocal_check.describe(info) == ("Gesungen von NEUTRINO 3.2.2, MERROW, Grafikkarte", False)
    monkeypatch.setitem(vocal_synthesizer.LETZTER_LAUF, "grafikkarte", False)
    assert "Prozessor" in vocal_check.describe(vocal_check.record(str(tmp_path), s, "NEUTRINO", "MERROW"))[0]
    text, warn = vocal_check.describe(vocal_check.record(str(tmp_path), s, "VOICEVOX", "ずんだもん"))
    assert text == "Gesungen von VOICEVOX, ずんだもん (NEUTRINO fehlte)" and not warn


def test_the_preview_voice_is_a_red_warning_unless_chosen(tmp_path):
    text, warn = vocal_check.describe(vocal_check.record(str(tmp_path), SongSettings(), "Vorschau"))
    assert warn and "Vorschau-Stimme" in text
    assert not vocal_check.describe(vocal_check.record(str(tmp_path), SongSettings(vocal_engine="Vorschau"),
                                                       "Vorschau"))[1]


def test_singing_writes_the_check(tmp_path, neutrino_attrappe):
    root, _ = neutrino_attrappe
    s = SongSettings(active_sections=["Chorus"], output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root),
                     harmonies=False, final_choir=False)
    tracks, _ = pipeline.compose(s)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    with open(os.path.join(s.output_dir(), vocal_check.SUNG_FILE), encoding="utf-8") as f:
        info = json.load(f)
    assert (info["engine"], info["voice"], info["device"]) == ("NEUTRINO", "MERROW", "Grafikkarte")


def test_the_fallback_to_the_preview_voice_is_recorded(tmp_path, monkeypatch):
    def preview(settings, tracks, wav):
        sf.write(wav, np.zeros(4800, dtype=np.float32), 48000)
        return True

    def missing(*a, **k):
        raise RuntimeError("fehlt")

    monkeypatch.setattr(pipeline, "_sing_preview", preview)
    monkeypatch.setattr(pipeline, "_sing_voicevox", missing)
    s = SongSettings(active_sections=["Chorus"], output_ordner=str(tmp_path / "out"),
                     neutrino_pfad=str(tmp_path / "kein"), phrase_expression=False, breaths=False, final_choir=False)
    tracks, _ = pipeline.compose(s)
    pipeline._synthesize_vocals(s, tracks, s.output_dir())
    assert vocal_check.describe(vocal_check.read(s.output_dir()))[1]


# ── NEUTRINO-Ausgabe (B7) ──────────────────────────────────────────────────────
def neutrino_at(tmp_path, *parts, readme=None, v2=False):
    root = tmp_path.joinpath(*parts)
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "NEUTRINO.exe").write_text("")
    if v2:
        (root / "bin" / "NSF.exe").write_text("")
    if readme:
        (root / "Readme.txt").write_text(readme, encoding="utf-8")
    return str(root)


def test_the_neutrino_version_is_found_and_old_ones_are_flagged(tmp_path):
    old = neutrino_at(tmp_path, "NEUTRINO-windows-v3.1", "NEUTRINO")
    assert vocal_synthesizer.neutrino_ausgabe(old) == "3.1"
    assert "älter als 3.2.2" in vocal_synthesizer.neutrino_hinweis(old)
    new = neutrino_at(tmp_path, "a", "NEUTRINO", readme="NEUTRINO Ver.3.2.2 (2025)")
    assert vocal_synthesizer.neutrino_ausgabe(new) == "3.2.2"
    assert vocal_synthesizer.neutrino_hinweis(new) == ""
    ex = neutrino_at(tmp_path, "NEUTRINO_v3.2.5", "NEUTRINO")
    assert "Tuning-Tool" in vocal_synthesizer.neutrino_hinweis(ex)
    unknown = neutrino_at(tmp_path, "Vloid_Songs-1.0.2", "NEUTRINO")
    assert vocal_synthesizer.neutrino_ausgabe(unknown) == "" and vocal_synthesizer.neutrino_hinweis(unknown) == ""
    assert "älter" in vocal_synthesizer.neutrino_hinweis(neutrino_at(tmp_path, "b", "NEUTRINO", v2=True))


# ── in der App ─────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def user(tmp_path):
    from gui import page
    SongSettings(output_ordner=str(tmp_path / "out"), seed=None, setup_wizard=False, update_check=False,
                 style="Rock").save()
    async with user_simulation(root=page.build) as user:
        yield user


async def until(condition, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    assert condition()


async def test_casting_in_the_app_remembers_the_voice_for_the_style(user, tmp_path, monkeypatch):
    def fake_cast(settings, progress=None):
        out = []
        for singer in ("MERROW", "REINA"):
            wav = tmp_path / f"{singer}.wav"
            sf.write(str(wav), np.zeros((2205, 2), dtype=np.float32), 22050)
            out.append(casting.Audition(singer, str(wav)))
        return out

    monkeypatch.setattr(casting, "cast", fake_cast)
    await user.open("/")
    user.find(marker="casting").click()
    await user.should_see(marker="cast-keep-REINA", retries=50)
    user.find(marker="cast-keep-REINA").click()
    await until(lambda: SongSettings.load().style_singers == {"Rock": "REINA"})
    assert SongSettings.load().singer == "REINA"

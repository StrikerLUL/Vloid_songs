# test_video_1110.py – „Das Video ist nicht so super“ (1.11.0)
#
# Grundlage war ein Lyric-Video aus 1.10.0 (Dark Vocaloid, Text „Mottenlicht“): oben stand „f“ als Titel, alle KI-Bilder
# zeigten dieselbe Gasse ohne Bezug zum Text (Flügel machten Blätter im Wind, das Licht der Laterne Sonnenschein), das
# Spektrum war eine graue Wand, ♭ stand dünn mit Lücke, der Sprechteil und der vierte Refrain des Texts wurden still
# nicht gesungen, und die zweite Strophe lag im Mix 5 dB tiefer unter der Band als die erste.
from types import SimpleNamespace

import numpy as np
import pytest

import bilder
import buildup
import lyric_helper
import musikvideo
import textmotive
import vocal_mix
import video_szenen as szenen
from parts import Ev
from settings import SongSettings
from test_app import fake_generation  # noqa: F401 – das Fixture gilt so auch hier
from test_video_171 import _fake_video, marked, until, user  # noqa: F401

RATE = 22050
MOTTENLICHT = """[Verse]
切れかけの 街灯で
> Unter der flackernden Straßenlaterne
銀の 鱗粉 まいて
硝子に 羽 ぶつけて

[Pre-Chorus]
熱いって 知ってるよ

[Chorus]
くるくる くるくる
狂うほど 回るの

[Sprechen]
ねえ どうして 目を閉じるの

[Chorus 4]
くるくる くるくる
"""


# ── Spektrum ──────────────────────────────────────────────────────────────────
def _music(seconds: float = 6.0) -> np.ndarray:
    """Bass, Akkord und Hi-Hat im Takt (120 BPM), dazu eine Sekunde Stille am Ende."""
    t = np.arange(int(RATE * seconds)) / RATE
    beat = (t % 0.5) < 0.12
    music = 0.5 * np.sin(2 * np.pi * 70 * t) * beat
    music += 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (440, 554, 659))
    rng = np.random.default_rng(3)
    music += 0.05 * rng.standard_normal(len(t)) * ((t % 0.25) < 0.03)
    music[int(RATE * (seconds - 1)):] = 0
    return music.astype(np.float32)


def test_the_spectrum_moves_and_shows_where_the_energy_is():
    seconds = 6.0
    sound = musikvideo.analyse(_music(seconds), RATE, int(seconds * musikvideo.FPS))
    playing = sound.bands[15:int((seconds - 1.2) * musikvideo.FPS)]
    edges = musikvideo.band_edges(RATE)
    chord, gap = np.searchsorted(edges, 554) - 1, np.searchsorted(edges, 2500) - 1
    # bis 1.10 wurde jedes Band auf sein eigenes Maximum gezogen: auch Bänder ohne Ton schlugen bis fast oben an,
    # alle Balken standen gleich hoch (eine Wand)
    assert playing[:, chord].max() > 0.8 > 0.3 > playing[:, gap].max()
    assert playing.max(axis=0).mean() < 0.6
    low = playing[:, :4].max(axis=0).mean()
    high = playing[:, -4:].max(axis=0).mean()
    assert low > high                                     # der Bass steht höher als die Luft
    assert playing[:, 0].std() > 0.15                     # und schlägt im Takt
    assert sound.bands[-3:].max() < 0.05                  # in der Stille am Ende fällt alles zusammen


def test_silence_gives_an_empty_spectrum():
    sound = musikvideo.analyse(np.zeros(RATE * 2, np.float32), RATE, 60)
    assert not sound.bands.any()


# ── Akkordnamen ───────────────────────────────────────────────────────────────
def test_flats_and_sharps_come_from_a_font_that_has_them():
    assert musikvideo.accidentals("B♭maj7", "Meiryo") == "B{\\fnSegoe UI Symbol}♭{\\fnMeiryo}maj7"
    assert musikvideo.accidentals("G#7", "Meiryo") == "G{\\fnSegoe UI Symbol}♯{\\fnMeiryo}7"
    assert musikvideo.accidentals("Am7", "Meiryo") == "Am7"


def test_the_chord_line_of_the_video_uses_the_symbol_font():
    import songkarte
    found = songkarte.Map(bpm=120, length=8.0, key="F", scale="major", chords=[(0.0, 4.0, "A#maj7"), (4.0, 8.0, "F")])
    scene = szenen.for_style("Ballade")
    text = musikvideo.ass([], scene, musikvideo.Options(), "Ballade", found=found, length=8.0)
    chord_lines = [line for line in text.splitlines() if ",Chord," in line]
    assert chord_lines and "{\\fnSegoe UI Symbol}♭" in chord_lines[0]


# ── Bilder aus dem Text ───────────────────────────────────────────────────────
def test_wings_are_no_wind_and_lamp_light_is_no_sunshine():
    assert set(textmotive.find("硝子に 羽 ぶつけて")) == {"window", "wings"}
    assert set(textmotive.find("切れかけの 街灯で")) == {"light"}
    assert "moth" in textmotive.find("銀の 鱗粉 まいて")
    assert "sun" not in textmotive.find("光の中で") and "light" in textmotive.find("光の中で")
    assert "wind" in textmotive.find("風が吹く")


def test_the_pictures_follow_the_text_of_each_section():
    from collections import Counter
    per_kind = {"Verse": Counter({"moth": 1, "window": 2, "light": 3, "night": 1}),
                "PreChorus": Counter({"fire": 2, "wings": 1}),
                "Chorus": Counter({"light": 2})}
    wanted = bilder.prompts("Dark Vocaloid", ["Intro", "Verse", "PreChorus", "Chorus"], per_kind,
                            ["light", "window", "moth", "fire"])
    assert "moths" in wanted["Verse"] and "embers" in wanted["PreChorus"]
    assert len(set(wanted.values())) == 4                 # vier Sektionen, vier verschiedene Bilder
    for prompt in wanted.values():
        assert "sunlight" not in prompt and "early light" not in prompt and "twilight" not in prompt
        assert prompt.count(", ") < 30


def test_night_and_sunshine_do_not_meet_in_one_picture():
    found = bilder.picked("Verse", {"Verse": {"night", "sun", "rain"}}, [])
    assert "night" in found and "sun" not in found
    assert "sun" not in bilder.picked("Verse", {"Verse": {"sun"}}, [], bilder.STYLE_PROMPTS["Dark Vocaloid"])
    assert "sun" in bilder.picked("Verse", {"Verse": {"sun"}}, [], bilder.STYLE_PROMPTS["J-Pop Energy"])


def test_moth_dust_is_drawn_and_keeps_out_of_the_text_band():
    painter = szenen.Painter(szenen.for_style("Dark Vocaloid"), 0.5, 3, tidy=True)
    frame = szenen.Frame(t=2.0, energy=0.8, motifs={"moth"})
    plain = szenen.Frame(t=2.0, energy=0.8)
    a, b = np.asarray(painter.frame(frame), np.int32), np.asarray(painter.frame(plain), np.int32)
    diff = np.abs(a - b).sum(axis=2)
    assert diff.sum() > 0
    lo, hi = szenen.TEXT_BAND
    assert diff[int(szenen.H * (lo + 0.05)):int(szenen.H * (hi - 0.05))].sum() == 0


# ── Name und ungesungener Text ────────────────────────────────────────────────
@pytest.mark.parametrize("text, name", [
    (MOTTENLICHT, "くるくる"),
    ("Titel: Mottenlicht\n" + MOTTENLICHT, "Mottenlicht"),
    ("# Mottenlicht\n[Verse]\nあ", "Mottenlicht"),
    ("[Refrain]\n君だけの 灯りに\n", "君だけの 灯りに"),
    ("[Chorus]\nい ま う た う よ\n", "いまうたうよ"),
    ("[Chorus]\n君[きみ]の 声\n", "君の 声"),
    ("[Verse]\n雨の 街を\n", "雨の 街を"),
    ("", ""),
])
def test_the_video_suggests_a_name_from_the_text(text, name):
    assert lyric_helper.title_suggestion(text) == name


def test_text_the_song_does_not_sing_is_named():
    s = SongSettings().with_updates(lyrics=MOTTENLICHT,
                                    active_sections=["Intro", "Verse", "PreChorus", "Chorus", "Chorus", "Chorus"])
    notes = lyric_helper.unused_notes(s)
    assert len(notes) == 2
    assert "Sprechen" in notes[0] and "nicht gesungen" in notes[0]
    assert "3× „Refrain“" in notes[1] and "4." in notes[1]
    helped = {sec.name: sec.note() for sec in lyric_helper.check(s)}
    assert "nicht gesungen" in helped["Spoken"] and "nicht gesungen" in helped["Chorus#4"]
    assert "nicht gesungen" not in helped["Verse"]
    everything = s.with_updates(active_sections=["Verse", "PreChorus", "Chorus", "Spoken", "Chorus", "Chorus",
                                                 "Chorus"])
    assert lyric_helper.unused_notes(everything) == []
    shared = everything.with_updates(numbered_lyrics=False)
    assert "Eigener Text für [Verse 2]" in lyric_helper.unused_notes(shared)[0]


# ── Gesang über der Band ──────────────────────────────────────────────────────
def _verse_below(seconds: float = 40.0, low_db: float = -5.0) -> tuple:
    """Gesang und Band (2, n): zwischen 20 und 30 s liegt der Gesang low_db tiefer als sonst (eine ganze Strophe)."""
    rate = 8000
    t = np.arange(int(rate * seconds)) / rate
    rng = np.random.default_rng(1)
    band = 0.1 * rng.standard_normal(len(t))
    vocal = 0.1 * np.sin(2 * np.pi * 800 * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))
    vocal[(t > 20) & (t < 30)] *= 10 ** (low_db / 20)
    return np.stack([vocal, vocal]).astype(np.float32), np.stack([band, band]).astype(np.float32), rate


def test_a_whole_verse_below_the_band_is_lifted_almost_fully():
    vocal, band, rate = _verse_below()
    gain = vocal_mix.ride_gain(vocal, band, rate)
    inside = 20 * np.log10(np.median(gain[int(22 * rate):int(28 * rate)]))
    outside = 20 * np.log10(np.median(gain[int(5 * rate):int(15 * rate)]))
    # bis 1.10 nur um 5 − 1,5 = 3,5 dB; jetzt fast um die ganzen 5 dB (höchstens RIDE_MAX_DB)
    assert inside - outside > 3.9
    assert abs(outside) < 1.0


def test_small_differences_still_stay():
    vocal, band, rate = _verse_below(low_db=-0.5)
    gain = vocal_mix.ride_gain(vocal, band, rate)
    assert np.abs(20 * np.log10(gain)).max() < 0.3


# ── Die Strophe atmet nach dem Refrain ────────────────────────────────────────
def _plan() -> SimpleNamespace:
    def sec(kind, start, bars, occurrence=1):
        return SimpleNamespace(kind=kind, occurrence=occurrence, bars=bars, feel="normal", start=start,
                               end=start + bars * 4.0, energy=0.7)
    return SimpleNamespace(sections=[sec("Intro", 0.0, 4), sec("Verse", 16.0, 8), sec("Chorus", 48.0, 8),
                                     sec("Verse", 80.0, 8, 2)])


def test_the_second_verse_breathes_after_the_chorus():
    plan = _plan()
    held_pad = Ev(76.0, 8.0, 64, 70)                 # Streicher aus dem Refrain, über die Grenze gehalten
    early_pad = Ev(82.0, 2.0, 64, 70)                # in den ersten zwei Takten der Strophe
    later_pad = Ev(88.0, 2.0, 64, 70)                # danach
    bells = Ev(80.0, 1.0, 84, 60)
    bass = Ev(80.0, 1.0, 40, 90)
    intro_pad = Ev(14.0, 4.0, 60, 70)                # vor der ersten Strophe (nach dem Intro): bleibt
    events = {"strings": [intro_pad, held_pad, early_pad, later_pad], "bells": [bells], "bass": [bass],
              "drums": [Ev(80.0, 0.2, 36, 100)]}
    assert buildup.breathe(plan, events) == [80.0]
    assert held_pad.dur == 4.0 and intro_pad.dur == 4.0
    assert events["strings"] == [intro_pad, held_pad, later_pad]
    assert events["bells"] == [] and events["bass"] == [bass] and len(events["drums"]) == 1


def test_apply_reports_the_breathing_verses():
    assert buildup.apply(_plan(), {})["breaths"] == [80.0]


# ── Oberfläche ────────────────────────────────────────────────────────────────
async def test_the_name_question_offers_the_hook_and_enter_takes_it(user, fake_generation, monkeypatch,  # noqa: F811
                                                                     tmp_path):
    import pipeline
    made = []
    monkeypatch.setattr(pipeline, "lyric_video", _fake_video(made, tmp_path))
    await user.open("/")
    marked(user, "lyrics")[0].set_value(MOTTENLICHT)
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    await user.should_see("Nicht alles aus deinem Text wird gesungen", retries=50)    # [Sprechen], [Chorus 4]
    user.find(marker="video").click()
    await user.should_see("Wie heißt der Song?", retries=50)
    assert marked(user, "video-name")[0].value == "くるくる"
    user.find(marker="video-name").trigger("keydown.enter")
    await until(lambda: made == [(1000, "くるくる", False)])


async def test_all_voice_sliders_go_back_to_the_defaults(user):  # noqa: F811
    await user.open("/")
    marked(user, "slider-vibrato")[0].set_value(1.6)
    marked(user, "slider-ornaments")[0].set_value(0.9)
    marked(user, "slider-verse_style_shift")[0].set_value(-3)
    await until(lambda: SongSettings.load().vibrato == 1.6 and SongSettings.load().ornaments == 0.9)
    user.find(marker="reset-voice-sliders").click()
    await user.should_see("Gesangsregler zurückgesetzt", retries=50)
    defaults = SongSettings()
    await until(lambda: (SongSettings.load().vibrato, SongSettings.load().ornaments,
                         SongSettings.load().verse_style_shift)
                == (defaults.vibrato, defaults.ornaments, defaults.verse_style_shift))


async def test_icon_buttons_are_named_for_screen_readers(user, fake_generation):  # noqa: F811
    await user.open("/")
    user.find(marker="generate").click()
    await user.should_see("Seed 1000", retries=50)
    await until(lambda: bool(marked(user, "history-edit")))
    assert marked(user, "history-edit")[0].props["aria-label"] == "Name und Notiz"
    assert marked(user, "history-video")[0].props["aria-label"].startswith("Lyric-Video")
    assert marked(user, "history-delete")[0].props["aria-label"] == "Song löschen"      # eigenes bleibt

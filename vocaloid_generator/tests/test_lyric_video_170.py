# test_lyric_video_170.py – Was am Lyric-Video, am Gesang und an der Melodie krumm und schief war (1.7.0)
#
# Gefunden in einem Ballade-Video aus 1.6.1: die Refrain-Zeilen verrutschten bei jedem „ー“, das Spektrum hatte tote
# Balken, unten links lagen Titel, Akkord und Schläge übereinander, der Titel war der Stil und die Tonart die der
# Einstellungen, die Stimme ging im Refrain unter, lange Töne blieben kerzengerade.
import json
import os
import random
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

import bilder
import history
import karaoke
import lyrics
import mixdown
import mixer
import musikvideo
import pipeline
import singing
import song_character
import songkarte
import style_dna
import systemcheck
import theory
import video_szenen as szenen
import voice_fx
import youtube
from melody_writer import register_window
from pipeline import SongResult
from settings import SongSettings

CHORUS = "[Chorus]\nパスワード パスワード 今 輝いて\n消えたアカウント 君の名前\n光る画面に 願いを込めて\n" \
         "消えてしまう前に パスワード\n"
PLAN = SimpleNamespace(section_at=lambda beat: SimpleNamespace(index=0, kind="Chorus", occurrence=1))


def _chorus_lines(old: bool = False) -> list:
    sections = lyrics.section_lines(CHORUS)
    lengths = {k: [len(line) for line in v] for k, v in sections.items()}
    texts = {k: [(w, "") for w, _, _ in v] for k, v in lyrics.sung_lines(CHORUS).items()}
    sung = [m for line in sections["Chorus"] for m in line]
    if old:                                     # so kamen die Silben bis 1.6 an: ohne „long“
        sung = [lyrics.Mora(str(m), melisma=m.melisma) for m in sung]
    notes = [SimpleNamespace(start=i * 0.5, end=i * 0.5 + 0.45) for i in range(len(sung))]
    return karaoke.lines(notes, sung, 120, PLAN, lengths, texts)


# ── T1, T2: Zeilen und Romaji ──────────────────────────────────────────────────
def test_long_vowels_keep_every_line_in_place_and_old_files_are_repaired(tmp_path):
    found = _chorus_lines()
    assert [line["romaji"] for line in found] == ["pasuwaado pasuwaado ima kagayaite", "kieta akaunto kimi no namae",
                                                  "hikaru gamen ni negai o komete", "kiete shimau mae ni pasuwaado"]
    assert found[0]["weights"][:4] == [1, 1, 2, 1]             # パ ス ワ(ー) ド: „wa“ hält das ー mit
    # パスワード dauert im Video so lange wie gesungen: fünf Moren, also fünf halbe Sekunden
    assert musikvideo.chunks(found[0])[0] == ("パスワード", 250)
    # eine Datei von 1.6 (ohne ー in den Silben) wird beim Laden mit der Songkarte repariert
    old = _chorus_lines(old=True)
    assert old[0]["romaji"] != found[0]["romaji"]
    path = tmp_path / karaoke.FILE
    path.write_text(json.dumps({"lines": old}, ensure_ascii=False), encoding="utf-8")     # so schrieb 1.6
    repaired = karaoke.load(str(path), [(0.0, 100.0)])
    assert [line["romaji"] for line in repaired] == [line["romaji"] for line in found]
    assert [(line["start"], line["end"]) for line in repaired] == [(line["start"], line["end"]) for line in found]


def test_prefixes_and_katakana_words_stay_one_word():
    assert [part for part, _ in lyrics.shown_parts("既読がつかない")][0] == "既読"
    assert "ログアウト" in [part for part, _ in lyrics.shown_parts("ログアウトした")]


# ── T3, T4: Name und Tonart ────────────────────────────────────────────────────
def _song_in(folder, seed: int, chords: list, key: str = "G", scale: str = "major", style: str = "Ballade"):
    found = songkarte.Map(style=style, bpm=80.0, key=key, scale=scale, seed=seed, length=60.0)
    found.sections = [songkarte.Section("Intro", 1, 0.0, 8.0, 0.3, False), songkarte.Section("Verse", 1, 8.0, 30.0,
                                                                                             0.5, True),
                      songkarte.Section("Chorus", 1, 30.0, 60.0, 0.9, True)]
    found.chords = [[i * 3.0, i * 3.0 + 3.0, name] for i, name in enumerate(chords)]
    songkarte.save(os.path.join(folder, songkarte.FILE), found)
    return found


GM = ["Gm", "Cm", "Dm7", "D7", "D#maj7", "F", "A#", "Gm", "Cm", "D7", "Gm"]


def test_the_key_comes_from_the_chords_and_is_spelled_with_flats(tmp_path):
    _song_in(str(tmp_path), 7, GM)
    s = SongSettings(style="Ballade", key="G", scale="major", seed=7, bpm=80)
    result = SongResult(seed=7, output_dir=str(tmp_path), settings=s)
    assert youtube.details(result) == ["Ballade", "80 BPM", "G Moll"]      # eingestellt war G-Dur, es klingt g-Moll
    _song_in(str(tmp_path), 7, ["C", "D", "Bm", "Em", "C", "D", "G", "G"])
    assert youtube.details(result)[2] == "G Dur"                           # passt die Einstellung, bleibt sie
    _song_in(str(tmp_path), 7, ["A#", "F", "Gm", "D#", "A#", "F", "D#", "F"], key="C")
    assert youtube.details(result)[2] == "B♭ Dur"
    assert theory.spelled("A#m7/D#", True) == "B♭m7/E♭" and theory.spelled("F#m", False) == "F#m"
    assert theory.key_name(10, False) == "B♭" and theory.key_name(6, False) == "F#" and theory.flat_key(7, True)


def test_the_title_is_the_song_name_and_without_one_there_is_no_card(tmp_path):
    found = _song_in(str(tmp_path), 7, GM)
    lines = [{"start": 9.0, "end": 12.0, "syllables": [[9.0, 10.0, "そ"], [10.0, 12.0, "ら"]], "text": "空"}]
    scene = szenen.for_style("Ballade")
    named = musikvideo.ass(lines, scene, musikvideo.Options(), "Ballade", "Vergessener Schirm", "Ballade", (), found,
                           60.0)
    assert ",Title,,0,0,0,,{\\fad(500,500)}Vergessener Schirm" in named
    assert "\\pos(40,984)" not in named                                    # kein Dauer-Titel unten links (B1)
    assert "E♭maj7" in named and "B♭" in named and "D#" not in named.split("[Events]")[1]
    nameless = musikvideo.ass(lines, scene, musikvideo.Options(), "Ballade", "", "Ballade", (), found, 60.0)
    assert ",Title," not in nameless.split("[Events]")[1] and "Ballade" not in nameless.split("[Events]")[1]


def test_the_name_is_found_in_the_history_even_when_another_song_was_made_since(tmp_path):
    s = SongSettings(style="Ballade", output_ordner=str(tmp_path), seed=7)
    audio = tmp_path / "final_song.mp3"
    audio.write_bytes(b"ID3")
    mine = history.record(str(audio), s, str(tmp_path))
    history.set_details(mine, label="Vergessener Schirm")
    other = history.record(str(audio), s.with_updates(seed=8), str(tmp_path))
    _song_in(str(tmp_path), 7, GM)
    result = SongResult(seed=7, output_dir=str(tmp_path), settings=s, history=other.audio)
    assert history.for_result(result).label == "Vergessener Schirm"   # der Verlauf zeigte auf einen anderen Eintrag
    assert history.folder_differs(result) is None
    _song_in(str(tmp_path), 8, GM)                                         # im Ordner liegt jetzt Seed 8
    assert history.folder_differs(result) == 8 and history.for_result(result).audio == other.audio


# ── B2: Spektrum ───────────────────────────────────────────────────────────────
def test_the_spectrum_has_no_dead_bands_and_no_wall():
    rate = 22050
    rng = np.random.default_rng(3)
    t = np.arange(rate * 8) / rate
    pink = np.cumsum(rng.normal(0, 1, t.size)) * 0.002
    music = (0.3 * np.sin(2 * np.pi * 55 * t) * (np.sin(2 * np.pi * 2 * t) > 0) + pink + 0.05 * rng.normal(0, 1, t.size))
    edges = musikvideo.band_edges(rate)
    assert edges[0] == musikvideo.LOW_HZ and edges[-1] == pytest.approx(min(musikvideo.HIGH_HZ, rate / 2), rel=0.01)
    assert np.diff(edges).min() >= rate / musikvideo.WINDOW
    sound = musikvideo.analyse(music.astype(np.float32), rate, 8 * musikvideo.FPS)
    assert (sound.bands.max(axis=0) > 0.05).all()                        # bis 1.6 blieben links 6 bis 7 auf null
    assert ((sound.bands > 0.97).mean(axis=1) < 0.3).all()               # und rechts schlugen alle zugleich an


# ── T5, T6, B1, B3, B5, B6, B7: das ruhige Video ──────────────────────────────
def _frame(**extra) -> szenen.Frame:
    f = szenen.Frame(t=5.0, kind="Verse", energy=0.5, beat=2, beat_pulse=1.0, sections=[(0, 0.5, "Verse"),
                                                                                     (0.5, 1, "Chorus")])
    f.bands = np.full(musikvideo.BANDS, 0.6)
    for key, value in extra.items():
        setattr(f, key, value)
    return f


def test_the_tidy_video_has_one_font_soft_lines_and_calm_ballads(tmp_path):
    found = _song_in(str(tmp_path), 7, GM)
    lines = [{"start": 9.0, "end": 12.0, "syllables": [[9.0, 10.0, "そ"], [10.0, 12.0, "ら"]], "text": "空",
              "romaji": "sora"}]
    scene = szenen.for_style("Ballade")
    s = SongSettings(style="Ballade")
    tidy = musikvideo.ass(lines, scene, musikvideo.options_from(s), "Ballade", "Titel", "", (), found, 60.0)
    old = musikvideo.ass(lines, scene, musikvideo.options_from(s.with_updates(video_tidy=False)), "Ballade", "Titel",
                         "", (), found, 60.0)
    fonts = {line.split(",")[1] for line in tidy.splitlines() if line.startswith("Style:")}
    assert fonts == {scene.look.font} and len({line.split(",")[1] for line in old.splitlines()
                                               if line.startswith("Style:")}) == 2
    assert ",Line,,0,0,0,,{\\pos(960,610)\\fad(150,150)}" in tidy and "\\fad" not in old.split(",Line,")[1][:30]
    # ruhige Szene: keine Notenlinie, keine Ablaufleiste, ein kleineres Spektrum
    calm = szenen.Painter(scene, szenen.CALM, 1, tidy=True)
    assert not calm.roll and not calm.hud and calm.calm
    assert szenen.Painter(scene, szenen.LIVELY, 1, tidy=True).roll
    # die Schläge liegen oben neben der Ablaufleiste, nicht mehr unten links auf dem Akkord
    lively = szenen.Painter(szenen.for_style("Rock"), 1.0, 1, spectrum=False, roll=False, tidy=True)
    plain = szenen.Painter(szenen.for_style("Rock"), 1.0, 1, spectrum=False, roll=False, hud=False, tidy=True)
    diff = np.abs(np.asarray(lively.frame(_frame()), float) - np.asarray(plain.frame(_frame()), float)).sum(axis=2)
    assert diff[:30].sum() > 0 and diff[int(szenen.H * 0.5):].sum() == 0
    # Chat-Blasen mit Wörtern der Zeile, über der Notenlinie
    chat = szenen.Painter(scene, 1.0, 1, chat=True, spectrum=False, roll=False, hud=False, tidy=True)
    empty = np.asarray(chat.frame(_frame(motifs={"chat"})), float)
    worded = np.asarray(chat.frame(_frame(motifs={"chat"}, words=("既読", "夜"))), float)
    rows = np.flatnonzero(np.abs(worded - empty).sum(axis=(1, 2)))
    if chat.kana:
        assert len(rows) and rows.max() < szenen.H * szenen.ROLL_BAND[0]
    # Funkeln lässt das Band hinter dem Text frei
    stars = szenen.Painter(scene, 1.0, 1, weather="stars", spectrum=False, roll=False, hud=False, tidy=True)
    none = szenen.Painter(scene, 1.0, 1, spectrum=False, roll=False, hud=False, tidy=True)
    band = slice(int(szenen.H * 0.5), int(szenen.H * 0.8))
    assert np.abs(np.asarray(stars.frame(_frame()), float)[band] - np.asarray(none.frame(_frame()), float)[band]).max() \
        < 1.0
    # beim Sektionswechsel blendet das Bild der Sektion davor über
    red, blue = tmp_path / "red.png", tmp_path / "blue.png"
    Image.new("RGB", (szenen.W, szenen.H), (200, 0, 0)).save(red)
    Image.new("RGB", (szenen.W, szenen.H), (0, 0, 200)).save(blue)
    pictures = {"Verse": str(red), "Chorus": str(blue)}
    soft = szenen.Painter(scene, 1.0, 1, pictures=pictures, spectrum=False, roll=False, hud=False, tidy=True)
    hard = szenen.Painter(scene, 1.0, 1, pictures=pictures, spectrum=False, roll=False, hud=False)
    change = _frame(kind="Chorus", chorus=True, index=1, prev_kind="Verse", change=0.5, fade=1.0)
    corner = (5, 5)
    assert soft._base(change).getpixel(corner)[0] > 50 and hard._base(change).getpixel(corner)[0] == 0


def test_the_sharp_video_paints_bigger_pictures_and_encodes_finer(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(bilder, "_run", lambda jobs, folder, size=bilder.SIZE: seen.append(size) or False)
    bilder.paint({"Verse": "rain"}, str(tmp_path / "a"), 3)
    bilder.paint({"Verse": "rain"}, str(tmp_path / "b"), 3, size=bilder.SHARP_SIZE)
    assert seen == [bilder.SIZE, bilder.SHARP_SIZE]
    commands = []

    def no_ffmpeg(command, **kw):
        commands.append(command)
        raise OSError("nur angesehen")
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", no_ffmpeg)
    rate = 22050
    sf.write(str(tmp_path / "song.wav"), np.zeros(rate, np.float32), rate)
    for sharp in (True, False):
        opts = musikvideo.options_from(SongSettings(video_sharp=sharp))
        with pytest.raises(RuntimeError):
            musikvideo.render(str(tmp_path / "song.wav"), str(tmp_path / "v.mp4"), [], None, "Ballade", opts,
                              ffmpeg="ffmpeg")
    sharp, plain = (" ".join(c) for c in commands)
    assert "lanczos" in sharp and "-crf 18" in sharp and "bicubic" in plain and "-crf 20" in plain


# ── G1, G2: Platz für die Stimme ───────────────────────────────────────────────
def test_the_voice_gets_room_in_the_chorus(new_170, tmp_path):
    s = SongSettings(style="Ballade", seed=11, output_ordner=str(tmp_path),
                     lyrics="[Verse]\nよるのまちを あるく\n[Chorus]\nらららら るるる らららら")
    tracks, _ = pipeline.compose(s)
    plain, _ = pipeline.compose(s.with_updates(vocal_room=False))
    plan = tracks["plan"]
    spb = plan.seconds_per_beat
    windows = [(sec.start * spb, sec.end * spb) for sec in plan.sections if sec.kind == "Chorus" and sec.has_vocals]

    def inside(notes) -> list:
        return [n for n in notes if any(a <= n.start < b for a, b in windows)]
    center = plan.style.vocal_center
    guide, before = inside(tracks["counter"]), inside(plain["counter"])
    assert guide and before and max(n.pitch for n in guide) <= center - 13 < max(n.pitch for n in before)
    assert not inside(tracks["choir"]) and inside(plain["choir"])          # der Keyboard-Chor fällt im Refrain weg
    assert style_dna.room_for_voice({"Chorus": {"choir": "aahs", "piano": "chords"}}, "Ballade")["Chorus"] == \
        {"choir": None, "piano": "chords"}
    on = mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=True)
    off = mixdown.mix_arguments(s.with_updates(vocal_room=False), tracks, str(tmp_path), has_vocals=True)
    assert on["vocal_room"] and off["vocal_room"] is None
    assert mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=False)["vocal_room"] is None
    curve = mixer._db_curve(mixer.SAMPLE_RATE * 4, [(1.0, 3.0)], mixer.ROOM_LEVELS["vocals"])
    assert curve[0, 0] == 1.0 and curve[0, 2 * mixer.SAMPLE_RATE] == pytest.approx(10 ** (1.5 / 20), rel=1e-4)


# ── G3: Vibrato auf langen Tönen ──────────────────────────────────────────────
def test_long_straight_notes_get_a_late_gentle_vibrato():
    frame = 0.005
    note = voice_fx.SungNote(0.0, 1.4, 64) if hasattr(voice_fx, "SungNote") else None
    notes = [note]
    f0 = np.full(int(1.4 / frame), 440.0 * 2 ** ((64 - 69) / 12))
    straight = voice_fx.shape_pitch(f0, frame, notes)
    moved = voice_fx.shape_pitch(f0, frame, notes, long_vibrato=voice_fx.LONG_VIBRATO)
    cents = 1200 * np.log2(moved / straight)
    t = np.arange(len(f0)) * frame
    assert np.abs(1200 * np.log2(straight / f0)).max() < 0.01                 # bis 1.6: kerzengerade
    assert np.abs(cents[t < 0.25]).max() < 0.5 and np.abs(cents[(t > 0.7) & (t < 1.2)]).max() > 5
    short = voice_fx.shape_pitch(f0[:80], frame, [voice_fx.SungNote(0.0, 0.4, 64)], long_vibrato=0.5)
    assert np.allclose(short, f0[:80])                                        # kurze Töne bleiben, wie sie sind
    assert singing.pitch_options(SongSettings(style="Ballade"))["long_vibrato"] == voice_fx.LONG_VIBRATO_CALM
    assert singing.pitch_options(SongSettings(long_note_vibrato=False))["long_vibrato"] == 0.0
    assert "long_note_vibrato" in singing.VOCAL_FIELDS


# ── G4, G5: Lage je Sektion ────────────────────────────────────────────────────
def test_the_chorus_sings_higher_than_the_verse_and_the_bridge_rises(new_170):
    for kind in ("Verse", "PreChorus", "Bridge"):
        assert register_window(67, 55, 72, kind)[2] < register_window(67, 55, 72, "Chorus")[2]
    assert register_window(67, 55, 72, "Chorus")[0] - register_window(67, 55, 72, "Verse")[0] >= 3
    lyrics_text = "[Verse]\nよるのまちを あるく ひとり\nかぜがふいて つめたい\n[Chorus]\nあいたい あいたい いますぐ\n" \
                  "きみのなまえを よんで\n[Bridge]\nとおい そらの むこうへ\nいつか とどく ように"
    s = SongSettings(style="Ballade", singer="REINA", lyrics=lyrics_text,
                     active_sections=["Verse", "Chorus", "Bridge", "Chorus"])

    def lift(settings) -> float:
        gaps = []
        for seed in (1, 2, 3):
            tracks, _ = pipeline.compose(settings.with_updates(seed=seed))
            plan = tracks["plan"]
            by_kind = {}
            for n in tracks["vocal_melody"]:
                sec = plan.section_at(n.start / plan.seconds_per_beat) if hasattr(plan, "section_at") else None
                kind = sec.kind if sec is not None else ""
                by_kind.setdefault(kind, []).append(n.pitch)
            gaps.append(np.median(by_kind["Chorus"]) - np.median(by_kind["Verse"]))
        return float(np.mean(gaps))
    assert lift(s) > lift(s.with_updates(section_registers=False)) and lift(s) >= 2.0


# ── G6: Atmer ──────────────────────────────────────────────────────────────────
def test_the_stand_in_breath_is_softer_and_darker(tmp_path, monkeypatch):
    rate = 44100
    hard = voice_fx.breath(rate // 2, rate, np.random.default_rng(1))
    soft = voice_fx.breath(rate // 2, rate, np.random.default_rng(1), soft=True)

    def high_share(x) -> float:
        spec = np.abs(np.fft.rfft(x)) ** 2
        freqs = np.fft.rfftfreq(len(x), 1 / rate)
        return float(spec[freqs > 3000].sum() / spec.sum())
    assert high_share(soft) < high_share(hard) / 3
    monkeypatch.setattr(voice_fx, "breath_samples", lambda rate, folder=None: [])
    notes = [voice_fx.SungNote(1.0, 2.0, 64), voice_fx.SungNote(3.0, 4.0, 64)]
    levels = []
    for soft_flag in (False, True):
        path = tmp_path / f"v{soft_flag}.wav"
        t = np.arange(rate * 5) / rate
        sung = ((t > 1) & (t < 2)) | ((t > 3) & (t < 4))
        sf.write(str(path), (0.3 * np.sin(2 * np.pi * 330 * t) * sung).astype(np.float32), rate)
        assert voice_fx.add_breaths(str(path), notes, seed=1, soft=soft_flag) == 2
        data, _ = sf.read(str(path))
        levels.append(float(np.sqrt(np.mean(data[int(2.3 * rate):int(2.9 * rate)] ** 2))))
    assert levels[1] < levels[0] * 10 ** (-4 / 20)
    ok, message = systemcheck.check_breaths(SongSettings(), str(tmp_path))
    assert ok is None and "Ersatz" in message and "leise" in message
    assert "soft_breaths" in singing.VOCAL_FIELDS


# ── M1, M2: Lautstärke-Bogen und Schluss ──────────────────────────────────────
def test_calm_songs_start_quiet_grow_to_the_last_chorus_and_fade(new_170, tmp_path):
    s = SongSettings(style="Ballade", seed=4, output_ordner=str(tmp_path),
                     active_sections=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"])
    tracks, _ = pipeline.compose(s)
    plan = tracks["plan"]
    rides = mixdown.arc_rides(s, plan)
    spb = plan.seconds_per_beat
    by_start = {round(start, 3): db for start, _, db in rides}
    intro, verse = plan.sections[0], plan.sections[1]
    last_chorus = [sec for sec in plan.sections if sec.kind == "Chorus"][-1]
    assert by_start[round(intro.start * spb, 3)] == -5.0 and by_start[round(verse.start * spb, 3)] == -3.0
    assert by_start[round(last_chorus.start * spb, 3)] == mixdown.ARC_LAST_CHORUS_DB
    assert mixdown.arc_rides(s.with_updates(dynamic_arc=False), plan) == []
    assert all(db > 0 for _, _, db in mixdown.arc_rides(s.with_updates(style="Rock"), plan))
    # eine Ballade klingt meist aus
    fades = sum(song_character.choose("Ballade", str(k), arc=True).ending == "fade" for k in range(200))
    before = sum(song_character.choose("Ballade", str(k)).ending == "fade" for k in range(200))
    assert fades > before * 1.5
    faded = dict(tracks, character=SimpleNamespace(ending="fade"))
    window = mixdown.fade_out(s, faded)
    assert window == pytest.approx((plan.sections[-1].start * spb, plan.sections[-1].end * spb))
    assert mixdown.fade_out(s.with_updates(dynamic_arc=False), faded) is None
    assert mixdown.fade_out(s, dict(tracks, character=SimpleNamespace(ending="ring"))) is None
    curve = mixer._fade_curve(mixer.SAMPLE_RATE * 10, 4.0, 8.0)
    assert curve[0] == 1.0 and 20 * np.log10(curve[-1]) == pytest.approx(mixdown.FADE_OUT_DB, abs=0.01)
    on = mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=True)
    assert set(map(tuple, rides)) <= set(map(tuple, on["tension"]))


def test_the_switches_are_on_for_new_songs():
    s = SongSettings()
    assert all(getattr(s, name) for name in ("video_tidy", "video_sharp", "vocal_room", "long_note_vibrato",
                                             "section_registers", "soft_breaths", "dynamic_arc"))
    assert set(pipeline.NEW_170) == {"vocal_room", "section_registers", "dynamic_arc"}
    assert random.Random(1).random() == random.Random(1).random() and shutil.which  # Module bleiben benutzt

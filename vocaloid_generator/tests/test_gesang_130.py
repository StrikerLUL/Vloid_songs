# test_gesang_130.py – Gesang 1.3.0: Tonhöhe glätten (G1), Härte zähmen (G2), Verzierungen (G3), Groove (G4),
# Gruppe (G5), Lesungen (G6), Sprechzeilen (G7), DiffSinger-Ausdruck (G8)
import os
import numpy as np
import pytest

import mixdown
import mixer
import resonance
from settings import SongSettings

SR = 44100


def _voice(seconds=4.0, boost_from=2.0, f0=440.0):
    """Eine Stimme aus Obertönen; ab boost_from sticht der Bereich um 3,5 kHz deutlich heraus."""
    t = np.arange(int(SR * seconds)) / SR
    out = np.zeros_like(t)
    for h in range(1, 40):
        f = f0 * h
        if f > 16000:
            break
        amp = 1 / h * (np.where(t > boost_from, 6.0, 1.0) if 3200 < f < 3800 else 1.0)
        out += amp * np.sin(2 * np.pi * f * t)
    return np.stack([out, out]).astype(np.float32) * 0.1


def _band_db(audio, lo, hi, part):
    seg = audio[0, part]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)
    return 10 * np.log10(spec[(freqs > lo) & (freqs < hi)].sum())


@pytest.fixture
def tamer(monkeypatch):
    monkeypatch.setattr(resonance, "MAX_CUT_DB", 6.0)      # conftest.py schaltet es ab


def test_only_what_sticks_out_gets_quieter(tamer):
    voice = _voice()
    tamed = resonance.tame(voice, SR)
    calm, harsh = slice(SR // 2, SR + SR // 2), slice(5 * SR // 2, 7 * SR // 2)
    assert _band_db(tamed, 3200, 3800, harsh) - _band_db(voice, 3200, 3800, harsh) < -2.0
    for lo, hi in ((800, 1400), (5500, 7000)):
        assert abs(_band_db(tamed, lo, hi, harsh) - _band_db(voice, lo, hi, harsh)) < 0.5
    assert abs(_band_db(tamed, 3200, 3800, calm) - _band_db(voice, 3200, 3800, calm)) < 0.5
    assert tamed.shape == voice.shape
    quiet = voice * 0.0
    assert resonance.tame(quiet, SR) is quiet


def test_the_mix_tames_the_voice_only_with_the_switch(tamer, tmp_path, monkeypatch):
    s = SongSettings(output_ordner=str(tmp_path))
    assert mixdown.mix_arguments(s, {}, str(tmp_path), has_vocals=True)["tame"] is True
    assert mixdown.mix_arguments(s.with_updates(resonance_tamer=False), {}, str(tmp_path), has_vocals=True)["tame"] \
        is False
    import soundfile as sf
    path = tmp_path / "vocals.wav"
    sf.write(str(path), _voice().T, SR)
    calls = []
    real = resonance.tame
    monkeypatch.setattr(resonance, "tame", lambda a, r: calls.append(len(a[0])) or real(a, r))
    mixer.mische_spuren([str(path)], output_pfad=str(tmp_path / "mix.wav"), tame=True)
    mixer.mische_spuren([str(path)], output_pfad=str(tmp_path / "mix2.wav"), tame=False)
    assert len(calls) == 1


# ── G6: Wörter richtig lesen ────────────────────────────────────────────────────
@pytest.fixture
def smart(monkeypatch):
    import readings
    monkeypatch.setattr(readings, "ACTIVE", True)


def test_particles_and_number_words_are_sung_like_spoken(smart):
    import pipeline
    text = "[Verse]\nきみは そらへ\nわたしははしる\n[Chorus]\nもう一回 三本の花\n明日も一歩ずつ\nゆめをみた"
    sung = pipeline.sung_lyrics(SongSettings(lyrics=text))
    assert "".join(sung["Verse"]) == "きみわそらえわたしわはしる"     # は in はしる gehört zum Verb
    assert "".join(sung["Chorus"]) == "もういっかいさんぼんのはなあしたもいっぽずつゆめおみた"
    written = pipeline.sung_lyrics(SongSettings(lyrics=text, smart_readings=False))
    assert "".join(written["Verse"]) == "きみはそらへわたしははしる"
    assert "".join(written["Chorus"]).startswith("もういちかい")


def test_spaced_kana_keep_their_syllables_and_only_true_particles_change(smart):
    from lyrics import syllables
    assert syllables("な に か が は じ ま る", smart=True) == list("なにかがはじまる")
    assert syllables("ふ り む か な い で は し り だ せ", smart=True) == list("ふりむかないではしりだせ")
    assert syllables("き み は そ ら へ", smart=True) == list("きみわそらえ")


def test_numbers_and_counters_follow_the_sound_changes():
    from readings import respell
    pairs = {"十回": "じゅっかい", "三十分": "さんじゅっぷん", "十分": "じゅうぶん", "六本": "ろっぽん", "何匹": "なんびき",
             "三階": "さんがい", "四分": "よんぷん", "三百回": "さんびゃっかい", "一ヶ月": "いっかげつ",
             "精一杯": "精一杯", "唯一本気": "唯一本気", "一回り": "ひとまわり", "千本桜": "せんぼんざくら"}
    assert {word: respell(word) for word in pairs} == pairs


def test_own_readings_from_the_file_always_apply(tmp_path):
    import config
    import pipeline
    import readings
    text = "[Verse]\n星空の下 Tokyo"
    assert readings.own_readings() == {}
    readings.ensure_file()
    assert readings.own_readings() == {}          # die Anleitung allein ändert nichts
    with open(readings.path(), "a", encoding="utf-8") as f:
        f.write("星空=ほしぞら\nTokyo = トウキョウ\nkaputt\n")
    assert readings.path().startswith(config.DATA_DIR)
    assert readings.own_readings() == {"星空": "ほしぞら", "Tokyo": "とうきょう"}
    sung = pipeline.sung_lyrics(SongSettings(lyrics=text, smart_readings=False))
    assert "".join(sung["Verse"]) == "ほしぞらのしたとうきょう"


def test_the_text_helper_shows_what_was_read_differently(smart, tmp_path):
    import lyric_helper
    import readings
    with open(readings.ensure_file(), "a", encoding="utf-8") as f:
        f.write("星空=ほしぞら\n")
    s = SongSettings(lyrics="[Verse]\nきみは 星空へ\nもう一回だけ\nよるのまち")
    lines = lyric_helper.check(s)[0].lines
    assert [line.changes for line in lines] == [[("星空", "ほしぞら"), ("は", "わ"), ("へ", "え")],
                                                [("一回", "いっかい")], []]
    off = lyric_helper.check(s.with_updates(smart_readings=False))[0].lines
    assert [line.changes for line in off] == [[("星空", "ほしぞら")], [], []]


# ── G1 Tonhöhe glätten, G3 Verzierungen ────────────────────────────────────────────
FRAME = 0.005


def _sung(notes, cents, vibrato=0.3, seconds=None):
    """Eine gesungene Tonhöhenkurve (Hz je FRAME): jeder Ton um cents daneben, mit Vibrato und kurzen Übergängen."""
    end = seconds or notes[-1].end
    t = np.arange(int(end / FRAME)) * FRAME
    midi = np.zeros_like(t)
    for n, off in zip(notes, cents):
        sel = (t >= n.start) & (t < n.end)
        midi[sel] = n.pitch + off / 100 + vibrato * np.sin(2 * np.pi * 5.5 * (t[sel] - n.start))
    for a, b in zip(notes, notes[1:]):                 # 40 ms Übergang
        sel = (t >= b.start - 0.02) & (t < b.start + 0.02)
        midi[sel] = np.linspace(midi[np.searchsorted(t, b.start - 0.02) - 1], midi[np.searchsorted(t, b.start + 0.02)],
                                sel.sum())
    return 440.0 * 2 ** ((midi - 69) / 12), t


def test_off_pitch_notes_are_pulled_in_and_vibrato_and_glides_stay():
    import singing
    import voice_fx
    notes = [voice_fx.SungNote(0.0, 1.0, 60), voice_fx.SungNote(1.0, 2.0, 62), voice_fx.SungNote(2.0, 3.0, 64)]
    f0, t = _sung(notes, [45, 10, -35])
    before = voice_fx.intonation_error(f0, FRAME, notes)
    assert before == pytest.approx([45, 10, -35], abs=3)
    full = voice_fx.shape_pitch(f0, FRAME, notes, intonation=1.0)
    after = voice_fx.intonation_error(full, FRAME, notes)
    assert abs(after[0]) < 3 and abs(after[2]) < 3, "zu weit danebenliegende Töne landen auf der Note"
    assert after[1] == pytest.approx(10, abs=2), "kleine Abweichungen bleiben, wie gesungen"
    half = voice_fx.intonation_error(voice_fx.shape_pitch(f0, FRAME, notes, intonation=0.5), FRAME, notes)
    assert half[0] == pytest.approx(22.5, abs=3)
    midi = lambda hz: 69 + 12 * np.log2(hz / 440.0)         # noqa: E731
    inside = (t > 0.3) & (t < 0.7)
    wobble = lambda x: np.std(x - np.mean(x))              # noqa: E731
    assert wobble(midi(full[inside])) == pytest.approx(wobble(midi(f0[inside])), rel=0.05), "das Vibrato bleibt"
    edge = (t > 1.0) & (t < 1.0 + voice_fx.GLIDE_ZONE * 0.5)
    assert np.allclose(full[edge], f0[edge], rtol=1e-3), "der Übergang bleibt"
    # in der App: 0,5 ab Werk, 0 = aus; ohne Änderung (auch ohne das Vibrato auf langen Tönen aus 1.7.0) bleibt die
    # Aufnahme unberührt
    assert singing.pitch_options(SongSettings())["intonation"] == 0.5
    off = singing.pitch_options(SongSettings(intonation=0.0, ornaments=0.0, long_note_vibrato=False))
    assert voice_fx.reshape("fehlt.wav", notes, **off) is False
    assert np.allclose(voice_fx.shape_pitch(f0, FRAME, notes, **{**off, "seed": 0}), f0)


def test_ornaments_scoop_fall_and_turn_and_follow_the_style(monkeypatch):
    import diffsinger
    import singing
    import voice_fx
    for name in ("SHAKURI", "FALL", "KOBUSHI"):
        monkeypatch.setattr(voice_fx, name, getattr(voice_fx, name)[:3] + (1.0,))
    notes = [voice_fx.SungNote(0.0, 0.5, 60), voice_fx.SungNote(0.5, 1.5, 65), voice_fx.SungNote(1.5, 2.5, 64)]
    kinds = [(kind, n.pitch) for kind, n in voice_fx.ornaments(notes, 1.0)]
    assert ("shakuri", 65) in kinds and ("fall", 64) in kinds and ("kobushi", 65) in kinds
    assert ("shakuri", 64) not in kinds, "kein Schleifer nach einem Schritt abwärts"
    t = np.arange(0, 2.5, FRAME)
    curve = voice_fx.ornament_curve(t, notes, 1.0)
    at = lambda s: curve[int(round(s / FRAME))]            # noqa: E731
    assert at(0.51) < -1.0, "Shakuri: von unten in den Ton"
    assert at(0.5 + 0.3 + 0.03) > 0.3, "Kobushi: kleiner Schnörkel nach oben"
    assert at(2.49) < -2.5 and at(2.0) == 0.0, "Fall am Phrasenende"
    assert np.all(voice_fx.ornament_curve(t, notes, 0.0) == 0)
    assert np.array_equal(curve, voice_fx.ornament_curve(t, notes, 1.0)), "gleiche Töne, gleiche Verzierungen"
    f0, _ = _sung(notes, [0, 0, 0], vibrato=0.0)
    shaped = voice_fx.shape_pitch(f0, FRAME, notes, ornaments=0.5)
    sel = slice(int(0.5 / FRAME), int(0.6 / FRAME))
    assert np.all(shaped[sel] <= f0[sel] + 1e-6) and shaped[sel].min() < f0[sel].min() * 0.97
    # DiffSinger bekommt dieselben Verzierungen in seine Tonhöhe
    phrase = [(n.start, n.end, n.pitch, "ら") for n in notes]
    plain = diffsinger.pitch_curve(phrase, t, vibrato=0.0)
    assert diffsinger.pitch_curve(phrase, t, vibrato=0.0, ornaments=1.0) == pytest.approx(plain + curve)
    # je Stil dosiert, ab Werk dezent
    assert voice_fx.ornament_amount(0.35, "Kawaii Chiptune") == 0.0
    assert voice_fx.ornament_amount(0.35, "Ballade") > voice_fx.ornament_amount(0.35, "Idol-Pop") > 0
    assert singing.pitch_options(SongSettings(style="Ballade"))["ornaments"] == pytest.approx(0.35 * 1.6)
    assert singing.pitch_options(SongSettings(style="Ballade", ornaments=0.0))["ornaments"] == 0.0


# ── G4 Gesang im Groove ──────────────────────────────────────────────────────────
def test_the_voice_sits_behind_or_ahead_of_the_beat_by_style(tmp_path):
    import soundfile as sf

    import singing
    rate = 48000

    def click():
        for name in ("vocals.wav", "vocals_harmony.wav"):
            x = np.zeros(rate * 2, dtype=np.float32)
            x[rate] = 1.0
            sf.write(tmp_path / name, x, rate, subtype="FLOAT")

    def where(name="vocals.wav"):
        x, _ = sf.read(tmp_path / name)
        return int(np.argmax(np.abs(x))) / rate

    for style, expected in (("Lo-Fi", 1.024), ("Rock", 0.99), ("J-Pop Energy", 1.0)):
        click()
        singing._vocal_pocket(SongSettings(style=style), str(tmp_path))
        assert where() == pytest.approx(expected, abs=1e-4) and where("vocals_harmony.wav") == where()
    click()
    singing._vocal_pocket(SongSettings(style="Lo-Fi", vocal_pocket=False), str(tmp_path))
    assert where() == 1.0
    assert singing.vocal_pocket_ms(SongSettings(style="City Pop")) > 0 > \
        singing.vocal_pocket_ms(SongSettings(style="Drum and Bass"))


# ── G5 Gruppe ────────────────────────────────────────────────────────────────────
def test_a_group_sings_the_chorus_together_and_the_verses_in_turn(tmp_path, monkeypatch):
    import soundfile as sf

    import pipeline
    import singing
    from melody_writer import group_turns, split_for_group
    root = tmp_path / "NEUTRINO"
    for name in ("MERROW", "NAKUMO", "REINA"):
        (root / "model" / name).mkdir(parents=True)
    s = SongSettings(output_ordner=str(tmp_path / "out"), seed=3, neutrino_pfad=str(root), singer="REINA",
                     group_vocals=3, structure=["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus",
                                                "Chorus", "Bridge", "Chorus", "Outro"])
    assert singing._group_members(s, str(root)) == ["REINA", "MERROW", "NAKUMO"]
    assert singing._group_members(s.with_updates(group_vocals=0), str(root)) == []
    (root / "model" / "NAKUMO").rmdir()
    assert singing._group_members(s, str(root)) == [], "mit zwei Stimmen keine Gruppe"
    (root / "model" / "NAKUMO").mkdir()
    tracks, _ = pipeline.compose(s)
    plan = tracks["plan"]
    turns = {(sec.kind, sec.occurrence): turns for sec in plan.sections
             if (turns := group_turns(plan, 3).get(sec.index, "-")) != "-"}
    assert turns == {("Verse", 1): 0, ("PreChorus", 1): 0, ("Chorus", 1): None, ("Verse", 2): 1,
                     ("PreChorus", 2): 1, ("Chorus", 2): None, ("Bridge", 1): 2, ("Chorus", 3): None}
    parts = split_for_group(plan, tracks["melody_data"], tracks["silben"], 3)
    sung = [sum(1 for p, _ in data if p is not None) for data, _ in parts]
    chorus = sum(1 for n in tracks["vocal_melody"] if plan.section_at(n.start / plan.seconds_per_beat).kind == "Chorus")
    assert all(n > chorus for n in sung) and sum(sung) == len(tracks["silben"]) + 2 * chorus
    assert [len(silben) for _, silben in parts] == sung
    # jede Stimme singt ihren Teil mit eigenem Ton; im Refrain stehen sie links, Mitte, rechts
    tones = {"REINA": 300.0, "MERROW": 500.0, "NAKUMO": 700.0}

    def lead(settings, data, xml, wav, neutrino_dir, singer, *args):
        rate, t, audio = 48000, 0.0, np.zeros(int(plan.total_beats * plan.seconds_per_beat * 48000) + 48000)
        for pitch, dur in data:
            a, b = int(t * plan.seconds_per_beat * rate), int((t + dur) * plan.seconds_per_beat * rate)
            if pitch is not None:
                audio[a:b] = 0.2 * np.sin(2 * np.pi * tones[singer] * np.arange(b - a) / rate)
            t += dur
        sf.write(wav, audio, rate)
    monkeypatch.setattr(singing, "_neutrino_lead", lead)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    singing._sing_group(s, tracks, str(out), str(root), ["REINA", "MERROW", "NAKUMO"], str(out / "vocals.wav"))
    audio, rate = sf.read(out / "vocals.wav", always_2d=True)

    def level(sec, hz, channel):
        part = audio[int(sec.start * plan.seconds_per_beat * rate):int(sec.end * plan.seconds_per_beat * rate),
                     channel]
        spec = np.abs(np.fft.rfft(part))
        freqs = np.fft.rfftfreq(len(part), 1 / rate)
        return spec[np.abs(freqs - hz) < 3].max() / len(part)
    verse2 = next(sec for sec in plan.sections if sec.kind == "Verse" and sec.occurrence == 2)
    bridge = next(sec for sec in plan.sections if sec.kind == "Bridge")
    chorus1 = next(sec for sec in plan.sections if sec.kind == "Chorus")
    assert level(verse2, 500, 0) > 20 * level(verse2, 300, 0) and level(verse2, 500, 0) == \
        pytest.approx(level(verse2, 500, 1), rel=0.05), "die zweite Strophe singt MERROW allein, in der Mitte"
    assert level(bridge, 700, 0) > 20 * level(bridge, 500, 0)
    assert all(level(chorus1, hz, 0) > 0 for hz in tones.values())
    assert level(chorus1, 500, 0) > 1.5 * level(chorus1, 500, 1), "MERROW steht im Refrain links"
    assert level(chorus1, 700, 1) > 1.5 * level(chorus1, 700, 0), "NAKUMO steht rechts"
    assert level(chorus1, 300, 0) == pytest.approx(level(chorus1, 300, 1), rel=0.05)
    assert not [p for p in out.iterdir() if "gruppe" in p.name], "die einzelnen Stimmen werden aufgeräumt"


# ── G7 Sprechen ─────────────────────────────────────────────────────────────────
from test_rap import RAP_HZ, FakeTalk, fake_talk, level_at, song, sung_notes  # noqa: E402, F401


def _spoken_song(tmp_path, root, url, **kw):
    return song(tmp_path, root, url, active_sections=["Verse", "Spoken"], section_bars={"Verse": 4, "Spoken": 4},
                lyrics="[Verse]\nよ る の ま ち\n[Sprechen]\nき み の な ま え を よ ん だ", **kw)


def test_a_spoken_line_is_said_freely_with_hall_or_left_out_without_voicevox(tmp_path, neutrino_attrappe, fake_talk):
    import pipeline
    import spoken
    from lyrics import parse_lyrics
    assert set(parse_lyrics("[Sprechen]\nき み\n[Gesprochen 2]\nあ さ")) == {"Spoken", "Spoken#2"}
    root, _ = neutrino_attrappe
    s = _spoken_song(tmp_path, root, fake_talk)
    tracks = pipeline.compose(s)[0]
    plan = tracks["plan"]
    said = next(sec for sec in plan.sections if sec.kind == "Spoken")
    assert not [n for n in tracks["drums"] if said.start <= n.start / plan.seconds_per_beat < said.end - 0.01], \
        "unter dem Sprechen schweigt das Schlagzeug"
    assert spoken.lines(tracks["melody_data"], tracks["silben"], spoken.windows(plan))[0][2] == "きみのなまえをよんだ"
    pipeline.generate_song(s, keep_history=False)
    out = s.output_dir()
    verse = [n for n in tracks["vocal_melody"] if n.start < said.start * plan.seconds_per_beat]
    assert len(sung_notes(out)) == len(verse), "NEUTRINO singt die gesprochene Zeile nicht"
    assert [r[2] for r in FakeTalk.requests if r[0] == "/audio_query"] == ["きみのなまえをよんだ"]
    vocals = os.path.join(out, "vocals.wav")
    spb = plan.seconds_per_beat
    begin = (said.start + spoken.START) * spb
    assert level_at(vocals, RAP_HZ, begin, said.end * spb) > 20 * level_at(vocals, RAP_HZ, 0.3, said.start * spb)
    # Hall verlängert die Zeile, Telefon nimmt die Tiefen
    rate = 48000
    x = np.zeros(rate, dtype=np.float32)
    x[:rate // 4] = np.sin(2 * np.pi * 150 * np.arange(rate // 4) / rate) + np.sin(2 * np.pi * 1000 *
                                                                                    np.arange(rate // 4) / rate)
    hall, phone = spoken.sound(x, rate, "Hall"), spoken.sound(x, rate, "Telefon")
    assert len(hall) > len(x) and np.abs(hall[rate // 4 + rate // 2:rate]).max() > 1e-3
    spec = np.abs(np.fft.rfft(phone[:rate // 4]))
    freqs = np.fft.rfftfreq(rate // 4, 1 / rate)
    assert spec[np.abs(freqs - 150) < 5].max() < 0.2 * spec[np.abs(freqs - 1000) < 5].max()
    assert np.array_equal(spoken.sound(x, rate, "trocken"), x)
    assert spoken.speed_for(3.0, 2.0) == 1.5 and spoken.speed_for(1.0, 2.0) == 1.0 and \
        spoken.speed_for(9.0, 2.0) == spoken.MAX_SPEED
    # ohne VOICEVOX fällt die Zeile weg, NEUTRINO singt sie trotzdem nicht
    s = _spoken_song(tmp_path / "b", root, "http://127.0.0.1:9", spoken_sound="Telefon")
    pipeline.generate_song(s, keep_history=False)
    assert len(sung_notes(s.output_dir())) == len(verse)
    import main
    assert main.parse_args(["--sprechen-klang", "Telefon"]).sprechen_klang == "Telefon"


# ── G8 DiffSinger-Ausdruck ───────────────────────────────────────────────────────
def test_diffsinger_breathes_in_the_verse_and_pushes_in_the_chorus(tmp_path):
    import diffsinger
    import singing
    from lyrics import Mora
    times = np.arange(0, 4, 0.01)
    phrase = [(0.0, 1.0, 60, "ら"), (1.0, 1.4, 67, "ら"), (2.0, 3.0, 60, "ら")]
    extra = diffsinger.expression(phrase, times, [(0.0, 2.0, "Verse"), (2.0, 4.0, "Chorus")])
    at = lambda name, s: extra[name][int(round(s * 100))]   # noqa: E731
    assert at("breathiness", 0.2) == pytest.approx(6.0) and at("breathiness", 2.2) == pytest.approx(-3.0)
    assert at("tension", 2.2) == pytest.approx(2.5) and at("energy", 2.2) > at("energy", 0.2)
    assert at("tension", 1.2) > at("tension", 0.2), "hohe Töne gespannter"
    assert at("breathiness", 0.95) > at("breathiness", 0.4), "lange Töne werden zum Ende hauchiger"
    # im Song: der Refrain kommt mit mehr Energie im akustischen Modell an
    from test_diffsinger import PHONEMES, acoustic, variance
    root = tmp_path / "ou"
    bank = root / "Singers" / "Probe"
    bank.mkdir(parents=True)
    import test_diffsinger as ds
    (bank / "phonemes.txt").write_text("\n".join(PHONEMES), encoding="utf-8")
    (bank / "dsdict.yaml").write_text(ds.DSDICT, encoding="utf-8")
    (bank / "dsconfig.yaml").write_text(
        f"phonemes: phonemes.txt\nacoustic: acoustic.onnx\nvocoder: nsf_hifigan\nsample_rate: {ds.RATE}\n"
        f"hop_size: {ds.HOP}\nnum_mel_bins: {ds.BINS}\nuse_energy_embed: true\n", encoding="utf-8")
    acoustic(bank / "acoustic.onnx", energy=True)
    voc = root / "Dependencies" / "nsf_hifigan"
    voc.mkdir(parents=True)
    ds.vocoder(voc / "model.onnx")
    (voc / "vocoder.yaml").write_text(f"model: model.onnx\nsample_rate: {ds.RATE}\nhop_size: {ds.HOP}\n"
                                      f"num_mel_bins: {ds.BINS}\n", encoding="utf-8")
    folder = bank / "dsvariance"
    folder.mkdir()
    (folder / "phonemes.txt").write_text("\n".join(PHONEMES), encoding="utf-8")
    (folder / "dsconfig.yaml").write_text(f"phonemes: phonemes.txt\nlinguistic: linguistic.onnx\n"
                                          f"variance: variance.onnx\nsample_rate: {ds.RATE}\nhop_size: {ds.HOP}\n",
                                          encoding="utf-8")
    variance(folder)
    import soundfile as sf
    wav = str(tmp_path / "vocals.wav")
    diffsinger.sing([(None, 2.0), (69, 1.0)], [Mora("さ")], 120, wav, str(bank), vibrato=0.0,
                    expression=[(0.0, 1.2, "Verse"), (1.2, 3.0, "Chorus")])
    audio, rate = sf.read(wav)
    assert audio[int(1.1 * rate)] == pytest.approx(0.44 - 0.00115, abs=1e-5)     # Energie −10 −1,5
    assert audio[int(1.4 * rate)] == pytest.approx(0.44 - 0.00085, abs=1e-5)     # Energie −10 +1,5
    diffsinger.sing([(None, 2.0), (69, 1.0)], [Mora("さ")], 120, wav, str(bank), vibrato=0.0)
    assert sf.read(wav)[0][int(1.4 * rate)] == pytest.approx(0.44 - 0.001, abs=1e-5)
    # der Schalter
    tracks = {"plan": type("P", (), {"sections": [], "seconds_per_beat": 0.5})()}
    assert singing._diffsinger_expression(SongSettings(), tracks) == []
    assert singing._diffsinger_expression(SongSettings(diffsinger_expression=False), tracks) is None
